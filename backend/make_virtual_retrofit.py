"""
가상 공사 후 시연 데이터 만들기 — 건물 2(양평 블룸비스타, 이미 '가상 데이터'로 표시된 건물)  (2026-10-22)

  python make_virtual_retrofit.py          ← savebridge.db 의 건물 2 만 바꾼다. 건물 1(실측)은 건드리지 않는다.

이 건물의 사용량은 처음부터 실측이 아니다 (건물 1 사용량 복사). 여기에 '2025년 5월에 공사를 마쳤다'는
가상 시나리오를 얹어, 공사 후 정산이 어떻게 돌아가는지 처음부터 끝까지 보여 주기 위한 데이터다.
화면·챗봇·API 어디서든 '가상 데이터 · 가상 공사'로 표시된다. 실제 절감 실적으로 발표하면 안 된다.

  공사 완료      : 2025년 5월 (RETROFIT_YM)
  공사 후 사용량 : 복사 원본 × (전기 1 − 15%, 가스 1 − 30%)  ← 합계 약 20%: 이자지원 최소 요건 · 개선 대책 시나리오(15~26%) 안쪽
  운영 변화 1건  : 2025년 11월 가스를 과거 같은 달 평균의 2.1배로 (영업시간 연장 가정) → 그 달은 보류되는지 시연
"""
import sqlite3
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "savebridge.db")

BLD = 2
RETROFIT_YM = "202505"
CUT = {"elec": 0.15, "gas": 0.30}
EVENT = {"ym": "202511", "fuel": "gas", "ratio": 2.1}
SOURCE = "simulated_retrofit_demo"


def main():
    c = sqlite3.connect(DB)
    src = {r[0]: (r[1], r[2]) for r in c.execute("SELECT ym, elec, gas FROM usage_monthly WHERE bld_id = 1")}
    c.execute("DELETE FROM usage_monthly WHERE bld_id = ?", (BLD,))
    for ym, (e, g) in sorted(src.items()):
        if ym >= RETROFIT_YM:
            e = None if e is None else round(e * (1 - CUT["elec"]))
            g = None if g is None else round(g * (1 - CUT["gas"]))
            if ym == EVENT["ym"] and g is not None:
                past = [v for k, (_, v) in src.items() if k[4:] == ym[4:] and k < ym and v]
                g = round(sum(past) / len(past) * EVENT["ratio"])
        t = None if e is None or g is None else e + g
        c.execute("INSERT INTO usage_monthly (bld_id, ym, elec, gas, total) VALUES (?,?,?,?,?)", (BLD, ym, e, g, t))
    c.execute("UPDATE building SET retrofit_ym = ?, data_source = ? WHERE bld_id = ?", (RETROFIT_YM, SOURCE, BLD))
    c.commit()
    n = c.execute("SELECT COUNT(*) FROM usage_monthly WHERE bld_id = ? AND ym >= ?", (BLD, RETROFIT_YM)).fetchone()[0]
    print(f"건물 {BLD}: 공사 완료 {RETROFIT_YM} · 공사 후 {n}개월 (가상) · 운영 변화 {EVENT['ym']} 가스 ×{EVENT['ratio']}")
    c.close()


if __name__ == "__main__":
    main()
