/* 🎤 음성 입력 — B 방식(브라우저 내장 Web Speech API, 요구서 4-3)
   음성은 브라우저(구글·애플) 음성 인식 서비스로 글자가 된다. 자동으로 보내지 않는다. */
import { useCallback, useEffect, useRef, useState } from 'react';

const SR = typeof window !== 'undefined' ? (window.SpeechRecognition || window.webkitSpeechRecognition) : null;
export const speechOk = !!SR && typeof window !== 'undefined' && window.isSecureContext;
export const VOICE_NOTICE = '음성은 브라우저(구글·애플) 음성 인식 서비스로 글자로 바뀌어요. 세이빙 셰어 서버에는 글자만 전달돼요.';
/* 처음 한 번 · 막지 않고 알림으로만 (요구서 4-3 고지문 그대로) */
export const VOICE_TOAST = VOICE_NOTICE;
const ERR = {
  'not-allowed': '마이크 권한을 허용해 주세요',
  'service-not-allowed': '마이크 권한을 허용해 주세요',
  'no-speech': '말소리가 안 들렸어요',
  network: '음성 인식에 인터넷이 필요해요. 글로 입력해 주세요',
};
const MAX_MS = 10000;

export const voiceAgreed = () => { try { return localStorage.getItem('ss.voiceOk') === '1'; } catch { return false; } };
export const agreeVoice = () => { try { localStorage.setItem('ss.voiceOk', '1'); } catch { /* 저장소 없음 */ } };

/* onFinal(글자) 는 인식이 끝났을 때 한 번 — 입력창에 넣기만 한다 */
export function useSpeech(onFinal) {
  const [on, setOn] = useState(false);
  const [interim, setInterim] = useState('');
  const [error, setError] = useState(null);
  const rec = useRef(null);
  const timer = useRef(null);
  const fin = useRef('');
  const cb = useRef(onFinal);
  cb.current = onFinal;

  const stop = useCallback(() => {
    clearTimeout(timer.current);
    try { rec.current?.stop(); } catch { /* 이미 멈춤 */ }
  }, []);

  const start = useCallback(() => {
    if (!speechOk) return;
    setError(null); setInterim(''); fin.current = '';
    const r = new SR();
    r.lang = 'ko-KR'; r.interimResults = true; r.continuous = false;
    r.onresult = e => {
      let f = '', mid = '';
      for (let i = 0; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) f += t; else mid += t;
      }
      fin.current = f;
      setInterim(f + mid);
    };
    r.onerror = e => { setError(ERR[e.error] || '글로 입력해 주세요'); };
    r.onend = () => {
      clearTimeout(timer.current);
      setOn(false); setInterim('');
      const t = fin.current.trim();
      if (t) cb.current?.(t);
      rec.current = null;
    };
    rec.current = r;
    try { r.start(); setOn(true); } catch { setError('글로 입력해 주세요'); return; }
    timer.current = setTimeout(stop, MAX_MS);
  }, [stop]);

  const toggle = useCallback(() => (on ? stop() : start()), [on, start, stop]);
  useEffect(() => () => { clearTimeout(timer.current); try { rec.current?.abort(); } catch { /* 무시 */ } }, []);
  return { on, interim, error, toggle, clearError: () => setError(null) };
}
