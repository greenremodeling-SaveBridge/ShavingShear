/* 서버 응답을 화면 규칙으로 옮기는 곳. 문구가 아니라 코드 값(status_code, action, state)으로 분기한다. */
import { api, post, ApiError } from './client.js';

export const SAMPLE = {
  address: '서울 ○○구 ○○동',
  codes: { sigungu: '11680', bjdong: '10100', bun: '0761', ji: '0026' },
};
/* 공사 후 정산 흐름 시연용 — 처음부터 가상 데이터인 건물 2에 가상 공사(2025.05)를 얹었다 */
export const SAMPLE_RETROFIT = {
  address: '양평 블룸비스타 (가상)',
  codes: { sigungu: '41830', bjdong: '32330', bun: '1235', ji: '0000' },
};
export const SAMPLES = [
  { ...SAMPLE, badge: ['blue', '실측 · 공사 전'] },
  { ...SAMPLE_RETROFIT, badge: ['purple', '가상 · 공사 후'] },
];

export const CODE_FIELDS = [
  { key: 'sigungu', label: '시군구코드', len: 5 },
  { key: 'bjdong',  label: '법정동코드', len: 5 },
  { key: 'bun',     label: '본번',      len: 4 },
  { key: 'ji',      label: '부번',      len: 4 },
];

export function validateCodes(c) {
  const err = {};
  for (const f of CODE_FIELDS) {
    const v = String(c?.[f.key] ?? '').trim();
    if (!v) err[f.key] = '비어 있어요';
    else if (!/^\d+$/.test(v)) err[f.key] = '숫자만 입력해요';
  }
  return Object.keys(err).length ? err : null;
}

/* 필수 필드 검사 — 빠지면 그리지 않고 안내한다 */
export function need(obj, keys, what) {
  if (!obj || typeof obj !== 'object') throw new ApiError(`${what} 응답이 비어 있습니다`, { shape: true });
  const miss = keys.filter(k => obj[k] === undefined);
  if (miss.length) throw new ApiError(`${what} 응답에 필요한 항목이 없습니다 (${miss.join(', ')})`, { shape: true });
  return obj;
}

/* ── 정산 상태 (status_code 기준) ── */
export const STATUS = {
  ESTIMATED:         { tone: 'blue',   label: '예상 금액', sub: '실제 정산 아님', icon: 'sim' },
  PROVISIONAL:       { tone: 'orange', label: '잠정',       sub: '',              icon: 'prov' },
  VERIFIED:          { tone: 'green',  label: '검증 완료',  sub: '',              icon: 'fix' },
  REVIEW_REQUIRED:   { tone: 'red',    label: '검토 필요',  sub: '정산 보류',     icon: 'hold' },
  INSUFFICIENT_DATA: { tone: 'gray',   label: '데이터 없음', sub: '정산 불가',    icon: 'none' },
};
export const statusOf = (code, fallback) =>
  STATUS[code] || { tone: 'gray', label: fallback || '상태 미상', sub: '', icon: 'unknown' };

/* 월별 state — '정산' 달은 분기 상태에 맞춰 시뮬레이션/잠정/검증 완료로 부른다 */
export function monthLabel(state, code) {
  if (state === '정산') {
    if (code === 'PROVISIONAL') return { text: '잠정', tone: 'orange' };
    if (code === 'VERIFIED') return { text: '검증 완료', tone: 'green' };
    return { text: '예상 금액', tone: 'blue' };
  }
  if (state === '확인 중') return { text: '확인 중 · 금액 제외', tone: 'red' };
  if (state === '데이터 없음') return { text: '데이터 없음', tone: 'gray' };
  return { text: state || '—', tone: 'gray' };
}

/* ── AI 설명 action (한국어 값 그대로) ── 모르는 값은 회색 기본 */
export const ACTION = {
  '데이터 없음': { tone: 'gray',   icon: 'none' },
  '시뮬레이션':  { tone: 'blue',   icon: 'sim' },
  '확정 보류':   { tone: 'red',    icon: 'hold' },
  '잠정 정산':   { tone: 'orange', icon: 'prov' },
  '금액 확정':   { tone: 'green',  icon: 'fix' },
};
export const actionOf = a => ACTION[a] || { tone: 'gray', icon: 'unknown' };

/* ── 분기 선택 ── /api/demo 의 label 은 쓰지 않는다 */
const CASE_META = {
  '2026-1': { txt: '이상 없음',   tip: '사용량 이상이 감지되지 않은 분기' },
  '2023-4': { txt: '일부 제외',   tip: '이상이 감지된 달만 금액에서 뺀 분기' },
  '2023-3': { txt: '전체 보류',   tip: '분기 전체에 이상이 감지되어 금액을 내지 않는 분기' },
  '2026-3': { txt: '데이터 없음', tip: '사용량이 아직 공개되지 않은 분기' },
};
const KIND_META = {
  normal: { txt: '이상 없음', tip: '사용량 이상이 감지되지 않은 분기' },
  partial: { txt: '일부 제외', tip: '이상이 감지된 달만 금액에서 뺀 분기' },
  full: { txt: '전체 보류', tip: '분기 전체에 이상이 감지되어 금액을 내지 않는 분기' },
};
export function caseList(cases) {
  const all = (Array.isArray(cases) ? cases : []).map(c => ({
    y: c.year, q: c.quarter, period: c.period || `${c.year} ${c.quarter}분기`, kind: c.kind, post: !!c.post,
  }));
  if (!all.some(c => c.y === 2026 && c.q === 3)) all.push({ y: 2026, q: 3, period: '2026 3분기' });
  return all.map(c => {
    const key = `${c.y}-${c.q}`;
    const m = (c.kind && KIND_META[c.kind]) || CASE_META[key] || { txt: '', tip: '' };
    return { ...c, key, txt: c.post ? `공사 후 · ${m.txt}` : m.txt, tip: c.post ? `공사 후 실측으로 정산한 분기 · ${m.tip}` : m.tip };
  });
}

/* 설명할 달: 이상이 있으면 그 달, 없으면 금액이 있는 마지막 달, 그것도 없으면 분기 마지막 달 */
export function explainTarget(setl) {
  const months = setl?.months || [];
  const flagged = months.find(m => m.state === '확인 중');
  const withData = months.filter(m => m.saving_won != null);
  return flagged || withData[withData.length - 1] || months[months.length - 1] || null;
}

export const hasAmount = d => d && d.saving_won !== null && d.saving_won !== undefined;

/* ── 서버 호출 + 필수 필드 확인 ── */
export const fetchBuilding = codes =>
  api('/api/building?' + new URLSearchParams(codes))
    .then(d => need(d, ['bld_id', 'addr', 'area', 'purpose', 'use_apr_day'], '건물'));

export const fetchEligibility = id =>
  api(`/api/eligibility?bld_id=${id}`).then(d => need(d, ['checks', 'eligible', 'msg'], '대상 판정'));

export const fetchProfile = id =>
  api(`/api/profile?bld_id=${id}`).then(d => need(d, ['years', 'findings', 'unverified'], '건축물 진단'));

export const fetchMeasures = (id, ids) =>
  api(`/api/measures?bld_id=${id}${ids ? '&ids=' + ids.join(',') : ''}`).then(d => {
    need(d, ['available'], '개선 대책');
    if (d.available) need(d, ['measures', 'total_saving_kwh', 'naive_sum_kwh', 'overlap_adjust_kwh',
      'total_saving_rate', 'total_co2_kg'], '개선 대책');
    return d;
  });

export const fetchBaseline = id =>
  api(`/api/baseline?bld_id=${id}`).then(d => need(d, ['metrics', 'monthly_baseline'], '기저선'));

export const fetchAllocation = body =>
  post('/api/allocation', body).then(d => need(d, ['owner_ratio', 'annual_saving_won', 'owner_annual_won',
    'tenant_annual_won', 'required_owner_ratio', 'recovery_rate', 'feasibility_msg'], '분배'));

export const fetchCases = id => api('/api/demo' + (id != null ? `?bld_id=${id}` : '')).then(d => (Array.isArray(d?.cases) ? d.cases : []));

export const fetchSettlement = (id, y, q, ratio) =>
  api('/api/settlement?' + new URLSearchParams({ bld_id: id, year: y, quarter: q, owner_ratio: ratio }))
    .then(d => need(d, ['status_code', 'period', 'months'], '정산'));

export const fetchExplain = (id, ym) =>
  api(`/api/explain?bld_id=${id}&ym=${ym}`).then(d => need(d, ['text'], 'AI 설명'));
