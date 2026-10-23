# 세이빙 셰어 화면

React로 만든 한 장짜리 HTML입니다. 폭이 1120px 이상이면 PC 화면, 그보다 좁으면 모바일 화면이 나옵니다.

| 파일 | 내용 |
|---|---|
| `web/index.html` | 시연 화면. FastAPI가 `web/` 폴더를 그대로 내주면 됩니다 |
| `web/backup.json` | 저장된 시연 데이터. 서버에 연결되지 않으면 이 값으로 보여줍니다 |

`web/index.html`을 더블클릭해서 열어도 화면이 나옵니다. 이때는 파일 안에 넣어 둔 시연 데이터를 쓰고, 화면 위쪽에 `저장된 시연 데이터 · 2026-10-19 02:47 기준`이 계속 표시됩니다.

## 빌드

```bash
cd frontend
npm install
npm run build            # ../web/index.html
npm run build:preview    # ../out/preview/index.html (서버 없이 도는 미리보기)
```

화면 문구를 바꿨다면 글꼴을 다시 줄인 뒤 빌드합니다.

```bash
pip install fonttools brotli
npm run font
npm run build
```

## 개발

```bash
uvicorn main:app --port 8000   # 백엔드 먼저
npm run dev                     # http://localhost:5173
```

## 구조

```
src/core/   서버 호출(client.js) · 상태 규칙(domain.js) · 공용 상태(useSavingShare.js) · 표시 도우미(format.js)
            세이빙 AI 호출(assist.js) · 목업(mockAssist.js, ?mock=1) · 음성(useSpeech.js)
src/app/
  App.jsx       처음 화면 → PC 또는 모바일
  entry.jsx     처음 화면 (건물 고르기 · 필수 안내 확인)
  mobile.jsx    모바일 · 한 화면에 한 단계
  desktop.jsx   PC · 위 메뉴, 유의 안내 띠, 하얀 판, 오른쪽 AI 설명, 아래 유의사항 줄
  steps.jsx     9단계 화면 내용 (PC와 모바일이 같은 것을 쓴다)
  charts.jsx    그래프
  ui.jsx        부품 ((i) 설명, ▼ 펼침, 시트, 체크, 칩 등)
  styles.css    화면 규칙
  assistant/    세이빙 AI — 늘 떠 있지 않고 필요한 자리에서 열린다 (../../CHATBOT_FRONT.md)
```

## 화면 규칙

- 모바일은 한 화면에 한 단계만 보여줍니다. 답 한 문장, 핵심 그림 하나, 그 자리에서 하는 조작, 아래 고정 버튼 하나.
- PC는 모든 화면이 같은 틀입니다. 메뉴, 제목 자리, 오른쪽 회색 칸, 아래 다음 버튼 위치가 같습니다.
- 설명 문장은 늘어놓지 않습니다. 꼭 필요한 것만 (i)를 누르거나 ▼를 열어야 보입니다.
- 글꼴은 Pretendard 하나. 크기는 40·28(처음 화면 제목), 34(금액), 26·24(단계 제목), 20, 17, 16, 15, 13px만 씁니다.
- 색은 파랑 하나를 동작에 쓰고, 상태는 정해진 색으로만 표시합니다.
  시뮬레이션은 주황, 잠정은 파랑, 검증 완료는 초록, 검토 필요는 빨강, 데이터 없음은 회색, 가상 데이터는 보라입니다.
- 금액은 서버 응답을 그대로 보여주고 화면에서 다시 계산하지 않습니다.
- 흐름은 ① 조회 → ② 대상 판정 → ③ 건축물 진단 → ④ 개선 대책 → ⑤ 기저선 추정 → ⑥ 분배 시뮬레이터 → ⑦ 정산 리포트 → ⑧ 임대차 특약 → ⑨ 시스템 구성 순서입니다.
- 움직임은 화면이 바뀔 때, 숫자가 나올 때, 그래프가 처음 그려질 때만 씁니다. 기기에서 움직임 줄이기를 켜면 모두 멈춥니다.
