/* ══════════════════════════════════════════════════════════════
   PC · 토스증권 짜임을 따른다.
   위 메뉴 → 유의 안내 띠 → 하얀 판 하나 → 아래 유의사항 줄, 오른쪽 AI 설명.
   홈이든 단계든 같은 판, 같은 제목 자리, 같은 줄 모양을 쓴다.
   ══════════════════════════════════════════════════════════════ */
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { cx, won, kwh, pct, ymTxt, firstSentence } from '../core/format.js';
import { hasAmount, fetchSettlement, fetchExplain } from '../core/domain.js';
import { useResource, usePersistent, useTheme } from '../core/hooks.js';
import { BuddyBody, BuddyFace, Badge, BrandMark, Button, ErrorBox, Icon, Row, Sheet, Skeleton, connInfo, monthBadge, statusText, usePulse } from './ui.jsx';
import { MiniBars, MiniChecks, MiniLines, MiniRange, MiniSplit, dataSpan } from './charts.jsx';
import {
  BasisRows, GROUPS, STEPS, ShellProvider, StepView, baselineFail, baselinePass, groupOf, pctRange, stepById, stepIndex, tidy,
} from './steps.jsx';
import { Picker, usePicker } from './entry.jsx';
import { useAssist } from './assistant/context.js';
import { Assistant } from './assistant/Assistant.jsx';
import { AskLink } from './assistant/Nudge.jsx';
import { chipOf, chipsFor, saveMe } from '../core/assist.js';
import { ViewSetting } from './viewMode.jsx';

const NAV = [{ id: 'home', name: '홈' }, ...GROUPS.filter(g => g.id !== 'sys').map(g => ({ id: g.id, name: g.name }))];
const HOME_TABS = [{ id: 'setl', name: '월별 절약 결과' }, { id: 'base', name: '원래 사용량 예측' }, { id: 'meas', name: '추천 공사' }];

function useLocal(key, init) {
  const [v, setV] = useState(() => {
    try { const r = localStorage.getItem(key); return r == null ? init : JSON.parse(r); } catch { return init; }
  });
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* 저장소 없음 */ } }, [key, v]);
  return [v, setV];
}

const quarterOf = ym => `${+ym.slice(0, 4)}-${Math.ceil(+ym.slice(4, 6) / 3)}`;

function phasesOf(rows) {
  const rs = (rows || []).filter(r => r?.ym).slice().sort((a, b) => (a.ym < b.ym ? -1 : 1));
  const out = [];
  for (const r of rs) {
    const l = out[out.length - 1];
    if (l && l.phase === r.phase) l.last = r.ym;
    else out.push({ phase: r.phase, first: r.ym, last: r.ym });
  }
  return out;
}

/* ── 위 메뉴 ── */
function Nav({ page, goPage, onSearch }) {
  return (
    <nav className="d-nav" aria-label="주 메뉴">
      <button type="button" className="brand" onClick={() => goPage('home')} aria-label="세이빙 셰어 홈">
        <BrandMark /><span className="brand-name">세이빙 셰어</span>
      </button>
      <div className="d-menu">
        {NAV.map(n => (
          <button key={n.id} type="button" aria-current={page === n.id ? 'page' : undefined} onClick={() => goPage(n.id)}>{n.name}</button>
        ))}
      </div>
      <button type="button" className="d-search" onClick={onSearch}>
        <Icon name="search" size={20} />
        <span><kbd>/</kbd> 를 눌러 건물을 찾으세요</span>
      </button>
    </nav>
  );
}

/* ── 유의 안내 띠 · 가장 오해하기 쉬운 것 하나만 ── */
function Notice({ onOpen, onClose }) {
  return (
    <div className="notice" role="note">
      <span className="notice-ic"><Icon name="megaphone" size={20} /></span>
      <b className="notice-t">공사 전 금액 유의 안내</b>
      <button type="button" className="notice-btn" onClick={onOpen}>계산 방식 보기</button>
      <button type="button" className="notice-x" aria-label="안내 닫기" onClick={onClose}><Icon name="close" size={18} /></button>
    </div>
  );
}

/* ── 판 맨 위 상태 줄 ── */
function PanelStatus({ S, onAbout }) {
  const c = connInfo(S.conn);
  const span = dataSpan(S.baseline.data?.monthly_baseline);
  return (
    <div className="p-status">
      {span && <span className="dot green"><i /><b>공공데이터</b> {ymTxt(span.last)}까지 반영</span>}
      <span className={cx('dot', c.tone)} role="status">
        <i />
        {S.conn.mode === 'backup' ? <><b>저장된 시연 데이터</b> · {S.conn.stampTime} 기준</> : <b>{c.text}</b>}
      </span>
      {c.action && <Button variant="weak" size="s" onClick={c.action.run}>{c.action.label}</Button>}
      {S.sim && <span className="p-sim" role="note"><b>가상 데이터 · 시연용</b><span>{S.sim.note || '실제 사용량이 아니에요'}</span></span>}
      <button type="button" className="ai-intro" onClick={onAbout}><Icon name="sparkle" size={16} />세이빙 셰어 AI 소개</button>
    </div>
  );
}

/* ── 홈 요약 칸 6개 · 단계마다 하나 ── */
function Tiles({ S, go }) {
  const el = S.eligibility.data, pr = S.profile.data, me = S.measures.data, ba = S.baseline.data, al = S.allocation.data, se = S.settlement.data;
  const last = pr?.years?.[pr.years.length - 1];
  const rr = me?.available ? me.total_saving_rate : null;
  const kk = me?.available ? me.total_saving_kwh : null;
  const recent = (ba?.monthly_baseline || []).slice(-24);
  const fail = baselineFail(ba), pass = baselinePass(ba);
  const pb = al?.payback_years;
  const has = se && hasAmount(se);
  // 칸에는 이름과 값만. 상태는 회색 글씨 대신 꼬리표로
  const SETL_SHORT = {
    ESTIMATED: ['amber', '예상 금액'], PROVISIONAL: ['blue', '잠정'], VERIFIED: ['green', '검증 완료'],
    REVIEW_REQUIRED: ['red', '정산 보류'], INSUFFICIENT_DATA: ['gray', '정산 불가'],
  };
  const sb = se && SETL_SHORT[se.status_code];
  const tiles = [
    { id: 'elig', k: '지원 대상', mini: <MiniChecks list={(el?.checks || []).map(c => c.ok)} />,
      v: el && (el.eligible ? `지원사업 ${el.programs?.length || 0}개` : '대상 아님') },
    { id: 'prof', k: last ? `${last.year}년 사용량` : '사용량', mini: <MiniBars values={(pr?.years || []).map(y => y.total)} />,
      v: last && `${kwh(last.total)} kWh` },
    { id: 'meas', k: '절감 가능', mini: <MiniRange lo={rr?.[0] ?? 0} hi={rr?.[1] ?? 0} />,
      v: rr && pctRange(rr[0], rr[1]), badge: kk && ['gray', '가정으로 계산한 값'] },
    { id: 'base', k: '원래 사용량 예측', mini: <MiniLines a={recent.map(r => r.actual)} b={recent.map(r => r.baseline)} />,
      v: ba && (fail ? '범위로 제시' : pass ? '기준 충족' : '판정 없음'), vTone: fail ? 'amber' : pass ? 'green' : null },
    { id: 'alloc', k: '공사비 회수', mini: <MiniSplit ratio={al?.owner_ratio ?? S.ratio} />,
      v: al && (Number.isFinite(pb) && pb < 99 ? `${pb}년` : '기간 안에 어려워요'), badge: al && (ba?.saving_basis?.actual_based ? ['blue', '공사 후 실측'] : ['amber', '예상 금액']) },
    { id: 'setl', k: se ? se.period : '분기 금액', mini: <MiniBars values={(se?.months || []).map(m => (m.saving_won == null ? NaN : m.saving_won))} />,
      v: se && (has ? `${won(se.saving_won)}원` : (se.amount_state || '금액 없음')), vTone: se && !has ? 'muted' : null, badge: sb },
  ];
  return (
    <div className="tiles">
      {tiles.map(t => (
        <button key={t.id} type="button" className="tile" onClick={() => go(t.id)} aria-label={`${t.k} ${t.v || ''} · ${stepById(t.id).name} 보기`}>
          <span className="tile-mini">{t.mini}</span>
          <span className="tile-t">
            <span className="tile-k">{t.k}</span>
            {t.v ? <span className={cx('tile-v num', t.vTone)}>{t.v}</span> : <span className="tile-sk" aria-hidden="true" />}
            {t.badge && <span className="tile-b"><Badge tone={t.badge[0]}>{t.badge[1]}</Badge></span>}
          </span>
        </button>
      ))}
    </div>
  );
}

/* ── 데이터 일정 · 지금 화면에 반영된 달까지 ── */
function Schedule({ S }) {
  const rows = S.baseline.data?.monthly_baseline;
  const span = dataSpan(rows);
  const ph = phasesOf(rows);
  return (
    <div className="sched">
      <p className="sched-h">데이터 일정</p>
      {span ? (
        <>
          <p className="sched-p">공공데이터는 공개까지 약 4개월 걸려서 지금은 {+span.last.slice(0, 4)}년 {+span.last.slice(4, 6)}월 사용량까지 반영돼요</p>
          <ul>
            {ph.map(b => (
              <li key={b.phase + b.first}><b className="num">{ymTxt(b.first)}~{ymTxt(b.last)}</b><span>{b.phase}{b.phase === '적용' ? ' · 공사 전' : b.phase === '이전' ? ' · 기저선에 안 씀' : ''}</span></li>
            ))}
          </ul>
        </>
      ) : S.baseline.status === 'error' ? <p className="sched-p">사용량 자료를 불러오지 못했어요</p> : <Skeleton lines={3} head={false} />}
    </div>
  );
}

/* ── 파란 안내 말풍선 · 처음 한 번만 ── */
function Coach({ box, sel, deps, onClose }) {
  const [pos, setPos] = useState(null);
  useLayoutEffect(() => {
    const place = () => {
      const b = box.current;
      const el = b?.querySelector(sel);
      if (!el) { setPos(null); return; }
      const br = b.getBoundingClientRect(), r = el.getBoundingClientRect();
      const x = r.left - br.left + r.width / 2;
      const left = Math.max(0, Math.min(x - 44, br.width - 400));
      setPos({ left, top: r.bottom - br.top + 24, pin: x - left });
    };
    place();
    const ro = new ResizeObserver(place);
    if (box.current) ro.observe(box.current);
    return () => ro.disconnect();
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  if (!pos) return null;
  return (
    <div className="coach" role="note" style={{ left: pos.left, top: pos.top }}>
      <span className="coach-pin" style={{ left: pos.pin }} aria-hidden="true" />
      <b>확정하지 않은 분기도 이유를 보여줘요</b>
      <p>‘2023 3분기 · 전체 보류’를 누르면 보류 이유를 AI가 쉬운 말로 알려줘요.</p>
      <button type="button" className="coach-x" aria-label="안내 닫기" onClick={onClose}><Icon name="close" size={16} stroke={2.4} /></button>
    </div>
  );
}

/* ── 홈 ── */
/* 처음 온 사람용 · 무엇을 어떤 순서로 보면 되는지 한 줄로 */
const GUIDE = [['bld', '건물 확인'], ['prof', '사용량 진단'], ['alloc', '나눌 비율 정하기'], ['setl', '정산 받기']];
function StartGuide({ go, onSearch, onClose }) {
  return (
    <div className="guide soft-in">
      <div className="guide-t">
        <b>처음이세요? 4단계로 보면 돼요</b>
        <span>단계를 누르면 그 화면으로 가요. 다른 건물은 주소로 찾을 수 있어요</span>
      </div>
      <ol className="guide-s">
        {GUIDE.map(([id, name], k) => (
          <li key={id}><button type="button" onClick={() => go(id)}><i className="num">{k + 1}</i>{name}</button></li>
        ))}
      </ol>
      <div className="guide-a">
        <Button size="s" onClick={() => go('bld')}>차례로 보기</Button>
        <Button size="s" variant="gray" onClick={onSearch}><Icon name="search" size={16} />주소로 찾기</Button>
        <button type="button" className="guide-x" aria-label="안내 닫기" onClick={onClose}><Icon name="close" size={16} /></button>
      </div>
    </div>
  );
}

/* 열자마자 보이는 한 장 · 이 건물에서 얼마를 아낄 수 있는지 + 어디부터 보면 되는지 */
function HomeHero({ S, go, onSearch }) {
  const se = S.settlement.data;
  const has = se && hasAmount(se);
  const st = se ? statusText(se.status_code) : null;
  const plain = !se ? '' : se.status_code === 'VERIFIED' ? '실제 사용량으로 확인한 금액이에요.'
    : se.status_code === 'PROVISIONAL' ? '실제 사용량으로 계산했지만, 아직 확정은 아니에요.'
    : se.status_code === 'ESTIMATED' ? '공사 전이라 실제로 아낀 금액이 아니라, 가정으로 계산한 예상이에요.'
    : '지금은 금액을 정할 수 없어요. 이유는 오른쪽에서 확인할 수 있어요.';
  const ratio = se?.owner_ratio ?? S.ratio;
  const STEP4 = [['bld', '건물이 맞는지 확인', '주소와 면적을 봐요'], ['prof', '얼마나 쓰는지 보기', '해마다 전기·가스 사용량'], ['alloc', '이익 나누는 비율 정하기', '건물주와 세입자 몫'], ['setl', '매달 절약 결과 보기', '정산 금액 확인']];
  return (
    <section className="hero" aria-label="한눈에 보기">
      <div>
        <p className="hero-k">{se ? se.period : '분기'} 절약 금액 {st && <Badge tone={st.tone} mark={st.mark}>{st.text}</Badge>}</p>
        {se ? (
          has
            ? <p className="hero-n num">{won(se.saving_won)}<small>원</small></p>
            : <p className="hero-n">{se.amount_state || '금액 없음'}</p>
        ) : <Skeleton lines={2} head={false} />}
        {se && <p className="hero-s">{plain}</p>}
        {se && has && Number.isFinite(ratio) && (
          <>
            <div className="hero-bar" aria-hidden="true"><i style={{ width: `${ratio * 100}%` }} /><i style={{ width: `${(1 - ratio) * 100}%` }} /></div>
            <div className="hero-who"><span>건물주 {Math.round(ratio * 100)}% <b className="num">{won(se.owner_won)}원</b></span><span>임차인 {Math.round((1 - ratio) * 100)}% <b className="num">{won(se.tenant_won)}원</b></span></div>
          </>
        )}
      </div>
      <div className="hero-go">
        <h2>처음이라면 이 순서로 보세요</h2>
        <div className="hero-steps">
          {STEP4.map(([id, t, d], k) => <button key={id} type="button" onClick={() => go(id)}><i className="num">{k + 1}</i><b>{t}<span>{d}</span></b></button>)}
        </div>
        <div className="hero-a">
          <Button size="m" onClick={() => go('bld')}>차례대로 시작하기</Button>
          <Button size="m" variant="gray" onClick={onSearch}><Icon name="search" size={16} />다른 건물</Button>
        </div>
      </div>
    </section>
  );
}

function Home({ S, go, onSearch, tab, setTab, focus }) {
  const [fold, setFold] = usePersistent('ss.v4.fold', false, v => v === true);
  const [coach, setCoach] = useLocal('ss.coach.v1', true);
  const [detail, setDetail] = useState(false);
  useEffect(() => { if (focus) setDetail(true); }, [focus]);
  const box = useRef(null);
  const seen = useRef(false);
  // 안내한 분기를 직접 누르면 다시 띄우지 않는다
  useEffect(() => {
    if (seen.current && S.quarterKey === '2023-3') setCoach(false);
    seen.current = true;
  }, [S.quarterKey]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="home" ref={box}>
      <HomeHero S={S} go={go} onSearch={onSearch} />
      <button type="button" className="more-btn" aria-expanded={detail} onClick={() => setDetail(d => !d)}>
        {detail ? '자세한 결과 접기' : '자세한 결과 펼치기'}<Icon name={detail ? 'up' : 'down'} size={18} />
      </button>
      {detail && (
        <div className="soft-in">
          {!fold && <div className="p-top"><Tiles S={S} go={go} /><Schedule S={S} /></div>}
          <div className="p-tabs" role="tablist" aria-label="홈 보기">
            {HOME_TABS.map(t => (
              <button key={t.id} type="button" role="tab" aria-selected={t.id === tab} onClick={() => setTab(t.id)}>{t.name}</button>
            ))}
            <button type="button" className="fold" aria-pressed={fold} onClick={() => setFold(f => !f)}>
              <Icon name="panel" size={18} />{fold ? '요약 펼치기' : '요약 접기'}
            </button>
          </div>
          <div key={tab} className="p-view soft-in"><StepView id={tab} S={S} /></div>
        </div>
      )}
      {false && detail && coach && tab === 'setl' && (
        <Coach box={box} sel={'[data-chip="2023-3"]'} deps={[S.caseItems.length, fold, tab, S.settlement.data?.period]} onClose={() => setCoach(false)} />
      )}
    </div>
  );
}

/* ── 단계 화면 · 묶음 탭 + 단계 + 다음 단추 ── */
function Category({ S, route, go, goPage, onSearch }) {
  const g = GROUPS.find(x => x.id === route.page) || GROUPS[0];
  const id = g.steps.includes(route.step) ? route.step : g.steps[0];
  const k = stepIndex(id);
  const next = STEPS[k + 1];
  const prev = STEPS[k - 1];
  return (
    <>
      <div className="p-prog" aria-label={`전체 ${STEPS.length}단계 중 ${k + 1}단계`}>
        <span className="num"><b>{k + 1}</b> / {STEPS.length}단계</span>
        <div className="p-prog-bar">
          {STEPS.map((s2, j) => (
            <button key={s2.id} type="button" title={`${j + 1}. ${s2.name}`} aria-label={`${j + 1}단계 ${s2.name}로 가기`}
              className={cx(j < k && 'done', j === k && 'cur')} onClick={() => go(s2.id)} />
          ))}
        </div>
      </div>
      <div className="p-tabs" role="tablist" aria-label={`${g.name} 단계`}>
        {g.steps.map(s => (
          <button key={s} type="button" role="tab" aria-selected={s === id} onClick={() => go(s)}>{stepById(s).name}</button>
        ))}
      </div>
      <div key={id} className="p-view soft-in"><StepView id={id} S={S} /></div>
      <div className="p-next">
        {prev
          ? <button type="button" className="p-prev" onClick={() => go(prev.id)}><Icon name="left" size={18} />{prev.name}</button>
          : <button type="button" className="p-prev" onClick={() => goPage('home')}><Icon name="left" size={18} />홈</button>}
        <span className="p-next-gap" />
        {id === 'bld' && <Button variant="gray" size="m" onClick={onSearch}>다른 건물</Button>}
        <Button size="m" disabled={id === 'bld' && !S.bld.data} onClick={() => (next ? go(next.id) : goPage('home'))}>
          {id === 'bld' ? '맞아요' : next ? `다음 · ${next.name}` : '처음으로'}
        </Button>
      </div>
    </>
  );
}

/* ── 오른쪽 · AI 설명 ── */
function useQuarters(S) {
  const id = S.bld.data?.bld_id;
  const keys = S.caseItems.map(c => c.key).join(',');
  return useResource(['qs', S.nonce, keys],
    () => Promise.all(S.caseItems.map(c => fetchSettlement(id, c.y, c.q, S.ratio).then(d => ({ ...c, d }), e => ({ ...c, err: e })))),
    { enabled: id != null && S.nonce > 0 && S.caseItems.length > 0 });
}

/* ── 오른쪽 · 고른 달 요약 ── 왼쪽 화면은 그대로 두고 여기서 짧게 (크게 보기를 눌러야만 이동) */
function MonthPeek({ S, peek, q, onClose, onBig, bigLabel }) {
  const a = useAssist();
  const id = S.bld.data?.bld_id;
  const ym = peek.ym;
  const m = q?.d?.months?.find(x => x.ym === ym);
  const an = (S.baseline.data?.anomalies || []).find(x => x.ym === ym);
  const ex = useResource(['ex', S.nonce, ym], () => fetchExplain(id, ym), { enabled: id != null && S.nonce > 0 });
  const [more, setMore] = useState(false);
  useEffect(() => setMore(false), [ym]);
  const mb = m && monthBadge(m.state, q.d.status_code);
  const text = ex.data?.text || '';
  const head = firstSentence(text);
  const rest = text.slice(head.length).trim();
  return (
    <section className="peek soft-in" key={ym} aria-label={`${ymTxt(ym)} 요약`}>
      <div className="peek-h">
        <span className="ds-ai-k"><Icon name="sparkle" size={16} />AI 요약</span>
        <button type="button" className="icon-btn" aria-label="요약 닫기" onClick={onClose}><Icon name="close" size={18} /></button>
      </div>
      <div className="peek-t">
        <b>{+ym.slice(0, 4)}년 {+ym.slice(4, 6)}월</b>
        {mb ? <Badge tone={mb.tone} mark={mb.mark}>{mb.text}</Badge> : an && <Badge tone="red" mark="hold">사용량 급증</Badge>}
      </div>
      <div className="rows lined peek-rows">
        {m && <Row k="금액" v={m.saving_won == null ? '금액 없음' : `${won(m.saving_won)}원`} strong />}
        {m?.actual_kwh != null && <Row k="실측 사용량" v={`${kwh(m.actual_kwh)} kWh`} />}
        {m?.baseline_kwh != null && <Row k="원래 사용량 예측" v={`${kwh(m.baseline_kwh)} kWh`} />}
        {!m && an && <Row k={`${an.fuel} 사용량`} v={`${kwh(an.actual)} kWh`} strong />}
        {!m && an && <Row k="과거 같은 달 평균" v={`${kwh(an.past_avg)} kWh · ${an.ratio}배`} />}
      </div>
      {m?.state === '확인 중' && m.note && ex.status === 'error' && <p className="peek-note">{tidy(m.note)}</p>}
      <div className="peek-ai">
        {ex.status === 'error' ? <p>설명을 불러오지 못했어요</p>
          : !ex.data ? <span className="tile-sk" />
          : <>
            <p>{head}{more && rest && <> {rest}</>}</p>
            {rest && <button type="button" className="peek-more" aria-expanded={more} onClick={() => setMore(v => !v)}>{more ? '접기' : '자세히'}</button>}
          </>}
      </div>
      <div className="peek-act">
        <button type="button" className="main" title={bigLabel} aria-label={bigLabel} onClick={onBig}>크게 보기<Icon name="right" size={16} /></button>
        {a && <button type="button" title="이 달을 세이빙 AI에게 더 묻기" onClick={() => a.ask(`${ym.slice(2, 4)}년 ${+ym.slice(4, 6)}월 사용량 분석해 줘`)}>더 묻기</button>}
      </div>
    </section>
  );
}

/* ── 오른쪽 · 지금 화면에서 물어볼 만한 것 (누르면 이 칸에서 대화가 열린다 · 왼쪽은 그대로) ──
   보고 있는 분기·이상 달을 넣어 묻는다 · 서버가 알아듣는 질문 모양만 쓴다 */
const TRUST_Q = '이 금액 믿어도 돼요?';
function suggestFor(step, S, top) {
  const per = S.settlement.data?.period;
  const odd = top && `${top.ym.slice(2, 4)}년 ${+top.ym.slice(4, 6)}월 ${top.fuel || '사용량'}${top.fuel ? '가' : '이'} 왜 튀었어?`;
  if (['prof', 'meas', 'base'].includes(step)) return [odd, TRUST_Q].filter(Boolean);
  if (step === 'setl') return [per && `${String(per).replace(/^(\d{4})\s*/, '$1년 ')} 정산해도 돼?`, TRUST_Q, odd].filter(Boolean);
  if (step === 'sys') return [TRUST_Q];
  return chipsFor(step);
}
function Suggest({ step, S, top, max = 3 }) {
  const a = useAssist();
  if (!a) return null;
  return (
    <div className="ds-sug" role="list" aria-label="이 화면에서 물어볼 만한 것">
      <p className="ds-sug-h">이 화면에서 물어볼 만한 것</p>
      {suggestFor(step, S, top).slice(0, max).map(c => {
        const x = chipOf(c);
        return (
          <button key={x.label} type="button" role="listitem" onClick={() => (x.message ? a.ask(x.message) : a.ask(x.fill, { send: false }))}>
            <Icon name="sparkle" size={14} /><span>{x.label}</span>
          </button>
        );
      })}
    </div>
  );
}

function AiPanel({ S, go, jump, setMonth, askAi, onHome, showReport, step }) {
  const assist = useAssist();
  // 새싹: 답을 기다리면 생각 중 · 고른 분기가 '검증 완료'면 만세
  const cheer0 = usePulse(S.settlement.data?.status_code === 'VERIFIED' ? S.quarterKey : null, 'cheer', 3200, true);
  const cheer1 = usePulse(assist?.cheerKey || null, 'cheer');
  const cheer = cheer1 || cheer0;
  const [peek, setPeek] = useState(null);   // { key, ym } · 이 칸에서만 요약해 보여주는 달
  const top = useMemo(() => (S.baseline.data?.anomalies || []).reduce((a, b) => (!a || b.ratio > a.ratio ? b : a), null), [S.baseline.data]);
  const id = S.bld.data?.bld_id;
  const ex = useResource(['ex', S.nonce, top?.ym ?? null], () => fetchExplain(id, top.ym), { enabled: !!top && id != null && S.nonce > 0 });
  const qs = useQuarters(S);
  const last = useMemo(() => {
    let r = null;
    (qs.data || []).forEach(q => (q.d?.months || []).forEach(m => { if (m.saving_won != null && (!r || m.ym > r.ym)) r = { key: q.key, ym: m.ym }; }));
    return r;
  }, [qs.data]);
  const lex = useResource(['lex', S.nonce, last?.ym ?? null], () => fetchExplain(id, last.ym), { enabled: !!last && id != null && S.nonce > 0 });
  const keys = new Set(S.caseItems.map(c => c.key));
  // 고르면 이 칸에서 요약만 · 왼쪽 화면은 건드리지 않는다
  const look = (key, ym) => setPeek({ key, ym });
  // 크게 보기 · 사용자가 누른 이동이라 이때만 왼쪽을 바꾼다
  const big = ({ key, ym }) => {
    if (!keys.has(key)) { jump('base'); return; }
    if (onHome) { jump(null, () => { showReport(key, ym); askAi(); }); return; }   // 홈이면 그 자리에서 왼쪽 정산 리포트를 바꾼다
    jump('setl', () => { S.setQuarterKey(key); setMonth(ym); askAi(); });
  };
  const bigLabel = p => (!keys.has(p.key) ? '원래 사용량 예측에서 크게 보기' : onHome ? '홈 리포트에서 크게 보기' : '정산 화면에서 크게 보기');
  return (
    <>
      <AskLink line send={false} className="ds-ask" />
      <div className="ds-head"><h2>AI 설명</h2></div>
      {peek ? (
        <MonthPeek S={S} peek={peek} q={(qs.data || []).find(x => x.key === peek.key)} onClose={() => setPeek(null)}
          onBig={() => big(peek)} bigLabel={bigLabel(peek)} />
      ) : (
        <>
          {last && (
            <div className="buddy">
              <button type="button" className="buddy-pic" onClick={() => look(last.key, last.ym)} aria-label={`${ymTxt(last.ym)} 요약 보기`}>
                <BuddyBody w={72} live mood={assist?.busy ? 'think' : cheer || 'idle'} />
              </button>
              <div className="buddy-b">
                <span className="ds-ai-k">세이빙 셰어 AI</span>
                <b>{+last.ym.slice(0, 4)}년 {+last.ym.slice(4, 6)}월 분석이 나왔어요</b>
                <p>{lex.data ? firstSentence(lex.data.text) : lex.status === 'error' ? '설명을 불러오지 못했어요' : <span className="tile-sk" />}</p>
              </div>
              <div className="buddy-act one">
                <button type="button" className="main" onClick={() => look(last.key, last.ym)}>{+last.ym.slice(4, 6)}월 요약 보기</button>
              </div>
            </div>
          )}
          {top && (
            <button type="button" className="ds-ai" onClick={() => look(quarterOf(top.ym), top.ym)}>
              <span className="ds-ai-k"><Icon name="sparkle" size={16} />눈여겨볼 달 · {ymTxt(top.ym)}</span>
              <span className="ds-ai-v">
                <span>{ex.data ? firstSentence(ex.data.text) : ex.status === 'error' ? '설명을 불러오지 못했어요' : <span className="tile-sk" />}</span>
                <Icon name="right" size={18} />
              </span>
            </button>
          )}
        </>
      )}
      <Suggest step={step} S={S} top={top} max={peek ? 2 : 3} />
    </>
  );
}

/* ── 오른쪽 · 내 건물 ── */
function BldPanel({ S, onSearch }) {
  const b = S.bld.data;
  const span = dataSpan(S.baseline.data?.monthly_baseline);
  return (
    <>
      <div className="ds-head"><h2>내 건물</h2></div>
      {!b ? <Skeleton lines={5} head={false} /> : (
        <div className="stack-20">
          <div className="bld-id"><b>{b.addr}</b></div>
          <div className="rows lined">
            <Row k="용도" v={b.purpose || '—'} />
            <Row k="연면적" v={`${Number(b.area).toLocaleString('ko-KR', { maximumFractionDigits: 2 })}㎡`} />
            <Row k="층수" v={b.floors || '—'} />
            <Row k="사용승인일" v={String(b.use_apr_day || '').replace(/(\d{4})(\d{2})(\d{2})/, '$1.$2.$3') || '—'} />
            <Row k="출처" v={b.data_origin ? <Badge tone={b.data_origin.is_simulated ? 'purple' : 'green'}>{b.data_origin.label}</Badge> : '출처 미표시'} />
            {span && <Row k="결측월" v={span.miss.length ? span.miss.map(ymTxt).join(' · ') : '없음'} />}
          </div>
          <Button variant="gray" block onClick={onSearch}>다른 건물 찾기</Button>
        </div>
      )}
    </>
  );
}

function Rail({ side, setSide, onSettings }) {
  const a = useAssist();
  const chatOn = !!a?.open;
  const [spinKey, setSpinKey] = useState(0);
  const [t, setT] = useTheme();
  const dark = t === 'dark' || (t === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches);
  return (
    <nav className="d-rail" aria-label="오른쪽 패널">
      <button type="button" className="rail-top" aria-label={side || chatOn ? '패널 접기' : '패널 펼치기'}
        onClick={() => { if (chatOn) { a.setOpen(false); setSide(null); } else setSide(s => (s ? null : 'ai')); }}>
        <Icon name={side || chatOn ? 'collapse' : 'expand'} size={20} />
      </button>
      {a && (
        <button type="button" className="rail-chat" data-rail="chat" aria-pressed={chatOn} onClick={() => { setSpinKey(k => k + 1); a.setOpen(!chatOn); }}>
          <span className="rail-ic face"><BuddyFace size={30} live spinKey={spinKey} /></span>세이빙 AI
        </button>
      )}
      <button type="button" data-rail="ai" aria-pressed={!chatOn && side === 'ai'} onClick={() => { a?.setOpen(false); setSide(s => (s === 'ai' && !chatOn ? null : 'ai')); }}>
        <span className="rail-ic"><Icon name="sparkle" size={18} /></span>AI 설명
      </button>
      <button type="button" aria-pressed={!chatOn && side === 'bld'} onClick={() => { a?.setOpen(false); setSide(s => (s === 'bld' && !chatOn ? null : 'bld')); }}>
        <span className="rail-ic"><Icon name="building" size={18} /></span>내 건물
      </button>
      <span className="rail-gap" />
      <button type="button" aria-haspopup="dialog" onClick={onSettings}>
        <span className="rail-ic"><Icon name="sliders" size={18} /></span>설정
      </button>
      <button type="button" className="rail-top" aria-label={dark ? '밝은 화면으로' : '어두운 화면으로'} onClick={() => setT(dark ? 'light' : 'dark')}>
        <Icon name={dark ? 'sun' : 'moon'} size={20} />
      </button>
    </nav>
  );
}

/* ── 아래 유의사항 줄 ── */
function Ticker({ S, onNotes }) {
  const al = S.allocation.data, ba = S.baseline.data;
  const m = ba?.metrics || {}, mc = ba?.metric_checks || {};
  const ok = k => (mc[k]?.ok ? <em className="green">기준 충족</em> : mc[k]?.ok === false ? <em className="amber">범위 제시</em> : null);
  return (
    <footer className="d-ticker">
      <button type="button" onClick={onNotes}>예상 금액 유의사항</button>
      {al && <span className="tk"><span>연간 절감액</span><b className="num">{won(al.annual_saving_won)}원</b>{ba?.saving_basis?.actual_based ? <em className="blue">공사 후 실측</em> : <em className="amber">예상 금액</em>}</span>}
      {al && Number.isFinite(al.payback_years) && <span className="tk"><span>공사비 회수</span><b className="num">{al.payback_years}년</b></span>}
      {ba && <span className="tk"><span>예측이 빗나간 정도</span><b className="num">{m.cv_rmse}%</b>{ok('cv_rmse')}</span>}
      {ba && <span className="tk"><span>예측이 맞는 정도</span><b className="num">{m.r2}</b>{ok('r2')}</span>}
    </footer>
  );
}

/* ── 시트 ── */
function BasisSheet({ open, onClose, S }) {
  const sb = S.allocation.data?.saving_basis || S.baseline.data?.saving_basis;
  return (
    <Sheet open={open} onClose={onClose} title="공사 전 금액 유의 안내" footer={<Button block onClick={onClose}>확인했어요</Button>}>
      <p className="sheet-lead">공사 전에는 실제 절감량이 없어요. 화면의 금액은 아래 가정으로 계산한 예상치예요.</p>
      {sb ? <BasisRows sb={sb} /> : <Skeleton lines={4} head={false} />}
    </Sheet>
  );
}

function SettingsSheet({ open, onClose }) {
  return (
    <Sheet open={open} onClose={onClose} title="설정">
      <ViewSetting pc />
    </Sheet>
  );
}

function NotesSheet({ open, onClose, S }) {
  const sb = S.allocation.data?.saving_basis || S.baseline.data?.saving_basis;
  const ba = S.baseline.data;
  const pr = S.profile.data;
  const span = dataSpan(ba?.monthly_baseline);
  const ann = (pr?.years || []).filter(y => y.annualized);
  const items = [
    ['amber', 'sim', '예상 금액', '공사 전 금액은 가정값으로 계산한 예상치예요'],
    sb && ['amber', null, '가정값', `절감률 ${pct(sb.saving_rate)} · 전기 ${won(sb.prices?.elec?.won_per_kwh)}원/kWh · 가스 ${won(sb.prices?.gas?.won_per_kwh)}원/kWh`],
    ba && baselineFail(ba) && ['amber', 'prov', '범위로 제시', `예측 오차 ${ba.metrics?.cv_rmse}% · 설명력 ${ba.metrics?.r2} — 확정 기준(오차 15% 이하 · 설명력 0.75 이상)을 모두 채우지 못해 금액을 확정하지 않고 90% 범위와 함께 보여드려요`],
    ['gray', null, '가정으로 계산한 값', '절감률과 배출계수를 확인하기 전이에요'],
    span && span.miss.length > 0 && ['gray', null, '결측', `${span.miss.map(ymTxt).join(', ')}은 사용량 자료가 없어요`],
    ann.length > 0 && ['gray', null, '연환산', `${ann.map(y => y.year).join(', ')}년은 ${ann[0].months}개월 자료를 12개월로 환산했어요`],
    ['gray', 'none', '데이터 없음', '사용량은 공개까지 약 4개월 걸려요'],
  ].filter(Boolean);
  return (
    <Sheet open={open} onClose={onClose} title="예상 금액 유의사항" footer={<Button block onClick={onClose}>확인했어요</Button>}>
      <ul className="notes">
        {items.map(([tone, mark, k, v]) => (
          <li key={k}><Badge tone={tone} mark={mark || undefined}>{k}</Badge><span>{v}</span></li>
        ))}
      </ul>
    </Sheet>
  );
}

function SearchSheet({ open, onClose, S, onFound }) {
  const a = useAssist();
  const p = usePicker(S);
  const busy = S.bld.status === 'loading';
  const run = async () => {
    if (await p.run()) {
      if (p.tab === 'addr' && p.sel) saveMe({ address: p.sel.addr, codes: p.sel.codes, bld_id: p.sel.bld_id });
      onClose(); onFound();
    }
  };
  return (
    <Sheet open={open} onClose={onClose} title="건물 찾기"
      footer={<Button block loading={busy} onClick={run}>조회하기</Button>}>
      <Picker S={S} tab={p.tab} setTab={p.setTab} onEnter={run} p={p} onAsk={() => { onClose(); a?.ask(); }} />
      {S.bld.status === 'error' && <ErrorBox error={S.bld.error} notFound="건물을 찾지 못했어요" />}
    </Sheet>
  );
}

/* 처음 들어왔을 때 한 번 · 세이빙 AI 버튼 옆에 반투명 안내 → 누르면 세이빙 AI 대화를 연다 */
function PcTip({ onOpen }) {
  const [show, setShow] = useState(false);
  const seen = () => { try { return sessionStorage.getItem('ss.tip.ai') === '1'; } catch { return false; } };
  const mark = () => { try { sessionStorage.setItem('ss.tip.ai', '1'); } catch { /* 무시 */ } };
  useEffect(() => {
    if (seen()) return undefined;
    const t1 = setTimeout(() => setShow(true), 1200);
    const t2 = setTimeout(() => { setShow(false); mark(); }, 10200);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);
  const [top, setTop] = useState(128);
  useLayoutEffect(() => {
    if (!show) return;
    const r = document.querySelector('.d-rail [data-rail="chat"] .rail-ic')?.getBoundingClientRect();
    if (r) setTop(Math.max(12, r.top + r.height / 2 - 34));
  }, [show]);
  if (!show) return null;
  const close = () => { setShow(false); mark(); };
  return (
    <div className="ai-tip pc" role="status" style={{ top }}>
      <button type="button" className="ai-tip-main" onClick={() => { close(); onOpen(); }}>
        <BuddyFace size={44} live />
        <span className="ai-tip-b"><b>세이빙 AI에게 물어보세요</b><span>"건물주 몫 몇 %가 좋아?"처럼 물으면 화면의 숫자로 답해 드려요</span></span>
      </button>
      <button type="button" className="ai-tip-x" aria-label="닫기" onClick={close}><Icon name="close" size={16} /></button>
    </div>
  );
}

/* 오른쪽 패널 폭 · 경계선을 잡고 옆으로 끌면 넓어지고 좁아진다 (두 번 누르면 처음 폭) */
function Splitter({ w, setW }) {
  const start = e => {
    e.preventDefault();
    const x0 = e.clientX, w0 = w || e.currentTarget.nextElementSibling?.getBoundingClientRect().width || 380;
    const max = Math.min(760, window.innerWidth - 640);
    const move = ev => setW(Math.round(Math.max(320, Math.min(max, w0 + (x0 - ev.clientX)))));
    const up = () => { document.removeEventListener('pointermove', move); document.removeEventListener('pointerup', up); document.body.classList.remove('resizing'); };
    document.body.classList.add('resizing');
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', up);
  };
  return (
    <div className="d-split" role="separator" aria-orientation="vertical" aria-label="패널 폭 조절 (옆으로 끌기)"
      onPointerDown={start} onDoubleClick={() => setW(null)}><span /></div>
  );
}

/* ══ PC 전체 ══ */
export function DesktopApp({ S }) {
  const a = useAssist();
  const [route, setRoute] = usePersistent('ss.v4.pc', { page: 'home', step: null },
    v => (v && typeof v.page === 'string' && (v.page === 'home' || GROUPS.some(g => g.id === v.page)) ? v : { page: 'home', step: null }));
  const [side, setSide] = useState(() => (window.innerWidth >= 1440 ? 'ai' : null));
  const [sheet, setSheet] = useState(null);
  const [month, setMonth] = useState(null);
  const [htab, setHtab] = usePersistent('ss.v4.htab', 'setl', v => (HOME_TABS.some(t => t.id === v) ? v : 'setl'));
  const [focus, setFocus] = useState(null);   // 오른쪽에서 고른 달 → 왼쪽 정산 리포트가 그 행으로 스크롤
  const showReport = (key, ym) => { S.setQuarterKey(key); setMonth(ym); setHtab('setl'); setFocus({ ym, n: Date.now() }); };
  const [aiReq, setAiReq] = useState(0);
  const askAi = () => setAiReq(n => n + 1);
  const [notice, setNotice] = useLocal('ss.notice.v1', true);
  const [sideW, setSideW] = useLocal('ss.side.w2', null);

  /* 왼쪽 화면이 바뀌는 모든 이동(메뉴·탭·이전/다음·바로가기·AI 쪽 이동 버튼)은 지나온 자리를 쌓는다
     → 「○○ 화면으로 돌아가기」로 한 칸씩 되돌아간다 (브라우저 뒤로가기처럼, 이 탭에서만 기억) */
  const [hist, setHist] = usePersistent('ss.v4.pc.hist', [],
    v => (Array.isArray(v) ? v.filter(h => h && h.route && typeof h.route.page === 'string').slice(-20) : []));
  const sid = r => (r.page === 'home' ? 'home' : r.step || GROUPS.find(g => g.id === r.page)?.steps[0]);   // 같은 화면인지
  const here = () => ({ route, y: document.querySelector('.d-main')?.scrollTop || 0 });
  const remember = () => setHist(h => [...h, here()].slice(-20));
  const moveTo = next => {
    if (sid(next) !== sid(route)) remember();
    setRoute(next);
    document.querySelector('.d-main')?.scrollTo(0, 0);
  };
  const goStep = id => {
    const g = groupOf(id);
    if (g) moveTo({ page: g.id, step: id });
  };
  const goPage = page => moveTo({ page, step: null });
  // 같은 화면 안에서 자리만 옮기는 것(홈 리포트로 내려가기 등)도 돌아올 수 있게
  const jump = (id, after) => {
    if (id) goStep(id); else remember();
    after?.();
  };
  const back = hist[hist.length - 1] || null;
  const goBack = () => {
    if (!back) return;
    setHist(h => h.slice(0, -1));
    setRoute(back.route);
    setTimeout(() => document.querySelector('.d-main')?.scrollTo(0, back.y), 80);
  };
  // 화면 제목과 같은 이름 (묶음만 골랐으면 그 묶음의 첫 단계)
  const routeName = r => (sid(r) === 'home' ? '홈' : stepById(sid(r))?.name || '이전');

  // 세이빙 AI 가 화면을 옮길 때 · 오른쪽 대화는 그대로 두고 판만 바꾼다 (이동 버튼을 누른 것만 · 돌아가기 가능)
  useEffect(() => { a?.bindNav(goStep, route.step || route.page, false, true); }); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const k = e => {
      const t = e.target;
      const typing = t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
      if (e.key === '/' && !typing && !sheet) { e.preventDefault(); setSheet('search'); }
    };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [sheet]);

  return (
    <ShellProvider value={{ device: 'pc', month, setMonth, go: goStep, aiReq, focus }}>
      <div className={cx('pc d-shell', !side && !a?.open && 'closed')}>
        <div className="d-main">
          <Nav page={route.page} goPage={goPage} onSearch={() => setSheet('search')} />
          {notice && <div className="d-notice-row"><Notice onOpen={() => setSheet('basis')} onClose={() => setNotice(false)} /></div>}
          <div className="d-page">
            {back && (
              <div className="d-back soft-in" role="navigation" aria-label="돌아가기">
                <button type="button" className="d-back-go" onClick={goBack}><Icon name="left" size={18} />
                  {sid(back.route) === sid(route) ? '보던 자리로 돌아가기' : `${routeName(back.route)} 화면으로 돌아가기`}
                </button>
                <button type="button" className="icon-btn" aria-label="돌아가기 닫기" onClick={() => setHist([])}><Icon name="close" size={16} /></button>
              </div>
            )}
            <section className="panel" aria-label={route.page === 'home' ? '홈' : undefined}>
              <PanelStatus S={S} onAbout={() => goStep('sys')} />
              {route.page === 'home'
                ? <Home S={S} go={goStep} onSearch={() => setSheet('search')} tab={htab} setTab={setHtab} focus={focus} />
                : <Category S={S} route={route} go={goStep} goPage={goPage} onSearch={() => setSheet('search')} />}
            </section>
          </div>
          {route.page !== 'home' && <Ticker S={S} onNotes={() => setSheet('notes')} />}
        </div>
        {(a?.open || side) && <Splitter w={sideW} setW={setSideW} />}
        {a?.open ? (
          <aside className="d-side chat" aria-label="세이빙 AI" style={sideW ? { width: sideW } : undefined}>
            <Assistant S={S} variant="panel" step={route.step || (route.page === 'home' ? 'bld' : route.page)} onClose={() => a.setOpen(false)} />
          </aside>
        ) : side && (
          <aside className="d-side" aria-label={side === 'ai' ? 'AI 설명' : '내 건물'} style={sideW ? { width: sideW } : undefined}>
            {side === 'ai'
              ? <AiPanel S={S} go={goStep} jump={jump} setMonth={setMonth} askAi={askAi} onHome={route.page === 'home'} showReport={showReport}
                  step={route.step || (route.page === 'home' ? 'bld' : GROUPS.find(g => g.id === route.page)?.steps[0])} />
              : <BldPanel S={S} onSearch={() => setSheet('search')} />}
          </aside>
        )}
        <Rail side={side} setSide={setSide} onSettings={() => setSheet('settings')} />
        <PcTip onOpen={() => a?.setOpen(true)} />
        <BasisSheet open={sheet === 'basis'} onClose={() => setSheet(null)} S={S} />
        <SettingsSheet open={sheet === 'settings'} onClose={() => setSheet(null)} />
        <NotesSheet open={sheet === 'notes'} onClose={() => setSheet(null)} S={S} />
        <SearchSheet open={sheet === 'search'} onClose={() => setSheet(null)} S={S} onFound={() => goStep('bld')} />
      </div>
    </ShellProvider>
  );
}
