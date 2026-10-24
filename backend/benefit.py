"""
세이빙 셰어 — 단독주택 혜택 정리  (2026-10-24 회의 결정)

돈의 흐름
    세입자  : 공사로 줄어든 전기·가스 요금을 그대로 가져간다 (매달 고지서가 준다)
    집 비우기: 공사 중 집을 비우는 기간이 있으면, 그 기간은 관리비 할인으로 보상한다
               (금액·방법은 두 사람이 정한다 — 앱은 기간만 계산해 보여준다)
    건물주  : 절감액을 나눠 갖지 않는다. 건물(집) 가치 상승 + 그린리모델링 이자지원

※ 아래 상승률은 출처 확인 전의 가정값이다. verified=False 인 동안 화면에 '확인 중'으로 표시된다.
"""

VALUE_UPLIFT = {
    "rate_low": 0.03,
    "rate_high": 0.07,
    "verified": False,
    "source": "에너지 성능 개선 주택의 가격 상승률 (출처 확인 중)",
    "note": "집값은 위치·시장에 더 크게 좌우됩니다. 이 상승률은 같은 조건에서 에너지 성능만 달라졌을 때의 차이를 다룬 연구값입니다.",
}


def value_gain(property_won):
    """시세(원) → 건물 가치 상승 범위(원). 시세를 모르면 상승률만 돌려준다."""
    lo, hi = VALUE_UPLIFT["rate_low"], VALUE_UPLIFT["rate_high"]
    out = {**VALUE_UPLIFT, "rate_range": [lo, hi], "property_won": property_won or None}
    if property_won and property_won > 0:
        out["gain_won"] = [round(property_won * lo), round(property_won * hi)]
    return out
