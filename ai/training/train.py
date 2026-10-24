#!/usr/bin/env python3
"""세이빙 AI 나노 의도 판단기 — 학습·평가 (2026-10-20)

  RACHEL-Jev 와 같은 틀: 양방향 인코더 한 번 → <cls> 자리에서 의도 7가지 + 확신도 (글자 생성 없음)
  int8 모드 = C++ 와 같은 계산 (가중치 행마다 int8 · 입력 벡터마다 int8 · 정수 합)

  python train.py train SA_d128L4.pt        (SA_DIM SA_LAYER SA_HEAD SA_FF SA_EPOCH SA_LR)
  python train.py eval  SA_d128L4.pt        # val · fresh · 실사용(real.tsv) — int8
"""
import os, sys, json, math, time, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tok, rules

try:
    sys.path.insert(0, '/home/drboom/project/2026_project/nano_llm/rachel_s')
    import cool  # noqa: F401 — GPU 기다릴 때 CPU 잠들기 (DGX 전용, 없으면 건너뜀)
except ImportError:
    pass
import torch, torch.nn as nn, torch.nn.functional as F
torch.backends.cuda.matmul.allow_tf32 = False
NI = len(tok.INTENTS)


def q8w(W):
    s = (W.abs().amax(1, keepdim=True) / 127).clamp(min=1e-8)
    return (W / s).round().clamp(-127, 127), s[:, 0]


class Block(nn.Module):
    def __init__(s, d, ff):
        super().__init__()
        s.ln1, s.ln2 = nn.LayerNorm(d), nn.LayerNorm(d)
        s.qkv, s.o = nn.Linear(d, 3 * d), nn.Linear(d, d)
        s.f1, s.f2 = nn.Linear(d, ff * d), nn.Linear(ff * d, d)


class SA(nn.Module):
    def __init__(s, d, layers, heads, ff, ctx):
        super().__init__()
        s.d, s.h = d, heads
        s.tok, s.pos = nn.Embedding(len(tok.VOCAB), d), nn.Embedding(ctx, d)
        s.blocks = nn.ModuleList(Block(d, ff) for _ in range(layers))
        s.ln = nn.LayerNorm(d)
        s.intent = nn.Linear(d, NI)
        s.mode = 'float'

    def lin(s, x, mod):
        if s.mode == 'float':
            return F.linear(x, mod.weight, mod.bias)
        Wq, ws = q8w(mod.weight.float())
        xs = (x.abs().amax(-1, keepdim=True) / 127).clamp(min=1e-8)
        xq = (x / xs).round().clamp(-127, 127)
        return (xq @ Wq.T) * xs * ws + mod.bias.float()

    def emb(s, X):
        if s.mode == 'float':
            return s.tok(X) + s.pos(torch.arange(X.size(1), device=X.device))[None]
        tq, ts = q8w(s.tok.weight.float()); pq, ps = q8w(s.pos.weight.float())
        return (tq * ts[:, None])[X] + (pq * ps[:, None])[:X.size(1)][None]

    def forward(s, X, pad):
        B, T = X.shape
        x = s.emb(X)
        am = (~pad)[:, None, None, :]
        for b in s.blocks:
            q, k, v = s.lin(F.layer_norm(x, (s.d,), b.ln1.weight, b.ln1.bias), b.qkv).view(B, T, 3, s.h, s.d // s.h).permute(2, 0, 3, 1, 4)
            a = F.scaled_dot_product_attention(q, k, v, attn_mask=am)
            x = x + s.lin(a.transpose(1, 2).reshape(B, T, s.d), b.o)
            x = x + s.lin(F.gelu(s.lin(F.layer_norm(x, (s.d,), b.ln2.weight, b.ln2.bias), b.f1)), b.f2)
        h0 = F.layer_norm(x[:, 0], (s.d,), s.ln.weight, s.ln.bias)
        return s.lin(h0, s.intent)


def read(fn):
    p = os.path.join(HERE, 'data', fn)
    if fn.endswith('.tsv'):
        rows = []
        for l in open(p, encoding='utf-8'):
            it, t = l.rstrip('\n').split('\t', 1)
            rows.append(dict(text=t, intent=it, model_text=rules.model_input(t)))
        return rows
    return [json.loads(l) for l in open(p, encoding='utf-8')]


def tensors(rows, dev, ctx, drop=0.0):
    ids = [tok.encode(r['model_text'], ctx) for r in rows]
    if drop:          # 자모 몇 개를 <unk> 로 — 오타·STT 에 버티게
        ids = [[i if (j == 0 or random.random() >= drop) else tok.UNK for j, i in enumerate(x)] for x in ids]
    T = max(map(len, ids))
    X = torch.zeros((len(rows), T), dtype=torch.long)
    pad = torch.ones((len(rows), T), dtype=torch.bool)
    for k, x in enumerate(ids):
        X[k, :len(x)] = torch.tensor(x); pad[k, :len(x)] = False
    y = torch.tensor([tok.INTENTS.index(r['intent']) for r in rows])
    return X.to(dev), pad.to(dev), y.to(dev)


def predict(m, rows, ctx, bs=2048):
    m.eval(); out = [None] * len(rows)
    order = sorted(range(len(rows)), key=lambda i: len(rows[i]['model_text']))
    with torch.no_grad():
        for j in range(0, len(order), bs):
            ids = order[j:j + bs]
            X, pad, _ = tensors([rows[i] for i in ids], 'cuda', ctx)
            p = m(X, pad).float().softmax(-1)
            c, a = p.max(-1)
            for i, ai, ci in zip(ids, a.tolist(), c.tolist()):
                out[i] = (tok.INTENTS[ai], ci)
            if torch.cuda.memory_reserved() > 3 * 2**30:
                torch.cuda.empty_cache()
    return out


def score(m, rows, ctx, th=0.9):
    pr = predict(m, rows, ctx)
    ok = sum(p[0] == r['intent'] for p, r in zip(pr, rows))
    hi = [(p, r) for p, r in zip(pr, rows) if p[1] >= th]
    okh = sum(p[0] == r['intent'] for p, r in hi)
    return ok / len(rows), (okh / len(hi) if hi else 0), 1 - len(hi) / len(rows), pr


def train(out):
    dev = 'cuda'
    D, L, H, FF = (int(os.environ.get(k, v)) for k, v in (('SA_DIM', 128), ('SA_LAYER', 4), ('SA_HEAD', 4), ('SA_FF', 3)))
    CTX = int(os.environ.get('SA_CTX', 160)); EPOCH = int(os.environ.get('SA_EPOCH', 6))
    LR = float(os.environ.get('SA_LR', 1e-3)); BS = 512
    torch.manual_seed(int(os.environ.get('SA_SEED', 0))); random.seed(0)
    tr = read('train.jsonl'); va = read('val.jsonl'); fr = read('fresh.jsonl'); rl = read('real.tsv')
    m = SA(D, L, H, FF, CTX).to(dev)
    nw = sum(p.numel() for n, p in m.named_parameters() if p.dim() == 2)
    print(f'세이빙 AI d{D} L{L} h{H} ff{FF} ctx{CTX} · int8 가중치 {nw / 1024:.0f}KB · 학습 {len(tr)}행 → {out}', flush=True)
    opt = torch.optim.AdamW(m.parameters(), lr=LR, weight_decay=0.05)
    steps = math.ceil(len(tr) / BS) * EPOCH
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, LR, total_steps=steps, pct_start=0.05)
    t0, best = time.time(), -1
    for ep in range(1, EPOCH + 1):
        m.train()
        idx = sorted(range(len(tr)), key=lambda i: len(tr[i]['model_text']) + random.random() * 6)
        bt = [idx[i:i + BS] for i in range(0, len(idx), BS)]
        random.shuffle(bt)
        for b in bt:
            X, pad, y = tensors([tr[i] for i in b], dev, CTX, drop=0.02)
            with torch.autocast('cuda', dtype=torch.bfloat16):
                lo = m(X, pad)
            loss = F.cross_entropy(lo.float(), y, label_smoothing=0.02)
            opt.zero_grad(set_to_none=True); loss.backward()
            torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0)
            opt.step(); sch.step()
        a = {n: score(m, s, CTX)[:3] for n, s in (('val', va), ('fresh', fr), ('real', rl))}
        print(f'  ep{ep} loss {loss.item():.4f} · ' + ' · '.join(f'{n} {v[0]:.2%} (≥0.9 {v[1]:.2%}, 되묻기 {v[2]:.1%})' for n, v in a.items())
              + f' · {time.time() - t0:.0f}s', flush=True)
        sc = a['val'][0] + a['fresh'][0]
        if sc >= best:
            best = sc
            torch.save(dict(model=m.state_dict(), dim=D, layers=L, heads=H, ff=FF, ctx=CTX, intents=tok.INTENTS, vocab=tok.VOCAB),
                       os.path.join(HERE, out))


def load(ck):
    k = torch.load(os.path.join(HERE, ck), map_location='cuda', weights_only=False)
    m = SA(k['dim'], k['layers'], k['heads'], k['ff'], k['ctx']).cuda()
    m.load_state_dict(k['model']); m.eval()
    return m, k['ctx']


def evaluate(ck):
    m, ctx = load(ck)
    m.mode = 'int8'
    res = {}
    for n in ['val.jsonl', 'fresh.jsonl', 'real.tsv'] + (['real2.tsv'] if os.environ.get('SA_REAL2') else []):
        rows = read(n)
        acc, acch, ask, pr = score(m, rows, ctx)
        wrong = [dict(text=r['text'], want=r['intent'], got=p[0], conf=round(p[1], 3)) for p, r in zip(pr, rows) if p[0] != r['intent']]
        res[n] = dict(acc=acc, acc_conf=acch, ask=ask, wrong=wrong[:60])
        print(f'{n:12s} {acc:.2%} · 확신≥0.9 {acch:.2%} · 되묻기 {ask:.1%} · 틀림 {len(wrong)}', flush=True)
        if n.endswith('.tsv'):
            for w in wrong:
                print(f"    {w['want']:11s}→ {w['got']:11s} {w['conf']:.2f}  {w['text']}")
    json.dump(res, open(os.path.join(HERE, 'eval_' + os.path.splitext(ck)[0] + '.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    {'train': train, 'eval': evaluate}[sys.argv[1]](sys.argv[2])
