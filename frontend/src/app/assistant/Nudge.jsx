/* ══════════════════════════════════════════════════════
   세이빙 AI 권유 — 늘 떠 있는 버튼 대신, 헤매는 그 자리 옆에서 한 번만
   AskRow   : 화면 흐름 속 한 줄 (✦ 세이빙 AI에게 물어보기 >)
   AskNudge : 헤매는 게 보일 때 나오는 초록 말풍선 (닫으면 이 탭에서 다시 안 나옴)
   ══════════════════════════════════════════════════════ */
import { useCallback, useRef, useState } from 'react';
import { cx } from '../../core/format.js';
import { Icon } from '../ui.jsx';
import { useAssist } from './context.js';

export function AskRow({ q, title = '세이빙 AI에게 물어보기', sub, send = true, before, compact, className }) {
  const a = useAssist();
  if (!a) return null;
  return (
    <button type="button" className={cx('ask-row', compact && 'compact', className)}
      onClick={() => { before?.(); a.ask(q, { send }); }}>
      <span className="ask-ic"><Icon name="sparkle" size={compact ? 14 : 16} /></span>
      <span className="ask-t"><b>{title}</b>{sub && <span>{sub}</span>}</span>
      <Icon name="right" size={18} />
    </button>
  );
}

/* 배경 없는 한 줄 — 화면을 무겁게 하지 않는 기본 권유 */
export function AskLink({ q, title = '세이빙 AI에게 물어보기', send = true, before, line, className }) {
  const a = useAssist();
  if (!a) return null;
  return (
    <button type="button" className={cx('ask-link', line && 'line', className)}
      onClick={() => { before?.(); a.ask(q, { send }); }}>
      <Icon name="sparkle" size={15} /><span>{title}</span><Icon name="right" size={16} />
    </button>
  );
}

const seen = id => { try { return sessionStorage.getItem(`ss.nudge.${id}`) === '1'; } catch { return false; } };
const mark = id => { try { sessionStorage.setItem(`ss.nudge.${id}`, '1'); } catch { /* 무시 */ } };

/* 같은 조작을 여러 번 되풀이하면 헤매는 것으로 본다 → [보일까, 한 번 셈, 닫기] */
export function useStruggle(id, times = 5, withinMs = 20000) {
  const [show, setShow] = useState(false);
  const hits = useRef([]);
  const bump = useCallback(() => {
    if (show || seen(id)) return;
    const now = Date.now();
    hits.current = [...hits.current.filter(t => now - t < withinMs), now];
    if (hits.current.length >= times) setShow(true);
  }, [id, times, withinMs, show]);
  const close = useCallback(() => { mark(id); setShow(false); }, [id]);
  const force = useCallback(() => { if (!seen(id)) setShow(true); }, [id]);
  return [show, bump, close, force];
}

export function AskNudge({ title, text, actions = [], onClose, className }) {
  return (
    <div className={cx('nudge', className)} role="note">
      <span className="nudge-ic" aria-hidden="true"><Icon name="sparkle" size={16} /></span>
      <div className="nudge-b">
        <b>{title}</b>
        {text && <p>{text}</p>}
        {actions.length > 0 && (
          <div className="nudge-act">
            {actions.map(x => <button key={x.label} type="button" className={cx(x.main && 'main')} onClick={x.onClick}>{x.label}</button>)}
          </div>
        )}
      </div>
      <button type="button" className="nudge-x" aria-label="권유 닫기" onClick={onClose}><Icon name="close" size={16} stroke={2.4} /></button>
    </div>
  );
}
