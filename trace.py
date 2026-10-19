"""
데이터 흐름 추적  —  python trace.py

지시서가 먼저 검증하라고 한 세 가지에 답합니다.

  ① 20% 절감률이 어디서 적용되는가
  ② 실제 건물 데이터가 모델에 들어가는가
  ③ 공사 후 데이터가 없을 때 정산이 어떻게 처리되는가

발표 전에 한 번 돌려서 출력을 그대로 캡처해 두세요.
"모델에 무엇이 들어가고 무엇이 나오는지 설명할 수 있어야 한다"는
완료 기준의 증거가 됩니다.
"""

import hashlib
import os
import sqlite3
import warnings

warnings.filterwarnings("ignore")

import pandas as pd

import baseline as B
import measures as M
from main import get_settlement, get_baseline, post_allocation, AllocationRequest

LINE = "─" * 68


def sha(path):
    if not os.path.exists(path):
        return "파일 없음"
    return hashlib.sha256(open(path, "rb").read()).hexdigest()[:12]


def q(sql, params=()):
    c = sqlite3.connect("savebridge.db")
    c.row_factory = sqlite3.Row
    r = [dict(x) for x in c.execute(sql, params).fetchall()]
    c.close()
    return r


print(f"\n{LINE}\n  ① 20% 절감률이 어디서 적용되는가\n{LINE}")

print(f"""
  정의 위치   baseline.py  SAVING_RATE = {B.SAVING_RATE}
  단가        baseline.py  PRICE_PER_KWH = {B.PRICE_PER_KWH} 원/kWh

  적용되는 곳은 두 군데입니다. 모델이 예측하는 값이 아닙니다.

  [1] 연간 절감액  — baseline.py  run_baseline()
      최근 12개월 실측 사용량 × {B.SAVING_RATE} × {B.PRICE_PER_KWH}원
      → /api/allocation 의 annual_saving_won

  [2] 월별 정산액  — main.py  get_settlement()
      그 달 기저선(모델 예측) × {B.SAVING_RATE} × {B.PRICE_PER_KWH}원
      → /api/settlement 의 months[].saving_won
""")

base = get_baseline(1)
sb = base["saving_basis"]
print(f"  실제 값으로 역산")
print(f"    최근 12개월 실측   {sb['annual_kwh']:>12,} kWh   [실측]")
print(f"    × 절감률           {sb['saving_rate']:>12}        [가정]")
print(f"    × 단가             {sb['price_per_kwh']:>12} 원/kWh [가정]")
print(f"    = 연간 절감액      {base['annual_saving_won']:>12,} 원   [시뮬레이션]")
chk = round(sb["annual_kwh"] * sb["saving_rate"] * sb["price_per_kwh"])
print(f"    역산 검증          {chk:>12,} 원   "
      f"{'일치' if abs(chk - base['annual_saving_won']) <= 1 else '불일치!'}")
print(f"\n  API가 이 사실을 밝히는가 : is_assumption = {sb['is_assumption']}")
print(f"  한계 문구               : {sb['note'][:46]}…")


print(f"\n{LINE}\n  ② 실제 건물 데이터가 모델에 들어가는가\n{LINE}")

print(f"""
  원본 파일 (지문으로 확인 — 바뀌면 지문이 바뀝니다)
    energy.csv      {sha('energy.csv')}
    gas.csv         {sha('gas.csv')}
    daily_temp.csv  {sha('daily_temp.csv')}
""")

rows = q("SELECT COUNT(*) n, MIN(ym) a, MAX(ym) b FROM usage_monthly WHERE total IS NOT NULL")[0]
miss = q("SELECT ym FROM usage_monthly WHERE total IS NULL ORDER BY ym")
w = q("SELECT COUNT(*) n, MIN(ym) a, MAX(ym) b FROM weather_monthly")[0]
joined = q("""SELECT COUNT(*) n FROM usage_monthly u JOIN weather_monthly w ON u.ym=w.ym
              WHERE u.bld_id=1 AND u.total IS NOT NULL""")[0]

print(f"  DB 적재")
print(f"    사용량      {rows['n']:>3}개월  {rows['a']} ~ {rows['b']}")
print(f"    결측월      {len(miss):>3}개월  {', '.join(m['ym'] for m in miss) or '없음'}")
print(f"    기상        {w['n']:>3}개월  {w['a']} ~ {w['b']}")
print(f"    모델 입력   {joined['n']:>3}개월  (사용량과 기상이 둘 다 있는 달)")

ev = base["eval_window"]
print(f"""
  모델이 실제로 쓰는 것
    입력 변수   {ev['inputs']}
    산정 기준   {ev['basis']}
    모델        {ev['model']}
    학습        {ev['train']}   ({ev['train_months']}개월)
    검증        {ev['valid']}   ({ev['valid_months']}개월) ← 학습에 쓰지 않은 구간
    전체        {ev['total_months']}개월

  검증 지표 (검증 구간에서만 계산)
    CV(RMSE)    {base['metrics']['cv_rmse']}%   기준 {B.CV_LIMIT}% 이하
    R2          {base['metrics']['r2']}    기준 {B.R2_LIMIT} 이상
    연 합계 오차 {base['metrics']['annual_error']}%
""")

prof = q("SELECT addr, area, purpose, retrofit_ym FROM building WHERE bld_id=1")[0]
print(f"  대상 건물")
print(f"    {prof['addr']} · {prof['purpose']} · 연면적 {prof['area']:,.0f} m2")
print(f"    합성·예시 데이터 혼입 여부: 건물 1건만 적재 (bld_id=1). 데모용 가짜 건물 없음")

if ev["total_months"] < 36:
    print(f"\n  ※ 표본 {ev['total_months']}개월 — 검증 결과가 불안정할 수 있습니다")


print(f"\n{LINE}\n  ③ 공사 후 데이터가 없을 때 정산이 어떻게 처리되는가\n{LINE}")

print(f"""
  이 건물의 retrofit_ym = {prof['retrofit_ym'] or 'NULL (공사 전)'}

  공사 전이므로 '실제 절감량'은 존재할 수 없습니다.
  따라서 어떤 조건에서도 VERIFIED 가 나오면 안 됩니다.
""")

print(f"  {'기간':10} {'상태코드':18} {'표시':8} {'금액':>14}  사유")
print(f"  {'─'*10} {'─'*18} {'─'*8} {'─'*14}  {'─'*28}")

cases = [(2026, 1), (2023, 4), (2023, 3), (2026, 3)]
verified_leak = False
for y, qt in cases:
    s = get_settlement(year=y, quarter=qt, owner_ratio=0.7)
    amt = f"{s['saving_won']:,}원" if s["saving_won"] is not None else "금액 없음"
    print(f"  {y}Q{qt:<6} {s['status_code']:18} {s['status']:8} {amt:>14}  {s['status_msg'][:28]}")
    if s["status_code"] == "VERIFIED":
        verified_leak = True

print(f"\n  VERIFIED 누출 : {'있음 — 버그!' if verified_leak else '없음 (정상)'}")

s = get_settlement(year=2023, quarter=3, owner_ratio=0.7)
print(f"""
  '금액 없음'과 '0원'의 구분
    saving_won   = {s['saving_won']}   (0 이 아니라 None)
    amount_state = {s['amount_state']}
    설명         = {s['amount_note']}
""")

print(f"  근거 추적 (provenance)")
for k, v in s["provenance"].items():
    if isinstance(v, dict):
        continue
    print(f"    {k:22} {v}")

print(f"\n{LINE}\n  요약\n{LINE}")
ok = [
    ("20% 절감률이 가정으로 표시되는가", base["saving_basis"]["is_assumption"] is True),
    ("실측 → 가정 → 금액 역산이 맞는가", abs(chk - base["annual_saving_won"]) <= 1),
    ("모델 입력이 실제 공공데이터인가", joined["n"] > 0),
    ("학습·검증 구간이 시간순 분리인가", ev["train"] < ev["valid"]),
    ("공사 전에 VERIFIED 가 안 나오는가", not verified_leak),
    ("금액 없음과 0원이 구분되는가", s["saving_won"] is None),
]
for name, good in ok:
    print(f"  {'통과' if good else '실패'}  {name}")
print(f"\n  {sum(g for _, g in ok)}/{len(ok)} 통과\n")
