"""Jinja2 환경 설정 + 숫자/통화 포맷 헬퍼."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _fmt_money(value: Any, currency: str = "USD", decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if currency == "KRW":
        return f"₩{v:,.0f}"
    return f"${v:,.{decimals}f}"


def _fmt_market_cap(value: Any, currency: str = "USD") -> str:
    """시가총액 — KRW 는 '조/억', USD 는 'B/T' 단위."""
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if currency == "KRW":
        # 100,000,000 (억), 1,000,000,000,000 (조)
        if v >= 1e12:
            return f"{v / 1e12:.2f}조"
        if v >= 1e8:
            return f"{v / 1e8:.0f}억"
        return f"{v:,.0f}"
    if v >= 1e12:
        return f"${v / 1e12:.2f}T"
    if v >= 1e9:
        return f"${v / 1e9:.2f}B"
    if v >= 1e6:
        return f"${v / 1e6:.0f}M"
    return f"${v:,.0f}"


def _fmt_pct(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "N/A"
    return f"{v:+.{decimals}f}%" if v != 0 else f"{v:.{decimals}f}%"


def _fmt_num(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_date(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return value.strftime("%Y.%m.%d")
    except AttributeError:
        return str(value)


def _json_safe(obj: Any) -> Any:
    """Decimal·numpy 스칼라 등 jinja tojson 이 다루기 어려운 값을 표준 타입으로."""
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "tolist"):
        return obj.tolist()
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    return obj


def _tojson_safe(value: Any) -> str:
    def default(o: Any) -> Any:
        return _json_safe(o)

    return json.dumps(value, default=default, ensure_ascii=False)


def get_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=False,  # 우리는 신뢰된 템플릿이고 HTML/JS 직접 작성
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
    )
    env.filters["money"] = _fmt_money
    env.filters["market_cap"] = _fmt_market_cap
    env.filters["pct"] = _fmt_pct
    env.filters["num"] = _fmt_num
    env.filters["fdate"] = _fmt_date
    env.filters["tojson_safe"] = _tojson_safe
    return env


def render(template_name: str, context: dict[str, Any]) -> str:
    env = get_env()
    return env.get_template(template_name).render(**context)
