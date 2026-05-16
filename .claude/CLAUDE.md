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
- [x] **Step 7 — Polish** (2026-05-07): `docs/spec.md` 에 initial commit README 의 시스템 프롬프트 명세(678줄) 보관. `docs/usage.md` 에 CLI 사용 가이드 (설치·모드별 예시·옵션·환경변수·PDF 저장·트러블슈팅·자동화). `.gitignore` 이미 정리됨. PDF print CSS 검증 (`@media print` / `page-break-inside: avoid` / 화이트 모드 변환 모두 적용). README.md 는 사용자 직접 수정 중이라 건드리지 않음. **전체 7단계 완료. 37 테스트 통과. 4 자산군 + 2 테마 + 2 비교 = 8개 리포트 모두 생성 검증.**

---

## Phase 2 — Streamlit Cloud 공유 (남은 작업)

### 확정된 결정 (2026-05-08)
- 공유 방식: **Streamlit Cloud** (무료, 24시간, 친구는 URL 클릭만)
- AI 글쓰기: **켜고 본인 비용 부담** (지인 5~10명이면 월 1~5만원)
- 차단: **비밀번호 1개** (카톡으로 공유)
- GitHub Public/Private: 일단 로컬 동작 확인 후 결정

### 남은 작업 체크리스트
- [x] **Phase 2a — Streamlit 앱** (2026-05-15): `app.py` 검색창 + 9섹션 + 비번 게이트(이후 제거)
- [x] **Phase 2b — GitHub push** (2026-05-15): Public, `mmi-ing/stock_report`
- [x] **Phase 2c — Streamlit Cloud 연동** (2026-05-15): 자동 재배포 동작
- [x] **Phase 2d — 친구 공유** (2026-05-15): URL만으로 접근 (비번 제거)

## Phase 2.5 — 데이터/UX 강화 (2026-05-15)

- [x] 대소문자 무시, 부분 이름 매칭(하이닉스→SK하이닉스 등)
- [x] 미국 주식 한글명 사전 80+ (엔비디아/애플/테슬라/팔란티어 등)
- [x] 후보 클릭 → 검색창 자동 입력 + 즉시 리포트 생성
- [x] 모바일 반응형 CSS (@media max-width:768px)
- [x] 미장 가격 옆 ≈ ₩원화 환산 (실시간 USD/KRW)
- [x] **분석 데이터 대폭 확장** (commit 051ca0e):
  - 퀄리티: FCF, ROE, ROA, PEG, EV/EBITDA, Gross Margin
  - 애널리스트: 평균/최고/최저 목표가 + 상승여력 + 매수의견
  - 시장 컨텍스트: 베타, 기관보유%, 내부자%, 공매도%, 숏 회전일
  - 단타 지표: 52주 위치, ATR(14)%, 거래량 spike, 일봉 RSI, 숏 스퀴즈 점수, MA5/20/50/200
  - EPS 서프라이즈: 최근 4분기 actual/estimate/surprise% + BEAT/MISS

### 핵심 코드 (작성 예정 `app.py`)
- Streamlit 1.x, 단일 파일
- 비번 게이트 (`st.text_input(type='password')` + `st.session_state`)
- 검색창 → `router.parse` → mode A/B/C 자동 분기 → `renderer.render` → `st.components.v1.html` 로 9섹션 표시
- AI 토글 (켜면 `narrative.generate` 호출, 꺼지면 `--no-llm` 폴백)
- 일일 호출 캡 (Streamlit 캐시 + 카운터)

## Phase 3a — 텔레그램 알림 봇 (2026-05-17 시작)

stocklab 모듈을 텔레그램 봇으로 노출. 같은 git repo 안 `bot/` 폴더.

### 구조
```
bot/
├── main.py                 # python-telegram-bot Application
├── storage.py              # 사용자별 관심종목 JSON
├── news_fetcher.py         # Yahoo RSS + yfinance 뉴스 fetch
├── news_db.py              # SQLite 뉴스 중복방지
├── handlers/
│   ├── ticker.py           # 자유 텍스트 → stocklab 리포트 + HTML 첨부
│   ├── watchlist.py        # /add /remove /list
│   └── news.py             # /news [TICKER] 명령어
├── jobs/
│   ├── premarket.py        # 미장 프리뷰/마감 요약 broadcast
│   └── news_monitor.py     # 2시간마다 관심종목 뉴스 모니터링
└── data/
    ├── watchlist.json      # {user_id: [tickers]}
    └── news.db             # 전송된 뉴스 ID (SQLite)
```

### 자동 알림 (KST)
- **07:30** — 미장 마감 요약 + 관심종목 변동
- **20:00** — 미장 프리뷰 + 매크로 (S&P/Nasdaq/Dow/VIX/USD-KRW)

### 명령어
- 자유 텍스트: `NVDA` / `엔비디아` / `AI 반도체` / `NVDA vs AMD`
- `/관심추가 NVDA` `/관심제거 NVDA` `/관심목록`
- `/start` `/help`

### 진행
- [x] 봇 골격 + handlers + jobs + storage (2026-05-17)
- [x] **Phase 3b — 뉴스 알림 봇** (2026-05-17): Yahoo RSS + yfinance fallback + SQLite 중복방지 + `/news` 명령어 + 2시간마다 관심종목 모니터링
- [ ] BotFather 토큰 발급 + 로컬 동작 테스트
- [ ] 호스팅 결정 (Oracle Cloud Always Free / Fly.io / 로컬)
- [ ] 미장 캘린더 API (실적 발표 예정) 추가
- [ ] 시나리오 강세 60%+ 자동 알림 트리거

### 호스팅 옵션
- **Oracle Cloud Always Free** — 영구 무료 ARM VM (추천)
- **Fly.io** — 카드 등록 필요
- **로컬 PC** — 컴 켜있어야 함
- **GitHub Actions cron** — 스케줄만 가능, 인터랙티브 불가능

## Phase 3 — 자동매매 로드맵 (단계적, 안전 우선)

자동매매 코드 자체는 1~2주면 만들 수 있으나 **잘 만드는 건 매우 어려움**. 권장 순서:

1. **알림 봇** (다음 우선 작업) — 시나리오 강세 60%+ 되면 텔레그램 전송. 매매는 손으로. 1~2일.
2. **모의 매매** — Alpaca 페이퍼 / 한투 모의 계좌. 1주.
3. **백테스트** — 과거 1~3년 시뮬레이션 + 손실 시나리오. 1주.
4. **소액 자동 매매** — 총자산 1~5%. 위험 시작.
5. **본격 자동 매매** — 충분한 검증 후.

### 증권사 API 옵션
- 한국 주식: 한국투자증권 OpenAPI (모의 계좌 무료)
- 미국 주식: Alpaca (페이퍼 무료, 가장 쉬움)
- 코인: 업비트 / 바이낸스 (모의 없음, 위험)

### 코드 재활용
- 분석 모듈의 시나리오 확률·매매 전략 테이블이 그대로 매매 신호로 변환 가능
- `stocklab.analysts.stock._build_scenarios_deterministic` 의 확률 룰을 알림/매매 트리거로 재사용

### 위험 요소 (기록 — 매매 코드 작성 시 반드시 점검)
- 알고리즘 버그 = 직접적 금전 손실
- 슬리피지·수수료로 백테스트 수익이 실전에서 사라질 수 있음
- API 키 유출 시 자산 즉시 탈취 (반드시 환경변수·Secrets로만)
- 백테스트 과적합 — 과거에 좋아도 미래엔 안 통할 수 있음
- 갭다운·서킷브레이커 시 알고리즘 이상 동작 가능

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
