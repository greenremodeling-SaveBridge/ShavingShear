# 세이빙 AI 의도 판단기 — 연결 안내

> 읽는 사람: `assist.py`(`POST /api/assist`)를 만드는 쪽.
> 이 묶음이 요구서 2-1의 **2단계 "자체 서버 LLM(Ollama)"을 대신**합니다. Ollama는 설치하지 않아도 됩니다.

## 1. 이게 무엇인가

- 사용자 문장 하나를 받아 **기능 7가지 중 무엇인지**만 판단하는 작은 모델(747KB)입니다. 숫자 해석과 개인정보 가리기는 같이 들어 있는 규칙(`rules.py`)이 합니다.
- **문장을 만들지 않습니다.** 답 문장은 지금처럼 서버 템플릿이 만듭니다. 그래서 요구서 3-4의 "LLM 숫자 검사, 금지어 검사"에 걸릴 일이 없습니다. 외부 AI도 부르지 않습니다.
- C++ 실행기를 한 번 띄워 두고 계속 씁니다. CPU 한 코어에서 문장 하나에 약 11ms 걸립니다(DGX ARM 실측, Windows x86은 미측정).
- 실행기가 없거나 죽거나 2초 넘게 걸리면 **규칙만으로** 판단합니다. 요구서의 "모델이 없어도 오류 없이 1단계로"를 따른 것입니다.

## 0. 참고 구현이 있어요

`assist_reference.py` — 이 모델로 `/api/assist`·`/api/mediate`·`/api/resolve`·`/api/analyze` 를 만든 참고 구현이에요(프론트 작업본에서 실제로 돌려 요구서 시나리오 36/36 확인). `main.py` 와 같은 폴더에 `assist.py` 로 두고, 이 묶음을 `saving_ai/` 폴더로 넣은 뒤 `main.py` 끝에 두 줄:

```python
from assist import router as assist_router
app.include_router(assist_router)
```

말하지 않은 값은 화면 값·직전 대화로 먼저 채우고(`filled` 로 알림), 정말 없을 때만 하나씩 되묻는다.

## 2. 파일

- `saving_ai.exe`: Windows x86-64 실행기. KERNEL32와 Windows 10 기본 UCRT만 씁니다.
- `saving_ai_linux_arm64`: DGX용 실행기. 다른 Linux에서는 다시 빌드해야 합니다.
- `saving_ai.bin`: 모델
- `saving_ai.py`: **백엔드가 import 할 입구.** 표준 라이브러리만 씁니다.
- `rules.py`: 개인정보 가리기(요구서 4-5 정규식), 숫자 해석(3-5), 힌트 표시
- `saving_ai.cpp`: 실행기 소스(외부 라이브러리 없음)
- `eval_human.py`, `tests/`: 시험지와 채점기
- `training/`: 다시 학습하는 코드(GPU용 PyTorch 필요, 7장)

`saving_ai.exe`, `saving_ai.bin`, `saving_ai.py`, `rules.py` 네 파일을 **같은 폴더**(예: 백엔드 폴더 안 `saving_ai/`)에 두면 됩니다.

## 3. 먼저 확인 (Windows)

```bat
cd saving_ai
python saving_ai.py "공사비 5천만, 8년 안에 회수하고 싶어요"
python eval_human.py saving_ai.bin tests/scenarios.tsv tests/real4.tsv
```

- 첫 줄 결과는 `MEDIATE  nano 0.98  {'invest_won': 50000000, 'target_years': 8}`이 나와야 합니다.
- `by`가 `nano`가 아니라 `rule`로 나오면 exe가 안 뜬 것입니다. 백신 차단이나 경로를 확인하세요.
- **이 exe는 Windows에서 아직 한 번도 실행해 보지 않았습니다.** 안 되면 4장 맨 아래 빌드 명령으로 그 PC에서 다시 빌드하세요.

## 4. 쓰는 법

```python
from saving_ai import SavingAI
AI = SavingAI()                 # 서버 시작할 때 한 번 (실행기를 상주시킴, 스레드 안전)
r = AI.understand(message)      # /api/assist 요청마다
```

`r`의 내용은 이렇습니다.

| 키 | 뜻 |
|---|---|
| `intent` | `MEDIATE` `RESOLVE` `ANALYZE` `TRUST` `VIEW_OWNER` `VIEW_TENANT` `OUT` `ASK` |
| `by` | `nano`(모델이 확신 0.9 이상) · `rule`(규칙이 정함) · `ask`(못 정함) |
| `confidence` | 모델 확신도 (실행기가 없으면 None) |
| `slots` | `invest_won`(원) `owner_ratio`(0~1, 건물주 몫) `target_years` `ym`("202308") `season`((2025,'여름')) `month_only`(8) |
| `ambiguous` | `('money_unit', 5000)` "5천" · `('season', (2025,'여름'))` · `('month_only', 8)` |
| `masked_text` | 개인정보를 가린 문장. **서버에서 쓰거나 남기는 문장은 이것만** |
| `pii_masked` | 가린 게 있으면 True → notices에 "개인정보는 보내지 않았어요" |

**숫자 해석 예** (요구서 3-5 표 전부 통과)
- "오천만 원", "50,000,000원" → 50000000
- "1억 2천" → 120000000
- "칠 대 삼", "세입자 30%", "반띵 말고 칠삼으로" → 0.7. 정정하는 말이 있으면 마지막 값을 씁니다.
- "팔 년" → 8
- "23년 8월" → "202308", "작년 8월" → "202508"(데이터 마지막 해 2026 기준)

범위 검사(비율 5~95%, 기간 1~30년, 공사비 > 0)는 하지 않습니다. assist에서 해 주세요.

### intent를 요구서 응답으로 바꾸기 (제안)

| intent | assist에서 할 일 | 응답 `intent` |
|---|---|---|
| MEDIATE | `slots`로 `/api/mediate` 내부 호출. 공사비나 기간이 없으면 `context`의 직전 조건이나 화면 값을 쓰고, 그것도 없으면 clarify | `mediate` |
| RESOLVE | `/api/resolve`에 `q = masked_text` | `resolve` |
| ANALYZE | `slots.ym`으로 `/api/analyze`. `ym`이 없고 `season`이나 `month_only`만 있으면 달·연도 칩으로 clarify | `analyze` |
| TRUST | `/api/baseline`의 `metric_checks` + `/api/settlement`의 `status_code`로 템플릿 | `trust` |
| VIEW_OWNER / VIEW_TENANT | 관점만 바꿈. 숫자는 그대로. `actions: [{"type":"set_viewer","viewer":"tenant"}]` 같은 동작 추가를 제안 | `mediate` |
| OUT | 요구서상 잡담·추천·결제는 안 함 → "합의 계산, 건물 찾기, 사용량 변화, 금액 신뢰 확인을 도와드려요" + 기능 칩 4개 | `clarify` |
| ASK | 같은 안내 + 칩 | `clarify` |

- `ambiguous`에 `money_unit`이 있으면 실행하지 말고 "5천만 원 말씀이신가요?"로 되물으세요(요구서 3-4 예시와 같음).
- **답 문장은 친절하게** — 짧게·공감 먼저·다음에 할 일, 같은 실패를 두 번 되풀이하지 않기, 말하지 않은 숫자 지어내지 않기. 경우별 문구는 프론트 작업본 `CHATBOT_FRONT.md` 9장 "답 문구 가이드"(주소를 모를 때, 우편번호, 데이터 없는 주소, 조건 없는 합의 요청 등).
- 응답의 `source`는 `by == 'nano'`이면 `local_llm`, 그 밖에는 `template`로 쓰면 요구서와 맞습니다.
- uvicorn 워커가 여러 개면 워커마다 실행기가 하나씩 뜹니다(각 약 10MB). 문제없습니다.

### 다른 PC에서 다시 빌드

- MSVC: `cl /O2 /EHsc /utf-8 saving_ai.cpp`
- MinGW: `g++ -O2 -std=c++17 -static -o saving_ai.exe saving_ai.cpp`
- Linux: `g++ -O2 -std=c++17 -o saving_ai saving_ai.cpp`

## 5. 시험 결과 (이 묶음 그대로, `eval_human.py`)

- `tests/scenarios.tsv`: 요구서 5장 시나리오 문장 10개, **10/10**
- `tests/real4.tsv`: 다른 에이전트가 사람 말투(사투리, 오타, 음성인식 오류, 영어 섞기)로 쓰고 **학습 내내 숨긴** 302문장. **전체 정답 96.0%**, 실행한 것 중 97.3%, 되묻기 1.3%
- `tests/real3.tsv`(353문장)는 98.6%예요. 고칠 때 틀린 문장을 본 시험지라 점수가 후합니다.
- C++ 실행기와 학습 코드(파이썬 int8)는 10,226문장에서 판단이 전부 같습니다.

**알려진 약점**
- 잡담·불평("밥은 먹었슈?", "왜 이렇게 느려")을 ANALYZE로 볼 때가 있습니다.
- "건물주 말고 내 입장"처럼 관점 전환과 정정이 섞인 말을 MEDIATE로 봅니다.
- 단위 없는 숫자("2500에서 3200으로")는 금액으로 읽지 않습니다.

## 6. 낱말 추가 (재학습 없이)

`rules.py`의 `HINTS`에 낱말을 넣으면 그 낱말 앞에 분류 기호가 붙어 모델 판단을 돕습니다. 예를 들어 신뢰 쪽 새 표현은 `'⑨'` 목록에 넣으세요. 바꾼 뒤에는 `eval_human.py`로 점수가 떨어지지 않았는지 확인하세요.

## 7. 다시 학습 (`training/`, GPU 권장)

```bash
cd training && mkdir -p data && cp ../tests/real.tsv data/
SA_ALL=1 SA_N=900000 python gen.py                    # 규칙 합성 데이터 90만 문장 (사람 라벨 0)
python train.py train SA3all_d128L4.pt                # d128 L4, GPU 약 5분
python export.py SA3all_d128L4.pt ../saving_ai.bin
python cpp_check.py SA3all_d128L4.pt ../saving_ai.bin # 실행기와 일치 확인 (리눅스 실행기 필요)
```

학습 데이터를 바꿨다면 **새 사람 말투 시험지를 먼저 만들어 숨겨 두고** 마지막에 한 번만 채점하세요. 고치면서 본 시험지는 점수가 부풀려집니다.
