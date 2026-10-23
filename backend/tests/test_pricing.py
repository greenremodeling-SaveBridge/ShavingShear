"""P0-1·2: 분배와 정산 금액 기준 통일, 연료별 단가"""
import sqlite3

import pricing


def test_연료별_단가_분리():
    w = pricing.won(1000, 1000)
    assert w["elec_won"] == int(1000 * 0.2 * pricing.PRICES["elec"]["won_per_kwh"])
    assert w["gas_won"] == int(1000 * 0.2 * pricing.PRICES["gas"]["won_per_kwh"])
    assert w["elec_won"] != w["gas_won"]
    assert w["total_won"] == w["elec_won"] + w["gas_won"]
    assert all(p["source"] and "요금표" in p["source"] for p in pricing.PRICES.values())


def test_분배연간_정산12개월합_일치(api):
    c, m, _ = api
    base = c.get("/api/baseline").json()
    alloc = c.post("/api/allocation", json={"invest_won": 50_000_000, "owner_ratio": 0.7}).json()
    last12 = [x["ym"] for x in base["monthly_baseline"]][-12:]
    s12 = sum(m.month_won(1, ym) for ym in last12)
    assert s12 == alloc["annual_saving_won"] == base["annual_saving_won"]


def test_정산월금액_역산(api):
    c, m, db = api
    s = c.get("/api/settlement?year=2026&quarter=1").json()
    conn = sqlite3.connect(db)
    for row in s["months"]:
        e, g = conn.execute("SELECT elec, gas FROM usage_monthly WHERE ym=?", (row["ym"],)).fetchone()
        P = pricing.PRICES
        assert row["saving_won"] == int(e * 0.2 * P["elec"]["won_per_kwh"]) + int(g * 0.2 * P["gas"]["won_per_kwh"])
    conn.close()


def test_근거에_연료별_숫자(api):
    c, _, _ = api
    b = c.get("/api/baseline").json()["saving_basis"]
    assert b["annual_kwh"] == b["annual_elec_kwh"] + b["annual_gas_kwh"]
    assert "가스" in b["formula"] and b["prices"]["gas"]["won_per_kwh"] == 79.3


def test_지표_각각_판정(api):
    c, m, _ = api
    c.get("/api/baseline")
    mc = m._cache[1]["metric_checks"]
    assert {"cv_rmse", "r2"} <= set(mc) <= {"cv_rmse", "r2", "nmbe"} and all("ok" in v for v in mc.values())


def test_가상데이터_표시(api):
    c, m, db = api
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO building (bld_id, addr, sido, sigungu, bjdong, bun, ji, area, purpose,"
                 " use_apr_day, year) VALUES (2,'양평','경기도','41830','32330','1235','0000',"
                 "12500,'숙박시설','20140515',2014)")
    conn.execute("INSERT INTO usage_monthly SELECT 2, ym, elec, gas, total FROM usage_monthly WHERE bld_id=1")
    conn.commit(); conn.close()
    b2 = c.get("/api/building?sigungu=41830&bjdong=32330&bun=1235&ji=0000").json()
    assert b2["data_origin"]["is_simulated"] and b2["data_origin"]["label"] == "가상 데이터"
    assert c.get("/api/usage?bld_id=2").json()["data_origin"]["is_simulated"]
    assert c.get("/api/baseline?bld_id=2").json()["data_origin"]["is_simulated"]
    assert not c.get("/api/baseline?bld_id=1").json()["data_origin"]["is_simulated"]
