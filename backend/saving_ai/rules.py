#!/usr/bin/env python3
"""세이빙 AI — 1단계 규칙 (2026-10-20)

  모델이 하지 않는 일을 전부 여기서 한다 (RACHEL 교훈: 사전 찾기·숫자는 모델에서 뺀다)
    mask_pii(text)   휴대폰·주민번호·이메일·계좌 → [전화번호] 등 (요구서 4-5와 같은 정규식)
    parse(text)      숫자 해석 (요구서 3-5) → 슬롯 + 모델 입력 문장(숫자 자리에 표시 기호)

  표시 기호: ⓜ 금액  ⓡ 비율  ⓟ 기간(년)  ⓓ 연월  ⓢ 계절(연도+여름 등)
  계산은 하지 않는다 — 글자를 숫자로 바꾸는 것까지만.
"""
import re

DATA_LAST_YEAR = 2026          # 데이터 마지막 해 — "작년" = 2025 (요구서 3-5)

# ───────────────────────── 개인정보 가리기 (요구서 4-5) ─────────────────────────
PII = [
    (re.compile(r'01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}'), '[전화번호]'),
    (re.compile(r'\d{6}[-\s]?[1-4]\d{6}'), '[주민번호]'),
    (re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+'), '[이메일]'),
    (re.compile(r'\d+(?:-\d+){2,}'), '[번호]'),          # 하이픈 2개 이상 숫자 묶음 (번지 761-26 은 하이픈 1개라 남는다)
]


def mask_pii(text):
    """→ (가린 문장, 가렸는가)"""
    hit = False
    for rx, rep in PII:
        text, n = rx.subn(rep, text)
        hit = hit or n > 0
    return text, hit


# ───────────────────────── 한글·아라비아 숫자 읽기 ─────────────────────────
KD = {'일': 1, '이': 2, '삼': 3, '사': 4, '오': 5, '육': 6, '륙': 6, '칠': 7, '팔': 8, '구': 9, '영': 0, '공': 0}
KM = {'십': 10, '백': 100, '천': 1000}
NUM = r'(?:\d[\d,]*(?:\.\d+)?|[일이삼사오육칠팔구십백천만억]+)'


def knum(s, after_eok_man=True):
    """'5천만' '일억 이천만' '1억 2천' '50,000,000' '1.5억' '십오' → 수 (못 읽으면 None)
       after_eok_man: '1억 2천' 처럼 억 뒤 맨숫자는 만 단위 (요구서 3-5: 1억 2천 = 120000000)"""
    s = re.sub(r'[\s,]', '', s)
    if not s:
        return None
    total, sec, cur, last_big = 0, 0, None, None
    i = 0
    while i < len(s):
        c = s[i]
        m = re.match(r'\d+(?:\.\d+)?', s[i:])
        if m:
            cur = float(m.group()); i += len(m.group()); continue
        if c in KD:
            if cur is not None:            # '사이' 처럼 단위 없이 이어진 한글 숫자는 숫자가 아니다
                return None
            cur = KD[c]
        elif c in KM:
            sec += (1 if cur is None else cur) * KM[c]; cur = None
        elif c == '만':
            sec += cur or 0
            total += (sec or 1) * 10_000; sec, cur, last_big = 0, None, '만'
        elif c == '억':
            sec += cur or 0
            total += (sec or 1) * 100_000_000; sec, cur, last_big = 0, None, '억'
        else:
            return None
        i += 1
    sec += cur or 0
    if sec and last_big == '억' and after_eok_man:
        sec *= 10_000
    v = total + sec
    return int(v) if abs(v - round(v)) < 1e-6 else v


MONTH_WORD = {'유월': 6, '시월': 10}


def _month(s):
    s = s.replace(' ', '')
    if s in MONTH_WORD:
        return MONTH_WORD[s]
    v = knum(s)
    return int(v) if v is not None and v == int(v) and 1 <= v <= 12 else None


def _year(s):
    v = knum(s, after_eok_man=False)
    if v is None or v != int(v):
        return None
    v = int(v)
    if 0 <= v <= 99:
        v += 2000
    return v if 2000 <= v <= 2099 else None


REL_YEAR = {'재작년': -2, '작년': -1, '지난해': -1, '올해': 0, '금년': 0, '올': 0}

# ───────────────────────── 슬롯 찾기 (순서 = 우선순위) ─────────────────────────
#   한글 숫자는 앞이 한글이면 낱말 속 글자일 수 있어 막는다 (예: '이사', '오늘') — 대신 뒤에 단위가 꼭 붙어야 한다
PAT = [
    # 연월: 23년 8월 · 2023년 8월 · 이천이십삼년 팔월 · 2023.08 · 작년 8월
    ('ym', re.compile(r'(?P<y>' + NUM + r')\s*년\s*(?P<m>' + NUM + r'|유월|시월)\s*월?(?<=월)')),
    ('ym', re.compile(r'(?<![\d-])(?:(?P<y>20\d\d)\s*[./-]\s*|(?P<y2>\d\d)\.)(?P<m>1[0-2]|0?[1-9])(?![\d.-])(?:\s*월)?')),
    ('ymr', re.compile(r'(?P<r>재작년|작년|지난해|올해|금년|올)\s*(?P<m>' + NUM + r'|유월|시월)\s*월?(?<=월)')),
    # 계절: 23년 여름 · 작년 겨울 → 되묻기
    ('season', re.compile(r'(?:(?P<y>' + NUM + r')\s*년|(?P<r>재작년|작년|지난해|올해|금년))\s*(?:의\s*)?(?P<s>봄|여름|가을|겨울)')),
    # 달만: 8월 (해 없음 → 되묻기)
    ('m', re.compile(r'(?<![가-힣\d])(?P<m>' + NUM + r'|유월|시월)\s*월?(?<=월)(?!\s*세)')),
    # 비율
    ('ratio_half', re.compile(r'반\s*반|오\s*대\s*오|반씩|절반씩|절반\s*절반|반띵|반땡|fifty|50\s*[:/]\s*50')),
    ('ratio_kpair', re.compile(r'(?<![가-힣])(?P<k>일구|이팔|삼칠|사육|육사|칠삼|팔이|구일)(?=\s|$|[,.?!~]|으로|로|이면|면|에|요|이요|씩|로요)')),
    ('ratio_pair', re.compile(r'(?P<a>' + NUM + r')\s*(?:대|:)\s*(?P<b>' + NUM + r')(?!\s*[년월억만천원])')),
    ('ratio_pct', re.compile(r'(?P<v>' + NUM + r')\s*(?:%|퍼센트|퍼|프로)')),
    # 기간: 8년 · 팔 년 · 십오 년 (뒤에 월이 오면 연월이라 위에서 먼저 잡힌다)
    ('period', re.compile(r'(?P<v>' + NUM + r')\s*(?:년|해)(?!\s*' + NUM + r'\s*월)(?!도)')),
    # 금액: 5천만 · 오천만 원 · 50,000,000원 · 1억 2천 · 3억 · 5천(애매)
    ('money', re.compile(r'(?P<v>(?:\d[\d,]*(?:\.\d+)?\s*(?:억|천만|백만|십만|만|천)|[일이삼사오육칠팔구십백천]+[만억]|[일이삼사오육칠팔구십백]+천)'
                         r'(?:\s*(?:\d[\d,]*(?:\.\d+)?|[일이삼사오육칠팔구십백천]+)\s*(?:천만|백만|십만|만|천|백))*)(?:\s*(?P<won>원))?'
                         r'|(?P<v2>\d{1,3}(?:,\d{3})+|\d{5,})\s*(?P<won2>원)')),
]
MARK = {'ym': 'ⓓ', 'ymr': 'ⓓ', 'm': 'ⓓ', 'season': 'ⓢ', 'ratio_half': 'ⓡ', 'ratio_kpair': 'ⓡ', 'ratio_pair': 'ⓡ', 'ratio_pct': 'ⓡ',
        'period': 'ⓟ', 'money': 'ⓜ'}
CORRECT = re.compile(r'말고|아니고|아니라|아니 |아니,|대신|정정|바꿔서|잘못 말')
_KGROUP = {'ratio_half': 'ratio', 'ratio_kpair': 'ratio', 'ratio_pair': 'ratio', 'ratio_pct': 'ratio', 'ymr': 'ym'}
OWNER_W = ('건물주', '집주인', '임대인', '주인', '오너')
TENANT_W = ('세입자', '임차인', '입주자', '입주민', '테넌트')


def _hangul_before(text, i):
    return i > 0 and '가' <= text[i - 1] <= '힣'


def _is_korean_num(s):
    return bool(re.fullmatch(r'[일이삼사오육칠팔구십백천만억\s]+', s))


def parse(text):
    """→ dict(slots=…, model_text=모델에 넣을 문장, spans=[(시작, 끝, 종류, 값)], ambiguous=[…])
       slots: invest_won · owner_ratio · target_years · ym · season(연도, 계절) · month_only"""
    taken = [False] * len(text)
    spans = []
    for kind, rx in PAT:
        for m in rx.finditer(text):
            s, e = m.span()
            if any(taken[s:e]):
                continue
            raw = m.group()
            #   한글 숫자 오인 막기: 한글 숫자로 시작하는데 앞 글자가 한글이면 낱말 속이다 ('이사 년'?)
            lead = re.match(r'[일이삼사오육칠팔구십백천만억]+', raw)
            #   '이십오프로' 처럼 두 글자 넘고 십·백·천이 든 한글 숫자는 붙여 써도 숫자다
            solid = lead and len(lead.group()) >= 2 and re.search(r'[십백천만억]', lead.group())
            if lead and not solid and _hangul_before(text, s) and kind not in ('ratio_half',):
                #   '공사비오천만' 처럼 붙여 쓴 금액은 살린다 (천·만·억이 들어간 금액만)
                if not (kind == 'money' and re.search(r'[천만억]', raw)):
                    continue
            val = None
            if kind == 'ym':
                y, mo = _year(m.group('y') or m.groupdict().get('y2') or ''), _month(m.group('m'))
                if y is None or mo is None:
                    continue
                val = f'{y}{mo:02d}'
            elif kind == 'ymr':
                mo = _month(m.group('m'))
                if mo is None:
                    continue
                val = f"{DATA_LAST_YEAR + REL_YEAR[m.group('r')]}{mo:02d}"
            elif kind == 'season':
                y = _year(m.group('y')) if m.group('y') else DATA_LAST_YEAR + REL_YEAR[m.group('r')]
                if y is None:
                    continue
                val = (y, m.group('s'))
            elif kind == 'm':
                mo = _month(m.group('m'))
                if mo is None:
                    continue
                val = mo
            elif kind == 'ratio_half':
                val = 0.5
            elif kind == 'ratio_kpair':
                a, b = KD[m.group('k')[0]], KD[m.group('k')[1]]
                val = round(a / (a + b), 4)
            elif kind == 'ratio_pair':
                a, b = knum(m.group('a')), knum(m.group('b'))
                if not a or not b or a + b <= 0 or a > 100 or b > 100:
                    continue
                if _is_korean_num(m.group('a')) and len(m.group('a').strip()) == 1 and _hangul_before(text, s):
                    continue
                val = round(a / (a + b), 4)
            elif kind == 'ratio_pct':
                v = knum(m.group('v'))
                if v is None or not 0 < v <= 100:
                    continue
                val = round(v / 100, 4)
            elif kind == 'period':
                v = knum(m.group('v'), after_eok_man=False)
                if v is None or v != int(v) or v <= 0:
                    continue
                v = int(v)
                if v > 99:                       # 2023년 — 기간이 아니라 연도
                    continue
                if _is_korean_num(m.group('v')) and len(m.group('v')) == 1 and _hangul_before(text, s):
                    continue
                val = v
            elif kind == 'money':
                if m.group('v2'):
                    val = knum(m.group('v2'))
                else:
                    val = knum(m.group('v'))
                if not val:
                    continue
                #   '이만큼' '삼만' — 한글로만 쓴 100만 원 미만은 '원'이 붙어야 금액
                if not m.group('v2') and _is_korean_num(m.group('v')) and val < 1_000_000 and not m.group('won') \
                        and not (val < 10_000 and val % 1000 == 0):     # '오천' 은 살려서 '5천만 원인가요?' 로 되묻는다
                    continue
            spans.append((s, e, kind, val))
            for k in range(s, e):
                taken[k] = True
    spans.sort()

    slots, amb = {}, []
    #   '반띵 말고 칠삼으로' · '8년 아니고 10년' — 정정 말이 있으면 같은 종류는 마지막 값을 쓴다
    if CORRECT.search(text):
        last = {}
        for sp in spans:
            last[_KGROUP.get(sp[2], sp[2])] = sp
        spans_use = [sp for sp in spans if last[_KGROUP.get(sp[2], sp[2])] is sp]
    else:
        spans_use = spans
    for s, e, kind, val in spans_use:
        if kind == 'money':
            if 'invest_won' not in slots:
                slots['invest_won'] = val
                raw = text[s:e]
                #   만·억·원이 없는 '5천' → 5천만 원인지 되묻는다
                if not re.search(r'[만억원]', raw):
                    amb.append(('money_unit', val))
        elif kind.startswith('ratio'):
            if 'owner_ratio' not in slots:
                near = text[max(0, s - 8):s]
                if kind == 'ratio_pct' and any(w in near for w in TENANT_W) and not any(w in near for w in OWNER_W):
                    val = round(1 - val, 4)          # '세입자 30%' → 건물주 0.7
                slots['owner_ratio'] = val
        elif kind == 'period':
            slots.setdefault('target_years', val)
        elif kind in ('ym', 'ymr'):
            slots.setdefault('ym', val)
        elif kind == 'season':
            slots.setdefault('season', val); amb.append(('season', val))
        elif kind == 'm':
            slots.setdefault('month_only', val); amb.append(('month_only', val))

    out, i = [], 0
    for s, e, kind, val in spans:
        out.append(text[i:s]); out.append(MARK[kind]); i = e
    out.append(text[i:])
    return dict(slots=slots, ambiguous=amb, spans=spans, model_text=''.join(out))


if __name__ == '__main__':
    import sys, json
    T = sys.argv[1:] or [
        '공사비 5천만, 8년 안에 회수하고 싶어요', '공사비 팔천만 반반 십오 년', '오천만 원', '5000만원', '50,000,000원',
        '1억 2천', '일억 이천만', '7대3', '칠 대 삼', '건물주 70%', '세입자 30%', '팔 년', '23년 8월 가스가 왜 튀었어?',
        '2023년 8월', '작년 8월', '작년 여름', '이 금액 믿어도 돼요?', '강남구 ○○동 761-26 우리 건물', '공사비 3억, 10년',
        '5천', '공사비오천만 팔년', '이사 오늘 오후', '연락처 010-1234-5678 로 주세요', '1.5억에 12년', '8월에 왜 늘었어',
        '2023.08 전기', '삼월 사용량', '시월에 가스',
    ]
    for t in T:
        p = parse(mask_pii(t)[0])
        print(f'{t:32s} → {p["model_text"]:28s} {json.dumps(p["slots"], ensure_ascii=False)} {p["ambiguous"] or ""}')


# ───────────────────────── 힌트 표시 (모델이 낱말 뜻을 외우지 않게) ─────────────────────────
#   핵심 낱말 앞에 분류 기호를 붙인다. 모델은 "어떤 기호가 어떤 맥락에 있나"만 배운다 (RACHEL hints.py 와 같은 생각)
#   목록은 팀이 직접 고칠 수 있다 — 고치면 모델을 다시 학습할 필요는 없지만, 새 낱말을 넣었다면 재학습이 좋다
HINTS = {
    '①': ['공사비', '공사 비용', '공사비용', '공사 금액', '공사금액', '공사대금', '리모델링 비용', '리모델링비', '시공비', '비용', '견적',
          '투자금', '투자비', '투자', '예산', '공사'],                                             # 공사비
    '②': ['payback', 'roi', 'break even', '손익분기', '투자 회수', '회수', '본전', '원금', '돌려받', '뽑으', '뽑고', '뽑을', '뽑아', '갚', '손해'],                   # 회수
    '③': ['반띵', 'split', 'ratio', '분배율', '비율', '분배', '배분', '나누', '나눠', '나눌', '나눈', '몫', '몇 대 몇', '몇대몇', '합의', '협상', '조율', '공평',
          '윈윈', '가져가', '가져갈'],                                                           # 나누기·합의
    '④': ['여유 있게', '여유있게', '넉넉하게', '안전 시나리오', '보수 시나리오', 'worst', 'conservative', '빡빡하지 않게', '안전', '보수적', '하한', '최악', '낮게 나오', '적게 나오', '덜 위험', '낮을 때', '기대보다 적', '적으면', '적게 나와'],  # 안전하게
    '⑤': ['공장', '창고', '오피스', '사무실', '물류센터', 'building', 'address', '주소', '번지', '건물', '빌딩', '상가', '호텔', '아파트', '빌라', '오피스텔', '주택', '사옥', '타워', '근린생활', '근생',
          '등록', '조회', '검색', '블룸비스타'],                                                    # 건물 찾기
    '⑥': ['electricity', 'gas', 'energy', 'usage', 'power', '가스', '전기', '전력', '사용량', '에너지', '난방', '냉방', 'kwh', '요금', '전기료', '관리비'],         # 사용량
    '⑦': ['why', 'reason', '왜', '원인', '이유', '어째서', '무슨 일', '때문', '탓'],                                       # 왜
    '⑧': ['go up', 'went up', 'increase', 'spike', 'vs', '대비', '공사 전', '공사 후', '전후', '튀', '뛰었', '뛴', '늘었', '늘어', '늘었', '올랐', '증가', '급증', '폭등', '줄었', '줄어', '감소', '떨어', '변동', '변화',
          '이상치', '이상하', '이상해', '이상한', '두배', '두 배', '많이 나', '많이 썼', '많이 써', '많이 씀', '높게', '높아',
          '적게 나왔', '치솟', '분석', '비교', '기온'],                                         # 변화
    '⑨': ['효력', '책임', '보증', '증거', '증빙', '백테스트', 'backtest', '유의미', '통계', 'mape', 'rmse', '오차율', '대충 뽑', '기반이야', '신빙성', '공증', '법적', '분쟁', '미더', 'accurate', 'reliable', 'trust', '데이터 쓴', '데이터 맞', '믿', '신뢰', '정확', '확실', '확정', '보장', '검증', '근거', '출처', '오차', '틀리', '틀릴', '틀린', '진짜', '사실',
          '뻥', '거짓', '과장', '추정', '예측', '가정', '설명력', 'r2', 'cv', '약속', '계약서', '제출', '사기'],     # 믿어도 돼?
    '⑩': ['소유주', '소유자', 'landlord', 'owner', '건물주', '집주인', '임대인', '건물 주인', '주인', '오너'],                                    # 건물주
    '⑪': ['tenant', '세 얻', '세를 얻', '세 들어', '세들어', '월세 내', '월세 사는', '장사하는 사람', '세입자', '임차인', '입주자', '입주민', '입주한', '입주 업체', '가게 사장', '임차 업체', '테넌트'],         # 세입자
    '⑫': ['view', '모드', 'mode', 'perspective', 'side', '입장', '관점', '시점', '기준으로', '버전', '쪽에서', '눈높이', '편에서', '보는 화면'],                # 관점
    '⑬': ['취득세', '재산세', '양도세', '충당금', '포인트', '인증', '바우처', '제도', '공유', '카톡', 'pdf', '개인정보', '브랜드', '중에 뭐가 나아', '뭐가 나아', '날씨', '추천', '사도', '살까', '사고 싶', '구매', '가격', '업체', '시공사', '쇼핑', '할인', '쿠폰', '결제', '환불', '구독',
          '회원', '로그인', '비밀번호', '다운로드', '대출', '이자', '주식', '코인', '세금', '보험', '지원금', '신청'],    # 범위 밖
}
_STEM = {}
for mk, ws in HINTS.items():
    for w in ws:
        _STEM.setdefault(w, mk)
_HRX = re.compile('|'.join(re.escape(w) for w in sorted(_STEM, key=len, reverse=True)))
#   주소 모양: 강남구 · 양평군 · 역삼동(변동·이동 등 제외) · 101동 · 테헤란로 152 · 761-26
_ADDR = re.compile(r'(?:[가-힣○]{1,5}(?:구|군|읍)(?=[\s\d]|$)|(?<![가-힣])(?!변동|이동|자동|행동|공동|작동|활동|운동|감동)[가-힣○]{1,4}동(?=[\s\d]|$)'
                   r'|\d+동|[가-힣]{1,6}(?:로|길)\s*\d|\d+-\d+)')
HINT_MARKS = list(HINTS) + ['⑭']           # ⑭ = 주소 모양


def hint(model_text):
    """핵심 낱말 앞에 기호 — '공사비 ⓜ' → '①공사비 ⓜ'"""
    t = _ADDR.sub(lambda m: '⑭' + m.group(), model_text)
    return _HRX.sub(lambda m: _STEM[m.group()] + m.group(), t)


def model_input(text):
    """서버가 모델에 넣는 최종 문장: 개인정보 가리기 → 숫자 표시 → 힌트 표시"""
    return hint(parse(mask_pii(text)[0])['model_text'])
