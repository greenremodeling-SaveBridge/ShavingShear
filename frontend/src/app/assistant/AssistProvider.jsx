/* ══════════════════════════════════════════════════════
   세이빙 AI 상태 — 대화 기록 · 보내기 · 화면 조작 · 되돌리기 알림
   챗봇은 늘 떠 있지 않는다. 필요한 자리에서 ask() 로 열리고, 닫으면 사라진다.
   대화 기록은 이 탭이 열려 있는 동안만 남는다 (서버·기기에 저장하지 않음).
   ══════════════════════════════════════════════════════ */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AssistCtx } from './context.js';
import { asksMyBuilding, callAssist, getMe, maskPII } from '../../core/assist.js';
import { BuddyBody, Icon, reduced } from '../ui.jsx';
import { koMoney } from '../../core/format.js';

let seq = 0;
const nid = () => `m${++seq}`;
const sleep = ms => new Promise(r => setTimeout(r, Math.max(0, ms)));
/* 분석 종류별 최소 대기 (ms) — AI 분석은 빨라도 4초 */
const MIN = { start: 4000, mediate: 4000, analyze: 4000, trust: 4000, resolve: 2600, clarify: 1100 };

export function AssistProvider({ S, children }) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState('');
  const [toast, setToast] = useState(null);
  const [cheerKey, setCheerKey] = useState(0);
  const [stay, setStay] = useState(false);       // PC · 왼쪽 화면은 사용자가 직접 넘길 때만 바뀐다
  const [navLen, setNavLen] = useState(null);    // PC · 지나온 자리 수 (이전 화면 버튼용)
  const backFn = useRef(null);   // 올라갈 때마다 새싹이 잠깐 만세 (특약 복사 · 합의안 나옴)
  const piiNoted = useRef(false);
  const last = useRef(null);                  // 직전 합의 조건 — "안전하게 하면?" 같은 이어 묻기에 쓴다
  const nav = useRef({ go: null, step: null, closeOnNav: false, stay: false });
  const SRef = useRef(S);
  SRef.current = S;

  const push = useCallback(m => setMsgs(ms => [...ms, { id: nid(), ...m }]), []);

  /* 서버에 보내는 맥락 (요구서 3-4 + 요청서 C-2 제안) */
  const context = () => {
    const s = SRef.current;
    return {
      step: nav.current.step || 'entry', bld_id: s.bld.data?.bld_id ?? null, viewer: s.viewer,
      invest_won: s.invest, owner_ratio: s.ratio, target_years: s.years,
      quarter: s.quarterKey, last: last.current,
    };
  };

  const send = useCallback(async raw => {
    const text = String(raw ?? '').trim();
    if (!text || busy) return;
    setDraft('');
    // "내 건물 주소가 뭐였지?" — 기기에서 답한다
    if (asksMyBuilding(text)) {
      push({ role: 'user', text });
      const me = getMe();
      push({ role: 'ai', text: me ? `이 기기에 저장한 건물은 ${me.address}이에요.` : '이 기기에 저장한 건물이 없어요. 주소로 찾은 뒤 저장할 수 있어요.',
        notices: ['이 기기에만 저장돼 있고 서버에는 보관하지 않아요'] });
      return;
    }
    const { text: masked, masked: hit } = maskPII(text);
    push({ role: 'user', text: masked });
    if (hit && !piiNoted.current) {
      piiNoted.current = true;
      push({ role: 'note', text: '개인정보는 보내지 않았어요' });
    }
    setBusy(true);
    // 토스처럼: 빨라도 분석하는 모습을 최소 시간 보여준 뒤 답을 펼친다
    const id = nid();
    const t0 = performance.now();
    setMsgs(ms => [...ms, { id, role: 'ai', pending: true, t0, min: MIN.start }]);
    const patch = p => setMsgs(ms => ms.map(m => (m.id === id ? { ...m, ...p } : m)));
    try {
      const res = await callAssist(masked, context());
      const min = reduced() ? 900 : (MIN[res?.intent] ?? MIN.start);
      // 같은 조건으로 다시 물어 답이 그대로면, 바뀐 게 없는 이유를 한 줄로 알린다
      const pv = last.current, dd = res?.data;
      if (res?.intent === 'mediate' && dd && !res.filled && pv?.intent === 'mediate'
        && pv.invest_won === dd.invest_won && pv.target_years === dd.target_years) {
        res.filled = `이미 ${dd.target_years}년 · ${koMoney(dd.invest_won)} 기준으로 계산한 결과와 같아요`;
      }
      patch({ res, min });
      // 서버가 준 대화 상태(무엇을 물었는지 · 어떤 조건이었는지)를 다음 질문에 그대로 돌려준다
      if (res?.state) last.current = res.state;
      else if (res?.intent === 'mediate' && res.data?.invest_won) {
        last.current = { intent: 'mediate', invest_won: res.data.invest_won, target_years: res.data.target_years };
      }
      await sleep(min - (performance.now() - t0));
      // 관점 바꾸기는 사용자가 바로 요청한 것이라 곧장 반영한다
      for (const a of res?.actions || []) {
        if (a.type === 'set_viewer' && (a.viewer === 'owner' || a.viewer === 'tenant')) SRef.current.setViewer(a.viewer);
      }
      patch({ pending: false });
      if (res?.intent === 'mediate' && res.data?.feasible && res.data.options?.length) setCheerKey(n => n + 1);   // 합의안 계산이 끝났어요
    } catch (e) {
      await sleep(900 - (performance.now() - t0));
      // 서버가 꺼져 저장본에 없는 질문 → 오류가 아니라 안내 (요구서 4-6)
      const canned = e?.code === 'NO_CANNED';
      setMsgs(ms => ms.map(m => (m.id === id
        ? (canned ? { id, role: 'ai', text: e.message } : { id, role: 'error', text: '답을 가져오지 못했어요', retry: masked }) : m)));
    } finally {
      setBusy(false);
    }
  }, [busy, push]); // eslint-disable-line react-hooks/exhaustive-deps

  /* 어디서든: ask('질문') → 열고 바로 보냄 · ask('질문', { send: false }) → 입력창에만 */
  const ask = useCallback((q, { send: now = true } = {}) => {
    setOpen(true);
    if (q && now) setTimeout(() => send(q), 60);
    else if (q) setDraft(q);
  }, [send]);

  /* 화면 이동 — 틀(모바일·PC·처음 화면)이 자기 이동 함수를 등록한다
     stay(PC): "○○ 화면에서 보기"처럼 사용자가 이동 버튼을 누른 것(explicit)만 옮긴다 */
  const go = useCallback((id, opt) => {
    const n = nav.current;
    if (!n.go || (n.stay && !opt?.explicit && !opt?.opened)) return;
    if (n.closeOnNav) setOpen(false);
    n.go(id, opt);
  }, []);
  const bindBack = useCallback((len, fn) => { backFn.current = fn; setNavLen(len); }, []);
  const navBack = useCallback(() => backFn.current?.(), []);
  const bindNav = useCallback((fn, step, closeOnNav, stayHere = false) => {
    nav.current = { go: fn, step, closeOnNav, stay: stayHere };
    setStay(stayHere);
  }, []);

  /* 조건 바꾸기 + 되돌리기 알림 (요구서 4-2) */
  const showToast = useCallback(t => { setToast({ ...t, key: nid() }); if (t.mood === 'cheer') setCheerKey(n => n + 1); }, []);
  const applyAlloc = useCallback(async ({ ratio, invest, years }, { to = 'alloc', ai = false, building = null } = {}) => {
    const s = SRef.current;
    // 건물을 고르기 전에 시연 건물로 계산한 답이면 그 건물부터 연다
    let opened = false;
    if (!s.bld.data && building?.codes) {
      s.setCodes(building.codes);
      s.setAddress(building.addr);
      if (!(await s.lookup(building.codes))) return;
      opened = true;
    }
    const prev = { ratio: s.ratio, invest: s.invest, years: s.years, aiDraft: s.aiDraft };
    if (Number.isFinite(ratio)) s.setRatio(ratio);
    if (Number.isFinite(invest)) s.setInvest(invest);
    if (Number.isFinite(years)) s.setYears(years);
    if (ai) s.setAiDraft(true);
    go(to, { opened, explicit: true });   // 사용자가 누른 버튼이라 그 화면으로 옮긴다 (PC 는 돌아가기가 생김)
    showToast({
      text: to === 'draft' ? '특약 초안에 반영했어요' : '분배 조건을 바꿨어요',
      undo: () => {
        const c = SRef.current;
        c.setRatio(prev.ratio); c.setInvest(prev.invest); c.setYears(prev.years); c.setAiDraft(prev.aiDraft);
      },
    });
  }, [go, showToast]);

  const value = useMemo(() => ({
    open, setOpen, msgs, setMsgs, push, busy, draft, setDraft, send, ask, go, bindNav, applyAlloc, showToast, cheerKey, stay,
    navLen, navBack, bindBack,
    reset: () => { setMsgs([]); last.current = null; },
  }), [open, msgs, push, busy, draft, send, ask, go, bindNav, applyAlloc, showToast, cheerKey, stay, navLen, navBack, bindBack]);

  return (
    <AssistCtx.Provider value={value}>
      {children}
      <Toast t={toast} onDone={() => setToast(null)} />
    </AssistCtx.Provider>
  );
}

/* ── 아래 알림 · "조건을 바꿨어요 · 되돌리기" ── */
function Toast({ t, onDone }) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (!t) return undefined;
    setShown(true);
    const a = setTimeout(() => setShown(false), 5200);
    const b = setTimeout(onDone, 5600);
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [t?.key]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!t) return null;
  return createPortal(
    <div className={`toast${shown ? ' in' : ''}${t.mood ? ' with-buddy' : ''}`} role="status">
      {t.mood ? <BuddyBody key={t.key} w={44} live mood={t.mood} /> : <Icon name="check-fill" size={20} />}
      <span>{t.text}</span>
      {t.undo && <button type="button" onClick={() => { t.undo(); setShown(false); setTimeout(onDone, 300); }}>되돌리기</button>}
    </div>,
    document.body);
}
