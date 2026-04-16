#!/usr/bin/env python3
"""Regenerate dist/index.html without using git or GitHub.

Reads the full dashboard markup from config/dashboard_template.html (tracked),
substitutes GEN_TS from output/bigdata_cache.db last finished run, optionally
verifies chunk_id strings against search_results, and writes dist/index.html.

Run from repo root:
  python3 scripts/build_dashboard.py
"""

from __future__ import annotations

import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "config" / "dashboard_template.html"
OUT = ROOT / "dist" / "index.html"
DB_PATH = ROOT / "output" / "bigdata_cache.db"


def _gen_ts_from_db() -> str:
    if not DB_PATH.is_file():
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT finished_at FROM runs WHERE finished_at IS NOT NULL ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    raw = str(row[0])
    if raw.endswith("+00:00"):
        raw = raw[:-6] + "+00:00"
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _verify_chunk_ids(html: str) -> list[str]:
    if not DB_PATH.is_file():
        return []
    ids = re.findall(r'chunk_id:"([^"]+)"', html)
    ids = [i for i in ids if i != "null"]
    conn = sqlite3.connect(DB_PATH)
    missing: list[str] = []
    for cid in ids:
        hit = conn.execute("SELECT 1 FROM search_results WHERE chunk_id=?", (cid,)).fetchone()
        if not hit:
            missing.append(cid)
    conn.close()
    return missing


def main() -> int:
    if not TEMPLATE.is_file():
        print(f"ERROR: missing template {TEMPLATE}", file=sys.stderr)
        print("Create it once from a known-good dashboard HTML (same as dist/index.html).", file=sys.stderr)
        return 1
    html = TEMPLATE.read_text(encoding="utf-8")
    gen_ts = _gen_ts_from_db()
    html_new, n = re.subn(
        r'const GEN_TS = "[^"]*";',
        f'const GEN_TS = "{gen_ts}";',
        html,
        count=1,
    )
    if n != 1:
        print(f"ERROR: expected exactly one GEN_TS line, replaced {n}", file=sys.stderr)
        return 1
    missing = _verify_chunk_ids(html_new)
    if missing:
        print("WARNING: chunk_ids not found in output/bigdata_cache.db:", file=sys.stderr)
        for m in missing[:25]:
            print(f"  {m}", file=sys.stderr)
        if len(missing) > 25:
            print(f"  ... and {len(missing) - 25} more", file=sys.stderr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html_new, encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes), GEN_TS={gen_ts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
