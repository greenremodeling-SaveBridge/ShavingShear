"""
기저선 지표 재현·불일치 추적  —  python verify_metrics.py

savebridge.db 를 읽어 baseline.py 와 같은 조건으로 지표를 다시 계산하고,
조건을 하나씩 바꿔 가며 어느 조건에서 숫자가 달라지는지 보여줍니다.
결과는 화면과 verify_log.txt 에 같이 남습니다.

baseline.py 는 고치지 않습니다. (담당: 지윤언니)  여기서는 '같은 식'을 따로 구현해 대조만 합니다.

────────────────────────────────────────────────
지표 정의 (baseline.py 현재 구현)
  검증 구간 n = 12행, 일평균 사용량 a_i = total_i / days_i, 예측 p_i
  CV(RMSE) = sqrt( Σ(a_i − p_i)² / n ) / mean(a) × 100
  R²       = 1 − Σ(a_i − p_i)² / Σ(a_i − mean(a))²
  연간 합계 오차 = (Σ p_i·days_i − Σ total_i) / Σ total_i × 100      (음수 = 과소 예측)

참고: ASHRAE Guideline 14 정의 (월 단위, p = 모델 계수 개수 = 3)
  CV(RMSE) = sqrt( Σ(y − ŷ)² / (n − p) ) / mean(y) × 100
  NMBE     = Σ(y − ŷ) / ((n − p) × mean(y)) × 100                (양수 = 과소 예측)
  → 분모가 n 이 아니라 n−p 이고, 일평균이 아니라 월 합계 기준이다.
────────────────────────────────────────────────
"""

import argparse
import json
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

TRAIN, VALID, P = 24, 12, 3

LOG = []


def out(s=""):
    print(s)
    LOG.append(s)


def load(db, bld_id):
    conn = sqlite3.connect(db)
    raw = pd.read_sql("SELECT * FROM usage_monthly WHERE bld_id=? ORDER BY ym", conn, params=(bld_id,))
    w = pd.read_sql("SELECT * FROM weather_monthly ORDER BY ym", conn)
    df = pd.read_sql("""
        SELECT u.ym, u.elec, u.gas, u.total, w.hdd, w.cdd, w.days
        FROM usage_monthly u JOIN weather_monthly w ON u.ym = w.ym
        WHERE u.bld_id = ? AND u.total IS NOT NULL ORDER BY u.ym""", conn, params=(bld_id,))
    conn.close()
    return raw, w, df


def inventory(raw, w, df):
    out("■ 1. 데이터 점검")
    out(f"  usage_monthly 행: {len(raw)}  ({raw['ym'].min()} ~ {raw['ym'].max()})")
    out(f"  전기 값 있음 {raw['elec'].notna().sum()} · 가스 값 있음 {raw['gas'].notna().sum()} · "
        f"total 있음 {raw['total'].notna().sum()}")
    out(f"  중복 ym: {raw['ym'][raw['ym'].duplicated()].tolist() or '없음'}")
    full = pd.period_range(pd.Period(raw['ym'].min(), 'M'), pd.Period(raw['ym'].max(), 'M'), freq='M')
    have = set(raw["ym"])
    out(f"  기간 내 행 자체가 없는 달: {[p.strftime('%Y%m') for p in full if p.strftime('%Y%m') not in have] or '없음'}")
    out(f"  total 결측(전기/가스 한쪽 없음): {raw.loc[raw['total'].isna(), 'ym'].tolist() or '없음'}")
    nw = sorted(set(raw.loc[raw['total'].notna(), 'ym']) - set(w['ym']))
    out(f"  기상 자료가 없어 JOIN 에서 빠진 달: {nw or '없음'}")
    cal = pd.PeriodIndex(df["ym"], freq="M").days_in_month
    short = df.loc[df["days"].values < cal, ["ym", "days"]]
    lst = [(r.ym, int(r.days), int(c)) for r, c in zip(short.itertuples(), cal[df['days'].values < cal])]
    out(f"  기온일수 < 달력일수 인 달: {len(lst)}개월 {lst[:6]}{' …' if len(lst) > 6 else ''}")
    out(f"  모델 입력 행: {len(df)}  ({df['ym'].iloc[0]} ~ {df['ym'].iloc[-1]})")
    out(f"  HDD/CDD 단위: 그 달 일별 도일의 평균(℃/일). 일별 HDD=max(0, 21.5−일평균기온), CDD=max(0, 일평균기온−16.0) (load_data.py)")
    out(f"    HDD 범위 {df['hdd'].min():.2f}~{df['hdd'].max():.2f}, CDD 범위 {df['cdd'].min():.2f}~{df['cdd'].max():.2f}")
    tr, va = df.iloc[:TRAIN], df.iloc[TRAIN:TRAIN + VALID]
    out(f"  학습 {TRAIN}행: {tr['ym'].iloc[0]} ~ {tr['ym'].iloc[-1]}  "
        f"(달력상 {len(pd.period_range(tr['ym'].iloc[0], tr['ym'].iloc[-1], freq='M'))}개월)")
    out(f"  검증 {VALID}행: {va['ym'].iloc[0]} ~ {va['ym'].iloc[-1]}  "
        f"(달력상 {len(pd.period_range(va['ym'].iloc[0], va['ym'].iloc[-1], freq='M'))}개월)")
    out(f"  시간 순서 누출: 학습 마지막 {tr['ym'].iloc[-1]} < 검증 첫 {va['ym'].iloc[0]} → "
        f"{'없음' if tr['ym'].iloc[-1] < va['ym'].iloc[0] else '⚠ 있음'}")
    out(f"  나머지 {len(df) - TRAIN - VALID}행({df['ym'].iloc[TRAIN + VALID]}~)은 지표 계산에 쓰이지 않음")
    out()


def metrics(df, target="total", days_col="days"):
    d = df.dropna(subset=[target]).reset_index(drop=True)
    d = d[d[target] > 0].reset_index(drop=True) if target != "total" else d
    y_daily = d[target] / d[days_col]
    X = d[["hdd", "cdd"]]
    tr, va = slice(0, TRAIN), slice(TRAIN, TRAIN + VALID)
    mdl = LinearRegression().fit(X[tr], y_daily[tr])
    p = mdl.predict(X[va])
    a = y_daily[va].values
    days = d[days_col][va].values
    pm, am = p * days, d[target][va].values
    n = len(a)
    r = {
        "cv_rmse": np.sqrt(((a - p) ** 2).sum() / n) / a.mean() * 100,
        "r2": 1 - ((a - p) ** 2).sum() / ((a - a.mean()) ** 2).sum(),
        "annual_error": (pm.sum() - am.sum()) / am.sum() * 100,
        # ASHRAE G14 (월 합계, n−p)
        "g14_cv": np.sqrt(((am - pm) ** 2).sum() / (n - P)) / am.mean() * 100,
        "g14_nmbe": (am - pm).sum() / ((n - P) * am.mean()) * 100,
        "valid": f"{d['ym'].iloc[TRAIN]}~{d['ym'].iloc[TRAIN + VALID - 1]}",
    }
    return r


def metrics_monthly(df, target="elec"):
    """같은 모델(일평균 학습)의 예측을 월 합계로 되돌려 CV·R²를 '월 합계 기준'으로 계산"""
    d = df.dropna(subset=[target]).reset_index(drop=True)
    y = d[target] / d["days"]
    mdl = LinearRegression().fit(d[["hdd", "cdd"]][:TRAIN], y[:TRAIN])
    pm = mdl.predict(d[["hdd", "cdd"]][TRAIN:TRAIN + VALID]) * d["days"][TRAIN:TRAIN + VALID].values
    am = d[target][TRAIN:TRAIN + VALID].values
    return {
        "cv_rmse": np.sqrt(((am - pm) ** 2).mean()) / am.mean() * 100,
        "r2": 1 - ((am - pm) ** 2).sum() / ((am - am.mean()) ** 2).sum(),
        "annual_error": (pm.sum() - am.sum()) / am.sum() * 100,
        "g14_cv": np.sqrt(((am - pm) ** 2).sum() / (len(am) - P)) / am.mean() * 100,
        "g14_nmbe": (am - pm).sum() / ((len(am) - P) * am.mean()) * 100,
        "valid": f"{d['ym'].iloc[TRAIN]}~{d['ym'].iloc[TRAIN + VALID - 1]}",
    }


def row(name, r):
    out(f"  {name:<34} CV {r['cv_rmse']:6.2f}%  R² {r['r2']:.3f}  연합계 {r['annual_error']:+6.2f}%  "
        f"| G14 CV {r['g14_cv']:6.2f}%  NMBE {r['g14_nmbe']:+6.2f}%  [{r['valid']}]")


def main_(db, bld_id, backup):
    out(f"DB: {os.path.abspath(db)}  (수정 {pd.Timestamp(os.path.getmtime(db), unit='s', tz='UTC').tz_convert('Asia/Seoul')})")
    raw, w, df = load(db, bld_id)
    inventory(raw, w, df)

    out("■ 2. 조건별 지표  (각 줄은 한 가지 조건만 바꾼 결과)")
    base = metrics(df)
    row("A. 현재 baseline.py 조건 (total)", base)
    row("B. 전기만", metrics(df, "elec"))
    row("C. 가스만", metrics(df, "gas"))
    d2 = df.copy()
    d2["cal_days"] = pd.PeriodIndex(d2["ym"], freq="M").days_in_month
    row("D. 일수 = 달력 일수", metrics(d2, "total", "cal_days"))
    row("E. 전기만 · 지표를 월 합계 기준으로", metrics_monthly(df, "elec"))
    out()
    out("  ※ A·B·C·E 는 모두 같은 방식(일평균 사용량 ~ HDD+CDD 선형회귀, 앞 24행 학습·다음 12행 검증)이며")
    out("    '무엇을 예측하나(전체/전기/가스)'와 '지표를 일평균/월합계 중 무엇으로 재나'만 다르다.")
    out()

    out("■ 3. 저장된 값과 비교")
    out(f"  DB 재계산(A, 반올림 전): CV {base['cv_rmse']:.2f}%  R² {base['r2']:.3f}  연합계 {base['annual_error']:+.2f}%")
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from baseline import run_baseline
        m = run_baseline(df)["metrics"]
        out(f"  baseline.run_baseline()  : {m}   ← A와 같아야 정상")
    except Exception as e:
        out(f"  baseline.run_baseline() 실행 실패: {e}")
    for path in backup:
        if os.path.exists(path):
            b = json.load(open(path, encoding="utf-8"))
            bm = b.get("baseline", {}).get("metrics")
            ew = b.get("baseline", {}).get("eval_window", {})
            meta = b.get("meta", {})
            out(f"  {path}: {bm}  검증 {ew.get('valid')} · 전체 {ew.get('total_months')}행 · "
                f"생성 {meta.get('generated_at', '기록 없음')} · DB해시 {meta.get('db', {}).get('sha256_12', '기록 없음')}")
            out(f"    파일 수정 시각 {pd.Timestamp(os.path.getmtime(path), unit='s', tz='UTC').tz_convert('Asia/Seoul')}")
    out("  제안서 7p 기재값(baseline.py 주석): CV 15.0% · R² 0.661 · 합계 약 5%  — 재현 조건 미확인")
    out()
    out("  판독: A와 백업이 다르면 → 백업 이후 DB가 다시 만들어졌거나 코드가 바뀐 것 (load_data.py 재실행 여부 확인)")
    out("        B가 제안서 값에 가까우면 → 제안서 수치는 전기 단독 기준")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="savebridge.db")
    ap.add_argument("--bld", type=int, default=1)
    ap.add_argument("--backup", nargs="*", default=["web/backup.json", "backup.json"])
    a = ap.parse_args()
    main_(a.db, a.bld, a.backup)
    with open("verify_log.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    print("\n→ verify_log.txt 저장")
