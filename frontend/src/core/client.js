/* ══════════════════════════════════════════════════════
   API 호출은 전부 이 파일 하나를 지난다.
   화면은 금액을 계산하지 않는다 — 서버 응답을 그대로 표시한다.
   서버에 닿지 않으면 backup.json(저장된 시연 데이터)으로 답한다.
   ══════════════════════════════════════════════════════ */
import { won, stampTime } from './format.js';
import EMBEDDED from '../../../web/backup.json';

// 미리보기 빌드(서버 없음)에서는 처음부터 저장된 시연 데이터만 쓴다
const STANDALONE = import.meta.env.VITE_STANDALONE === '1';

export const TIMEOUT_MS = 12000;
export const BACKUP_INVEST = 50000000;   // 저장된 시연 데이터의 분배 조건
export const BACKUP_YEARS = 10;

export class ApiError extends Error {
  constructor(message, extra = {}) {
    super(message);
    this.name = 'ApiError';
    Object.assign(this, extra);
  }
}

/* 같은 서버(8000)가 화면과 API를 함께 내주면 상대 경로, 아니면 localhost:8000 */
const API = (() => {
  if (import.meta.env.DEV) return '';
  const { protocol, port, pathname } = window.location;
  if (protocol === 'file:') return 'http://localhost:8000';
  if (pathname.startsWith('/app')) return '';          // 백엔드가 /app/ 으로 화면을 내주는 중 (포트가 8000이 아니어도)
  return port === '8000' ? '' : 'http://localhost:8000';
})();

const st = { mode: 'live', status: 'wait', backup: null, canReconnect: false, epoch: 0, booted: false };
const subs = new Set();
let snapshot = makeSnap();

function makeSnap() {
  return {
    mode: st.mode,                 // live | backup
    status: st.status,             // wait | up | down | backup
    canReconnect: st.canReconnect, // 백업 사용 중 서버가 다시 살아났는가
    epoch: st.epoch,               // 모드가 바뀔 때마다 1씩 — 화면이 다시 불러온다
    booted: st.booted,
    hasBackup: !!st.backup,
    backupPicks: !!st.backup?.picks,  // 저장 데이터에 공사 조합이 다 있으면 스위치도 움직인다
    stampTime: stampTime(st.backup?.meta?.generated_at),
  };
}
function emit() { snapshot = makeSnap(); subs.forEach(f => f()); }
function setStatus(s) { if (st.status !== s) { st.status = s; emit(); } }

export const subscribe = f => { subs.add(f); return () => subs.delete(f); };
export const getSnapshot = () => snapshot;

async function request(path, opt = {}) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), TIMEOUT_MS);
  let res;
  try {
    res = await fetch(API + path, { ...opt, signal: ctl.signal });
  } catch (e) {
    clearTimeout(timer);
    if (st.mode === 'live') setStatus('down');
    const timeout = e?.name === 'AbortError';
    throw new ApiError(timeout ? '서버 응답이 너무 늦습니다' : '서버에 연결할 수 없습니다', { network: true, timeout });
  }
  clearTimeout(timer);
  if (st.mode === 'live') setStatus('up');
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === 'string' ? j.detail : (j.detail?.[0]?.msg || detail);
    } catch { /* 본문 없음 */ }
    throw new ApiError(detail || '요청을 처리하지 못했습니다', { status: res.status });
  }
  try { return await res.json(); }
  catch { throw new ApiError('서버 응답을 읽을 수 없습니다', { shape: true }); }
}

export function api(path) {
  if (st.mode === 'backup') return fromBackup(path);
  return request(path, { headers: { Accept: 'application/json' } });
}
export function post(path, body) {
  if (st.mode === 'backup') return fromBackup(path, body);
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/* ── 저장된 시연 데이터 ── 실제 API 응답을 저장해둔 값. 계산은 하지 않는다 */
async function fromBackup(path, body) {
  const B = st.backup;
  if (!B) throw new ApiError('저장된 시연 데이터가 없습니다', { status: 503 });
  const [p, qs] = path.split('?');
  const q = new URLSearchParams(qs || '');
  const pick = k => {
    if (B[k] == null) throw new ApiError('저장된 시연 데이터에 이 항목이 없습니다', { status: 404 });
    return B[k];
  };
  switch (p) {
    case '/api/building':    return pick('building');
    case '/api/eligibility': return pick('eligibility');
    case '/api/baseline':    return pick('baseline');
    case '/api/demo':        return pick('demo');   // 백업은 건물 1 기준
    case '/api/profile':     return pick('profile');
    case '/api/measures': {
      const ids = (q.get('ids') || '').split(',').filter(Boolean);
      const all = pick('measures');
      if (!ids.length || ids.length === (all.measures || []).length) return all;
      const hit = B.picks?.[ids.join(',')]?.measures;
      if (hit) return hit;
      throw new ApiError('저장된 시연 데이터에서는 대책 선택을 바꿀 수 없습니다', { status: 409 });
    }
    case '/api/benefit': {
      const ids = (q.get('ids') || '').split(',').filter(Boolean);
      const all = pick('benefit');
      if (!ids.length || ids.length === (B.measures?.measures || []).length) return all;
      const hit = B.picks?.[ids.join(',')]?.benefit;
      if (hit) return hit;
      throw new ApiError('저장된 시연 데이터에서는 공사 선택을 바꿀 수 없습니다', { status: 409 });
    }
    case '/api/allocation': {
      const list = pick('allocation');
      if (body.invest_won !== BACKUP_INVEST || body.period_years !== BACKUP_YEARS) {
        throw new ApiError(
          `저장된 시연 데이터에는 공사비 ${won(BACKUP_INVEST)}원 · 분배 기간 ${BACKUP_YEARS}년 조건만 있습니다. 서버에 연결하면 다른 조건도 계산합니다.`,
          { status: 409, code: 'BACKUP_COND' });
      }
      const hit = list.find(a => Math.abs(a.owner_ratio - body.owner_ratio) < 1e-9);
      if (!hit) throw new ApiError('저장된 시연 데이터에 이 분배율이 없습니다', { status: 404 });
      return hit;
    }
    case '/api/settlement': {
      const s = B.settlement?.[`${q.get('year')}Q${q.get('quarter')}`];
      if (!s) throw new ApiError('저장된 시연 데이터에 없는 분기입니다', { status: 404 });
      return s;
    }
    /* 세이빙 AI — 저장해 둔 추천 질문 답만 (요구서 4-6). 없으면 대화는 서버 연결 뒤에 */
    case '/api/assist': {
      const c = B.assist_canned?.[body?.message];
      if (!c) throw new ApiError('서버 연결 시 대화할 수 있어요', { status: 503, code: 'NO_CANNED' });
      return c;
    }
    case '/api/mediate':
    case '/api/resolve':
    case '/api/analyze':
      throw new ApiError('서버 연결 시 대화할 수 있어요', { status: 503, code: 'NO_CANNED' });
    case '/api/explain':
      return B.explain?.[q.get('ym')] ||
        { ym: q.get('ym'), action: null, text: '저장된 시연 데이터에 이 달의 설명이 없습니다.' };
    default:
      throw new ApiError('저장된 시연 데이터에 없는 경로입니다', { status: 404 });
  }
}

/* 서버가 살아 있는지만 본다 (화면 데이터에는 쓰지 않음) */
export async function ping() {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 4000);
  try { return (await fetch(API + '/api/demo', { signal: ctl.signal, cache: 'no-store' })).ok; }
  catch { return false; }
  finally { clearTimeout(t); }
}

let bootPromise = null;
export function boot() {
  if (bootPromise) return bootPromise;
  bootPromise = (async () => {
    if (STANDALONE) {
      st.backup = EMBEDDED; st.booted = true; st.mode = 'backup'; st.status = 'backup';
      emit();
      return;
    }
    try {
      const r = await fetch('backup.json', { cache: 'no-store' });
      if (r.ok) st.backup = await r.json();
    } catch { /* 파일로 열면 막힌다 → 아래 내장본 */ }
    if (!st.backup) st.backup = EMBEDDED;
    const ok = await ping();
    st.booted = true;
    if (ok) st.status = 'up';
    else if (st.backup) { st.mode = 'backup'; st.status = 'backup'; }
    else st.status = 'down';
    emit();
    // 10초마다 실제 서버 상태를 확인 — 서버를 끄고 켜도 표시가 실제와 맞도록
    setInterval(async () => {
      if (document.hidden) return;
      const alive = await ping();
      if (st.mode === 'backup') {
        if (st.canReconnect !== alive) { st.canReconnect = alive; emit(); }
      } else setStatus(alive ? 'up' : 'down');
    }, 10000);
  })();
  return bootPromise;
}

export function enterBackup() {
  if (!st.backup || st.mode === 'backup') return false;
  st.mode = 'backup'; st.status = 'backup'; st.canReconnect = false; st.epoch++;
  emit();
  return true;
}
export function leaveBackup() {
  if (st.mode !== 'backup') return;
  st.mode = 'live'; st.status = 'wait'; st.canReconnect = false; st.epoch++;
  emit();
  ping().then(ok => setStatus(ok ? 'up' : 'down'));
}
