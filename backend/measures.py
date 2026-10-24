"""
세이브브릿지 — 건축물 진단과 개선 대책  (담당: 건축·에너지)

본선 심사표에서 이 파일이 담당하는 배점
    건축물 이해도      20점   → diagnose()
    에너지 저감 방향성  25점   → apply_measures()

■ 이 파일의 원칙

  1. 데이터로 확인되는 것과 현장 확인이 필요한 것을 섞지 않는다.
     공공 에너지데이터만 보고 "단열이 나쁘다", "보일러가 노후됐다"고
     단정할 수 없다. 그건 현장 진단의 영역이다.

  2. 모든 숫자에 출처를 붙인다.
     measured  = 공공데이터에서 계산한 값
     reference = 문헌·지침에서 가져온 값   ← 출처를 반드시 채울 것
     assumed   = 근거를 밝힌 가정값

  3. 확인하지 못한 값은 비워 둔다. 그럴듯한 숫자로 채우지 않는다.

────────────────────────────────────────────────
★ 본선 전에 반드시 채워야 하는 항목
   아래에 VERIFY = False 로 표시된 값은 전부 확인이 필요합니다.
   공식 출처에서 값을 확인해 넣고 VERIFY = True 로 바꾸세요.
────────────────────────────────────────────────
"""

# ══════════════════════════════════════════════════════
#  온실가스 배출계수
#
#  ※ 아래 값은 임시값입니다. 반드시 확인하고 바꾸세요.
#
#  확인처
#    전력   : 온실가스종합정보센터 — 국가 고유 전력배출계수
#             https://www.gir.go.kr
#             ('국가 온실가스 배출계수' 승인 공고에서 기준연도와 값을 확인)
#    도시가스: 에너지관리공단 탄소중립 통계 — 에너지 발열량 및 배출계수
#             https://tips.energy.or.kr/carbon/Ggas_tatistics03.do
#
#  주의
#    전력배출계수는 갱신 주기가 3년에서 1년으로 바뀌었습니다.
#    발표 기준으로 가장 최근 승인된 값인지 확인하세요.
#    도시가스 값은 보통 Nm³ 기준으로 고시되므로,
#    우리 데이터 단위(kWh)로 환산한 근거를 함께 적어야 합니다.
# ══════════════════════════════════════════════════════

EMISSION_FACTORS = {
    "elec": {
        "value": 0.4173,                    # 2026-10-22 교체 (이전 0.4594)
        "unit": "kgCO2eq/kWh",
        "name": "전력",
        "source": "국가 고유 전력배출계수 0.4173 tCO2eq/MWh (2023년 기준 · 2025.12.18 국가 온실가스 통계관리위원회 확정)",
        "base_year": "2023",
        # 0.4594 tCO2eq/MWh 는 오래전 승인된 국가 전력배출계수로 널리 인용되는 값이다.
        # 최근 승인값으로 갱신됐을 수 있으므로 gir.go.kr 공고문(승인 연도·기준연도)을 확인할 것.
        "scope": "간접배출(Scope 2) · 소비단 기준 여부 확인 필요",
        "derivation": "0.4173 tCO2eq/MWh = 0.4173 kgCO2eq/kWh (단위 환산)",
        "verified": True,
    },
    "gas": {
        "value": 0.2020,                    # ← 확인 후 교체
        "unit": "kgCO2eq/kWh",
        "name": "도시가스(LNG)",
        "source": "IPCC 2006 지침 천연가스 CO2 기본 배출계수 56,100 kgCO2/TJ",
        "base_year": "IPCC 2006",
        "scope": "직접배출(Scope 1) · CO2만 (CH4·N2O 미포함)",
        # 0.2020 은 IPCC 2006 천연가스 기본 CO2 배출계수 56,100 kgCO2/TJ 를
        # kWh 로 환산한 값과 일치한다: 56,100 kg/TJ × 0.0000036 TJ/kWh = 0.20196 kg/kWh
        # 미확인: ① 공공데이터 가스 kWh 가 총발열량·순발열량 중 어느 기준으로 환산됐는가
        #         ② 국가 고유 계수(LNG)를 써야 하는가
        "derivation": "IPCC 2006 기본값 56,100 kgCO2/TJ × 3.6e-6 TJ/kWh = 0.2020 kgCO2/kWh (공공데이터 가스 kWh 의 발열량 기준은 미확인)",
        "verified": True,
    },
}


# ══════════════════════════════════════════════════════
#  개선 대책
#
#  rate 는 '그 대책이 해당 연료 사용량을 몇 % 줄이는가'입니다.
#  low~high 범위로 두고, 화면에는 범위째로 보여줍니다.
#  단일값으로 확정해 제시하지 않습니다.
#
#  ※ source 가 비어 있는 항목은 아직 근거가 없는 것입니다.
#    그린리모델링 사업 지침이나 기술자료에서 근거를 찾아 채우세요.
#    못 찾으면 그 대책은 빼는 게 낫습니다.
# ══════════════════════════════════════════════════════

SRC_COMPARE = "개별 절감률은 가정값. 비교 근거 — 4개 합계(15~26%)는 실제 사례보다 낮게 잡았다: 중앙보훈병원 별관 그린리모델링 컨설팅 23.1%·실시설계 44% (2026 그린리모델링 챌린지 본선 사전교육 발표), 노후 보건소 그린리모델링 시뮬레이션 39.6~45.4% (조정흠 외, 한국지열·수열에너지학회논문집 19(4), 2023)"

# 공사 기간(days)·집을 비우는 기간(vacate_days)은 일반적인 경우를 잡은 가정값이다. 현장마다 다르다.
MEASURES = [
    {
        "id": "window",
        "name": "창호 교체 (고단열 창호)",
        "target": "gas",
        "addresses": "난방 부하",
        "rate_low": 0.10, "rate_high": 0.20,
        "basis": "assumed",              # 출처 확인 전 — 시나리오 가정값
        "source": SRC_COMPARE,
        "needs_survey": True,
        "survey_note": "현재 창호의 유형·기밀 상태·면적 확인 필요",
        "days": 7, "vacate_days": 0,
    },
    {
        "id": "envelope",
        "name": "외피 단열 보강",
        "target": "gas",
        "addresses": "난방 부하",
        "rate_low": 0.15, "rate_high": 0.30,
        "basis": "assumed",              # 출처 확인 전 — 시나리오 가정값
        "source": SRC_COMPARE,
        "needs_survey": True,
        "survey_note": "외벽 단열재 유무·두께, 열교 부위 확인 필요",
        "days": 21, "vacate_days": 0,     # 비주거: 바깥 비계 작업(외단열)
    },
    {
        "id": "boiler",
        "name": "고효율 보일러 교체",
        "target": "gas",
        "addresses": "난방 설비 효율",
        "rate_low": 0.10, "rate_high": 0.15,
        "basis": "assumed",              # 출처 확인 전 — 시나리오 가정값
        "source": SRC_COMPARE,
        "needs_survey": True,
        "survey_note": "현재 보일러 연식·효율등급 확인 필요",
        "days": 1, "vacate_days": 0,
    },
    {
        "id": "led",
        "name": "LED 조명 교체",
        "target": "elec",
        "addresses": "조명 전력",
        "rate_low": 0.05, "rate_high": 0.10,   # 전체 전력 대비
        "basis": "assumed",              # 출처 확인 전 — 시나리오 가정값
        "source": SRC_COMPARE,
        "needs_survey": True,
        "survey_note": "현재 조명 종류·대수, 조명이 전력에서 차지하는 비중 확인 필요",
        "days": 1, "vacate_days": 0,
    },
]

# 단독주택: 외피 단열은 실내 단열을 포함한다고 보고 집을 비운다 · 태양광을 더한다
# 태양광은 비율이 아니라 연간 발전량(kWh)으로 전기 사용량을 줄인다 (fixed_kwh)
SOLAR_3KW = {
    "id": "solar",
    "name": "태양광 설치 (3kW)",
    "target": "elec",
    "addresses": "전기 사용량(자가 발전)",
    "fixed_kwh": [3456, 3456],          # 288kWh/월 × 12
    "basis": "reference",
    "source": "서울시 주택 태양광 산식 3kW × 3.2시간 × 30일 = 월 288kWh (내 손안에 서울, 2020.4.14)",
    "needs_survey": True,
    "survey_note": "지붕 방향·그늘·구조 하중 확인 필요",
    "days": 3, "vacate_days": 0,
    "days_note": "설치 1~3일 (참고·업체: 한화큐셀 FAQ)",
    "start_note": ("한전 상계 신청 후 약 13일(사용전점검일 제외) · 가동은 신청 7일 이후부터 · "
                   "보조금을 받으면 사업 승인 후 90일 안에 설치 (한전 요금상계 업무처리절차 · 기후에너지환경부 공고 제2026-236호)"),
    "cost_won": [4_540_000, 4_940_000], "subsidy_won": 1_650_000,
    "cost_source": ("2026 신재생에너지 융복합지원사업 설비가격 주택 3kW 1,497천원/kW(부가세 별도, 계산 약 494만 원) · "
                    "예산군 2026 사례 454만 원 · 국비 보조 550천원/kW = 165만 원(한국에너지공단 주택지원)"),
}

# 단독주택(132㎡, 2층) 공사비 · 공식 ㎡당 단가가 없는 공사는 업체·연구 단가 × 면적 가정(외벽 174㎡ 중 창 45㎡ · 벽 129㎡)으로 계산
HOUSE_COST = {
    "window": {"cost_won": [15_900_000, 25_700_000], "days": 2,
               "days_note": "1~2일 (참고·업체: LX Z:IN · KCC 대리점). 35평이 넘으면 하루에 못 끝날 수 있음",
               "cost_source": "참고(업체) 도구스 2026 ㎡당 28.5만(로이 이중창)~46만 원(시스템창호) × 철거·부가세 1.232 × 창 45.4㎡(계산)"},
    "envelope": {"cost_won": [4_500_000, 23_500_000],
                 "cost_source": ("내단열 약 3.5만 원/㎡ × 벽 129㎡ = 약 450만 원(마감 제외, 황석호 2022 KIAEBS · 물가정보 단가) ~ "
                                 "참고(업체) 외단열 12.1만~18.2만 원/㎡ × 129㎡ = 약 2,350만 원")},
    "boiler": {"cost_won": [930_000, 2_500_000], "subsidy_won": 0,
               "days_note": "2~3시간 (참고·업체), 위치를 옮기면 5시간 이상 · 가스 안전점검 후 1일 이내 공급(한국도시가스협회)",
               "cost_source": "LH 토지주택연구원 2022 콘덴싱보일러 933천원/대 ~ 참고(민간) 32평 이상 단독 1등급 220만~250만 원 · 일반가구 보조금 없음(2024~)"},
    "led": {"cost_won": [1_000_000, 2_000_000],
            "days_note": "등 하나당 15~30분 (참고·업체)",
            "cost_source": "LH 토지주택연구원 2022 LED 1,025천원 ~ 참고(민간) 40평·28개 108만~197만 원"},
}
MEASURES_HOUSE = [
    {**m, **HOUSE_COST.get(m["id"], {}),
     **({"days": 28, "vacate_days": 28, "days_note": "가정값 — 외단열·내단열 공사 기간은 공식·업체 자료를 찾지 못함",
         "survey_note": m["survey_note"] + " · 단독주택은 실내 단열을 함께 해 집을 비우는 기간이 생김"}
        if m["id"] == "envelope" else {})}
    for m in MEASURES
] + [SOLAR_3KW]


# ══════════════════════════════════════════════════════
#  건축물 진단 — 공공데이터로 확인되는 것만
# ══════════════════════════════════════════════════════

# '단계 변화'의 정의:
#   변화 이후의 가장 낮은 해가, 변화 이전의 가장 높은 해보다도 이 배수 이상 높을 것.
#   평균끼리 비교하면 한 해만 튀어도 걸린다. 두 구간이 겹치지 않아야 단계 변화다.
STEP_CHANGE_RATIO = 1.25
STEP_MIN_YEARS = 2           # 그 수준이 몇 년 이상 유지되어야 하는지


def diagnose(df, area, use_apr_day=None):
    """
    df   : ym, elec, gas, total (월별, total 결측 제외)
    area : 연면적 m²

    반환: 확인된 사실(measured)과 현장 확인이 필요한 항목(unverified)을 분리한 진단
    """
    d = df.copy()
    d["y"] = d["ym"].str[:4]
    d["m"] = d["ym"].str[4:6].astype(int)

    # ── 연도별 ────────────────────────────────────
    #    결측이 1~2개월이면 그 해를 버리지 않고 연 단위로 환산한다.
    #    (원자료에 2021.10, 2022.08이 비어 있음)
    #    버리면 비교할 해가 줄어 단계 변화를 못 찾는다.
    years = []
    for y, g in d.groupby("y"):
        n = len(g)
        if n < 10:
            continue
        k = 12 / n
        years.append({
            "year": y,
            "months": n,
            "annualized": n < 12,
            "elec": round(float(g["elec"].sum()) * k),
            "gas": round(float(g["gas"].sum()) * k),
            "total": round(float(g["total"].sum()) * k),
            "intensity": round(float(g["total"].sum()) * k / area, 1),   # kWh/m²·년
        })

    findings = []

    # ── ① 연료 단계 변화 찾기 ──────────────────────
    #    일시적 이상과 영구적 수준 변화는 다르다.
    #    후자는 기저선 모델을 통째로 무효화한다.
    for fuel, label in [("gas", "가스"), ("elec", "전기")]:
        # 가장 먼저 걸리는 분할이 아니라 '가장 뚜렷한' 분할을 고른다
        best = None
        for i in range(1, len(years)):
            before, after = years[:i], years[i:]
            if len(after) < STEP_MIN_YEARS:
                continue
            hi_before = max(x[fuel] for x in before)    # 이전의 최고
            lo_after = min(x[fuel] for x in after)      # 이후의 최저
            if hi_before <= 0:
                continue
            gap = lo_after / hi_before                  # 두 구간이 겹치지 않는 정도
            if gap >= STEP_CHANGE_RATIO and (best is None or gap > best[0]):
                b = sum(x[fuel] for x in before) / len(before)
                a = sum(x[fuel] for x in after) / len(after)
                best = (gap, i, before, after, b, a)

        if best:
            gap, i, before, after, b, a = best
            findings.append({
                    "kind": "step_change",
                    "basis": "measured",
                    "title": f"{years[i]['year']}년부터 {label} 사용량이 단계적으로 증가",
                    "detail": (
                        f"{before[0]['year']}~{before[-1]['year']}년 평균 {b:,.0f} kWh → "
                        f"{after[0]['year']}~{after[-1]['year']}년 평균 {a:,.0f} kWh "
                        f"({a/b:.2f}배). 변화 이후 가장 낮은 해가 이전 가장 높은 해보다도 "
                        f"{gap:.2f}배 높아 두 구간이 겹치지 않습니다. "
                        f"{len(after)}년간 그 수준이 유지됩니다."
                    ),
                    "implication": (
                        "일시적 이상이 아니라 건물 운영 조건이 바뀐 것으로 보입니다. "
                        "변화 이전 데이터로 학습한 기저선은 이후 기간을 대표하지 못합니다."
                    ),
                "action": "현장 확인 — 설비 교체, 용도 변경, 임차인 변경, 영업시간 변동 여부",
            })

    # ── ② 에너지 원단위 ───────────────────────────
    if years:
        last = years[-1]
        findings.append({
            "kind": "intensity",
            "basis": "measured",
            "title": f"단위면적당 에너지 사용량 {last['intensity']} kWh/m²·년",
            "detail": (f"{last['year']}년 기준. 연면적 {area:,.0f} m², "
                       f"연간 {last['total']:,} kWh."),
            "implication": "",
            "action": "동일 용도·규모 건물의 원단위와 비교 필요 (벤치마크 확인)",
        })

    # ── ③ 연료 구성과 계절 패턴 ────────────────────
    if years:
        last_y = years[-1]["year"]
        g = d[d["y"] == last_y]
        e_share = g["elec"].sum() / g["total"].sum()
        win = g[g["m"].isin([12, 1, 2])]["total"].mean()
        sum_ = g[g["m"].isin([6, 7, 8])]["total"].mean()
        gas_win = g[g["m"].isin([12, 1, 2])]["gas"].mean()
        gas_sum = g[g["m"].isin([6, 7, 8])]["gas"].mean()

        findings.append({
            "kind": "profile",
            "basis": "measured",
            "title": f"전기 {e_share:.0%} · 가스 {1-e_share:.0%}, 겨울 부하가 여름의 {win/sum_:.1f}배",
            "detail": (
                f"{last_y}년 겨울(12·1·2월) 월평균 {win:,.0f} kWh, "
                f"여름(6·7·8월) {sum_:,.0f} kWh. "
                f"가스는 겨울 {gas_win:,.0f} kWh에서 여름 {gas_sum:,.0f} kWh로 "
                f"{gas_win/gas_sum:.1f}배 차이가 납니다."
            ),
            "implication": (
                "가스 사용이 겨울에 집중되어 난방 용도임이 분명합니다. "
                "난방 부하를 줄이는 대책(외피·창호·난방 설비)의 영향 범위가 "
                "전체 에너지의 상당 부분에 해당합니다."
            ),
            "action": "",
        })

    # ── ④ 확인하지 못한 것 ─────────────────────────
    unverified = [
        {"item": "외벽·지붕 단열 성능", "why": "공공 에너지데이터로는 알 수 없음", "how": "현장 실사 또는 설계도서 확인"},
        {"item": "창호 유형·기밀 상태", "why": "공공 에너지데이터로는 알 수 없음", "how": "현장 실사"},
        {"item": "난방 설비 연식·효율", "why": "공공 에너지데이터로는 알 수 없음", "how": "설비 명판 확인"},
        {"item": "조명 종류·대수", "why": "전력 사용량에서 조명 비중을 분리할 수 없음", "how": "현장 실사 또는 분전반 계측"},
        {"item": "재실 인원·영업시간", "why": "사용량 변화의 원인을 특정할 수 없음", "how": "임차인 확인"},
    ]

    return {
        "area": area,
        "use_apr_day": use_apr_day,
        "years": years,
        "findings": findings,
        "unverified": unverified,
        "note": ("공공 에너지데이터와 건축물대장으로 확인되는 범위까지만 제시합니다. "
                 "건축물의 물리적 상태는 현장 확인이 필요하며, 사용량만으로 단정하지 않습니다."),
    }


# ══════════════════════════════════════════════════════
#  개선 대책 → 에너지 절감량 → 온실가스 감축량
# ══════════════════════════════════════════════════════

def _saving(m, fuel_kwh):
    """대책 하나의 절감량(kWh) 범위 · 비율형과 발전량형(fixed_kwh)"""
    if "fixed_kwh" in m:
        return min(m["fixed_kwh"][0], fuel_kwh), min(m["fixed_kwh"][1], fuel_kwh)
    return fuel_kwh * m["rate_low"], fuel_kwh * m["rate_high"]


def apply_measures(years, selected=None, catalog=None, prices=None):
    """
    years    : diagnose()가 돌려준 연도별 사용량
    selected : 적용할 대책 id 목록 (None이면 전부)
    catalog  : 대책 목록 (None 이면 MEASURES · 단독주택은 MEASURES_HOUSE)
    prices   : 연료별 단가 (None 이면 pricing.PRICES) — 절감량을 원으로 바꿀 때

    반환: 대책별 절감량·절감 금액·온실가스 감축량(범위) + 공사 일정·집을 비우는 기간.
    """
    if not years:
        return {"available": False, "reason": "연 단위 사용량이 확보되지 않았습니다"}
    import pricing
    catalog = catalog or MEASURES
    prices = prices or pricing.PRICES
    price = {f: prices[f]["won_per_kwh"] for f in ("elec", "gas")}

    base = years[-1]            # 가장 최근 완전한 해
    picks = [m for m in catalog if selected is None or m["id"] in selected]

    rows = []
    for m in picks:
        fuel_kwh = base[m["target"]]
        lo, hi = _saving(m, fuel_kwh)
        ef = EMISSION_FACTORS[m["target"]]

        rows.append({
            "id": m["id"],
            "name": m["name"],
            "addresses": m["addresses"],
            "fuel": ef["name"],
            "fuel_kwh": fuel_kwh,
            "rate_range": ([round(lo / fuel_kwh, 3), round(hi / fuel_kwh, 3)] if "fixed_kwh" in m and fuel_kwh
                           else [m.get("rate_low"), m.get("rate_high")]),
            "saving_kwh_low": round(lo),
            "saving_kwh_high": round(hi),
            "saving_won_low": round(lo * price[m["target"]]),
            "saving_won_high": round(hi * price[m["target"]]),
            "days": m.get("days"),
            "vacate_days": m.get("vacate_days", 0),
            "cost_won": m.get("cost_won"),            # [low, high] 이 건물 기준 공사비 · 없으면 None
            "subsidy_won": m.get("subsidy_won"),      # 보조금(원) · 없으면 None
            "cost_source": m.get("cost_source"),
            "days_note": m.get("days_note"),
            "start_note": m.get("start_note"),
            "co2_kg_low": round(lo * ef["value"]),
            "co2_kg_high": round(hi * ef["value"]),
            "basis": m["basis"],
            "basis_label": {"measured": "실측", "reference": "문헌 확인값",
                            "assumed": "가정값"}[m["basis"]],
            "source": m["source"] or None,
            "source_missing": not m["source"],
            "needs_survey": m["needs_survey"],
            "survey_note": m["survey_note"],
        })

    # 대책을 겹쳐 적용할 때 단순 합산은 과대 추정이 된다.
    # 같은 연료를 건드리는 대책은 곱으로 누적한다. (1-a)(1-b)
    totals = {}
    for fuel in ("elec", "gas"):
        ms = [m for m in picks if m["target"] == fuel]
        if not ms:
            continue
        keep_lo = keep_hi = 1.0
        for m in ms:
            if "fixed_kwh" in m:
                continue
            keep_lo *= (1 - m["rate_low"])
            keep_hi *= (1 - m["rate_high"])
        kwh = base[fuel]
        # 발전량형(태양광)은 비율 대책을 적용하고 남은 사용량에서 뺀다 (0 밑으로는 안 내려감)
        fix_lo = sum(m["fixed_kwh"][0] for m in ms if "fixed_kwh" in m)
        fix_hi = sum(m["fixed_kwh"][1] for m in ms if "fixed_kwh" in m)
        cut_lo = min(kwh, kwh * (1 - keep_lo) + fix_lo)
        cut_hi = min(kwh, kwh * (1 - keep_hi) + fix_hi)
        ef = EMISSION_FACTORS[fuel]
        totals[fuel] = {
            "fuel": ef["name"],
            "base_kwh": kwh,
            "saving_kwh_low": round(cut_lo),
            "saving_kwh_high": round(cut_hi),
            "saving_won_low": round(cut_lo * price[fuel]),
            "saving_won_high": round(cut_hi * price[fuel]),
            "co2_kg_low": round(cut_lo * ef["value"]),
            "co2_kg_high": round(cut_hi * ef["value"]),
        }

    all_kwh_lo = sum(t["saving_kwh_low"] for t in totals.values())
    all_kwh_hi = sum(t["saving_kwh_high"] for t in totals.values())
    all_co2_lo = sum(t["co2_kg_low"] for t in totals.values())
    all_co2_hi = sum(t["co2_kg_high"] for t in totals.values())

    # 대책별 절감량을 그냥 더한 값. 화면에서 보정 전후를 나란히 보여주기 위함.
    # 이걸 안 보여주면 "합계가 안 맞는다"는 오해를 받는다.
    naive_lo = sum(r["saving_kwh_low"] for r in rows)
    naive_hi = sum(r["saving_kwh_high"] for r in rows)

    unverified_ef = [v["name"] for v in EMISSION_FACTORS.values() if not v["verified"]]
    missing_src = [r["name"] for r in rows if r["source_missing"]]

    # 공사 일정 · 여러 공사를 한꺼번에 진행한다고 보고 겹친다(가장 긴 공사 = 전체 일정). 집 비우는 기간도 겹친다.
    schedule = {
        "works": [{"id": r["id"], "name": r["name"], "days": r["days"], "vacate_days": r["vacate_days"]} for r in rows],
        "total_days": max([r["days"] or 0 for r in rows], default=0),
        "vacate_days": max([r["vacate_days"] or 0 for r in rows], default=0),
        "is_assumption": True,
        "note": "공사를 한꺼번에 진행해 가장 긴 공사 기간을 전체 일정으로 잡았어요. 기간은 가정값이에요.",
    }
    won_lo = sum(t["saving_won_low"] for t in totals.values())
    won_hi = sum(t["saving_won_high"] for t in totals.values())
    costed = [r for r in rows if r["cost_won"]]
    cost = ({"low": sum(r["cost_won"][0] for r in costed), "high": sum(r["cost_won"][1] for r in costed),
             "subsidy": sum(r["subsidy_won"] or 0 for r in costed),
             "missing": [r["name"] for r in rows if not r["cost_won"]]} if costed else None)

    return {
        "available": True,
        "base_year": base["year"],
        "base_elec_kwh": base["elec"],
        "base_gas_kwh": base["gas"],
        "total_saving_won": [won_lo, won_hi],
        "total_cost": cost,
        "prices": prices,
        "schedule": schedule,
        "base_total_kwh": base["total"],
        "measures": rows,
        "by_fuel": totals,
        "total_saving_kwh": [all_kwh_lo, all_kwh_hi],
        "naive_sum_kwh": [naive_lo, naive_hi],
        "overlap_adjust_kwh": [naive_lo - all_kwh_lo, naive_hi - all_kwh_hi],
        "total_saving_rate": [round(all_kwh_lo / base["total"], 3),
                              round(all_kwh_hi / base["total"], 3)],
        "total_co2_kg": [all_co2_lo, all_co2_hi],
        "emission_factors": EMISSION_FACTORS,
        "method": ("각 대책의 절감률을 해당 연료 사용량에 적용하고, "
                   "같은 연료에 겹치는 대책은 (1-a)(1-b)로 누적했습니다. "
                   "태양광은 발전량만큼 남은 전기 사용량에서 뺍니다. "
                   "단순 합산하면 과대 추정이 됩니다. 금액은 절감량 × 연료별 단가입니다."),
        "limits": [
            "절감률은 출처 확인 전의 시나리오 가정값이며 이 건물에서 실측한 값이 아닙니다.",
            "현장 진단 전이므로 각 대책의 적용 가능 여부가 확정되지 않았습니다.",
            "공사 후 실제 절감량은 날씨·영업시간·재실 인원 변화의 영향을 받습니다.",
            "온실가스 감축량은 적용한 배출계수에 따라 달라집니다.",
        ],
        "warnings": (
            ([f"배출계수 미확인: {', '.join(unverified_ef)}"] if unverified_ef else []) +
            ([f"절감률 출처 미기재: {', '.join(missing_src)}"] if missing_src else [])
        ),
    }
