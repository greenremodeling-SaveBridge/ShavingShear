import { useMemo, useState } from 'react';
import { kwh, ymTxt } from '../core/format.js';
import { useMeasure } from '../core/hooks.js';
import { Badge, useReveal } from './ui.jsx';

const ordOf = ym => (+ym.slice(0, 4)) * 12 + (+ym.slice(4, 6)) - 1;
const ymOf = o => `${Math.floor(o / 12)}${String((o % 12) + 1).padStart(2, '0')}`;
const man = v => (v === 0 ? '0' : v % 10000 === 0 ? `${v / 10000}만` : `${(v / 10000).toFixed(1)}만`);
const man1 = v => `${(v / 10000).toFixed(1)}만`;

function niceStep(raw) {
  const p = 10 ** Math.floor(Math.log10(raw));
  const m = raw / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 2.5 ? 2.5 : m <= 5 ? 5 : 10) * p;
}

/* 사용량 자료 범위와 결측월 */
export function dataSpan(rows) {
  const rs = (rows || []).filter(r => r && typeof r.ym === 'string' && r.ym.length >= 6).map(r => r.ym).sort();
  if (!rs.length) return null;
  const have = new Set(rs.map(ordOf));
  const miss = [];
  for (let o = ordOf(rs[0]); o <= ordOf(rs[rs.length - 1]); o++) if (!have.has(o)) miss.push(ymOf(o));
  return { first: rs[0], last: rs[rs.length - 1], n: rs.length, miss };
}

/* ── 연도별 사용량 (전기 + 가스) ── */
export function YearBars({ years }) {
  const ys = years || [];
  const on = useReveal();
  const max = Math.max(1, ...ys.map(y => y.total || 0));
  const h = v => (on ? `calc((100% - 22px) * ${(v || 0) / max})` : '0px');
  return (
    <figure className="yb" aria-label="연도별 전기·가스 사용량">
      <div className="legend">
        <span className="key"><i className="sw-sq" style={{ background: 'var(--elec)' }} />전기</span>
        <span className="key"><i className="sw-sq" style={{ background: 'var(--gas)' }} />가스</span>
        <span className="push">단위 kWh</span>
      </div>
      <div className="ybars" style={{ '--n': ys.length }} role="list">
        {ys.map((y, i) => (
          <div className={`yb-col${on ? ' on' : ''}`} key={y.year} role="listitem" style={{ '--d': `${i * 50}ms` }}
            aria-label={`${y.year}년 ${kwh(y.total)} kWh, 전기 ${kwh(y.elec)}, 가스 ${kwh(y.gas)}${y.annualized ? `, ${y.months}개월 자료 연환산` : ''}`}>
            <span className="yb-v num">{man1(y.total || 0)}</span>
            <span className="yb-gas" style={{ height: h(y.gas) }} />
            <span className="yb-elec" style={{ height: h(y.elec) }} />
          </div>
        ))}
      </div>
      <div className="yb-x" style={{ '--n': ys.length }} aria-hidden="true">
        {ys.map(y => (
          <div key={y.year}>
            <b className="num">{y.year}</b>
            {y.annualized && <Badge tone="gray" title={`${y.months}개월 자료를 12개월로 환산`}>연환산</Badge>}
          </div>
        ))}
      </div>
    </figure>
  );
}

/* ── 월별 실측과 예측 ── 결측월은 잇지 않는다 */
function prepare(rows, anomalies) {
  const rs = (rows || []).filter(r => r && typeof r.ym === 'string' && r.ym.length >= 6)
    .map(r => ({ ...r, o: ordOf(r.ym) })).sort((a, b) => a.o - b.o);
  if (!rs.length) return null;
  const o0 = rs[0].o, o1 = rs[rs.length - 1].o;
  const byO = new Map(rs.map(r => [r.o, r]));
  const missing = [];
  for (let o = o0; o <= o1; o++) if (!byO.has(o)) missing.push(o);
  const bands = [];
  let st = 0;
  for (let i = 1; i <= rs.length; i++) {
    if (i === rs.length || rs[i].phase !== rs[st].phase) {
      bands.push({ phase: rs[st].phase, a: rs[st].o, b: rs[i - 1].o, n: i - st });
      st = i;
    }
  }
  const vals = rs.flatMap(r => [r.actual, r.baseline]).filter(v => Number.isFinite(v));
  const step = niceStep(Math.max(1, ...vals) / 3);
  const max = Math.ceil(Math.max(1, ...vals) / step) * step;
  const ticks = [];
  for (let v = 0; v <= max + 1e-9; v += step) ticks.push(v);
  return { rs, o0, o1, byO, missing, bands, max, ticks, anom: new Map((anomalies || []).map(a => [a.ym, a])) };
}

const PHASE_NOTE = { 적용: '공사 전' };

export function BaselineChart({ rows, anomalies }) {
  const [ref, w] = useMeasure();
  const [cur, setCur] = useState(null);
  const on = useReveal();
  const D = useMemo(() => prepare(rows, anomalies), [rows, anomalies]);
  if (!D) return <p className="t-b2">표시할 월별 자료가 없어요.</p>;

  const H = w >= 600 ? 280 : w >= 480 ? 260 : 228;
  const M = { l: 34, r: 6, t: 32, b: 26 };
  const iw = Math.max(10, w - M.l - M.r), ih = H - M.t - M.b;
  const span = Math.max(1, D.o1 - D.o0);
  const X = o => M.l + ((o - D.o0) / span) * iw;
  const Y = v => M.t + ih - (v / D.max) * ih;
  const edge = o => Math.min(M.l + iw, Math.max(M.l, X(o)));

  const path = k => {
    let d = '', prev = null;
    for (const r of D.rs) {
      if (!Number.isFinite(r[k])) { prev = null; continue; }
      d += `${prev === null || r.o - prev > 1 ? 'M' : 'L'}${X(r.o).toFixed(1)} ${Y(r[k]).toFixed(1)}`;
      prev = r.o;
    }
    return d;
  };
  const jans = D.rs.filter(r => r.ym.endsWith('01'));

  const pick = e => {
    const b = e.currentTarget.getBoundingClientRect();
    const o = Math.round(D.o0 + ((e.clientX - b.left) / iw) * span);
    setCur(Math.min(D.o1, Math.max(D.o0, o)));
  };
  const key = e => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') { if (e.key === 'Escape') setCur(null); return; }
    e.preventDefault();
    const d = e.key === 'ArrowRight' ? 1 : -1;
    setCur(c => Math.min(D.o1, Math.max(D.o0, (c ?? (d > 0 ? D.o0 - 1 : D.o1 + 1)) + d)));
  };

  const row = cur != null ? D.byO.get(cur) : null;
  const an = cur != null ? D.anom.get(ymOf(cur)) : null;
  const ph = cur != null ? D.bands.find(b => cur >= b.a && cur <= b.b)?.phase : null;
  const TW = 196;
  const tipX = cur != null ? (X(cur) + 12 + TW > w ? X(cur) - 12 - TW : X(cur) + 12) : 0;
  const missTxt = D.missing.map(o => ymTxt(ymOf(o))).join(', ');

  return (
    <div className="chart" ref={ref} tabIndex={0} onKeyDown={key} onBlur={() => setCur(null)}
      aria-label={`월별 실측 사용량과 예측. 좌우 화살표로 달을 옮겨 볼 수 있어요.${missTxt ? ` 결측월 ${missTxt}` : ''}`}>
      {w > 0 && (
        <svg width={w} height={H} role="img" aria-label="월별 실측과 예측 그래프">
          {D.bands.map((b, i) => (b.phase === '검증' ? (
            <rect key={'b' + i} x={edge(b.a - 0.5)} y={M.t} width={edge(b.b + 0.5) - edge(b.a - 0.5)} height={ih} className="ch-band" />
          ) : null))}
          {D.ticks.map(t => (
            <g key={t}>
              <line x1={M.l} x2={M.l + iw} y1={Y(t)} y2={Y(t)} className="ch-grid" />
              <text x={M.l - 8} y={Y(t) + 4} textAnchor="end" className="ch-tick">{man(t)}</text>
            </g>
          ))}
          {D.bands.slice(1).map((b, i) => (
            <line key={'s' + i} x1={edge(b.a - 0.5)} x2={edge(b.a - 0.5)} y1={M.t - 24} y2={M.t + ih} className="ch-sep" />
          ))}
          {D.bands.map((b, i) => {
            const x0 = edge(b.a - 0.5), x1 = edge(b.b + 0.5), bw = x1 - x0;
            const label = bw >= 150 && PHASE_NOTE[b.phase] ? `${b.phase} ${b.n}개월 · ${PHASE_NOTE[b.phase]}`
              : bw >= 76 ? `${b.phase} ${b.n}개월` : bw >= 30 ? b.phase : '';
            return label ? <text key={'p' + i} x={x0 + 6} y={M.t - 12} className="ch-phase">{label}</text> : null;
          })}
          <text x={M.l - 8} y={M.t - 12} textAnchor="end" className="ch-tick">kWh</text>
          {D.missing.map(o => <line key={'m' + o} x1={X(o)} x2={X(o)} y1={M.t} y2={M.t + ih} className="ch-miss" />)}
          <g className={`reveal${on && w > 0 ? ' on' : ''}`}>
            <path d={path('baseline')} className="ch-base" />
            <path d={path('actual')} className="ch-act" />
          </g>
          {D.rs.filter(r => D.anom.has(r.ym) && Number.isFinite(r.actual)).map((r, i) => (
            <circle key={'a' + r.ym} cx={X(r.o)} cy={Y(r.actual)} r={4.5} className={`ch-anom${on ? ' on' : ''}`} style={{ '--d': `${750 + i * 60}ms` }} />
          ))}
          {jans.map(r => <text key={'y' + r.ym} x={X(r.o)} y={H - 6} textAnchor="middle" className="ch-year">{r.ym.slice(0, 4)}</text>)}
          {cur != null && (
            <g pointerEvents="none">
              <line x1={X(cur)} x2={X(cur)} y1={M.t} y2={M.t + ih} className="ch-x" />
              {Number.isFinite(row?.baseline) && <circle cx={X(cur)} cy={Y(row.baseline)} r={4.5} className="ch-dot-b" />}
              {Number.isFinite(row?.actual) && <circle cx={X(cur)} cy={Y(row.actual)} r={4.5} className="ch-dot-a" />}
            </g>
          )}
          <rect x={M.l} y={M.t} width={iw} height={ih} fill="transparent"
            onPointerMove={pick} onPointerDown={pick} onPointerLeave={e => { if (e.pointerType === 'mouse') setCur(null); }} />
        </svg>
      )}
      {cur != null && w > 0 && (
        <div className="tip" style={{ left: Math.max(0, tipX), top: M.t }}>
          <div className="tip-h"><b>{ymTxt(ymOf(cur))}</b>{ph && <span>{ph}</span>}</div>
          {row ? (
            <>
              <div className="tip-r"><span>실측</span><b className="num">{kwh(row.actual)} kWh</b></div>
              <div className="tip-r"><span>예측</span><b className="num">{kwh(row.baseline)} kWh</b></div>
              {an && <div className="tip-f">{an.fuel} 사용량이 과거 같은 달 평균의 {an.ratio}배</div>}
            </>
          ) : <div className="tip-r"><span>결측월 · 원자료가 없어요</span></div>}
        </div>
      )}
    </div>
  );
}

export const LineLegend = () => (
  <div className="legend">
    <span className="key"><i className="sw-ln" />실측</span>
    <span className="key"><i className="sw-ln dash" />예측</span>
    <span className="key"><i className="sw-dot" />이상 감지</span>
    <span className="key"><i className="sw-gap" />결측월</span>
  </div>
);

/* ── 건물주 · 임차인 몫 ── */
export function ShareBar({ ratio, owner, tenant }) {
  const r = Math.min(1, Math.max(0, Number(ratio) || 0));
  const on = useReveal();
  return (
    <div>
      <div className={`share-bar reveal${on ? ' on' : ''}`} aria-hidden="true">
        <span className="o" style={{ flexGrow: r }} />
        <span className="t" style={{ flexGrow: 1 - r }} />
      </div>
      <div className="share-legend">
        <div>
          <span className="k"><i style={{ background: 'var(--owner)' }} />건물주 {Math.round(r * 100)}%</span>
          <span className="v num">{owner}</span>
        </div>
        <div>
          <span className="k"><i style={{ background: 'var(--tenant)' }} />임차인 {Math.round((1 - r) * 100)}%</span>
          <span className="v num">{tenant}</span>
        </div>
      </div>
    </div>
  );
}

/* ══ 요약 칸에 들어가는 작은 그림 (56 × 36) ══ */
const MW = 56, MH = 36;

export function MiniBars({ values, hi, color = 'var(--primary)' }) {
  const vs = values || [];
  const n = Math.max(1, vs.length);
  const max = Math.max(1, ...vs.filter(Number.isFinite));
  const gap = n > 4 ? 3 : 5, bw = (MW - gap * (n - 1)) / n;
  const last = hi ?? n - 1;
  return (
    <svg className="mini" width={MW} height={MH} viewBox={`0 0 ${MW} ${MH}`} aria-hidden="true">
      {vs.map((v, i) => {
        const x = i * (bw + gap);
        if (!Number.isFinite(v)) return <rect key={i} x={x} y={MH - 3} width={bw} height={3} rx={1.5} className="mini-nil" />;
        const bh = Math.max(3, (v / max) * MH);
        return <rect key={i} x={x} y={MH - bh} width={bw} height={bh} rx={Math.min(2.5, bw / 2)} style={{ fill: i === last ? color : 'var(--fill-2)' }} />;
      })}
    </svg>
  );
}

export function MiniLines({ a, b }) {
  const all = [...(a || []), ...(b || [])].filter(Number.isFinite);
  if (!all.length) return <svg className="mini" width={MW} height={MH} aria-hidden="true" />;
  const lo = Math.min(...all), hi = Math.max(...all);
  const n = Math.max(2, (a || []).length);
  const X = i => 1 + (i / (n - 1)) * (MW - 2);
  const Y = v => MH - 3 - ((v - lo) / (hi - lo || 1)) * (MH - 6);
  const p = arr => {
    let d = '', pen = false;
    (arr || []).forEach((v, i) => {
      if (!Number.isFinite(v)) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`;
      pen = true;
    });
    return d;
  };
  return (
    <svg className="mini" width={MW} height={MH} viewBox={`0 0 ${MW} ${MH}`} aria-hidden="true">
      <path d={p(b)} className="mini-b" />
      <path d={p(a)} className="mini-a" />
    </svg>
  );
}

export function MiniSplit({ ratio }) {
  const r = 14, c = 2 * Math.PI * r, k = Math.min(1, Math.max(0, Number(ratio) || 0));
  return (
    <svg className="mini" width={MW} height={MH} viewBox={`0 0 ${MW} ${MH}`} aria-hidden="true">
      <circle cx={MW / 2} cy={MH / 2} r={r} fill="none" stroke="var(--tenant)" strokeWidth="6" />
      <circle cx={MW / 2} cy={MH / 2} r={r} fill="none" stroke="var(--owner)" strokeWidth="6"
        strokeDasharray={`${(c * k).toFixed(2)} ${c.toFixed(2)}`} transform={`rotate(-90 ${MW / 2} ${MH / 2})`} />
    </svg>
  );
}

export function MiniRange({ lo, hi }) {
  const x0 = 2 + Math.max(0, Math.min(1, lo)) * (MW - 4), x1 = 2 + Math.max(0, Math.min(1, hi)) * (MW - 4);
  return (
    <svg className="mini" width={MW} height={MH} viewBox={`0 0 ${MW} ${MH}`} aria-hidden="true">
      <rect x="2" y={MH / 2 - 3} width={MW - 4} height="6" rx="3" className="mini-track" />
      <rect x={x0} y={MH / 2 - 3} width={Math.max(4, x1 - x0)} height="6" rx="3" style={{ fill: 'var(--primary)' }} />
    </svg>
  );
}

export function MiniChecks({ list }) {
  const xs = (list || []).slice(0, 6);
  const n = Math.max(1, xs.length), step = Math.min(14, (MW - 10) / Math.max(1, n - 1));
  const x0 = MW / 2 - (step * (n - 1)) / 2;
  return (
    <svg className="mini" width={MW} height={MH} viewBox={`0 0 ${MW} ${MH}`} aria-hidden="true">
      {xs.map((ok, i) => (
        <g key={i} transform={`translate(${x0 + i * step} ${MH / 2})`}>
          <circle r="6" style={{ fill: ok ? 'var(--green-text)' : 'var(--red-text)' }} />
          {ok ? <path d="M-2.6 0.1l1.8 1.8 3.4-3.6" fill="none" stroke="var(--surface)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            : <path d="M-2.2-2.2l4.4 4.4M2.2-2.2l-4.4 4.4" stroke="var(--surface)" strokeWidth="1.6" strokeLinecap="round" />}
        </g>
      ))}
    </svg>
  );
}
