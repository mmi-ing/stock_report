"""리포트 HTML 파일 저장."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path


def save(html: str, key: str, out_dir: Path = Path("output")) -> Path:
    """`output/{key}_{YYYYMMDD}.html` 파일로 저장."""
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_").replace(" ", "_").replace(":", "_")
    fname = f"{safe_key}_{datetime.now():%Y%m%d}.html"
    path = out_dir / fname
    path.write_text(html, encoding="utf-8")
    return path
