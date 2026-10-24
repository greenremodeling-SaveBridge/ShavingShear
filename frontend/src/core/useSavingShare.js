/* PC·모바일이 함께 쓰는 화면 상태. 두 화면이 같은 값을 같은 순서로 불러온다. */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { boot, BACKUP_INVEST, BACKUP_YEARS } from './client.js';
import { useClient, useDebounced, usePersistent, useResource } from './hooks.js';
import {
  SAMPLE, validateCodes, caseList, explainTarget,
  fetchBuilding, fetchEligibility, fetchProfile, fetchMeasures, fetchBaseline,
  fetchAllocation, fetchCases, fetchSettlement, fetchExplain,
} from './domain.js';

const RATIO_MIN = 0.05, RATIO_MAX = 0.95, RATIO_STEP = 0.05;
const snapRatio = r => Math.round(Math.min(RATIO_MAX, Math.max(RATIO_MIN, r)) / RATIO_STEP) * RATIO_STEP;
export const RATIO = { min: RATIO_MIN, max: RATIO_MAX, step: RATIO_STEP, snap: r => +snapRatio(r).toFixed(2) };
const exact = r => +Math.min(RATIO_MAX, Math.max(RATIO_MIN, r)).toFixed(3);
export const INVEST = { min: 1_000_000, max: 10_000_000_000 };
export const YEARS = { min: 1, max: 30 };

export function useSavingShare({ autoLookup = true } = {}) {
  const conn = useClient();

  /* ── 입력값 ── */
  const [codes, setCodes] = useState(SAMPLE.codes);
  const [address, setAddress] = useState(SAMPLE.address);
  const [invest, setInvest] = usePersistent('ss.invest', 50000000,
    v => (Number.isFinite(v) && v >= INVEST.min && v <= INVEST.max ? Math.round(v) : 50000000));
  //   회수선에 붙인 값(예: 49.5%)도 남는다 — 5% 칸이 아닐 수 있다
  const [ratio, setRatioRaw] = usePersistent('ss.ratio', 0.7,
    v => (Number.isFinite(v) ? exact(v) : 0.7));
  const [years, setYears] = usePersistent('ss.years', 10,
    v => (Number.isInteger(v) && v >= YEARS.min && v <= YEARS.max ? v : 10));
  const [quarterKey, setQuarterKey] = usePersistent('ss.quarter', null);
  const [picked, setPicked] = useState(null);       // null = 전부 선택
  // 세이빙 AI: 누구 관점으로 설명할지 (숫자는 같고 문장만 바뀐다) · 특약을 AI 가 채웠는지
  const [viewer, setViewer] = usePersistent('ss.viewer', 'owner', v => (v === 'tenant' ? 'tenant' : 'owner'));
  const [aiDraft, setAiDraft] = usePersistent('ss.aiDraft', false, v => v === true);

  const setRatio = useCallback(r => setRatioRaw(RATIO.snap(r)), [setRatioRaw]);
  const setRatioExact = useCallback(r => setRatioRaw(exact(r)), [setRatioRaw]);

  /* ── 건물 조회 ── */
  const [bld, setBld] = useState({ status: 'idle', data: null, error: null, fieldErrors: null });
  const [nonce, setNonce] = useState(0);             // 조회에 성공할 때마다 1씩 — 나머지가 다시 불러온다
  const codesRef = useRef(codes);
  codesRef.current = codes;
  const seq = useRef(0);
  const looked = useRef(false);

  const lookup = useCallback(async c => {
    const cc = c || codesRef.current;
    const fe = validateCodes(cc);
    if (fe) {
      setBld(s => ({ ...s, fieldErrors: fe }));
      return false;
    }
    const my = ++seq.current;
    setBld(s => ({ status: 'loading', data: s.data, error: null, fieldErrors: null }));
    try {
      const d = await fetchBuilding(cc);
      if (my !== seq.current) return false;
      looked.current = true;
      setPicked(null);
      setBld({ status: 'ok', data: d, error: null, fieldErrors: null });
      setNonce(n => n + 1);
      return true;
    } catch (e) {
      if (my === seq.current) setBld({ status: 'error', data: null, error: e, fieldErrors: null });
      return false;
    }
  }, []);

  const [booted, setBooted] = useState(false);
  useEffect(() => {
    let alive = true;
    boot().then(() => {
      if (!alive) return;
      setBooted(true);
      if (autoLookup) lookup();
    });
    return () => { alive = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // 서버 ↔ 저장된 시연 데이터 전환 시 처음부터 다시 불러온다
  const firstEpoch = useRef(true);
  useEffect(() => {
    if (firstEpoch.current) { firstEpoch.current = false; return; }
    if (looked.current || bld.status === 'error') lookup();
  }, [conn.epoch]); // eslint-disable-line react-hooks/exhaustive-deps

  const id = bld.data?.bld_id;
  const on = bld.status !== 'error' && id != null && nonce > 0;

  /* ── 건물별 자원 ── */
  const eligibility = useResource(['elig', nonce], () => fetchEligibility(id), { enabled: on });
  const profile = useResource(['profile', nonce], () => fetchProfile(id), { enabled: on });
  const pickedKey = picked ? picked.join(',') : 'ALL';
  const measures = useResource(['meas', nonce, pickedKey], () => fetchMeasures(id, picked), { enabled: on, keep: true });
  // 서버는 고른 대책만 돌려준다 → 전부 고른 상태의 목록을 기억해 두고, 끈 대책도 목록에 남겨 다시 켤 수 있게
  const allMeas = useRef(null);
  if (!picked && measures.data?.measures) allMeas.current = measures.data.measures;
  const baseline = useResource(['base', nonce], () => fetchBaseline(id), { enabled: on });

  const dInvest = useDebounced(invest, 250);
  const dRatio = useDebounced(ratio, 140);
  const dYears = useDebounced(years, 140);
  const allocation = useResource(['alloc', nonce, dInvest, dRatio, dYears],
    () => fetchAllocation({ bld_id: id, invest_won: dInvest, owner_ratio: dRatio, period_years: dYears }),
    { enabled: on, keep: true });

  const cases = useResource(['cases', nonce, id], () => fetchCases(id), { enabled: on });
  const caseItems = useMemo(() => (cases.data ? caseList(cases.data) : []), [cases.data]);
  useEffect(() => {
    if (caseItems.length && !caseItems.some(c => c.key === quarterKey)) setQuarterKey(caseItems[0].key);
  }, [caseItems]); // eslint-disable-line react-hooks/exhaustive-deps
  const qSel = caseItems.find(c => c.key === quarterKey) || null;

  const settlement = useResource(['setl', nonce, quarterKey, dRatio],
    () => fetchSettlement(id, qSel.y, qSel.q, dRatio), { enabled: on && !!qSel, keep: true });

  const target = settlement.status === 'ok' ? explainTarget(settlement.data) : null;
  const explain = useResource(['explain', nonce, quarterKey, target?.ym ?? null],
    () => fetchExplain(id, target.ym), { enabled: on && !!target });

  /* ── 가상 데이터 표시: 응답 어디서든 is_simulated 이면 상시 표시 ── */
  const sim = [bld.data?.data_origin, baseline.data?.data_origin, settlement.data?.provenance?.data_origin]
    .find(o => o && o.is_simulated) || null;

  /* ── 대책 고르기: 하나 이상은 남긴다 ── */
  const toggleMeasure = useCallback((mid, nextOn, allIds) => {
    const cur = picked ?? allIds;
    const next = nextOn ? [...new Set([...cur, mid])] : cur.filter(x => x !== mid);
    if (!next.length) return false;
    setPicked(allIds.filter(x => next.includes(x)));
    return true;
  }, [picked]);

  const resetDemoConditions = useCallback(() => {
    setInvest(BACKUP_INVEST);
    setYears(BACKUP_YEARS);
  }, [setInvest, setYears]);

  return {
    conn, booted,
    codes, setCodes, address, setAddress,
    bld, lookup, nonce, looked: looked.current,
    invest, setInvest, ratio, setRatio, setRatioExact, years, setYears,
    eligibility, profile, measures, baseline, allocation,
    cases, caseItems, quarterKey, setQuarterKey, qSel, settlement, explain, target,
    picked, toggleMeasure, resetDemoConditions, measureList: allMeas.current,
    sim, viewer, setViewer, aiDraft, setAiDraft,
  };
}
