"""
가상 단독주택 시연 데이터 만들기 — 건물 3  (2026-10-24 회의: 대상 건물을 단독주택으로)

  python make_virtual_house.py      ← savebridge.db 에 건물 3 을 넣는다(있으면 바꾼다). 건물 1·2 는 건드리지 않는다.
  load_data.py 로 DB 를 다시 만들면 건물 3 이 사라지니, 그 뒤에 이 파일을 다시 실행할 것.

단독주택은 공공 에너지데이터가 없다(건물 1 처럼 공공데이터로 받을 수 없다). 그래서 실측이 아니라,
건물 1(서울 실측)의 월별 사용 '패턴'을 한 가구 규모로 줄인 가상 데이터다.
화면·API 어디서든 '가상 데이터'로 표시된다. 실제 어느 집의 사용량으로 발표하면 안 된다.

  규모(최근 1년) : 전기 ANNUAL_ELEC kWh · 도시가스 ANNUAL_GAS kWh  ← 출처 확인 후 맞춘다
  기저선 지표    : 전기·가스를 서로 다른 비율로 줄여 합계 패턴이 달라지므로 건물 1 과 다르게 나온다
"""
import sqlite3
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "savebridge.db")

BLD = 3
SRC_BLD = 1
ANNUAL_ELEC = 4000      # kWh/년 ← 출처 확인 후 교체
ANNUAL_GAS = 14000      # kWh/년 ← 출처 확인 후 교체
SOURCE = "simulated_house_demo"
ROW = (BLD, "서울 ○○구 ○○동 단독주택 (가상)", "서울특별시", "11680", "10300", "0123", "0004",
       132.0, "조적조", "단독주택", "19980610", 1998, "지상2", None, SOURCE)


def main():
    c = sqlite3.connect(DB)
    src = c.execute("SELECT ym, elec, gas FROM usage_monthly WHERE bld_id = ? ORDER BY ym", (SRC_BLD,)).fetchall()
    # 가장 최근 완전한 12개월(둘 다 값이 있는 달)로 비율을 잡는다
    full = [r for r in src if r[1] is not None and r[2] is not None][-12:]
    k_e = ANNUAL_ELEC / sum(r[1] for r in full)
    k_g = ANNUAL_GAS / sum(r[2] for r in full)
    c.execute("DELETE FROM building WHERE bld_id = ?", (BLD,))
    c.execute("DELETE FROM usage_monthly WHERE bld_id = ?", (BLD,))
    c.execute("INSERT INTO building VALUES (" + ",".join("?" * len(ROW)) + ")", ROW)
    for ym, e, g in src:
        e = None if e is None else round(e * k_e)
        g = None if g is None else round(g * k_g)
        t = None if e is None or g is None else e + g
        c.execute("INSERT INTO usage_monthly (bld_id, ym, elec, gas, total) VALUES (?,?,?,?,?)", (BLD, ym, e, g, t))
    c.commit()
    print(f"건물 {BLD}: 가상 단독주택 · {len(src)}개월 · 비율 전기 ×{k_e:.4f} · 가스 ×{k_g:.4f}")
    c.close()


if __name__ == "__main__":
    main()
