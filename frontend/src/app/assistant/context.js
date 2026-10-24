/* 세이빙 AI 를 어디서든 부르는 통로. 화면 부품(ui.jsx)도 이걸로 "AI에게 물어보기"를 단다. */
import { createContext, useContext, useState } from 'react';

export const AssistCtx = createContext(null);
/* 없으면 null — 챗봇이 없는 곳에서는 권유를 그리지 않는다 */
export const useAssist = () => useContext(AssistCtx);

/* 이동 버튼을 누른 자리에서 바로 「‹ 이전 화면」으로 바뀌게 (PC)
   누를 때 지나온 자리 수를 기억 → 그 뒤로 다른 이동이 없으면 이전 화면 버튼을 보여준다 */
export function useJumpBack() {
  const a = useAssist();
  const [at, setAt] = useState(null);   // { len, which } · which: 버튼이 여럿일 때 누른 것
  const on = at != null && a?.navLen === at.len;
  return {
    on,
    which: on ? at.which : null,
    mark: which => setAt(a?.navLen != null ? { len: a.navLen + 1, which } : null),
    back: () => { setAt(null); a?.navBack?.(); },
    reset: () => setAt(null),
  };
}
