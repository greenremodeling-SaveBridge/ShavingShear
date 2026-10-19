"""
제미나이 연결 전 5가지 점검  —  python test_llm_safety.py

실제 Gemini 키 없이도 돌아갑니다. 키가 있으면 ①⑤에서 진짜 호출을 섞어 시험합니다.
"""
import os, warnings; warnings.filterwarnings("ignore")
import explain as E
from main import get_settlement, get_explain

P = F = 0
def chk(n, cond, detail=""):
    global P, F
    print(f"  {'통과' if cond else '실패'}  {n}" + (f"\n          {detail}" if detail else ""))
    globals().__setitem__('P', P+1) if cond else globals().__setitem__('F', F+1)

HOLD = {"bld_id":1,"ym":"202307","month":7,"verdict":"RANGE",
        "metrics":{"cv_rmse":18.7,"r2":0.655,"annual_error":-5.0},
        "anomaly":{"fuel":"가스","ratio":1.94}}

print("\n① API 오류·시간 초과 → 템플릿 자동 전환")
E.CACHE_FILE.unlink(missing_ok=True)
saved = os.environ.pop("GEMINI_API_KEY", None)
r = E.explain(dict(HOLD))
chk("키 없음 → 템플릿", r["source"].startswith("template:") and len(r["text"]) > 40,
    f'source={r["source"]}')
if saved: os.environ["GEMINI_API_KEY"] = saved

os.environ["GEMINI_API_KEY"] = "invalid-key-for-test"
E.CACHE_FILE.unlink(missing_ok=True)
r = E.explain(dict(HOLD))
chk("잘못된 키 → 템플릿", r["source"].startswith("template:"), f'source={r["source"]}')

orig, E.TIMEOUT_MS = E.TIMEOUT_MS, 1
E.CACHE_FILE.unlink(missing_ok=True)
r = E.explain(dict(HOLD))
chk("1ms 제한시간 → 템플릿", r["source"].startswith("template:"), f'source={r["source"]}')
E.TIMEOUT_MS = orig
if saved: os.environ["GEMINI_API_KEY"] = saved
else: os.environ.pop("GEMINI_API_KEY", None)

print("\n② 없던 금액·절감률을 만들면 폐기")
facts = "대상 월: 7월 / 배수 1.94 / 오차 18.7% / 설명력 0.655"
for text, want, why in [
    ("7월 가스가 1.94배로 늘었습니다.", True,  "입력에 있는 숫자만"),
    ("7월 가스가 늘었습니다.",            True,  "숫자 생략은 허용"),
    ("약 2배로 늘었습니다.",              False, "2는 입력에 없음"),
    ("절감액은 3,570만원입니다.",         False, "금액을 만들어냄"),
    ("절감률 25%를 적용했습니다.",        False, "절감률을 만들어냄"),
    ("설명력은 65.5%입니다.",             False, "0.655를 변환"),
]:
    ok, inv = E.numbers_ok(text, facts)
    chk(f"{why}", ok == want, f'"{text}" → {"유지" if ok else "폐기"}' + (f" {inv}" if inv else ""))

print("\n③ 보류를 확정으로 바꿔 말하면 폐기")
for text, want, why in [
    ("이 달은 금액을 확정하지 않고 확인 중입니다.", True,  "보류를 보류로"),
    ("검토 결과 금액을 확정했습니다.",              False, "보류인데 확정했다고 말함"),
    ("정산 완료되어 지급됩니다.",                   False, "보류인데 지급을 말함"),
]:
    ok, hits = E.verdict_ok(text, "확정 보류")
    chk(why, ok == want, f'"{text}" → {"유지" if ok else "폐기 " + str(hits)}')
ok, _ = E.verdict_ok("기준 충족으로 금액을 확정했습니다.", "금액 확정")
chk("확정을 확정으로", ok)

print("\n④ 같은 입력 반복 → 금액·상태 불변")
runs = [get_settlement(year=2023, quarter=3, owner_ratio=0.7) for _ in range(5)]
chk("보류 분기 5회 — 금액 동일", len({r["saving_won"] for r in runs}) == 1,
    f'금액 {[r["saving_won"] for r in runs]}')
chk("보류 분기 5회 — 상태 동일", len({r["status"] for r in runs}) == 1,
    f'상태 {runs[0]["status"]}')
runs = [get_settlement(year=2026, quarter=1, owner_ratio=0.7) for _ in range(5)]
chk("정상 분기 5회 — 금액 동일", len({r["saving_won"] for r in runs}) == 1,
    f'{runs[0]["saving_won"]:,}원')
acts = {get_explain(1, "202307")["action"] for _ in range(5)}
chk("설명 5회 — 판정 동일", len(acts) == 1, f'판정 {acts}')

print("\n⑤ 인터넷 없이 핵심 시연 완주")
E.CACHE_FILE.unlink(missing_ok=True)
os.environ["SB_USE_GEMINI"] = "0"
import importlib; importlib.reload(E)
import main; importlib.reload(main)
allok = True
for y, q in [(2026,1),(2023,4),(2023,3),(2026,3)]:
    s = main.get_settlement(year=y, quarter=q, owner_ratio=0.7)
    e = main.get_explain(1, s["months"][0]["ym"])
    good = s["status"] and len(e["text"]) > 30 and e["source"].startswith("template")
    allok &= good
    print(f"          {y}Q{q}  상태={s['status']:6} 금액={s['saving_won']:>10,}원  설명={len(e['text'])}자")
chk("4개 사례 전부 설명까지 완주", allok)
os.environ.pop("SB_USE_GEMINI")

print(f"\n{'='*52}\n  통과 {P} · 실패 {F}\n{'='*52}\n")
