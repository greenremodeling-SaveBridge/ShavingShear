"""
운영 변화(구조 변화) 자동 탐지 + 기온 보정 이상 점수  (2026-10-23 추가)

목적
  - "공사 직전 36개월" 같은 기저선 구간을 사람이 정하지 않아도, 건물의 운영이 언제 바뀌었는지를
    데이터에서 찾아 내고, 지금 쓰는 학습 구간이 그 변화 '이후'인지 확인한다.
  - "같은 달 과거 평균의 1.8배" 규칙은 올해가 유난히 추워서 많이 쓴 달도 이상으로 잡는다.
    기온(HDD/CDD)의 영향을 먼저 빼고 남은 부분(잔차)이 평소보다 얼마나 벗어났는지로 다시 본다.

이 모듈은 기존 계산(기저선 회귀·판정·정산)을 바꾸지 않는다. baseline.run_baseline 이
결과 딕셔너리에 새 키(regime_shift, anomalies_adjusted)만 덧붙인다. 여기서 예외가 나도
기존 결과는 그대로 나간다(baseline 쪽에서 try/except).

방법
  1) 연료(가스·전기·합계)별로 일평균 사용량(월 합계 ÷ 일수)을 HDD·CDD 로 설명하는 선형회귀를,
     데이터 맨 앞 24개월(기준 상태)로 학습한다.
  2) 그 모델로 이후 모든 달의 잔차를 구하고, 기준 구간 잔차의 로버스트 표준편차(MAD)로 나눠 z 로 만든다.
  3) 단측 CUSUM (k = 1.0σ, h = 5σ) 으로 위·아래 지속적 이동이 있는지 본다. 처음 경보가 난 달이 alarm.
  4) 경보가 났으면, 기준 구간 이후 모든 달을 후보로 '수준 이동(step) + HDD + CDD' 회귀의 오차가 가장 작아지는 달을
     변화 시작월(onset)로 정한다. 수준 이동을 넣어도 오차가 충분히(30% 이상) 줄지 않으면 잡음으로 보고 버린다.
  5) 변화 크기 = step 계수 ÷ 기준 구간 평균 일사용량 (기온 보정 후 %).

한계 (발표 때 물어보면 그대로 말할 것)
  - '기준 상태'를 데이터 맨 앞 24개월로 가정한다. 그 구간 자체가 특이하면(예: 코로나 시기) 변화 크기는 그 구간 대비다.
  - 월 데이터라 시점의 오차는 ±1~2개월이다.
  - 변화가 '왜' 생겼는지는 알 수 없다. 현장 확인이 필요하다.
"""

import numpy as np
from sklearn.linear_model import LinearRegression

REF_MONTHS = 24        # 기준 상태로 보는 맨 앞 개월 수
CUSUM_K = 1.0          # 허용 오차 (σ 단위)
CUSUM_H = 5.0          # 경보 문턱 (σ 단위)
MIN_ROWS = 36          # 이보다 짧으면 탐지하지 않는다
MIN_CHANGE_PCT = 10.0  # 기온 보정 후 이만큼은 변해야 '변화'로 보고한다
SSE_RATIO_MAX = 0.7    # 수준 이동을 넣은 회귀의 오차 ≤ 넣지 않은 회귀의 70%
SIGMA_FLOOR = 0.02     # σ 하한 (기준 평균의 2%) — 너무 예민해지는 것을 막는다
Z_LIMIT = 3.5          # 이상 점수 문턱 (로버스트 z)
MIN_REGIME_ROWS = 12   # 변화 이후 구간이 이보다 짧으면 이상 점수를 내지 않는다
LABEL = {"gas": "가스", "elec": "전기", "total": "전기+가스"}


def _mad_sigma(x):
    x = np.asarray(x, dtype=float)
    return 1.4826 * float(np.median(np.abs(x - np.median(x))))


def _ymtxt(ym):
    return f"{ym[:4]}.{ym[4:6]}"


def _series(df, col):
    """(일평균 y, 유효 행 번호). col 이 없거나 값이 없으면 (None, [])"""
    if col not in df.columns:
        return None, []
    y = (df[col].astype(float) / df["days"].astype(float)).values
    idx = [i for i in range(len(df)) if np.isfinite(y[i]) and y[i] > 0]
    return y, idx


def _detect_one(df, col):
    y, idx = _series(df, col)
    if y is None or len(idx) < MIN_ROWS:
        return None
    X = df[["hdd", "cdd"]].values.astype(float)
    ref = idx[:REF_MONTHS]
    m = LinearRegression().fit(X[ref], y[ref])
    res = y - m.predict(X)
    ref_mean = float(np.mean(y[ref]))
    n_ref = len(ref)
    # 학습에 쓴 점의 잔차는 실제보다 작게 나온다 → 자유도(3)만큼 보정
    sig = max(_mad_sigma(res[ref]) * np.sqrt(n_ref / max(1, n_ref - 3)), SIGMA_FLOOR * ref_mean)
    z = res / sig

    alarm = None
    for direction in (+1, -1):
        s = 0.0
        for i in idx:
            if i <= ref[-1]:
                continue
            s = max(0.0, s + direction * z[i] - CUSUM_K)
            if s > CUSUM_H and (alarm is None or i < alarm[0]):
                alarm = (i, direction)
                break
    if alarm is None:
        return None
    a_i, direction = alarm

    # onset: alarm 앞 12개월 안에서 수준 이동 회귀의 오차가 가장 작은 달
    # CUSUM 은 '무언가 바뀌었다'는 신호(경보)만 준다. 시작 시점은 기준 구간 이후 모든 달을 후보로
    # '수준 이동 + HDD + CDD' 회귀의 오차가 가장 작아지는 달로 정한다 (경보가 잡음에 일찍 울려도 시점이 끌려가지 않게).
    cands = [c for c in idx if c > ref[-1] and c <= idx[-3]] or [a_i]
    F0 = X[idx]
    sse0 = float(np.sum((y[idx] - LinearRegression().fit(F0, y[idx]).predict(F0)) ** 2))
    best = None
    for c in cands:
        step = np.array([1.0 if i >= c else 0.0 for i in idx])
        F = np.column_stack([X[idx], step])
        mm = LinearRegression().fit(F, y[idx])
        sse = float(np.sum((y[idx] - mm.predict(F)) ** 2))
        if best is None or sse < best[0]:
            best = (sse, c, float(mm.coef_[-1]))
    sse1, onset_i, step_coef = best
    pct = step_coef / ref_mean * 100.0
    if abs(pct) < MIN_CHANGE_PCT:
        return None
    # 수준 이동을 넣었을 때 오차가 충분히 줄어야 '진짜 변화'로 본다 (잡음에 대한 경보를 걸러낸다)
    if sse1 > SSE_RATIO_MAX * sse0:
        return None
    return {
        "fuel": LABEL[col],
        "fuel_key": col,
        "direction": "up" if pct > 0 else "down",
        "onset_ym": str(df["ym"].iloc[onset_i]),
        "alarm_ym": str(df["ym"].iloc[a_i]),
        "change_pct": round(pct, 1),
        "ref_period": f"{df['ym'].iloc[ref[0]]} ~ {df['ym'].iloc[ref[-1]]}",
    }


def detect_regime_shift(df, train_start_ym=None):
    """df: ym, elec, gas, total, hdd, cdd, days (공사 전 행만). 반환: dict (항상 detected 키가 있다)"""
    base = {
        "method": "기온(HDD·CDD) 보정 잔차의 CUSUM(k=1.0σ, h=5σ) + 수준 이동 위치 탐색",
        "ref_months": REF_MONTHS,
        "min_change_pct": MIN_CHANGE_PCT,
    }
    if len(df) < MIN_ROWS:
        return {**base, "detected": False, "reason": "too_short",
                "message": f"운영 변화를 찾으려면 공사 전 데이터가 {MIN_ROWS}개월 이상 필요해요 (현재 {len(df)}개월)"}

    shifts = []
    for col in ("gas", "elec", "total"):
        r = _detect_one(df, col)
        if r:
            shifts.append(r)
    if not shifts:
        return {**base, "detected": False, "reason": "none", "shifts": [],
                "message": "기온을 보정하고 나면 사용량의 뚜렷한 운영 변화는 보이지 않아요"}

    head = max((s for s in shifts if s["fuel_key"] != "total"), key=lambda s: abs(s["change_pct"]),
               default=shifts[0])
    tot = next((s for s in shifts if s["fuel_key"] == "total"), None)
    sign = "+" if head["change_pct"] > 0 else ""
    verb = "늘었어요" if head["change_pct"] > 0 else "줄었어요"
    msg = f"운영 변화 감지: {_ymtxt(head['onset_ym'])}부터 {head['fuel']} 사용량이 기온을 보정하고도 약 {sign}{head['change_pct']:.0f}% {verb}"
    if tot and tot is not head:
        ts = "+" if tot["change_pct"] > 0 else ""
        msg += f" (전기+가스 {ts}{tot['change_pct']:.0f}%)"
    after = None
    if train_start_ym:
        after = str(train_start_ym) >= head["onset_ym"]
        msg += (f" → 기저선 학습 구간({_ymtxt(str(train_start_ym))}~)은 변화 이후 구간이에요" if after
                else f" → 기저선 학습 구간({_ymtxt(str(train_start_ym))}~)이 변화 이전을 포함해요. 구간 재검토가 필요해요")
    return {**base, "detected": True, "headline": head, "shifts": shifts,
            "train_start_ym": str(train_start_ym) if train_start_ym else None,
            "train_after_shift": after,
            "suggested_train_start_ym": head["onset_ym"],
            "message": msg}


def adjusted_anomalies(df, regime):
    """기온 보정 이상 점수. 변화 이후 구간(없으면 전체)에서 연료별로 로버스트 z 를 구해 |z| > 3.5 인 달을 돌려준다."""
    out = []
    start_ym = regime.get("headline", {}).get("onset_ym") if regime.get("detected") else None
    X = df[["hdd", "cdd"]].values.astype(float)
    for col in ("gas", "elec"):
        y, idx = _series(df, col)
        if y is None:
            continue
        reg = [i for i in idx if start_ym is None or str(df["ym"].iloc[i]) >= start_ym]
        if len(reg) < MIN_REGIME_ROWS:
            continue
        use = list(reg)
        z = None
        for _ in range(3):                      # 튀는 달을 빼고 다시 맞춘다 (이상 달이 기준을 끌어올리지 않게)
            m = LinearRegression().fit(X[use], y[use])
            pred = m.predict(X)
            # 사용량이 많은 겨울에는 오차도 크다 → 예측값 대비 비율(상대 잔차)로 비교한다
            # (분모 하한: 변화 이후 평균 일사용량의 25% — 여름 가스처럼 예측값이 0 에 가까운 달에서 폭주하지 않게)
            rel = (y - pred) / np.maximum(pred, 0.25 * float(np.mean(y[reg])))
            # σ 는 튀는 달을 뺀 점만이 아니라 변화 이후 구간 전체의 MAD (MAD 자체가 튀는 값에 강하다)
            # → 빼고 다시 맞출수록 σ 가 줄어 멀쩡한 달까지 이상으로 잡히는 것을 막는다
            sg = max(_mad_sigma(rel[reg]) * np.sqrt(len(reg) / max(1, len(reg) - 3)), SIGMA_FLOOR)
            z = rel / sg
            nxt = [i for i in reg if abs(z[i]) <= Z_LIMIT]
            if len(nxt) < MIN_REGIME_ROWS or nxt == use:
                break
            use = nxt
        for i in reg:
            if abs(z[i]) > Z_LIMIT:
                days = float(df["days"].iloc[i])
                exp = float(pred[i]) * days
                out.append({
                    "ym": str(df["ym"].iloc[i]), "fuel": LABEL[col],
                    "direction": "up" if z[i] > 0 else "down",
                    "z": round(float(z[i]), 1),
                    "actual": round(float(y[i] * days)), "expected": round(exp),
                    "method": "기온 보정 잔차의 로버스트 z (변화 이후 구간)",
                })
    return sorted(out, key=lambda a: a["ym"])
