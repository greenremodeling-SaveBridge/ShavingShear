/* 모바일 · 한 화면에 한 단계. 위에서 어디쯤인지, 아래에서 다음 할 일 하나. */
import { useEffect, useRef, useState } from 'react';
import { cx } from '../core/format.js';
import { usePersistent } from '../core/hooks.js';
import { BigTextBtn, BuddyFace, Button, Fold, Icon, Sheet, connInfo } from './ui.jsx';
import { useAssist } from './assistant/context.js';
import { Assistant, AiTitle, ViewerToggle } from './assistant/Assistant.jsx';
import { AskRow } from './assistant/Nudge.jsx';
import { ThemeBtn } from './entry.jsx';
import { ViewSetting } from './viewMode.jsx';
import { CalcMethod, GROUPS, STEPS, ShellProvider, StepView, stepById, stepIndex, summaries } from './steps.jsx';

function StepSheet({ open, onClose, S, cur, onPick, onExit }) {
  const sum = summaries(S);
  const c = connInfo(S.conn);
  return (
    <Sheet open={open} onClose={onClose} title="전체 단계"
      footer={<Button variant="gray" block onClick={() => { onClose(); onExit(); }}>다른 건물 보기</Button>}>
      <div className={cx('conn-row', c.tone)}>
        <span><i />{c.text}</span>
        {c.action && <Button variant="weak" size="s" onClick={c.action.run}>{c.action.label}</Button>}
        <BigTextBtn className="ss-big" /><ThemeBtn className="ss-theme" />
      </div>
      <div className="ss-set">
        <p className="ss-h">설정</p>
        <ViewSetting pc={false} />
      </div>
      <AskRow before={onClose} send={false} />
      <div className="ss">
        {GROUPS.map(g => (
          <div key={g.id} className="ss-g">
            <p className="ss-h">{g.name}</p>
            {g.steps.map(id => {
              const s = stepById(id);
              const k = stepIndex(id);
              const v = sum[id];
              return (
                <button key={id} type="button" className="ss-row" aria-current={k === cur ? 'step' : undefined}
                  onClick={() => { onPick(k); onClose(); }}>
                  <span className="ss-n num">{s.n}</span>
                  <span className="ss-k">{s.name}</span>
                  {v && <span className={cx('ss-v', v.tone)}>{v.text}</span>}
                  <Icon name="right" size={18} />
                </button>
              );
            })}
          </div>
        ))}
      </div>
      {/* 계산 방법 · 9단계에서 옮겨 옴 (9단계는 결론 정리) */}
      <div className="ss-calc"><Fold title="계산 방법"><CalcMethod /></Fold></div>
    </Sheet>
  );
}

/* 처음 들어온 조회 화면에서만 한 번 · AI 설명이 있다고 알려주는 반투명 안내 */
const tipSeen = () => { try { return sessionStorage.getItem('ss.tip.ai.m') === '1'; } catch { return false; } };
const tipMark = () => { try { sessionStorage.setItem('ss.tip.ai.m', '1'); } catch { /* 무시 */ } };
function MobileTip() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (tipSeen()) return undefined;
    const t1 = setTimeout(() => setShow(true), 1200);
    const t2 = setTimeout(() => { setShow(false); tipMark(); }, 9200);
    return () => { clearTimeout(t1); clearTimeout(t2); tipMark(); };
  }, []);
  if (!show) return null;
  return (
    <div className="ai-tip" role="status">
      <BuddyFace size={44} live />
      <div className="ai-tip-b">
        <b>AI 설명 기능이 있어요!</b>
        <p>정산 단계에서 새싹을 누르면 달마다 금액이 왜 이렇게 나왔는지 설명해 드려요</p>
      </div>
      <button type="button" onClick={() => { setShow(false); tipMark(); }}>알겠어요</button>
    </div>
  );
}

export function MobileApp({ S, onExit }) {
  const a = useAssist();
  const [i, setI] = usePersistent('ss.v4.step', 0, v => (Number.isInteger(v) && v >= 0 && v < STEPS.length ? v : 0));
  const [dir, setDir] = useState(0);
  const [list, setList] = useState(false);
  const [month, setMonth] = useState(null);
  const body = useRef(null);
  const step = STEPS[i];
  const next = STEPS[i + 1];
  const go = j => {
    if (j === i || j < 0 || j >= STEPS.length) return;
    setDir(j > i ? 1 : -1);
    setI(j);
  };
  useEffect(() => { body.current?.scrollTo(0, 0); }, [i]);
  // 세이빙 AI 가 화면을 옮길 때 · 시트를 닫고 그 단계로
  useEffect(() => { a?.bindNav(id => go(stepIndex(id)), step.id, true); }, [i]); // eslint-disable-line react-hooks/exhaustive-deps
  const c = connInfo(S.conn);
  const shell = { device: 'm', month, setMonth, go: id => go(stepIndex(id)) };

  return (
    <ShellProvider value={shell}>
      <div className="m-app">
        {i === 0 && <MobileTip />}
        <header className="m-bar">
          <button type="button" className="icon-btn" aria-label={i === 0 ? '건물 고르기로 돌아가기' : '이전 단계'}
            onClick={() => (i === 0 ? onExit() : go(i - 1))}>
            <Icon name="left" size={24} />
          </button>
          <div className="m-bar-t">
            <b>{step.name}</b>
            <span className={cx('m-conn', c.tone)} role="status">{c.text}</span>
          </div>
          <button type="button" className="icon-btn" aria-label="전체 단계" aria-haspopup="dialog" onClick={() => setList(true)}>
            <Icon name="list" size={24} />
          </button>
        </header>
        <div className="m-prog" role="progressbar" aria-label="진행 단계" aria-valuemin={1} aria-valuemax={STEPS.length} aria-valuenow={i + 1}>
          {STEPS.map((s, k) => <i key={s.id} className={cx(k <= i && 'on')} />)}
        </div>
        {S.sim && (
          <div className="m-alert purple" role="note">
            <span><b>가상 데이터</b> · {S.sim.note || '실제 사용량이 아니에요'}</span>
          </div>
        )}
        {c.action && (
          <div className={cx('m-alert', c.tone)}>
            <span>{c.tone === 'red' ? '저장된 시연 데이터로 이어서 볼 수 있어요' : '서버가 다시 연결됐어요'}</span>
            <button type="button" onClick={c.action.run}>{c.action.label}<Icon name="right" size={16} /></button>
          </div>
        )}
        <main className="m-body" ref={body}>
          <div key={step.id} className={cx('m-step', dir > 0 && 'from-r', dir < 0 && 'from-l')}>
            <StepView id={step.id} S={S} />
          </div>
        </main>
        <footer className="m-cta">
          {step.id === 'bld' ? (
            <>
              <Button variant="gray" onClick={onExit}>다른 건물</Button>
              <Button className="grow" disabled={!S.bld.data} onClick={() => go(1)}>맞아요</Button>
            </>
          ) : (
            <Button block onClick={() => (next ? go(i + 1) : go(0))}>{next ? `다음 · ${next.name}` : '처음으로'}</Button>
          )}
        </footer>
        <StepSheet open={list} onClose={() => setList(false)} S={S} cur={i} onPick={go} onExit={onExit} />
        {a && (
          <Sheet open={a.open} onClose={() => a.setOpen(false)} title={<AiTitle />} aside={<ViewerToggle S={S} />} className="as-sheet">
            <Assistant S={S} variant="sheet" step={step.id} />
          </Sheet>
        )}
      </div>
    </ShellProvider>
  );
}
