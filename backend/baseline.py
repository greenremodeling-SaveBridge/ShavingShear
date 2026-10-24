"""
세이브브릿지 — 기저선 추정 모듈  (담당: 지윤언니)

서현님은 이 파일을 수정하지 않습니다.
백엔드는 run_baseline() 함수만 호출하면 됩니다.

■ 2026-10-22 기저선 기간 변경 (BASELINE_MODE = "recent")
    공사 직전 36개월: 학습 2023.05~2025.04(이상 감지 5개월 제외, 19개월) · 검증 2025.05~2026.04
    전체(전기+가스) · 일평균 기준   CV 12.6% · R² 0.692 · NMBE −2.6%
    BASELINE_MODE = "legacy" 로 바꾸면 아래 예전 숫자가 그대로 나온다.

■ 지표 대조표 (2026-10-19 실제 DB로 재현 — verify_metrics.py, legacy 방식)
    이 파일(run_baseline)은 total = 전기+가스 를 예측한다.
    전체(전기+가스) · 일평균 기준   CV 18.67% · R² 0.655 · 합계 −5.69%   ← 이 파일이 내는 값
    전기만 · 일평균 기준            CV 15.02% · R² 0.661 · 합계 −4.96%   ← 제안서 7p 15.0% / 0.661
    전기만 · 월 합계 기준           CV 14.92% · R² 0.616 · 합계 −4.96%   ← 예선 제안서 14.9% / 0.616 (validation.csv)
    예전 backup.json 19.4% / 0.626 / −7.6%  → 현재 데이터·코드로 재현 안 됨 (폐기)

※ 제안서 7p 숫자는 '전기 단독' 결과다. 이 파일의 출력과 같은 숫자가 아니다.

지윤언니가 할 일:
- fit_and_predict() 안의 모델 개선 (선형회귀 → XGBoost 등)
- 이상 감지 로직 고도화
- 함수가 돌려주는 딕셔너리의 key 이름은 바꾸지 말 것 ← 백엔드·프론트가 씁니다
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

# ─── 설정값 ───────────────────────────────────────────
TRAIN_MONTHS = 24          # 학습에 쓸 개월 수
VALID_MONTHS = 12          # 검증에 쓸 개월 수
PRICE_PER_KWH = 150        # 원/kWh — 제안서 10·11p에 '(가정)'으로 명시한 값
SAVING_RATE = 0.20         # 이자지원사업 성능개선 요건 20%

# 판정 기준 (제안서 7p)
CV_LIMIT = 15.0            # 예측 오차 CV(RMSE) 15% 이하
R2_LIMIT = 0.75            # 설명력 R² 0.75 이상
CI_Z = 1.645               # 90% 신뢰구간 (제안서 12p)

# 이상 감지 기준 (제안서 8p — 난방 없는 여름에 가스 2배)
ANOMALY_RATIO = 1.8        # 같은 달 과거 평균 대비 몇 배부터 이상으로 볼지

# ─── 기저선 기간 (2026-10-22 변경) ─────────────────────
# "recent" : 공사 직전 36개월 — 마지막 12개월 검증, 그 앞 24개월 학습. 학습 구간의 이상 감지 달은 뺀다.
#            M&V 원칙: 기저선은 공사 직전의 운영 상태를 대표해야 한다.
#            이 건물은 2023년부터 사용량이 약 30% 늘었다(운영 변화). 2020~2022년(코로나 시기 포함)으로
#            학습하면 지금 건물이 아니라 예전 건물을 예측하게 된다.
# "legacy" : 예전 방식 — 데이터 맨 앞 24개월 학습, 다음 12개월 검증 (예선 제안서 수치 재현용)
BASELINE_MODE = "recent"


def windows(df, anomaly_yms=(), n_pre=None):
    """학습·검증 행 번호를 정한다. 반환: (학습에 쓴 행, 학습 창 시작, 학습 창 끝, 검증 시작, 검증 끝)
    n_pre: 공사 전 행 수 (공사 완료월이 있으면 그 전까지만 학습·검증에 쓴다)"""
    n = len(df) if n_pre is None else n_pre
    if BASELINE_MODE == "legacy":
        tr0, tr1, va0, va1 = 0, TRAIN_MONTHS, TRAIN_MONTHS, TRAIN_MONTHS + VALID_MONTHS
        used = list(range(tr0, tr1))
    else:
        va1 = n
        va0 = n - VALID_MONTHS
        tr0 = max(0, va0 - TRAIN_MONTHS)
        tr1 = va0
        used = [i for i in range(tr0, tr1) if df["ym"].iloc[i] not in set(anomaly_yms)]
    return used, tr0, tr1, va0, va1


def fit_and_predict(df, anomaly_yms=(), n_pre=None):
    """
    df: ym, total, hdd, cdd, days 컬럼 (ym 오름차순)
    반환: model, 일평균 예측, 일평균 실측, 월 단위 예측, 월 단위 실측, ym 리스트, 창 정보
    """
    df = df.reset_index(drop=True)
    df["daily_use"] = df["total"] / df["days"]      # 일평균으로 정규화

    X = df[["hdd", "cdd"]]
    y = df["daily_use"]

    used, tr0, tr1, va0, va1 = windows(df, anomaly_yms, n_pre)
    model = LinearRegression().fit(X.iloc[used], y.iloc[used])

    pred_daily = model.predict(X[va0:va1])
    actual_daily = y[va0:va1].values
    days = df["days"][va0:va1].values

    pred_month = pred_daily * days                   # 월 합계로 되돌리기 (그래프용)
    actual_month = df["total"][va0:va1].values
    yms = df["ym"][va0:va1].tolist()

    win = {"used": used, "tr0": tr0, "tr1": tr1, "va0": va0, "va1": va1}
    return model, pred_daily, actual_daily, pred_month, actual_month, yms, win


def predict_all_months(model, df, win=None, after_label="적용"):
    """
    학습된 모델로 전 기간의 기저선을 산출한다.

    정산은 '그 달에 공사를 안 했다면 썼을 양'이 필요하므로
    검증 12개월만으로는 부족하다. 같은 모델을 전 기간에 적용한다.

    phase: 이전(기저선에 안 씀) / 학습 / 검증 / 적용(검증 뒤)
    """
    df = df.reset_index(drop=True)
    if win is None:
        win = {"tr0": 0, "tr1": TRAIN_MONTHS, "va0": TRAIN_MONTHS, "va1": TRAIN_MONTHS + VALID_MONTHS}
    pred_daily = model.predict(df[["hdd", "cdd"]])
    out = []
    for i, row in df.iterrows():
        phase = ("이전" if i < win["tr0"]
                 else "학습" if i < win["tr1"]
                 else "검증" if i < win["va1"]
                 else after_label)
        out.append({
            "ym": row["ym"],
            "actual": round(float(row["total"])),
            "baseline": round(float(pred_daily[i] * row["days"])),
            "phase": phase,
        })
    return out


def calc_metrics(actual_daily, pred_daily, actual_month, pred_month):
    """
    제안서 7p 지표.
    CV(RMSE)와 R²는 '일평균 기준' — 기준을 바꾸면 제안서 숫자와 달라집니다.
    """
    n = len(actual_daily)
    mean = actual_daily.mean()

    cv_rmse = np.sqrt(((actual_daily - pred_daily) ** 2).sum() / n) / mean * 100
    r2 = 1 - (((actual_daily - pred_daily) ** 2).sum()
            / ((actual_daily - mean) ** 2).sum())

    # 12개월 합계 오차 — 제안서 7p "약 5% → 연 단위로 확정"
    annual_err = (pred_month.sum() - actual_month.sum()) / actual_month.sum() * 100

    # NMBE — 평균 편향 (ASHRAE Guideline 14 월별 기준 ±5%). 실측 − 예측 기준, 분모 (n−1)·평균
    nmbe = (actual_daily - pred_daily).sum() / ((n - 1) * mean) * 100

    return {
        "cv_rmse": round(float(cv_rmse), 1),
        "r2": round(float(r2), 3),
        "annual_error": round(float(annual_err), 1),
        "nmbe": round(float(nmbe), 1),
    }


def judge(metrics):
    """
    모델 품질 판정 (제안서 7·8p)
    CONFIRMED  정상 — 오차·설명력 기준 모두 충족    → 금액 확정
    RANGE      주의 — 둘 중 하나라도 미충족         → 금액을 확정하지 않고 90% 구간과 함께 잠정 제시

    ※ '보류(HOLD)'는 모델 전체가 아니라 '이상이 감지된 정산 기간'에만 붙습니다.
    제안서 10p에서 3분기가 '잠정 정산'이고 7월 한 달만 회색인 것이 그 구조입니다.
    → 기간별 판정은 main.py의 /api/settlement 가 처리합니다.
    """
    cv_ok = metrics["cv_rmse"] <= CV_LIMIT
    r2_ok = metrics["r2"] >= R2_LIMIT

    if cv_ok and r2_ok:
        return "CONFIRMED", "기저선 모델이 예측 오차·설명력 기준을 모두 충족했습니다"
    return "RANGE", (f"예측 오차 {metrics['cv_rmse']}% (기준 {CV_LIMIT}% 이하) · "
                    f"설명력 {metrics['r2']} (기준 {R2_LIMIT} 이상) — "
                    f"기준 미달이므로 금액을 확정하지 않고 추정 범위(90% 구간)와 함께 제시합니다")


# 이 판정이 무엇을 뜻하고 무엇을 뜻하지 않는지.
# 심사위원이 "모델이 좋으면 절감 효과가 입증된 건가요"라고 물을 때의 답.
VERDICT_MEANING = (
    "이 판정은 '기저선 모델이 과거 사용량을 얼마나 잘 재현하는가'만 평가합니다. "
    "그린리모델링의 절감 효과가 입증되었다는 뜻이 아닙니다. "
    "실제 절감량은 공사 후 사용량이 확보되어야 검증할 수 있습니다."
)


def detect_anomalies(df):
    """
    제안서 8p의 이상 감지.

    연료별(전기·가스)로, 같은 달의 과거 평균과 비교한다.
    합계로 보면 '난방 없는 여름에 가스만 2배' 같은 변화가 묻혀서 안 잡힌다.
    """
    out = []
    df = df.copy()
    df["month"] = df["ym"].str[4:6]

    for fuel, label in [("gas", "가스"), ("elec", "전기")]:
        if fuel not in df.columns:
            continue
        for _, row in df.iterrows():
            past = df[(df["month"] == row["month"]) & (df["ym"] < row["ym"])]
            past = past[past[fuel].notna() & (past[fuel] > 0)]   # 결측월 제외
            if len(past) < 2 or pd.isna(row[fuel]) or row[fuel] <= 0:
                continue
            base = past[fuel].mean()
            if base > 0 and row[fuel] > base * ANOMALY_RATIO:
                out.append({
                    "ym": row["ym"],
                    "fuel": label,
                    "actual": round(float(row[fuel])),
                    "past_avg": round(float(base)),
                    "ratio": round(float(row[fuel] / base), 2),
                    # 이 검사는 '같은 달 과거 평균'과의 비교다. 기온 보정은 들어가 있지 않다.
                    # 따라서 '날씨로 설명되지 않는다'고 단정하지 않는다 — 확인이 필요한 변화다.
                    "reason": f"{row['month']}월 {label} 사용량이 과거 같은 달 평균의 "
                            f"{row[fuel] / base:.1f}배 — 기온 외 요인 확인 필요",
                    "method": "같은 달 과거 평균 대비 (기온 보정 없음)",
                })

    return sorted(out, key=lambda x: x["ym"])


def fuel_baselines(df, win):
    """공사 후 정산용 — 같은 학습 행으로 전기·가스를 따로 예측한다. {ym: (전기 kWh, 가스 kWh)}"""
    out = {ym: [None, None] for ym in df["ym"]}
    X = df[["hdd", "cdd"]]
    for k, col in enumerate(("elec", "gas")):
        if col not in df or df[col].isna().all():
            continue
        y = df[col] / df["days"]
        rows = [i for i in win["used"] if pd.notna(y.iloc[i])]
        m = LinearRegression().fit(X.iloc[rows], y.iloc[rows])
        p = m.predict(X) * df["days"].values
        for ym, v in zip(df["ym"], p):
            out[ym][k] = max(0.0, float(v))
    return out


def run_baseline(df, retrofit_ym=None):
    """
    백엔드가 호출하는 함수. 이것만 쓰면 됩니다.
    입력: ym, total, hdd, cdd, days 컬럼을 가진 데이터프레임
    retrofit_ym: 그린리모델링 공사 완료월(YYYYMM). 있으면 그 전 데이터로만 기저선을 만들고, 그 뒤는 '공사 후'로 표시한다.
    """
    df = df.reset_index(drop=True)
    n_pre = int((df["ym"] < retrofit_ym).sum()) if retrofit_ym else None
    need = TRAIN_MONTHS + VALID_MONTHS
    if (n_pre if n_pre is not None else len(df)) < need:
        raise ValueError(f"공사 전 데이터가 {need}개월 이상 필요합니다 (현재 {n_pre if n_pre is not None else len(df)}개월)")

    anomalies = detect_anomalies(df)
    model, pd_daily, ad_daily, pd_month, ad_month, yms, win = fit_and_predict(df, {a["ym"] for a in anomalies}, n_pre)
    metrics = calc_metrics(ad_daily, pd_daily, ad_month, pd_month)
    verdict, msg = judge(metrics)
    monthly = predict_all_months(model, df, win, after_label="공사 후" if retrofit_ym else "적용")
    excluded = [df["ym"].iloc[i] for i in range(win["tr0"], win["tr1"]) if i not in set(win["used"])]

    # 절감액 환산 (제안서 10p: 실측 사용량 × 20% × 150원/kWh)
    annual_kwh = float(df["total"].tail(12).sum())
    saving_kwh = annual_kwh * SAVING_RATE
    saving_won = int(saving_kwh * PRICE_PER_KWH)

    # 90% 신뢰구간 (제안서 12p)
    err_rate = float(np.std((ad_daily - pd_daily) / ad_daily))
    ci_low = max(0, int(saving_won * (1 - CI_Z * err_rate)))
    ci_high = int(saving_won * (1 + CI_Z * err_rate))

    return {
        "metrics": metrics,
        "verdict": verdict,
        "verdict_msg": msg,
        "verdict_meaning": VERDICT_MEANING,

        # CONFIRMED 가 무엇을 뜻하는지 못박아 둔다.
        # 모델이 과거를 잘 맞췄다는 것과, 그린리모델링의 절감 효과가
        # 입증됐다는 것은 전혀 다른 이야기다.
        "verdict_meaning": (
            "모델이 과거 사용량을 기준 이내 오차로 재현했다는 뜻입니다. "
            "그린리모델링의 절감 효과가 입증되었다는 뜻이 아닙니다. "
            "절감 효과는 공사 후 실측 데이터로 따로 검증해야 합니다."
        ),
        "anomalies": anomalies,
        "fuel_baseline": fuel_baselines(df, win) if retrofit_ym else None,
        "retrofit_ym": retrofit_ym,
        "annual_saving_won": saving_won,
        "ci_low_won": ci_low,
        "ci_high_won": ci_high,
        "series": [
            {"ym": ym, "actual": round(float(a)), "baseline": round(float(p))}
            for ym, a, p in zip(yms, ad_month, pd_month)
        ],

        # ── 아래는 화면에서 '근거'를 보여주기 위해 추가한 항목 ──

        # 전 기간 기저선 — 정산할 달의 '공사 안 했다면 썼을 양'
        "monthly_baseline": monthly,

        # 지표를 어떤 조건에서 뽑았는지. 심사위원 질문 대비 (평가 기간·데이터·조건)
        "eval_window": {
            "train": f"{df['ym'].iloc[win['tr0']]} ~ {df['ym'].iloc[win['tr1'] - 1]}",
            "train_months": win["tr1"] - win["tr0"],
            "train_used_months": len(win["used"]),
            "train_excluded": excluded,                 # 학습 창 안에서 이상 감지로 뺀 달
            "rule": ("공사 직전 36개월 — 마지막 12개월 검증, 그 앞 24개월 학습 · 학습 창의 이상 감지 달 제외"
                     if BASELINE_MODE != "legacy" else "데이터 맨 앞 24개월 학습 · 다음 12개월 검증 (예선 방식)"),
            "valid": f"{yms[0]} ~ {yms[-1]}",
            "valid_months": VALID_MONTHS,
            "total_months": len(df),
            "basis": "일평균 사용량 (월 합계 ÷ 그 달 일수)",
            "inputs": "난방도일(HDD) · 냉방도일(CDD)",
            "model": type(model).__name__,
            "criteria": f"CV(RMSE) {CV_LIMIT}% 이하 · R² {R2_LIMIT} 이상",
        },

        # 절감액이 '실측'이 아니라 '가정'이라는 사실을 숨기지 않는다.
        # 아직 공사 전이므로 실측 절감량은 존재할 수 없다.
        "saving_basis": {
            "is_assumption": True,
            "formula": "최근 12개월 실측 사용량 × 절감률 20% × 150원/kWh",
            "annual_kwh": round(annual_kwh),
            "saving_rate": SAVING_RATE,
            "price_per_kwh": PRICE_PER_KWH,
            "note": ("공사 전이므로 절감량 실측값은 아직 없습니다. "
                    "절감률 20%는 그린리모델링 이자지원사업 성능개선 요건, "
                    "단가 150원/kWh는 가정값입니다. "
                    "공사 후에는 이 자리에 기저선−실측 차이가 들어갑니다."),
        },
    }


if __name__ == "__main__":
    import sqlite3
    conn = sqlite3.connect("savebridge.db")
    df = pd.read_sql("""
        SELECT u.ym, u.elec, u.gas, u.total, w.hdd, w.cdd, w.days
        FROM usage_monthly u JOIN weather_monthly w ON u.ym = w.ym
        WHERE u.bld_id = 1 AND u.total IS NOT NULL ORDER BY u.ym
    """, conn)
    conn.close()

    r = run_baseline(df)
    m = r["metrics"]
    print("\n=== 기저선 추정 결과 (제안서 7p와 대조) ===")
    print(f"  예측 오차 CV(RMSE) : {m['cv_rmse']}%    (전체 기준. 제안서 7p 15.0%는 전기 단독)")
    print(f"  설명력    R²       : {m['r2']}   (전체 기준. 제안서 7p 0.661은 전기 단독)")
    print(f"  12개월 합계 오차   : {m['annual_error']}%")
    print(f"\n  판정 : {r['verdict']} — {r['verdict_msg']}")
    if r["anomalies"]:
        print(f"  이상 감지 {len(r['anomalies'])}건:")
        for a in r["anomalies"][:5]:
            print(f"    {a['ym']} {a['fuel']} ×{a['ratio']}")
    print(f"  연간 절감액 : {r['annual_saving_won']:,}원 "
        f"(90% 구간 {r['ci_low_won']:,} ~ {r['ci_high_won']:,})")
