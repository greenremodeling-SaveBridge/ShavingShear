"""
세이브브릿지 — 절감 금액 계산 단일 기준  (담당: 서현)

분배(/api/allocation)와 정산(/api/settlement)이 같은 함수로 금액을 만든다.
전에는 분배 = 실측 × 20% × 150원, 정산 = 기저선 × 20% × 150원 이라
같은 12개월인데 금액이 24% 달랐다.

■ 공사 전 시뮬레이션 금액 (현재)
    월 절감액 = 전기 실측 kWh × 절감률 × 전기 단가
              + 가스 실측 kWh × 절감률 × 가스 단가
    연간 절감액 = 최근 12개월 월 절감액의 합
  → 정산 화면 12개월 합 = 분배 화면 연간 금액 (반올림 차이 ±12원 이내)

  왜 기저선이 아니라 실측인가
    공사 전에는 '실제로 쓰는 양의 20%를 줄인다'는 시나리오다.
    기저선은 2020~2022년 데이터로 학습해 2023년 가스 단계 변화를 반영하지 못하고,
    최근 12개월을 실측보다 약 19% 낮게 잡는다 (백업 기준 9,959,910 / 12,336,600). 금액을 기저선에 걸면 모델 오차가 금액에 섞인다.

■ 공사 후 실제 정산 (미구현)
    월 절감액 = (기저선 − 실측) × 단가   ← 연료별 기저선이 필요. main.ACTUAL_BASED_SETTLEMENT
"""

SAVING_RATE = 0.20  # 2026 민간건축물 그린리모델링 이자지원: 공사 전 대비 에너지 성능개선 20% 이상이 신청 요건 → 최소 시나리오

PRICES = {
    "elec": {
        "name": "전기",
        "won_per_kwh": 125,
        "unit": "원/kWh",
        "is_assumption": False,
        # (여름 132.4×3 + 겨울 119.0×4 + 봄가을 91.9×5) / 12 = 111.1  + 기후환경요금 9 + 연료비조정 5 = 125.1
        "source": "한전 일반용(갑)Ⅰ 저압 전력량요금 월수 가중평균 111.1원 + 기후환경요금 9원 + 연료비조정 5원 (2025.4.1 요금표 · 2026년 4분기 동결)",
        "to_verify": "기본요금·부가세·전력기금 제외. 실제 건물은 계약종별(갑Ⅱ·을)·계절 사용 비중에 따라 다를 수 있음",
    },
    "gas": {
        "name": "도시가스",
        "won_per_kwh": 79.3,
        "unit": "원/kWh",
        "is_assumption": False,
        "source": "서울도시가스 영업용(1) 22.0349원/MJ × 3.6 MJ/kWh (2026.10.1 요금표)",
        "to_verify": "기본요금·부가세 제외. 공공데이터 가스 kWh 의 발열량 환산 기준(총·순발열량)은 미확인",
    },
}


def won(elec_kwh, gas_kwh, rate=SAVING_RATE):
    """한 달(또는 한 기간) 사용량 → 절감액(원). 연료별로 계산해 더한다."""
    e = (elec_kwh or 0) * rate * PRICES["elec"]["won_per_kwh"]
    g = (gas_kwh or 0) * rate * PRICES["gas"]["won_per_kwh"]
    return {"elec_won": int(e), "gas_won": int(g), "total_won": int(e) + int(g)}


def basis(annual_elec, annual_gas):
    """화면·provenance 에 그대로 보여줄 계산 근거. 역산 가능하게 숫자를 전부 남긴다."""
    w = won(annual_elec, annual_gas)
    return {
        "is_assumption": True,
        "formula": (f"최근 12개월 실측 (전기 kWh × {SAVING_RATE:.0%} × {PRICES['elec']['won_per_kwh']}원 "
                    f"+ 가스 kWh × {SAVING_RATE:.0%} × {PRICES['gas']['won_per_kwh']}원)"),
        "annual_kwh": round(annual_elec) + round(annual_gas),   # 연료별 합과 정확히 일치
        "annual_elec_kwh": round(annual_elec),
        "annual_gas_kwh": round(annual_gas),
        "saving_rate": SAVING_RATE,
        # 기존 키 유지 (프론트 호환). 연료별 단가는 prices 에 있다.
        "price_per_kwh": PRICES["elec"]["won_per_kwh"],
        "prices": PRICES,
        "elec_saving_won": w["elec_won"],
        "gas_saving_won": w["gas_won"],
        "note": ("공사 전이므로 절감량 실측값은 아직 없습니다. "
                 "절감률 20%는 2026 그린리모델링 이자지원 신청 최소 요건(성능개선 20% 이상)을 쓴 시나리오이고, "
                 "단가는 한전 일반용(갑)Ⅰ·서울도시가스 영업용(1) 요금표 기준입니다. "
                 "공사 후에는 이 자리에 기저선−실측 차이가 들어갑니다."),
    }
