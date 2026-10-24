"""주요 API 응답 필드 유지 — 프론트·backup.json 이 쓰는 키가 빠지지 않았는지"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP = json.load(open(os.path.join(ROOT, "tests", "fixtures", "backup_old.json"), encoding="utf-8"))


def keys_superset(new, old, path=""):
    missing = []
    for k in old:
        if k not in new:
            missing.append(path + k)
    return missing


def test_baseline_필드(api):
    c, _, _ = api
    r = c.get("/api/baseline").json()
    assert not keys_superset(r, BACKUP["baseline"])
    assert r["eval_window"]["train_months"] == 24 and r["eval_window"]["valid_months"] == 12


def test_settlement_필드(api):
    c, _, _ = api
    for k, old in BACKUP["settlement"].items():
        y, q = k.split("Q")
        r = c.get(f"/api/settlement?year={y}&quarter={q}").json()
        assert not keys_superset(r, old), k


def test_building_필드와_matched(api):
    c, _, _ = api
    ok = c.get("/api/building?sigungu=11680&bjdong=10100&bun=0761&ji=0026").json()
    bad = c.get("/api/building?sigungu=0&bjdong=0&bun=0&ji=0").json()
    assert not keys_superset(ok, BACKUP["building"])
    assert ok["matched"] is True and bad["matched"] is False


def test_measures_profile_필드(api):
    c, _, _ = api
    assert not keys_superset(c.get("/api/measures").json(), BACKUP["measures"])
    assert not keys_superset(c.get("/api/profile").json(), BACKUP["profile"])


def test_explain_필드_와_미공개월(api):
    c, _, _ = api
    r = c.get("/api/explain?ym=202608").json()
    assert not keys_superset(r, BACKUP["explain"]["202608"])
    assert r["action"] == "데이터 없음"


def test_allocation(api):
    c, _, _ = api
    r = c.post("/api/allocation", json={"invest_won": 50_000_000, "owner_ratio": 0.7}).json()
    assert not keys_superset(r, BACKUP["allocation"][13])
    assert r["owner_annual_won"] + r["tenant_annual_won"] == r["annual_saving_won"]


def test_explain_잘못된_ym은_400(api):
    c, _, _ = api
    for bad in ("abc", "2026", "202613", "20260a"):
        assert c.get(f"/api/explain?ym={bad}").status_code == 400
