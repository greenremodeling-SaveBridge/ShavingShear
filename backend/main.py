"""
세이브브릿지 — 백엔드 서버  (담당: 서현)

실행:  uvicorn main:app --reload
확인:  http://localhost:8000/docs

■ 제안서 9p 화면 흐름과 API 대응
    ① 주소 입력      → GET  /api/building
    ② 대상 판정      → GET  /api/eligibility
    ③ 분배 시뮬레이터 → GET  /api/usage, /api/baseline, POST /api/allocation
    ④ 특약 초안      → (화면 설계로만 제시 · 14p)
    ⑤ 정산 리포트    → GET  /api/settlement, /api/explain
"""

import sqlite3
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from baseline import run_baseline
from explain import explain as make_explanation
from measures import diagnose, apply_measures
import pricing

# 실행 위치와 상관없이 이 파일 옆의 DB·화면을 쓴다
BASE_DIR = Path(__file__).resolve().parent
DB = str(BASE_DIR / "savebridge.db")

app = FastAPI(title="세이브브릿지 API", version="2.0")

# 프론트가 다른 포트(예: 5173)에서 돌아가므로 허용해줘야 합니다.
# 이게 없으면 브라우저가 요청을 막습니다. (CORS 에러)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_cache = {}  # 기저선 결과 캐시 — 슬라이더가 자주 호출하므로 매번 재학습하지 않는다
_fuel = {}   # bld_id → {ym: (전기 kWh, 가스 kWh)} — 연료별 금액 계산용
_post = {}   # bld_id → {ym: 공사 후 실측 기반 월 절감액(원)} — (기저선 − 실측) × 단가, 연료별

# 실측 데이터가 아닌 건물. DB 에 data_source 컬럼이 없을 때 쓰는 기본값.
# 건물 2(양평 블룸비스타)는 건물 1 사용량을 그대로 복사한 것이다.
SIMULATED_BUILDINGS = {2: "simulated_copy_of_bld1"}


# ══════════════════════════════════════════════════════
#  정산 상태 — 지시서 2-B
#
#  핵심 규칙 하나만 기억하면 됩니다.
#    VERIFIED 는 '그린리모델링 공사 후 실측 데이터'가 있어야만 나옵니다.
#    모델 지표가 아무리 좋아도, 공사를 안 했으면 검증할 절감량이 없습니다.
#    → retrofit_ym 이 NULL 인 동안 VERIFIED 는 절대 나오지 않습니다.
# ══════════════════════════════════════════════════════

STATUS = {
    "INSUFFICIENT_DATA": {
        "label": "정산 불가",
        "amount": False,
        "desc": "필요한 사용량 데이터가 없어 금액을 산출하지 않습니다",
    },
    "REVIEW_REQUIRED": {
        "label": "검토 필요",
        "amount": False,
        "desc": "사용량에 설명되지 않는 변화가 있어 금액을 산출하지 않습니다",
    },
    "ESTIMATED": {
        "label": "추정",
        "amount": True,
        "desc": "공사 전이므로 가정 기반 시뮬레이션 값입니다. 실제 절감 실적이 아닙니다",
    },
    "PROVISIONAL": {
        "label": "잠정",
        "amount": True,
        "desc": "공사 후 실측으로 절감량을 검증하기 전까지의 잠정 값입니다",
    },
    "VERIFIED": {
        "label": "검증 완료",
        "amount": True,
        "desc": "공사 후 실측 사용량으로 절감량을 검증했습니다",
    },
}


# 정산 금액을 '기저선 − 공사 후 실측'으로 계산하는 로직이 구현됐는가.
# 2026-10-22 구현: 공사 완료월(retrofit_ym)이 있는 건물의 공사 후 분기는 연료별 (기저선 − 실측) × 단가.
# get_settlement 가 분기마다 actual_based 를 넘긴다. 이 기본값은 공사 전 건물용(False).
ACTUAL_BASED_SETTLEMENT = False


def settlement_status(
    retrofit_ym,
    months_settled,
    months_flagged,
    months_nodata,
    model_verdict,
    period_start_ym=None,
    actual_based=ACTUAL_BASED_SETTLEMENT,
):
    """
    반환: (코드, 사유)

    판단 순서 (위에서 걸리면 거기서 끝):
      1. 정산 가능한 달이 0개
           데이터 없음만 있음        → INSUFFICIENT_DATA
           이상만 있음               → REVIEW_REQUIRED (전체 이상)
           이상 + 데이터 없음 섞임   → REVIEW_REQUIRED (사유에 둘 다 표기)
      2. 공사 전 (retrofit_ym 없음)  → ESTIMATED
      3. 정산 기간이 공사 완료월보다 앞섬 → ESTIMATED
           (공사 후 실측이 없는 기간을 '검증'할 수 없다)
      4. 실측 기반 정산 로직 미구현   → PROVISIONAL
      5. 모델 판정 CONFIRMED 아님    → PROVISIONAL
      6. 위를 모두 통과              → VERIFIED

    모델 지표를 먼저 보면 '모델이 좋으니 확정'이라는 잘못된 결론이 나옵니다.
    """
    if months_settled == 0:
        if months_nodata and not months_flagged:
            return "INSUFFICIENT_DATA", "해당 기간의 사용량이 아직 공개되지 않았습니다"
        if months_nodata and months_flagged:
            return "REVIEW_REQUIRED", (
                f"정산 가능한 달이 없습니다 — 이상 감지 {months_flagged}개월, "
                f"데이터 미공개 {months_nodata}개월"
            )
        return "REVIEW_REQUIRED", "해당 기간 전체에서 사용량 이상이 감지되었습니다"

    if not retrofit_ym:
        # 공사 전 — 검증할 절감량 자체가 없다. 전부 시뮬레이션이다.
        return "ESTIMATED", (
            "그린리모델링 공사 전이므로 실제 절감량이 존재하지 않습니다. "
            "표시된 금액은 가정한 절감률을 적용한 시뮬레이션입니다"
        )

    if period_start_ym and period_start_ym < retrofit_ym:
        return "ESTIMATED", (
            f"정산 기간이 공사 완료({retrofit_ym[:4]}.{retrofit_ym[4:]}) 이전을 포함하므로 "
            "공사 후 실측으로 검증할 수 없습니다. 표시된 금액은 시뮬레이션입니다"
        )

    if not actual_based:
        return "PROVISIONAL", (
            "공사 후 기간이지만 금액은 아직 가정 절감률로 계산한 값입니다. "
            "기저선과 실측 사용량의 차이로 다시 계산해야 검증 완료가 됩니다"
        )

    if model_verdict != "CONFIRMED":
        return "PROVISIONAL", "기저선 모델이 검증 기준에 미달해 보수적으로 처리했습니다"

    return "VERIFIED", "공사 후 실측 사용량과 기저선을 비교해 절감량을 검증했습니다"


def query(sql, params=()):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def baseline_of(bld_id: int):
    """기저선 추정 결과를 가져온다 (한 번 계산하면 캐시에서 재사용)"""
    if bld_id in _cache:
        return _cache[bld_id]

    conn = sqlite3.connect(DB)
    df = pd.read_sql(
        """
        SELECT u.ym, u.elec, u.gas, u.total, w.hdd, w.cdd, w.days
        FROM usage_monthly u
        JOIN weather_monthly w ON u.ym = w.ym
        WHERE u.bld_id = ? AND u.total IS NOT NULL
        ORDER BY u.ym
    """,
        conn,
        params=(bld_id,),
    )
    conn.close()

    if df.empty:
        raise HTTPException(404, "데이터가 없습니다")

    b = query("SELECT retrofit_ym FROM building WHERE bld_id=?", (bld_id,))
    retrofit_ym = b[0]["retrofit_ym"] if b else None

    try:
        result = run_baseline(df, retrofit_ym)
    except ValueError as e:
        raise HTTPException(400, str(e))

    result["bld_id"] = bld_id

    # ── 금액은 백엔드(pricing.py)가 연료별로 다시 계산한다 ──────────
    # baseline.py 의 annual_saving_won 은 전기+가스 합계에 150원/kWh 를 곱한 값이라
    # 가스에도 전기 단가가 붙는다. 같은 키 이름으로 덮어써 프론트 호환을 유지한다.
    fuel = {r.ym: (float(r.elec), float(r.gas)) for r in df.itertuples()}
    last12 = df.tail(12)
    monthly_won = {ym: pricing.won(*fuel[ym])["total_won"] for ym in last12["ym"]}
    annual = sum(monthly_won.values())          # 월별 금액의 합 = 정산 화면 12개월 합과 동일
    old = result["annual_saving_won"] or 1
    result["ci_low_won"] = int(annual * result["ci_low_won"] / old)    # 오차 비율은 그대로 유지
    result["ci_high_won"] = int(annual * result["ci_high_won"] / old)
    result["annual_saving_won"] = annual
    result["saving_basis"] = {
        **pricing.basis(float(last12["elec"].sum()), float(last12["gas"].sum())),
        "period": f"{last12['ym'].iloc[0]} ~ {last12['ym'].iloc[-1]}",
    }

    # 두 지표의 충족 여부를 각각 남긴다 (판정 문자열만 보고 뭉뚱그리지 않게)
    m = result["metrics"]
    result["metric_checks"] = {
        "cv_rmse": {"value": m["cv_rmse"], "limit": "≤ 15.0", "ok": m["cv_rmse"] <= 15.0},
        "r2": {"value": m["r2"], "limit": "≥ 0.75", "ok": m["r2"] >= 0.75},
    }
    if m.get("nmbe") is not None:   # 평균 편향 — 판정(verdict)에는 쓰지 않고 근거로만 보여준다 (ASHRAE G14 월별 ±5%)
        result["metric_checks"]["nmbe"] = {"value": m["nmbe"], "limit": "±5", "ok": abs(m["nmbe"]) <= 5.0}
    result["data_origin"] = data_origin(bld_id)

    # ── 공사 후: 금액을 '기저선 − 실측'으로 다시 계산한다 (연료별 기저선 × 연료별 단가) ──
    post = {}
    if retrofit_ym and result.get("fuel_baseline"):
        pe, pg = pricing.PRICES["elec"]["won_per_kwh"], pricing.PRICES["gas"]["won_per_kwh"]
        for ym, (be, bg) in result["fuel_baseline"].items():
            if ym >= retrofit_ym and ym in fuel:
                e, g = fuel[ym]
                post[ym] = int((be - e) * pe + ((bg or 0) - (g or 0)) * pg)
        anomaly_ym = {a["ym"] for a in result["anomalies"]}
        ok = [ym for ym in sorted(post) if ym not in anomaly_ym][-12:]
        if len(ok) >= 6:
            annual = int(sum(post[ym] for ym in ok) * 12 / len(ok))
            old_ci = (result["ci_low_won"], result["ci_high_won"], result["annual_saving_won"] or 1)
            result["ci_low_won"] = int(annual * old_ci[0] / old_ci[2])
            result["ci_high_won"] = int(annual * old_ci[1] / old_ci[2])
            result["annual_saving_won"] = annual
            sim = result["saving_basis"]
            result["saving_basis"] = {
                **sim,
                "actual_based": True,
                "is_assumption": False,
                "saving_rate": None,
                "formula": (f"공사 후 {len(ok)}개월 (기저선 − 실측) × 연료별 단가 → 12개월 환산 "
                            f"(이상 감지 달 제외 · 전기 {pe}원 · 가스 {pg}원)"),
                "period": f"{ok[0]} ~ {ok[-1]}",
                "pre_simulation_won": sim.get("elec_saving_won", 0) + sim.get("gas_saving_won", 0),
                "note": (f"공사 완료({retrofit_ym[:4]}.{retrofit_ym[4:]}) 이후 실측 사용량과, 공사 전 데이터로 만든 기저선의 차이입니다. "
                         "기저선은 공사 전 36개월(학습 24 · 검증 12)만으로 만들었습니다."),
            }
    result["retrofit_ym"] = retrofit_ym

    _fuel[bld_id] = fuel
    _post[bld_id] = post
    _cache[bld_id] = result
    return result


def month_won(bld_id: int, ym: str):
    """정산·차트가 쓰는 월 금액.
    공사 후 달: (기저선 − 실측) × 단가 (실측 기반) · 공사 전 달: 분배 연간 금액과 같은 시뮬레이션(pricing.won)."""
    if ym in _post.get(bld_id, {}):
        return _post[bld_id][ym]
    e, g = _fuel[bld_id][ym]
    return pricing.won(e, g)["total_won"]


def data_origin(bld_id: int):
    """
    사용량이 실측인지 가상인지. 화면에 그대로 표시한다.
    building.data_source 컬럼이 있으면 그 값, 없으면(옛 DB) 아래 기본값.
    """
    try:
        r = query("SELECT data_source FROM building WHERE bld_id=?", (bld_id,))
        src = r[0]["data_source"] if r else None
    except sqlite3.OperationalError:          # 컬럼 없는 옛 DB
        src = None
    if src is None:
        src = SIMULATED_BUILDINGS.get(bld_id, "measured")
    simulated = src != "measured"
    if src == "simulated_retrofit_demo":
        note = ("가상 공사 시연 — 서울 샘플 사용량에 2025년 5월 가상 공사(전기 −15% · 가스 −30%)와 "
                "11월 운영 변화 1건을 얹었습니다. 실제 절감 실적이 아닙니다.")
    elif simulated:
        note = "이 건물의 사용량은 실제 측정값이 아닙니다. 건물 1(서울 샘플) 사용량을 복사한 시나리오 가정값입니다."
    else:
        note = "건물에너지 공공데이터(data.go.kr) 월별 실측 사용량입니다."
    return {
        "type": src,
        "is_simulated": simulated,
        "label": ("가상 데이터 · 가상 공사" if src == "simulated_retrofit_demo" else "가상 데이터") if simulated else "공공데이터 실측",
        "note": note,
    }


# ══════════════════════════════════════════════════════
#  ① 건물 조회
# ══════════════════════════════════════════════════════
@app.get("/api/building")
def get_building(sigungu: str, bjdong: str, bun: str, ji: str):
    """주소 코드로 건물 정보를 찾는다. (건축물대장 자동 조회)"""
    rows = query(
        """
        SELECT bld_id, addr, sido, area, struct, purpose, use_apr_day, year, floors
        FROM building
        WHERE sigungu=? AND bjdong=? AND bun=? AND ji=?
    """,
        (sigungu, bjdong, bun, ji),
    )

    matched = bool(rows)
    if not rows:
        # [시연 방어 로직] 입력한 코드가 DB에 정확히 일치하지 않아도 404 에러를 내지 않고
        # bld_id 가 가장 작은 건물(현재 1번 서울 샘플)을 돌려준다.
        # 다른 건물을 돌려준다는 사실은 matched=False 로 숨기지 않는다.
        rows = query("""
            SELECT bld_id, addr, sido, area, struct, purpose, use_apr_day, year, floors
            FROM building
            ORDER BY bld_id
            LIMIT 1
        """)
    if not rows:
        raise HTTPException(404, "등록된 건물 데이터가 없습니다")
    return {**rows[0], "matched": matched, "data_origin": data_origin(rows[0]["bld_id"])}


# ══════════════════════════════════════════════════════
#  ② 대상 판정   (제안서 9p)
# ══════════════════════════════════════════════════════
@app.get("/api/eligibility")
def get_eligibility(bld_id: int = 1):
    """
    건축물대장 값만으로 지원사업·서비스 대상 요건을 확인한다.
    요건 출처는 제안서 3p·9p 각주 참조.
    """
    rows = query(
        """
        SELECT addr, sido, purpose, use_apr_day, year, area
        FROM building WHERE bld_id=?
    """,
        (bld_id,),
    )
    if not rows:
        raise HTTPException(404, "건물이 없습니다")
    b = rows[0]

    from datetime import date

    this_year = date.today().year
    age = this_year - b["year"]
    is_nonresi = not any(
        k in b["purpose"] for k in ("주택", "아파트", "연립", "다세대")
    )
    is_seoul = "서울" in (b["sido"] or "")

    checks = [
        {
            "program": "이자지원",
            "name": "2016.1.1 이전 사용승인",
            "ok": b["use_apr_day"] < "20160101",
            "detail": f"사용승인 {b['use_apr_day'][:4]}.{b['use_apr_day'][4:6]}.{b['use_apr_day'][6:]}",
        },
        {
            "program": "BRP (서울시)",
            "name": "서울 소재 · 준공 15년 이상",
            "ok": is_seoul and age >= 15,
            "detail": f"{b['sido']} · 준공 {age}년 경과",
        },
        {
            "program": "세이빙 셰어",
            "name": "1차 대상 — 비주거 건축물",
            "ok": is_nonresi,
            "detail": b["purpose"],
        },
        {
            "program": "데이터",
            "name": "공공 에너지데이터 제공 대상",
            "ok": is_nonresi,
            "detail": "단독주택·200세대 미만 공동주택은 제공 제외 (2020.1 적용)",
        },
    ]

    programs = sorted(
        {
            c["program"]
            for c in checks
            if c["ok"] and c["program"] in ("이자지원", "BRP (서울시)")
        }
    )
    # 서비스 대상 여부는 서비스 요건(비주거 · 데이터 제공)으로만 정한다.
    # 지원사업(BRP 는 서울만)은 신청 가능 목록일 뿐 — 서울 밖 건물이 '대상 아님'이 되면 안 된다.
    eligible = all(c["ok"] for c in checks if c["program"] in ("세이빙 셰어", "데이터"))

    return {
        "bld_id": bld_id,
        "addr": b["addr"],
        "eligible": eligible,
        "programs": programs,
        "checks": checks,
        "msg": (
            ("서비스 1차 대상이며 " + " · ".join(programs) + " 신청 가능") if eligible and programs
            else "서비스 1차 대상 · 요건에 맞는 지원사업 없음" if eligible
            else "서비스 대상 요건 미충족 — 상세 확인 필요"
        ),
    }


# ══════════════════════════════════════════════════════
#  ③ 사용 이력
# ══════════════════════════════════════════════════════
@app.get("/api/usage")
def get_usage(bld_id: int = 1):
    """월별 전기·가스 사용량. total이 null인 달은 원자료 결측."""
    rows = query(
        """
        SELECT ym, elec, gas, total
        FROM usage_monthly WHERE bld_id=? ORDER BY ym
    """,
        (bld_id,),
    )

    if not rows:
        raise HTTPException(404, "사용 이력이 없습니다")
    return {
        "bld_id": bld_id,
        "data_origin": data_origin(bld_id),
        "count": len(rows),
        "missing": [r["ym"] for r in rows if r["total"] is None],
        "months": rows,
    }


# ══════════════════════════════════════════════════════
#  ④ 기저선 추정 + 판정   ← AI 핵심 (제안서 7·8p)
# ══════════════════════════════════════════════════════
@app.get("/api/baseline")
def get_baseline(bld_id: int = 1, refresh: bool = False):
    """
    metrics 와 함께 eval_window(평가 조건)를 돌려줍니다.
    발표에서 "그 숫자 어떤 조건에서 나온 겁니까" 질문에 쓰는 값입니다.

    refresh=1 : 캐시를 버리고 다시 계산.
      load_data.py 를 다시 돌린 뒤에는 이걸 한 번 호출하세요.
      (서버는 .db 변경을 자동으로 감지하지 않습니다)
    """
    if refresh:
        _cache.pop(bld_id, None)
    return baseline_of(bld_id)


# ══════════════════════════════════════════════════════
#  ⑤ 분배안 산출 + 합의 가능 판정   (제안서 9p ① · 11p)
# ══════════════════════════════════════════════════════
class AllocationRequest(BaseModel):
    bld_id: int = 1
    invest_won: int = Field(..., gt=0, description="개선 투자비 (소유주 입력)")
    owner_ratio: float = Field(..., gt=0, lt=1, description="건물주 분배율 0~1")
    period_years: int = Field(10, ge=1, le=30, description="분배 기간 (년)")


@app.post("/api/allocation")
def post_allocation(req: AllocationRequest):
    """
    슬라이더를 움직일 때마다 호출된다.

    합의 가능 판정 (제안서 9p ①):
      분배만으로 공사비가 회수되는지 본다.
      필요 건물주 몫이 100%를 넘으면 공사 범위나 분배 기간을 조정해야 한다.
      (11p K-water 사례 = 필요 몫 143% → 재설계)
    """
    base = baseline_of(req.bld_id)
    annual = base["annual_saving_won"]

    owner_annual = annual * req.owner_ratio
    owner_total = owner_annual * req.period_years  # 분배 기간 전체 회수액
    tenant_monthly = annual * (1 - req.owner_ratio) / 12

    recovery_rate = owner_total / req.invest_won
    required_ratio = req.invest_won / (annual * req.period_years)

    # 두 판정을 분리한다. 전에는 하나로 묶여 있어서
    # '50%만 회수되는데 합의 가능'이라는 모순된 문장이 나왔다.
    recovered = recovery_rate >= 1.0  # 지금 이 분배율로 회수되는가
    feasible = required_ratio <= 1.0  # 분배율을 올리면 회수 가능한가

    if recovered:
        msg = (
            f"현재 분배율 {req.owner_ratio * 100:.0f}%로 "
            f"{req.period_years}년간 투자비의 {recovery_rate * 100:.0f}% 회수 — 합의 가능"
        )
    elif feasible:
        msg = (
            f"현재 분배율로는 {recovery_rate * 100:.0f}%만 회수됩니다. "
            f"건물주 몫을 {required_ratio * 100:.0f}% 이상으로 올리면 "
            f"{req.period_years}년 내 회수 가능합니다"
        )
    else:
        msg = (
            f"필요 건물주 몫 {required_ratio * 100:.0f}% — 절감액 전액을 건물주가 가져가도 "
            f"{req.period_years}년 안에 회수되지 않습니다. "
            f"공사 범위 축소 또는 분배 기간 연장이 필요합니다"
        )

    # 분배 기간을 몇 년으로 늘리면 회수되는지 (회수 불가일 때 화면에 제시)
    min_years = None
    if not feasible:
        min_years = -(-req.invest_won // annual)  # 몫 100% 기준, 올림

    return {
        "bld_id": req.bld_id,
        "annual_saving_won": annual,
        "ci_low_won": base["ci_low_won"],
        "ci_high_won": base["ci_high_won"],
        "owner_ratio": req.owner_ratio,
        "period_years": req.period_years,
        "payback_years": round(req.invest_won / owner_annual, 1),
        "owner_annual_won": int(owner_annual),
        "owner_total_won": int(owner_total),
        # 합계가 연간 절감액과 어긋나지 않게 임차인 몫은 차액으로
        "tenant_annual_won": annual - int(owner_annual),
        "tenant_monthly_won": int(tenant_monthly),
        "recovery_rate": round(recovery_rate, 3),
        "required_owner_ratio": round(required_ratio, 3),
        "recovered": recovered,
        "feasible": feasible,
        "min_period_years": min_years,
        "feasibility_msg": msg,
        "verdict": base["verdict"],
        "saving_basis": base["saving_basis"],
    }


# ══════════════════════════════════════════════════════
#  ⑥ 정산 리포트 — 분기 단위   (제안서 9·10p)
# ══════════════════════════════════════════════════════
@app.get("/api/settlement")
def get_settlement(
    bld_id: int = 1, year: int = 2026, quarter: int = 3, owner_ratio: float = 0.7
):
    """
    분기 정산. 해당 분기에 이상이 감지된 달이 있으면 '보류'.
    제안서 10p의 '3분기 잠정 정산 · 7월 회색 막대'가 이 구조입니다.
    """
    if quarter not in (1, 2, 3, 4):
        raise HTTPException(400, "분기는 1~4 사이여야 합니다")
    if not 0 < owner_ratio < 1:
        raise HTTPException(400, "건물주 분배율은 0과 1 사이여야 합니다")

    b = query("SELECT retrofit_ym FROM building WHERE bld_id=?", (bld_id,))
    if not b:
        raise HTTPException(404, "건물이 없습니다")
    retrofit_ym = b[0]["retrofit_ym"]  # NULL 이면 공사 전

    base = baseline_of(bld_id)
    months = [f"{year}{m:02d}" for m in range(quarter * 3 - 2, quarter * 3 + 1)]

    anomaly_ym = {a["ym"] for a in base["anomalies"]}
    bl = {m["ym"]: m for m in base["monthly_baseline"]}

    rows = []
    for ym in months:
        m = bl.get(ym)

        # ① 그 달 데이터가 아직 없으면 금액을 만들지 않는다.
        #    공공 에너지데이터는 공개까지 약 4개월이 걸린다.
        if m is None:
            rows.append(
                {
                    "ym": ym,
                    "saving_won": None,
                    "state": "데이터 없음",
                    "note": "에너지 사용량이 아직 공개되지 않았습니다 (공개 지연 약 4개월)",
                }
            )
            continue

        # ② 이상이 감지된 달은 금액을 산출하지 않는다.
        #    0원이 아니라 '금액 없음'이다. 절감이 0이었다는 뜻이 아니라
        #    아직 판단할 수 없다는 뜻이므로 null 로 둔다.
        if ym in anomaly_ym:
            a = next(x for x in base["anomalies"] if x["ym"] == ym)
            rows.append(
                {
                    "ym": ym,
                    "saving_won": None,
                    "state": "확인 중",
                    "note": f"{a['fuel']} 사용량이 과거 같은 달 평균의 {a['ratio']}배",
                    "baseline_kwh": m["baseline"],
                    "actual_kwh": m["actual"],
                }
            )
            continue

        # ③ 정상 달 — 그 달 기저선에 비례해 배분한다.
        #    연간÷12로 나누면 계절성이 사라져 겨울·여름이 같은 금액이 된다.
        rows.append(
            {
                "ym": ym,
                "saving_won": month_won(bld_id, ym),   # 분배와 같은 pricing.won()
                "state": "정산",
                "note": "",
                "baseline_kwh": m["baseline"],
                "actual_kwh": m["actual"],
            }
        )

    n_data = sum(r["state"] != "데이터 없음" for r in rows)
    n_flagged = sum(r["state"] == "확인 중" for r in rows)
    n_settled = sum(r["state"] == "정산" for r in rows)
    saving = sum(r["saving_won"] for r in rows if r["saving_won"] is not None)

    # ── 분기 상태 판정 ───────────────────────────────────
    last_ym = base["monthly_baseline"][-1]["ym"]

    # 근거 추적 — 이 결과를 나중에 같은 조건으로 재현할 수 있게 한다
    prov = {
        "bld_id": bld_id,
        "period": f"{year} {quarter}분기",
        "data_last_month": last_ym,
        "method": ("공사 후: 연료별 (기저선 − 실측) kWh × 단가" if retrofit_ym and months[0] >= retrofit_ym else
                   "월 실측 사용량을 연료별로 나눠 (전기 kWh × 절감률 × 전기 단가 + "
                   "가스 kWh × 절감률 × 가스 단가). 분배 화면 연간 금액과 같은 식(pricing.won)"),
        "assumptions": base["saving_basis"]["formula"],
        "model_metrics": base["metrics"],
        "model_verdict": base["verdict"],
        "model_verdict_meaning": base["verdict_meaning"],
        "eval_window": base["eval_window"],
        "data_origin": base["data_origin"],
        "metric_checks": base["metric_checks"],
    }

    n_nodata = len(rows) - n_data
    post_period = bool(retrofit_ym) and months[0] >= retrofit_ym
    code, reason = settlement_status(
        retrofit_ym, n_settled, n_flagged, n_nodata, base["verdict"],
        period_start_ym=months[0],
        actual_based=post_period and bool(_post.get(bld_id)),
    )
    meta = STATUS[code]
    status, status_msg = meta["label"], reason
    prov["status_code"] = code
    prov["retrofit_ym"] = retrofit_ym

    if not meta["amount"]:
        # 금액을 산출하지 않는 상태. 0원이 아니라 '없음'이다.
        prov["hold_reason"] = (
            "데이터 미공개"
            if code == "INSUFFICIENT_DATA"
            else f"이상 감지 {n_flagged}개월 · 데이터 미공개 {n_nodata}개월"
            if n_nodata
            else f"이상 감지 {n_flagged}개월 (전체)"
        )
        if code == "INSUFFICIENT_DATA":
            status_msg += (
                f". 확보된 마지막 월은 {last_ym[:4]}년 {int(last_ym[4:])}월입니다"
            )
        return {
            "bld_id": bld_id,
            "period": f"{year} {quarter}분기",
            "data_available": n_data > 0,
            "months": rows,
            "chart": [],
            "saving_won": None,
            "owner_won": None,
            "tenant_won": None,
            "amount_state": "금액 없음",
            "amount_note": "금액을 산출하지 않았습니다. 절감액이 0원이라는 뜻이 아닙니다.",
            "owner_ratio": owner_ratio,
            "flagged_count": n_flagged,
            "months_with_data": n_data,
            "months_settled": 0,
            "status": status,
            "status_code": code,
            "status_desc": meta["desc"],
            "status_msg": status_msg,
            "verdict": base["verdict"],
            "verdict_meaning": base["verdict_meaning"],
            "saving_basis": base["saving_basis"],
            "provenance": prov,
            "next_period": None,
        }

    if n_flagged:
        status_msg += f" · 이상 감지 {n_flagged}개월은 금액 산출에서 제외"
        prov["hold_reason"] = f"이상 감지 {n_flagged}개월 (부분)"
    if n_nodata:
        status_msg += f" · {n_nodata}개월은 데이터 미공개"

    # 화면용 최근 6개월 막대 (제안서 10p 정산 리포트)
    last = f"{year}{quarter * 3:02d}"
    chart = [
        {
            "ym": m["ym"],
            "saving_won": (
                None if m["ym"] in anomaly_ym else month_won(bld_id, m["ym"])
            ),
            "flagged": m["ym"] in anomaly_ym,
        }
        for m in base["monthly_baseline"]
        if m["ym"] <= last
    ][-6:]

    nq = quarter + 1 if quarter < 4 else 1
    ny = year if quarter < 4 else year + 1

    sim = data_origin(bld_id)["is_simulated"]
    if post_period:
        amount_state = "공사 후 실측 기반 금액" + (" (가상 데이터)" if sim else "")
        amount_note = ("공사 후 실측 사용량과 기저선의 차이로 계산했습니다. "
                       + ("이 건물은 가상 공사 시연 데이터라 실제 절감 실적이 아닙니다. " if sim else "")
                       + ("기저선 모델이 확정 기준에 못 미쳐 잠정 금액이며, 연 단위로 다시 확인합니다." if code == "PROVISIONAL" else ""))
        if saving < 0:
            status_msg += " · 이 분기는 기저선보다 더 써서 나눌 절감액이 없습니다"
    else:
        amount_state = "시뮬레이션 금액"
        amount_note = ("가정한 절감률과 단가를 적용한 시뮬레이션 값입니다. "
                       "공사 후 실측으로 검증된 절감액이 아닙니다.")
    share = max(0, saving)

    return {
        "bld_id": bld_id,
        "period": f"{year} {quarter}분기",
        "data_available": True,
        "months": rows,
        "chart": chart,
        "saving_won": saving,
        # 분배 합계가 절감액과 어긋나지 않게: 임차인 몫은 차액으로 둔다 (절감액이 음수면 나눌 것이 없다)
        "owner_won": int(share * owner_ratio),
        "tenant_won": share - int(share * owner_ratio),
        "amount_state": amount_state,
        "amount_note": amount_note,
        "actual_based": post_period,
        "owner_ratio": owner_ratio,
        "flagged_count": n_flagged,
        "months_with_data": n_data,
        "months_settled": n_settled,
        "status": status,
        "status_code": code,
        "status_desc": meta["desc"],
        "status_msg": status_msg,
        "verdict": base["verdict"],
        "verdict_meaning": base["verdict_meaning"],
        "saving_basis": base["saving_basis"],
        "provenance": prov,
        "next_period": f"{ny} {nq}분기",
    }


# ══════════════════════════════════════════════════════
#  ⑦ 결과 설명   (제안서 12p · 14p 'LLM 설명 구현')
# ══════════════════════════════════════════════════════
@app.get("/api/explain")
def get_explain(bld_id: int = 1, ym: str = "202607"):
    """
    정산 결과를 비전문가가 알아들을 문장으로 설명한다.
    제안서 10p의 'AI : 7월은 사용량 급증, 확인 중'이 이 출력.

    문장 생성은 explain.py 가 한다. 순서는 캐시 → Gemini → 템플릿.
    숫자는 전부 여기(백엔드)에서 계산해 넘긴다. LLM 은 문장만 다듬는다.
    → 제안서 12p "AI는 절감액을 임의로 결정하지 않는다"
    """
    if not (len(ym) == 6 and ym.isdigit() and 1 <= int(ym[4:]) <= 12):
        raise HTTPException(400, "ym 은 YYYYMM 형식이어야 합니다 (예: 202607)")
    base = baseline_of(bld_id)

    b = query("SELECT retrofit_ym FROM building WHERE bld_id=?", (bld_id,))
    retrofit_ym = b[0]["retrofit_ym"] if b else None
    has_data = any(m["ym"] == ym for m in base["monthly_baseline"])
    # 그 달이 공사 후 실측으로 검증 가능한 달인지. 아니면 금액은 시뮬레이션이다.
    simulated = (not retrofit_ym) or ym < retrofit_ym or not ACTUAL_BASED_SETTLEMENT

    r = make_explanation(
        {
            "bld_id": bld_id,
            "ym": ym,
            "month": int(ym[4:6]),
            "verdict": base["verdict"],
            "metrics": base["metrics"],
            "anomaly": next((a for a in base["anomalies"] if a["ym"] == ym), None),
            "has_data": has_data,
            "simulated": simulated,
        }
    )

    return {
        "bld_id": bld_id,
        "ym": ym,
        "action": r["action"],
        "text": r["text"],
        "source": r["source"],  # gemini / cache / template:<이유>
    }


# ══════════════════════════════════════════════════════
#  ⑧ 건축물 진단   (심사표 '건축물 이해도' 20점)
# ══════════════════════════════════════════════════════
@app.get("/api/profile")
def get_profile(bld_id: int = 1):
    """
    공공데이터로 확인되는 것과 현장 확인이 필요한 것을 나눠 돌려준다.
    사용량만 보고 건물의 물리적 상태를 단정하지 않는다.
    """
    b = query(
        "SELECT addr, area, purpose, year, floors, struct, use_apr_day "
        "FROM building WHERE bld_id=?",
        (bld_id,),
    )
    if not b:
        raise HTTPException(404, "건물이 없습니다")
    b = b[0]

    conn = sqlite3.connect(DB)
    df = pd.read_sql(
        """SELECT ym, elec, gas, total FROM usage_monthly
                        WHERE bld_id=? AND total IS NOT NULL ORDER BY ym""",
        conn,
        params=(bld_id,),
    )
    conn.close()
    if df.empty:
        raise HTTPException(404, "사용 이력이 없습니다")

    d = diagnose(df, b["area"], b["use_apr_day"])
    d["building"] = b
    return d


# ══════════════════════════════════════════════════════
#  ⑨ 개선 대책 → 절감량 → 온실가스   (심사표 '에너지 저감 방향성' 25점)
# ══════════════════════════════════════════════════════
@app.get("/api/measures")
def get_measures(bld_id: int = 1, ids: str = ""):
    """
    ids: 적용할 대책 id를 쉼표로 (예: window,boiler). 비우면 전체.
    절감량과 온실가스 감축량을 '범위'로 돌려준다. 단일 확정값으로 주지 않는다.
    """
    prof = get_profile(bld_id)
    selected = [s.strip() for s in ids.split(",") if s.strip()] or None
    r = apply_measures(prof["years"], selected)
    r["bld_id"] = bld_id
    r["area"] = prof["area"]
    return r


@app.get("/api/demo")
def get_demo(bld_id: int = 1):
    """
    시연에 쓸 분기를 실제 데이터에서 골라 돌려준다.
    화면이 날짜를 하드코딩하지 않게 하기 위함 —
    데이터가 갱신되면 시연 기간도 같이 따라간다.
    """
    base = baseline_of(bld_id)
    anomaly_ym = {a["ym"] for a in base["anomalies"]}
    have = {m["ym"] for m in base["monthly_baseline"]}

    normal, partial, full_hold = [], [], []
    for ym in sorted(have):
        y, q = int(ym[:4]), (int(ym[4:6]) - 1) // 3 + 1
        key = (y, q)
        ms = [f"{y}{m:02d}" for m in range(q * 3 - 2, q * 3 + 1)]
        if not all(m in have for m in ms):
            continue
        n = sum(m in anomaly_ym for m in ms)
        bucket = full_hold if n == 3 else partial if n else normal
        if key not in bucket:
            bucket.append(key)

    retro = base.get("retrofit_ym")

    def pack(lst, label, note, kind):
        if not lst:
            return None
        y, q = lst[-1]
        return {
            "year": y,
            "quarter": q,
            "label": label,
            "period": f"{y} {q}분기",
            "note": note,
            "kind": kind,
            # 분기 시작월이 공사 완료월 이후면 '공사 후' 분기
            "post": bool(retro) and f"{y}{q * 3 - 2:02d}" >= retro,
        }

    return {
        "last_data_month": max(have),
        "cases": [
            c
            for c in [
                pack(
                    normal,
                    "정상 — 정산 가능",
                    "이상 없음. 근거가 충분할 때 금액을 계산하고 설명합니다",
                    "normal",
                ),
                pack(
                    partial,
                    "부분 제외 — 잠정 정산",
                    "이상이 감지된 달만 금액에서 빼고 분기는 정산합니다",
                    "partial",
                ),
                pack(
                    full_hold,
                    "전체 보류 — 확정 안 함",
                    "분기 전체에 이상. 근거가 부족하면 확정하지 않습니다",
                    "full",
                ),
            ]
            if c
        ],
    }


# ══════════════════════════════════════════════════════
#  화면 서빙 — web/index.html
#  http://localhost:8000/app/  로 열면 CORS 문제가 없습니다.
#
#  web 폴더는 '실행한 위치'가 아니라 이 main.py 가 있는 폴더 기준으로 찾는다.
#  zip 을 풀면서 한 단계 안쪽(예: saving-share-v4_1/web)에 들어가도 찾아낸다.
# ══════════════════════════════════════════════════════
import os
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles


def _find_web_dir():
    """
    화면 폴더 찾기. 우선 main.py 옆의 web/, 없으면 하위 폴더(최대 4단계)를 뒤진다.
    zip 을 '모두 압축 풀기' 하면 web\\web\\index.html 처럼 한 겹 더 생기는 경우가 많다.
    index.html 옆에 backup.json 이 있는 폴더만 화면 폴더로 인정한다
    (frontend/index.html 은 빌드 전 원본이라 열어도 빈 화면이다).
    """
    def ok(d):
        return (d / "index.html").is_file() and (d / "backup.json").is_file()

    if ok(BASE_DIR / "web"):
        return BASE_DIR / "web"
    skip = {"node_modules", "__pycache__", "frontend", "src", "tests"}
    found = []
    base_depth = len(BASE_DIR.parts)
    for root, dirs, files in os.walk(BASE_DIR):
        depth = len(Path(root).parts) - base_depth
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in skip and depth < 4]
        if "index.html" in files and "backup.json" in files:
            found.append(Path(root))
    found.sort(key=lambda p: (len(p.parts), str(p)))
    return found[0] if found else None


WEB_DIR = _find_web_dir()
if WEB_DIR:
    app.mount("/app", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
    print(f"[세이브브릿지] 화면 폴더: {WEB_DIR}  →  http://127.0.0.1:8000/app/")
else:
    print(f"[세이브브릿지] 화면 폴더를 찾지 못했습니다 (index.html + backup.json 이 함께 있는 폴더). "
          f"{BASE_DIR / 'web'} 안에 두 파일을 넣고 서버를 다시 켜세요. API 는 정상 동작합니다.")


@app.get("/")
def root():
    if WEB_DIR:
        return RedirectResponse("/app/")
    return {
        "service": "세이브브릿지 API",
        "docs": "/docs",
        "web": "화면 폴더를 찾지 못했습니다",
        "expected": str(BASE_DIR / "web" / "index.html"),
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    if WEB_DIR and (WEB_DIR / "icon.svg").is_file():
        return FileResponse(str(WEB_DIR / "icon.svg"), media_type="image/svg+xml")
    raise HTTPException(404)


# 세이빙 AI 대화 입구 (참고 구현 · assist.py)
from assist import router as assist_router  # noqa: E402
app.include_router(assist_router)
