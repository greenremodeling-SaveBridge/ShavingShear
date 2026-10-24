# 세이빙 셰어 · 내 PC(Windows)에서 켜기

## 켜기
1. **파이썬 3.9 이상**이 없다면 설치: https://www.python.org/downloads/ (설치할 때 **Add python.exe to PATH** 체크)
2. **`켜기.bat` 더블클릭** → 처음 한 번만 패키지를 설치하고(1~3분), 브라우저가 **http://localhost:8000/app/** 로 열린다
3. 끄기: 켜기 창을 닫거나 **`끄기.bat`**

## 무엇이 들어 있나
- `backend/` — 서버(FastAPI) · `assist.py`(세이빙 AI 대화 입구) · `saving_ai/`(자체 의도 판단 모델: `saving_ai.exe` + `saving_ai.bin`) · `web/`(빌드된 화면)
- `frontend/` — 화면 원본(React). 고친 뒤 **`화면빌드.bat`** (Node.js 18 이상 필요)
- `ai/` — 세이빙 AI 모델 묶음 · 연결 안내(`HANDOFF.md`) · 다시 학습하는 코드(`training/`, GPU 필요) · 사람 말투 시험지
- `docs/` — `CHATBOT_FRONT.md`(챗봇 화면·말투 가이드·알아서 채우기) · 백엔드 요청서

## 알아 둘 것
- 세이빙 AI 실행파일(`saving_ai.exe`)은 Windows 에서 처음 실행해 보는 것 — 백신이 막거나 안 돌면 **규칙만으로 자동 대체**되어 대화는 그대로 된다 (서버 응답의 `source` 가 `template` 이면 대체 중, `local_llm` 이면 모델이 판단)
  - 다시 빌드: `backend\saving_ai` 에서 `g++ -O2 -std=c++17 -static -o saving_ai.exe saving_ai.cpp` (MinGW) 또는 `cl /O2 /EHsc /utf-8 saving_ai.cpp`
- 🎤 음성 입력은 Chrome·Edge 에서 `localhost` 로 열 때 보인다 (Firefox 는 브라우저가 지원하지 않아 숨김)
- 목업 대화(서버 없이 화면 속 가짜 답): 주소 끝에 `?mock=1`
- 개발: `backend` 에서 `.venv\Scripts\python -m uvicorn main:app --reload` + `frontend` 에서 `npm run dev` → http://localhost:5173
