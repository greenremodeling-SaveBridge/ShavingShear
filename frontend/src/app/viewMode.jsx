/* 설정 · 화면 보기(자동 / PC / 모바일). 바꿔도 보던 단계는 그대로 이어서 보여준다. */
import { useViewMode } from '../core/hooks.js';
import { Seg2 } from './ui.jsx';
import { GROUPS, STEPS, groupOf, stepIndex } from './steps.jsx';

const OPTIONS = [{ value: 'auto', label: '자동' }, { value: 'pc', label: 'PC' }, { value: 'm', label: '모바일' }];

const read = k => { try { return JSON.parse(sessionStorage.getItem(k)); } catch { return null; } };
const write = (k, v) => { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch { /* 저장소 없음 */ } };

/* PC 는 묶음·단계(ss.v4.pc), 모바일은 단계 번호(ss.v4.step)로 자리를 기억한다 · 서로 옮겨 적는다 */
function carryPlace(to) {
  if (to === 'pc') {
    const s = STEPS[read('ss.v4.step')] || STEPS[0];
    write('ss.v4.pc', s.id === 'bld' ? { page: 'home', step: null } : { page: groupOf(s.id).id, step: s.id });
  } else {
    const r = read('ss.v4.pc');
    const id = r?.step || GROUPS.find(g => g.id === r?.page)?.steps[0] || 'bld';
    write('ss.v4.step', Math.max(0, stepIndex(id)));
  }
}

export function ViewSetting({ pc }) {
  const [mode, setMode] = useViewMode();
  const pick = v => {
    if (v === mode) return;
    const wide = window.matchMedia('(min-width: 1120px)').matches;
    const nextPc = v === 'auto' ? wide : v === 'pc';
    if (nextPc !== pc) carryPlace(nextPc ? 'pc' : 'm');
    setMode(v);
  };
  return (
    <div className="set-row">
      <div className="set-k">
        <b>화면 보기</b>
        <span>{mode === 'auto' ? `창 크기에 맞춰요 · 지금 ${pc ? 'PC' : '모바일'}` : `${mode === 'pc' ? 'PC' : '모바일'} 화면으로 고정`}</span>
      </div>
      <Seg2 label="화면 보기" value={mode} onChange={pick} options={OPTIONS} />
    </div>
  );
}
