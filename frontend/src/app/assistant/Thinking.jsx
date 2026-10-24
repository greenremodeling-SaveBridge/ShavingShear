/* ══════════════════════════════════════════════════════
   AI 가 일하는 동안 · 토스식 "흐르는" 점
   점은 제자리에 있고 밝기만 왼쪽에서 오른쪽으로 번진다 — 무언가 건너가는 느낌만 준다.
   단계(steps)는 정해진 시간에 하나씩 체크된다. 빨라도 최소 시간(min)은 보여준다.
   ══════════════════════════════════════════════════════ */
import { useEffect, useRef, useState } from 'react';
import { cx } from '../../core/format.js';
import { Icon, reduced } from '../ui.jsx';

export function Flow({ from = 'building', to = 'sparkle', size = 'm' }) {
  return (
    <div className={cx('flow', size)} aria-hidden="true">
      <span className="flow-node"><Icon name={from} size={size === 'l' ? 26 : 18} /></span>
      <span className="flow-track">
        <span className="flow-glow" />
        {Array.from({ length: 9 }, (_, i) => <i key={i} style={{ '--i': i }} />)}
      </span>
      <span className="flow-node to"><Icon name={to} size={size === 'l' ? 26 : 18} /></span>
    </div>
  );
}

/* title 이 바뀌면 부드럽게 바꿔 끼운다 · steps 는 차례로 체크 */
export function Thinking({ title, steps = [], done = 0, from, to, size }) {
  return (
    <div className={cx('think', size)} role="status" aria-live="polite">
      <Flow from={from} to={to} size={size} />
      <p key={title} className="think-t">{title}</p>
      {steps.length > 0 && (
        <ol className="think-steps">
          {steps.map((s, i) => (
            <li key={s} className={cx(i < done && 'ok', i === done && 'now')}>
              <span className="think-ic">{i < done ? <Icon name="check" size={13} stroke={3} /> : <i />}</span>{s}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/* 최소 시간 동안 단계를 하나씩 넘긴다 · ready 가 참이고 시간이 다 되면 onDone */
export function usePaced(active, { min = 4000, steps = 3, ready = true } = {}) {
  const [done, setDone] = useState(0);
  const [over, setOver] = useState(false);
  const t0 = useRef(0);
  const m = reduced() ? Math.min(min, 1200) : min;
  useEffect(() => {
    if (!active) { setDone(0); setOver(false); return undefined; }
    t0.current = performance.now();
    setDone(0); setOver(false);
    const ts = [];
    for (let k = 1; k <= steps; k++) ts.push(setTimeout(() => setDone(d => Math.max(d, Math.min(k, steps - 1))), (m * k) / (steps + 0.6)));
    ts.push(setTimeout(() => setOver(true), m));
    return () => ts.forEach(clearTimeout);
  }, [active, m, steps]);
  return { done: over && ready ? steps : done, finished: over && ready };
}
