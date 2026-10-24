/* 화면 부품. 모양만 만들고 값은 바꾸지 않는다. */
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { cx, koMoney, won } from '../core/format.js';
import { CODE_FIELDS } from '../core/domain.js';
import { useBigText } from '../core/hooks.js';
import { enterBackup, leaveBackup } from '../core/client.js';
import { useAssist } from './assistant/context.js';
import buddyFace from '../assets/buddy-face.png';
import buddyBody from '../assets/buddy.png';
import { mountBuddy } from './buddy3d.js';

/* ── 아이콘 (24 격자) ── */
const PATHS = {
  down: 'M6 9l6 6 6-6',
  right: 'M9 6l6 6-6 6',
  left: 'M15 5l-7 7 7 7',
  close: 'M6 6l12 12M18 6L6 18',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  minus: 'M6 12h12',
  plus: 'M12 6v12M6 12h12',
  list: 'M9 7h10M9 12h10M9 17h10M5 7h.01M5 12h.01M5 17h.01',
  sliders: 'M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4',
  search: 'M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13zM15.5 15.5L20 20',
  building: 'M5 20V5.5A1.5 1.5 0 0 1 6.5 4h7A1.5 1.5 0 0 1 15 5.5V20M15 10h3.5a1.5 1.5 0 0 1 1.5 1.5V20M3.5 20h17M8.5 8h3M8.5 12h3M8.5 16h3',
  collapse: 'M6 6l6 6-6 6M13 6l6 6-6 6',
  expand: 'M18 6l-6 6 6 6M11 6l-6 6 6 6',
  panel: 'M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5zM4 9.5h16',
  sun: 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2.5v2M12 19.5v2M4.6 4.6l1.4 1.4M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z',
  mic: 'M12 15a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zM18.5 11a6.5 6.5 0 0 1-13 0M12 17.5V21',
  up: 'M12 19V5.5M5.5 12L12 5.5 18.5 12',
  trash: 'M4.5 7h15M10 11v5.5M14 11v5.5M6.5 7l.8 11.2A2 2 0 0 0 9.3 20h5.4a2 2 0 0 0 2-1.8L17.5 7M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2',
  copy: 'M9 9h9.5A1.5 1.5 0 0 1 20 10.5v9a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 8 19.5v-9A1.5 1.5 0 0 1 9.5 9zM16 9V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8',
};
const FILLED = {
  sparkle: 'M12 2.8c.55 4.75 2.95 7.15 7.7 7.7-4.75.55-7.15 2.95-7.7 7.7-.55-4.75-2.95-7.15-7.7-7.7 4.75-.55 7.15-2.95 7.7-7.7z',
  megaphone: 'M3.5 9.6A1.6 1.6 0 0 1 5.1 8h2.6l7.1-3.9a.8.8 0 0 1 1.2.7v14.4a.8.8 0 0 1-1.2.7L7.7 16H7l.9 3.3a1 1 0 0 1-1 1.2H6a1 1 0 0 1-1-.8L4.2 16a1.6 1.6 0 0 1-.7-1.3z',
};
export function Icon({ name, size = 20, stroke = 2, className }) {
  if (FILLED[name]) {
    return (
      <svg className={className} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
        <path d={FILLED[name]} fill="currentColor" />
        {name === 'megaphone' && <path d="M18.6 9.4a3.6 3.6 0 0 1 0 5.2" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />}
      </svg>
    );
  }
  if (name === 'check-fill' || name === 'x-fill') {
    return (
      <svg className={className} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="10" fill="currentColor" />
        {name === 'check-fill'
          ? <path d="M7.5 12.3l3 3 6-6.3" fill="none" stroke="var(--surface)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          : <path d="M8.5 8.5l7 7M15.5 8.5l-7 7" fill="none" stroke="var(--surface)" strokeWidth="2.2" strokeLinecap="round" />}
      </svg>
    );
  }
  if (name === 'info' || name === 'alert') {
    return (
      <svg className={className} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth={stroke} />
        {name === 'info'
          ? <><circle cx="12" cy="8.1" r="1.15" fill="currentColor" /><path d="M12 11.2v5.6" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" /></>
          : <><path d="M12 7.4v5.6" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" /><circle cx="12" cy="16.3" r="1.15" fill="currentColor" /></>}
      </svg>
    );
  }
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d={PATHS[name]} fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* 상태 기호 (12px). 색만으로 구분하지 않도록 모양도 다르게 */
const MARK = {
  sim: <circle cx="6" cy="6" r="4.2" fill="none" stroke="currentColor" strokeWidth="1.6" strokeDasharray="2.2 1.8" />,
  prov: <><circle cx="6" cy="6" r="4.2" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M6 1.8a4.2 4.2 0 0 1 0 8.4z" fill="currentColor" /></>,
  fix: <path d="M2.4 6.3l2.3 2.3 4.9-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />,
  hold: <path d="M4.2 2.8v6.4M7.8 2.8v6.4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />,
  none: <path d="M2.8 6h6.4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />,
  unknown: <circle cx="6" cy="6" r="2" fill="currentColor" />,
};
export const Mark = ({ k, size = 12 }) => (
  <svg width={size} height={size} viewBox="0 0 12 12" aria-hidden="true">{MARK[k] || MARK.unknown}</svg>
);

/* 팀 아이콘 (web/icon.svg 와 같은 모양) */
export const BrandMark = ({ size = 28 }) => (
  <svg className="brand-mark" width={size} height={size} viewBox="0 0 100 100" aria-hidden="true"><defs><linearGradient id="bm-a2" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#4CC9B0"/><stop offset="1" stopColor="#238F7C"/></linearGradient>
<linearGradient id="bm-b2" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#C9EE55"/><stop offset="1" stopColor="#8FCB2E"/></linearGradient>
<clipPath id="bm-k2"><path d="M52 72C40 72 17 60 17 38C17 26 25 20 34 20C46 20 53 40 52 72Z"/></clipPath></defs><defs><linearGradient id="bm-bgm" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#F4FBDD"/><stop offset="1" stopColor="#D9F2E6"/></linearGradient></defs><rect width="100" height="100" rx="26" fill="url(#bm-bgm)"/>
<g transform="translate(50,50) scale(1) translate(-50,-52)"><path d="M50 68V84" stroke="#8FCB2E" strokeWidth="6" strokeLinecap="round"/>
<path d="M52 72C40 72 17 60 17 38C17 26 25 20 34 20C46 20 53 40 52 72Z" fill="url(#bm-a2)"/><g transform="translate(100,0) scale(-1,1)"><path d="M52 72C40 72 17 60 17 38C17 26 25 20 34 20C46 20 53 40 52 72Z" fill="url(#bm-b2)"/></g>
<g clipPath="url(#bm-k2)"><g transform="translate(100,0) scale(-1,1)"><path d="M52 72C40 72 17 60 17 38C17 26 25 20 34 20C46 20 53 40 52 72Z" fill="#1B7F6C"/></g></g></g></svg>
);

/* ── 연결 상태 ── 실제 상태와 같은 말만 쓴다 */
export function connInfo(c) {
  if (c.mode === 'backup') {
    return { tone: 'amber', text: `저장된 시연 데이터 · ${c.stampTime} 기준`,
      action: c.canReconnect ? { label: '실시간으로 보기', run: leaveBackup } : null };
  }
  if (c.status === 'down') {
    return { tone: 'red', text: '서버에 연결할 수 없어요',
      action: c.hasBackup ? { label: '저장본 보기', run: enterBackup } : null };
  }
  if (c.status === 'up') return { tone: 'green', text: '서버 연결됨', action: null };
  return { tone: 'gray', text: '연결 확인 중', action: null };
}

/* ── 단추 ── */
export function Button({ variant = 'primary', size, block, loading, className, children, ...rest }) {
  return (
    <button type="button" className={cx('btn', `btn-${variant}`, size && `btn-${size}`, block && 'block', loading && 'loading', className)}
      aria-busy={loading || undefined} {...rest}>
      {loading && <i className="dots" aria-hidden="true"><i /><i /><i /></i>}
      <span>{children}</span>
    </button>
  );
}

/* ── 큰 글씨 켜고 끄기 · 눈에 띄는 글자 버튼 ── */
export function BigTextBtn({ className }) {
  const [big, toggle] = useBigText();
  return (
    <button type="button" className={cx('big-btn', big && 'on', className)} aria-pressed={big} onClick={toggle}
      aria-label={big ? '글씨를 기본 크기로' : '글씨를 크게'}>
      <b>가</b><span>{big ? '기본 글씨' : '큰 글씨'}</span>
    </button>
  );
}

/* ── 꼬리표 ── */
export const Badge = ({ tone = 'gray', lg, mark, children, title }) => (
  <span className={cx('badge', tone, lg && 'lg')} title={title}>{mark && <Mark k={mark} />}{children}</span>
);

/* 정산 상태 (status_code) · 요청서 문구 그대로 */
const STATUS_TEXT = {
  ESTIMATED: { text: '예상 금액 · 실제 정산 아님', tone: 'amber', mark: 'sim' },
  PROVISIONAL: { text: '잠정', tone: 'blue', mark: 'prov' },
  VERIFIED: { text: '검증 완료', tone: 'green', mark: 'fix' },
  REVIEW_REQUIRED: { text: '검토 필요 · 정산 보류', tone: 'red', mark: 'hold' },
  INSUFFICIENT_DATA: { text: '데이터 없음 · 정산 불가', tone: 'gray', mark: 'none' },
};
export const statusText = (code, fallback) => STATUS_TEXT[code] || { text: fallback || '상태 미상', tone: 'gray', mark: 'unknown' };
export function StatusBadge({ code, fallback, lg = true }) {
  const s = statusText(code, fallback);
  return <Badge tone={s.tone} mark={s.mark} lg={lg}>{s.text}</Badge>;
}

/* AI 설명 action · 한국어 값 그대로, 모르는 값은 회색 */
const ACTION_TONE = {
  '시뮬레이션': { tone: 'amber', mark: 'sim' },
  '예상치': { tone: 'amber', mark: 'sim' },
  '잠정 정산': { tone: 'blue', mark: 'prov' },
  '금액 확정': { tone: 'green', mark: 'fix' },
  '확정 보류': { tone: 'red', mark: 'hold' },
  '데이터 없음': { tone: 'gray', mark: 'none' },
};
export function ActionBadge({ action }) {
  const a = ACTION_TONE[action] || { tone: 'gray', mark: 'unknown' };
  return <Badge tone={a.tone} mark={a.mark}>{action || '분류 없음'}</Badge>;
}

/* 월별 판정 (months[].state) */
export function monthBadge(state, code) {
  if (state === '정산') {
    if (code === 'PROVISIONAL') return { text: '잠정', tone: 'blue', mark: 'prov' };
    if (code === 'VERIFIED') return { text: '검증 완료', tone: 'green', mark: 'fix' };
    return { text: '예상 금액', tone: 'amber', mark: 'sim' };
  }
  if (state === '확인 중') return { text: '확인 중 · 금액 제외', tone: 'red', mark: 'hold' };
  if (state === '데이터 없음') return { text: '데이터 없음', tone: 'gray', mark: 'none' };
  return { text: state || '상태 미상', tone: 'gray', mark: 'unknown' };
}

/* ── 값 줄 ── 값 밑에 회색 줄을 달지 않는다. 덧붙일 말(sub)은 이름 옆 (i) 안에 */
export const Row = ({ k, v, sub, strong, className }) => (
  <div className={cx('row', strong && 'strong', className)}>
    <span className="row-k">{k}{sub && <Info>{sub}</Info>}</span>
    <span className="row-v num">{v}</span>
  </div>
);

/* ── 눌러야 열리는 줄 (▼) ── */
export function Fold({ title, aside, children, defaultOpen = false, className }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className={cx('fold', open && 'open', className)}>
      <button type="button" className="fold-btn" aria-expanded={open} aria-controls={id} onClick={() => setOpen(o => !o)}>
        <span className="fold-t">{title}</span>
        {aside != null && <span className="fold-a">{aside}</span>}
        <Icon name="down" size={20} />
      </button>
      <div id={id} className={cx('fold-body', open && 'open')} role="region" aria-hidden={!open}>
        <div><div className="fold-in">{children}</div></div>
      </div>
    </div>
  );
}

/* ── (i) 눌러서 보는 설명 ── 화면에는 기호만 두고 설명은 필요할 때만 */
/* ask = { q, label } 를 주면 설명 아래에 '세이빙 AI에게 물어보기' 줄이 붙는다 (모르는 순간 그 자리에서 권한다) */
export function Info({ children, label = '설명 보기', size = 18, ask }) {
  const [open, setOpen] = useState(false);
  const assist = useAssist();
  const [pos, setPos] = useState(null);
  const btn = useRef(null);
  const pop = useRef(null);
  const id = useId();
  useLayoutEffect(() => {
    if (!open) { setPos(null); return undefined; }
    const r = btn.current.getBoundingClientRect();
    const vw = document.documentElement.clientWidth, vh = window.innerHeight;
    const w = Math.min(300, vw - 32);
    const left = Math.max(16, Math.min(r.left + r.width / 2 - 26, vw - 16 - w));
    const up = r.bottom + 170 > vh && r.top > 180;
    setPos({ left, w, top: up ? r.top - 8 : r.bottom + 8, up, ax: r.left + r.width / 2 - left });
    const away = e => { if (!btn.current?.contains(e.target) && !pop.current?.contains(e.target)) setOpen(false); };
    const esc = e => { if (e.key === 'Escape') { setOpen(false); btn.current?.focus(); } };
    const off = e => { if (!pop.current?.contains(e.target)) setOpen(false); };
    const close = () => setOpen(false);
    document.addEventListener('pointerdown', away, true);
    window.addEventListener('keydown', esc);
    window.addEventListener('scroll', off, true);
    window.addEventListener('resize', close);
    return () => {
      document.removeEventListener('pointerdown', away, true);
      window.removeEventListener('keydown', esc);
      window.removeEventListener('scroll', off, true);
      window.removeEventListener('resize', close);
    };
  }, [open]);
  return (
    <span className="info">
      <button ref={btn} type="button" className="info-btn" aria-label={label} aria-expanded={open}
        aria-describedby={open ? id : undefined} onClick={() => setOpen(o => !o)}>
        <Icon name="info" size={size} stroke={1.8} />
      </button>
      {open && pos && createPortal(
        <div id={id} ref={pop} role="tooltip" className={cx('info-pop', pos.up && 'up')}
          style={{ left: pos.left, top: pos.top, maxWidth: pos.w, '--ax': `${pos.ax}px` }}>
          {children}
          {ask && assist && (
            <button type="button" className="info-ask" onClick={() => { setOpen(false); assist.ask(ask.q, { send: ask.send !== false }); }}>
              <Icon name="sparkle" size={14} />{ask.label || '세이빙 AI에게 물어보기'}<Icon name="right" size={14} stroke={2.4} />
            </button>
          )}
        </div>,
        document.body)}
    </span>
  );
}

/* ── 체크 (약관 동의 모양) ── */
export function Check({ checked, onChange, children, strong, onMore, moreLabel = '자세히 보기' }) {
  const id = useId();
  return (
    <div className={cx('ck-row', strong && 'all')}>
      <label className="ck" htmlFor={id}>
        <input id={id} type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
        <span className="ck-box" aria-hidden="true"><Icon name="check" size={15} stroke={2.8} /></span>
        <span className="ck-t">{children}</span>
      </label>
      {onMore && <button type="button" className="ck-more" aria-label={moreLabel} onClick={onMore}><Icon name="right" size={18} /></button>}
    </div>
  );
}

/* ── 두 칸 탭 (로그인 방식 고르기 모양) ── */
export function Seg2({ value, onChange, options, label }) {
  return (
    <div className="seg2" role="tablist" aria-label={label} style={{ '--n': options.length }}>
      {options.map(o => (
        <button key={o.value} type="button" role="tab" aria-selected={o.value === value} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

/* ── 하나 고르기 (칩) ── */
export function Chips({ label, value, onChange, options }) {
  const refs = useRef({});
  useEffect(() => {
    const el = refs.current[value];
    const box = el?.parentElement;
    if (!el || !box || box.scrollWidth <= box.clientWidth) return;
    box.scrollTo({ left: el.offsetLeft - (box.clientWidth - el.offsetWidth) / 2, behavior: reduced() ? 'auto' : 'smooth' });
  }, [value]);
  const move = (e, i) => {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = options[(i + d + options.length) % options.length];
    onChange(next.value);
    refs.current[next.value]?.focus();
  };
  return (
    <div className="chips" role="radiogroup" aria-label={label}>
      {options.map((o, i) => (
        <button key={o.value} ref={el => { refs.current[o.value] = el; }} type="button" role="radio" className="chip"
          data-chip={o.value} aria-checked={o.value === value} tabIndex={o.value === value ? 0 : -1}
          onKeyDown={e => move(e, i)} onClick={() => onChange(o.value)}>{o.label}</button>
      ))}
    </div>
  );
}

export function Switch({ checked, onChange, label, disabled }) {
  return (
    <button type="button" role="switch" className="sw" aria-checked={checked} aria-label={label} disabled={disabled}
      onClick={() => onChange(!checked)} />
  );
}

/* ── 입력칸 ── */
export function Field({ label, value, onChange, error, hint, unit, inputRef, disabled, className, ...rest }) {
  const id = useId();
  const msg = error || hint;
  return (
    <div className={cx('field', error && 'bad', disabled && 'off', className)}>
      <label htmlFor={id} className="field-l">{label}</label>
      <div className="field-box">
        <input id={id} ref={inputRef} value={value ?? ''} onChange={e => onChange(e.target.value)} disabled={disabled}
          autoComplete="off" spellCheck={false} aria-invalid={error ? true : undefined}
          aria-describedby={msg ? `${id}-m` : undefined} {...rest} />
        {unit && <span className="field-u">{unit}</span>}
      </div>
      {msg !== undefined && <span id={`${id}-m`} className={cx('field-m', error && 'err')}>{msg || ''}</span>}
    </div>
  );
}

/* 테두리 입력칸 · 글자가 들어가면 이름이 위로 올라간다 */
export function LineField({ label, value, onChange, error, inputRef, ...rest }) {
  const id = useId();
  return (
    <div className={cx('lf', error && 'bad')}>
      <input id={id} ref={inputRef} placeholder=" " value={value ?? ''} onChange={e => onChange(e.target.value)}
        autoComplete="off" spellCheck={false} aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-e` : undefined} {...rest} />
      <label htmlFor={id}>{label}</label>
      {error && <span id={`${id}-e`} className="lf-e">{error}</span>}
    </div>
  );
}

/* 건물 코드 4칸 · 다 채우면 다음 칸으로 */
export function CodeFields({ codes, setCodes, errors, onEnter }) {
  const refs = useRef([]);
  return (
    <div className="codes">
      {CODE_FIELDS.map((f, i) => (
        <LineField key={f.key} label={`${f.label} ${f.len}자리`} value={codes[f.key]} inputMode="numeric"
          maxLength={f.len} error={errors?.[f.key]}
          inputRef={el => { refs.current[i] = el; }}
          onKeyDown={e => { if (e.key === 'Enter') onEnter?.(); }}
          onChange={v => {
            const d = v.replace(/\D/g, '').slice(0, f.len);
            setCodes(c => ({ ...c, [f.key]: d }));
            if (d.length === f.len) refs.current[i + 1]?.focus();
          }} />
      ))}
    </div>
  );
}

/* 금액 입력 · 쉼표 자동, 아래에 읽는 말 */
export function AmountField({ label, value, onChange, min, max }) {
  const [s, setS] = useState(() => won(value));
  const d = s.replace(/\D/g, '');
  const n = d ? Number(d) : 0;
  const err = !d ? '금액을 입력해 주세요' : n < min ? `${koMoney(min)} 이상 입력해 주세요` : n > max ? `${koMoney(max)} 이하로 입력해 주세요` : null;
  useEffect(() => { onChange?.(err ? null : n); }, [n, err]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Field label={label} value={s} unit="원" inputMode="numeric"
      onChange={v => { const dd = v.replace(/\D/g, '').replace(/^0+(?=\d)/, '').slice(0, 11); setS(dd ? Number(dd).toLocaleString('ko-KR') : ''); }}
      error={err} hint={koMoney(n)} />
  );
}

export function Stepper({ label, info, value, min, max, onChange, unit }) {
  const id = useId();
  return (
    <div className="field">
      <span id={id} className="field-l">{label}{info}</span>
      <div className="stepper" role="group" aria-labelledby={id}>
        <button type="button" aria-label={`${label} 줄이기`} disabled={value <= min} onClick={() => onChange(value - 1)}><Icon name="minus" /></button>
        <output className="num" aria-live="polite">{value}{unit}</output>
        <button type="button" aria-label={`${label} 늘리기`} disabled={value >= max} onClick={() => onChange(value + 1)}><Icon name="plus" /></button>
      </div>
    </div>
  );
}

/* ── 움직임 ── */
export const reduced = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

/* 그려진 다음 프레임에 켜진다 · 막대가 자라고 선이 그려지는 데 쓴다 */
export function useReveal() {
  const [on, setOn] = useState(false);
  useEffect(() => {
    let b;
    const a = requestAnimationFrame(() => { b = requestAnimationFrame(() => setOn(true)); });
    return () => { cancelAnimationFrame(a); cancelAnimationFrame(b); };
  }, []);
  return on;
}

/* 숫자를 부드럽게 바꾼다. from0 이면 처음에 0부터 올라간다 */
export function useTween(value, { ms = 420, from0 = false } = {}) {
  const [v, setV] = useState(from0 && !reduced() ? 0 : value);
  const from = useRef(from0 && !reduced() ? 0 : value);
  useEffect(() => {
    if (!Number.isFinite(value)) { setV(value); from.current = value; return undefined; }
    const a = Number.isFinite(from.current) ? from.current : value;
    if (reduced() || a === value) { setV(value); from.current = value; return undefined; }
    let raf;
    const t0 = performance.now();
    const dur = from0 && a === 0 ? Math.max(ms, 760) : ms;
    const step = t => {
      const k = Math.min(1, (t - t0) / dur), e = 1 - (1 - k) ** 3;
      const cur = a + (value - a) * e;
      setV(cur); from.current = cur;
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]); // eslint-disable-line react-hooks/exhaustive-deps
  return v;
}
export function Num({ value, format = won, className, from0 }) {
  const v = useTween(Number(value), { from0 });
  return <span className={cx('num', className)}>{format(v)}</span>;
}

/* 열고 닫을 때 움직임이 끝날 때까지 남겨 둔다 */
export function usePresence(open, ms = 320) {
  const [mounted, setMounted] = useState(open);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (open) {
      setMounted(true);
      let b;
      const a = requestAnimationFrame(() => { b = requestAnimationFrame(() => setShown(true)); });
      return () => { cancelAnimationFrame(a); cancelAnimationFrame(b); };
    }
    setShown(false);
    const t = setTimeout(() => setMounted(false), reduced() ? 0 : ms);
    return () => clearTimeout(t);
  }, [open, ms]);
  return [mounted, shown];
}

/* ── 아래에서 올라오는 시트 (PC에서는 가운데 창) ── */
export function Sheet({ open, onClose, title, children, footer, wide, aside, className }) {
  const [mounted, shown] = usePresence(open, 300);
  const ref = useRef(null);
  const tid = useId();
  useEffect(() => {
    if (!open) return undefined;
    const back = document.activeElement;
    const k = e => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', k);
    const t = setTimeout(() => ref.current?.focus(), 30);
    return () => { window.removeEventListener('keydown', k); clearTimeout(t); back?.focus?.(); };
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!mounted) return null;
  return createPortal(
    <div className={cx('sheet-wrap', shown && 'in')}>
      <div className="sheet-dim" onClick={onClose} aria-hidden="true" />
      <div className={cx('sheet', wide && 'wide', className)} role="dialog" aria-modal="true" aria-labelledby={tid} tabIndex={-1} ref={ref}>
        <div className="sheet-head">
          <h2 id={tid} className="sheet-t">{title}</h2>
          {aside}
          <button type="button" className="icon-btn" aria-label="닫기" onClick={onClose}><Icon name="close" size={22} /></button>
        </div>
        <div className="sheet-body">{children}</div>
        {footer && <div className="sheet-foot">{footer}</div>}
      </div>
    </div>,
    document.body);
}

/* ── 불러오는 중 · 오류 ── */
export const Skeleton = ({ lines = 3, head = true }) => (
  <div className="sk" aria-hidden="true">{head && <i className="h" />}{Array.from({ length: lines }, (_, i) => <i key={i} />)}</div>
);

export const errorHead = (error, notFound = '찾지 못했어요') =>
  error?.network ? '서버에 연결하지 못했어요' : error?.status === 404 ? notFound : '불러오지 못했어요';

export function ErrorBox({ error, onRetry, extra, notFound, bare }) {
  const retry = onRetry && error?.status !== 404;
  return (
    <div className="err-box" role="alert">
      <p>{!bare && <b>{errorHead(error, notFound)}</b>}{error?.message || '잠시 후 다시 시도해 주세요'}</p>
      {(retry || extra) && (
        <div className="err-act">
          {retry && <Button variant="gray" size="m" onClick={onRetry}>다시 시도</Button>}
          {extra}
        </div>
      )}
    </div>
  );
}

/* 자원 상태에 따라 그린다 */
export function Res({ r, lines = 3, children, extra }) {
  if (r.status === 'error') return <ErrorBox error={r.error} onRetry={r.reload} extra={extra} />;
  if (!r.data) return <Skeleton lines={lines} head={false} />;
  return <div className={cx('res', r.stale && 'stale')}>{children(r.data)}</div>;
}

export const Note = ({ tone = 'gray', icon = 'info', children }) => (
  <div className={cx('note', tone)}><Icon name={icon} size={18} /><div>{children}</div></div>
);

/* 새싹 캐릭터 · AI 설명 표시 */
/* 처음 나타날 때 한 바퀴 돌고, 그 뒤엔 살랑살랑. 누르거나 spinKey 가 바뀌면 다시 한 바퀴 */
export function BuddyFace({ size = 22, live = false, spinKey = 0 }) {
  const [spin, setSpin] = useState(live);
  useEffect(() => { if (live && spinKey) setSpin(true); }, [spinKey, live]);
  return (
    <img className={cx('buddy-face', live && 'live', spin && 'spin')} src={buddyFace} width={size} height={size} alt=""
      onAnimationEnd={e => { if (e.animationName === 'buddyspin') setSpin(false); }} />
  );
}
/* 값(key)이 바뀌면 mood 를 잠깐(ms) 보여준다. 처음 그릴 때는 건너뛴다(initial 이면 처음에도).
   예) const cheer = usePulse(확정이면 분기키 : null, 'cheer') → <BuddyBody mood={cheer || 'idle'} /> */
export function usePulse(key, mood, ms = 3200, initial = false) {
  const [on, setOn] = useState(false);
  const first = useRef(true);
  useEffect(() => {
    const skip = first.current && !initial;
    first.current = false;
    if (key == null || key === false || skip) return undefined;
    setOn(true);
    const t = setTimeout(() => setOn(false), ms);
    return () => clearTimeout(t);
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return on ? mood : null;
}

/* 3D 새싹. mood: idle(기본) · wave(인사) · think(생각 중) · cheer(만세) · surprise(놀람)
   누르면 한 바퀴. WebGL 을 못 쓰면 예전 그림(buddy.png)으로 대신 보여준다. */
export function BuddyBody({ w = 64, live = false, spinKey = 0, mood = 'idle' }) {
  const h = Math.round(w * 199 / 160);
  const cv = useRef(null);
  const sprout = useRef(null);
  const [flat, setFlat] = useState(false);
  const [spin, setSpin] = useState(live);
  useEffect(() => {
    const el = cv.current;
    if (!el) return undefined;
    const b = mountBuddy(el, { dist: 8.8, wide: 8.8, lookY: 0.1 });
    if (!b) { setFlat(true); return undefined; }
    sprout.current = b;
    b.setMood(mood);
    if (live) b.spin();
    return () => { sprout.current = null; b.unmount(); };
  }, [w]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { sprout.current?.setMood(mood); }, [mood]);
  useEffect(() => { if (live && spinKey) sprout.current?.spin(); }, [spinKey, live]);
  useEffect(() => { setSpin(false); }, []);
  if (flat) {
    return (
      <img className={cx('buddy-body', live && 'live', spin && 'spin')} src={buddyBody} width={w} height={h} alt=""
        onAnimationEnd={e => { if (e.animationName === 'buddyspin') setSpin(false); }} />
    );
  }
  return <canvas ref={cv} className="buddy-body buddy3d" style={{ width: w, height: h }} width={w} height={h} role="img" aria-label="세이빙 AI 새싹" onClick={() => sprout.current?.spin()} />;
}
