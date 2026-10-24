/* ══════════════════════════════════════════════════════
   세이빙 AI 호출 · 개인정보 가리기 · 기기 저장 (요구서 3장 · 4-4 · 4-5)
   화면은 숫자를 계산하지 않는다 — 서버(또는 ?mock=1 목업) 응답을 그대로 쓴다.
   ══════════════════════════════════════════════════════ */
import { post, getSnapshot } from './client.js';
import { mockAssist, mockResolve } from './mockAssist.js';

export const MOCK = (() => {
  try { return new URLSearchParams(window.location.search).get('mock') === '1'; } catch { return false; }
})();

/* ── 개인정보 가리기 (요구서 4-5) — 번지 761-26 은 하이픈이 하나라 남는다 ── */
const PII = [
  [/01[016789][-\s.]?\d{3,4}[-\s.]?\d{4}/g, '[전화번호]'],
  [/\d{6}[-\s]?[1-4]\d{6}/g, '[주민번호]'],
  [/[\w.+-]+@[\w-]+\.[\w.]+/g, '[이메일]'],
  [/\d+(?:-\d+){2,}/g, '[번호]'],
];
export function maskPII(text) {
  let t = String(text ?? ''), hit = false;
  for (const [rx, rep] of PII) {
    const n = t.replace(rx, rep);
    if (n !== t) hit = true;
    t = n;
  }
  return { text: t, masked: hit };
}

/* ── 서버 호출 ── 목업이면 서버를 부르지 않는다 */
/* 서버가 꺼져 저장본을 쓰는 중이면 목업이어도 저장본 규칙을 따른다 (시나리오 9) */
const mockOn = () => MOCK && getSnapshot().mode !== 'backup';
export function callAssist(message, context) {
  return mockOn() ? mockAssist(message, context) : post('/api/assist', { message, context });
}
export function callResolve(q) {
  return mockOn() ? mockResolve(q) : post('/api/resolve', { q });
}

/* ── 이 기기에 저장한 내 건물 (요구서 4-4) — 서버로 보내지 않는다 ── */
const ME = 'ss.me';
export function getMe() {
  try {
    const v = JSON.parse(localStorage.getItem(ME) || 'null');
    return v && v.codes ? v : null;
  } catch { return null; }
}
export function saveMe(v) {
  try { localStorage.setItem(ME, JSON.stringify({ ...v, saved_at: new Date().toISOString() })); return true; } catch { return false; }
}
export function clearMe() {
  try { localStorage.removeItem(ME); } catch { /* 저장소 없음 */ }
}
/* "내 건물 주소가 뭐였지?" — 기기에서 바로 답한다 (서버를 부르지 않음) */
export const asksMyBuilding = t => /(내|제|우리|저장한)\s*건물.{0,8}(주소|어디|뭐였|뭐더라|기억)/.test(t);

/* ── 단계별 추천 질문 ── 서버가 칩을 주면 그걸 쓴다 */
export const STEP_CHIPS = {
  entry: ['이 금액 믿어도 돼요?', '23년 8월 가스가 왜 튀었어?'],
  bld: ['이 금액 믿어도 돼요?', '23년 8월 가스가 왜 튀었어?'],
  diag: ['23년 8월 가스가 왜 튀었어?', '이 금액 믿어도 돼요?'],
  deal: ['이 금액 믿어도 돼요?', '23년 8월 가스가 왜 튀었어?'],
};
export const chipsFor = step => (
  !step ? STEP_CHIPS.entry
    : ['bld', 'elig'].includes(step) ? STEP_CHIPS.bld
      : ['prof', 'meas', 'base'].includes(step) ? STEP_CHIPS.diag
        : STEP_CHIPS.deal
);

/* 칩은 문자열이거나 { label, message } 또는 { label, fill } — fill 은 보내지 않고 입력창에 넣어 둔다 */
export const chipOf = c => (typeof c === 'string'
  ? { label: c, message: c }
  : c.fill != null ? { label: c.label, fill: c.fill } : { label: c.label, message: c.message || c.label });

/* 숫자 종류 (요구서 2장 10) — 색만으로 구분하지 않도록 글자와 기호를 같이 */
export const KIND = {
  measured: { text: '실측', tone: 'green', mark: 'fix' },
  model: { text: '모델 예측', tone: 'blue', mark: 'prov' },
  simulated: { text: '예상 금액', tone: 'amber', mark: 'sim' },
  ledger: { text: '건축물대장', tone: 'green', mark: 'fix' },
};
