/* ══════════════════════════════════════════════════════════════
   단계 9개.
   화면마다 답 한 문장, 핵심 그림 하나, 그 자리에서 하는 조작 하나.
   덧붙이는 설명은 (i) 나 ▼ 안에 넣는다.
   숫자와 문장은 전부 서버 응답에서 온다.
   ══════════════════════════════════════════════════════════════ */
import { createContext, useContext, useEffect, useId, useRef, useState } from 'react';
import { cx, won, kwh, pct, pct1, ymTxt, periodTxt, dateTxt, koMoney, manwon, manRange } from '../core/format.js';
import { hasAmount, explainTarget, fetchExplain } from '../core/domain.js';
import { useResource } from '../core/hooks.js';
import { BACKUP_INVEST, BACKUP_YEARS } from '../core/client.js';
import { INVEST, PROPERTY, YEARS, RATIO } from '../core/useSavingShare.js';
import {
  ActionBadge, AmountField, Badge, Button, Check, Chips, ErrorBox, Fold, Icon, Info, Note, Num, Res, Row, Sheet,
  Skeleton, StatusBadge, Stepper, Switch, errorHead, monthBadge, BuddyFace, BuddyBody } from './ui.jsx';
import { BaselineChart, LineLegend, ShareBar, YearBars, dataSpan } from './charts.jsx';
import { useAssist } from './assistant/context.js';
import { AskLink, AskNudge, useStruggle } from './assistant/Nudge.jsx';
import { Thinking, usePaced } from './assistant/Thinking.jsx';

/* ── 단계와 묶음 ── */
export const STEPS = [
  { id: 'bld', n: 1, name: '건물 확인' },
  { id: 'elig', n: 2, name: '지원 대상 확인' },
  { id: 'prof', n: 3, name: '건물 현황' },
  { id: 'meas', n: 4, name: '추천 공사' },
  { id: 'base', n: 5, name: '원래 사용량 예측' },
  { id: 'alloc', n: 6, name: '이득 확인' },
  { id: 'draft', n: 7, name: '계약서 문구' },
  { id: 'sys', n: 8, name: '결론 정리' },
];
export const GROUPS = [
  { id: 'bld', name: '건물', steps: ['bld', 'elig'] },
  { id: 'diag', name: '진단', steps: ['prof', 'meas', 'base'] },
  { id: 'alloc', name: '이득', steps: ['alloc'] },
  { id: 'setl', name: '계약', steps: ['draft'] },
  { id: 'sys', name: '결론', steps: ['sys'] },
];
export const stepIndex = id => STEPS.findIndex(s => s.id === id);
export const stepById = id => STEPS[stepIndex(id)];
export const groupOf = id => GROUPS.find(g => g.steps.includes(id));

/* 화면 틀이 단계에 넘겨주는 것: 기기, 고른 달, 단계 이동 */
const ShellCtx = createContext({ device: 'm', month: null, setMonth: () => {}, go: () => {}, focus: null });
export const ShellProvider = ShellCtx.Provider;
export const useShell = () => useContext(ShellCtx);

/* 서버 문장 속 줄표는 가운뎃점으로 바꾸고, 가운뎃점 앞뒤에서 줄이 갈리지 않게 한다 */
const WJ = '⁠';
export const tidy = s => String(s ?? '').replace(/\s*—\s*/g, ' · ').replace(/(\S)([·−])(\S)/g, `$1${WJ}$2${WJ}$3`);
export const pctRange = (a, b) => `${Math.round(a * 100)}~${Math.round(b * 100)}%`;
const sqm = n => `${Number(n).toLocaleString('ko-KR', { maximumFractionDigits: 2 })}㎡`;
const tco2 = kg => (kg / 1000).toFixed(1);
export const baselineFail = d => !!d && (d.metric_checks?.cv_rmse?.ok === false || d.metric_checks?.r2?.ok === false);
export const baselinePass = d => !!d && d.metric_checks?.cv_rmse?.ok === true && d.metric_checks?.r2?.ok === true;

/* ══ 단계 화면의 짜임 ══
   lead   제목 위 조작 (분기 고르기)
   eyebrow · title · meta   상태 꼬리표, 답 한 문장, 보조 꼬리표
   main   핵심 그림이나 목록
   side   PC 오른쪽 회색 칸 · 모바일은 main 아래 (fold 면 ▼ 로 접음, hide 면 숨김)
   more   ▼ 로 여는 근거                                            */
export function StepLayout({ lead, eyebrow, title, meta, head, main, side, sideTitle, sideInfo, sideMode = 'show', more }) {
  const { device } = useShell();
  const m = device === 'm';
  const showSide = side != null && side !== false && !(m && sideMode === 'hide');
  const fold = m && sideMode === 'fold';
  return (
    <article className="step">
      {lead && <div className="step-lead">{lead}</div>}
      <div className={cx('step-body', !showSide && 'solo')}>
        <div className="step-l">
          <header className="step-head">
            {head || (
              <>
                {eyebrow && <div className="step-eye">{eyebrow}</div>}
                <h1 className="step-t">{title}</h1>
                {meta && <div className="step-meta">{meta}</div>}
              </>
            )}
          </header>
          {main && <div className="step-main">{main}</div>}
          {more && <div className="step-more">{more}</div>}
        </div>
        {showSide && (fold
          ? <div className="step-side folded"><Fold title={sideTitle}>{side}</Fold></div>
          : (
            <aside className="step-side">
              {sideTitle && <h2 className="side-t">{sideTitle}{sideInfo && <Info>{sideInfo}</Info>}</h2>}
              {side}
            </aside>
          ))}
      </div>
    </article>
  );
}

function StepPending({ r, lead, notFound }) {
  if (r.status === 'error') {
    return <StepLayout lead={lead} title={errorHead(r.error, notFound)} main={<ErrorBox bare error={r.error} onRetry={r.reload} />} />;
  }
  return (
    <StepLayout lead={lead}
      head={<div className="sk sk-head" aria-hidden="true"><i className="h" /><i className="h2" /></div>}
      main={<Skeleton lines={5} head={false} />} />
  );
}

/* ══ ① 조회 ══ */
function BldView({ S }) {
  const { bld } = S;
  if (bld.status === 'error') {
    return <StepPending r={{ status: 'error', error: bld.error, reload: () => S.lookup() }} notFound="건물을 찾지 못했어요" />;
  }
  const b = bld.data;
  if (!b) return <StepPending r={{ status: 'loading' }} />;
  const o = b.data_origin;
  const span = dataSpan(S.baseline.data?.monthly_baseline);
  return (
    <StepLayout title="이 건물이 맞나요?"
      main={
        <div className="stack-20">
          {b.matched === false && <Note tone="amber" icon="alert">입력한 주소가 등록되지 않아 샘플 건물을 표시합니다</Note>}
          <div className="bld-id"><b>{b.addr}</b></div>
          <div className="rows lined">
            <Row k="용도" v={b.purpose || '—'} />
            <Row k="연면적" v={sqm(b.area)} />
            <Row k="층수" v={b.floors || '—'} />
            <Row k="구조" v={b.struct || '—'} />
            <Row k="사용승인일" v={dateTxt(b.use_apr_day)} />
          </div>
        </div>
      }
      sideTitle="사용량 자료" sideMode="fold"
      side={
        <div className="rows lined">
          <Row k="출처" v={o ? <Badge tone={o.is_simulated ? 'purple' : 'green'}>{o.label}</Badge> : '출처 미표시'} />
          {span && <Row k="기간" v={`${ymTxt(span.first)} ~ ${ymTxt(span.last)}`} />}
          {span && <Row k="결측월" v={span.miss.length ? span.miss.map(ymTxt).join(' · ') : '없음'} />}
        </div>
      } />
  );
}

/* ══ ② 대상 판정 ══ */
function EligView({ S }) {
  const r = S.eligibility;
  if (!r.data) return <StepPending r={r} />;
  const d = r.data;
  const programs = Array.isArray(d.programs) ? d.programs : [];
  const title = d.eligible
    ? (programs.length ? `지원사업 ${programs.length}개를 신청할 수 있어요` : '세이빙 셰어 대상 건물이에요')
    : '지원 대상이 아니에요';
  return (
    <StepLayout title={title}
      meta={programs.length > 0 && <div className="badges">{programs.map(p => <Badge key={p} tone="blue" lg>{p}</Badge>)}</div>}
      main={
        <div className="folds">
          {(d.checks || []).map((c, i) => (
            <Fold key={i} title={
              <span className="chk">
                <span className={cx('chk-ic', c.ok ? 'ok' : 'no')}><Icon name={c.ok ? 'check-fill' : 'x-fill'} size={22} /></span>
                <span>{tidy(c.name)}<span className="sr">{c.ok ? ' 충족' : ' 미충족'}</span></span>
              </span>
            }>
              <p><b>{c.program}</b> · {tidy(c.detail)}</p>
            </Fold>
          ))}
        </div>
      } />
  );
}

/* ══ ③ 건축물 진단 ══ */
function ProfView({ S }) {
  const r = S.profile;
  if (!r.data) return <StepPending r={r} />;
  const d = r.data;
  const ys = d.years || [];
  const last = ys[ys.length - 1];
  const un = d.unverified || [];
  return (
    <StepLayout title={last ? `${last.year}년에 ${kwh(last.total)} kWh를 썼어요` : '연도별 사용량'}
      meta={S.benefit.data?.available && (
        <span className="prof-cost num">1년 요금 약 {manwon(S.benefit.data.current.total_won)} 원 · 전기 {manwon(S.benefit.data.current.elec_won)} · 가스 {manwon(S.benefit.data.current.gas_won)}</span>
      )}
      main={
        <>
          <YearBars years={ys} />
          {(d.findings || []).length > 0 && (
            <div className="folds mt-24">
              {d.findings.map((f, i) => (
                <Fold key={i} title={tidy(f.title)}>
                  <p>{tidy(f.detail)}</p>
                  {f.implication && <p>{tidy(f.implication)}</p>}
                  {f.action && <p className="act">확인할 것 · {tidy(f.action)}</p>}
                </Fold>
              ))}
            </div>
          )}
        </>
      }
      sideTitle={un.length ? `현장에서 확인할 것 ${un.length}가지` : null} sideInfo={d.note ? tidy(d.note) : null} sideMode="fold"
      side={un.length ? <div className="rows lined">{un.map(u => <Row key={u.item} k={u.item} v={u.how} />)}</div> : null} />
  );
}

/* ══ ④ 개선 대책 ══ */
function Warn({ list }) {
  if (!list?.length) return null;
  const items = list.map(w => {
    const i = String(w).indexOf(':');
    return i > 0 ? [w.slice(0, i).trim(), w.slice(i + 1).trim()] : [String(w), ''];
  });
  return (
    <div className="warn" role="note">
      <Icon name="alert" size={18} />
      <ul>{items.map(([k, v]) => <li key={k}><b>{k}</b>{v && <Info label={`${k} 자세히`}>{tidy(v)}</Info>}</li>)}</ul>
    </div>
  );
}

/* 공사별 세입자 영향 · 계산값이 아닌 일반 안내 (현장마다 다름) */
const TENANT_IMPACT = {
  window: { stay: '나가지 않아도 돼요 · 방을 나눠 진행', noise: '보통 · 창틀 뜯을 때', note: '교체하는 동안 그 방은 냉난방이 안 돼요' },
  envelope: { stay: '나가지 않아도 돼요 · 바깥 비계 작업', noise: '보통~많음 · 소음·분진', note: '비계·가림막이 창과 출입구를 가릴 수 있어요' },
  boiler: { stay: '나가지 않아도 돼요 · 하루면 끝나요', noise: '적음', note: '바꾸는 날은 난방·온수가 잠깐 멈춰요' },
  led: { stay: '나가지 않아도 돼요 · 하루면 끝나요', noise: '적음', note: '천장 작업하는 자리만 잠깐 비워 주면 돼요' },
  solar: { stay: '나가지 않아도 돼요 · 지붕 작업', noise: '보통 · 설치하는 날', note: '지붕 방향·그늘에 따라 발전량이 달라져요' },
};
/* m: 서버가 준 대책 한 줄 (공사 기간·집 비우는 기간은 서버 값) */
function Impact({ m }) {
  const t = TENANT_IMPACT[m.id];
  if (!t) return null;
  return (
    <div className="imp">
      <p className="imp-h">세입자에게는</p>
      <dl>
        <div><dt>사는 채로 공사</dt><dd>{m.vacate_days ? `집을 비워야 해요 · 약 ${m.vacate_days}일` : t.stay}</dd></div>
        <div><dt>소음·분진</dt><dd>{t.noise}</dd></div>
        <div><dt>공사 기간</dt><dd>{m.days ? `약 ${m.days}일` : '—'}</dd></div>
        <div><dt>주의</dt><dd>{t.note}</dd></div>
      </dl>
      <p className="imp-s">일반적인 경우예요 · 현장마다 달라요</p>
    </div>
  );
}

const priceOpen = p => Object.values(p || {}).some(x => x && x.verified === false);

function MeasView({ S }) {
  const r = S.measures;
  if (!r.data) return <StepPending r={r} />;
  const d = r.data;
  if (!d.available) return <StepLayout title="개선 대책을 계산할 수 없어요" main={d.reason ? <p className="t-b">{tidy(d.reason)}</p> : null} />;
  const live = S.conn.mode !== 'backup';
  const list = S.measureList || d.measures;   // 끈 대책도 남아 있는 전체 목록
  const all = list.map(m => m.id);
  const sel = S.picked ?? all;
  const [klo, khi] = d.total_saving_kwh;
  const [rlo, rhi] = d.total_saving_rate || [];
  const [nlo, nhi] = d.naive_sum_kwh;
  const [olo, ohi] = d.overlap_adjust_kwh;
  const [clo, chi] = d.total_co2_kg;
  const labels = [...new Set(list.map(m => m.basis_label || '가정값'))];
  const missAll = list.every(m => m.source_missing);
  const uniform = labels.length === 1 && (missAll || list.every(m => !m.source_missing));
  const efOpen = Object.values(d.emission_factors || {}).some(f => f && f.verified === false);
  return (
    <StepLayout eyebrow={<Badge tone="amber" lg mark="sim">예상치</Badge>}
      title={rlo != null ? `에너지 사용량을 ${pctRange(rlo, rhi)} 줄일 수 있어요` : `연 ${kwh(klo)}~${kwh(khi)} kWh를 줄일 수 있어요`}
      main={
        <div className={cx('stack-16', r.stale && 'stale')}>
          <Warn list={d.warnings} />
          <div>
            {uniform && (
              <div className="ms-tags">
                <span>{list.length}개 모두</span>
                <Badge>{labels[0]}</Badge>
                {missAll && <Badge tone="red">출처 확인 중</Badge>}
              </div>
            )}
            <ul className="ms-list">
              {list.map(m => {
                const on = sel.includes(m.id);
                const rr = m.rate_range || [];
                return (
                  <li key={m.id} className={cx('ms', !on && 'off')}>
                    <div className="ms-main">
                      <span className="ms-n">
                        {m.name}
                        <Info label={`${m.name} 자세히`}>
                          <p>{tidy(m.addresses)}{rr.length === 2 ? ` · 절감률 ${pctRange(rr[0], rr[1])}` : ''}</p>
                          {m.survey_note && <p>{tidy(m.survey_note)}</p>}
                          <Impact m={m} />
                        </Info>
                      </span>
                      <span className="ms-v num">
                        연 {kwh(m.saving_kwh_low)}~{kwh(m.saving_kwh_high)} kWh
                        {m.saving_won_low != null && <b className="ms-won"> · {manRange(m.saving_won_low, m.saving_won_high)}</b>}
                        {m.days != null && <span className="ms-sch"> · 공사 {m.days}일{m.vacate_days ? ` · 집 비우기 ${m.vacate_days}일` : ''}</span>}
                      </span>
                      {!uniform && (
                        <span className="badges">
                          <Badge>{m.basis_label || '가정값'}</Badge>
                          {m.source_missing && <Badge tone="red">출처 확인 중</Badge>}
                        </span>
                      )}
                    </div>
                    {live && <Switch checked={on} label={`${m.name} 포함`} onChange={v => S.toggleMeasure(m.id, v, all)} />}
                  </li>
                );
              })}
            </ul>
          </div>
        </div>
      }
      sideTitle="합계"
      side={
        <div className={cx('rows lined', r.stale && 'stale')}>
          <Row k="대책별 단순 합" v={`${kwh(nlo)}~${kwh(nhi)} kWh`} />
          <Row k={<>겹치는 만큼 빼기{d.method && <Info>{tidy(d.method)}</Info>}</>} v={`${kwh(olo)}~${kwh(ohi)} kWh`} />
          <Row k="절감 합계" v={`${kwh(klo)}~${kwh(khi)} kWh`} strong />
          {d.total_saving_won && <Row k={<>1년에 아끼는 돈{priceOpen(d.prices) && <Info>주택용 단가는 출처를 확인하는 중이에요</Info>}</>}
            v={manRange(...d.total_saving_won)} strong />}
          {d.schedule && <Row k={<>공사 일정<Info>{tidy(d.schedule.note)}</Info></>}
            v={`약 ${d.schedule.total_days}일${d.schedule.vacate_days ? ` · 집 비우기 ${d.schedule.vacate_days}일` : ''}`} />}
          <Row k={<>온실가스 감축{efOpen && <Info>배출계수를 아직 확인하지 않아 추정값이에요</Info>}</>}
            v={<span className="v-tag">{tco2(clo)}~{tco2(chi)} tCO₂e{efOpen && <Badge>예상치</Badge>}</span>} />
        </div>
      } />
  );
}

/* ══ ⑤ 기저선 추정 ══ */
const limitTxt = (lim, unit = '') => {
  if (String(lim ?? '').startsWith('±')) return `${lim}${unit} 이내`;
  const m = /([≤≥<>]=?)\s*(-?[\d.]+)/.exec(String(lim ?? ''));
  if (!m) return lim || '';
  return `${+m[2]}${unit} ${m[1].startsWith('≤') || m[1].startsWith('<') ? '이하' : '이상'}`;
};
function Metric({ k, tech, v, chk, unit }) {
  return (
    <div className="metric">
      <span className="metric-k">{k}<Info ask={{ q: '이 예측 믿어도 돼요?', label: '이 예측 믿어도 되는지 묻기' }}>
        <p>{tech}</p>
        <p>{chk ? `기준 ${limitTxt(chk.limit, unit)}` : '기준 정보 없음'}</p>
      </Info></span>
      <span className="metric-v">
        <span className="num">{v}</span>
        {chk && <Badge tone={chk.ok ? 'green' : 'amber'}>{chk.ok ? '충족' : '범위 제시'}</Badge>}
      </span>
    </div>
  );
}
function BaseView({ S }) {
  const r = S.baseline;
  if (!r.data) return <StepPending r={r} />;
  const d = r.data;
  const m = d.metrics || {}, mc = d.metric_checks || {}, w = d.eval_window || {};
  const fail = baselineFail(d), pass = baselinePass(d);
  const by = w.valid_months ? ` · 검증 ${w.valid_months}개월로 계산` : '';
  return (
    <StepLayout
      eyebrow={<>
        <Badge tone={fail ? 'amber' : pass ? 'green' : 'gray'} lg mark={fail ? 'prov' : pass ? 'fix' : 'unknown'}>{fail ? '범위로 제시' : pass ? '기준 충족' : '판정 없음'}</Badge>
        {!pass && <Info ask={{ q: '이 예측 믿어도 돼요?', label: '이 예측 믿어도 되는지 묻기' }}>{fail ? `확정 기준(오차 15% 이하 · 설명력 0.75 이상)을 모두 채우지 못해서, 금액을 한 숫자로 확정하지 않고 90%${WJ}범위와 함께 보여드려요. 근거가 부족할 때 확정하지 않는 것도 세이빙 셰어의 규칙이에요` : '판정 정보가 없으면 금액을 확정하지 않아요'}</Info>}
      </>}
      title={fail ? '금액은 범위로 보여드려요' : pass ? '예측이 기준을 충족했어요' : '예측 판정 정보가 없어요'}
      main={<><LineLegend /><BaselineChart rows={d.monthly_baseline} anomalies={d.anomalies} /></>}
      sideTitle="예측 지표"
      side={
        <div className="stack-16">
          <div className="metrics">
            <Metric k="예측이 빗나간 정도" tech={`CV(RMSE)${by}`} v={`${m.cv_rmse}%`} chk={mc.cv_rmse} unit="%" />
            {mc.nmbe && <Metric k="한쪽으로 치우친 정도" tech={`NMBE${by} · ASHRAE Guideline 14 월별 기준 ±5%`} v={`${m.nmbe}%`} chk={mc.nmbe} unit="%" />}
            <Metric k="예측이 들어맞는 정도" tech={`R²${by}`} v={m.r2} chk={mc.r2} />
          </div>
          <div className="rows lined">
            <Row k="학습 구간" v={`${periodTxt(w.train)} · ${w.train_used_months ?? w.train_months}개월`} />
            {w.train_excluded?.length > 0 && <Row k="학습에서 뺀 달" v={`이상 감지 ${w.train_excluded.length}개월`} />}
            <Row k="검증 구간" v={`${periodTxt(w.valid)} · ${w.valid_months}개월`} />
          </div>
          {fail && <AskLink title="범위로 보여주는 이유가 궁금해요" q="이 예측 믿어도 돼요?" />}
        </div>
      } />
  );
}

/* ══ 계산 근거 (saving_basis) ══ */
export function BasisRows({ sb }) {
  if (!sb) return <p>응답에 산정 근거가 없어요.</p>;
  const pr = sb.prices || {};
  const tag = on => (on ? <Badge tone="amber">가정값</Badge> : <Badge tone="green">확인값</Badge>);
  const price = p => (p ? <span className="v-tag">{won(p.won_per_kwh)}{p.unit || '원/kWh'}{tag(p.is_assumption)}</span> : '—');
  return (
    <div className="basis">
      {sb.formula && <p className="basis-f">{tidy(sb.formula)}</p>}
      <div className="rows lined">
        <Row k="사용량 기간" v={periodTxt(sb.period)} />
        <Row k="전기분" v={`${won(sb.elec_saving_won)}원`} sub={`전기 사용량 ${kwh(sb.annual_elec_kwh)} kWh 기준`} />
        <Row k="가스분" v={`${won(sb.gas_saving_won)}원`} sub={`가스 사용량 ${kwh(sb.annual_gas_kwh)} kWh 기준`} />
        {sb.actual_based
          ? <Row k="계산 방식" v={<span className="v-tag">기저선 − 실측<Badge tone="blue">공사 후</Badge></span>} sub={sb.note} />
          : <Row k="절감률" v={<span className="v-tag">{pct(sb.saving_rate)}{tag(sb.is_assumption)}</span>} sub="그린리모델링 이자지원 신청 최소 요건(성능개선 20% 이상)" />}
        <Row k="전기 단가" v={price(pr.elec)} sub={pr.elec?.source} />
        <Row k="가스 단가" v={price(pr.gas)} sub={pr.gas?.source} />
      </div>
    </div>
  );
}

/* ══ ⑥ 분배 (예전 화면 · 지금은 이득 확인으로 바뀜) ══ */
function ConditionSheet({ open, onClose, S }) {
  const [inv, setInv] = useState(S.invest);
  const [yrs, setYrs] = useState(S.years);
  useEffect(() => { if (open) { setInv(S.invest); setYrs(S.years); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Sheet open={open} onClose={onClose} title="공사비와 분배 기간"
      footer={<Button block disabled={inv == null} onClick={() => { S.setInvest(inv); S.setYears(yrs); S.setAiDraft(false); onClose(); }}>적용하기</Button>}>
      {open && (
        <div className="stack-16">
          <AmountField label="공사비" value={S.invest} min={INVEST.min} max={INVEST.max} onChange={setInv} />
          <Stepper label="분배 기간" value={yrs} min={YEARS.min} max={YEARS.max} unit="년" onChange={setYrs} />
          <AskLink title="말로 정할래요" send={false} before={onClose}
            q={`공사비 ${koMoney(S.invest).replace(/원$/, '')} 원, ${S.years}년 안에 회수하고 싶어요`} />
        </div>
      )}
    </Sheet>
  );
}

/* 회수선 자석 — 회수선 ±2.5%p 안으로 오면 회수선에 딱 붙는다.
   저장된 시연 데이터는 5% 칸만 있어서 회수선 바로 위 칸에 붙인다. */
const MAGNET = 2.5;
export function RatioControl({ S, need, onSettle }) {
  const id = useId();
  const span = RATIO.max - RATIO.min;
  const v = S.ratio * 100;
  const f = (S.ratio - RATIO.min) / span;
  const needF = Number.isFinite(need) ? Math.min(1, Math.max(0, (need - RATIO.min) / span)) : null;
  const backup = S.conn.mode === 'backup';
  const line = needF == null ? null : backup ? Math.min(95, Math.ceil((need * 100) / 5 - 1e-9) * 5) : +(need * 100).toFixed(1);
  const snapped = line != null && Math.abs(v - line) < 0.05;
  const was = useRef(snapped);
  useEffect(() => {
    if (snapped && !was.current) { try { navigator.vibrate?.(8); } catch { /* 진동 없음 */ } }
    was.current = snapped;
  }, [snapped]);
  const put = p => {
    let r = Math.round(p / 5) * 5;
    if (line != null && Math.abs(p - line) <= MAGNET) r = line;
    S.setRatioExact(Math.min(95, Math.max(5, r)) / 100);
    if (S.aiDraft) S.setAiDraft(false);           // 직접 바꾸면 더는 'AI가 정리한 문안'이 아니다
  };
  // 화살표는 5% 칸씩 · 사이에 회수선이 있으면 거기서 한 번 멈춘다
  const key = e => {
    const d = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[e.key];
    if (!d) return;
    e.preventDefault();
    let nx = d > 0 ? Math.floor(v / 5 + 1e-9) * 5 + 5 : Math.ceil(v / 5 - 1e-9) * 5 - 5;
    if (line != null && (d > 0 ? line > v + 0.01 && line < nx : line < v - 0.01 && line > nx)) nx = line;
    S.setRatioExact(Math.min(95, Math.max(5, nx)) / 100);
    onSettle?.();
  };
  const at = t => `calc(14px + (100% - 28px) * ${t})`;
  return (
    <div className={cx('ratio', snapped && 'snapped')}>
      <label htmlFor={id} className="sr">건물주 몫</label>
      <div className="ratio-pair">
        <span className="ratio-o"><span className="ratio-k"><i />건물주</span><b className="num">{pct1(S.ratio)}</b></span>
        <span className="ratio-t"><span className="ratio-k"><i />임차인</span><b className="num">{pct1(1 - S.ratio)}</b></span>
      </div>
      <div className="slider-wrap" style={{ '--p': at(f) }}>
        <input id={id} className="slider" type="range" min={RATIO.min * 100} max={RATIO.max * 100} step={0.5}
          value={v} onChange={e => put(Number(e.target.value))} onKeyDown={key}
          onPointerUp={() => onSettle?.()}
          aria-valuetext={`건물주 ${pct1(S.ratio)}, 임차인 ${pct1(1 - S.ratio)}${snapped ? ', 회수선에 맞춤' : ''}`} />
        {needF != null && <span className="need" style={{ left: at(needF) }} aria-hidden="true" />}
      </div>
      <div className="slider-scale">
        <span>{pct(RATIO.min)}</span>
        {needF != null && <span className="need-l" style={{ left: at(needF) }}>{snapped && <Icon name="check" size={12} stroke={3} />}돌려받는 선 <b>{pct1(need)}</b></span>}
        <span>{pct(RATIO.max)}</span>
      </div>
    </div>
  );
}

function AllocView({ S }) {
  const ai = useAssist();
  const [stuck, bump, unstuck] = useStruggle('alloc', 4, 25000);
  const sayIt = `공사비 ${koMoney(S.invest).replace(/원$/, '')} 원, ${S.years}년 안에 회수하고 싶어요`;
  const a = S.allocation;
  const d = a.data;
  const backup = S.conn.mode === 'backup';
  const [sheet, setSheet] = useState(false);
  useEffect(() => {
    if (backup && (S.invest !== BACKUP_INVEST || S.years !== BACKUP_YEARS)) S.resetDemoConditions();
  }, [backup]); // eslint-disable-line react-hooks/exhaustive-deps
  const pb = d?.payback_years;
  const pbOk = Number.isFinite(pb) && pb < 99;
  const backTo = a.error?.code === 'BACKUP_COND'
    ? <Button variant="gray" size="m" onClick={S.resetDemoConditions}>시연 조건으로 되돌리기</Button> : null;
  return (
    <StepLayout eyebrow={S.baseline.data?.saving_basis?.actual_based
        ? <Badge tone="blue" lg mark="prov">공사 후 실측 기반</Badge>
        : <Badge tone="amber" lg mark="sim">예상 금액</Badge>}
      title="건물주 몫을 얼마로 할까요?"
      main={
        <div className="stack-24">
          <RatioControl S={S} need={d?.required_owner_ratio} onSettle={bump} />
          <Res r={a} lines={3} extra={backTo}>
            {x => (
              <div className="outs">
                <div className="out">
                  <span className="out-k">건물주가 공사비를 돌려받는 기간<Info ask={{ q: sayIt, label: '목표 기간에 맞는 몫 물어보기' }}>
                    <p>건물주 몫으로 공사비를 모두 돌려받는 데 걸리는 기간이에요.</p>
                    <p>{x.period_years}년 동안 공사비의 {pct(x.recovery_rate)}를 돌려받아요.</p>
                  </Info></span>
                  <span className="out-v num">{pbOk ? <><Num value={pb} format={v => v.toFixed(1)} />년</> : '기간 안에 어려워요'}</span>
                </div>
                <div className="out">
                  <span className="out-k">임차인 매달 절감<Info ask={{ q: '세입자 입장은?', label: '세입자 입장으로 설명 듣기' }}>임차인 몫 연 {won(x.tenant_annual_won)}원을 12개월로 나눈 금액이에요.</Info></span>
                  <span className="out-v num"><Num value={x.tenant_monthly_won} />원</span>
                </div>
              </div>
            )}
          </Res>
          {stuck && ai && (
            <AskNudge className="soft-in" title="원하는 회수 기간이 있나요?" text="기간만 말하면 맞는 몫을 찾아드려요" onClose={unstuck}
              actions={[{ label: '세이빙 AI에게 말하기', main: true, onClick: () => { unstuck(); ai.ask(sayIt, { send: false }); } }]} />
          )}
        </div>
      }
      sideTitle="분배 결과"
      side={d ? (
        <>
          <ConditionSheet open={sheet} onClose={() => setSheet(false)} S={S} />
          <div className={cx('rows lined', a.stale && 'stale')}>
            <Row k="연간 절감액" v={`${won(d.annual_saving_won)}원`} sub={`90% 범위 ${won(d.ci_low_won)}~${won(d.ci_high_won)}원`} />
            <Row k="건물주 몫" v={`연 ${won(d.owner_annual_won)}원`} />
            <Row k={<>공사비를 돌려받으려면 필요한 몫<Info ask={{ q: sayIt, label: '안전한 몫까지 물어보기' }}>{d.period_years}년 안에 공사비를 돌려받으려면 건물주 몫이 이만큼은 돼야 해요</Info></>} v={pct1(d.required_owner_ratio)} />
            <Row k={<>공사비 · 기간{backup && <Info>저장된 시연 데이터에는 이 조건만 있어요</Info>}</>}
              v={<span className="v-tag">{koMoney(S.invest)} · {S.years}년{!backup && <Button variant="gray" size="s" onClick={() => setSheet(true)}>변경</Button>}</span>} />
          </div>
        </>
      ) : a.status === 'error' ? null : <Skeleton lines={4} head={false} />}
      more={d ? <Fold title="계산 근거"><BasisRows sb={d.saving_basis} /><AskLink title="이 금액, 믿어도 될까요?" q="이 금액 믿어도 돼요?" /></Fold> : null} />
  );
}

/* ══ ⑦ 정산 리포트 ══ */
function MonthList({ months, code, sel, onPick }) {
  const { device } = useShell();
  if (device === 'pc') {
    return (
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th scope="col">월</th><th scope="col">판정</th><th scope="col">실측 사용량</th><th scope="col">금액</th></tr></thead>
          <tbody>
            {months.map(m => {
              const mb = monthBadge(m.state, code);
              const nil = m.saving_won == null;
              return (
                <tr key={m.ym} data-ym={m.ym} aria-selected={m.ym === sel} tabIndex={0} onClick={() => onPick(m.ym)}
                  onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPick(m.ym); } }}>
                  <td className="num"><b>{ymTxt(m.ym)}</b></td>
                  <td className="st">
                    <Badge tone={mb.tone} mark={mb.mark}>{mb.text}</Badge>
                    {m.state === '확인 중' && m.note && <span className="tbl-note">{tidy(m.note)}</span>}
                  </td>
                  <td className="num">{m.actual_kwh != null ? `${kwh(m.actual_kwh)} kWh` : '—'}</td>
                  <td className={cx('num', nil && 'nil')}>{nil ? '금액 없음' : `${won(m.saving_won)}원`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }
  return (
    <div className="mons" role="radiogroup" aria-label="AI 설명을 볼 달">
      {months.map(m => {
        const mb = monthBadge(m.state, code);
        const nil = m.saving_won == null;
        return (
          <button key={m.ym} type="button" role="radio" aria-checked={m.ym === sel} className="mon" onClick={() => onPick(m.ym)}>
            <span className="mon-l">
              <span className="mon-t"><b className="num">{ymTxt(m.ym)}</b><Badge tone={mb.tone} mark={mb.mark}>{mb.text}</Badge></span>
              {m.state === '확인 중' && m.note && <span className="mon-s">{tidy(m.note)}</span>}
            </span>
            <span className={cx('mon-r num', nil && 'nil')}>{nil ? '금액 없음' : `${won(m.saving_won)}원`}</span>
          </button>
        );
      })}
    </div>
  );
}

function AIBox({ r, ym }) {
  if (!ym) return null;
  if (r.status === 'error') {
    return (
      <div className="ai">
        <p>설명을 불러오지 못했어요. 월별 금액은 그대로예요.</p>
        <div><Button variant="gray" size="s" onClick={r.reload}>다시 시도</Button></div>
      </div>
    );
  }
  if (!r.data) return <div className="ai"><Skeleton lines={3} head={false} /></div>;
  return (
    <div className="ai swap" key={r.data.ym || ym}>
      <div className="ai-h">
        <span className="ai-k"><Icon name="sparkle" size={16} />{ymTxt(r.data.ym || ym)}</span>
        <ActionBadge action={r.data.action} />
      </div>
      <p>{r.data.text}</p>
    </div>
  );
}

/* 처음 여는 달은 빨라도 4초 동안 살펴보는 모습을 보여준다 (이 탭에서 한 번) */
const seenYm = new Set();
function AIReveal({ r, ym }) {
  const first = !seenYm.has(ym);
  const { done, finished } = usePaced(first, { min: 4000, steps: 3, ready: r.status === 'ok' || r.status === 'error' });
  useEffect(() => { if (finished) seenYm.add(ym); }, [finished, ym]);
  if (first && !finished) {
    return <div className="ai think-box"><Thinking title={`${+ym.slice(4, 6)}월 사용량을 살펴보고 있어요`} steps={['실측 사용량 확인', '기저선과 비교', '판정 정리']} done={done} /></div>;
  }
  return <AIBox r={r} ym={ym} />;
}

function AIExplain({ r, ym, open, setOpen, flagged }) {
  const box = useRef(null);
  const { device } = useShell();
  useEffect(() => {
    if (open && device === 'm') setTimeout(() => box.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }), 60);
  }, [open, ym]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!ym) return null;
  return (
    <div className={cx('aix', open && 'open')} ref={box}>
      <button type="button" className="aix-btn" aria-expanded={open} onClick={() => setOpen(o => !o)}>
        <span className="ai-k"><Icon name="sparkle" size={16} />{ymTxt(ym)} AI 설명</span>
        <Icon name="down" size={20} />
      </button>
      {!open && (
        <button type="button" className="aix-buddy" onClick={() => setOpen(true)}>
          <BuddyBody w={64} live mood={flagged ? 'surprise' : 'idle'} />
          <span className="aix-bubble"><b>{+ym.slice(4, 6)}월 금액, 왜 이렇게 나왔을까요?</b></span>
        </button>
      )}
      {open && (
        <div className="aix-body soft-in">
          <AIReveal key={ym} r={r} ym={ym} />
          {flagged && <AskLink title={`${+ym.slice(4, 6)}월은 왜 튀었는지 묻기`} q={`${ym.slice(2, 4)}년 ${+ym.slice(4, 6)}월 사용량이 왜 튀었어?`} />}
        </div>
      )}
    </div>
  );
}

/* 모바일 · 분기 고르기는 한 줄 단추 → 아래 시트 (칩을 옆으로 밀지 않게) */
function QuarterSelect({ S, onPick }) {
  const [open, setOpen] = useState(false);
  const cur = S.caseItems.find(c => c.key === S.quarterKey) || S.caseItems[0];
  if (!cur) return <Skeleton lines={1} head={false} />;
  return (
    <>
      <button type="button" className="qsel" aria-haspopup="dialog" onClick={() => setOpen(true)}>
        <b>{cur.period}</b>{cur.txt && <span>{cur.txt}</span>}<Icon name="down" size={18} />
      </button>
      <Sheet open={open} onClose={() => setOpen(false)} title="정산 분기">
        <div className="qlist" role="radiogroup" aria-label="정산 분기">
          {S.caseItems.map(c => (
            <button key={c.key} type="button" role="radio" aria-checked={c.key === S.quarterKey} className="qrow"
              onClick={() => { onPick(c.key); setOpen(false); }}>
              <span className="qrow-t"><b>{c.period}</b>{c.txt && <span>{c.txt}</span>}</span>
              {c.key === S.quarterKey && <Icon name="check" size={20} stroke={2.6} />}
            </button>
          ))}
        </div>
      </Sheet>
    </>
  );
}

export function quarterOptions(S) {
  return S.caseItems.map(c => ({ value: c.key, label: `${c.period} · ${c.txt}` }));
}

let aiTaken = 0;
function SetlView({ S }) {
  const { month, setMonth, device, aiReq = 0, focus } = useShell();
  const [aiOpen, setAiOpen] = useState(false);
  useEffect(() => { if (aiReq && aiReq !== aiTaken) { aiTaken = aiReq; setAiOpen(true); } }, [aiReq]);
  const d = S.settlement.data;
  const months = d?.months || [];
  // 오른쪽 '월별 판정'에서 달을 고르면 이 표의 그 달 행으로 스크롤하고 잠깐 강조한다 (분기 자료가 오면 그때 실행)
  const done = useRef(0);
  useEffect(() => {
    if (!focus || focus.n === done.current || !months.some(m => m.ym === focus.ym)) return;
    done.current = focus.n;
    setTimeout(() => {
      const row = document.querySelector(`tr[data-ym="${focus.ym}"]`);
      if (!row) return;
      row.scrollIntoView({ block: 'center', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
      row.classList.remove('flash'); void row.offsetWidth; row.classList.add('flash');
      setTimeout(() => row.classList.remove('flash'), 2000);
    }, 140);
  }, [focus, d]); // eslint-disable-line react-hooks/exhaustive-deps
  const target = d ? explainTarget(d) : null;
  const sel = month && months.some(m => m.ym === month) ? month : target?.ym ?? null;
  const id = S.bld.data?.bld_id;
  const ex = useResource(['ex', S.nonce, sel], () => fetchExplain(id, sel), { enabled: !!sel && id != null && S.nonce > 0 });
  const opts = quarterOptions(S);
  const lead = S.cases.status === 'error' ? <ErrorBox error={S.cases.error} onRetry={S.cases.reload} />
    : opts.length ? (device === 'm'
      ? <QuarterSelect S={S} onPick={k => { setMonth(null); setAiOpen(false); S.setQuarterKey(k); }} />
      : <Chips label="정산 분기" value={S.quarterKey} onChange={k => { setMonth(null); setAiOpen(false); S.setQuarterKey(k); }} options={opts} />)
    : <Skeleton lines={1} head={false} />;
  if (!d) return <StepPending r={S.settlement} lead={lead} />;
  const has = hasAmount(d);
  const label = has ? `${d.period} ${d.amount_state || '정산액'}` : `${d.period} 정산`;
  return (
    <StepLayout lead={lead}
      head={
        <div className={cx('setl-head', S.settlement.stale && 'stale')} key={d.period}>
          <div className="step-eye"><StatusBadge code={d.status_code} fallback={d.status} /></div>
          <p className="amt-k">{label}{d.amount_note && <Info ask={{ q: '이 금액 믿어도 돼요?', label: '이 금액 믿어도 되는지 묻기' }}>{tidy(d.amount_note)}</Info>}</p>
          <p className={cx('amt', !has && 'none')}>{has ? <><Num value={d.saving_won} from0 />원</> : (d.amount_state || '금액 없음')}</p>
          {!has && d.status_msg && <p className={cx('amt-why', d.status_code === 'REVIEW_REQUIRED' && 'red')}>{tidy(d.status_msg)}</p>}
          {has && d.flagged_count > 0 && <p className="amt-why red">이상이 감지된 {d.flagged_count}개월은 금액에서 뺐어요</p>}
          <AskLink title="이 분기, 정산해도 될까요?" q={`${String(d.period).replace(/^(\d{4})\s*/, '$1년 ')} 정산해도 돼?`} />
        </div>
      }
      main={
        <div className={cx('stack-24', S.settlement.stale && 'stale')}>
          {has && (
            <div>
              <ShareBar ratio={d.owner_ratio} owner={<><Num value={d.owner_won} from0 />원</>} tenant={<><Num value={d.tenant_won} from0 />원</>} />
              {d.owner_won + d.tenant_won !== d.saving_won && (
                <p className="t-cap t-red mt-8">건물주와 임차인 몫의 합이 금액과 달라요. 서버 응답을 확인해 주세요</p>
              )}
            </div>
          )}
          <MonthList months={months} code={d.status_code} sel={sel} onPick={ym => { setMonth(ym); setAiOpen(true); }} />
        </div>
      }
      side={<AIExplain r={ex} ym={sel} open={aiOpen} setOpen={setAiOpen} flagged={months.find(m => m.ym === sel)?.state === '확인 중'} />}
      more={has ? <Fold title="금액 산정 근거"><BasisRows sb={d.saving_basis} /></Fold> : null} />
  );
}

/* ══ ⑥ 이득 확인 (2026-10-24 회의) ══
   세입자: 줄어든 전기·가스 요금 그대로 · 집 비우는 기간: 관리비 할인(금액은 두 사람이 정함)
   건물주: 절감액을 나눠 갖지 않고, 건물 가치 상승 + 이자지원. 금액은 서버(/api/benefit) 값 그대로 */
function BenefitView({ S }) {
  const r = S.benefit;
  if (!r.data) return <StepPending r={r} />;
  const d = r.data;
  if (!d.available) return <StepLayout title="이득을 계산할 수 없어요" main={d.reason ? <p className="t-b">{tidy(d.reason)}</p> : null} />;
  const { tenant: t, saving: sv, current: cur, schedule: sch, owner: ow } = d;
  const v = ow.value;
  const [mlo, mhi] = t.monthly_won;
  const vac = sch.vacate_days;
  const vacWorks = sch.works.filter(w => w.vacate_days);
  return (
    <StepLayout eyebrow={<Badge tone="amber" lg mark="sim">예상치</Badge>}
      title={`세입자는 매달 ${won(mlo)}~${won(mhi)}원을 아끼고, 건물주는 건물 가치가 올라요`}
      main={
        <div className={cx('ben', r.stale && 'stale')}>
          <section className="ben-c tenant" aria-label="세입자 이득">
            <h3>세입자 이득</h3>
            <p className="ben-big num">매달 {won(mlo)}~{won(mhi)}원</p>
            <div className="rows lined">
              <Row k="지금 1년 요금" v={`${manwon(cur.total_won)} 원`} sub={`${d.base_year}년 사용량 × 단가 · 전기 ${won(cur.elec_won)}원 · 가스 ${won(cur.gas_won)}원`} />
              <Row k="줄어드는 전기" v={`연 ${manRange(...sv.elec_won)}`} />
              <Row k="줄어드는 가스" v={`연 ${manRange(...sv.gas_won)}`} />
            </div>
            <p className="ben-note">{t.note}</p>
          </section>
          <section className="ben-c vacate" aria-label="집 비우는 기간">
            <h3>집 비우는 기간</h3>
            <p className="ben-big num">{vac ? `약 ${vac}일` : '없어요'}</p>
            <div className="rows lined">
              {vacWorks.map(w => <Row key={w.id} k={w.name} v={`약 ${w.vacate_days}일`} />)}
              <Row k="전체 공사 일정" v={`약 ${sch.total_days}일`} sub={sch.note} />
              {vac > 0 && <Row k="보상" v="관리비 할인" />}
            </div>
            <p className="ben-note">{d.compensation.note}</p>
          </section>
          <section className="ben-c owner" aria-label="건물주 이득">
            <h3>건물주 이득</h3>
            <p className="ben-big num">
              {v.gain_won ? `건물 가치 +${koMoney(v.gain_won[0])}~${koMoney(v.gain_won[1])}` : `건물 가치 +${pctRange(...v.rate_range)}`}
            </p>
            <div className="ben-prop">
              <AmountField label="집값(시세)" value={S.property} min={PROPERTY.min} max={PROPERTY.max}
                onChange={x => { if (x != null && x !== S.property) S.setProperty(x); }} />
            </div>
            <div className="rows lined">
              <Row k={<>상승률{!v.verified && <Badge tone="red">출처 확인 중</Badge>}</>} v={pctRange(...v.rate_range)} sub={`${v.source} · ${v.note}`} />
              <Row k="공사비" v={`${koMoney(S.invest)} · 건물주 부담`} />
              <Row k="지원사업" v={ow.programs.length ? ow.programs.join(' · ') : '해당 없음'} />
            </div>
            <p className="ben-note">{ow.note}</p>
          </section>
        </div>
      } />
  );
}

/* ══ ⑧ 임대차 특약 ══
   가상 계약서 한 장. 1~7단계에서 정한 값은 형광펜(h) · i 를 누르면 어느 단계에서 왜 이 값인지.
   화면과 복사 글이 같은 문안에서 나온다 (draftDoc) */
const h = (v, n, why) => ({ v, n, why });
const partText = ps => ps.map(p => (typeof p === 'string' ? p : p.v)).join('');
function draftDoc(S) {
  const b = S.bld.data || {}, el = S.eligibility.data, me = S.measures.data, ba = S.baseline.data, bn = S.benefit.data;
  const list = S.measureList || me?.measures || [];
  const on = list.filter(m => (S.picked ?? list.map(x => x.id)).includes(m.id)).map(m => m.name);
  const m = ba?.metrics || {}, mc = ba?.metric_checks || {};
  const ok = bn?.available;
  const sch = ok ? bn.schedule : null;
  const pr = ok ? bn.prices : {};
  const vac = sch?.vacate_days || 0;
  const v = ok ? bn.owner.value : null;
  // 형광펜 값 · 한 번 만들어 핵심 줄과 원문에 같이 쓴다
  const H = {
    addr: h(b.addr || '○○', 1, '1단계 「건물 확인」에서 맞다고 확인한 건축물대장 주소예요.'),
    area: b.area ? h(`${Number(b.area).toLocaleString('ko-KR')}㎡`, 1, '건축물대장의 연면적이에요.') : null,
    work: h(on.length ? on.join(', ') : '추천 공사', 4, '4단계 「추천 공사」에서 켜 둔 공사예요. 스위치로 끈 공사는 여기서 빠져요.'),
    days: h(sch ? `약 ${sch.total_days}일` : '—', 4, sch ? `4단계에서 고른 공사를 차례로 한다고 보고 더한 일정이에요. ${sch.note}` : '4단계에서 계산해요.'),
    vac: h(vac ? `약 ${vac}일` : '없음', 4, vac ? `집을 비워야 하는 공사(${sch.works.filter(w => w.vacate_days).map(w => w.name).join(', ')})의 기간이에요. 가정값이에요.` : '고른 공사 중 집을 비우는 공사가 없어요.'),
    monthly: h(ok ? `${won(bn.tenant.monthly_won[0])}~${won(bn.tenant.monthly_won[1])}원` : '—', 6, '6단계 「이득 확인」의 예상 절감액이에요. 고른 공사의 절감량 × 주택용 단가로 계산했어요.'),
    pe: h(pr.elec ? `${pr.elec.won_per_kwh}원/kWh` : '—', 6, pr.elec ? `${pr.elec.source}${pr.elec.verified === false ? ' · 출처 확인 중' : ''}` : '단가'),
    pg: h(pr.gas ? `${pr.gas.won_per_kwh}원/kWh` : '—', 6, pr.gas ? `${pr.gas.source}${pr.gas.verified === false ? ' · 출처 확인 중' : ''}` : '단가'),
    invest: h(koMoney(S.invest), 6, '6단계 「이득 확인」의 공사비예요. 맨 위 조건에서 바꿀 수 있어요.'),
    prog: h(el?.programs?.length ? el.programs.join(' · ') : '지원사업', 2, el?.msg ? `2단계 「지원 대상 확인」 결과예요: ${el.msg}` : '2단계 「지원 대상 확인」 결과예요.'),
    value: h(v ? (v.gain_won ? `${koMoney(v.gain_won[0])}~${koMoney(v.gain_won[1])}` : pctRange(...v.rate_range)) : '—', 6,
      v ? `집값(시세) × 상승률 ${pctRange(...v.rate_range)} 이에요. ${v.source}${v.verified ? '' : ' · 출처 확인 중'}` : '6단계에서 계산해요.'),
    cv: h(m.cv_rmse != null ? `${m.cv_rmse}%` : '—', 5, `5단계 「원래 사용량 예측」의 예측이 빗나간 정도예요. ${mc.cv_rmse?.ok ? '기준(15% 이하)을 충족해요.' : '기준(15% 이하)을 넘어요.'}`),
    r2: h(m.r2 ?? '—', 5, `예측이 들어맞는 정도예요. ${mc.r2?.ok ? '기준(0.75 이상)을 충족해요.' : '기준(0.75 이상)에 못 미쳐서 금액을 범위로 보여줘요.'}`),
  };
  const meta = [
    ['대상 건물', [H.addr, ...(H.area ? [' · 연면적 ', H.area] : [])]],
    ['임대인', ['○○○ (건물주)']],
    ['임차인', ['○○○']],
  ];
  /* 조항마다 keys(화면에 보이는 핵심 줄) · full(원문 · 복사) */
  const cl = [
    { k: '공사와 일정',
      keys: [['공사', [H.work]], ['전체 일정', [H.days]], ['집 비우는 기간', [H.vac]]],
      full: ['임대인은 ', H.work, ' 공사를 하며, 전체 일정은 ', H.days, ', 그중 임차인이 집을 비우는 기간은 ', H.vac, '으로 한다.'] },
    { k: '집 비우는 기간 보상',
      keys: [['보상', ['관리비 할인']], ['기간', [H.vac]], ['할인 금액', ['월 ○○원 (두 분이 정함)']]],
      full: ['임대인은 임차인이 집을 비우는 ', H.vac, ' 동안 관리비를 할인한다. 할인 금액과 방법은 두 당사자가 협의하여 정한다.'] },
    { k: '요금 절감',
      keys: [['줄어드는 요금', [H.monthly, ' / 월 (예상)']], ['단가', ['전기 ', H.pe, ' · 가스 ', H.pg]], ['누구 몫', ['요금을 내는 임차인']]],
      full: ['공사로 줄어든 전기·가스 요금은 요금을 내는 임차인의 몫으로 하며, 예상 절감액은 월 ', H.monthly, '(전기 ', H.pe, ' · 가스 ', H.pg, ' 기준)이다.'] },
    { k: '공사비와 건물 가치',
      keys: [['공사비', [H.invest, ' · 임대인 부담']], ['지원사업', [H.prog, ' 신청 검토']], ['건물 가치 상승', [H.value]]],
      full: ['공사비 ', H.invest, '은 임대인이 부담하고 ', H.prog, ' 신청을 함께 검토한다. 공사로 오르는 건물 가치(', H.value, ')는 임대인에게 귀속된다.'] },
    { k: '사용량 확인',
      keys: [['방법', ['전기·가스 고지서 공유 (임차인 동의)']], ['AI 예측', ['오차 ', H.cv, ' · 설명력 ', H.r2]]],
      full: ['임차인은 공사 전후 전기·가스 고지서를 임대인과 공유하는 데 동의하며, 절감량은 기온을 보정한 AI 예측(오차 ', H.cv, ', 설명력 ', H.r2, ')과 비교해 확인한다.'] },
    { k: '이견 처리', keys: [['열람', ['산출 근거 · 계산 내역을 양측 동일하게']]], full: ['양측은 산출 근거와 계산 내역을 동일하게 열람한다.'] },
  ];
  return { meta, cl };
}
const docText = (S, head) => {
  const d = draftDoc(S);
  return [head, `${S.benefit.data?.is_house ? '주택' : '상가건물'} 임대차계약서 특약사항`, ...d.meta.map(([k, ps]) => `${k}: ${partText(ps)}`), '', '[특약사항]',
    ...d.cl.map((c, i) => `제${i + 1}조 (${c.k}) ${partText(c.full)}`)].join('\n');
};

/* 형광펜 · 앞 단계에서 온 값 */
function Hl({ p }) {
  return (
    <mark className="hl">
      {p.v}
      <Info label={`${p.n}단계에서 온 값 · 이유 보기`} size={14}>
        <p className="hl-src">{p.n}단계 · {STEPS[p.n - 1]?.name}</p>
        <p>{tidy(p.why)}</p>
      </Info>
    </mark>
  );
}
const Parts = ({ ps }) => ps.map((p, i) => (typeof p === 'string' ? <span key={i}>{p}</span> : <Hl key={i} p={p} />));

async function copyText(t) {
  try { await navigator.clipboard.writeText(t); return true; } catch { /* 아래 방법 */ }
  try {
    const el = document.createElement('textarea');
    el.value = t; el.setAttribute('readonly', ''); el.style.position = 'fixed'; el.style.opacity = '0';
    document.body.appendChild(el); el.select();
    const ok = document.execCommand('copy'); el.remove(); return ok;
  } catch { return false; }
}

/* 복사 전 확인 세 가지 (요구서 4-2) — 셋 다 체크해야 복사가 켜진다 */
function CopySheet({ open, onClose, S }) {
  const ai = useAssist();
  const [ck, setCk] = useState({ split: false, hold: false, vac: false });
  const [fail, setFail] = useState(false);
  useEffect(() => { if (open) { setCk({ split: false, hold: false, vac: false }); setFail(false); } }, [open]);
  const all = ck.split && ck.hold && ck.vac;
  const run = async () => {
    const head = S.aiDraft ? '[법률 검토 전 초안 · AI가 정리한 문안입니다]' : '[설계안 · 법적 효력 없음]';
    const ok = await copyText(docText(S, head));
    if (!ok) { setFail(true); return; }
    onClose();
    ai?.showToast({ text: '특약 초안을 복사했어요', mood: 'cheer' });
  };
  return (
    <Sheet open={open} onClose={onClose} title="복사하기 전에 확인해 주세요"
      footer={<Button block disabled={!all} onClick={run}><Icon name="copy" size={20} />복사</Button>}>
      <div className="ck-list">
        <Check checked={ck.split} onChange={v => setCk(c => ({ ...c, split: v }))}>공사 일정과 집 비우는 기간이 맞아요</Check>
        <Check checked={ck.hold} onChange={v => setCk(c => ({ ...c, hold: v }))}>관리비 할인 금액은 두 사람이 따로 정해요</Check>
        <Check checked={ck.vac} onChange={v => setCk(c => ({ ...c, vac: v }))}>공사비와 건물 가치 조항을 확인했어요</Check>
      </div>
      {fail && <p className="t-cap t-red">복사하지 못했어요. 글을 길게 눌러 직접 복사해 주세요</p>}
    </Sheet>
  );
}

/* 가상 계약서 한 장 · 조항은 하나씩 (핵심 줄만, 원문은 펼쳐서) */
function DraftDoc({ S, tools }) {
  const d = draftDoc(S);
  const [i, setI] = useState(0);
  const [full, setFull] = useState(false);
  const c = d.cl[i];
  const pick = k => { setI(k); setFull(false); };
  return (
    <div className="doc" role="document" aria-label="가상 임대차 계약서 특약사항">
      <div className="doc-h">
        <h3>{S.benefit.data?.is_house ? '주택' : '상가건물'} 임대차계약서 <small>특약사항</small></h3>
      </div>
      <dl className="doc-meta">
        {d.meta.map(([k, ps]) => <div key={k}><dt>{k}</dt><dd><Parts ps={ps} /></dd></div>)}
      </dl>
      <div className="doc-body">
      <div className="doc-tabs" role="tablist" aria-label="조항">
        {d.cl.map((x, k) => (
          <button key={x.k} type="button" role="tab" aria-selected={k === i} onClick={() => pick(k)}><i className="num">{k + 1}</i>{x.k}</button>
        ))}
      </div>
      <section key={i} className="doc-c soft-in" aria-label={`제${i + 1}조 ${c.k}`}>
        <h4>제{i + 1}조 <span>{c.k}</span></h4>
        <dl className="doc-keys">
          {c.keys.map(([k, ps]) => <div key={k}><dt>{k}</dt><dd><Parts ps={ps} /></dd></div>)}
        </dl>
        <button type="button" className="doc-full-btn" aria-expanded={full} onClick={() => setFull(v => !v)}>{full ? '원문 접기' : '원문 보기'}</button>
        {full && <p className="doc-full"><Parts ps={c.full} /></p>}
      </section>
      </div>
      <div className="doc-foot">
        {tools && <div className="doc-tools">{tools}</div>}
        <div className="doc-nav">
          <button type="button" disabled={i === 0} onClick={() => pick(i - 1)}><Icon name="left" size={16} />이전 조항</button>
          <span className="num">{i + 1} / {d.cl.length}</span>
          <button type="button" disabled={i === d.cl.length - 1} onClick={() => pick(i + 1)}>다음 조항<Icon name="right" size={16} /></button>
        </div>
      </div>
    </div>
  );
}

function DraftView({ S }) {
  const { go } = useShell();
  const [copy, setCopy] = useState(false);
  return (
    <StepLayout
      eyebrow={S.aiDraft
        ? <><Badge tone="blue" lg><Icon name="sparkle" size={14} />법률 검토 전 초안 · AI가 정리한 문안입니다</Badge><Info>실제 계약서로 쓰려면 법률 검토가 필요해요</Info></>
        : <><Badge tone="gray" lg>설계안 · 법적 효력 없음</Badge><Info>실제 계약서로 쓰려면 법률 검토가 필요해요</Info></>}
      title="앞에서 정한 값이 계약서에 이렇게 들어가요"
      main={
        <>
          <DraftDoc S={S} tools={<>
            <Button size="s" onClick={() => setCopy(true)}><Icon name="copy" size={16} />특약 복사</Button>
            <Button size="s" variant="gray" onClick={() => go('alloc')}>이득 다시 보기</Button>
          </>} />
          <CopySheet open={copy} onClose={() => setCopy(false)} S={S} />
        </>
      } />
  );
}

/* ══ ⑨ 시스템 구성 ══ */
const FLOW = [
  ['공공데이터', '건축물대장 · 건물에너지 사용량(지번 단위 월별, 2020.01~) · 기상청 일자료 · 한전·도시가스 요금표'],
  ['적재', '결측월 보존 · 난방도일과 냉방도일 산출'],
  ['기저선 AI', '공사 직전 36개월로 "공사를 안 했다면 썼을 양"을 추정해요(학습 24 · 검증 12, 이상 감지 달 제외). 예측 오차·평균 편향·설명력을 함께 공개해요'],
  ['이상 감지', '같은 달 과거 평균보다 크게 튄 달을 찾아 금액에서 빼요. 사람이 원인을 확인하기 전에는 돈을 나누지 않아요'],
  ['정산 판정', '공사 전은 예상 금액 · 공사 후는 (기저선 − 실측) × 단가 · 모델이 기준을 다 채우면 검증 완료, 아니면 잠정 · 이상 달은 제외 · 데이터 없으면 정산 불가'],
  ['세이빙 AI', '자체 경량 모델(CPU, 747KB)이 질문의 의도만 판단하고, 숫자는 서버가 계산한 값만 써요. 화면 값과 직전 대화로 빈칸을 먼저 채우고, 모를 때만 하나씩 되물어요'],
  ['AI 설명', '캐시 → Gemini → 규칙 기반 템플릿 순서로 문장을 만들고, 숫자를 만들거나 판정을 바꾼 문장은 버려요'],
];
/* 계산 방법 · 모바일 「전체 단계」 창과 PC ✦ 버튼에서 연다 */
export function CalcMethod() {
  return (
    <div className="calc">
      <p className="calc-t">금액과 판정은 서버가 계산하고, AI는 설명만 해요</p>
      <ol className="pipe">
          {FLOW.map(([k, v], i) => (
            <li key={k} className={cx(k === 'AI 설명' && 'ai-step')}>
              <Fold title={<span className="cl"><span className="cl-n num">{i + 1}</span>{k}</span>}>
                <p>{tidy(v)}</p>
              </Fold>
            </li>
          ))}
      </ol>
      <Fold title="기술 구성">
        <div className="rows lined">
          <Row k="백엔드" v={`FastAPI · SQLite · pandas · scikit${WJ}-${WJ}learn`} />
          <Row k="화면" v="한 장짜리 HTML · PC와 모바일 공용" />
          <Row k="장애 대비" v="서버 미연결 시 저장된 시연 데이터" />
        </div>
      </Fold>
    </div>
  );
}

/* ══ ⑨ 결론 정리 · 공사 비용·유형·기간, 건물주와 세입자에게 남는 것 ══
   금액은 서버가 계산한 값 그대로 (화면은 모아서 보여주기만) */
function SumView({ S }) {
  const { go } = useShell();
  const bn = S.benefit.data, me = S.measures.data, el = S.eligibility.data;
  const ok = bn?.available;
  const list = S.measureList || me?.measures || [];
  const picked = list.filter(m => (S.picked ?? list.map(x => x.id)).includes(m.id));
  const [rlo, rhi] = me?.total_saving_rate || [];
  const sch = ok ? bn.schedule : null;
  const v = ok ? bn.owner.value : null;
  const mo = ok ? `매달 ${won(bn.tenant.monthly_won[0])}~${won(bn.tenant.monthly_won[1])}원` : '—';
  const val = v ? (v.gain_won ? `+${koMoney(v.gain_won[0])}~${koMoney(v.gain_won[1])}` : `+${pctRange(...v.rate_range)}`) : '—';
  const cards = [
    { k: '공사 유형', v: picked.map(m => m.name.replace(/\s*\(.*\)$/, '')).join(' · ') || '—', sub: rlo != null ? `에너지 사용량 ${pctRange(rlo, rhi)} 감소 (예상)` : null, to: 'meas' },
    { k: '공사 일정', v: sch ? `약 ${sch.total_days}일` : '—', sub: sch ? (sch.vacate_days ? `그중 집 비우는 기간 약 ${sch.vacate_days}일 (가정값)` : '집을 비우지 않아요 (가정값)') : null, to: 'meas' },
    { k: '공사 비용', v: koMoney(S.invest), sub: `건물주 부담${el?.programs?.length ? ` · ${el.programs.join(' · ')} 신청 가능` : ''}`, to: 'alloc' },
    { k: '세입자에게 이득', v: mo, sub: ok ? `줄어든 전기·가스 요금 · 연 ${manRange(...bn.saving.total_won)}` : null, tone: 'tenant', to: 'alloc' },
    { k: '집 비우는 기간 보상', v: sch?.vacate_days ? '관리비 할인' : '필요 없음', sub: sch?.vacate_days ? '금액과 방법은 두 분이 정해요' : '사는 채로 공사해요', to: 'draft' },
    { k: '건물주에게 이득', v: `건물 가치 ${val}`, sub: v ? `집값 ${koMoney(S.property)} 기준 · 상승률 ${pctRange(...v.rate_range)}${v.verified ? '' : ' (출처 확인 중)'}` : null, tone: 'owner', to: 'alloc' },
  ];
  return (
    <StepLayout
      eyebrow={<Badge tone="amber" lg mark="sim">예상치</Badge>}
      title={ok ? `세입자는 ${mo}을 아끼고, 건물주는 건물 가치가 ${val} 올라요` : '결론을 정리하고 있어요'}
      main={
        <div className="sum">
          {cards.map(c => (
            <div key={c.k} className={cx('sum-c', c.tone)}>
              <span className="sum-k">{c.k}</span>
              <b className="sum-v num">{c.v}</b>
              {c.sub && <span className="sum-s">{c.sub}</span>}
              <button type="button" className="sum-go" onClick={() => go(c.to)}>바꾸기<Icon name="right" size={14} /></button>
            </div>
          ))}
        </div>
      } />
  );
}

const VIEWS = { bld: BldView, elig: EligView, prof: ProfView, meas: MeasView, base: BaseView, alloc: BenefitView, draft: DraftView, sys: SumView };
/* 화면마다 맨 위에 한 번 · "이 화면은 무엇이고, 지금 뭘 하면 되는지" 한 줄씩 */
const GUIDE = {
  bld: ['건물 정보가 맞는지만 확인해 주세요', '맞으면 아래 「맞아요」를 눌러 주세요. 다르면 「다른 건물」을 누르세요.'],
  elig: ['정부 지원을 받을 수 있는 건물인지 살펴봤어요', '초록 체크는 해당돼요, 빨간 X는 해당되지 않아요. 항목을 누르면 이유가 나와요.'],
  prof: ['이 건물이 해마다 전기·가스를 얼마나 썼는지 보여줘요', '막대가 높을수록 에너지를 많이 쓴 해예요. 따로 할 일은 없어요.'],
  meas: ['어떤 공사를 하면 1년에 얼마나 아끼고, 며칠 걸리는지 보여줘요', ''],
  base: ['공사를 안 했다면 얼마나 썼을지, 컴퓨터가 예측한 결과예요', '이 예측과 실제 사용량의 차이가 "아낀 양"이 돼요. 몰라도 다음 단계로 가면 돼요.'],
  alloc: ['공사로 세입자와 건물주가 각각 무엇을 얻는지 보여줘요', ''],
  setl: ['매달 얼마나 아꼈는지 보여줘요', '오른쪽(또는 아래) 목록에서 달을 누르면 그 달 내용이 나와요.'],
  draft: ['앞 단계에서 정한 값이 계약서에 들어간 모습이에요', '형광펜은 1~7단계에서 온 값이고, ⓘ를 누르면 왜 그 값인지 나와요. 꼭 전문가와 함께 확인하세요.'],
  sys: ['공사부터 정산까지, 두 사람에게 무엇이 남는지 한눈에 정리했어요', ''],
};
function StepGuide({ id }) {
  const g = GUIDE[id];
  if (!g) return null;
  return (
    <aside className="sguide" aria-label="이 화면 안내">
      <span className="sguide-ic" aria-hidden="true"><Icon name="info" size={20} /></span>
      <div><p className="sguide-t">{g[0]}</p></div>
    </aside>
  );
}

export function StepView({ id, S }) {
  const V = VIEWS[id] || BldView;
  return <V S={S} />;   // 단계 안내 상자는 뺐다 (2026-10-24 · 너무 당연한 말)
}

/* ══ 단계별 한 줄 요약 (모바일 단계 목록) ══ */
export function summaries(S) {
  const el = S.eligibility.data, pr = S.profile.data, me = S.measures.data, ba = S.baseline.data;
  const bn = S.benefit.data?.available ? S.benefit.data : null;
  const last = pr?.years?.[pr.years.length - 1];
  const rr = me?.total_saving_rate;
  return {
    bld: S.bld.data ? { text: S.bld.data.addr } : null,
    elig: el ? { text: el.eligible ? (el.programs?.length ? `${el.programs.length}개 신청 가능` : '대상 건물') : '대상 아님', tone: el.eligible ? 'green' : 'red' } : null,
    prof: last ? { text: `${kwh(last.total)} kWh` } : null,
    meas: me?.available && rr ? { text: `${pctRange(rr[0], rr[1])} 절감` } : null,
    base: ba ? (baselineFail(ba) ? { text: '범위로 제시', tone: 'amber' } : baselinePass(ba) ? { text: '기준 충족', tone: 'green' } : { text: '판정 없음' }) : null,
    alloc: bn ? { text: `세입자 매달 ${won(bn.tenant.monthly_won[0])}~${won(bn.tenant.monthly_won[1])}원` } : null,
    draft: { text: '초안' },
    sys: null,
  };
}
