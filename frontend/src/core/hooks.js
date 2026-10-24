import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react';
import { subscribe, getSnapshot } from './client.js';

export const useClient = () => useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

/**
 * 서버 자원 하나를 불러온다.
 *  - key 가 바뀌면 다시 부른다
 *  - 늦게 도착한 옛 응답은 버린다 (마지막 요청만 반영)
 *  - keep: 다시 부르는 동안 이전 값을 흐리게 보여준다 (깜빡임 없음)
 */
export function useResource(key, fetcher, { enabled = true, keep = false } = {}) {
  const [st, setSt] = useState({ status: 'idle', data: null, error: null });
  const seq = useRef(0);
  const fRef = useRef(fetcher);
  fRef.current = fetcher;
  const k = JSON.stringify(key);

  const run = useCallback(async () => {
    const my = ++seq.current;
    setSt(s => ({ status: 'loading', data: keep ? s.data : null, error: null }));
    try {
      const d = await fRef.current();
      if (my === seq.current) setSt({ status: 'ok', data: d, error: null });
    } catch (e) {
      if (my === seq.current) setSt({ status: 'error', data: null, error: e });
    }
  }, [k, keep]);

  useEffect(() => {
    if (enabled) run();
    else { seq.current++; setSt({ status: 'idle', data: null, error: null }); }
  }, [run, enabled]);

  return {
    ...st,
    reload: run,
    loading: st.status === 'loading' || (enabled && st.status === 'idle'),
    stale: st.status === 'loading' && st.data != null,
  };
}

export function useDebounced(value, ms) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function usePersistent(key, init, sanitize) {
  const [v, setV] = useState(() => {
    try {
      const raw = sessionStorage.getItem(key);
      if (raw != null) {
        const p = JSON.parse(raw);
        return sanitize ? sanitize(p, init) : p;
      }
    } catch { /* 저장소 없음 */ }
    return init;
  });
  useEffect(() => {
    try { sessionStorage.setItem(key, JSON.stringify(v)); } catch { /* 무시 */ }
  }, [key, v]);
  return [v, setV];
}

export function useMediaQuery(q) {
  const [m, setM] = useState(() => typeof window !== 'undefined' && window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    const f = () => setM(mq.matches);
    f();
    mq.addEventListener('change', f);
    return () => mq.removeEventListener('change', f);
  }, [q]);
  return m;
}

/* 요소 폭을 따라간다 — 차트를 실제 픽셀 폭으로 그려 글자가 줄어들지 않게 */
export function useMeasure() {
  const [el, setEl] = useState(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    if (!el) return;
    setW(el.getBoundingClientRect().width);
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, [el]);
  return [setEl, w];
}

/* 어두운 화면이 기본 · 밝은 화면으로 바꿀 수 있다 (화면 어디서 바꿔도 같이 바뀐다) */
const themeSubs = new Set();
export function useTheme() {
  const [t, setT] = useState(() => {
    try { return localStorage.getItem('ss.theme') === 'dark' ? 'dark' : 'light'; } catch { return 'light'; }
  });
  useEffect(() => {
    const f = v => setT(v);
    themeSubs.add(f);
    return () => themeSubs.delete(f);
  }, []);
  const set = useCallback(v => {
    const n = typeof v === 'function' ? v(document.documentElement.dataset.theme || 'light') : v;
    const r = document.documentElement;
    r.dataset.theme = n;
    try { localStorage.setItem('ss.theme', n); } catch { /* 무시 */ }
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', n === 'light' ? '#FFFFFF' : '#161D1A');
    themeSubs.forEach(f => f(n));
  }, []);
  return [t, set];
}

/* 큰 글씨 · 화면 어디서 바꿔도 같이 바뀐다 (이 기기에 기억) */
const bigSubs = new Set();
const readBig = () => { try { return localStorage.getItem('ss.big') === '1'; } catch { return false; } };
export function applyBig() { document.documentElement.dataset.big = readBig() ? '1' : '0'; }
export function useBigText() {
  const [b, setB] = useState(readBig);
  useEffect(() => {
    const f = v => setB(v);
    bigSubs.add(f);
    return () => bigSubs.delete(f);
  }, []);
  const toggle = useCallback(() => {
    const n = !readBig();
    try { localStorage.setItem('ss.big', n ? '1' : '0'); } catch { /* 무시 */ }
    document.documentElement.dataset.big = n ? '1' : '0';
    bigSubs.forEach(f => f(n));
  }, []);
  return [b, toggle];
}

/* 화면 보기 · 자동(창 폭) / PC / 모바일 · 화면 어디서 바꿔도 같이 바뀐다 (이 기기에 기억) */
const viewSubs = new Set();
const VIEWS = ['auto', 'pc', 'm'];
const readView = () => { try { const v = localStorage.getItem('ss.view'); return VIEWS.includes(v) ? v : 'auto'; } catch { return 'auto'; } };
export function useViewMode() {
  const [v, setV] = useState(readView);
  useEffect(() => {
    const f = n => setV(n);
    viewSubs.add(f);
    return () => viewSubs.delete(f);
  }, []);
  const set = useCallback(n => {
    try { localStorage.setItem('ss.view', n); } catch { /* 무시 */ }
    viewSubs.forEach(f => f(n));
  }, []);
  return [v, set];
}
