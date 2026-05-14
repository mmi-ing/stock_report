"""yfinance 래퍼 — 가격, 재무, OHLC, 뉴스를 StockSnapshot 으로 정규화.

README §13 룰 4: 임의 생성 절대 금지. 결측은 None 유지 → 템플릿이 N/A 출력.
한국 종목은 .KS 우선 시도 후 실패 시 .KQ 폴백.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

import pandas as pd

AssetClass = Literal["us_stock", "kr_stock", "etf", "crypto"]


@dataclass
class FinancialBlock:
    """모드 A 의 ④ 재무 지표 5 카드 데이터."""

    revenue_ttm: float | None = None
    net_income_ttm: float | None = None
    operating_margin: float | None = None  # %
    debt_to_equity: float | None = None
    cash: float | None = None
    revenue_yoy: float | None = None
    net_income_yoy: float | None = None
    revenue_history: list[float] = field(default_factory=list)
    net_income_history: list[float] = field(default_factory=list)


@dataclass
class NewsItem:
    title: str
    publisher: str | None
    url: str | None
    published_at: datetime | None


@dataclass
class StockSnapshot:
    ticker: str
    name: str
    exchange: str | None
    currency: str
    asset_class: AssetClass
    price: Decimal | None
    change_pct: float | None
    market_cap: int | None = None
    pe_forward: float | None = None
    ps_ttm: float | None = None
    div_yield: float | None = None
    next_earnings: date | None = None
    consensus: str | None = None
    week52_high: Decimal | None = None
    week52_low: Decimal | None = None
    sector: str | None = None
    industry: str | None = None
    # 시계열
    ohlc: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    # 재무
    financials: FinancialBlock = field(default_factory=FinancialBlock)
    # 뉴스
    news: list[NewsItem] = field(default_factory=list)
    # 데이터 부족 플래그 (차트 푸터에 (est.) 표시용)
    ohlc_estimated: bool = False
    fetch_warnings: list[str] = field(default_factory=list)


def _to_weekly_ohlc(daily: pd.DataFrame, weeks: int = 26) -> pd.DataFrame:
    """일봉 → 주봉 (월~금 묶음) 으로 리샘플링, 최근 N주 반환."""
    if daily.empty:
        return pd.DataFrame()
    df = daily.copy()
    df.index = pd.to_datetime(df.index)
    weekly = df.resample("W-FRI").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna()
    weekly = weekly.tail(weeks)
    weekly = weekly.rename(columns={"Open": "O", "High": "H", "Low": "L", "Close": "C", "Volume": "V"})
    return weekly


def _safe_get(d: dict | None, key: str, default=None):
    if d is None:
        return default
    val = d.get(key, default)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    return val


def fetch_usd_krw() -> float | None:
    """USD/KRW 실시간 환율. 실패 시 None."""
    try:
        import yfinance as yf
        t = yf.Ticker("KRW=X")
        hist = t.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
        info = t.fast_info
        rate = getattr(info, "last_price", None)
        return float(rate) if rate else None
    except Exception:
        return None


def fetch(ticker: str, asset_class: AssetClass) -> StockSnapshot:
    """yfinance 로 단일 종목 데이터 수집 → StockSnapshot 으로 정규화."""
    import yfinance as yf  # 지연 임포트 — 테스트 환경에서 라이브러리 로딩 비용 회피

    warnings: list[str] = []

    yt = yf.Ticker(ticker)
    info: dict = {}
    try:
        info = yt.info or {}
    except Exception as e:
        warnings.append(f"info: {e}")

    # 가격 / 등락률
    price_raw = _safe_get(info, "currentPrice") or _safe_get(info, "regularMarketPrice")
    prev_close = _safe_get(info, "previousClose") or _safe_get(info, "regularMarketPreviousClose")
    price = Decimal(str(price_raw)) if price_raw is not None else None
    change_pct: float | None = None
    if price_raw is not None and prev_close not in (None, 0):
        try:
            change_pct = (float(price_raw) - float(prev_close)) / float(prev_close) * 100
        except Exception:
            change_pct = None

    currency = _safe_get(info, "currency") or ("KRW" if ticker.endswith((".KS", ".KQ")) else "USD")
    if asset_class == "crypto":
        currency = "USD"
    exchange = _safe_get(info, "fullExchangeName") or _safe_get(info, "exchange")
    name = (
        _safe_get(info, "longName")
        or _safe_get(info, "shortName")
        or ticker
    )

    # 메타
    week_hi = _safe_get(info, "fiftyTwoWeekHigh")
    week_lo = _safe_get(info, "fiftyTwoWeekLow")
    market_cap = _safe_get(info, "marketCap")
    pe_fwd = _safe_get(info, "forwardPE")
    ps_ttm = _safe_get(info, "priceToSalesTrailing12Months")
    div_yield = _safe_get(info, "dividendYield")
    next_earn_ts = _safe_get(info, "earningsTimestamp")
    next_earn: date | None = None
    if next_earn_ts:
        try:
            next_earn = datetime.fromtimestamp(int(next_earn_ts)).date()
        except Exception:
            pass

    # 컨센서스
    rec = _safe_get(info, "recommendationKey") or _safe_get(info, "averageAnalystRating")
    consensus = str(rec) if rec else None

    # OHLC (주봉 24~30주)
    ohlc = pd.DataFrame()
    ohlc_estimated = False
    try:
        hist = yt.history(period="2y", interval="1d", auto_adjust=False)
        ohlc = _to_weekly_ohlc(hist, weeks=26)
        if ohlc.empty:
            warnings.append("ohlc: empty history")
            ohlc_estimated = True
    except Exception as e:
        warnings.append(f"ohlc: {e}")
        ohlc_estimated = True

    # 재무
    fin = FinancialBlock(
        revenue_ttm=_safe_get(info, "totalRevenue"),
        net_income_ttm=_safe_get(info, "netIncomeToCommon"),
        operating_margin=_safe_get(info, "operatingMargins"),
        debt_to_equity=_safe_get(info, "debtToEquity"),
        cash=_safe_get(info, "totalCash"),
        revenue_yoy=_safe_get(info, "revenueGrowth"),
        net_income_yoy=_safe_get(info, "earningsGrowth"),
    )

    # 뉴스 (최대 5개)
    news_items: list[NewsItem] = []
    try:
        for item in (yt.news or [])[:5]:
            content = item.get("content") if isinstance(item, dict) else None
            if isinstance(content, dict):
                title = content.get("title") or item.get("title")
                pub = (content.get("provider") or {}).get("displayName") if content.get("provider") else None
                url = (content.get("clickThroughUrl") or {}).get("url") if content.get("clickThroughUrl") else None
                ts = content.get("pubDate") or item.get("providerPublishTime")
            else:
                title = item.get("title") if isinstance(item, dict) else None
                pub = item.get("publisher") if isinstance(item, dict) else None
                url = item.get("link") if isinstance(item, dict) else None
                ts = item.get("providerPublishTime") if isinstance(item, dict) else None
            published_at: datetime | None = None
            if ts:
                try:
                    if isinstance(ts, (int, float)):
                        published_at = datetime.fromtimestamp(int(ts))
                    else:
                        published_at = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                except Exception:
                    published_at = None
            if title:
                news_items.append(NewsItem(title=title, publisher=pub, url=url, published_at=published_at))
    except Exception as e:
        warnings.append(f"news: {e}")

    return StockSnapshot(
        ticker=ticker,
        name=str(name),
        exchange=str(exchange) if exchange else None,
        currency=str(currency),
        asset_class=asset_class,
        price=price,
        change_pct=change_pct,
        market_cap=int(market_cap) if market_cap else None,
        pe_forward=float(pe_fwd) if pe_fwd is not None else None,
        ps_ttm=float(ps_ttm) if ps_ttm is not None else None,
        div_yield=float(div_yield) if div_yield is not None else None,
        next_earnings=next_earn,
        consensus=consensus,
        week52_high=Decimal(str(week_hi)) if week_hi is not None else None,
        week52_low=Decimal(str(week_lo)) if week_lo is not None else None,
        sector=_safe_get(info, "sector"),
        industry=_safe_get(info, "industry"),
        ohlc=ohlc,
        financials=fin,
        news=news_items,
        ohlc_estimated=ohlc_estimated,
        fetch_warnings=warnings,
    )


def fetch_kr_with_fallback(ticker6: str) -> StockSnapshot:
    """6자리 한국 코드를 .KS 우선, 실패 시 .KQ 로 시도."""
    snap = fetch(f"{ticker6}.KS", "kr_stock")
    if snap.price is None:
        snap2 = fetch(f"{ticker6}.KQ", "kr_stock")
        if snap2.price is not None:
            return snap2
    return snap
