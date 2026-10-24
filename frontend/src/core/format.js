/* 표시 도우미 — 값을 바꾸지 않고 모양만 만든다. 금액 계산은 여기서도 하지 않는다. */

export const isNum = n => n !== null && n !== undefined && n !== '' && Number.isFinite(Number(n));

export const won  = n => (isNum(n) ? Math.round(Number(n)).toLocaleString('ko-KR') : '—');
export const kwh  = n => (isNum(n) ? Math.round(Number(n)).toLocaleString('ko-KR') : '—');
export const pct  = n => (isNum(n) ? `${(Number(n) * 100).toFixed(0)}%` : '—');
export const pct1 = n => (isNum(n) ? `${+(Number(n) * 100).toFixed(1)}%` : '—');
export const ymTxt = s => (typeof s === 'string' && s.length >= 6 ? `${s.slice(0, 4)}.${s.slice(4, 6)}` : '—');
export const periodTxt = p => String(p ?? '').replace(/(\d{4})(\d{2})/g, '$1.$2');
export const dateTxt = s => {
  const t = String(s ?? '');
  return t.length === 8 ? `${t.slice(0, 4)}.${t.slice(4, 6)}.${t.slice(6)}` : (t || '—');
};
/** 첫 문장만 (소수점 7.6 같은 건 문장 끝으로 보지 않는다) */
export const firstSentence = t => {
  const m = /^(.+?[.!?])(\s|$)/.exec(String(t || ''));
  return m ? m[1] : String(t || '');
};
/** 87만 25원 → '87만' · 요약 자리에서 만 원 단위로만 보여준다 (값은 서버 그대로, 반올림 표시) */
export const manwon = n => (isNum(n) ? `${Math.round(Number(n) / 1e4).toLocaleString('ko-KR')}만` : '—');
export const manRange = (a, b) => (a === b ? `${manwon(a)} 원` : `${manwon(a)}~${manwon(b)} 원`);
/* 공사비 합계 {low, high} → '1,200만~1,800만 원' · 없으면 null */
export const costTxt = c => (c ? manRange(c.low, c.high) : null);
export const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const cx = (...a) => a.filter(Boolean).join(' ');

/** 50000000 → "5,000만원", 123456789 → "1억 2,345만 6,789원" (읽기 쉽게 단위만 붙인다) */
export function koMoney(n) {
  if (!isNum(n)) return '';
  n = Math.floor(Number(n));
  if (n === 0) return '0원';
  const eok = Math.floor(n / 1e8), man = Math.floor((n % 1e8) / 1e4), rest = n % 1e4;
  const parts = [];
  if (eok) parts.push(`${eok.toLocaleString('ko-KR')}억`);
  if (man) parts.push(`${man.toLocaleString('ko-KR')}만`);
  if (rest) parts.push(rest.toLocaleString('ko-KR'));
  return parts.join(' ') + '원';
}

/** 2026-10-19T02:47:38 → 2026-10-19 02:47 */
export const stampTime = g => (g ? String(g).replace('T', ' ').slice(0, 16) : '시각 미상');
