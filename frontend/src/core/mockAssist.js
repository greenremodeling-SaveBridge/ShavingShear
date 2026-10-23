/* ══════════════════════════════════════════════════════
   ?mock=1 일 때만 쓰는 가짜 응답 — 백엔드 /api/assist 가 생기기 전 시연용
   숫자는 요구서 3장 예시 값 그대로. 문장은 "답 문구 가이드"(CHATBOT_FRONT.md 9장)를 따른다:
     짧게 · 공감 먼저 · 다음에 할 일 · 같은 실패를 두 번 되풀이하지 않기 · 말하지 않은 숫자를 지어내지 않기
   의도 고르기는 낱말로 한다 — 진짜 판단은 서버의 세이빙 AI 모델이 한다.
   ══════════════════════════════════════════════════════ */

/* 은/는 · 이/가 — 숫자로 끝나면 읽는 소리로 (17085 → '오'라서 '는') */
const BATCHIM_DIGIT = { 0: 1, 1: 1, 3: 1, 6: 1, 7: 1, 8: 1 };
function josa(word, a, b) {
  const c = String(word).trim().slice(-1);
  if (/\d/.test(c)) return word + (BATCHIM_DIGIT[c] ? a : b);
  const k = c.charCodeAt(0) - 0xAC00;
  return word + (k >= 0 && k <= 11171 && k % 28 ? a : b);
}

const wait = (v, ms = 520) => new Promise(r => setTimeout(() => r(JSON.parse(JSON.stringify(v))), ms));

const CODES1 = { sigungu: '11680', bjdong: '10100', bun: '0761', ji: '0026' };
const CODES2 = { sigungu: '41830', bjdong: '32330', bun: '1235', ji: '0000' };

/* 자주 쓰는 칩 · fill 은 보내지 않고 입력창에 넣어 둔다 */
const C = {
  sample: { label: '시연 건물로 둘러볼게요', message: '시연 건물 보여줘' },
  byName: { label: '건물 이름으로 찾을게요', fill: '건물 이름: ' },
  retry: { label: '다시 말해 볼게요', fill: '' },
  deal: { label: '공사비 5천만, 8년', message: '공사비 5천만, 8년 안에 회수하고 싶어요' },
  dealFill: { label: '조건 직접 쓸게요', fill: '공사비 ' },
  gas: '23년 8월 가스가 왜 튀었어?',
  trust: '이 금액 믿어도 돼요?',
  tenant: '세입자 입장은?',
  owner: '건물주 입장은?',
  safe: '안전하게 하면?',
};

const BLD1 = { bld_id: 1, addr: '서울 ○○구 ○○동', purpose: '제1종근린생활시설', area: 1975.78, codes: CODES1,
  data_origin: { is_simulated: false, label: '공공데이터 실측' } };
const BLD2 = { bld_id: 2, addr: '경기도 양평군 강하면 강남로 316', purpose: '숙박시설(관광호텔)', area: 12500, codes: CODES2,
  data_origin: { is_simulated: true, label: '가상 데이터' } };

const MEDIATE = {
  feasible: true, invest_won: 50000000, target_years: 8,
  annual_saving_won: 10099932, annual_saving_low_won: 7955522,
  options: [
    { key: 'base', label: '기본 추정', owner_ratio: 0.65,
      base: { owner_annual_won: 6564955, tenant_monthly_won: 294581, payback_years: 7.6, recovery_rate: 1.05 },
      low: { owner_annual_won: 5171089, tenant_monthly_won: 232036, payback_years: 9.7, recovery_rate: 0.827 },
      meets_target_base: true, meets_target_low: false,
      note: '절감액이 기본 추정만큼 나오면 8년 안에 회수되지만, 낮게 나오면 9.7년이 걸려요' },
    { key: 'safe', label: '안전하게', owner_ratio: 0.8,
      base: { owner_annual_won: 8079945, tenant_monthly_won: 168332, payback_years: 6.2, recovery_rate: 1.293 },
      low: { owner_annual_won: 6364417, tenant_monthly_won: 132592, payback_years: 7.9, recovery_rate: 1.018 },
      meets_target_base: true, meets_target_low: true,
      note: '절감액이 낮게 나와도(90% 범위 하한) 8년 안에 회수돼요' },
  ],
  reply_owner: '건물주 몫을 65%로 하면 공사비 5,000만 원을 7.6년 만에 돌려받아요. 다만 절감액이 예상보다 적으면 9.7년이 걸려서, 그때도 8년 안에 받으려면 80%가 필요해요.',
  reply_tenant: '건물주 몫이 65%면 세입자는 매달 294,581원을, 80%면 매달 168,332원을 아껴요. 절감액이 예상보다 적으면 각각 232,036원, 132,592원이에요.',
  facts: [
    { label: '연간 절감액', value: 10099932, unit: '원', kind: 'simulated', goto: 'alloc' },
    { label: '90% 범위 하한', value: 7955522, unit: '원', kind: 'simulated', goto: 'base' },
  ],
  notices: ['공사 전 예상 금액이에요. 실제로 아낀 금액이 아니에요'],
  actions: [{ type: 'set_alloc', ratio: 0.65, invest: 50000000, years: 8 }],
  status: 'ESTIMATED',
};
const MEDIATE_NO = {
  feasible: false, invest_won: 300000000, target_years: 10, annual_saving_won: 10099932, options: [],
  alternatives: [
    { type: 'longer', years: 30, text: '건물주가 절감액을 전부 가져가도 30년이 걸려요' },
    { type: 'smaller', max_invest_won: 95949354, text: '10년 안에 받으려면 공사비를 약 9,595만 원 이하로 줄여야 해요(건물주 몫 95% 기준)' },
  ],
  reply_owner: '아쉽지만 공사비 3억 원은 10년 안에 돌려받기 어려워요. 이렇게 바꿔 보면 어떨까요?',
  reply_tenant: '이 조건은 건물주가 기간 안에 돌려받을 수 없어서 나눌 몫을 정하기 어려워요. 기간이나 공사비를 바꿔 볼까요?',
  facts: [{ label: '연간 절감액', value: 10099932, unit: '원', kind: 'simulated', goto: 'alloc' }],
  notices: ['공사 전 예상 금액이에요. 실제로 아낀 금액이 아니에요'], actions: [],
};
const ANALYZE = {
  available: true, ym: '202308', ref_ym: '202108',
  ref_note: '2022년 8월은 원자료가 없어 2021년 8월과 비교했어요',
  actual_kwh: 36806, ref_actual_kwh: 26879,
  change_kwh: 9927, weather_kwh: 1613, other_kwh: 8314,
  by_fuel: { elec: [23241, 27569], gas: [3638, 9237] },
  findings: ['OUT_OF_SEASON_GAS', 'NON_WEATHER', 'ANOMALY', 'STRUCTURAL_CHANGE'],
  reply: '2023년 8월은 2021년 8월보다 9,927 kWh를 더 썼어요. 그중 더위 때문인 건 1,613 kWh뿐이고, 8,314 kWh는 다른 이유예요. 난방이 없는 여름에 가스가 3,638 → 9,237 kWh로 늘었으니, 영업시간이나 가스 설비가 바뀌었는지 현장에서 확인해 보면 좋아요.',
  survey: ['급탕·주방 가스 설비 사용 변화', '영업시간 변화', '가스 설비 교체·추가'],
  facts: [{ label: '2023.08 실측', value: 36806, unit: 'kWh', kind: 'measured', goto: 'base' },
    { label: '기온 영향', value: 1613, unit: 'kWh', kind: 'model', goto: 'base' },
    { label: '기온 외 요인', value: 8314, unit: 'kWh', kind: 'model', goto: 'base' }],
  notices: ['원인은 사용량만으로 확정할 수 없어요'], actions: [],
};
const TRUST = {
  status_code: 'ESTIMATED',
  metric_checks: { cv_rmse: { value: 18.7, limit: '≤ 15.0', ok: false }, r2: { value: 0.655, limit: '≥ 0.75', ok: false } },
  reply: '솔직히 말씀드리면 아직은 예상 금액이에요. 공사 전이라 실제로 아낀 양이 없고, 예측 정확도도 기준보다 조금 낮아요. 그래서 금액을 확정하지 않고 범위로 보여드리고 있어요.',
};

const tagOf = { mediate: '🤝 합의 도우미', resolve: '🏢 건물 찾기', analyze: '🔎 변동 분석', trust: '🛡 신뢰 확인', clarify: '' };
function wrap(intent, reply, data, extra = {}) {
  return {
    intent, tag: tagOf[intent], reply, data,
    facts: data?.facts || [], notices: data?.notices || [], actions: data?.actions || [],
    chips: [], source: 'template', ...extra,
  };
}

/* ── 건물 찾기 ── 못 찾으면 이유를 말하고 다른 길을 준다. 두 번째 실패는 말을 바꾼다 */
let missed = 0;
const ROAD = /([가-힣\d]+(?:로|길))\s*(\d+(?:번길)?)\s*(\d+(?:-\d+)?)?/;
const LOT = /([가-힣]+(?:동|리|읍|면))\s*(\d+(?:-\d+)?)\s*(번지)?/;
const resolveRes = (result, message, candidates = [], extra = {}) => ({ result, candidates, message, facts: [], notices: [], actions: [], ...extra });

function resolveOf(t) {
  if (/양평|블룸|호텔/.test(t)) {
    return resolveRes('matched', '찾았어요. 다만 이 건물은 시연을 위해 만든 가상 데이터예요. 이 건물이 맞나요?', [BLD2]);
  }
  if (/761|○○동|근린|시연/.test(t)) return resolveRes('matched', '찾았어요. 이 건물이 맞나요?', [BLD1]);
  if (/아파트|빌라|다세대|오피스텔|단독주택|주택/.test(t) && !/모르|몰라/.test(t)) {
    return resolveRes('residential', '아파트·주택은 공공 에너지데이터 제공 대상이 아니라서 찾을 수 없어요. 상가나 사무실 건물이라면 주소를 알려 주세요.');
  }
  const road = t.match(ROAD);
  const lot = t.match(LOT);
  if (road || lot) {
    const where = (road ? road[0] : lot[0]).trim();
    return resolveRes('unregistered', `${josa(where, '은', '는')} 아직 에너지 데이터가 없는 건물이에요. 공공데이터가 공개된 건물만 볼 수 있거든요.`);
  }
  return null;
}

function resolveChat(t) {
  // 주소를 모를 때
  if (/(주소|번지|도로명).{0,8}(모르|몰라|기억\s*안|생각\s*안)|(모르|몰라).{0,6}(주소|건물)/.test(t)) {
    missed = 0;
    return wrap('clarify', '괜찮아요. 주소를 몰라도 건물 이름이나 동네만 알면 찾을 수 있어요. 예를 들어 ‘역삼동 상가’나 ‘블룸비스타 호텔’처럼 말해 주세요.', null,
      { chips: [C.byName, C.sample] });
  }
  // 우편번호 (숫자 5자리만)
  const zip = t.match(/(?<![\d-])(\d{5})(?![\d-])/);
  if (zip && !/만|억|원|년|%|월/.test(t)) {
    missed = 0;
    return wrap('clarify', `${josa(zip[1], '은', '는')} 우편번호 같아요. 우편번호로는 건물을 찾을 수 없어서, 도로명 주소(예: ○○로 12)나 건물 이름을 알려 주세요.`, null,
      { chips: [C.byName, C.sample] });
  }
  const d = resolveOf(t);
  if (d) {
    missed = 0;
    const chips = d.result === 'matched' ? [C.gas, C.deal] : [C.sample, { label: '다른 주소로 찾을게요', fill: '' }];
    return wrap('resolve', d.message, d, { chips });
  }
  return null;
}

export function mockResolve(q) {
  const d = resolveOf(String(q || ''));
  return wait(d || resolveRes('not_found', '어떤 건물인지 잘 모르겠어요. 예: 강남구 ○○동 761-26 · 양평 블룸비스타 호텔'));
}

export function mockAssist(message, context = {}) {
  const t = String(message || '').trim();
  const hasMoney = /\d\s*(천만|만|억)|[일이삼사오육칠팔구십백천]+\s*(천만|만|억)|\d[\d,]{4,}\s*원/.test(t);
  const hasYears = /\d+\s*년(?!\s*\d+\s*월)|[일이삼사오육칠팔구십]+\s*년/.test(t);
  const hasRatio = /반반|반띵|\d+\s*(대|:)\s*\d+|\d+\s*(%|프로|퍼센트)|칠삼|육사/.test(t);

  // 인사·고마움 — 짧게 받고 할 수 있는 걸 보여준다
  if (/^(안녕|하이|hi|hello|ㅎㅇ|반가)/i.test(t)) {
    return wait(wrap('clarify', '안녕하세요, 세이빙 AI예요. 공사비를 몇 년 안에 돌려받을 수 있는지, 이 건물 사용량이 왜 바뀌었는지 같은 걸 물어보세요.', null,
      { chips: [C.deal, C.gas, C.trust] }), 400);
  }
  if (/고마|감사|땡큐|ㄱㅅ/.test(t)) {
    return wait(wrap('clarify', '도움이 됐다니 다행이에요. 더 궁금한 게 생기면 언제든 물어보세요.', null, { chips: [C.trust, C.gas] }), 400);
  }

  // 건물 찾기 (주소·건물 이름·우편번호·"주소를 몰라요")
  if (!hasMoney && !hasRatio) {
    const r = resolveChat(t);
    if (r) return wait(r);
  }

  // 관점 바꾸기 (숫자 없이)
  if (/(세입자|임차인|입주|tenant)/i.test(t) && !hasMoney && !hasYears) {
    return wait(wrap('mediate', '이제 세입자 입장으로 설명할게요. 숫자는 그대로예요.', null,
      { actions: [{ type: 'set_viewer', viewer: 'tenant' }], chips: [C.owner, C.safe] }));
  }
  if (/(건물주|임대인|집주인|주인|landlord|owner)/i.test(t) && /입장|관점|기준|쪽|버전|시점|인데|예요|이에요/.test(t) && !hasMoney && !hasYears) {
    return wait(wrap('mediate', '이제 건물주 입장으로 설명할게요. 숫자는 그대로예요.', null,
      { actions: [{ type: 'set_viewer', viewer: 'owner' }], chips: [C.tenant, C.safe] }));
  }

  // 변동 분석
  if (/왜|튀|늘었|줄었|원인|이유|분석|많이\s*(나왔|썼)/.test(t) && !hasMoney) {
    if (/(26|2026)년\s*(7|8|9|1[0-2])월/.test(t)) {
      return wait(wrap('analyze', '그 달 사용량은 아직 공개되지 않았어요. 공공데이터는 약 4개월 늦게 나와서, 지금은 2026년 4월까지 볼 수 있어요.',
        { available: false, last_data_ym: '202604', facts: [], notices: [], actions: [] }, { chips: ['2026년 4월 사용량 분석해줘', C.gas] }));
    }
    const ym = t.match(/(\d{2,4})\s*년\s*(\d{1,2})\s*월|작년\s*(\d{1,2})\s*월/);
    if (!ym) {
      const m = t.match(/(\d{1,2})\s*월/);
      return wait(wrap('clarify', m ? `몇 년 ${m[1]}월인지 알려 주세요.` : '어느 달이 궁금하세요? 예를 들어 ‘2023년 8월’처럼 말해 주세요.', null,
        { chips: m ? [`2023년 ${m[1]}월 사용량 분석해줘`, `2024년 ${m[1]}월 사용량 분석해줘`, `2025년 ${m[1]}월 사용량 분석해줘`] : [C.gas] }), 900);
    }
    return wait(wrap('analyze', ANALYZE.reply, ANALYZE, { chips: [C.trust, C.deal] }));
  }

  // 신뢰 확인
  if (/믿|정확|확실|근거|보장|신뢰|검증|오차|진짜/.test(t) && !hasYears) {
    return wait(wrap('trust', TRUST.reply, TRUST, {
      facts: [{ label: '예측 오차', value: 18.7, unit: '%', kind: 'model', goto: 'base' }, { label: '설명력', value: 0.655, unit: '', kind: 'model', goto: 'base' }],
      notices: ['공사 전 금액은 예상이에요'], chips: [C.deal, C.gas],
    }));
  }

  // 합의 도우미
  if (/3억|삼억/.test(t)) {
    return wait(wrap('mediate', MEDIATE_NO.reply_owner, MEDIATE_NO, { chips: ['공사비 3억, 30년', '공사비 9천만, 10년'] }));
  }
  if (/(^|[^\d])5천(?!\s*만)|오천(?!\s*만)/.test(t)) {
    return wait(wrap('clarify', '5천만 원 말씀이신가요?', null,
      { chips: [{ label: '네, 5천만 원이에요', message: '공사비 5천만, 8년 안에 회수하고 싶어요' }, { label: '아니에요', fill: '공사비 ' }] }), 900);
  }
  const followUp = /안전|보수|낮게|적게|최악/.test(t);
  if (hasMoney || (hasYears && (hasRatio || /회수|공사비/.test(t))) || (followUp && context.last)) {
    return wait(wrap('mediate', MEDIATE.reply_owner, MEDIATE, { chips: [C.tenant, C.trust] }));
  }
  // 합의를 원하는데 조건이 없다 → 지어내지 않고 묻는다
  if (followUp || hasRatio || /회수|공사비|분배|나누|합의|비율|몫|본전/.test(t)) {
    return wait(wrap('clarify', '좋아요, 같이 정해 봐요. 공사비가 얼마인지, 몇 년 안에 돌려받고 싶은지 알려 주세요.', null,
      { chips: [C.deal, C.dealFill] }), 900);
  }

  // 못 알아들음 — 두 번째부터는 말을 바꾸고 다른 길을 준다
  missed += 1;
  if (missed >= 2) {
    missed = 0;
    return wait(wrap('clarify', '제가 잘 못 알아듣고 있네요. 시연 건물로 먼저 둘러보시면 어떤 걸 물어볼 수 있는지 금방 보여요.', null,
      { chips: [C.sample, C.deal, C.gas] }), 900);
  }
  return wait(wrap('clarify', '제가 잘 모르는 내용이에요. 공사비 회수 계산, 건물 찾기, 사용량이 바뀐 이유, 금액을 믿어도 되는지는 바로 알려드릴 수 있어요.', null,
    { chips: [C.deal, C.gas, C.trust] }), 900);
}
