"""실제 savebridge.db 로 지표·금액 재현 (DB 가 없으면 건너뜀)"""
import os
import sqlite3

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "savebridge.db")
pytestmark = pytest.mark.skipif(not os.path.exists(DB), reason="실제 DB 없음")


@pytest.fixture
def real(monkeypatch):
    monkeypatch.setenv("SB_USE_GEMINI", "0")
    import main
    monkeypatch.setattr(main, "DB", DB)
    main._cache.clear()
    from fastapi.testclient import TestClient
    yield TestClient(main.app), main
    main._cache.clear()


def test_전체기준_지표_재현_예선방식(real, monkeypatch):
    c, _ = real
    import baseline
    monkeypatch.setattr(baseline, "BASELINE_MODE", "legacy")
    b = c.get("/api/baseline").json()
    assert {k: b["metrics"][k] for k in ("cv_rmse", "r2", "annual_error")} == {"cv_rmse": 18.7, "r2": 0.655, "annual_error": -5.7}
    assert b["verdict"] == "RANGE"
    assert not b["metric_checks"]["cv_rmse"]["ok"] and not b["metric_checks"]["r2"]["ok"]
    assert b["eval_window"]["valid"] == "202202 ~ 202302" and b["eval_window"]["total_months"] == 74


def test_공사직전_36개월_기저선(real):
    c, _ = real
    b = c.get("/api/baseline").json()
    m = b["metrics"]
    assert (m["cv_rmse"], m["r2"], m["nmbe"]) == (12.6, 0.692, -2.6)
    assert b["metric_checks"]["cv_rmse"]["ok"] and not b["metric_checks"]["r2"]["ok"]
    w = b["eval_window"]
    assert w["train"] == "202305 ~ 202504" and w["valid"] == "202505 ~ 202604"
    assert w["train_used_months"] == 19 and "202308" in w["train_excluded"]
    assert {r["phase"] for r in b["monthly_baseline"]} == {"이전", "학습", "검증"}


def test_제안서_전기기준_재현():
    import sys
    sys.path.insert(0, ROOT)
    import verify_metrics as v
    _, _, df = v.load(DB, 1)
    b = v.metrics(df, "elec")
    assert round(b["cv_rmse"], 1) == 15.0 and round(b["r2"], 3) == 0.661
    e = v.metrics_monthly(df, "elec")
    assert round(e["cv_rmse"], 1) == 14.9 and round(e["r2"], 3) == 0.616


def test_validation_csv와_같은_예측():
    path = os.path.join(ROOT, "validation.csv")
    if not os.path.exists(path):
        pytest.skip("validation.csv 없음")
    import verify_metrics as v
    from sklearn.linear_model import LinearRegression
    _, _, df = v.load(DB, 1)
    y = df["elec"] / df["days"]
    m = LinearRegression().fit(df[["hdd", "cdd"]][:24], y[:24])
    pred = np.round(m.predict(df[["hdd", "cdd"]][24:36]) * df["days"][24:36].values)
    val = pd.read_csv(path, dtype={"ym": str})
    assert list(val["ym"]) == list(df["ym"][24:36])
    assert np.allclose(pred, val["예측(월)"].values, atol=1)


def test_분배_정산_금액_일치(real):
    c, m = real
    base = c.get("/api/baseline").json()
    alloc = c.post("/api/allocation", json={"invest_won": 50_000_000, "owner_ratio": 0.7}).json()
    last12 = [x["ym"] for x in base["monthly_baseline"]][-12:]
    assert sum(m.month_won(1, ym) for ym in last12) == alloc["annual_saving_won"]
    sb = base["saving_basis"]
    assert sb["elec_saving_won"] == int(sb["annual_elec_kwh"] * 0.2 * 125) or abs(
        sb["elec_saving_won"] - sb["annual_elec_kwh"] * 0.2 * 125) < 1


def test_시연분기_상태(real):
    c, _ = real
    exp = {(2026, 1): "ESTIMATED", (2023, 4): "ESTIMATED", (2023, 3): "REVIEW_REQUIRED",
           (2026, 3): "INSUFFICIENT_DATA"}
    for (y, q), code in exp.items():
        assert c.get(f"/api/settlement?year={y}&quarter={q}").json()["status_code"] == code


def test_건물2_가상표시(real):
    c, _ = real
    assert c.get("/api/baseline?bld_id=2").json()["data_origin"]["is_simulated"]
    assert not c.get("/api/baseline?bld_id=1").json()["data_origin"]["is_simulated"]


def test_가상공사_건물_공사후_정산(real):
    """건물 2: 가상 공사(2025.05) — 공사 후 분기는 '기저선 − 실측'으로 계산하고, 모델 기준 미달이면 잠정, 이상 달은 제외"""
    c, m = real
    b = c.get("/api/baseline?bld_id=2").json()
    assert b["retrofit_ym"] == "202505" and b["data_origin"]["is_simulated"]
    assert b["eval_window"]["valid"].endswith("202504")              # 기저선은 공사 전 데이터만
    assert b["saving_basis"]["actual_based"] is True
    assert any(r["phase"] == "공사 후" for r in b["monthly_baseline"])
    q1 = c.get("/api/settlement?bld_id=2&year=2026&quarter=1&owner_ratio=0.7").json()
    assert q1["status_code"] == "PROVISIONAL" and q1["actual_based"] is True
    assert q1["owner_won"] + q1["tenant_won"] == max(0, q1["saving_won"])
    q4 = c.get("/api/settlement?bld_id=2&year=2025&quarter=4&owner_ratio=0.7").json()
    assert [x["state"] for x in q4["months"]] == ["정산", "확인 중", "정산"]
    q_pre = c.get("/api/settlement?bld_id=2&year=2025&quarter=1&owner_ratio=0.7").json()
    assert q_pre["status_code"] == "ESTIMATED"                       # 공사 전 분기는 시뮬레이션
    d = c.get("/api/demo?bld_id=2").json()
    assert any(x["post"] for x in d["cases"])
    # 실측 건물 1은 그대로 공사 전
    assert c.get("/api/baseline?bld_id=1").json()["retrofit_ym"] is None
