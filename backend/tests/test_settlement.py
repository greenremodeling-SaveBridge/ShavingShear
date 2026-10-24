"""정산 상태 규칙 — settlement_status() 단위 테스트 + /api/settlement 실제 호출"""
import main
from main import settlement_status as st


# ── 단위 테스트 (함수 직접) ─────────────────────────────
def test_데이터_없음():
    assert st(None, 0, 0, 3, "CONFIRMED")[0] == "INSUFFICIENT_DATA"


def test_전체_이상():
    code, why = st(None, 0, 3, 0, "CONFIRMED")
    assert code == "REVIEW_REQUIRED" and "전체" in why


def test_이상과_데이터없음_섞임_사유():
    code, why = st(None, 0, 1, 2, "CONFIRMED")
    assert code == "REVIEW_REQUIRED"
    assert "이상 감지 1개월" in why and "데이터 미공개 2개월" in why


def test_일부_이상은_공사전이면_추정():
    assert st(None, 2, 1, 0, "CONFIRMED")[0] == "ESTIMATED"


def test_공사전은_모델이_좋아도_추정():
    assert st(None, 3, 0, 0, "CONFIRMED")[0] == "ESTIMATED"


def test_공사완료_이전_기간은_추정():
    assert st("202501", 3, 0, 0, "CONFIRMED", period_start_ym="202307",
              actual_based=True)[0] == "ESTIMATED"


def test_실측기반_미구현이면_VERIFIED_불가():
    assert st("202501", 3, 0, 0, "CONFIRMED", period_start_ym="202601")[0] == "PROVISIONAL"


def test_모델_미달은_잠정():
    assert st("202501", 3, 0, 0, "RANGE", period_start_ym="202601",
              actual_based=True)[0] == "PROVISIONAL"


def test_VERIFIED는_모든_조건_충족시에만():
    assert st("202501", 3, 0, 0, "CONFIRMED", period_start_ym="202601",
              actual_based=True)[0] == "VERIFIED"


def test_현재_설정으로는_어떤_입력도_VERIFIED_아님():
    assert main.ACTUAL_BASED_SETTLEMENT is False
    for rf in (None, "202001", "202501", "209912"):
        for s in range(0, 4):
            for f in range(0, 4 - s):
                for v in ("CONFIRMED", "RANGE"):
                    for p in ("202001", "202601"):
                        assert st(rf, s, f, 3 - s - f, v, period_start_ym=p)[0] != "VERIFIED"


# ── API 실제 호출 (합성 DB) ─────────────────────────────
def test_api_분기별_상태(api):
    c, m, _ = api
    r = {q: c.get(f"/api/settlement?year={y}&quarter={qq}").json()
         for q, (y, qq) in {"정상": (2026, 1), "부분": (2023, 4), "전체": (2023, 3),
                            "미공개": (2026, 3), "섞임": (2026, 2)}.items()}
    assert r["정상"]["status_code"] == "ESTIMATED" and r["정상"]["saving_won"] > 0
    assert r["부분"]["status_code"] == "ESTIMATED" and r["부분"]["flagged_count"] == 1
    assert r["전체"]["status_code"] == "REVIEW_REQUIRED" and r["전체"]["saving_won"] is None
    assert r["미공개"]["status_code"] == "INSUFFICIENT_DATA" and r["미공개"]["saving_won"] is None
    # 2026 2분기: 4월만 데이터 있음 → 정산 1개월
    assert r["섞임"]["months_settled"] == 1


def test_api_공사후_모델통과일때만_VERIFIED(api, monkeypatch):
    """2026-10-22: 공사 후 '기저선 − 실측' 정산을 구현했다. 그래서 공사 후 + 모델 기준 통과일 때만 VERIFIED,
    모델이 기준 미달이면 PROVISIONAL, 공사 전 기간은 ESTIMATED."""
    c, m, db = api
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute("UPDATE building SET retrofit_ym='202501'")
    conn.commit(); conn.close()
    m._cache.clear()
    c.get("/api/baseline")
    m._cache[1]["verdict"] = "CONFIRMED"          # 모델이 기준을 통과했다고 가정
    pre = c.get("/api/settlement?year=2023&quarter=1").json()
    post = c.get("/api/settlement?year=2026&quarter=1").json()
    assert pre["status_code"] == "ESTIMATED"       # 공사 전 기간
    assert post["status_code"] == "VERIFIED" and post["actual_based"] is True
    m._cache[1]["verdict"] = "RANGE"              # 모델이 기준 미달이면
    assert c.get("/api/settlement?year=2026&quarter=1").json()["status_code"] == "PROVISIONAL"


def test_api_분배_합계_보존(api):
    c, _, _ = api
    s = c.get("/api/settlement?year=2026&quarter=1&owner_ratio=0.7").json()
    assert s["owner_won"] + s["tenant_won"] == s["saving_won"]
    assert s["saving_won"] == sum(x["saving_won"] for x in s["months"] if x["saving_won"])
