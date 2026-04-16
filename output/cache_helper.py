"""
cache_helper.py — SQLite-backed cache for Bigdata MCP responses.
Stores entity resolutions and search result chunks across runs.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DB_DIR, "bigdata_cache.db")

# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _init_schema(conn)
    return conn

def _init_schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS entities (lookup TEXT PRIMARY KEY, entity_id TEXT, company_type TEXT, resolved_name TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS search_results (chunk_id TEXT PRIMARY KEY, run_id TEXT, query TEXT, airline TEXT, headline TEXT, snippet TEXT, url TEXT, source_name TEXT, timestamp TEXT, raw_json TEXT, created_at TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, started_at TEXT, finished_at TEXT, airlines_count INTEGER, chunks_count INTEGER)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS dashboard_kv (
            tile_key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            value_text TEXT NOT NULL,
            sub TEXT NOT NULL,
            sub_color TEXT NOT NULL,
            chunk_id TEXT,
            source_name TEXT,
            document_date TEXT,
            url TEXT,
            verbatim_quote TEXT,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.commit()

# ---------------------------------------------------------------------------
# Run management
# ---------------------------------------------------------------------------

def start_run(run_id):
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO runs(run_id, started_at) VALUES (?,?)",
        (run_id, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    return run_id

def finish_run(run_id, airlines_count=0, chunks_count=0):
    conn = _get_conn()
    conn.execute(
        "UPDATE runs SET finished_at=?, airlines_count=?, chunks_count=? WHERE run_id=?",
        (datetime.now(timezone.utc).isoformat(), airlines_count, chunks_count, run_id)
    )
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Entity cache
# ---------------------------------------------------------------------------

def save_entity(lookup, entity_id, company_type, resolved_name):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO entities(lookup, entity_id, company_type, resolved_name) VALUES (?,?,?,?)",
        (lookup, entity_id, company_type, resolved_name)
    )
    conn.commit()
    conn.close()

def get_entity(lookup):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM entities WHERE lookup=?", (lookup,)).fetchone()
    conn.close()
    return dict(row) if row else None

# ---------------------------------------------------------------------------
# Search chunk cache
# ---------------------------------------------------------------------------

def _chunk_identifier(chunk):
    """Derive a stable dedup key from a chunk dict."""
    for key in ("id", "chunk_id", "document_id"):
        if chunk.get(key):
            return str(chunk[key])
    # synthetic fallback
    parts = [chunk.get("url",""), chunk.get("timestamp",""), chunk.get("headline","")]
    return "|".join(str(p) for p in parts)[:255]

def save_search_chunks(run_id, query, airline, chunks):
    """Save a list of chunk dicts. Returns number of newly inserted rows."""
    if not isinstance(chunks, list):
        raise ValueError("chunks must be a list")
    conn = _get_conn()
    inserted = 0
    for ch in chunks:
        cid = _chunk_identifier(ch)
        src = ch.get("source") or {}
        src_name = src.get("name","") if isinstance(src, dict) else str(src)
        try:
            conn.execute(
                """INSERT OR IGNORE INTO search_results
                   (chunk_id, run_id, query, airline, headline, snippet, url, source_name, timestamp, raw_json)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    cid, run_id, query, airline,
                    ch.get("headline",""),
                    ch.get("snippet","") or ch.get("text",""),
                    ch.get("url",""),
                    src_name,
                    ch.get("timestamp","") or ch.get("date",""),
                    json.dumps(ch)
                )
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except Exception as e:
            print(f"  Warning: could not insert chunk {cid}: {e}", file=sys.stderr)
    conn.commit()
    conn.close()
    return inserted


def flatten_bigdata_search_documents(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand MCP bigdata_search `results` (documents with nested chunks) into flat chunk dicts."""
    out: list[dict[str, Any]] = []
    for doc in results or []:
        doc_id = str(doc.get("id", ""))
        for ch in doc.get("chunks") or []:
            if not isinstance(ch, dict):
                continue
            cnum = ch.get("cnum")
            cid = f"{doc_id}_{cnum}" if doc_id and cnum is not None else doc_id or _chunk_identifier(doc)
            out.append(
                {
                    "id": cid,
                    "headline": doc.get("headline", "") or "",
                    "timestamp": doc.get("timestamp", "") or "",
                    "url": doc.get("url", "") or "",
                    "source": doc.get("source") if isinstance(doc.get("source"), dict) else {},
                    "snippet": ch.get("text", "") or "",
                }
            )
    return out


def save_bigdata_search_response(run_id: str, query: str, airline: str | None, payload: dict[str, Any]) -> int:
    """Persist MCP bigdata_search JSON (object with `results` list) via save_search_chunks."""
    results = payload.get("results")
    if not isinstance(results, list):
        results = []
    return save_search_chunks(run_id, query, airline, flatten_bigdata_search_documents(results))


def get_all_chunks_for_airline(airline_name):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM search_results WHERE airline=? ORDER BY timestamp DESC",
        (airline_name,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Dashboard header tiles (published macro snapshot — option A)
# ---------------------------------------------------------------------------

MARKET_TILE_KEYS: tuple[str, ...] = (
    "brent_crude",
    "jet_fuel_nw_eu",
    "jet_crack_spread",
    "hormuz_status",
)


def list_dashboard_tiles() -> list[dict[str, Any]]:
    """Return all rows from dashboard_kv ordered by canonical tile key order, then extras."""
    conn = _get_conn()
    rows = {r["tile_key"]: dict(r) for r in conn.execute("SELECT * FROM dashboard_kv").fetchall()}
    conn.close()
    ordered: list[dict[str, Any]] = []
    for k in MARKET_TILE_KEYS:
        if k in rows:
            ordered.append(rows[k])
    for k, r in sorted(rows.items()):
        if k not in MARKET_TILE_KEYS:
            ordered.append(r)
    return ordered


def save_dashboard_tile(
    tile_key: str,
    label: str,
    value_text: str,
    sub: str,
    sub_color: str,
    *,
    chunk_id: str | None = None,
    source_name: str | None = None,
    document_date: str | None = None,
    url: str | None = None,
    verbatim_quote: str | None = None,
) -> None:
    """Upsert one header market tile. When chunk_id is set and provenance fields are omitted, fills from search_results."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    if chunk_id and (source_name is None or document_date is None or url is None or verbatim_quote is None):
        row = conn.execute("SELECT * FROM search_results WHERE chunk_id=?", (chunk_id,)).fetchone()
        if row:
            rowd = dict(row)
            source_name = source_name or rowd.get("source_name") or ""
            url = url or rowd.get("url") or ""
            snip = rowd.get("snippet") or ""
            verbatim_quote = verbatim_quote or (snip[:800] + ("…" if len(snip) > 800 else ""))
            ts = rowd.get("timestamp") or ""
            document_date = document_date or (ts[:10] if len(ts) >= 10 else ts)
    conn.execute(
        """INSERT INTO dashboard_kv (
            tile_key, label, value_text, sub, sub_color, chunk_id, source_name, document_date, url, verbatim_quote, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(tile_key) DO UPDATE SET
            label=excluded.label,
            value_text=excluded.value_text,
            sub=excluded.sub,
            sub_color=excluded.sub_color,
            chunk_id=excluded.chunk_id,
            source_name=excluded.source_name,
            document_date=excluded.document_date,
            url=excluded.url,
            verbatim_quote=excluded.verbatim_quote,
            updated_at=excluded.updated_at
        """,
        (
            tile_key,
            label,
            value_text,
            sub,
            sub_color,
            chunk_id,
            source_name or "",
            document_date or "",
            url or "",
            verbatim_quote or "",
            now,
        ),
    )
    conn.commit()
    conn.close()


def delete_dashboard_tile(tile_key: str) -> int:
    conn = _get_conn()
    cur = conn.execute("DELETE FROM dashboard_kv WHERE tile_key=?", (tile_key,))
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _stats():
    conn = _get_conn()
    total_chunks = conn.execute("SELECT COUNT(*) FROM search_results").fetchone()[0]
    cached_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    run = conn.execute("SELECT run_id, finished_at FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
    completed_runs = conn.execute("SELECT COUNT(*) FROM runs WHERE finished_at IS NOT NULL").fetchone()[0]
    conn.close()
    last_run = run["finished_at"] if run and run["finished_at"] else None
    unique_airlines = len(set())
    conn2 = _get_conn()
    unique_airlines = conn2.execute("SELECT COUNT(DISTINCT airline) FROM search_results WHERE airline IS NOT NULL").fetchone()[0]
    kv_n = 0
    try:
        kv_n = conn2.execute("SELECT COUNT(*) FROM dashboard_kv").fetchone()[0]
    except sqlite3.OperationalError:
        kv_n = 0
    conn2.close()
    return {
        "total_chunks": total_chunks,
        "unique_airlines": unique_airlines,
        "cached_entities": cached_entities,
        "completed_runs": completed_runs,
        "last_run": last_run,
        "dashboard_kv_rows": kv_n,
    }

def _entities():
    conn = _get_conn()
    rows = conn.execute("SELECT lookup, entity_id, company_type, resolved_name FROM entities").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def _airlines_with_chunks():
    conn = _get_conn()
    rows = conn.execute(
        "SELECT airline, COUNT(*) as n FROM search_results WHERE airline IS NOT NULL GROUP BY airline"
    ).fetchall()
    conn.close()
    return {r["airline"]: r["n"] for r in rows}

def _uncached(*lookups):
    conn = _get_conn()
    missing = []
    for lk in lookups:
        row = conn.execute("SELECT entity_id FROM entities WHERE lookup=?", (lk,)).fetchone()
        if not row:
            missing.append(lk)
    conn.close()
    return missing

def _chunks():
    conn = _get_conn()
    n = conn.execute("SELECT COUNT(*) FROM search_results").fetchone()[0]
    conn.close()
    return {"search_results_rows": n}

# ---------------------------------------------------------------------------
# Entry point (CLI)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Usage: cache_helper.py <command> [args]")
        sys.exit(1)
    cmd = args[0]
    if cmd == "stats":
        print(json.dumps(_stats(), indent=2))
    elif cmd == "entities":
        rows = _entities()
        print(json.dumps(rows, indent=2))
        print(f"Total: {len(rows)} entities")
    elif cmd == "uncached":
        missing = _uncached(*args[1:])
        print(json.dumps(missing))
    elif cmd == "airlines-with-chunks":
        print(json.dumps(_airlines_with_chunks(), indent=2))
    elif cmd == "chunks":
        print(json.dumps(_chunks(), indent=2))
    elif cmd == "save-mcp":
        # Usage: save-mcp <run_id> <query> <airline_or_dash> < stdin.json
        # Use "-" for airline to mean None (supplementary queries).
        if len(args) < 4:
            print("Usage: cache_helper.py save-mcp <run_id> <query> <airline_or_-> < stdin.json", file=sys.stderr)
            sys.exit(1)
        run_id, query, airline_s = args[1], args[2], args[3]
        airline: str | None = None if airline_s == "-" else airline_s
        payload = json.load(sys.stdin)
        n = save_bigdata_search_response(run_id, query, airline, payload)
        print(n)
    elif cmd == "dashboard-tiles-list":
        print(json.dumps(list_dashboard_tiles(), indent=2))
    elif cmd == "dashboard-tiles-import":
        if len(args) < 2:
            print("Usage: cache_helper.py dashboard-tiles-import <path.json>", file=sys.stderr)
            sys.exit(1)
        path = args[1]
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            print("JSON must be a list of tile objects", file=sys.stderr)
            sys.exit(1)
        for obj in raw:
            save_dashboard_tile(
                str(obj["tile_key"]),
                str(obj["label"]),
                str(obj["value_text"]),
                str(obj["sub"]),
                str(obj["sub_color"]),
                chunk_id=obj.get("chunk_id"),
                source_name=obj.get("source_name"),
                document_date=obj.get("document_date"),
                url=obj.get("url"),
                verbatim_quote=obj.get("verbatim_quote"),
            )
        print(f"Imported {len(raw)} dashboard_kv row(s)")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
