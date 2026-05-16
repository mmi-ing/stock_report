"""사용자별 관심종목 JSON 저장소."""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

_PATH = Path(__file__).parent / "data" / "watchlist.json"
_LOCK = Lock()


def _load() -> dict[str, list[str]]:
    if not _PATH.exists():
        return {}
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict[str, list[str]]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_watchlist(user_id: int) -> list[str]:
    with _LOCK:
        return _load().get(str(user_id), [])


def add_to_watchlist(user_id: int, ticker: str) -> list[str]:
    with _LOCK:
        data = _load()
        key = str(user_id)
        items = data.get(key, [])
        ticker = ticker.upper().strip()
        if ticker and ticker not in items:
            items.append(ticker)
            data[key] = items
            _save(data)
        return items


def remove_from_watchlist(user_id: int, ticker: str) -> list[str]:
    with _LOCK:
        data = _load()
        key = str(user_id)
        items = data.get(key, [])
        ticker = ticker.upper().strip()
        if ticker in items:
            items.remove(ticker)
            data[key] = items
            _save(data)
        return items


def all_users_with_watchlist() -> dict[str, list[str]]:
    with _LOCK:
        return _load()
