#!/usr/bin/env python3
"""세이빙 AI → C++ 용 바이너리 (2026-10-20)

  양자화는 train.py int8 모드와 똑같이 (행마다 s = max|w|/127 · round · ±127)
  형식 (little endian)
    'SAB1' · u32 d L h ff ctx V nint
    어휘 V 개: u8 길이 + UTF-8 · 의도 이름 nint 개: u8 길이 + UTF-8
    tok: V×d int8 + V f32 · pos: ctx×d int8 + ctx f32
    층마다: ln1 w,b · qkv (3d×d int8, 3d f32 s, 3d f32 b) · o · ln2 · f1 · f2
    lnf w,b · 의도 머리 nint×d int8 + nint f32 s + nint f32 b
  python export.py SA_d128L4.pt saving_ai.bin
"""
import sys, struct
import torch


def q8w(W):
    s = (W.abs().amax(1, keepdim=True) / 127).clamp(min=1e-8)
    return (W / s).round().clamp(-127, 127).to(torch.int8), s[:, 0].float()


def main():
    ck = torch.load(sys.argv[1], map_location='cpu', weights_only=False)
    sd = {k: v.float() for k, v in ck['model'].items()}
    d, L, h, ff, ctx = ck['dim'], ck['layers'], ck['heads'], ck['ff'], ck['ctx']
    voc, its = ck['vocab'], ck['intents']
    b = bytearray(b'SAB1') + struct.pack('<7I', d, L, h, ff, ctx, len(voc), len(its))
    for t in voc + its:
        e = t.encode('utf-8'); b += struct.pack('<B', len(e)) + e

    def mat(W):
        q, s = q8w(W)
        return q.numpy().tobytes() + s.numpy().astype('<f4').tobytes()

    def vec(v):
        return v.numpy().astype('<f4').tobytes()
    b += mat(sd['tok.weight']) + mat(sd['pos.weight'])
    for i in range(L):
        p = f'blocks.{i}.'
        b += vec(sd[p + 'ln1.weight']) + vec(sd[p + 'ln1.bias'])
        for n in ('qkv', 'o'):
            b += mat(sd[p + n + '.weight']) + vec(sd[p + n + '.bias'])
        b += vec(sd[p + 'ln2.weight']) + vec(sd[p + 'ln2.bias'])
        for n in ('f1', 'f2'):
            b += mat(sd[p + n + '.weight']) + vec(sd[p + n + '.bias'])
    b += vec(sd['ln.weight']) + vec(sd['ln.bias'])
    b += mat(sd['intent.weight']) + vec(sd['intent.bias'])
    open(sys.argv[2], 'wb').write(bytes(b))
    print(f'{sys.argv[2]}: {len(b):,} B · d{d} L{L} ff{ff} ctx{ctx} · 어휘 {len(voc)} · 의도 {len(its)}')


if __name__ == '__main__':
    main()
