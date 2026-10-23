/* 처음 화면 · 로그인 화면 짜임. 건물을 고르고, 필수 안내 두 가지를 확인하고 시작한다.
   직접 고르기 싫은 사람은 아래 "세이빙 AI와 대화로 시작하기"로 말로 한다. */
import { useEffect, useRef, useState } from 'react';
import { SAMPLE, SAMPLES, CODE_FIELDS } from '../core/domain.js';
import { cx } from '../core/format.js';
import { useTheme } from '../core/hooks.js';
import { callResolve, clearMe, getMe, maskPII, saveMe } from '../core/assist.js';
import { agreeVoice, speechOk, useSpeech, voiceAgreed, VOICE_TOAST } from '../core/useSpeech.js';
import { Badge, BrandMark, Button, Check, CodeFields, ErrorBox, BigTextBtn, Icon, LineField, Seg2, Sheet, connInfo } from './ui.jsx';
import { useAssist } from './assistant/context.js';
import { Assistant } from './assistant/Assistant.jsx';
import { AskNudge, useStruggle } from './assistant/Nudge.jsx';
import { Thinking } from './assistant/Thinking.jsx';

export const sameCodes = (a, b) => CODE_FIELDS.every(f => String(a?.[f.key] ?? '') === String(b?.[f.key] ?? ''));

/* 건물 고르기 · 시연 건물 · 주소로 찾기 · 건축물대장 코드 */
export function usePicker(S) {
  const [tab, setTab] = useState(() => (getMe() ? 'addr' : SAMPLES.some(x => sameCodes(S.codes, x.codes)) ? 'sample' : 'code'));
  const [si, setSi] = useState(() => Math.max(0, SAMPLES.findIndex(x => sameCodes(S.codes, x.codes))));   // 시연 건물 중 고른 것
  const [sel, setSel] = useState(() => { const m = getMe(); return m ? { addr: m.address, codes: m.codes, bld_id: m.bld_id } : null; });   // 주소로 고른 건물
  const [miss, setMiss] = useState(false);        // 주소 탭에서 고르지 않고 시작을 눌렀다
  const run = () => {
    if (tab === 'sample') {
      const x = SAMPLES[si] || SAMPLE;
      S.setCodes(x.codes);
      S.setAddress(x.address);
      return S.lookup(x.codes);
    }
    if (tab === 'addr') {
      if (!sel) { setMiss(true); return Promise.resolve(false); }
      S.setCodes(sel.codes);
      S.setAddress(sel.addr);
      return S.lookup(sel.codes);
    }
    return S.lookup();
  };
  return { tab, setTab: t => { setMiss(false); setTab(t); }, run, sel, setSel: c => { setMiss(false); setSel(c); }, miss, si, setSi };
}

/* 주소·건물 이름으로 찾기 (요구서 3-2) — 칸 하나. 입력을 멈추면 바로 아래에 결과 한 줄, 누르면 끝.
   찾은 건물은 묻지 않고 이 기기에만 기억한다(서버로 보내지 않음) → 다음에 '최근' 한 줄로 */
function AddrFind({ S, p }) {
  const a = useAssist();
  const [q, setQ] = useState('');
  const [r, setR] = useState({ status: 'idle', data: null, error: null });
  const [me, setMe] = useState(() => getMe());
  const seq = useRef(0);
  const find = async raw => {
    const text = maskPII(String(raw ?? '').trim()).text;
    if (text.length < 2) { setR({ status: 'idle', data: null, error: null }); return; }
    const my = ++seq.current;
    setR(x => ({ status: 'loading', data: x.data, error: null }));
    try {
      const d = await callResolve(text);
      if (my === seq.current) setR({ status: 'ok', data: d, error: null });
    } catch (e) { if (my === seq.current) setR({ status: 'error', data: null, error: e }); }
  };
  useEffect(() => {
    const h = setTimeout(() => find(q), 450);
    return () => clearTimeout(h);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps
  const sp = useSpeech(t => setQ(t));
  const mic = () => {
    if (!voiceAgreed()) { agreeVoice(); a?.showToast({ text: VOICE_TOAST }); }
    sp.toggle();
  };
  const d = r.data;
  const c = d?.result === 'matched' ? d.candidates?.[0] : null;
  const on = x => p.sel && sameCodes(p.sel.codes, x.codes);
  const row = (x, k, extra) => (
    <button key={k} type="button" role="radio" aria-checked={!!on(x)} className="addr-row" onClick={() => p.setSel(on(x) ? null : x)}>
      <span className="pick-dot" aria-hidden="true" />
      <span className="addr-t"><b>{x.addr}</b>{x.sub && <span>{x.sub}</span>}</span>
      {extra}
    </button>
  );
  const MSG = { unregistered: '아직 데이터가 없는 건물이에요', residential: '주택은 공공 에너지데이터 제공 대상이 아니에요', not_found: '예: 강남구 ○○동 761-26 · 양평 블룸비스타 호텔' };
  return (
    <div className="addr">
      <div className="addr-field">
        <LineField label="주소나 건물 이름" value={sp.on ? sp.interim : q} readOnly={sp.on}
          onChange={v => { setQ(v); sp.clearError(); }} onKeyDown={e => { if (e.key === 'Enter') find(q); }} enterKeyHint="search" />
        <span className="addr-tool">
          {r.status === 'loading' ? <i className="dots" aria-label="찾는 중"><i /><i /><i /></i>
            : speechOk && <button type="button" className={cx('addr-mic', sp.on && 'on')} aria-label={sp.on ? '음성 입력 멈추기' : '음성으로 입력'} aria-pressed={sp.on} onClick={mic}><Icon name="mic" size={20} /></button>}
        </span>
      </div>
      <div className="addr-list" role="radiogroup" aria-label="찾은 건물">
        {!q.trim() && me && row({ addr: me.address, codes: me.codes, bld_id: me.bld_id, sub: '최근' }, 'me',
          <span role="button" tabIndex={0} className="addr-del" aria-label="최근 건물 지우기"
            onClick={e => { e.stopPropagation(); clearMe(); setMe(null); if (p.sel && sameCodes(p.sel.codes, me.codes)) p.setSel(null); }}
            onKeyDown={e => { if (e.key === 'Enter') { e.stopPropagation(); clearMe(); setMe(null); } }}>
            <Icon name="close" size={16} stroke={2.4} />
          </span>)}
        {q.trim() && c && row({ ...c, sub: c.purpose }, 'c', c.data_origin?.is_simulated ? <Badge tone="purple">가상 데이터</Badge> : null)}
        {q.trim() && d && !c && r.status !== 'loading' && <p className="addr-msg">{MSG[d.result] || d.message}</p>}
        {r.status === 'error' && <p className="addr-msg red">찾지 못했어요. 잠시 후 다시 해 주세요</p>}
        {sp.error && <p className="addr-msg red" role="alert">{sp.error}</p>}
        {p.miss && !p.sel && <p className="addr-msg red">건물을 눌러 골라 주세요</p>}
      </div>
    </div>
  );
}

export function Picker({ S, tab, setTab, onEnter, p, onAsk }) {
  const a = useAssist();
  const stuck = tab === 'code' && (S.bld.fieldErrors || S.bld.status === 'error');
  const [show, , close, force] = useStruggle('code', 99);
  useEffect(() => { if (stuck) force(); }, [stuck]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="picker">
      <Seg2 label="건물 찾는 방법" value={tab} onChange={setTab}
        options={[{ value: 'sample', label: '시연 건물' }, { value: 'addr', label: '주소로 찾기' }, { value: 'code', label: '코드로 찾기' }]} />
      <div className="picker-body" key={tab}>
        {tab === 'sample' ? (
          <div className="picks" role="radiogroup" aria-label="시연 건물">
            {SAMPLES.map((x, i) => (
              <button type="button" key={x.address} className={cx('pick', p.si === i ? 'on' : 'off')} role="radio" aria-checked={p.si === i}
                onClick={() => p.setSi(i)}>
                <span className="pick-dot" aria-hidden="true" />
                <span className="pick-txt">
                  <span className="pick-name">{x.address}</span>
                  <Badge tone={x.badge[0]}>{x.badge[1]}</Badge>
                </span>
              </button>
            ))}
          </div>
        ) : tab === 'addr' ? (
          <AddrFind S={S} p={p} />
        ) : (
          <CodeFields codes={S.codes} setCodes={S.setCodes} errors={S.bld.fieldErrors} onEnter={onEnter} />
        )}
      </div>
      {stuck && show && a && (
        <AskNudge className="soft-in" title="코드를 몰라도 괜찮아요" text="주소나 건물 이름으로도 찾을 수 있어요" onClose={close}
          actions={[
            { label: '주소로 찾기', main: true, onClick: () => { close(); setTab('addr'); } },
            { label: 'AI에게 말하기', onClick: () => { close(); (onAsk || (() => a.ask()))(); } },
          ]} />
      )}
    </div>
  );
}

export function ConnChip({ S }) {
  const c = connInfo(S.conn);
  return (
    <span className="conn-chip-wrap">
      <span className={cx('conn-chip', c.tone)} role="status"><i />{c.text}</span>
      {c.action && <Button variant="weak" size="s" onClick={c.action.run}>{c.action.label}</Button>}
    </span>
  );
}

export function ThemeBtn({ className }) {
  const [t, setT] = useTheme();
  const dark = t === 'dark' || (t === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches);
  return (
    <button type="button" className={cx('icon-btn', className)} aria-label={dark ? '밝은 화면으로' : '어두운 화면으로'} onClick={() => setT(dark ? 'light' : 'dark')}>
      <Icon name={dark ? 'sun' : 'moon'} size={20} />
    </button>
  );
}

/* 들어가기 전 · 실제로 불러오는 것을 차례로 보여준다 (토스식 진행 화면, 최소 시간) */
const LOADS = [['eligibility', '지원사업 대상 확인'], ['profile', '사용량 불러오기'], ['baseline', '원래 사용량 예측'], ['allocation', '이익 나누기 준비']];
function Opening({ S, onDone }) {
  const [t0] = useState(() => performance.now());
  const [now, setNow] = useState(t0);
  useEffect(() => { const i = setInterval(() => setNow(performance.now()), 120); return () => clearInterval(i); }, []);
  const MIN = 3200;
  // 단계는 실제 응답이 와야 체크된다 + 단계마다 최소 간격
  const per = MIN / LOADS.length;
  let done = 0;
  for (let i = 0; i < LOADS.length; i++) {
    const r = S[LOADS[i][0]];
    const ok = r.status === 'ok' || r.status === 'error';
    if (ok && now - t0 >= per * (i + 1)) done = i + 1; else break;
  }
  const left = useRef(false);
  const leave = () => { if (!left.current) { left.current = true; onDone(); } };
  useEffect(() => {
    if (done < LOADS.length) return undefined;
    const t = setTimeout(leave, 420);
    return () => clearTimeout(t);
  }, [done]); // eslint-disable-line react-hooks/exhaustive-deps
  // 오래 걸려도 6.5초 뒤엔 들어간다 (늦은 자원은 화면에서 마저 불러온다)
  useEffect(() => { const t = setTimeout(leave, 6500); return () => clearTimeout(t); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="opening" role="dialog" aria-modal="true" aria-label="건물 불러오는 중">
      <div className="opening-in">
        <Thinking size="l" from="building" to="sparkle"
          title={done < LOADS.length ? `${S.bld.data?.addr || '건물'} 데이터를 살펴보고 있어요` : '다 준비됐어요'}
          steps={LOADS.map(x => x[1])} done={done} />
      </div>
    </div>
  );
}

export function Entry({ S, onDone, pc }) {
  const a = useAssist();
  const p = usePicker(S);
  const [agree, setAgree] = useState({ sim: false, lag: false });
  const [info, setInfo] = useState(null);
  const [nudgeAgree, setNudgeAgree] = useState(false);
  const [opening, setOpening] = useState(null);     // 들어갈 단계 · 진행 화면을 띄우는 동안
  const all = agree.sim && agree.lag;
  const busy = S.bld.status === 'loading';
  const open = at => setOpening(at || 'bld');
  const go = async () => {
    if (!all) { setNudgeAgree(true); return; }
    if (busy) return;
    if (await p.run()) {
      if (p.tab === 'addr' && p.sel) saveMe({ address: p.sel.addr, codes: p.sel.codes, bld_id: p.sel.bld_id });
      open();
    }
  };

  // 대화 중 화면 이동(예: '이 조건으로 보기')은 건물이 열린 뒤에만
  useEffect(() => {
    a?.bindNav((id, opt) => {
      if (!S.bld.data && !opt?.opened) {
        a.push({ role: 'ai', text: '먼저 건물을 골라 주세요.', res: null });
        return;
      }
      a.setOpen(!!pc);
      onDone(id);
    }, null, false);
  }, [S.bld.data, pc]); // eslint-disable-line react-hooks/exhaustive-deps

  if (opening) return <Opening S={S} onDone={() => { a?.setOpen(!!pc && a.msgs.length > 0); onDone(opening); }} />;

  const chat = a?.open;
  return (
    <div className={cx('entry', chat && 'chat')}>
      <header className="entry-top">
        <span className="brand"><BrandMark /><span className="brand-name">세이빙 셰어</span></span>
        <span className="entry-top-r"><ConnChip S={S} /><BigTextBtn /><ThemeBtn /></span>
      </header>
      {chat ? (
        <main className="entry-chat soft-in">
          <Assistant S={S} variant="page" entry onBack={() => a.setOpen(false)}
            onEnter={() => open('bld')} />
        </main>
      ) : (
        <main className="entry-in">
          <h1 className="entry-t">어떤 건물을 확인할까요?</h1>
          <div className="entry-card">
            <Picker S={S} tab={p.tab} setTab={p.setTab} onEnter={go} p={p} />
            {S.bld.status === 'error' && <ErrorBox error={S.bld.error} notFound="건물을 찾지 못했어요" />}
            <div className={cx('agree', nudgeAgree && !all && 'need')}>
              <Check strong checked={all} onChange={v => setAgree({ sim: v, lag: v })}>필수 안내 모두 확인</Check>
              <div className="agree-items">
                <Check checked={agree.sim} onChange={v => setAgree(x => ({ ...x, sim: v }))}
                  onMore={() => setInfo('sim')} moreLabel="공사 전 금액 안내 보기">공사 전 금액은 예상이에요</Check>
                <Check checked={agree.lag} onChange={v => setAgree(x => ({ ...x, lag: v }))}
                  onMore={() => setInfo('lag')} moreLabel="공공데이터 공개 시기 보기">공공데이터는 공개까지 약 4개월 걸려요</Check>
              </div>
            </div>
            <div className="entry-cta">
              <Button block disabled={!all || !S.booted} loading={busy} onClick={go}>시작하기</Button>
              {a && <button type="button" className="entry-alt" onClick={() => a.ask()}><Icon name="sparkle" size={14} />말로 할래요</button>}
            </div>
          </div>
          <p className="entry-foot">세이브 브릿지 · 제6회 그린리모델링 챌린지 대학생 해커톤</p>
        </main>
      )}

      <Sheet open={info === 'sim'} onClose={() => setInfo(null)} title="공사 전 금액은 예상이에요"
        footer={<Button block onClick={() => { setAgree(x => ({ ...x, sim: true })); setInfo(null); }}>확인했어요</Button>}>
        <p>공사 전에는 실제 절감량이 없어요.</p>
        <p>화면의 금액은 가정한 절감률과 단가로 계산한 예상치예요. 실제 정산액은 공사 후 실측 사용량으로 다시 계산해요.</p>
      </Sheet>
      <Sheet open={info === 'lag'} onClose={() => setInfo(null)} title="공공데이터는 공개까지 약 4개월 걸려요"
        footer={<Button block onClick={() => { setAgree(x => ({ ...x, lag: true })); setInfo(null); }}>확인했어요</Button>}>
        <p>건물에너지 사용량은 공개까지 약 4개월이 걸려요.</p>
        <p>아직 공개되지 않은 달은 ‘데이터 없음 · 정산 불가’로 보여드려요.</p>
      </Sheet>
    </div>
  );
}
