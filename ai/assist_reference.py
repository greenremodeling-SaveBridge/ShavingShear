"""
세이빙 AI 대화 입구 — POST /api/assist  (+ /api/mediate · /api/resolve · /api/analyze)
참고 구현 · 프론트 작업본용 (2026-10-21). 형식은 요구서 3장 그대로.

  의도 판단 : saving_ai/ (자체 C++ 경량 모델 + 규칙). 외부 AI 를 부르지 않는다.
  숫자     : 여기서 계산한다 (요구서 3-1 · 3-3 공식, main.baseline_of · post_allocation 과 같은 값)
  문장     : 템플릿. 짧게 · 공감 먼저 · 다음에 할 일.

  사용자가 말하지 않은 값은 묻기 전에 먼저 채운다.
    ① 이번 말 → ② 직전 대화(context.last) → ③ 지금 화면 값(context) → ④ 이 건물 데이터(가장 크게 튄 달 등)
  채웠으면 무엇을 채웠는지 첫 문장으로 말하고, 바꾸기 쉬운 칩을 준다.
  채울 곳이 정말 없을 때만, 한 번에 하나만 되묻는다(고르기만 하면 되는 칩과 함께).

  main.py 에 두 줄:  from assist import router as assist_router  /  app.include_router(assist_router)
"""
import math
import re
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import main as M

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "saving_ai"))
from saving_ai import SavingAI  # noqa: E402
import rules as R  # noqa: E402

AI = SavingAI()
router = APIRouter()

TAG = {"mediate": "🤝 합의 도우미", "resolve": "🏢 건물 찾기", "analyze": "🔎 변동 분석", "trust": "🛡 신뢰 확인", "clarify": ""}
SIM_NOTE = "공사 전 시뮬레이션이에요. 실제로 아낀 금액이 아니에요"


# ───────────────────────── 말 다듬기 ─────────────────────────
def won(v):
    return f"{int(v):,}"


def man(v):
    """50000000 → '5,000만 원' · 120000000 → '1억 2,000만 원' (읽기용 표기, 반올림 없음)"""
    v = int(v)
    eok, rest = divmod(v, 100_000_000)
    m, r = divmod(rest, 10_000)
    s = []
    if eok:
        s.append(f"{eok:,}억")
    if m:
        s.append(f"{m:,}만")
    if r or not s:
        s.append(f"{r:,}")
    return " ".join(s) + " 원"


def man_about(v):
    """문장용 · 만 원 단위로 반올림해 '약'을 붙인다 (숫자 칸은 원 단위 그대로)"""
    return "약 " + man(round(int(v) / 10_000) * 10_000)


def pct(r):
    v = r * 100
    return f"{v:.0f}%" if abs(v - round(v)) < 1e-9 else f"{v:.1f}%"


_BATCHIM_DIGIT = set("013678")


def josa(word, a, b):
    """받침 보고 은/는 · 이/가 · 으로/로 (숫자로 끝나면 읽는 소리로)"""
    w = str(word).rstrip()
    c = w[-1:] if w else ""
    if c.isdigit():
        return w + (a if c in _BATCHIM_DIGIT else b)
    if "가" <= c <= "힣":
        jong = (ord(c) - 0xAC00) % 28
        if a.startswith("으로"):
            return w + (a if jong and jong != 8 else b)
        return w + (a if jong else b)
    return w + a


def ymk(ym):
    return f"{int(ym[:4])}년 {int(ym[4:])}월"


def resp(intent, reply, data=None, chips=None, facts=None, notices=None, actions=None, state=None, source="template", **extra):
    out = {
        "intent": intent, "tag": TAG.get(intent, ""), "reply": reply, "data": data,
        "facts": facts if facts is not None else (data or {}).get("facts", []) if isinstance(data, dict) else [],
        "notices": notices if notices is not None else (data or {}).get("notices", []) if isinstance(data, dict) else [],
        "actions": actions if actions is not None else (data or {}).get("actions", []) if isinstance(data, dict) else [],
        "chips": chips or [], "source": source,
    }
    if state is not None:
        out["state"] = state
    out.update(extra)
    return out


# ───────────────────────── 건물 ─────────────────────────
ALIAS = {1: ["서울", "강남", "근린생활시설", "근린", "761-26", "761", "시연", "○○동", "샘플"],
         2: ["양평", "블룸비스타", "블룸", "호텔"]}


def buildings():
    return M.query("SELECT bld_id, addr, purpose, area, sigungu, bjdong, bun, ji FROM building ORDER BY bld_id")


def cand(b):
    return {
        "bld_id": b["bld_id"], "addr": b["addr"], "purpose": b["purpose"], "area": b["area"],
        "codes": {"sigungu": b["sigungu"], "bjdong": b["bjdong"], "bun": b["bun"], "ji": b["ji"]},
        "data_origin": {k: v for k, v in M.data_origin(b["bld_id"]).items() if k in ("is_simulated", "label")},
    }


def bld_by_id(i):
    return next((b for b in buildings() if b["bld_id"] == i), None)


def short_name(b):
    return "양평 블룸비스타 호텔" if b["bld_id"] == 2 else f"{b['addr']} {b['purpose'].replace('제1종', '')}"


def bld_chips():
    """등록된 건물을 바로 고를 수 있는 칩 — 사용자에게 다시 쓰게 하지 않는다"""
    return [{"label": short_name(b), "message": "양평 블룸비스타 호텔" if b["bld_id"] == 2 else "강남구 ○○동 761-26"} for b in buildings()]


ROAD = re.compile(r"([가-힣\d]+(?:로|길))\s*(\d+(?:번길)?)\s*(\d+(?:-\d+)?)?")
LOT = re.compile(r"([가-힣]+(?:동|리|읍|면))\s*(\d+(?:-\d+)?)\s*(번지)?")
ZIP = re.compile(r"(?<![\d-])(\d{5})(?![\d-])")
RESIDENTIAL = re.compile(r"아파트|빌라|다세대|오피스텔|단독주택|주택")


def resolve_q(q):
    """요구서 3-2 · matched / unregistered / residential / not_found"""
    t = str(q or "")
    hits = [b for b in buildings() if any(w in t for w in ALIAS.get(b["bld_id"], []))]
    if hits:
        b = hits[0]
        sim = M.data_origin(b["bld_id"])["is_simulated"]
        msg = "찾았어요. " + ("다만 이 건물은 시연을 위해 만든 가상 데이터예요. " if sim else "") + "이 건물이 맞나요?"
        return {"result": "matched", "candidates": [cand(b)], "message": msg, "facts": [], "notices": [], "actions": []}
    if RESIDENTIAL.search(t):
        return {"result": "residential", "candidates": [], "facts": [], "notices": [], "actions": [],
                "message": "아파트·주택은 공공 에너지데이터 제공 대상이 아니라서 찾을 수 없어요. 상가나 사무실 건물이라면 주소를 알려 주세요."}
    m = ROAD.search(t) or LOT.search(t)
    if m:
        where = m.group(0).strip()
        return {"result": "unregistered", "candidates": [], "facts": [], "notices": [], "actions": [],
                "message": f"{josa(where, '은', '는')} 아직 에너지 데이터가 없는 건물이에요. 공공데이터가 공개된 건물만 볼 수 있거든요."}
    return {"result": "not_found", "candidates": [], "facts": [], "notices": [], "actions": [],
            "message": "어떤 건물인지 잘 모르겠어요. 도로명 주소나 건물 이름으로 알려 주세요."}


# ───────────────────────── 🤝 합의 (요구서 3-1) ─────────────────────────
def ceil5(r):
    return math.ceil(r * 20 - 1e-9) / 20


def mediate_calc(bld_id, invest, years, owner_ratio=None):
    base = M.baseline_of(bld_id)
    A, L = base["annual_saving_won"], base["ci_low_won"]

    def two(saving, ratio):
        oa = saving * ratio
        return ({"owner_annual_won": int(oa), "tenant_monthly_won": int(saving * (1 - ratio) / 12),
                 "payback_years": round(invest / oa, 1), "recovery_rate": round(oa * years / invest, 3)},
                oa * years / invest >= 1)

    def card(key, label, r):
        b, ob = two(A, r)
        lo, ol = two(L, r)
        return {"key": key, "label": label, "owner_ratio": r, "base": b, "low": lo,
                "meets_target_base": ob, "meets_target_low": ol}

    head = {"invest_won": invest, "target_years": years, "annual_saving_won": A, "annual_saving_low_won": L,
            "facts": [{"label": "연간 절감액", "value": A, "unit": "원", "kind": "simulated", "goto": "alloc"},
                      {"label": "90% 범위 하한", "value": L, "unit": "원", "kind": "simulated", "goto": "base"}],
            "notices": [SIM_NOTE], "status": "ESTIMATED"}

    if owner_ratio is not None:                                   # 말한 비율을 평가
        c = card("user", f"말씀하신 {pct(owner_ratio)}", owner_ratio)
        return {**head, "feasible": True, "options": [c], "actions": [{"type": "set_alloc", "ratio": owner_ratio, "invest": invest, "years": years}]}

    br = invest / (A * years)
    if br > 0.95:                                                 # 몫을 다 줘도 기간 안에 안 됨
        longer = math.ceil(invest / A)
        alts = []
        if longer <= 30:
            alts.append({"type": "longer", "years": longer, "text": f"건물주가 절감액을 전부 가져가도 {longer}년이 걸려요"})
        mx = int(A * 0.95 * years)
        alts.append({"type": "smaller", "max_invest_won": mx,
                     "text": f"{years}년 안에 받으려면 공사비를 {man_about(mx)} 이하로 줄여야 해요(건물주 몫 95% 기준)"})
        return {**head, "feasible": False, "options": [], "alternatives": alts, "actions": []}
    br = max(0.05, ceil5(br))
    sr = min(0.95, max(br, ceil5(invest / (L * years))))
    opts = [card("base", "기본 추정", br)]
    if sr > br:
        opts.append(card("safe", "안전하게", sr))
    return {**head, "feasible": True, "options": opts, "actions": [{"type": "set_alloc", "ratio": br, "invest": invest, "years": years}]}


def mediate_text(d, safe_first=False, say_invest=True):
    """건물주 · 세입자 두 벌 (숫자는 d 그대로)"""
    inv, yrs = d["invest_won"], d["target_years"]
    if not d["feasible"]:
        return (f"아쉽지만 공사비 {man(inv)}은 {yrs}년 안에 돌려받기 어려워요. 이렇게 바꿔 보면 어떨까요?",
                "이 조건은 건물주가 기간 안에 돌려받을 수 없어서 나눌 몫을 정하기 어려워요. 기간이나 공사비를 바꿔 볼까요?")
    o = d["options"]
    b = o[0]
    s = o[1] if len(o) > 1 else None
    if b["key"] == "user":
        if b["meets_target_base"]:
            own = f"건물주 몫 {pct(b['owner_ratio'])}면 공사비 {man(inv)}을 {b['base']['payback_years']}년 만에 돌려받아요."
            own += " 절감액이 예상보다 적어도 기간 안에 돼요." if b["meets_target_low"] else f" 다만 절감액이 예상보다 적으면 {b['low']['payback_years']}년이 걸려요."
        else:
            own = f"건물주 몫 {pct(b['owner_ratio'])}로는 {yrs}년 안에 다 돌려받기 어려워요({b['base']['payback_years']}년 걸려요)."
        ten = f"건물주 몫이 {pct(b['owner_ratio'])}면 세입자는 매달 {won(b['base']['tenant_monthly_won'])}원을 아껴요."
        return own, ten
    if safe_first and s:
        own = (f"안전하게 가려면 건물주 몫을 {pct(s['owner_ratio'])}로 하면 돼요. 절감액이 예상보다 적어도 "
               f"{s['low']['payback_years']}년 만에 돌려받아요.")
    else:
        own = (f"건물주 몫을 {pct(b['owner_ratio'])}로 하면 " + (f"공사비 {man(inv)}을 " if say_invest else "")
               + f"{b['base']['payback_years']}년 만에 돌려받아요.")
        if not b["meets_target_low"] and s:
            own += f" 다만 절감액이 예상보다 적으면 {b['low']['payback_years']}년이 걸려서, 그때도 {yrs}년 안에 받으려면 {pct(s['owner_ratio'])}가 필요해요."
        elif b["meets_target_low"]:
            own += " 절감액이 예상보다 적어도 기간 안에 돌려받아요."
    ten = f"건물주 몫이 {pct(b['owner_ratio'])}면 세입자는 매달 {won(b['base']['tenant_monthly_won'])}원을"
    if s:
        ten += f", {pct(s['owner_ratio'])}면 매달 {won(s['base']['tenant_monthly_won'])}원을"
    ten += " 아껴요."
    if s:
        ten += f" 절감액이 예상보다 적으면 각각 {won(b['low']['tenant_monthly_won'])}원, {won(s['low']['tenant_monthly_won'])}원이에요."
    else:
        ten += f" 절감액이 예상보다 적으면 {won(b['low']['tenant_monthly_won'])}원이에요."
    return own, ten


# ───────────────────────── 🔎 변동 분석 (요구서 3-3) ─────────────────────────
SEASON = {"봄": [3, 4, 5], "여름": [6, 7, 8], "가을": [9, 10, 11], "겨울": [12, 1, 2]}


def fuel_of(bld_id):
    return {r["ym"]: (r["elec"], r["gas"]) for r in M.query("SELECT ym, elec, gas FROM usage_monthly WHERE bld_id=?", (bld_id,))}


def analyze_calc(bld_id, ym):
    base = M.baseline_of(bld_id)
    mb = {r["ym"]: r for r in base["monthly_baseline"]}
    last, first = max(mb), min(mb)
    if ym not in mb:
        if ym > last:
            return {"available": False, "last_data_ym": last, "facts": [], "notices": [], "actions": [],
                    "reply": f"그 달 사용량은 아직 공개되지 않았어요. 공공데이터는 약 4개월 늦게 나와서, 지금은 {ymk(last)}까지 볼 수 있어요."}
        return {"available": False, "last_data_ym": last, "facts": [], "notices": [], "actions": [],
                "reply": f"{ymk(ym)} 사용량은 원자료에 없어요. {ymk(first)}부터 {ymk(last)}까지 볼 수 있어요."}
    y, m = int(ym[:4]), int(ym[4:])
    ref, note = f"{y - 1}{m:02d}", None
    if ref not in mb:
        ref = f"{y - 2}{m:02d}"
        note = f"{y - 1}년 {m}월은 원자료가 없어 {y - 2}년 {m}월과 비교했어요"
        if ref not in mb:
            return {"available": False, "last_data_ym": last, "facts": [], "notices": [], "actions": [],
                    "reply": f"{ymk(ym)}과 비교할 지난해 자료가 없어서 변화를 나눠 볼 수 없어요."}
    cur, prv = mb[ym], mb[ref]
    change = int(round(cur["actual"] - prv["actual"]))
    weather = int(round(cur["baseline"] - prv["baseline"]))
    other = change - weather
    fu = fuel_of(bld_id)
    e0, g0 = fu.get(ref, (None, None))
    e1, g1 = fu.get(ym, (None, None))
    anomaly = {a["ym"] for a in base["anomalies"]}
    findings = []
    summer_gas = m in (6, 7, 8, 9) and g0 and g1 and g1 > g0 * 1.5
    if summer_gas:
        findings.append("OUT_OF_SEASON_GAS")
    if abs(other) > abs(weather):
        findings.append("NON_WEATHER")
    if ym in anomaly:
        findings.append("ANOMALY")
    if summer_gas:
        survey = ["급탕·주방 가스 설비 사용 변화", "영업시간 변화", "가스 설비 교체·추가"]
    elif change >= 0:
        survey = ["냉난방 설비 사용 변화", "영업시간 변화", "새로 들인 설비"]
    else:
        survey = ["휴업·공실 여부", "영업시간 단축", "설비 교체"]
    more = change >= 0
    rk = f"{int(ref[:4])}년 {m}월"
    reply = f"{ymk(ym)}은 {rk}보다 {abs(change):,} kWh를 {'더' if more else '덜'} 썼어요. "
    if weather and other and (weather > 0) != (other > 0):
        reply += (f"날씨만 보면 {abs(weather):,} kWh {'늘' if weather > 0 else '줄'}었어야 하는데, "
                  f"다른 이유로 {abs(other):,} kWh가 {'늘' if other > 0 else '줄'}었어요.")
    elif abs(weather) >= abs(other):
        reply += f"대부분 날씨 영향이에요({abs(weather):,} kWh)."
    else:
        reply += f"그중 날씨 때문인 건 {abs(weather):,} kWh뿐이고, {abs(other):,} kWh는 다른 이유예요."
    if summer_gas:
        reply += f" 난방이 없는 여름에 가스가 {int(g0):,} → {int(g1):,} kWh로 늘었으니, 영업시간이나 가스 설비가 바뀌었는지 현장에서 확인해 보면 좋아요."
    elif abs(other) > abs(weather):
        reply += " 현장에서 무엇이 바뀌었는지 확인해 보면 좋아요."
    return {
        "available": True, "ym": ym, "ref_ym": ref, "ref_note": note,
        "actual_kwh": int(cur["actual"]), "ref_actual_kwh": int(prv["actual"]),
        "change_kwh": change, "weather_kwh": weather, "other_kwh": other,
        "by_fuel": {"elec": [int(e0), int(e1)], "gas": [int(g0), int(g1)]} if e0 is not None and e1 is not None else {},
        "findings": findings, "reply": reply, "survey": survey,
        "facts": [{"label": f"{ym[:4]}.{ym[4:]} 실측", "value": int(cur["actual"]), "unit": "kWh", "kind": "measured", "goto": "base"},
                  {"label": "기온 영향", "value": weather, "unit": "kWh", "kind": "model", "goto": "base"},
                  {"label": "기온 외 요인", "value": other, "unit": "kWh", "kind": "model", "goto": "base"}],
        "notices": ["원인은 사용량만으로 확정할 수 없어요"], "actions": [],
    }


def pick_month(bld_id, u, ctx_last):
    """분석할 달 고르기 → (ym, 채운 이유 문장 or None, 다른 후보 칩)"""
    base = M.baseline_of(bld_id)
    have = sorted(r["ym"] for r in base["monthly_baseline"])
    last = have[-1]
    s = u["slots"]
    if s.get("ym"):
        return s["ym"], None, []
    if s.get("month_only"):
        mo = s["month_only"]
        ys = [ym for ym in have if int(ym[4:]) == mo]
        if ys:
            ym = ys[-1]
            others = [f"{int(x[:4])}년 {mo}월 사용량 분석해줘" for x in ys[-4:-1]][::-1]
            return ym, f"가장 최근 {ymk(ym)}", others
    if s.get("season"):
        yy, name = s["season"]
        ms = [f"{yy + (1 if (name == '겨울' and mm in (1, 2)) else 0)}{mm:02d}" for mm in SEASON[name]]
        ms = [x for x in ms if x in have]
        if ms:
            mb = {r["ym"]: r for r in base["monthly_baseline"]}
            ym = max(ms, key=lambda x: abs(mb[x]["actual"] - mb[x]["baseline"]))
            return ym, f"{yy}년 {name} 중 가장 많이 변한 {int(ym[4:])}월", [f"{ymk(x)} 사용량 분석해줘" for x in ms if x != ym]
    if ctx_last and ctx_last.get("intent") == "analyze" and ctx_last.get("ym"):
        return ctx_last["ym"], None, []
    an = sorted(base["anomalies"], key=lambda a: -a["ratio"])
    if an:
        ym = an[0]["ym"]
        others = []
        for a in an[1:]:
            k = f"{ymk(a['ym'])} 사용량 분석해줘"
            if a["ym"] != ym and k not in others:
                others.append(k)
        return ym, f"가장 크게 튄 {ymk(ym)}", others[:3]
    return last, f"가장 최근 {ymk(last)}", []


# ───────────────────────── 🛡 신뢰 ─────────────────────────
def trust_calc(bld_id, quarter, ratio):
    base = M.baseline_of(bld_id)
    mc = base["metric_checks"]
    y, q = None, None
    if quarter and re.fullmatch(r"\d{4}-[1-4]", str(quarter)):
        y, q = map(int, str(quarter).split("-"))
    else:
        cs = M.get_demo()["cases"]
        if cs:
            y, q = cs[0]["year"], cs[0]["quarter"]
    code = None
    if y:
        try:
            code = M.get_settlement(bld_id, y, q, min(0.95, max(0.05, ratio or 0.7)))["status_code"]
        except HTTPException:
            code = None
    fail = not (mc["cv_rmse"]["ok"] and mc["r2"]["ok"])
    if code in (None, "ESTIMATED"):
        reply = "솔직히 말씀드리면 아직은 시뮬레이션이에요. 공사 전이라 실제로 아낀 양이 없어요."
    elif code == "PROVISIONAL":
        reply = "이 분기 금액은 잠정이에요. 근거가 조금 부족한 달이 있어서 연 단위로 다시 확인해요."
    elif code == "REVIEW_REQUIRED":
        reply = "이 분기는 아직 믿기 어려워요. 기온으로 설명되지 않는 변화가 있어서 금액을 확정하지 않았어요."
    elif code == "INSUFFICIENT_DATA":
        reply = "이 분기는 사용량이 아직 공개되지 않아서 판단할 수 없어요."
    else:
        reply = "공사 후 실측 사용량으로 검증한 금액이라 믿으셔도 돼요."
    reply += (" 예측 정확도도 기준보다 조금 낮아서 금액을 확정하지 않고 범위로 보여드리고 있어요." if fail
              else " 예측 모델은 기준을 통과했어요.")
    data = {"status_code": code, "metric_checks": mc, "is_simulated": M.data_origin(bld_id)["is_simulated"]}
    facts = [{"label": "예측 오차", "value": mc["cv_rmse"]["value"], "unit": "%", "kind": "model", "goto": "base"},
             {"label": "설명력", "value": mc["r2"]["value"], "unit": "", "kind": "model", "goto": "base"}]
    return data, reply, facts


# ───────────────────────── 대화 입구 ─────────────────────────
class AssistReq(BaseModel):
    message: str
    context: dict = {}


YES = re.compile(r"^(네|응|ㅇㅇ|맞아|맞아요|그래|좋아|ㅇㅋ|오케이|예)\b")
DONT_KNOW = re.compile(r"모르|몰라|기억\s*안|생각\s*안")
GREET = re.compile(r"^(안녕|하이|hi|hello|ㅎㅇ|반가)", re.I)
THANKS = re.compile(r"고마|감사|땡큐|ㄱㅅ")
SAFE = re.compile(r"안전|보수|최악|낮게\s*나|적게\s*나|덜\s*위험")
CH = {
    "deal": {"label": "공사비 5천만, 8년", "message": "공사비 5천만, 8년 안에 회수하고 싶어요"},
    "gas": "가스가 왜 튀었어?",
    "trust": "이 금액 믿어도 돼요?",
    "tenant": "세입자 입장은?",
    "owner": "건물주 입장은?",
    "safe": "안전하게 하면?",
    "years": {"label": "기간 바꿔 볼래요", "fill": "기간 "},
    "money": {"label": "공사비 바꿔 볼래요", "fill": "공사비 "},
    "byName": {"label": "건물 이름으로 찾을게요", "fill": "건물 이름: "},
}


@router.post("/api/assist")
def post_assist(req: AssistReq):
    ctx = req.context or {}
    last = ctx.get("last") or {}
    u = AI.understand(req.message)
    t = u["masked_text"].strip()
    s = u["slots"]
    intent = u["intent"]
    src = "local_llm" if u["by"] == "nano" else "template"

    # 직전에 하나를 물었다면 그 답으로 이어 받는다
    if last.get("need") == "confirm_money" and (YES.search(t) or s.get("invest_won")):
        s = {**s, "invest_won": s.get("invest_won") if s.get("invest_won") and s["invest_won"] >= 1_000_000 else last.get("cand_won")}
        intent = "MEDIATE"
    # 날짜만 말하면 사용량 이야기로 본다 ('8월', '작년 여름')
    if intent in ("OUT", "ASK") and (s.get("ym") or s.get("month_only") or s.get("season")):
        intent = "ANALYZE"
    # 숫자만 던지면 합의 이어가기 ('10년이면?', '1억')
    if intent in ("OUT", "ASK") and (s.get("invest_won") or s.get("target_years") or s.get("owner_ratio")):
        intent = "MEDIATE"

    # 건물: 이번 말에 없으면 화면에 열린 건물 → 없으면 시연 건물(그렇다고 말한다)
    bld_id = ctx.get("bld_id")
    assumed_bld = None
    if not bld_id and intent in ("MEDIATE", "ANALYZE", "TRUST"):
        bld_id, assumed_bld = 1, bld_by_id(1)
    said = bool(last.get("assumed_said"))
    pre = ""                                     # 채운 것은 문장이 아니라 filled 한 줄로 알린다
    fill_bld = ["시연 건물"] if assumed_bld else []
    extra = {"building": cand(assumed_bld)} if assumed_bld else {}

    # ── 인사 · 고마움 ──
    if intent in ("OUT", "ASK") and GREET.search(t):
        return resp("clarify", "안녕하세요, 세이빙 AI예요. 공사비를 몇 년 안에 돌려받을 수 있는지, 사용량이 왜 바뀌었는지 같은 걸 편하게 물어보세요.",
                    chips=[CH["deal"], CH["gas"], CH["trust"]], source=src)
    if intent in ("OUT", "ASK") and THANKS.search(t):
        return resp("clarify", "도움이 됐다니 다행이에요. 더 궁금한 게 생기면 언제든 물어보세요.", chips=[CH["trust"], CH["gas"]], source=src)

    # ── 🏢 건물 찾기 ──
    if intent == "RESOLVE":
        if DONT_KNOW.search(t):
            if ctx.get("bld_id"):
                b = bld_by_id(ctx["bld_id"])
                d = {"result": "matched", "candidates": [cand(b)], "message": "", "facts": [], "notices": [], "actions": []}
                return resp("resolve", f"지금 보고 있는 건물은 {b['addr']}예요. 이 건물 이야기인가요?", d, chips=[CH["byName"]], source=src)
            d = {"result": "matched", "candidates": [cand(b) for b in buildings()], "message": "", "facts": [], "notices": [], "actions": []}
            return resp("resolve", "괜찮아요. 지금 볼 수 있는 건물은 이 두 곳이에요. 이 중에 있나요? 없으면 건물 이름이나 동네를 알려 주세요.",
                        d, chips=[CH["byName"]], source=src)
        z = ZIP.search(t)
        if z and not s:
            return resp("resolve", f"{josa(z.group(1), '은', '는')} 우편번호 같아요. 우편번호로는 찾을 수 없어서, 지금 볼 수 있는 건물을 보여드릴게요. 이 중에 있나요?",
                        {"result": "matched", "candidates": [cand(b) for b in buildings()], "message": "", "facts": [], "notices": [], "actions": []},
                        chips=[CH["byName"]], source=src)
        d = resolve_q(t)
        chips = [CH["gas"], CH["deal"]] if d["result"] == "matched" else bld_chips() + [{"label": "다른 주소로 찾을게요", "fill": ""}]
        if d["result"] in ("unregistered", "not_found", "residential"):
            d = {**d, "message": d["message"] + " 지금 볼 수 있는 건물은 아래에 있어요."}
        return resp("resolve", d["message"], d, chips=chips, source=src)

    # ── 관점 ──
    if intent in ("VIEW_OWNER", "VIEW_TENANT"):
        v = "tenant" if intent == "VIEW_TENANT" else "owner"
        return resp("mediate", f"이제 {'세입자' if v == 'tenant' else '건물주'} 입장으로 설명할게요. 숫자는 그대로예요.",
                    actions=[{"type": "set_viewer", "viewer": v}], chips=[CH["owner" if v == "tenant" else "tenant"], CH["safe"]], source=src)

    # ── 🤝 합의 ──
    if intent == "MEDIATE":
        if any(k == "money_unit" for k, _ in u["ambiguous"]) and last.get("need") != "confirm_money":
            v = dict(u["ambiguous"])["money_unit"]
            return resp("clarify", f"{v // 1000}천만 원 말씀이신가요?", source=src,
                        chips=[{"label": f"네, {v // 1000}천만 원이에요", "message": f"네 {v // 1000}천만 원"}, {"label": "아니에요", "fill": "공사비 "}],
                        state={"intent": "mediate", "need": "confirm_money", "cand_won": v * 10_000,
                               "target_years": last.get("target_years") if last.get("intent") == "mediate" else None})
        filled = []
        inv = s.get("invest_won") or (last.get("invest_won") if last.get("intent") == "mediate" else None)
        if not inv:
            inv = ctx.get("invest_won")
            if inv:
                filled.append(f"공사비 {man(inv)}")
        yrs = s.get("target_years") or (last.get("target_years") if last.get("intent") == "mediate" else None)
        if not yrs:
            yrs = ctx.get("target_years")
            if yrs:
                filled.append(f"{yrs}년")
        if not inv:
            return resp("clarify", "공사비가 얼마예요?", source=src, chips=[CH["deal"], {"label": "1억", "message": "공사비 1억"}, {"label": "직접 쓸게요", "fill": "공사비 "}],
                        state={"intent": "mediate", "need": "invest", "target_years": yrs})
        if not yrs:
            return resp("clarify", "몇 년 안에 돌려받고 싶으세요?", source=src,
                        chips=[{"label": f"{n}년", "message": f"{n}년"} for n in (5, 8, 10, 15)],
                        state={"intent": "mediate", "need": "years", "invest_won": inv})
        if not 1 <= yrs <= 30:
            return resp("clarify", "기간은 1년에서 30년 사이로 정할 수 있어요. 몇 년으로 볼까요?", source=src,
                        chips=[{"label": f"{n}년", "message": f"{n}년"} for n in (5, 10, 15, 20)], state={"intent": "mediate", "invest_won": inv})
        r = s.get("owner_ratio")
        if r is not None and not 0.05 <= r <= 0.95:
            return resp("clarify", "건물주 몫은 5%에서 95% 사이로 정할 수 있어요.", source=src, chips=[CH["deal"]])
        d = mediate_calc(bld_id, inv, yrs, r)
        own, ten = mediate_text(d, safe_first=bool(SAFE.search(t)) and r is None, say_invest=not filled)
        if SAFE.search(t) and len(d.get("options", [])) > 1:
            d["pick"] = "safe"
        d["reply_owner"], d["reply_tenant"] = own, ten
        fl = fill_bld + filled
        if fl and not (said and not filled):
            extra = {**extra, "filled": f"{' · '.join(fl)}으로 계산했어요"}
        chips = [CH["tenant"], CH["years"], CH["money"]] if d["feasible"] else \
            [{"label": f"기간 {a['years']}년으로", "message": f"{a['years']}년"} for a in d["alternatives"] if a["type"] == "longer"] + [CH["money"]]
        return resp("mediate", d["reply_owner"], d, chips=chips, source=src,
                    state={"intent": "mediate", "invest_won": inv, "target_years": yrs, "assumed_said": bool(assumed_bld) or said}, **extra)

    # ── 🔎 변동 분석 ──
    if intent == "ANALYZE":
        ym, why, others = pick_month(bld_id, u, last)
        d = analyze_calc(bld_id, ym)
        reply = d["reply"]
        fl = fill_bld + ([why] if why else [])
        if fl and not (said and not why):
            extra = {**extra, "filled": josa(" · ".join(fl), "으로", "로") + " 봤어요"}
        chips = (others or [])[:2] + [CH["trust"]]
        return resp("analyze", reply, d, chips=chips, source=src, state={"intent": "analyze", "ym": ym, "assumed_said": bool(assumed_bld) or said}, **extra)

    # ── 🛡 신뢰 ──
    if intent == "TRUST":
        d, reply, facts = trust_calc(bld_id, ctx.get("quarter"), ctx.get("owner_ratio"))
        if fill_bld and not said:
            extra = {**extra, "filled": "시연 건물 기준으로 봤어요"}
        return resp("trust", reply, d, facts=facts, notices=["공사 전 금액은 시뮬레이션이에요"],
                    chips=[CH["deal"], CH["gas"]], source=src, state={"intent": "trust", "assumed_said": bool(assumed_bld) or said}, **extra)

    # ── 범위 밖 · 못 알아들음 ── 두 번째부터는 말을 바꾼다
    miss = int(last.get("miss", 0)) + 1 if last.get("intent") == "clarify" else 1
    if miss >= 2:
        return resp("clarify", "제가 잘 못 알아듣고 있네요. 이렇게 물어보시면 바로 답할 수 있어요.", source=src,
                    chips=[CH["deal"], CH["gas"], bld_chips()[0]], state={"intent": "clarify", "miss": 0})
    return resp("clarify", "그건 제가 잘 모르는 내용이에요. 공사비 회수 계산, 건물 찾기, 사용량이 바뀐 이유, 금액을 믿어도 되는지는 바로 알려드릴 수 있어요.",
                source=src, chips=[CH["deal"], CH["gas"], CH["trust"]], state={"intent": "clarify", "miss": miss})


# ───────────────────────── 요구서 3-1 · 3-2 · 3-3 ─────────────────────────
class MediateReq(BaseModel):
    bld_id: int = 1
    invest_won: int
    target_years: int
    owner_ratio: float | None = None
    viewer: str = "owner"


@router.post("/api/mediate")
def post_mediate(req: MediateReq):
    if req.invest_won <= 0 or not 1 <= req.target_years <= 30:
        raise HTTPException(400, "공사비는 0보다 크고 기간은 1~30년이어야 합니다")
    if req.owner_ratio is not None and not 0.05 <= req.owner_ratio <= 0.95:
        raise HTTPException(400, "건물주 몫은 5~95% 사이여야 합니다")
    d = mediate_calc(req.bld_id, req.invest_won, req.target_years, req.owner_ratio)
    d["reply_owner"], d["reply_tenant"] = mediate_text(d)
    return d


class ResolveReq(BaseModel):
    q: str


@router.post("/api/resolve")
def post_resolve(req: ResolveReq):
    return resolve_q(R.mask_pii(req.q)[0])          # 주소는 로그에 남기지 않는다


class AnalyzeReq(BaseModel):
    bld_id: int = 1
    ym: str


@router.post("/api/analyze")
def post_analyze(req: AnalyzeReq):
    if not re.fullmatch(r"\d{6}", req.ym):
        raise HTTPException(400, "ym 은 YYYYMM 형식이어야 합니다")
    return analyze_calc(req.bld_id, req.ym)
