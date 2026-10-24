"""
2023년 가스 구조 변화 분석 (읽기 전용 — baseline.py / DB 를 수정하지 않는다)

실행:  python gas_2023_analysis.py [savebridge.db 경로]

현재 모델과 같은 조건
  일평균 사용량 = a + b*HDD + c*CDD (선형회귀), 앞 24행(2020.01~2022.01)으로 학습
  → 학습 이후 모든 달(검증 12행 + 그 이후)에 같은 모델을 그대로 적용해 잔차(실측 − 예측)를 본다.
잔차는 월 합계(kWh)로 환산해서 본다.  (+) = 실측이 예측보다 큼 = 기저선이 과소 예측
"""
import sqlite3
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

DB = sys.argv[1] if len(sys.argv) > 1 else "savebridge.db"
TRAIN = 24
BLD = 1

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
df = pd.read_sql("""
    SELECT u.ym, u.elec, u.gas, u.total, w.hdd, w.cdd, w.days
    FROM usage_monthly u JOIN weather_monthly w ON u.ym = w.ym
    WHERE u.bld_id = ? AND u.total IS NOT NULL ORDER BY u.ym""", conn, params=(BLD,))
conn.close()
df["year"] = df["ym"].str[:4].astype(int)
df["mon"] = df["ym"].str[4:6].astype(int)


def fit_predict(d, target):
    y = d[target] / d["days"]
    m = LinearRegression().fit(d[["hdd", "cdd"]][:TRAIN], y[:TRAIN])
    d[f"{target}_pred"] = m.predict(d[["hdd", "cdd"]]) * d["days"]
    d[f"{target}_res"] = d[target] - d[f"{target}_pred"]
    return m


print(f"모델 입력 {len(df)}행  {df['ym'].iloc[0]}~{df['ym'].iloc[-1]}  학습 {df['ym'].iloc[0]}~{df['ym'].iloc[TRAIN-1]}")
print("가스/전기 결측(0 아님·NaN):", int(df["gas"].isna().sum()), "/", int(df["elec"].isna().sum()), "\n")

models = {t: fit_predict(df, t) for t in ("gas", "elec", "total")}
for t, m in models.items():
    print(f"[{t}] 학습 모델  일평균 = {m.intercept_:,.1f} + {m.coef_[0]:,.1f}*HDD + {m.coef_[1]:,.1f}*CDD")

# 1. 연도별 합계와 잔차
print("\n■ 1. 연도별 실측·예측·잔차 (kWh, 월 합계 기준)  ← 학습(2020.01~2022.01) 이후 구간은 '검증/적용' 구간")
rows = []
for yr, g in df.groupby("year"):
    r = {"연도": yr, "행수": len(g)}
    for t in ("elec", "gas"):
        r[f"{t} 실측"] = g[t].sum(); r[f"{t} 예측"] = g[f"{t}_pred"].sum()
        r[f"{t} 잔차%"] = (g[t].sum() - g[f"{t}_pred"].sum()) / g[f"{t}_pred"].sum() * 100
    rows.append(r)
T = pd.DataFrame(rows)
with pd.option_context("display.width", 200, "display.float_format", "{:,.1f}".format):
    print(T.to_string(index=False))
print("  ※ 2020(학습 전부)·2021·2022.01 은 학습 구간이라 잔차가 작은 게 당연하다(정보 없음). 의미 있는 건 2022.02 이후.")

# 2. 월별 가스 (난방 없는 여름 포함)
print("\n■ 2. 가스 월별 실측 · 예측 · 잔차 (2022.02 이후)")
g = df[df["ym"] >= df["ym"].iloc[TRAIN]][["ym", "hdd", "gas", "gas_pred", "gas_res"]].copy()
g["잔차%"] = g["gas_res"] / g["gas_pred"] * 100
with pd.option_context("display.width", 200, "display.max_rows", 200, "display.float_format", "{:,.1f}".format):
    print(g.to_string(index=False))

# 3. 난방 없는 달(HDD 거의 0)의 가스 = 기온과 무관한 기저 부하
print("\n■ 3. 난방 없는 달(HDD ≤ 0.5)의 가스 일평균 (기온으로 설명 안 되는 '기저 부하')")
nh = df[df["hdd"] <= 0.5].copy()
nh["gas_daily"] = nh["gas"] / nh["days"]
byyr = nh.groupby("year").agg(달수=("ym", "count"), 가스_일평균=("gas_daily", "mean"), 평균CDD=("cdd", "mean"))
with pd.option_context("display.float_format", "{:,.1f}".format):
    print(byyr.to_string())

# 4. 기저선 사용 가능성: 2022.02~2023.02(검증) vs 2023.03 이후 잔차
print("\n■ 4. 구간별 잔차 (total = 현재 모델이 실제로 쓰는 값)")
def seg(name, mask):
    s = df[mask]
    if len(s) == 0: return
    for t in ("total", "gas", "elec"):
        res = s[f"{t}_res"].sum(); pred = s[f"{t}_pred"].sum()
        print(f"  {name:<24} {t:<5} 행 {len(s):2d}  잔차합 {res:>10,.0f}kWh  ({res / pred * 100:+6.1f}% of 예측)")
yms = df["ym"]
seg("검증 12행", (yms >= df['ym'].iloc[TRAIN]) & (yms <= df['ym'].iloc[TRAIN + 11]))
seg("검증 이후 ~2023.12", (yms > df['ym'].iloc[TRAIN + 11]) & (yms <= "202312"))
seg("2024 이후", yms >= "202401")
seg("최근 12행", yms >= df['ym'].iloc[-12])
last12 = df.iloc[-12:]
print(f"  최근 12행 = {last12['ym'].iloc[0]}~{last12['ym'].iloc[-1]}")

# 5. 같은 모델을 2023.03 이후 데이터로 다시 맞췄을 때 기저 부하(절편) 변화 — '기온 밖의 변화'인지 본다
print("\n■ 5. 가스 회귀 계수 비교 (진단용 — 모델 교체 제안 아님)")
def coefs(d):
    y = d["gas"] / d["days"]
    m = LinearRegression().fit(d[["hdd", "cdd"]], y)
    return m.intercept_, m.coef_[0], m.coef_[1]
for name, d in [("학습 24행(2020.01~2022.01)", df.iloc[:TRAIN]),
                ("2023.03 이후", df[df["ym"] >= "202303"])]:
    if len(d) >= 6:
        a, b, c = coefs(d)
        print(f"  {name:<26} n={len(d):2d}  절편(기온 무관 가스 일평균) {a:7.1f}  HDD 계수 {b:7.1f}  CDD 계수 {c:7.1f}")
print("  ※ 2023.03 이후 행 수가 적으면 계수는 참고용일 뿐이다.")
