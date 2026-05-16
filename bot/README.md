# Stock Lab Telegram Bot

stocklab 분석 엔진을 텔레그램 봇으로 노출. 검색·관심종목·정기 알림 지원.

## 셋업

### 1. 봇 토큰 발급
- 텔레그램에서 `@BotFather` 검색
- `/newbot` → 이름·아이디 설정 → 토큰 받기

### 2. 의존성
```bash
.venv/bin/pip install -e ".[bot]"
```

### 3. 환경변수
```bash
export TELEGRAM_BOT_TOKEN="123456:ABC..."
export ANTHROPIC_API_KEY="sk-ant-..."  # 선택: narrative LLM
```

### 4. 실행
```bash
.venv/bin/python -m bot.main
```

## 사용

- 자유 텍스트: `NVDA`, `엔비디아`, `AI 반도체 추천`, `NVDA vs AMD`
- `/관심추가 NVDA`
- `/관심제거 NVDA`
- `/관심목록`
- `/start` 또는 `/help`

## 자동 알림 (KST)
- **07:30** — 미장 마감 요약 + 내 관심종목 변동
- **20:00** — 미장 프리뷰 + 매크로

## 호스팅 옵션
- **Oracle Cloud Always Free** — 영구 무료, ARM VM 1대 (추천)
- **Fly.io** — 카드 등록 필요, 무료 한도
- **로컬 PC** — 컴퓨터 켜있어야 함
