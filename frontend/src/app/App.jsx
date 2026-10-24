import { useState } from 'react';
import { useSavingShare } from '../core/useSavingShare.js';
import { useMediaQuery, useViewMode } from '../core/hooks.js';
import { Entry } from './entry.jsx';
import { MobileApp } from './mobile.jsx';
import { DesktopApp } from './desktop.jsx';
import { AssistProvider } from './assistant/AssistProvider.jsx';
import { STEPS, stepIndex, groupOf } from './steps.jsx';

const ss = {
  get: k => { try { return sessionStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { sessionStorage.setItem(k, v); } catch { /* 저장소 없음 */ } },
  del: k => { try { sessionStorage.removeItem(k); } catch { /* 저장소 없음 */ } },
};
const ENTERED = 'ss.v4.entered';

export default function App() {
  const entered0 = ss.get(ENTERED) === '1';
  const S = useSavingShare({ autoLookup: entered0 });
  const wide = useMediaQuery('(min-width: 1120px)');
  const [mode] = useViewMode();   // 설정 · 자동이면 창 폭, 아니면 고른 화면
  const pc = mode === 'auto' ? wide : mode === 'pc';
  const [view, setView] = useState(entered0 ? 'app' : 'entry');

  // 처음 화면에서 들어갈 때 · 세이빙 AI 가 정한 단계(예: 분배)로 바로 열 수도 있다
  const enter = (at = 'bld') => {
    const id = STEPS.some(s => s.id === at) ? at : 'bld';
    ss.set(ENTERED, '1');
    ss.set('ss.v4.step', String(stepIndex(id)));
    ss.set('ss.v4.pc', JSON.stringify(id === 'bld' ? { page: 'home', step: null } : { page: groupOf(id).id, step: id }));
    setView('app');
    window.scrollTo(0, 0);
  };
  const exit = () => {
    ss.del(ENTERED);
    setView('entry');
    window.scrollTo(0, 0);
  };

  return (
    <AssistProvider S={S}>
      {view === 'entry'
        ? <Entry S={S} onDone={enter} pc={pc} />
        : <>{pc ? <DesktopApp S={S} onExit={exit} /> : <MobileApp S={S} onExit={exit} />}</>}
    </AssistProvider>
  );
}
