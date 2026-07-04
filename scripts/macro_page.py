#!/usr/bin/env python
"""Build docs/macro.html — the Macro Health stoplight page. Fetches FRED
(needs FRED_API_KEY) and Stooq live, renders static HTML. Run by the refresh
workflow after snapshot.py; also runnable locally."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bcm.macro import build

if __name__ == "__main__":
    html = build(ROOT / "config" / "macro.yaml")
    out = ROOT / "docs" / "macro.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html)
    print(f"wrote {out}")
