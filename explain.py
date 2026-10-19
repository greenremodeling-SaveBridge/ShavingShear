"""
세이브브릿지 — 정산 설명 생성  (담당: 서현)

제안서 12p "AI는 절감액을 임의로 결정하지 않는다" 를 코드로 보장한다.

  1) 금액·배수·지표는 전부 백엔드가 계산한다.
  2) Gemini는 그 숫자를 문장으로 다듬기만 한다.
  3) Gemini 답에 입력에 없던 숫자가 섞이면 버리고 템플릿을 쓴다.  ← 숫자 검증
  4) 캐시에 있으면 호출하지 않는다.                                ← 현장 네트워크 대비
  5) 호출이 실패하거나 느리면 템플릿을 쓴다.

→ 어떤 경우에도 화면에 나가는 숫자는 백엔드가 계산한 값이다.

────────────────────────────────────────────────
준비 (한 번만)
    pip install google-genai

    키 발급:  https://aistudio.google.com/apikey
    키 등록:  PowerShell 에서
        $env:GEMINI_API_KEY = "여기에_키"
      (VS Code 를 켠 채로 터미널에서 실행하면 그 터미널에서만 유효합니다.
       영구 등록은 아래 '키 등록' 주석 참고)

본선 발표 전에 반드시:
    python explain.py --prewarm
  → 발표에 쓸 설명을 미리 생성해 explain_cache.json 에 저장합니다.
    현장에서 인터넷이 끊겨도 같은 문장이 그대로 나옵니다.
────────────────────────────────────────────────
"""

import json
import os
import pathlib
import re

# ─── 설정 ─────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"      # AI Studio 에 표시된 모델명과 맞추세요
TIMEOUT_MS = 8000                      # 8초 넘으면 포기하고 템플릿
CACHE_FILE = pathlib.Path(__file__).parent / "explain_cache.json"

# 끄고 싶을 때:  $env:SB_USE_GEMINI = "0"
USE_GEMINI = os.environ.get("SB_USE_GEMINI", "1") == "1"

R2_LIMIT = 0.75
CV_LIMIT = 15.0


SYSTEM = """너는 건물 에너지 절감액 정산 리포트의 설명 문장을 다듬는 역할이다.

규칙:
1. 아래 '계산 결과'에 있는 숫자만 쓴다. 숫자를 새로 만들거나 계산하지 마라.
2. 숫자 표기를 바꾸지 마라. 단위 변환·반올림·자릿수 축약(예: 3,570만) 전부 금지.
3. 금액이 맞는지 틀렸는지 판단하지 마라. 판정은 이미 끝났다.
4. 임대인과 임차인이 함께 읽는 문서다. 한쪽 편을 들지 마라.
5. 판정을 바꾸지 마라. 보류는 보류로, 잠정은 잠정으로 쓴다.
   금액이 확정됐다거나 지급된다는 말을 네가 만들어 붙이지 마라.
6. 2~3문장, 존댓말. 전문용어는 풀어서 쓴다.
7. 설명 문장만 출력한다. 머리말·목록·따옴표·마크다운 금지."""


# 판정별 금지어 — LLM이 판정을 뒤집는 것을 막는다.
# 숫자 검증만으로는 "확정했습니다" 같은 말을 걸러내지 못한다.
FORBIDDEN = {
    "확정 보류": ["확정했", "확정합니다", "확정됩니다", "확정된 금액", "확정되었",
                "지급", "정산 완료", "정산했", "정산됩니다"],
    "잠정 정산": ["최종 확정", "확정했", "확정됩니다", "지급 완료"],
    "금액 확정": ["보류", "확인 중", "정산하지 않", "확정하지 않"],
    # 공사 전 시뮬레이션을 실적처럼 말하는 것을 막는다
    "시뮬레이션": ["확정했", "확정됩니다", "확정된 금액", "지급", "정산했", "정산 완료",
                "절감했", "절감되었", "줄었습니다", "검증 완료", "검증되었", "검증했"],
}


def verdict_ok(answer, action):
    """판정과 모순되는 표현이 섞였는지 본다."""
    hits = [w for w in FORBIDDEN.get(action, []) if w in answer]
    return (not hits), hits


# ─── 1. 템플릿 (폴백이면서, Gemini 에게 주는 초안) ──────────

def _model_gap(m):
    """기준에 미달한 지표만 골라 문장으로. 충족한 지표를 미달이라고 쓰지 않는다."""
    gaps = []
    if m["cv_rmse"] > CV_LIMIT:
        gaps.append(f"예측 오차가 {m['cv_rmse']}%로 기준({CV_LIMIT:g}% 이하)을 넘고")
    if m["r2"] < R2_LIMIT:
        gaps.append(f"기온만으로 사용량을 설명하는 정도가 {m['r2']}로 기준({R2_LIMIT})에 못 미칩니다")
    if not gaps:
        return ""
    s = " ".join(gaps)
    return s[:-1] + "습니다" if s.endswith("넘고") else s


def build_template(ctx):
    """규칙 기반 설명. Gemini 가 실패하면 이 문장이 그대로 나간다."""
    month = ctx["month"]
    hit = ctx["anomaly"]
    m = ctx["metrics"]

    # 데이터가 없는 달 — 예측 범위니 정산이니 하는 말을 붙이지 않는다
    if not ctx.get("has_data", True):
        return (
            f"{month}월 사용량은 아직 공개되지 않아 금액을 계산하지 않았습니다. "
            f"공공 에너지데이터는 공개까지 약 4개월이 걸립니다."
        ), "데이터 없음"

    if hit:
        return (
            f"{month}월은 {hit['fuel']} 사용량이 과거 같은 달 평균의 "
            f"{hit['ratio']}배로 늘었습니다. 같은 달 기준으로 보기 어려운 폭이라, "
            f"원인이 확인되기 전까지 이 달은 금액을 산출하지 않고 확인 중입니다. "
            f"그해 기온이 특히 달랐는지, 영업시간·인원·설비가 바뀌었는지 확인이 필요합니다."
        ), "확정 보류"

    # 공사 전(또는 실측 기반 정산 미구현) — 금액은 시뮬레이션이다.
    # '사용량이 줄었다', '정산했다'고 쓰면 사실이 아니다.
    if ctx.get("simulated", True):
        gap = _model_gap(m)
        model = (f"기저선 모델은 {gap.rstrip('.')}." if gap
                 else f"기저선 모델은 예측 오차 {m['cv_rmse']}%로 기준을 충족했습니다.")
        return (
            f"{month}월 금액은 그린리모델링 공사 전이므로 실제 절감액이 아니라, "
            f"가정한 절감률을 적용한 시뮬레이션입니다. {model} "
            f"실제 절감액은 공사 후 사용량을 기저선과 비교해야 산출됩니다."
        ), "시뮬레이션"

    if ctx["verdict"] == "CONFIRMED":
        return (
            f"{month}월은 예측한 범위 안에서 사용량이 줄었습니다. "
            f"예측 오차 {m['cv_rmse']}%로 기준을 충족해 금액을 확정했습니다."
        ), "금액 확정"

    return (
        f"{month}월은 예측 범위 안입니다. 다만 {_model_gap(m).rstrip('.')}. "
        f"그래서 오차만큼 적게 잡아 잠정 정산했습니다. "
        f"12개월 합계 오차는 약 {abs(m['annual_error'])}%이므로 "
        f"최종 금액은 연 단위로 확정합니다."
    ), "잠정 정산"


# ─── 2. 숫자 검증 ────────────────────────────────────────

NUM = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")


def numbers_in(text):
    """문장에서 숫자만 뽑아 비교 가능한 형태로 정규화한다."""
    out = set()
    for raw in NUM.findall(text):
        try:
            out.add(float(raw.replace(",", "")))
        except ValueError:
            pass
    return out


def numbers_ok(answer, allowed_text):
    """
    Gemini 답에 들어간 숫자가 전부 '허용된 숫자'인지 본다.
    숫자를 빼먹는 건 괜찮다. 없던 숫자를 만들어 넣는 건 안 된다.
    """
    invented = numbers_in(answer) - numbers_in(allowed_text)
    return (not invented), sorted(invented)


# ─── 3. 캐시 ────────────────────────────────────────────

def _load_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache):
    CACHE_FILE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def cache_key(ctx, template):
    """같은 상황이면 같은 키 — 슬라이더를 흔들어도 재호출하지 않는다."""
    return f"{ctx['bld_id']}|{ctx['ym']}|{template}"


# ─── 4. Gemini 호출 ─────────────────────────────────────

def polish_with_gemini(ctx, template, action):
    """
    성공하면 (문장, 'gemini'), 실패하면 (None, 이유).
    여기서 예외를 밖으로 던지지 않는다. API 가 죽어도 서버는 살아야 한다.
    """
    if not USE_GEMINI:
        return None, "SB_USE_GEMINI=0"
    if not os.environ.get("GEMINI_API_KEY"):
        return None, "GEMINI_API_KEY 없음"

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None, "google-genai 미설치"

    m = ctx["metrics"]
    facts = [
        f"대상 월: {ctx['month']}월",
        f"예측 오차 CV(RMSE): {m['cv_rmse']}%  (기준 15% 이하)",
        f"설명력 R2: {m['r2']}  (기준 {R2_LIMIT} 이상)",
        f"12개월 합계 오차: {abs(m['annual_error'])}%",
        f"판정: {ctx['verdict']}",
    ]
    if ctx["anomaly"]:
        a = ctx["anomaly"]
        facts.append(
            f"이상 감지: {a['fuel']} 사용량이 과거 같은 달 평균의 {a['ratio']}배")
    if ctx.get("simulated", True):
        facts.append("금액 성격: 공사 전 시뮬레이션 (실제 절감액 아님)")
    facts.append(f"이 문장의 판정: {action}")

    prompt = (
        "[계산 결과]\n" + "\n".join(f"- {f}" for f in facts) +
        "\n\n[규칙 기반 초안]\n" + template +
        "\n\n위 초안을 같은 뜻으로, 더 읽기 쉽게 다듬어라. "
        "숫자는 [계산 결과]에 있는 것만 그대로 쓴다."
    )

    try:
        client = genai.Client(
            http_options=types.HttpOptions(timeout=TIMEOUT_MS))
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                temperature=0.2,            # 흔들리지 않게 낮게
                max_output_tokens=400,
            ),
        )
        text = (resp.text or "").strip()
    except Exception as e:                  # 네트워크·쿼터·키 전부 여기로
        return None, f"호출 실패: {type(e).__name__}"

    if not text:
        return None, "빈 응답"

    # ① 숫자 검증 — 허용 숫자 = 계산 결과 + 초안에 등장한 숫자
    ok, invented = numbers_ok(text, "\n".join(facts) + "\n" + template)
    if not ok:
        return None, f"없던 숫자 생성 {invented} — 폐기"

    # ② 판정 검증 — 보류를 확정으로 바꿔 말하는 것을 막는다
    ok, hits = verdict_ok(text, action)
    if not ok:
        return None, f"판정과 모순 {hits} — 폐기"

    return text, "gemini"


# ─── 5. 백엔드가 부르는 함수 ─────────────────────────────

def explain(ctx):
    """
    ctx = {bld_id, ym, month, verdict, metrics, anomaly}
    반환 = {text, action, source}
      source: gemini / cache / template:<이유>
    """
    template, action = build_template(ctx)

    # 데이터가 없는 달은 다듬을 내용이 없다 — LLM 을 부르지 않는다
    if action == "데이터 없음":
        return {"text": template, "action": action, "source": "template:데이터 없음"}

    cache = _load_cache()
    key = cache_key(ctx, template)
    if key in cache:
        return {"text": cache[key], "action": action, "source": "cache"}

    text, src = polish_with_gemini(ctx, template, action)
    if text:
        cache[key] = text
        try:
            _save_cache(cache)
        except Exception:
            pass
        return {"text": text, "action": action, "source": src}

    return {"text": template, "action": action, "source": f"template:{src}"}


# ─── 6. 발표 전 미리 생성 ────────────────────────────────

def prewarm():
    """
    발표에 쓸 월을 미리 돌려 캐시에 담는다.
    현장에서 인터넷이 끊겨도 같은 문장이 나온다.

    대상은 /api/demo 가 고른 시연 분기의 달들이다.
    화면이 실제로 띄우는 달과 같아야 구멍이 안 생긴다.
    """
    import warnings
    warnings.filterwarnings("ignore")
    from main import baseline_of, get_demo, get_settlement

    base = baseline_of(1)
    demo = get_demo()

    # ① 시연 분기에 실제로 표시되는 달 (여기가 핵심)
    targets = []
    for c in demo["cases"] + [{"year": 2026, "quarter": 3}]:
        s = get_settlement(year=c["year"], quarter=c["quarter"])
        targets += [m["ym"] for m in s["months"] if m["saving_won"] is not None]

    # ② 이상 감지된 달 — 심사위원이 다른 분기를 물어볼 수 있다
    targets += [a["ym"] for a in base["anomalies"]]

    # ③ 최근 12개월 — 즉석에서 다른 기간을 눌러볼 경우 대비
    targets += [m["ym"] for m in base["monthly_baseline"][-12:]]

    targets = list(dict.fromkeys(targets))

    print(f"\n[미리 생성] 시연 분기 {', '.join(c['period'] for c in demo['cases'])}")
    print(f"            대상 {len(targets)}개월")
    for ym in targets:
        ctx = {
            "bld_id": 1, "ym": ym, "month": int(ym[4:6]),
            "verdict": base["verdict"], "metrics": base["metrics"],
            "anomaly": next((a for a in base["anomalies"] if a["ym"] == ym), None),
        }
        r = explain(ctx)
        mark = {"gemini": "생성", "cache": "캐시"}.get(r["source"], "템플릿")
        print(f"  {ym}  [{mark}]  {r['text'][:50]}...")
        if r["source"].startswith("template:"):
            print(f"         └ 이유: {r['source'][9:]}")

    print(f"\n저장: {CACHE_FILE}")
    print("이 파일을 발표용 노트북에 꼭 같이 올리세요.\n")


if __name__ == "__main__":
    import sys
    if "--prewarm" in sys.argv:
        prewarm()
    else:
        print(__doc__)
        print(f"GEMINI_API_KEY 등록됨 : {bool(os.environ.get('GEMINI_API_KEY'))}")
        print(f"캐시 파일 존재        : {CACHE_FILE.exists()}")
        print("\n미리 생성:  python explain.py --prewarm\n")
