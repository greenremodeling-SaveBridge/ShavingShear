#!/usr/bin/env python3
"""C++ 실행기 ↔ 파이썬 int8 판단 전수 비교 (의도 같고 확신도 차 < 1e-3 이면 일치)"""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import train as TR

ck, binf = sys.argv[1], sys.argv[2]
m, ctx = TR.load(ck); m.mode = 'int8'
rows = TR.read('val.jsonl')[:5000] + TR.read('fresh.jsonl')[:5000] + TR.read('real.tsv') + TR.read('real2.tsv')
py = TR.predict(m, rows, ctx)
inp = ''.join(r['model_text'].replace('\n', ' ') + '\n' for r in rows)
out = subprocess.run([os.path.join(HERE, 'saving_ai'), os.path.join(HERE, binf)], input=inp.encode(), capture_output=True).stdout.decode().splitlines()
same = sum(o.split('\t')[0] == p[0] and abs(float(o.split('\t')[1]) - p[1]) < 1e-3 for o, p in zip(out, py))
it = sum(o.split('\t')[0] == p[0] for o, p in zip(out, py))
md = max(abs(float(o.split('\t')[1]) - p[1]) for o, p in zip(out, py))
print(f'{len(rows)}문장 · 의도 일치 {it}/{len(rows)} · 확신도까지 일치 {same}/{len(rows)} · 확신도 최대 차 {md:.2e}')
dec = lambda it, c: it if c >= 0.9 else 'ASK'
dsame = sum(dec(o.split('\t')[0], float(o.split('\t')[1])) == dec(p[0], p[1]) for o, p in zip(out, py))
print(f'실행/되묻기 판단(확신 0.9 기준) 일치 {dsame}/{len(rows)}')
for r, o, p in zip(rows, out, py):
    if dec(o.split('\t')[0], float(o.split('\t')[1])) != dec(p[0], p[1]):
        print(f"  C++ {o}  ·  py {p[0]} {p[1]:.4f}  ·  {r['text']}")
