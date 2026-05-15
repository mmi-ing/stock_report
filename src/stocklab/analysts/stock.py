"""모드 A — 개별 종목 분석. ReportContext 를 빌드해 템플릿에 넘긴다.

이 단계 (Step 3) 의 narrative (시나리오 / 핵심포인트 / verdict) 는 결정론 폴백으로 채운다.
Step 4 에서 anthropic 연동으로 자연스러운 문장으로 교체된다.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from stocklab.config import PALETTE
from stocklab.data.yahoo import StockSnapshot, fetch_usd_krw
from stocklab.indicators import IndicatorBundle


@dataclass
class StrategyRow:
    label: str
    badge: str  # buy / hold / target / stop
    price_range: str
    weight: str
    action: str
    rationale: str
    condition: str


@dataclass
class Scenario:
    kind: str  # bull / neutral / bear
    title: str
    emoji: str
    probability: int  # 0~100
    target_range: str
    bullets: list[str]
    checks: list[str]


@dataclass
class FinCard:
    label: str
    icon: str
    value: str
    yoy: str | None
    direction: str  # up / down / neutral
    sparkline: list[float]


@dataclass
class IndustryRow:
    ticker: str
    specialty: str
    ps: str
    revenue_growth: str
    is_target: bool


@dataclass
class IndustryTags:
    positive: list[str]
    negative: list[str]
    neutral: list[str]


@dataclass
class ChartData:
    """차트 JS 로 직렬화될 묶음."""

    weeks: list[str]
    ohlc: list[list[float]]  # [[O,H,L,C], ...]
    ema5: list[float | None]
    ema20: list[float | None]
    ema60: list[float | None]
    ema120: list[float | None]
    rsi: list[float | None]
    macd: list[float | None]
    signal: list[float | None]
    hist: list[float | None]
    events: dict[int, str]  # week index → label
    volume_profile: list[dict]  # price_low, price_high, pct, zone
    current_price: float | None


@dataclass
class ReportContext:
    """mode_a.html.j2 가 사용하는 모든 데이터의 묶음."""

    ticker: str
    display_name: str
    company_sub: str
    asset_class: str
    currency: str
    price: float | None
    change_pct: float | None
    market_cap_str: str
    week52_high_str: str
    week52_low_str: str
    pe_forward_str: str
    ps_ttm_str: str
    div_yield_str: str
    next_earnings_str: str
    consensus_str: str
    sector: str
    industry: str

    chart: ChartData
    indicator_panel: dict  # rsi value/signal/desc, macd, ema 4종

    fin_cards: list[FinCard]
    strategy_rows: list[StrategyRow]
    scenarios: list[Scenario]
    industry_rows: list[IndustryRow]
    industry_tags: IndustryTags

    summary_points: list[dict]  # {num, title, body}
    risks: list[dict]  # {num, title, body}
    verdict: dict  # {label, sub}

    generated_at: str
    sources: list[str]
    palette: dict
    ohlc_estimated: bool


def _rsi_signal(rsi_val: float | None) -> tuple[str, str]:
    if rsi_val is None or pd.isna(rsi_val):
        return "N/A", "데이터 부족"
    if rsi_val >= 70:
        return "과매수 경고", "단기 차익실현 압력 가능"
    if rsi_val <= 30:
        return "과매도 매수기", "기술적 반등 가능 구간"
    return "중립 관찰", "방향성 미확인 — 추세선 확인"


def _macd_desc(macd_val: float | None, signal_val: float | None) -> str:
    if macd_val is None or signal_val is None:
        return "데이터 부족"
    if macd_val > signal_val:
        return "골든크로스 — 상승 모멘텀"
    if macd_val < signal_val:
        return "데드크로스 — 하락 모멘텀"
    return "전환 임박"


def _ema_desc(ema5: float | None, ema20: float | None, ema60: float | None) -> str:
    if None in (ema5, ema20, ema60):
        return "데이터 부족"
    if ema5 > ema20 > ema60:  # type: ignore[operator]
        return "정배열 — 상승 추세"
    if ema5 < ema20 < ema60:  # type: ignore[operator]
        return "역배열 — 하락 추세"
    return "혼조 — 추세 전환 구간"


def _build_strategy_rows(snap: StockSnapshot, ind: IndicatorBundle) -> list[StrategyRow]:
    p = float(snap.price) if snap.price else None
    if p is None:
        return []

    def _range(low_pct: float, high_pct: float) -> str:
        lo = p * (1 + low_pct / 100)
        hi = p * (1 + high_pct / 100)
        sym = "₩" if snap.currency == "KRW" else "$"
        if snap.currency == "KRW":
            return f"{sym}{lo:,.0f}~{sym}{hi:,.0f}"
        return f"{sym}{lo:,.2f}~{sym}{hi:,.2f}"

    def _single(pct: float) -> str:
        v = p * (1 + pct / 100)
        sym = "₩" if snap.currency == "KRW" else "$"
        if snap.currency == "KRW":
            return f"{sym}{v:,.0f} 이하"
        return f"{sym}{v:,.2f} 이하"

    return [
        StrategyRow("1차 매수", "buy", _range(-3, 3), "30%", "현재가 부근 진입", "EMA20 근접, 조정 마무리", "EMA20 위 종가 마감"),
        StrategyRow("2차 매수", "buy", _range(-10, -5), "35%", "조정 시 추가", "강한 매물대, 피보 38.2% 지지", "거래량 동반 반등 확인"),
        StrategyRow("3차 매수", "buy", _range(-20, -15), "25%", "급락 시 대량", "EMA120 지지대", "RSI 40 이하 + 반등 캔들"),
        StrategyRow("현금 보유", "hold", "—", "10%", "예비 실탄", "블랙스완 대비", "상시 유지"),
        StrategyRow("목표가 (3년)", "target", _range(30, 50), "—", "부분 익절", "펀더멘털 시나리오 달성", "가이던스 연속 상향"),
        StrategyRow("손절가", "stop", _single(-25), "—", "스탑로스", "추세 훼손", "EMA120 이탈 + 가이던스 하향"),
    ]


def _build_scenarios_deterministic(snap: StockSnapshot, ind: IndicatorBundle) -> list[Scenario]:
    """Step 3 용 결정론 시나리오 (RSI / EMA 위치 / 1Y 수익률 룰)."""
    latest = ind.latest()
    rsi_val = latest.get("rsi")
    close = latest.get("close")
    ema60 = latest.get("ema60")
    p_above_ema60 = close is not None and ema60 is not None and close > ema60

    bull_pr, neu_pr, bear_pr = 35, 40, 25
    if p_above_ema60 and rsi_val and rsi_val < 70:
        bull_pr, neu_pr, bear_pr = 50, 35, 15
    elif rsi_val and rsi_val > 75:
        bull_pr, neu_pr, bear_pr = 25, 35, 40
    elif rsi_val and rsi_val < 30:
        bull_pr, neu_pr, bear_pr = 45, 35, 20

    def _r(low: float, high: float) -> str:
        if not snap.price:
            return "N/A"
        sym = "₩" if snap.currency == "KRW" else "$"
        p = float(snap.price)
        a, b = p * (1 + low / 100), p * (1 + high / 100)
        if snap.currency == "KRW":
            return f"{sym}{a:,.0f}~{sym}{b:,.0f}"
        return f"{sym}{a:,.2f}~{sym}{b:,.2f}"

    return [
        Scenario(
            "bull", "강세 시나리오", "🚀", bull_pr, _r(20, 50),
            [
                "실적 컨센서스 지속 상회",
                "주요 신제품 / 신규 계약 가시화",
                "산업 사이클 회복 동반",
                "외국인 수급 지속 유입",
                "EMA20 위 안착 후 신고가 갱신",
            ],
            ["다음 분기 가이던스 상향", "주요 고객 발주 확인", "RSI 70 이하 유지"],
        ),
        Scenario(
            "neutral", "중립 시나리오", "📊", neu_pr, _r(-5, 15),
            [
                "현 추세 박스권 유지",
                "실적 컨센서스 부합",
                "신규 모멘텀 제한적",
                "거시 변수에 따라 변동",
                "EMA20~EMA60 사이 진동",
            ],
            ["거래량 평균 유지", "외국인 보유 비중 안정", "RSI 50 부근"],
        ),
        Scenario(
            "bear", "하락 시나리오", "🐻", bear_pr, _r(-30, -10),
            [
                "실적 컨센서스 하회",
                "산업 사이클 둔화 신호",
                "외국인 매도 출회",
                "주요 경쟁자 점유율 확대",
                "EMA120 이탈 후 추세 전환",
            ],
            ["가이던스 하향 발표", "재고 증가율 가속", "RSI 30 하회 후 반등 실패"],
        ),
    ]


def _build_summary_deterministic(snap: StockSnapshot, ind: IndicatorBundle) -> tuple[list[dict], list[dict], dict]:
    """Step 3 용 결정론 요약 — Step 4 에서 LLM 으로 교체된다."""
    latest = ind.latest()
    points = [
        {"num": "01", "title": "현재 추세", "body": _ema_desc(latest.get("ema5"), latest.get("ema20"), latest.get("ema60"))},
        {"num": "02", "title": "모멘텀 지표", "body": f"RSI {latest.get('rsi'):.1f} — {_rsi_signal(latest.get('rsi'))[0]}" if latest.get("rsi") else "RSI 데이터 부족"},
        {"num": "03", "title": "MACD 신호", "body": _macd_desc(latest.get("macd"), latest.get("signal"))},
        {"num": "04", "title": "재무 상태", "body": f"매출 YoY {snap.financials.revenue_yoy*100:.1f}%" if snap.financials.revenue_yoy else "재무 데이터 부족"},
        {"num": "05", "title": "밸류에이션", "body": f"Forward P/E {snap.pe_forward:.1f}" if snap.pe_forward else "P/E 데이터 부족"},
    ]
    risks = [
        {"num": "R1", "title": "기술적 리스크", "body": "주요 지지선 이탈 시 추세 전환"},
        {"num": "R2", "title": "펀더멘털 리스크", "body": "분기 실적 컨센서스 하회 가능성"},
        {"num": "R3", "title": "거시 리스크", "body": "금리·환율·정책 변수"},
    ]

    # Verdict 분류 (시나리오 확률 기반)
    scenarios = _build_scenarios_deterministic(snap, ind)
    bull = next(s for s in scenarios if s.kind == "bull").probability
    neu = next(s for s in scenarios if s.kind == "neutral").probability
    bear = next(s for s in scenarios if s.kind == "bear").probability
    if bull >= 60:
        label, sub = "★ 적극 매수 ★", "강세 시나리오 우세"
    elif bull >= 40:
        label, sub = "★ 분할매수 매력 ★", "강세 가능성 유효, 분할 진입 권장"
    elif neu >= 50:
        label, sub = "⚠ 관망 권장 ⚠", "추세 확정 후 진입"
    elif bear >= 40:
        label, sub = "🚫 비추천 🚫", "하락 위험 우세"
    else:
        label, sub = "⚠ 관망 권장 ⚠", "방향성 모호"

    verdict = {"label": label, "sub": sub}
    return points, risks, verdict


def _serialize_chart(snap: StockSnapshot, ind: IndicatorBundle) -> ChartData:
    if snap.ohlc.empty:
        return ChartData([], [], [], [], [], [], [], [], [], [], {}, [], None)

    weeks = [d.strftime("%b W%U") for d in snap.ohlc.index]
    ohlc = [
        [float(r["O"]), float(r["H"]), float(r["L"]), float(r["C"])]
        for _, r in snap.ohlc.iterrows()
    ]

    def _to_list(s: pd.Series) -> list[float | None]:
        return [None if pd.isna(v) else float(v) for v in s.tolist()]

    current = float(snap.price) if snap.price else None
    vp_dicts = []
    for vb in ind.vol_profile:
        zone = "current"
        if current is not None:
            if vb.price_high < current * 0.98:
                zone = "support"
            elif vb.price_low > current * 1.02:
                zone = "resistance"
            elif vb.price_low < current * 0.85:
                zone = "long_support"
        vp_dicts.append({
            "price_low": vb.price_low,
            "price_high": vb.price_high,
            "mid": vb.mid,
            "pct": vb.pct,
            "zone": zone,
        })

    return ChartData(
        weeks=weeks,
        ohlc=ohlc,
        ema5=_to_list(ind.ema5),
        ema20=_to_list(ind.ema20),
        ema60=_to_list(ind.ema60),
        ema120=_to_list(ind.ema120),
        rsi=_to_list(ind.rsi),
        macd=_to_list(ind.macd_line),
        signal=_to_list(ind.macd_signal),
        hist=_to_list(ind.macd_hist),
        events={},
        volume_profile=vp_dicts,
        current_price=current,
    )


def _build_fin_cards(snap: StockSnapshot) -> list[FinCard]:
    fin = snap.financials
    if snap.asset_class == "etf":
        # ETF 변형은 데이터가 다른데, 일단 기본형으로 N/A 처리 후 Step 7 에서 확장
        pass
    if snap.asset_class == "crypto":
        # Crypto 변형 동일
        pass

    def _yoy(value: float | None) -> tuple[str | None, str]:
        if value is None:
            return None, "neutral"
        pct = value * 100
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.1f}%", ("up" if pct >= 0 else "down")

    rev_yoy, rev_dir = _yoy(fin.revenue_yoy)
    ni_yoy, ni_dir = _yoy(fin.net_income_yoy)

    # 임시 스파크라인 (실제 시계열은 Step 7 에서 history 보강)
    return [
        FinCard("매출 (TTM)", "📈", _scale_money(fin.revenue_ttm, snap.currency), rev_yoy, rev_dir, []),
        FinCard("순이익 (TTM)", "💰", _scale_money(fin.net_income_ttm, snap.currency), ni_yoy, ni_dir, []),
        FinCard("영업이익률", "📊", _pct_or_na(fin.operating_margin, mult=100), None, "neutral", []),
        FinCard("부채비율 (D/E)", "🏦", _pct_or_na(fin.debt_to_equity, mult=1), None, "neutral", []),
        FinCard("현금자산", "💵", _scale_money(fin.cash, snap.currency), None, "neutral", []),
    ]


def _scale_money(v: float | None, currency: str) -> str:
    if v is None:
        return "N/A"
    if currency == "KRW":
        if v >= 1e12:
            return f"{v/1e12:.2f}조"
        if v >= 1e8:
            return f"{v/1e8:.0f}억"
        return f"{v:,.0f}"
    if v >= 1e9:
        return f"${v/1e9:.2f}B"
    if v >= 1e6:
        return f"${v/1e6:.0f}M"
    return f"${v:,.0f}"


def _pct_or_na(v: float | None, mult: float = 100) -> str:
    if v is None:
        return "N/A"
    return f"{v*mult:.1f}%"


def _rec_to_label(mean: float | None) -> str:
    if mean is None:
        return "N/A"
    if mean <= 1.5:
        return "Strong Buy"
    if mean <= 2.5:
        return "Buy"
    if mean <= 3.5:
        return "Hold"
    if mean <= 4.5:
        return "Sell"
    return "Strong Sell"


def _build_quality_block(snap: StockSnapshot) -> dict:
    fin = snap.financials
    return {
        "fcf_str": _scale_money(fin.free_cash_flow, snap.currency),
        "roe_str": f"{fin.roe*100:.1f}%" if fin.roe is not None else "N/A",
        "roa_str": f"{fin.roa*100:.1f}%" if fin.roa is not None else "N/A",
        "peg_str": f"{fin.peg_ratio:.2f}" if fin.peg_ratio is not None else "N/A",
        "ev_ebitda_str": f"{fin.ev_to_ebitda:.1f}" if fin.ev_to_ebitda is not None else "N/A",
        "gross_margin_str": f"{fin.gross_margin*100:.1f}%" if fin.gross_margin is not None else "N/A",
        "roe_class": "up" if fin.roe and fin.roe > 0.15 else ("down" if fin.roe and fin.roe < 0 else "neutral"),
        "peg_class": "up" if fin.peg_ratio and 0 < fin.peg_ratio < 1 else ("down" if fin.peg_ratio and fin.peg_ratio > 2 else "neutral"),
    }


def _build_analyst_box(snap: StockSnapshot) -> dict:
    t = snap.analyst_targets
    p = float(snap.price) if snap.price else None
    upside = None
    if t.mean and p:
        upside = (t.mean - p) / p * 100
    sym = "₩" if snap.currency == "KRW" else "$"
    fmt = (lambda v: f"{sym}{v:,.0f}") if snap.currency == "KRW" else (lambda v: f"{sym}{v:,.2f}")
    return {
        "mean_str": fmt(t.mean) if t.mean else "N/A",
        "high_str": fmt(t.high) if t.high else "N/A",
        "low_str": fmt(t.low) if t.low else "N/A",
        "n_analysts": t.n_analysts or 0,
        "upside_str": f"{upside:+.1f}%" if upside is not None else "N/A",
        "upside_class": "up" if upside and upside > 0 else "down",
        "rec_label": _rec_to_label(t.recommendation_mean),
        "rec_mean": t.recommendation_mean,
    }


def _build_market_ctx(snap: StockSnapshot) -> dict:
    m = snap.market_context
    return {
        "beta_str": f"{m.beta:.2f}" if m.beta is not None else "N/A",
        "beta_class": "down" if m.beta and m.beta > 1.5 else ("up" if m.beta and m.beta < 0.8 else "neutral"),
        "inst_str": f"{m.institutional_pct*100:.1f}%" if m.institutional_pct is not None else "N/A",
        "insider_str": f"{m.insider_pct*100:.2f}%" if m.insider_pct is not None else "N/A",
        "short_str": f"{m.short_pct_float*100:.2f}%" if m.short_pct_float is not None else "N/A",
        "short_ratio_str": f"{m.short_ratio:.1f}일" if m.short_ratio is not None else "N/A",
    }


def _build_trading_box(snap: StockSnapshot, p_val: float | None) -> dict:
    s = snap.trading_signals
    sym = "₩" if snap.currency == "KRW" else "$"
    fmt = (lambda v: f"{sym}{v:,.0f}") if snap.currency == "KRW" else (lambda v: f"{sym}{v:,.2f}")
    # 단기 추세 신호
    trend = "N/A"
    if s.ma5 and s.ma20:
        if s.ma5 > s.ma20 * 1.01:
            trend = "단기 상승 (5MA > 20MA)"
        elif s.ma5 < s.ma20 * 0.99:
            trend = "단기 하락 (5MA < 20MA)"
        else:
            trend = "혼조"
    return {
        "pos_52w_pct": f"{s.pos_in_52w_range*100:.0f}%" if s.pos_in_52w_range is not None else "N/A",
        "pos_52w_val": (s.pos_in_52w_range or 0) * 100,
        "near_high_str": f"{s.near_52w_high_pct:+.1f}%" if s.near_52w_high_pct is not None else "N/A",
        "atr_str": f"{s.atr_pct:.2f}%" if s.atr_pct is not None else "N/A",
        "atr_class": "down" if s.atr_pct and s.atr_pct > 5 else "neutral",
        "vol_spike_str": f"{s.volume_spike:.2f}x" if s.volume_spike is not None else "N/A",
        "vol_spike_class": "up" if s.volume_spike and s.volume_spike > 1.5 else "neutral",
        "daily_rsi_str": f"{s.daily_rsi:.1f}" if s.daily_rsi is not None else "N/A",
        "daily_rsi_class": "down" if s.daily_rsi and s.daily_rsi > 70 else ("up" if s.daily_rsi and s.daily_rsi < 30 else "neutral"),
        "ma5_str": fmt(s.ma5) if s.ma5 else "N/A",
        "ma20_str": fmt(s.ma20) if s.ma20 else "N/A",
        "ma50_str": fmt(s.ma50) if s.ma50 else "N/A",
        "ma200_str": fmt(s.ma200) if s.ma200 else "N/A",
        "trend_label": trend,
        "squeeze_str": f"{s.short_squeeze_score:.1f}" if s.short_squeeze_score is not None else "N/A",
        "squeeze_class": "up" if s.short_squeeze_score and s.short_squeeze_score > 50 else "neutral",
    }


def _build_eps_surprises(snap: StockSnapshot) -> list[dict]:
    out = []
    for e in snap.earnings_surprises:
        out.append({
            "quarter": e.quarter,
            "actual": f"{e.eps_actual:.2f}" if e.eps_actual is not None else "N/A",
            "estimate": f"{e.eps_estimate:.2f}" if e.eps_estimate is not None else "N/A",
            "surprise_str": f"{e.surprise_pct:+.1f}%" if e.surprise_pct is not None else "N/A",
            "beat": (e.surprise_pct or 0) > 0,
        })
    return out


def _format_company_sub(snap: StockSnapshot) -> str:
    parts = []
    if snap.exchange:
        parts.append(snap.exchange)
    if snap.sector:
        parts.append(snap.sector)
    if snap.industry:
        parts.append(snap.industry)
    return " · ".join(parts) if parts else snap.ticker


def build_context(
    snap: StockSnapshot,
    ind: IndicatorBundle,
    weights: list[str] | None = None,
    narrative_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """ReportContext 를 dict 로 반환 — 템플릿 렌더에 그대로 사용."""
    chart = _serialize_chart(snap, ind)
    latest = ind.latest()

    rsi_val = latest.get("rsi")
    rsi_sig, rsi_desc = _rsi_signal(rsi_val)

    indicator_panel = {
        "rsi": {
            "value": f"{rsi_val:.1f}" if rsi_val is not None and not pd.isna(rsi_val) else "N/A",
            "color": "red" if rsi_val and rsi_val >= 70 else "green" if rsi_val and rsi_val <= 30 else "yellow",
            "signal": rsi_sig,
            "desc": rsi_desc,
        },
        "macd": {
            "macd": f"{latest['macd']:.3f}" if latest.get("macd") is not None else "N/A",
            "signal": f"{latest['signal']:.3f}" if latest.get("signal") is not None else "N/A",
            "hist": f"{latest['hist']:.3f}" if latest.get("hist") is not None else "N/A",
            "macd_pos": (latest.get("macd") or 0) >= 0,
            "desc": _macd_desc(latest.get("macd"), latest.get("signal")),
        },
        "ema": {
            "ema5": f"{latest['ema5']:.2f}" if latest.get("ema5") else "N/A",
            "ema20": f"{latest['ema20']:.2f}" if latest.get("ema20") else "N/A",
            "ema60": f"{latest['ema60']:.2f}" if latest.get("ema60") else "N/A",
            "ema120": f"{latest['ema120']:.2f}" if latest.get("ema120") else "N/A",
            "desc": _ema_desc(latest.get("ema5"), latest.get("ema20"), latest.get("ema60")),
        },
    }

    if narrative_override:
        # Claude 가 만든 narrative — target_range 는 코드 계산값으로 보강
        code_scenarios = _build_scenarios_deterministic(snap, ind)
        code_by_kind = {s.kind: s for s in code_scenarios}
        scenarios = narrative_override.get("scenarios") or [asdict(s) for s in code_scenarios]
        for s in scenarios:
            if isinstance(s, dict) and not s.get("target_range") and s.get("kind") in code_by_kind:
                s["target_range"] = code_by_kind[s["kind"]].target_range
                s.setdefault("emoji", {"bull": "🚀", "neutral": "📊", "bear": "🐻"}.get(s["kind"], ""))
                s.setdefault("title", {"bull": "강세 시나리오", "neutral": "중립 시나리오", "bear": "하락 시나리오"}.get(s["kind"], ""))
        points = narrative_override.get("summary_points") or _build_summary_deterministic(snap, ind)[0]
        risks = narrative_override.get("risks") or _build_summary_deterministic(snap, ind)[1]
        verdict = narrative_override.get("verdict") or _build_summary_deterministic(snap, ind)[2]
    else:
        scenarios_obj = _build_scenarios_deterministic(snap, ind)
        scenarios = [asdict(s) for s in scenarios_obj]
        points, risks, verdict = _build_summary_deterministic(snap, ind)

    industry_tags = IndustryTags(
        positive=["산업 성장 모멘텀 (예시)", "정책 우호적 (예시)", "글로벌 트렌드 부합 (예시)"],
        negative=["주요 경쟁사 진입 (예시)", "원가 상승 (예시)"],
        neutral=["사이클 후반부 (예시)", "환율 변수 (예시)"],
    )
    industry_rows: list[IndustryRow] = []  # Step 7 에서 .info 의 동종업계로 보강

    p_val = float(snap.price) if snap.price else None
    change_str = "N/A"
    if snap.change_pct is not None:
        sign = "+" if snap.change_pct >= 0 else ""
        change_str = f"{sign}{snap.change_pct:.2f}%"

    # 미장/크립토 → KRW 환산 (실시간 USD/KRW)
    krw_price_str = ""
    if snap.currency == "USD" and p_val:
        rate = fetch_usd_krw()
        if rate:
            krw_val = p_val * rate
            krw_price_str = f"₩{krw_val:,.0f}"

    ctx = {
        "ticker": snap.ticker,
        "display_name": snap.name,
        "company_sub": _format_company_sub(snap),
        "asset_class": snap.asset_class,
        "currency": snap.currency,
        "price": p_val,
        "price_str": _scale_money(p_val, snap.currency).lstrip("$").lstrip("₩") if p_val else "N/A",
        "price_symbol": "₩" if snap.currency == "KRW" else "$",
        "krw_price_str": krw_price_str,
        "change_str": change_str,
        "change_pct": snap.change_pct,
        "market_cap_str": _scale_money(snap.market_cap, snap.currency),
        "week52_high_str": _scale_money(float(snap.week52_high) if snap.week52_high else None, snap.currency),
        "week52_low_str": _scale_money(float(snap.week52_low) if snap.week52_low else None, snap.currency),
        "pe_forward_str": f"{snap.pe_forward:.2f}" if snap.pe_forward else "N/A",
        "ps_ttm_str": f"{snap.ps_ttm:.2f}" if snap.ps_ttm else "N/A",
        "div_yield_str": f"{snap.div_yield*100:.2f}%" if snap.div_yield else "N/A",
        "next_earnings_str": snap.next_earnings.strftime("%Y.%m.%d") if snap.next_earnings else "N/A",
        "consensus_str": snap.consensus or "N/A",
        "sector": snap.sector or "N/A",
        "industry": snap.industry or "N/A",
        "quality": _build_quality_block(snap),
        "analyst_box": _build_analyst_box(snap),
        "market_ctx": _build_market_ctx(snap),
        "trading_box": _build_trading_box(snap, p_val),
        "eps_surprises": _build_eps_surprises(snap),
        "chart": asdict(chart),
        "indicator_panel": indicator_panel,
        "fin_cards": [asdict(c) for c in _build_fin_cards(snap)],
        "strategy_rows": [asdict(r) for r in _build_strategy_rows(snap, ind)],
        "scenarios": scenarios,
        "industry_rows": [asdict(r) for r in industry_rows],
        "industry_tags": asdict(industry_tags),
        "summary_points": points,
        "risks": risks,
        "verdict": verdict,
        "generated_at": datetime.now().strftime("%Y.%m.%d"),
        "sources": ["Yahoo Finance"],
        "palette": PALETTE,
        "ohlc_estimated": snap.ohlc_estimated,
        "weights": weights or [],
    }
    return ctx
