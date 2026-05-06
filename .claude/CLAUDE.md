# Stock Lab — Claude Code 작업 가이드

> 이 파일은 매 세션 자동으로 로드된다. 새 세션이 열려도 이 문서를 따라 진행 상황을 파악하고 다음 작업으로 넘어갈 수 있어야 한다.

## 프로젝트 한 줄 정의

`python -m stocklab NVDA` 한 줄로 `output/NVDA_<YYYYMMDD>.html` 가 생성되어 브라우저로 열면 README 명세의 9 섹션 다크모드 대시보드가 그대로 보이는 **로컬 Python CLI 도구**.

- 텔레그램 봇 X — **순수 로컬 도구**
- 부모 페이지(텔레그램 봇 허브) 무관 — **이 프로젝트는 독립적**
- 원본 명세 보관: `docs/spec.md` (현재 `README.md` 의 시스템 프롬프트 명세를 이전)

## 핵심 참조

- **상세 계획**: `/Users/ham/.claude/plans/git-readme-flickering-lovelace.md`
- **Notion 페이지**: 「주식 분석 프로젝트」 (`35109ff8-f30e-8097-ab96-efe019038379`)
- **시스템 프롬프트 원본**: 현재 루트 `README.md` (디자인·9 섹션 구조·Chart.js plugin 의 정답지)

## 기술 스택 (확정)

- **Python 3.10+** (`.venv/` 표준 venv + pip — uv 미설치 환경 대응), `pyproject.toml`
- 데이터: **yfinance** (주력), `httpx + selectolax` (Naver 금융 KR fallback)
- 지표: **pandas + numpy** (직접 구현, ta-lib 의존 X)
- 차트: **Chart.js 4.4.1 CDN** (README §8 plugin 그대로)
- 템플릿: **Jinja2**
- LLM 서술: **anthropic SDK (claude-opus-4-7)** — 시나리오·핵심포인트·verdict 만 위임. `--no-llm` / API 키 미설정 시 결정론 폴백
- CLI: **Typer**
- 테스트: **pytest** + VCR

## 디렉터리 구조 (목표)

```
src/stocklab/
├── __main__.py                # python -m stocklab
├── cli.py                     # Typer 엔트리
├── router.py                  # 모드 A/B/C 분기
├── config.py                  # 컬러·테마 사전·상수
├── data/{yahoo,naver,theme_pool}.py
├── indicators.py              # ema, rsi14, macd, volume_profile
├── analysts/{stock,theme,compare}.py   # 모드 A/B/C
├── narrative.py               # anthropic + 폴백 + 캐시
├── render/
│   ├── renderer.py
│   └── templates/{base,_candle.js,mode_a,mode_b,mode_c}.html.j2
└── output.py
tests/{test_router,test_indicators,test_yahoo,test_render}.py
docs/spec.md                   # 현재 README 의 시스템 프롬프트 명세 이전
```

## 구현 진행 체크리스트 (한 단계씩 완료 후 체크)

- [x] **Step 1 — Skeleton** (2026-05-07): `pyproject.toml`, venv, `cli.py` + `router.py` + `config.py` + `data/theme_pool.py`, 22 router 테스트 통과. `.venv/bin/python -m stocklab NVDA` / `"소부장 추천"` / `"NVDA vs AMD"` 모드 분기 검증.
- [x] **Step 2 — Data + Indicators** (2026-05-07): `indicators.py` (ema/rsi14/macd/volume_profile + IndicatorBundle), `data/yahoo.py` (StockSnapshot/FinancialBlock/NewsItem + fetch + KR .KS/.KQ 폴백), 37 테스트 통과. NVDA·005930 실데이터 fetch 검증 (가격·시총·26주봉·뉴스 5개).
- [x] **Step 3 — Mode A 렌더** (2026-05-07): Jinja2 환경 + `base.html.j2` (CSS 변수·PDF 버튼·@media print) + `_candle.js.j2` (Chart.js plugin) + `mode_a.html.j2` (9 섹션) + `analysts/stock.py` (ReportContext) + `output.py`. CLI 연결 후 NVDA / 005930 / BTC-USD / QQQ 4종 자산군 HTML 생성 검증 (각 42~43KB, 9 섹션·EMA 4종·RSI/MACD/매물대 모두 포함). narrative는 결정론 폴백 (Step 4에서 LLM 교체).
- [x] **Step 4 — Narrative** (2026-05-07): `narrative.py` Claude opus-4-7 tool_use JSON Schema 강제 (시나리오 3·요약 5·리스크 3·verdict 4분류). `~/.cache/stocklab/narrative/{ticker}-{date}.json` 캐시. API 키 / 호출 실패 시 결정론 폴백. `analysts/stock.py` 가 LLM 시나리오에 코드 계산 target_range 주입.
- [x] **Step 5 — Mode B** (2026-05-07): `analysts/theme.py` 후보 종목 ThreadPoolExecutor 병렬 fetch + 모멘텀 점수 (1Y 수익률·RSI·P/E·매출성장 가중) + 매트릭스 정렬 + Top3 (gold/silver/bronze) + 4그룹 (대장/성장/가치/배당) + 매크로/진입전략. `mode_b.html.j2` 보라색 THEME 배지로 7섹션. 검증: "AI 반도체" 8행 / "소부장 추천" 9행 모두 정상.
- [x] **Step 6 — Mode C** (2026-05-07): `analysts/compare.py` 두 종목 병렬 fetch + 7항목 우월성 매트릭스 (매출성장/이익률/부채/모멘텀/밸류/배당/수익률) + 비중 추천 (5:5/6:4/7:3). `mode_c.html.j2` 좌우 2컬럼 + 차트 + 우월성 매트릭스 ✓ 표시 + verdict 박스. 검증: NVDA vs AMD 4:3 / 삼성전자 vs SK하이닉스 3:4.
- [ ] **Step 7 — Polish**: `@media print` PDF 검증, KR 종목 N/A 강건성, README 사용자 가이드 재작성, `docs/spec.md` 명세 이전, `.gitignore` 보강

## 새 세션 시작 시 행동 강령

1. 이 파일을 자동으로 읽었는지 확인하고, **현재 어디까지 완료됐는지** 위 체크리스트로 파악한다.
2. `git status` + `ls src/stocklab/` 로 실제 코드 상태와 체크리스트의 일치 여부를 검증한다 (체크리스트가 실제와 다르면 코드를 진실로 본다).
3. **다음 미완료 단계**를 골라 작업한다. 단계가 끝나면 이 파일의 체크박스를 업데이트한다.
4. 핵심 결정사항 (모드 분기 / 데이터 / 지표 / 서술 / 렌더 / CLI) 은 `/Users/ham/.claude/plans/git-readme-flickering-lovelace.md` 에 상세히 있다 — 막히면 그 파일 참조.
5. **하지 말 것**:
   - 텔레그램 봇으로 만들지 말 것 (사용자가 명시적으로 거부)
   - 차트 OHLC / 재무 수치 임의 생성 금지 (README §13 룰 4) — 결측은 `None` → 템플릿 `N/A`
   - Chart.js 외 추가 차트 라이브러리 도입 금지 (README §3)
   - CSS 변수 / 컬러 팔레트 / 폰트 변경 금지 (README §3 절대 변경 금지)

## E2E 검증 명령

```bash
# 환경 셋업 (최초 1회)
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# 단계 별 검증
.venv/bin/python -m stocklab NVDA --no-llm                 # Mode A US
.venv/bin/python -m stocklab 005930 --no-llm               # Mode A KR
.venv/bin/python -m stocklab BTC-USD --no-llm              # Mode A crypto
.venv/bin/python -m stocklab QQQ --no-llm                  # Mode A ETF
.venv/bin/python -m stocklab "소부장 추천" --no-llm         # Mode B
.venv/bin/python -m stocklab "NVDA vs AMD" --no-llm        # Mode C
ANTHROPIC_API_KEY=... .venv/bin/python -m stocklab NVDA    # narrative LLM
.venv/bin/pytest -q                                        # 모든 단위 테스트
```

## 코딩 원칙 (이 프로젝트 한정)

- 결측 데이터에 가짜 값 넣지 말 것 (README §13 룰 4).
- 한 단계 끝나면 항상 브라우저로 실제 HTML 출력을 눈으로 확인하고 다음 단계로.
- 한국 종목은 yfinance → 실패 시 Naver fallback. 두 군데 다 실패해도 N/A 표시로 계속 진행.
- LLM 호출은 1 회로 묶고 JSON Schema 강제. 캐시 파일이 있으면 호출 스킵.
- Git 커밋 메시지에 Co-Authored-By 라인 넣지 말 것 (사용자 메모리).
