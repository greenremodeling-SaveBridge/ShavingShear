"""
세이브브릿지 — 기저선 추정 모듈  (담당: 지윤언니)

서현님은 이 파일을 수정하지 않습니다.
백엔드는 run_baseline() 함수만 호출하면 됩니다.

■ 지표 대조표 (2026-10-19 실제 DB로 재현 — verify_metrics.py)
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


def fit_and_predict(df):
    """
    df: ym, total, hdd, cdd, days 컬럼 (ym 오름차순)
    반환: model, 일평균 예측, 일평균 실측, 월 단위 예측, 월 단위 실측, ym 리스트
    """
    df = df.reset_index(drop=True)
    df["daily_use"] = df["total"] / df["days"]      # 일평균으로 정규화

    X = df[["hdd", "cdd"]]
    y = df["daily_use"]

    tr_end = TRAIN_MONTHS
    va_end = TRAIN_MONTHS + VALID_MONTHS

    model = LinearRegression().fit(X[:tr_end], y[:tr_end])

    pred_daily = model.predict(X[tr_end:va_end])
    actual_daily = y[tr_end:va_end].values
    days = df["days"][tr_end:va_end].values

    pred_month = pred_daily * days                   # 월 합계로 되돌리기 (그래프용)
    actual_month = df["total"][tr_end:va_end].values
    yms = df["ym"][tr_end:va_end].tolist()

    return model, pred_daily, actual_daily, pred_month, actual_month, yms


def predict_all_months(model, df):
    """
    학습된 모델로 전 기간의 기저선을 산출한다.

    정산은 '그 달에 공사를 안 했다면 썼을 양'이 필요하므로
    검증 12개월만으로는 부족하다. 같은 모델을 전 기간에 적용한다.

    phase 로 학습 / 검증 / 적용 구간을 구분해 둔다 — 화면에서
    '모델이 본 데이터'와 '보지 않은 데이터'를 나눠 보여주기 위함.
    """
    df = df.reset_index(drop=True)
    pred_daily = model.predict(df[["hdd", "cdd"]])
    out = []
    for i, row in df.iterrows():
        phase = ("학습" if i < TRAIN_MONTHS
                else "검증" if i < TRAIN_MONTHS + VALID_MONTHS
                else "적용")
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

    return {
        "cv_rmse": round(float(cv_rmse), 1),
        "r2": round(float(r2), 3),
        "annual_error": round(float(annual_err), 1),
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


def run_baseline(df):
    """
    백엔드가 호출하는 함수. 이것만 쓰면 됩니다.
    입력: ym, total, hdd, cdd, days 컬럼을 가진 데이터프레임
    """
    need = TRAIN_MONTHS + VALID_MONTHS
    if len(df) < need:
        raise ValueError(f"데이터가 {need}개월 이상 필요합니다 (현재 {len(df)}개월)")

    df = df.reset_index(drop=True)
    model, pd_daily, ad_daily, pd_month, ad_month, yms = fit_and_predict(df)
    metrics = calc_metrics(ad_daily, pd_daily, ad_month, pd_month)
    anomalies = detect_anomalies(df)
    verdict, msg = judge(metrics)
    monthly = predict_all_months(model, df)

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
            "train": f"{df['ym'].iloc[0]} ~ {df['ym'].iloc[TRAIN_MONTHS - 1]}",
            "train_months": TRAIN_MONTHS,
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
