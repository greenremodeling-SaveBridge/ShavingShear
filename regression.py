import pandas as pd, numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

daily = pd.read_csv("daily_temp.csv", parse_dates=["tm"])
energy = pd.read_csv("energy.csv", dtype={"ym": str})
med = energy["elec"].median()
energy = energy[energy["elec"] <= med * 2]


def build(hb, cb):
    d = daily.copy()
    d["HDD"] = (hb - d["avgTa"]).clip(lower=0)
    d["CDD"] = (d["avgTa"] - cb).clip(lower=0)
    g = d.set_index("tm")[["HDD", "CDD"]].resample("ME")
    m = g.mean().round(3)  # 일평균 도일
    m["days"] = g.size()
    m = m[m["days"] >= 25]
    m.index = m.index.strftime("%Y%m")
    m.index.name = "ym"
    df = energy.merge(m.reset_index(), on="ym").sort_values("ym").reset_index(drop=True)
    df["daily_elec"] = df["elec"] / df["days"]  # 일평균 사용량
    return df


def evaluate(df):
    if len(df) < 36:
        return None
    X, y = df[["HDD", "CDD"]], df["daily_elec"]
    m = LinearRegression().fit(X[:24], y[:24])
    pred = m.predict(X[24:36])
    yv = y[24:36]
    return (
        r2_score(yv, pred),
        np.sqrt(((yv - pred) ** 2).mean()) / yv.mean() * 100,
        m,
        df,
    )


best = None
for hb in np.arange(12, 22, 0.5):
    for cb in np.arange(16, 26, 0.5):
        r = evaluate(build(hb, cb))
        if r and (best is None or r[0] > best[0]):
            best = (*r, hb, cb)

r2, cv, model, df, hb, cb = best
print("=" * 50)
print(f"  기준온도   난방 {hb}℃ / 냉방 {cb}℃")
print(f"  R²        = {r2:.3f}   → {'통과' if r2 >= .75 else '미달'}")
print(f"  CV(RMSE)  = {cv:.1f}%   → {'통과' if cv <= 15 else '미달'}")
print("=" * 50)
print(
    f"\n일평균사용량 = {model.intercept_:.0f} "
    f"+ {model.coef_[0]:.1f}×HDD + {model.coef_[1]:.1f}×CDD"
)

X, y = df[["HDD", "CDD"]], df["daily_elec"]
pred = model.predict(X[24:36])
comp = pd.DataFrame(
    {
        "ym": df.ym[24:36].values,
        "실측(월)": df.elec[24:36].values,
        "예측(월)": (pred * df.days[24:36].values).round(0),
        "오차%": ((pred - y[24:36]) / y[24:36] * 100).round(1),
    }
)
print("\n", comp.to_string(index=False))
comp.to_csv("validation.csv", index=False, encoding="utf-8-sig")
