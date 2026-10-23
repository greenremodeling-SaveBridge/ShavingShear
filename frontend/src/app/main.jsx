import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import App from './App.jsx';

/* 줄바꿈 다듬기 · "전기·가스"처럼 가운뎃점으로 붙은 말이 줄 끝에서 갈리지 않게 (보이지 않는 이음표를 넣는다) */
const WJ = '\u2060';
const DOT = /([^\s\u2060])([·∙ㆍ~])(?=[^\s\u2060])/g;
const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'CODE', 'PRE']);
const fixText = n => {
  if (!n.nodeValue || !DOT.test(n.nodeValue)) return;
  DOT.lastIndex = 0;
  const p = n.parentNode;
  if (!p || SKIP.has(p.nodeName) || p.isContentEditable) return;
  const v = n.nodeValue.replace(DOT, (m, a, d) => `${a}${WJ}${d}${WJ}`);
  if (v !== n.nodeValue) n.nodeValue = v;
};
const fixTree = root => {
  if (root.nodeType === 3) { fixText(root); return; }
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) fixText(n);
};
new MutationObserver(ms => {
  for (const m of ms) {
    if (m.type === 'characterData') fixText(m.target);
    else m.addedNodes.forEach(fixTree);
  }
}).observe(document.getElementById('root'), { subtree: true, childList: true, characterData: true });
import { applyBig } from '../core/hooks.js';

applyBig();

/* 옆으로 긴 줄(칩·근거·유의사항) · 마우스 휠과 끌기로 옆으로 넘긴다 */
const HS = '.as-facts, .as-chips, .chips, .d-ticker';
document.addEventListener('wheel', e => {
  const el = e.target.closest?.(HS);
  if (!el || el.scrollWidth <= el.clientWidth + 1 || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
  const max = el.scrollWidth - el.clientWidth;
  if ((e.deltaY < 0 && el.scrollLeft <= 0) || (e.deltaY > 0 && el.scrollLeft >= max - 1)) return;
  el.scrollLeft += e.deltaY;
  e.preventDefault();
}, { passive: false });
let drag = null;
document.addEventListener('pointerdown', e => {
  if (e.pointerType !== 'mouse' || e.button !== 0) return;
  const el = e.target.closest?.(HS);
  if (el && el.scrollWidth > el.clientWidth + 1) drag = { el, x: e.clientX, left: el.scrollLeft, moved: false };
});
document.addEventListener('pointermove', e => {
  if (!drag) return;
  const dx = e.clientX - drag.x;
  if (Math.abs(dx) > 5) { drag.moved = true; drag.el.classList.add('dragging'); }
  if (drag.moved) drag.el.scrollLeft = drag.left - dx;
});
document.addEventListener('pointerup', () => {
  if (!drag) return;
  const d = drag; drag = null;
  d.el.classList.remove('dragging');
  if (d.moved) document.addEventListener('click', ev => { ev.stopPropagation(); ev.preventDefault(); }, { capture: true, once: true });
});

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
