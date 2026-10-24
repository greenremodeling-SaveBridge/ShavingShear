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
    },
]


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

def apply_measures(years, selected=None):
    """
    years    : diagnose()가 돌려준 연도별 사용량
    selected : 적용할 대책 id 목록 (None이면 전부)

    반환: 대책별 절감량과 온실가스 감축량. 전부 범위로 돌려준다.
    """
    if not years:
        return {"available": False, "reason": "연 단위 사용량이 확보되지 않았습니다"}

    base = years[-1]            # 가장 최근 완전한 해
    picks = [m for m in MEASURES if selected is None or m["id"] in selected]

    rows = []
    for m in picks:
        fuel_kwh = base[m["target"]]
        lo = fuel_kwh * m["rate_low"]
        hi = fuel_kwh * m["rate_high"]
        ef = EMISSION_FACTORS[m["target"]]

        rows.append({
            "id": m["id"],
            "name": m["name"],
            "addresses": m["addresses"],
            "fuel": ef["name"],
            "fuel_kwh": fuel_kwh,
            "rate_range": [m["rate_low"], m["rate_high"]],
            "saving_kwh_low": round(lo),
            "saving_kwh_high": round(hi),
            "co2_kg_low": round(lo * ef["value"]),
            "co2_kg_high": round(hi * ef["value"]),
            "basis": m["basis"],
            "basis_label": {"measured": "실측", "reference": "문헌 확인값",
                            "assumed": "시나리오 가정값"}[m["basis"]],
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
            keep_lo *= (1 - m["rate_low"])
            keep_hi *= (1 - m["rate_high"])
        kwh = base[fuel]
        ef = EMISSION_FACTORS[fuel]
        totals[fuel] = {
            "fuel": ef["name"],
            "base_kwh": kwh,
            "saving_kwh_low": round(kwh * (1 - keep_lo)),
            "saving_kwh_high": round(kwh * (1 - keep_hi)),
            "co2_kg_low": round(kwh * (1 - keep_lo) * ef["value"]),
            "co2_kg_high": round(kwh * (1 - keep_hi) * ef["value"]),
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

    return {
        "available": True,
        "base_year": base["year"],
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
                   "단순 합산하면 과대 추정이 됩니다."),
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
