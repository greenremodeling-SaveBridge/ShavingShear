"""자모 단위 토크나이저 — 어휘가 고정이라 처음 보는 한글 글자도 <unk> 가 되지 않는다
   (RACHEL '야'·'으' 사고: 글자 단위 어휘에 없는 글자가 들어오면 출력이 깨졌다)

   한글 음절 → 초성·중성·(종성) 조합형 자모 (U+1100 / U+1161 / U+11A8 대)
   C++ 쪽(saving_ai.cpp)도 같은 계산으로 나눈다.
"""
INTENTS = ['MEDIATE', 'RESOLVE', 'ANALYZE', 'TRUST', 'VIEW_OWNER', 'VIEW_TENANT', 'OUT']
TAG = {'MEDIATE': '🤝 합의 도우미', 'RESOLVE': '🏢 건물 찾기', 'ANALYZE': '🔎 변동 분석', 'TRUST': '🛡 신뢰 확인',
       'VIEW_OWNER': '🤝 합의 도우미', 'VIEW_TENANT': '🤝 합의 도우미', 'OUT': ''}

SPECIAL = ['<pad>', '<unk>', '<cls>']
L = [chr(0x1100 + i) for i in range(19)]
V = [chr(0x1161 + i) for i in range(21)]
T = [chr(0x11A8 + i) for i in range(27)]
COMPAT = [chr(c) for c in range(0x3131, 0x3164)]          # ㄱ~ㅣ (ㅋㅋ · ㅠㅠ)
ASCII = list('abcdefghijklmnopqrstuvwxyz0123456789')
MARKS = list('ⓜⓡⓟⓓⓢ') + list('①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭')        # 숫자 표시 + 힌트 표시 (rules.py)
PUNCT = list(' ?!.,~-()[]○%:/\'"^*&+=@#;…·')
VOCAB = SPECIAL + L + V + T + COMPAT + ASCII + MARKS + PUNCT
STOI = {t: i for i, t in enumerate(VOCAB)}
UNK, CLS = STOI['<unk>'], STOI['<cls>']


def jamo(text):
    out = []
    for ch in text:
        if ch.isascii():
            ch = ch.lower()                        # 영문만 소문자 (C++ 와 같다)
        c = ord(ch)
        if 0xAC00 <= c <= 0xD7A3:
            k = c - 0xAC00
            out.append(L[k // 588]); out.append(V[(k % 588) // 28])
            if k % 28:
                out.append(T[k % 28 - 1])
        elif ch in ('\t', '\n', '\r', '　'):
            out.append(' ')
        else:
            out.append(ch)
    return out


def encode(model_text, ctx=256):
    ids = [CLS] + [STOI.get(t, UNK) for t in jamo(model_text)]
    return ids[:ctx]
