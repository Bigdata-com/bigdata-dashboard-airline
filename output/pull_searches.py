#!/usr/bin/env python3
"""Cold-start / full-history batch: POST /v1/search per airline + supplementary, save to SQLite."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"
TICKERS_PATH = REPO_ROOT / "config" / "tickers.json"
API_URL = "https://api.bigdata.com/v1/search"

EU_COUNTRIES = {"Greece", "France", "Finland", "Germany", "Ireland", "UK", "Spain", "Netherlands"}


def _load_api_key() -> str:
    if os.environ.get("BIGDATA_API_KEY"):
        return os.environ["BIGDATA_API_KEY"].strip()
    if ENV_PATH.is_file():
        for line in ENV_PATH.read_text().splitlines():
            if line.startswith("BIGDATA_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("BIGDATA_API_KEY not set and .env missing")


def _post_search(api_key: str, body: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Content-Type": "application/json", "X-API-KEY": api_key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err}") from e


def flatten_results(results: list[dict[str, Any]], id_suffix: str = "") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for doc in results:
        did = str(doc.get("id", ""))
        for ch in doc.get("chunks") or []:
            cnum = ch.get("cnum", 0)
            cid = f"{did}_{cnum}{id_suffix}"
            out.append(
                {
                    "id": cid,
                    "headline": doc.get("headline", ""),
                    "timestamp": doc.get("timestamp", ""),
                    "url": doc.get("url", ""),
                    "snippet": ch.get("text", ""),
                    "source": doc.get("source", {}),
                }
            )
    return out


def search_body(text: str, entity_ids: list[str], max_chunks: int = 20) -> dict[str, Any]:
    return {
        "search_mode": "fast",
        "query": {
            "text": text,
            "max_chunks": max_chunks,
            "filters": {
                "reporting_entities": entity_ids,
                "category": {"mode": "INCLUDE", "values": ["filings", "transcripts"]},
            },
        },
    }


def supplementary_body(text: str, max_chunks: int = 20) -> dict[str, Any]:
    return {
        "search_mode": "fast",
        "query": {
            "text": text,
            "max_chunks": max_chunks,
            "filters": {
                "category": {"mode": "INCLUDE", "values": ["filings", "transcripts", "news"]},
            },
        },
    }


def four_queries(display: str, eu: bool) -> tuple[str, str, str, str]:
    if eu:
        q1 = f"{display} fuel cost per available seat kilometre CASK fuel expense litre"
    else:
        q1 = f"{display} fuel cost per available seat mile CASM fuel expense gallon"
    q2 = f"{display} revenue per available seat mile RASM PRASM TRASM unit revenue yield"
    q3 = f"{display} fuel hedge hedging program crude oil jet fuel derivative contract"
    q4 = f"{display} Iran oil price Middle East crude supply disruption energy cost"
    return q1, q2, q3, q4


def _entity_id_for_lookup(lookup: str) -> str:
    sys.path.insert(0, str(REPO_ROOT))
    from output.cache_helper import get_entity

    row = get_entity(lookup)
    if not row or not row.get("entity_id"):
        raise RuntimeError(
            f"No cached entity for lookup {lookup!r}. Run find_companies + save_entity first."
        )
    return str(row["entity_id"])


def main() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    from output.cache_helper import finish_run, save_search_chunks, start_run

    airlines_cfg = json.loads(TICKERS_PATH.read_text())["airlines"]
    iag_lookup = "International Airlines Group"

    api_key = _load_api_key()
    run_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not run_id:
        from datetime import datetime, timezone

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    start_run(run_id)
    total_inserted = 0
    total_flat = 0

    def run_one(query: str, airline: str | None, entity_ids: list[str], supp: bool = False) -> None:
        nonlocal total_inserted, total_flat
        body = supplementary_body(query) if supp else search_body(query, entity_ids)
        raw = _post_search(api_key, body)
        results = raw.get("results", raw if isinstance(raw, list) else [])
        if not isinstance(results, list):
            results = []
        chunks = flatten_results(results)
        n = save_search_chunks(run_id, query, airline, chunks)
        total_inserted += n
        total_flat += len(chunks)
        label = airline or "SUPP"
        print(f"  [{label}] +{n} new / {len(chunks)} flat — {query[:70]}...")
        time.sleep(0.35)

    print("Run", run_id)

    # Carriers with their own lookup (excludes IAG rows — those share parent filings)
    for row in airlines_cfg:
        if row["lookup"] == iag_lookup:
            continue
        display = row["name"]
        country = row.get("country", "")
        eu = country in EU_COUNTRIES
        eid = _entity_id_for_lookup(row["lookup"])
        for q in four_queries(display, eu):
            run_one(q, display, [eid])

    iag_eid = _entity_id_for_lookup(iag_lookup)
    for q in four_queries("British Airways", True):
        run_one(q, "British Airways", [iag_eid])
    for q in four_queries("International Airlines Group", False):
        run_one(q, "British Airways", [iag_eid])
    for q in four_queries("Iberia", True):
        run_one(q, "Iberia", [iag_eid])

    supp_queries = [
        "airline hedging strategies fall short jet fuel price surges Iran oil",
        "Asian airlines fuel cost Iran Middle East oil crisis impact",
        "Gulf carriers route disruption Iran conflict airspace closure",
        "airline fuel hedge percentage 2026 crude oil forward contract",
        "IATA airline fuel cost forecast 2026 Iran geopolitical risk",
        "jet fuel crack spread refinery Iran conflict all-time high",
        "China airline fuel hedging ban CAAC regulatory 2026",
    ]
    for q in supp_queries:
        run_one(q, None, [], supp=True)

    airlines_count = len(airlines_cfg)
    finish_run(run_id, airlines_count=airlines_count, chunks_count=total_flat)
    print(json.dumps({"run_id": run_id, "new_rows": total_inserted, "chunks_flat": total_flat}, indent=2))


if __name__ == "__main__":
    main()
