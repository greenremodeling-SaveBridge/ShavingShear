/* 세이빙 AI 를 어디서든 부르는 통로. 화면 부품(ui.jsx)도 이걸로 "AI에게 물어보기"를 단다. */
import { createContext, useContext } from 'react';

export const AssistCtx = createContext(null);
/* 없으면 null — 챗봇이 없는 곳에서는 권유를 그리지 않는다 */
export const useAssist = () => useContext(AssistCtx);
