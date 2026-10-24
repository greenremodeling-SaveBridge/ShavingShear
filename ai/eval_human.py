#!/usr/bin/env python3
"""사람 말투 시험지 채점 — 배포 경로 그대로 (C++ 실행파일 + 규칙 + 되묻기)

  python eval_human.py saving_ai.bin data/real3.tsv [data/real4.tsv …]
  '실행' = 의도를 정해 바로 답함 · '되묻기' = 확신이 낮아 사용자에게 다시 물음
  틀린 실행이 제일 나쁘다 (엉뚱한 답). 되묻기는 한 번 더 묻는 비용만 든다.
"""
import os, sys
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from saving_ai import SavingAI

ai = SavingAI(model=os.path.join(HERE, sys.argv[1]))
for fn in sys.argv[2:]:
    R = [l.rstrip('\n').split('\t', 1) for l in open(os.path.join(HERE, fn), encoding='utf-8') if '\t' in l]
    n = len(R); ok = ask = 0; bad = []; per = Counter(); perok = Counter()
    for it, t in R:
        u = ai.understand(t); per[it] += 1
        if u['intent'] == 'ASK':
            ask += 1; bad.append(('되묻기', it, u.get('nano'), u['confidence'], t))
        elif u['intent'] == it:
            ok += 1; perok[it] += 1
        else:
            bad.append(('틀림', it, u['intent'], u['confidence'], t))
    ex = n - ask
    print(f'{fn}: {n}문장 · 전체 정답 {ok / n:.1%} · 실행 {ex / n:.1%} 중 맞음 {ok / max(ex, 1):.2%} · 되묻기 {ask / n:.1%} · 틀린 실행 {ex - ok}')
    print('   ' + ' · '.join(f'{k} {perok[k]}/{per[k]}' for k in per))
    if os.environ.get('SHOW'):
        for b in bad:
            print(f'   {b[0]} {b[1]} → {b[2]} {"" if b[3] is None else round(b[3], 2)}  {b[4]}')
ai.close()
