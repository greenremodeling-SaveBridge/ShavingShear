/* ══════════════════════════════════════════════════════
   세이빙 AI 답 카드 — 숫자는 서버 응답 그대로 (천 단위 쉼표만)
   합의 · 건물 · 변동 분석 · 신뢰 확인 · 근거 칩 · 안내
   ══════════════════════════════════════════════════════ */
import { useState } from 'react';
import { cx, won, kwh, pct, ymTxt, isNum } from '../../core/format.js';
import { KIND, saveMe } from '../../core/assist.js';
import { Badge, BuddyBody, Button, Icon, Mark, StatusBadge } from '../ui.jsx';
import { useAssist } from './context.js';

/* 쉼표만 붙이고 소수는 그대로 (0.655 → 0.655, 18.7 → 18.7) */
export const numTxt = v => (isNum(v) ? Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 3 }) : '—');
const sqm = n => `${numTxt(n)}\u00A0㎡`;

/* ── 근거 칩 · 누르면 그 단계로 (PC 는 화면을 옮기지 않으니 값만) ── */
export function Facts({ facts }) {
  const a = useAssist();
  if (!facts?.length) return null;
  return (
    <div className="as-facts">
      {facts.map((f, i) => {
        const k = KIND[f.kind] || { text: '값', tone: 'gray', mark: 'unknown' };
        const body = (
          <>
            <Badge tone={k.tone} mark={k.mark}>{k.text}</Badge>
            <span className="as-fact-k">{f.label}</span>
            <b className="num">{numTxt(f.value)}{f.unit ? ` ${f.unit}` : ''}</b>
          </>
        );
        return f.goto && !a.stay
          ? <button key={i} type="button" className="as-fact" onClick={() => a.go(f.goto)}>{body}<Icon name="right" size={14} stroke={2.4} /></button>
          : <span key={i} className="as-fact">{body}</span>;
      })}
    </div>
  );
}

export function Notices({ list }) {
  if (!list?.length) return null;
  return <div className="as-notes">{list.map((n, i) => <p key={i}><Icon name="info" size={15} />{n}</p>)}</div>;
}

/* ── 🤝 합의 카드 (요구서 4-2) ── 두 장을 나란히, 줄마다 기본 추정 · 낮을 때 */
function Line({ k, d, ok, viewer }) {
  const a = <span className="mc-a num">{numTxt(d?.payback_years)}년 회수</span>;
  const b = <span className="mc-b num">{viewer === 'tenant' ? '월' : '세입자 월'} {won(d?.tenant_monthly_won)}원</span>;
  return (
    <div className="mc-line">
      <span className="mc-k">{k}{ok === false && <Badge tone="red" mark="hold">목표 초과</Badge>}</span>
      {viewer === 'tenant' ? <>{b}{a}</> : <>{a}{b}</>}
    </div>
  );
}

export function MediateCard({ data, viewer, building }) {
  const a = useAssist();
  const [sel, setSel] = useState(data.pick || data.options?.[0]?.key);
  if (!data.feasible) return <Alternatives data={data} />;
  const o = data.options.find(x => x.key === sel) || data.options[0];
  const cond = { ratio: o.owner_ratio, invest: data.invest_won, years: data.target_years };
  // 가장 마지막 합의 카드에만 만세 새싹을 둔다 (카드마다 3D 를 켜지 않게)
  const newest = [...(a?.msgs || [])].reverse().find(m => m.role === 'ai' && m.res?.data?.options)?.res.data === data;
  return (
    <div className="mc">
      {newest && (
        <div className="mc-done">
          <BuddyBody w={52} live mood="cheer" />
          <div><b>합의안이 나왔어요</b><span>안을 눌러 비교하고, 마음에 드는 걸 고르세요</span></div>
        </div>
      )}
      <div className="mc-cards" role="radiogroup" aria-label="합의안">
        {data.options.map(x => (
          <button key={x.key} type="button" role="radio" aria-checked={x.key === sel} className="mc-card" onClick={() => setSel(x.key)}>
            <span className="mc-h">
              <span className="mc-l">{x.label}</span>
              <span className="mc-r"><b className="num">{pct(x.owner_ratio)}</b><span>건물주 몫</span></span>
            </span>
            <Line k="기본 추정일 때" d={x.base} ok={x.meets_target_base} viewer={viewer} />
            <Line k="절감액이 낮을 때" d={x.low} ok={x.meets_target_low} viewer={viewer} />
          </button>
        ))}
      </div>
      <div className="mc-act">
        <Button variant="gray" size="m" onClick={() => a.applyAlloc(cond, { to: 'draft', ai: true, building })}>{a.stay ? '특약에 반영' : '특약 만들기'}</Button>
        <Button size="m" onClick={() => a.applyAlloc(cond, { building })}>{a.stay ? '이 조건 적용' : '이 조건으로 보기'}</Button>
      </div>
    </div>
  );
}

/* 회수가 안 되는 조건 → 대안 버튼 (문구와 숫자는 서버 응답, 다시 묻는 말만 화면이 만든다) */
function Alternatives({ data }) {
  const a = useAssist();
  const alts = data.alternatives || [];
  if (!alts.length) return null;
  const msg = x => (x.type === 'longer'
    ? `공사비 ${won(data.invest_won)}원, ${x.years}년`
    : `공사비 ${won(x.max_invest_won)}원, ${data.target_years}년`);
  return (
    <div className="alts">
      {alts.map((x, i) => (
        <div key={i} className="alt">
          <p>{x.text}</p>
          <Button variant="weak" size="s" onClick={() => a.send(msg(x))}>
            {x.type === 'longer' ? `기간 ${x.years}년으로` : '공사비 줄여서'} 다시 계산
          </Button>
        </div>
      ))}
    </div>
  );
}

/* ── 🏢 건물 후보 (요구서 3-2) ── 맞아요 → 조회. 연 건물은 묻지 않고 이 기기에만 기억 */
export function ResolveCard({ data, S, entry, onEnter }) {
  const a = useAssist();
  const [st, setSt] = useState('ask');           // ask · busy · opened · no
  const c = data.candidates?.[0];
  if (data.result !== 'matched' || !c) return null;      // 못 찾은 경우의 다음 길은 추천 칩으로
  const [picked, setPicked] = useState(null);
  const many = data.candidates.length > 1;
  const one = many ? (picked || data.candidates.find(x => x.bld_id === S.bld.data?.bld_id)) : c;
  const sim = one?.data_origin?.is_simulated;
  // 화면이 바뀌어 다시 그려져도 이미 연 건물이면 열린 상태로
  const opened = st === 'opened' || (st === 'ask' && one && S.bld.data?.bld_id === one.bld_id);
  const yes = async x => {
    const b = x || c;
    setPicked(b);
    setSt('busy');
    S.setCodes(b.codes);
    S.setAddress(b.addr);
    const ok = await S.lookup(b.codes);
    if (ok) saveMe({ address: b.addr, codes: b.codes, bld_id: b.bld_id });
    setSt(ok ? 'opened' : 'ask');
    if (!ok) a.push({ role: 'error', text: '건물을 열지 못했어요' });
  };
  if (many && !opened) {
    return (
      <div className="bc-list" role="list">
        {data.candidates.map(x => (
          <button key={x.bld_id} type="button" role="listitem" className="bc-row" disabled={st === 'busy'} onClick={() => yes(x)}>
            <span className="bc-ic"><Icon name="building" size={18} /></span>
            <span className="bc-t"><b>{x.addr}</b><span>{x.purpose} · {sqm(x.area)}</span></span>
            {x.data_origin?.is_simulated && <Badge tone="purple">가상 데이터</Badge>}
            {st === 'busy' && picked?.bld_id === x.bld_id ? <i className="dots" aria-hidden="true"><i /><i /><i /></i> : <Icon name="right" size={18} />}
          </button>
        ))}
      </div>
    );
  }
  return (
    <div className={cx('bc', sim && 'sim')}>
      <div className="bc-top">
        <span className="bc-ic"><Icon name="building" size={20} /></span>
        <span className="bc-t">
          <b>{one.addr}</b>
          <span>{one.purpose} · {sqm(one.area)}</span>
        </span>
        {sim && <Badge tone="purple">가상 데이터</Badge>}
      </div>
      {!opened && (st === 'ask' || st === 'busy') ? (
        <div className="bc-act">
          <Button variant="gray" size="m" disabled={st === 'busy'} onClick={() => { setSt('no'); a.push({ role: 'ai', text: '다른 주소나 건물 이름을 알려 주세요.' }); }}>아니에요</Button>
          <Button size="m" loading={st === 'busy'} onClick={() => yes(c)}>맞아요</Button>
        </div>
      ) : opened ? (
        entry
          ? <Button block size="m" onClick={onEnter}>이 건물로 시작하기</Button>
          : <Button variant="gray" block size="m" onClick={() => a.go('bld', { explicit: true })}>건물 정보 보기</Button>
      ) : null}
    </div>
  );
}

/* ── 🔎 변동 분석 (요구서 3-3) ── 비교 해가 바뀌면 노란 띠 */
export function AnalyzeCard({ data }) {
  if (!data?.available) {
    return data?.last_data_ym ? <div className="badges"><Badge tone="gray" mark="none">데이터 없음 · 최근 {ymTxt(data.last_data_ym)}</Badge></div> : null;
  }
  const f = data.by_fuel || {};
  const FUEL = [['elec', '전기'], ['gas', '가스']];
  return (
    <div className="an">
      {data.ref_note && <div className="an-warn" role="note"><Icon name="alert" size={18} />{data.ref_note}</div>}
      <div className="an-pair">
        <div><span>{ymTxt(data.ref_ym)}</span><b className="num">{kwh(data.ref_actual_kwh)}</b><em>kWh</em></div>
        <Icon name="right" size={18} />
        <div className="now"><span>{ymTxt(data.ym)}</span><b className="num">{kwh(data.actual_kwh)}</b><em>kWh</em></div>
      </div>
      <div className="rows lined">
        <div className="row"><span className="row-k">달라진 양</span><span className="row-v num">{kwh(data.change_kwh)} kWh</span></div>
        <div className="row"><span className="row-k">기온 영향<Badge tone="blue" mark="prov">모델 예측</Badge></span><span className="row-v num">{kwh(data.weather_kwh)} kWh</span></div>
        <div className="row"><span className="row-k">기온 외 요인<Badge tone="blue" mark="prov">모델 예측</Badge></span><span className="row-v num">{kwh(data.other_kwh)} kWh</span></div>
        {FUEL.filter(([k]) => Array.isArray(f[k])).map(([k, n]) => (
          <div key={k} className="row"><span className="row-k">{n} 실측</span><span className="row-v num">{kwh(f[k][0])} → {kwh(f[k][1])} kWh</span></div>
        ))}
      </div>
      {data.survey?.length > 0 && (
        <div className="an-survey">
          <p>현장에서 확인해 보세요</p>
          <ul>{data.survey.map(x => <li key={x}><Mark k="unknown" />{x}</li>)}</ul>
        </div>
      )}
    </div>
  );
}

/* ── 🛡 신뢰 확인 ── 정산 상태 + 예측 지표 */
export function TrustCard({ data }) {
  if (!data) return null;
  const mc = data.metric_checks || {};
  const rows = [['예측 오차', mc.cv_rmse, '%'], ['평균 편향', mc.nmbe, '%'], ['설명력', mc.r2, '']].filter(r => r[1]);
  return (
    <div className="tc">
      {data.status_code && <div className="badges"><StatusBadge code={data.status_code} lg={false} /></div>}
      {rows.length > 0 && (
        <div className="rows lined">
          {rows.map(([k, c, u]) => (
            <div key={k} className="row">
              <span className="row-k">{k}<span className="tc-lim">기준 {c.limit}{u}</span></span>
              <span className="row-v"><span className="num">{numTxt(c.value)}{u}</span><Badge tone={c.ok ? 'green' : 'amber'}>{c.ok ? '충족' : '범위 제시'}</Badge></span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
