"""세이빙 AI — 백엔드가 부르는 입구 (2026-10-20) · 표준 라이브러리만 씀

  from saving_ai import SavingAI
  ai = SavingAI()                       # 같은 폴더의 saving_ai.exe(Windows) / saving_ai(Linux) + saving_ai.bin 을 한 번 띄워 둔다
  r = ai.understand("공사비 5천만, 8년 안에 회수하고 싶어요")
  → {'intent': 'MEDIATE', 'confidence': 0.98, 'by': 'nano',            # nano = C++ 모델 · rule = 1단계 규칙 · ask = 되묻기
     'slots': {'invest_won': 50000000, 'target_years': 8}, 'ambiguous': [], 'pii_masked': False,
     'masked_text': '…', 'model_text': '①공사비 ⓜ, ⓟ 안에 ②회수하고 싶어요'}

  판단 순서 (요구서 2-1)
    1. 규칙: 개인정보 가리기 → 숫자 해석 → 힌트 표시 (rules.py, 항상)
    2. 나노 모델(C++, CPU 한 코어 약 10ms): 확신 0.9 이상이면 그 의도
    3. 모델이 없거나 죽었거나 확신이 낮으면: 규칙 판단이 한 가지로 정해지면 그것, 아니면 intent='ASK' (되묻기)
  외부 AI 는 부르지 않는다. 모델이 문장을 만들지 않으므로 숫자 검사·금지어 검사가 실패할 일이 없다 (답 문장은 템플릿).
"""
import os, sys, threading, subprocess, platform

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rules  # noqa: E402

INTENTS = ['MEDIATE', 'RESOLVE', 'ANALYZE', 'TRUST', 'VIEW_OWNER', 'VIEW_TENANT', 'OUT']
CONF = 0.9
TIMEOUT_S = 2.0


def rule_intent(mt, slots):
    """1단계 규칙 판단 — 힌트 기호 개수로. 한 가지로 정해지지 않으면 None"""
    c = lambda *ks: sum(mt.count(k) for k in ks)
    nums = c('ⓜ', 'ⓟ', 'ⓡ')
    sc = {
        'MEDIATE': nums * 2 + c('①', '②', '③', '④') * 2,
        'RESOLVE': c('⑤', '⑭') * 2,
        'ANALYZE': c('ⓓ', 'ⓢ') * 2 + c('⑥', '⑦', '⑧') * 2,
        'TRUST': c('⑨') * 3,
        'OUT': c('⑬') * 2,
    }
    if c('⑫') and not nums and not c('①', '②', '③'):
        if c('⑪') > c('⑩'):
            sc['VIEW_TENANT'] = 5
        elif c('⑩') > c('⑪'):
            sc['VIEW_OWNER'] = 5
    best = sorted(sc.items(), key=lambda kv: -kv[1])
    if best[0][1] == 0:
        return 'OUT' if len(mt.strip()) <= 12 else None
    if len(best) > 1 and best[1][1] == best[0][1]:
        return None
    return best[0][0]


class SavingAI:
    def __init__(self, exe=None, model=None):
        win = platform.system() == 'Windows'
        names = ['saving_ai.exe'] if win else ['saving_ai', 'saving_ai_linux_arm64']
        self.exe = exe or next((os.path.join(HERE, n) for n in names if os.path.exists(os.path.join(HERE, n))),
                               os.path.join(HERE, names[0]))
        self.model = model or os.path.join(HERE, 'saving_ai.bin')
        self.proc, self.lock = None, threading.Lock()
        self._start()

    def _start(self):
        try:
            flags = 0x08000000 if platform.system() == 'Windows' else 0       # CREATE_NO_WINDOW
            self.proc = subprocess.Popen([self.exe, self.model], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL, creationflags=flags)
        except OSError:
            self.proc = None

    def _ask_model(self, mt):
        """→ (의도, 확신도) · 실패하면 None (요구서: 모델이 없거나 느려도 오류 없이 규칙으로)"""
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self._start()
                if self.proc is None:
                    return None
            res = {}

            def talk():
                try:
                    self.proc.stdin.write((mt.replace('\n', ' ') + '\n').encode('utf-8'))
                    self.proc.stdin.flush()
                    res['line'] = self.proc.stdout.readline().decode('utf-8')
                except Exception:
                    pass
            th = threading.Thread(target=talk, daemon=True)
            th.start(); th.join(TIMEOUT_S)
            line = res.get('line', '')
            if th.is_alive() or not line:
                try:
                    self.proc.kill()
                except Exception:
                    pass
                self.proc = None
                return None
            it, conf, *_ = line.rstrip('\n').split('\t')
            return it, float(conf)

    def understand(self, text):
        masked, pii = rules.mask_pii(text)
        p = rules.parse(masked)
        mt = rules.hint(p['model_text'])
        out = dict(masked_text=masked, pii_masked=pii, slots=p['slots'], ambiguous=p['ambiguous'], model_text=mt)
        m = self._ask_model(mt)
        r = rule_intent(mt, p['slots'])
        if m and m[1] >= CONF:
            out.update(intent=m[0], confidence=m[1], by='nano')
        elif r:
            out.update(intent=r, confidence=m[1] if m else None, by='rule', nano=m[0] if m else None)
        else:
            out.update(intent='ASK', confidence=m[1] if m else None, by='ask', nano=m[0] if m else None)
        return out

    def close(self):
        if self.proc:
            self.proc.kill()


if __name__ == '__main__':
    ai = SavingAI()
    for t in sys.argv[1:] or ['공사비 5천만, 8년 안에 회수하고 싶어요', '강남구 ○○동 761-26 우리 건물', '23년 8월 가스가 왜 튀었어?',
                              '이 금액 믿어도 돼요?', '세입자 입장은?', '공사비 3억, 10년', '양평 블룸비스타 호텔', '보일러 추천해줘',
                              '작년 여름 전기 왜 늘었어', '공사비 5천 8년', '제 번호 010-1234-5678 이고 공사비 1억 10년']:
        r = ai.understand(t)
        print(f"{r['intent']:11s} {r['by']:4s} {r['confidence'] if r['confidence'] is None else round(r['confidence'], 3)!s:6s} "
              f"{r['slots']} {r['ambiguous'] or ''} {'[개인정보 가림]' if r['pii_masked'] else ''} ← {t}")
