"""운영 변화 탐지(regime.py) 테스트.

합성 자료(기온 → 사용량 + 잡음)로 '변화 없음 / 위로 변화 / 아래로 변화 / 짧은 자료'를 확인하고,
실제 DB 가 있으면 ① 기존 지표 숫자가 그대로인지 ② 이 건물에서 변화 시점이 2023년 초로 잡히는지 확인한다.
"""
import os
import sqlite3

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "savebridge.db")

import regime  # noqa: E402  (conftest 가 ROOT 를 sys.path 에 넣는다)


def _synth(n=60, shift_at=None, shift_pct=0.0, seed=0, noise=0.04):
    rng = np.random.default_rng(seed)
    yms, hdd, cdd, days = [], [], [], []
    for i in range(n):
        y, m = 2020 + i // 12, i % 12 + 1
        yms.append(f"{y}{m:02d}")
        t = 13 - 14 * np.cos((m - 1) / 12 * 2 * np.pi)          # 월평균 기온 비슷한 곡선
        hdd.append(max(0.0, 21.5 - t))
        cdd.append(max(0.0, t - 16.0))
        days.append(30)
    hdd, cdd = np.array(hdd), np.array(cdd)
    gas = 100 + 30 * hdd
    elec = 200 + 6 * cdd + 2 * hdd
    if shift_at is not None:
        k = np.arange(n) >= shift_at
        gas = gas + k * shift_pct * gas.mean()          # 사용량 평균의 shift_pct 만큼 수준이 이동
    gas = gas * (1 + rng.normal(0, noise, n))
    elec = elec * (1 + rng.normal(0, noise, n))
    return pd.DataFrame({"ym": yms, "elec": elec * 30, "gas": gas * 30, "total": (elec + gas) * 30,
                         "hdd": hdd, "cdd": cdd, "days": days})


def test_변화_없으면_탐지_안함():
    for seed in range(5):
        r = regime.detect_regime_shift(_synth(seed=seed))
        assert r["detected"] is False, (seed, r)


def test_위로_변화를_찾는다():
    df = _synth(shift_at=40, shift_pct=0.4)
    r = regime.detect_regime_shift(df, train_start_ym=df["ym"].iloc[44])
    assert r["detected"] is True
    h = r["headline"]
    assert h["fuel"] == "가스" and h["direction"] == "up"
    # 시작 시점 ±2개월 (월 자료의 한계)
    i = list(df["ym"]).index(h["onset_ym"])
    assert abs(i - 40) <= 2, h
    assert 30 <= h["change_pct"] <= 90, h
    assert r["train_after_shift"] is True


def test_학습구간이_변화_이전을_포함하면_알려준다():
    df = _synth(shift_at=40, shift_pct=0.4)
    r = regime.detect_regime_shift(df, train_start_ym=df["ym"].iloc[24])
    assert r["detected"] is True and r["train_after_shift"] is False
    assert "재검토" in r["message"]


def test_아래로_변화도_찾는다():
    df = _synth(shift_at=40, shift_pct=-0.3)
    r = regime.detect_regime_shift(df)
    assert r["detected"] is True and r["headline"]["direction"] == "down"


def test_자료가_짧으면_탐지하지_않는다():
    r = regime.detect_regime_shift(_synth(n=30))
    assert r["detected"] is False and r["reason"] == "too_short"


def test_연료_열이_없어도_죽지_않는다():
    df = _synth(shift_at=40, shift_pct=0.4).drop(columns=["gas"])
    r = regime.detect_regime_shift(df)
    assert "detected" in r


def test_기온_보정_이상점수_튀는_달을_잡고_정상_달은_안_잡는다():
    df = _synth(n=48, seed=3)
    i = 30
    df.loc[i, "gas"] *= 2.5
    reg = regime.detect_regime_shift(df)
    out = regime.adjusted_anomalies(df, reg)
    assert any(a["ym"] == df["ym"].iloc[i] and a["fuel"] == "가스" and a["direction"] == "up" for a in out)
    assert len(out) <= 2, out                                   # 튀는 한 달 말고는 거의 안 잡힘


def test_추운_해는_이상이_아니다():
    """같은 달 평균 대비 1.8배 규칙은 혹한의 달을 이상으로 잡지만, 기온 보정 점수는 잡지 않는다."""
    df = _synth(n=48, seed=4, noise=0.02)
    i = 36                                    # 36 = 2023.01
    df.loc[i, "hdd"] *= 1.5                   # 유난히 추운 달 → 가스도 그만큼 더 씀
    df.loc[i, "gas"] = (100 + 30 * df.loc[i, "hdd"]) * 30
    df.loc[i, "elec"] = (200 + 6 * df.loc[i, "cdd"] + 2 * df.loc[i, "hdd"]) * 30
    out = regime.adjusted_anomalies(df, regime.detect_regime_shift(df))
    assert not any(a["ym"] == df["ym"].iloc[i] for a in out), out


# ── 실제 DB (없으면 건너뜀) ─────────────────────────────

@pytest.mark.skipif(not os.path.exists(DB), reason="실제 DB 없음")
def test_실제건물_기존_지표_불변_그리고_변화시점():
    import baseline
    conn = sqlite3.connect(DB)
    df = pd.read_sql(
        "SELECT u.ym,u.elec,u.gas,u.total,w.hdd,w.cdd,w.days FROM usage_monthly u "
        "JOIN weather_monthly w ON u.ym=w.ym WHERE u.bld_id=1 AND u.total IS NOT NULL ORDER BY u.ym", conn)
    conn.close()
    r = baseline.run_baseline(df)
    # 안전 모드: 기존 숫자는 그대로여야 한다
    assert r["metrics"] == {"cv_rmse": 12.6, "r2": 0.692, "annual_error": 2.6, "nmbe": -2.6}
    assert r["verdict"] == "RANGE"
    assert r["eval_window"]["train"] == "202305 ~ 202504"
    rs = r["regime_shift"]
    assert rs["detected"] is True
    assert rs["headline"]["fuel"] == "가스" and rs["headline"]["direction"] == "up"
    assert "202301" <= rs["headline"]["onset_ym"] <= "202305"        # 2023년 초
    assert rs["train_after_shift"] is True                            # 지금 학습 구간(2023.05~)은 변화 이후
