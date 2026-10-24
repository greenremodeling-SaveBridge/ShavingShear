"""설명 생성 — 폴백·숫자 변조·판정 변조 방지"""
import sys
import types

import pytest

import explain as ex

M_RANGE = {"cv_rmse": 19.4, "r2": 0.626, "annual_error": -7.6}
M_CV_ONLY = {"cv_rmse": 19.4, "r2": 0.80, "annual_error": -7.6}


def ctx(**kw):
    c = {"bld_id": 1, "ym": "202601", "month": 1, "verdict": "RANGE", "metrics": M_RANGE,
         "anomaly": None, "has_data": True, "simulated": True}
    c.update(kw)
    return c


@pytest.fixture(autouse=True)
def no_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "CACHE_FILE", tmp_path / "c.json")


def test_데이터없는_달은_정산문장_안씀():
    r = ex.explain(ctx(has_data=False, ym="202608", month=8))
    assert r["action"] == "데이터 없음"
    assert "정산" not in r["text"] and "예측 범위" not in r["text"]


def test_공사전은_예상치로_설명():
    t, a = ex.build_template(ctx())
    assert a == "예상치" and "예상치" in t and "줄었" not in t
    ok, hits = ex.verdict_ok(t, a)
    assert ok, hits


def test_충족한_지표를_미달이라고_안씀():
    t, _ = ex.build_template(ctx(metrics=M_CV_ONLY))
    assert "19.4%" in t and "0.8" not in t


def test_이상월은_확정보류():
    a = {"fuel": "가스", "ratio": 2.41}
    t, act = ex.build_template(ctx(anomaly=a))
    assert act == "확정 보류" and "2.41" in t


def test_API키_없음(monkeypatch):
    monkeypatch.setattr(ex, "USE_GEMINI", True)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert ex.explain(ctx())["source"] == "template:GEMINI_API_KEY 없음"


def test_기능_끔(monkeypatch):
    monkeypatch.setattr(ex, "USE_GEMINI", False)
    assert ex.explain(ctx())["source"] == "template:SB_USE_GEMINI=0"


def _fake_genai(monkeypatch, reply=None, exc=None):
    """google.genai 를 가짜로 바꿔 끼운다 — 네트워크 없이 성공·실패·시간초과 재현"""
    class Models:
        def generate_content(self, **kw):
            if exc:
                raise exc
            return types.SimpleNamespace(text=reply)

    class Client:
        def __init__(self, **kw):
            self.models = Models()

    genai = types.ModuleType("google.genai")
    genai.Client = Client
    t = types.ModuleType("google.genai.types")
    for n in ("HttpOptions", "GenerateContentConfig"):
        setattr(t, n, lambda **kw: kw)
    genai.types = t
    google = types.ModuleType("google")
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", t)
    monkeypatch.setattr(ex, "USE_GEMINI", True)
    monkeypatch.setenv("GEMINI_API_KEY", "test")


def test_성공_후_캐시(monkeypatch):
    _fake_genai(monkeypatch, reply="1월 금액은 공사 전 예상치입니다. 예측 오차는 19.4%입니다.")
    assert ex.explain(ctx())["source"] == "gemini"
    assert ex.explain(ctx())["source"] == "cache"


def test_시간초과(monkeypatch):
    _fake_genai(monkeypatch, exc=TimeoutError())
    assert ex.explain(ctx())["source"] == "template:호출 실패: TimeoutError"


def test_없던_숫자_폐기(monkeypatch):
    _fake_genai(monkeypatch, reply="1월 절감액은 3,570,000원입니다.")
    r = ex.explain(ctx())
    assert r["source"].startswith("template:없던 숫자") and "3,570,000" not in r["text"]


def test_숫자_바꿔치기_폐기(monkeypatch):
    _fake_genai(monkeypatch, reply="예측 오차는 14.9%로 양호합니다.")
    assert ex.explain(ctx())["source"].startswith("template:없던 숫자")


def test_판정_뒤집기_폐기(monkeypatch):
    _fake_genai(monkeypatch, reply="1월은 사용량이 줄었습니다. 금액을 확정했습니다.")
    assert ex.explain(ctx())["source"].startswith("template:판정과 모순")


def test_보류를_확정으로_폐기(monkeypatch):
    _fake_genai(monkeypatch, reply="1월 가스는 2.41배지만 정산 완료되었습니다.")
    r = ex.explain(ctx(anomaly={"fuel": "가스", "ratio": 2.41}))
    assert r["source"].startswith("template:판정과 모순")


def test_빈응답(monkeypatch):
    _fake_genai(monkeypatch, reply="")
    assert ex.explain(ctx())["source"] == "template:빈 응답"
