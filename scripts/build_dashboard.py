#!/usr/bin/env python3
"""Regenerate dist/index.html without using git or GitHub.

Reads the full dashboard markup from config/dashboard_template.html (tracked),
substitutes GEN_TS from output/bigdata_cache.db last finished run, merges
STATIC_MARKET_TILES from dashboard_kv (option A) when rows exist, optionally
verifies chunk_id strings against search_results, and writes dist/index.html.

Run from repo root:
  python3 scripts/build_dashboard.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "config" / "dashboard_template.html"
OUT = ROOT / "dist" / "index.html"
DB_PATH = ROOT / "output" / "bigdata_cache.db"
CACHE_HELPER = ROOT / "output" / "cache_helper.py"

# Defaults when dashboard_kv has no row for that tile_key (same order as MARKET_TILE_KEYS).
DEFAULT_MARKET_TILES: list[dict[str, str]] = [
    {
        "label": "Brent Crude",
        "value": "$110/bbl",
        "sub": "Manual scenario marker (not spot ICE)",
        "subColor": "#ef4444",
    },
    {
        "label": "Jet Fuel NW EU",
        "value": "$1,730/mt",
        "sub": "+133% vs pre-conflict baseline (manual)",
        "subColor": "#ef4444",
    },
    {
        "label": "Jet Crack Spread",
        "value": "$45+/bbl",
        "sub": "vs historical avg $8–12/bbl (manual)",
        "subColor": "#f97316",
    },
    {
        "label": "Hormuz Status",
        "value": "RESTRICTED",
        "sub": "Scenario label (manual)",
        "subColor": "#f97316",
    },
]


def _load_cache_helper():
    spec = importlib.util.spec_from_file_location("cache_helper", CACHE_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {CACHE_HELPER}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _merged_market_tiles(market_tile_keys: tuple[str, ...]) -> list[dict[str, str]]:
    if not DB_PATH.is_file():
        return list(DEFAULT_MARKET_TILES)
    conn = sqlite3.connect(DB_PATH)
    rows: dict[str, tuple] = {}
    try:
        for r in conn.execute(
            "SELECT tile_key, label, value_text, sub, sub_color FROM dashboard_kv"
        ).fetchall():
            rows[r[0]] = r
    except sqlite3.OperationalError:
        rows = {}
    finally:
        conn.close()
    out: list[dict[str, str]] = []
    for i, key in enumerate(market_tile_keys):
        base = DEFAULT_MARKET_TILES[i] if i < len(DEFAULT_MARKET_TILES) else DEFAULT_MARKET_TILES[-1]
        if key not in rows:
            out.append(dict(base))
            continue
        _tk, label, value_text, sub, sub_color = rows[key]
        out.append(
            {
                "label": str(label),
                "value": str(value_text),
                "sub": str(sub),
                "subColor": str(sub_color),
            }
        )
    return out


def _replace_static_market_tiles(html: str, tiles: list[dict[str, str]]) -> str:
    marker = "\n\nconst AUDIT_CHUNKS"
    start = html.find("// Header snapshot tiles")
    if start == -1:
        start = html.find("const STATIC_MARKET_TILES")
    if start == -1:
        print("WARNING: STATIC_MARKET_TILES block not found; skipping tile merge", file=sys.stderr)
        return html
    end = html.find(marker, start)
    if end == -1:
        print("WARNING: AUDIT_CHUNKS marker not found; skipping tile merge", file=sys.stderr)
        return html
    comment = (
        "// Header snapshot tiles (first four): values from SQLite dashboard_kv when a row\n"
        "// exists for each tile_key; otherwise defaults in scripts/build_dashboard.py.\n"
        "// Update rows after macro searches (see update-dashboard.md). At-risk / Unhedged tiles are computed in App().\n"
    )
    injected = comment + "const STATIC_MARKET_TILES = " + json.dumps(tiles, ensure_ascii=False) + ";"
    return html[:start] + injected + html[end:]


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

    try:
        ch = _load_cache_helper()
        keys: tuple[str, ...] = tuple(ch.MARKET_TILE_KEYS)
        tiles = _merged_market_tiles(keys)
        html_new = _replace_static_market_tiles(html_new, tiles)
        n_kv = 0
        if DB_PATH.is_file():
            conn = sqlite3.connect(DB_PATH)
            try:
                n_kv = int(conn.execute("SELECT COUNT(*) FROM dashboard_kv").fetchone()[0])
            except sqlite3.OperationalError:
                n_kv = 0
            finally:
                conn.close()
        print(f"Market tiles merged from dashboard_kv (rows={n_kv})")
    except Exception as e:
        print(f"WARNING: market tile merge skipped: {e}", file=sys.stderr)

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
