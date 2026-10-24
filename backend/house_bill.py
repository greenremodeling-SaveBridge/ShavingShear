"""
단독주택 전기·가스 고지서 계산 — 달마다 실제 요금표로 (2026-10-25)

평균단가 × kWh 대신, 한전 주택용 저압 누진 요금표와 서울도시가스 주택용 요금표로 달마다 고지서 금액을 낸다.
태양광은 달마다 발전량을 빼고, 남는 전기는 다음 달로 넘긴다(상계). 남는 전기를 돈으로 받지는 않는다.

  전기 (한전 주택용 저압, 2023.11.9 시행 요금표 · 현행)
    기타계절 구간 200 / 400 kWh, 하계(7~8월) 300 / 450 kWh
    기본요금 910 / 1,600 / 7,300 원 · 전력량요금 120.0 / 214.6 / 307.3 원/kWh (구간별 누진)
    기후환경요금 9 원/kWh · 연료비조정요금 5 원/kWh
    부가가치세 10% · 전력산업기반기금 FUND_RATE (요금에 정률)
  가스 (서울도시가스 주택용 2026.10.1) 기본요금 1,250 원/월 + 22.5268 원/MJ (1 kWh = 3.6 MJ) · 부가세 10%
"""

TIERS = {"normal": (200, 400), "summer": (300, 450)}
BASIC = (910, 1_600, 7_300)
RATE = (120.0, 214.6, 307.3)
CLIMATE = 9.0
FUEL_ADJ = 5.0
VAT = 0.10
FUND_RATE = 0.027          # 전력산업기반기금 · 2025.7 부터 2.7% (확인 중이면 교체)
MIN_CHARGE = 0             # 주택용 최저요금 (확인 후 교체)

GAS_BASIC = 1_250
GAS_WON_PER_MJ = 22.5268
MJ_PER_KWH = 3.6

# 태양광 월별 발전 비율(1~12월, 합 1.0) · 확인 전에는 고르게
PV_PROFILE = [1 / 12] * 12


def elec_bill(kwh, month):
    """한 달 전기 고지서(원) · kwh 는 상계 후 청구 사용량"""
    kwh = max(0.0, kwh)
    a, b = TIERS["summer" if month in (7, 8) else "normal"]
    if kwh <= a:
        basic, energy = BASIC[0], kwh * RATE[0]
    elif kwh <= b:
        basic, energy = BASIC[1], a * RATE[0] + (kwh - a) * RATE[1]
    else:
        basic, energy = BASIC[2], a * RATE[0] + (b - a) * RATE[1] + (kwh - b) * RATE[2]
    base = max(MIN_CHARGE, basic + energy + kwh * (CLIMATE + FUEL_ADJ))
    total = base * (1 + VAT + FUND_RATE)
    return int(total // 10 * 10)                       # 10원 미만 버림


def gas_bill(kwh):
    """한 달 도시가스 고지서(원)"""
    base = GAS_BASIC + max(0.0, kwh) * MJ_PER_KWH * GAS_WON_PER_MJ
    return int(base * (1 + VAT) // 10 * 10)


def year_elec(monthly_kwh, keep=1.0, pv_kwh=0.0):
    """1년 전기 고지서 합(원) · monthly_kwh: [(month, kWh)] 12개 · keep: 비율형 대책 뒤 남는 비율 · pv_kwh: 연 발전량"""
    carry, total = 0.0, 0
    for month, kwh in monthly_kwh:
        use = kwh * keep
        have = pv_kwh * PV_PROFILE[month - 1] + carry
        billed, carry = (0.0, have - use) if have >= use else (use - have, 0.0)
        total += elec_bill(billed, month)
    return total


def year_gas(monthly_kwh, keep=1.0):
    return sum(gas_bill(kwh * keep) for _, kwh in monthly_kwh)
