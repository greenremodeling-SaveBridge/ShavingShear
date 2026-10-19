import pandas as pd, numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

daily = pd.read_csv("daily_temp.csv", parse_dates=["tm"])
e = pd.read_csv("energy.csv", dtype={"ym": str})
g = pd.read_csv("gas.csv", dtype={"ym": str})

# 전기 + 가스 (둘 다 kWh) → 총 에너지
use = e.merge(g, on="ym")
use["total"] = use["elec"] + use["gas"]

# 이상치 제거 (중앙값 2배 초과)
med = use["total"].median()
out = use[use["total"] > med * 2]
if len(out):
    print("[이상치 제외]")
    print(out.to_string(index=False))
    print()
use = use[use["total"] <= med * 2].reset_index(drop=True)
print(f"분석 대상 {len(use)}개월  ({use.ym.min()} ~ {use.ym.max()})\n")


def build(hb, cb):
    d = daily.copy()
    d["HDD"] = (hb - d["avgTa"]).clip(lower=0)
    d["CDD"] = (d["avgTa"] - cb).clip(lower=0)
    gr = d.set_index("tm")[["HDD", "CDD"]].resample("ME")
    m = gr.mean().round(3)
    m["days"] = gr.size()
    m = m[m["days"] >= 25]
    m.index = m.index.strftime("%Y%m")
    m.index.name = "ym"
    df = use.merge(m.reset_index(), on="ym").sort_values("ym").reset_index(drop=True)
    df["daily_use"] = df["total"] / df["days"]
    return df


def evaluate(df):
    if len(df) < 36:
        return None
    X, y = df[["HDD", "CDD"]], df["daily_use"]
    m = LinearRegression().fit(X[:24], y[:24])
    p = m.predict(X[24:36])
    yv = y[24:36]
    return r2_score(yv, p), np.sqrt(((yv - p) ** 2).mean()) / yv.mean() * 100, m, df


best = None
for hb in np.arange(12, 22, 0.5):
    for cb in np.arange(16, 26, 0.5):
        r = evaluate(build(hb, cb))
        if r and (best is None or r[0] > best[0]):
            best = (*r, hb, cb)

r2, cv, model, df, hb, cb = best
print("=" * 52)
print(f"  기준온도    난방 {hb}℃ / 냉방 {cb}℃")
print(f"  R²        = {r2:.3f}   기준 0.75 → {'통과' if r2 >= .75 else '미달'}")
print(f"  CV(RMSE)  = {cv:.1f}%   기준 15%  → {'통과' if cv <= 15 else '미달'}")
print("=" * 52)
print(
    f"\n일평균 사용량 = {model.intercept_:.0f} + {model.coef_[0]:.1f}×HDD + {model.coef_[1]:.1f}×CDD"
)

X, y = df[["HDD", "CDD"]], df["daily_use"]
pred = model.predict(X[24:36])
comp = pd.DataFrame(
    {
        "ym": df.ym[24:36].values,
        "실측(월)": df.total[24:36].values,
        "예측(월)": (pred * df.days[24:36].values).round(0),
        "오차%": ((pred - y[24:36]) / y[24:36] * 100).round(1),
    }
)
print("\n", comp.to_string(index=False))

# 참고: 전기/가스 비중
print(
    f"\n전기 비중 {use.elec.sum()/use.total.sum()*100:.0f}%  /  가스 비중 {use.gas.sum()/use.total.sum()*100:.0f}%"
)
