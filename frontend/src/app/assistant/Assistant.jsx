/* ══════════════════════════════════════════════════════
   세이빙 AI 대화창 — 모바일 시트 · PC 오른쪽 칸 · 처음 화면 공용
   위에서 아래로: 머리(관점 토글) → 말풍선 → 추천 질문 → [🎤][입력][보내기]
   ══════════════════════════════════════════════════════ */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { cx } from '../../core/format.js';
import { chipOf, chipsFor } from '../../core/assist.js';
import { agreeVoice, speechOk, useSpeech, voiceAgreed, VOICE_TOAST } from '../../core/useSpeech.js';
import { Badge, BuddyBody, BuddyFace, Button, Icon, Info, usePulse } from '../ui.jsx';
import { useAssist } from './context.js';
import { AnalyzeCard, Facts, MediateCard, ResolveCard, TrustCard } from './cards.jsx';
import { Thinking } from './Thinking.jsx';

/* 분석 종류마다 진행 단계 (요구서 숫자와 무관한 표시 문구) */
export const PLAN = {
  start: { title: '질문을 읽고 있어요', steps: ['질문 읽기', '데이터 확인', '답 정리'], from: 'search' },
  mediate: { title: '건물주와 세입자 몫을 계산하고 있어요', steps: ['조건 읽기', '두 가지 안 계산', '회수 기간 확인'], from: 'building' },
  analyze: { title: '기온 영향과 다른 요인을 나누고 있어요', steps: ['실측 사용량 확인', '기온 영향 계산', '원인 정리'], from: 'building' },
  trust: { title: '예측 지표를 확인하고 있어요', steps: ['정산 상태 확인', '예측 오차 확인', '설명력 확인'], from: 'building' },
  resolve: { title: '건물을 찾고 있어요', steps: ['주소 읽기', '등록 건물 찾기'], from: 'search' },
  clarify: { title: '질문을 읽고 있어요', steps: [], from: 'search' },
};

export function ViewerToggle({ S }) {
  return (
    <div className="segbar sm as-view" role="radiogroup" aria-label="설명 관점">
      {[['owner', '건물주'], ['tenant', '세입자']].map(([v, t]) => (
        <button key={v} type="button" role="radio" aria-checked={S.viewer === v} onClick={() => S.setViewer(v)}>{t}</button>
      ))}
    </div>
  );
}

/* 머리글 새싹: 답을 기다리면 생각 중 · 답이 오면 인사 · 오류면 놀람 */
export function AiTitle() {
  const a = useAssist();
  const msgs = a?.msgs || [];
  const answered = msgs.filter(m => m.role === 'ai' && m.res && !m.pending).length;
  const failed = msgs.filter(m => m.role === 'error').length;
  const hi = usePulse(answered, 'wave');
  const yay = usePulse(a?.cheerKey || null, 'cheer');
  const oops = usePulse(failed, 'surprise');
  const mood = a?.busy ? 'think' : oops || yay || hi || 'idle';
  return <span className="as-title"><span className="as-av face sprout3d"><BuddyBody w={36} live mood={mood} /></span>세이빙 AI</span>;
}

/* 아직 답이 오지 않았거나 최소 시간이 지나지 않은 답 */
function Pending({ m }) {
  const plan = PLAN[m.res?.intent] || PLAN.start;
  const [now, setNow] = useState(() => performance.now());
  useEffect(() => {
    const t = setInterval(() => setNow(performance.now()), 160);
    return () => clearInterval(t);
  }, []);
  const n = plan.steps.length;
  const done = n ? Math.min(n - 1, Math.floor(((now - m.t0) / (m.min || 4000)) * n)) : 0;
  return <div className="as-ai"><Thinking title={plan.title} steps={plan.steps} done={done} from={plan.from} /></div>;
}

function Answer({ m, S, entry, onEnter }) {
  const r = m.res;
  const d = r.data;
  const text = r.intent === 'mediate' && d && (d.reply_owner || d.reply_tenant)
    ? (S.viewer === 'tenant' ? d.reply_tenant : d.reply_owner) || r.reply : r.reply;
  const simulated = (r.intent === 'mediate' && !!d) || (r.facts || []).some(f => f.kind === 'simulated');
  const virtual = S.sim && ['mediate', 'analyze', 'trust', 'carbon', 'measures', 'support', 'rent', 'settle'].includes(r.intent);
  let card = null;
  if (d && r.intent === 'mediate' && (d.options || d.alternatives)) card = <MediateCard data={d} viewer={S.viewer} building={r.building} />;
  else if (d && r.intent === 'resolve') card = <ResolveCard data={d} S={S} entry={entry} onEnter={onEnter} />;
  else if (d && r.intent === 'analyze') card = <AnalyzeCard data={d} />;
  else if (d && r.intent === 'trust') card = <TrustCard data={d} />;
  return (
    <div className="as-ai as-in">
      {(r.tag || simulated || virtual || r.notices?.length > 0) && (
        <div className="as-meta">
          {r.tag && <span className="as-tag">{noEmoji(r.tag)}</span>}
          {simulated && <Badge tone="amber" mark="sim">예상 금액</Badge>}
          {virtual && <Badge tone="purple">가상 데이터</Badge>}
          {r.notices?.length > 0 && <Info label="유의사항 보기">{r.notices.map((x, i) => <p key={i}>{x}</p>)}</Info>}
        </div>
      )}
      {r.filled && <p className="as-filled"><Icon name="check" size={14} stroke={2.6} />{r.filled}</p>}
      {text && <p className="as-text">{text}</p>}
      {card}
      {/* 분석·신뢰 카드는 근거 숫자를 이미 보여준다 → 칩 대신 그 화면으로 가는 한 줄 */}
      {card && (r.intent === 'analyze' || r.intent === 'trust') && r.facts?.length > 0
        ? <GotoRow to={r.facts.find(f => f.goto)?.goto} />
        : <Facts facts={r.facts} />}
      {r.source === 'external_ai' && <p className="as-ext">외부 AI 사용</p>}
    </div>
  );
}

const noEmoji = t => String(t).replace(/[\p{Extended_Pictographic}\uFE0F\u200D]/gu, '').trim();
const STEP_NAME = { bld: '건물', elig: '대상 판정', prof: '건축물 진단', meas: '개선 대책', base: '기저선', alloc: '분배', setl: '정산 리포트', draft: '특약' };
function GotoRow({ to }) {
  const a = useAssist();
  if (!to || !STEP_NAME[to]) return null;
  return (
    <button type="button" className="as-goto" onClick={() => a.go(to)}>
      {STEP_NAME[to]} 화면에서 보기<Icon name="right" size={16} />
    </button>
  );
}

function Msg({ m, S, entry, onEnter }) {
  const a = useAssist();
  if (m.role === 'user') return <div className="as-me"><p>{m.text}</p></div>;
  if (m.role === 'note') return <p className="as-sys"><Icon name="check-fill" size={15} />{m.text}</p>;
  if (m.role === 'error') {
    return (
      <div className="as-ai as-in">
        <div className="as-errbox" role="alert">
          <p>{m.text}</p>
          {m.retry && <Button variant="gray" size="s" onClick={() => a.send(m.retry)}>다시 시도</Button>}
        </div>
      </div>
    );
  }
  if (m.pending) return <Pending m={m} />;
  if (m.res) return <Answer m={m} S={S} entry={entry} onEnter={onEnter} />;
  return (
    <div className="as-ai as-in">
      <p className="as-text">{m.text}</p>
      {m.notices?.length > 0 && <div className="as-meta"><Info label="유의사항 보기">{m.notices.map((x, i) => <p key={i}>{x}</p>)}</Info></div>}
    </div>
  );
}

/* 처음 열었을 때 · 이렇게 물어보세요 (모드 고르기가 아니라 예시 질문) */
function Hello({ chips, entry, onPick }) {
  return (
    <div className="as-hello as-in">
      <div className="as-hello-top"><BuddyBody w={72} live mood="wave" /><h3>무엇을 도와드릴까요?</h3></div>
      <ul className="as-ex">
        {chips.map(c => {
          const x = chipOf(c);
          return <li key={x.label}><button type="button" onClick={() => onPick(x)}><Icon name="sparkle" size={15} /><span>{x.label}</span><Icon name="right" size={16} /></button></li>;
        })}
      </ul>
      {entry && (
        <ul className="as-must">
          <li><Badge tone="amber" mark="sim">예상 금액</Badge>공사 전 금액은 예상 금액이에요</li>
          <li><Badge tone="gray" mark="none">4개월 지연</Badge>공공데이터는 공개까지 약 4개월 걸려요</li>
        </ul>
      )}
    </div>
  );
}

/* 휴대폰 키보드가 올라오면 그만큼 비켜선다 (iOS 는 화면이 줄지 않아 직접 잰다) */
function useKeyboardInset(on) {
  useEffect(() => {
    const vv = window.visualViewport;
    if (!on || !vv) return undefined;
    const r = document.documentElement;
    const f = () => r.style.setProperty('--kb', `${Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop))}px`);
    f();
    vv.addEventListener('resize', f);
    vv.addEventListener('scroll', f);
    return () => { vv.removeEventListener('resize', f); vv.removeEventListener('scroll', f); r.style.removeProperty('--kb'); };
  }, [on]);
}

export function Assistant({ S, variant = 'sheet', onClose, entry, onEnter, onBack, step }) {
  const a = useAssist();
  useKeyboardInset(variant !== 'panel');
  const log = useRef(null);
  const input = useRef(null);
  const down = S.conn.mode === 'backup' || S.conn.status === 'down';
  const sp = useSpeech(t => a.setDraft(d => (d ? `${d} ${t}` : t)));
  const last = [...a.msgs].reverse().find(m => m.role === 'ai' && m.res && !m.pending);
  const chips = (last?.res?.chips?.length ? last.res.chips : chipsFor(step)).slice(0, 3);
  const pending = a.msgs.some(m => m.pending);

  // 새 말이 오면 맨 아래를 보여 준다
  const n = a.msgs.length;
  const sig = a.msgs.map(m => (m.pending ? 'p' : 'r')).join('');
  const stick = useRef(true);
  useLayoutEffect(() => {
    const el = log.current;
    if (el) { el.scrollTop = el.scrollHeight; stick.current = true; }
  }, [n, sig]);
  // 맨 아래를 보던 중이면, 내용·입력창 높이가 바뀌어도 맨 아래에 붙어 있게
  useEffect(() => {
    const el = log.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const onScroll = () => { stick.current = el.scrollHeight - el.clientHeight - el.scrollTop < 24; };
    const pin = () => { if (stick.current) el.scrollTop = el.scrollHeight; };
    const ro = new ResizeObserver(pin);
    ro.observe(el);
    const watch = () => { Array.from(el.children).forEach(ch => ro.observe(ch)); };
    watch();
    const mo = new MutationObserver(() => { watch(); pin(); });
    mo.observe(el, { childList: true, subtree: true });
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => { ro.disconnect(); mo.disconnect(); el.removeEventListener('scroll', onScroll); };
  }, []);
  // 입력창 · 글자가 늘면 높아지고 120px에서 멈춘다
  const grow = () => { const el = input.current; if (!el) return; el.style.height = 'auto'; el.style.height = `${Math.min(el.scrollHeight, 120)}px`; };
  useLayoutEffect(grow, [a.draft, sp.interim, sp.on]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = e => {
    e?.preventDefault();
    if (down || pending) return;
    a.send(a.draft);
  };
  // 칩: 보내는 것과 입력창에 넣어 주는 것(fill)
  const pick = x => {
    if (pending) return;
    if (x.fill != null || !x.message) {
      a.setDraft(x.fill || '');
      setTimeout(() => { const el = input.current; if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } }, 30);
      return;
    }
    a.send(x.message);
  };
  // 처음 한 번은 막지 않고 알림으로 고지 (요구서 4-3)
  const mic = () => {
    if (!voiceAgreed()) { agreeVoice(); a.showToast({ text: VOICE_TOAST }); }
    sp.toggle();
  };

  return (
    <div className={cx('as', `as-in-${variant}`)}>
      {variant !== 'sheet' && (
        <header className="as-head">
          {onBack && <button type="button" className="icon-btn" aria-label="직접 설정하기로 돌아가기" onClick={onBack}><Icon name="left" size={22} /></button>}
          <AiTitle />
          <ViewerToggle S={S} />
          {onClose && <button type="button" className="icon-btn as-x" aria-label="세이빙 AI 닫기" onClick={onClose}><Icon name="close" size={20} /></button>}
        </header>
      )}
      <div className="as-log" ref={log}>
        {a.msgs.length === 0
          ? <Hello chips={chipsFor(step)} entry={entry} onPick={pick} />
          : a.msgs.map(m => <Msg key={m.id} m={m} S={S} entry={entry} onEnter={onEnter} />)}
      </div>
      <div className="as-foot">
        {a.msgs.length > 0 && !pending && (
          <div className="as-chips" role="list" aria-label="추천 질문">
            {chips.map(c => {
              const x = chipOf(c);
              return <button key={x.label} type="button" role="listitem" className={cx('chip', x.fill != null && 'fill')} onClick={() => pick(x)}>{x.label}</button>;
            })}
          </div>
        )}
        <form className={cx('as-input', down && 'off', sp.on && 'rec')} onSubmit={submit}>
          {speechOk && !down && (
            <button type="button" className={cx('as-mic', sp.on && 'on')} aria-label={sp.on ? '음성 입력 멈추기' : '음성으로 입력'} aria-pressed={sp.on} onClick={mic}>
              <Icon name="mic" size={20} />
            </button>
          )}
          <textarea ref={input} rows={1} className={cx(sp.on && 'interim')} value={sp.on ? sp.interim : a.draft} readOnly={sp.on}
            onChange={e => { sp.clearError(); a.setDraft(e.target.value); }} disabled={down}
            placeholder={down ? '서버 연결 시 대화할 수 있어요' : sp.on ? '듣고 있어요…' : '궁금한 걸 말해 보세요'}
            aria-label="세이빙 AI에게 보낼 말" enterKeyHint="send" autoComplete="off"
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit(); } }} />
          <button type="submit" className={cx('as-send', pending && 'busy')} aria-label="보내기" disabled={down || pending || !a.draft.trim()}>
            {pending ? <i className="dots" aria-hidden="true"><i /><i /><i /></i> : <Icon name="up" size={20} stroke={2.4} />}
          </button>
        </form>
        {sp.error && <p className="as-hint red" role="alert">{sp.error}</p>}
      </div>
    </div>
  );
}
