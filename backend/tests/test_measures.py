"""절감량·중복 보정 교차 검증 — 손계산과 비교"""
import pytest
from measures import apply_measures, MEASURES, EMISSION_FACTORS

YEARS = [{"year": "2025", "elec": 252247, "gas": 157954, "total": 410201}]   # backup.json 2025년 값


def by_id(r):
    return {m["id"]: m for m in r["measures"]}


def test_개별_대책_손계산():
    r = by_id(apply_measures(YEARS, ["window"]))["window"]
    assert r["saving_kwh_low"] == round(157954 * 0.10)
    assert r["saving_kwh_high"] == round(157954 * 0.20)
    assert r["co2_kg_low"] == round(157954 * 0.10 * EMISSION_FACTORS["gas"]["value"])


def test_단일_대책은_보정_없음():
    r = apply_measures(YEARS, ["window"])
    assert r["naive_sum_kwh"] == r["total_saving_kwh"]
    assert r["overlap_adjust_kwh"] == [0, 0]


def test_가스_3개_곱셈_누적():
    r = apply_measures(YEARS, ["window", "envelope", "boiler"])
    lo = 157954 * (1 - 0.9 * 0.85 * 0.9)
    hi = 157954 * (1 - 0.8 * 0.7 * 0.85)
    assert r["by_fuel"]["gas"]["saving_kwh_low"] == round(lo)
    assert r["by_fuel"]["gas"]["saving_kwh_high"] == round(hi)
    assert r["total_saving_kwh"][0] < r["naive_sum_kwh"][0]      # 단순합보다 작아야 함


def test_연료가_다르면_곱하지_않음():
    r = apply_measures(YEARS, ["window", "led"])
    assert r["by_fuel"]["gas"]["saving_kwh_low"] == round(157954 * 0.10)
    assert r["by_fuel"]["elec"]["saving_kwh_low"] == round(252247 * 0.05)
    # 연료가 다르면 겹침 없음 → 단순합 = 총합 (반올림 차 ±1)
    assert abs(r["naive_sum_kwh"][0] - r["total_saving_kwh"][0]) <= 1


def test_전체_backup값과_일치():
    r = apply_measures(YEARS)
    assert r["total_saving_kwh"] == [61815, 107993]
    assert r["naive_sum_kwh"] == [67895, 127895]
    assert r["total_co2_kg"] == [15202, 27245]   # 전력 0.4173(2023 국가 고유값) · 가스 0.2020


def test_출처없는_값은_검증표시_금지():
    for m in MEASURES:
        if not m["source"]:
            assert m["basis"] != "reference"
    for ef in EMISSION_FACTORS.values():
        # 확인 표시(verified)는 출처와 기준연도가 적힌 값에만
        assert not ef["verified"] or (ef["source"] and ef["base_year"] != "확인 필요")
    for m in MEASURES:
        assert m["basis"] == "assumed"          # 개별 절감률은 문헌값이 아니라 가정값으로 남긴다


def test_빈_입력():
    assert apply_measures([])["available"] is False
