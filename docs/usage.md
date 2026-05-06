# Stock Lab — 사용 가이드

`python -m stocklab NVDA` 한 줄로 `output/NVDA_<YYYYMMDD>.html` 파일이 생성됩니다.
브라우저로 열면 README의 9 섹션 다크모드 대시보드가 그대로 보입니다.

## 설치

```bash
# Python 3.10+ 필요
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## 사용법

### Mode A — 개별 종목 (9 섹션)

```bash
.venv/bin/python -m stocklab NVDA            # 미국 주식
.venv/bin/python -m stocklab 005930          # 한국 주식 (자동 .KS)
.venv/bin/python -m stocklab 042700.KQ       # KOSDAQ 명시
.venv/bin/python -m stocklab 삼성전자         # 한국 회사명
.venv/bin/python -m stocklab BTC-USD         # 암호화폐
.venv/bin/python -m stocklab QQQ             # ETF
```

### Mode B — 테마 발굴 (7 섹션)

```bash
.venv/bin/python -m stocklab "AI 반도체"
.venv/bin/python -m stocklab "소부장 추천"
.venv/bin/python -m stocklab "K-방산"
.venv/bin/python -m stocklab "2차전지"
.venv/bin/python -m stocklab "고배당주"
```

### Mode C — 비교 분석 (좌우 2컬럼)

```bash
.venv/bin/python -m stocklab "NVDA vs AMD"
.venv/bin/python -m stocklab "삼성전자 vs SK하이닉스"
```

## 옵션

| 플래그 | 의미 |
|--------|------|
| `--no-llm` | narrative 결정론 폴백 (LLM 호출 안 함) |
| `--short` | 단기 트레이딩 가중 |
| `--aggressive` | 공격적 (Mode B 전용) |
| `--conservative` | 보수적 (Mode B 전용) |
| `--out PATH` | 출력 디렉터리 변경 (기본 `output/`) |
| `--open` | 생성 후 브라우저 자동 오픈 |

옵션 키워드는 입력 문자열에 직접 넣어도 됩니다:

```bash
.venv/bin/python -m stocklab "NVDA 단기"
.venv/bin/python -m stocklab "NVDA 심층"
.venv/bin/python -m stocklab "AI 반도체 공격적"
```

## 환경변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `ANTHROPIC_API_KEY` | 선택 | Claude opus-4-7 narrative 생성. 미설정 시 결정론 폴백 |
| `STOCKLAB_LOG_LEVEL` | 선택 | 기본 `INFO` |

LLM 호출 결과는 `~/.cache/stocklab/narrative/{ticker}-{date}.json` 에 캐시되어
같은 날 재실행 시 API 무호출됩니다.

## PDF 저장

생성된 HTML 우상단의 📥 PDF 저장 버튼 → 브라우저 인쇄 다이얼로그 → "PDF로 저장".
"추가 설정" → "배경 그래픽" 체크 권장. 자동으로 화이트 모드 변환되며
카드별 page-break-inside: avoid 가 적용되어 있습니다.

## 데이터 출처

- **yfinance**: 미국·한국·ETF·암호화폐 통합 (가격, 재무, OHLC, 뉴스)
- **Naver 금융** (한국 종목 fallback)
- README §13 룰 4 — **임의 생성 절대 금지**. 결측은 N/A 표시.

## 한계

- yfinance 가 일부 한국 종목의 분기 실적 / 다음 발표일을 제공하지 않을 수 있음 (해당 필드는 N/A 표시)
- 26주봉만 사용 — 연간 수익률은 "보유 기간 수익률" 로 표기됨
- 동종업계 비교 행은 현재 비어 있음 (향후 yfinance peers 활용 예정)

## 트러블슈팅

**Q. 한국 종목이 N/A 만 떠요**
A. yfinance 에서 해당 종목 데이터가 누락된 경우. 종목코드(`005930`)와 회사명(`삼성전자`) 둘 다 시도해보세요.

**Q. 차트가 안 그려져요**
A. Chart.js CDN(`cdnjs.cloudflare.com`) 차단된 환경. 다른 네트워크에서 시도.

**Q. PDF 저장 시 차트가 잘려요**
A. 브라우저 인쇄 설정에서 "배경 그래픽 인쇄" 체크 + 용지 방향 가로 또는 A3.

**Q. narrative 가 영어로 나와요**
A. `ANTHROPIC_API_KEY` 가 미설정이면 결정론 폴백이 사용됩니다. 폴백은 한국어로 작성됨.

## 개발

```bash
.venv/bin/pytest -q                           # 단위 테스트
.venv/bin/pytest tests/test_router.py -v      # 모드 분기 테스트만
.venv/bin/pytest tests/test_indicators.py -v  # 지표 테스트만
```

## 자동화 — 새 세션에서 작업 이어가기

이 프로젝트는 다음 세 곳에 진행 상황과 계획이 동기화되어 있습니다:

1. **`.claude/CLAUDE.md`** — Claude Code 가 매 세션 자동 로드. 7 단계 진행 체크리스트.
2. **`/Users/ham/.claude/plans/git-readme-flickering-lovelace.md`** — 상세 계획 원본.
3. **Notion 「주식 분석 프로젝트」** — 사람이 보는 단일 진실원.

새 세션이 열리면 1번을 자동 로드하여 진행 상황을 파악하고 다음 단계로 이어갑니다.
