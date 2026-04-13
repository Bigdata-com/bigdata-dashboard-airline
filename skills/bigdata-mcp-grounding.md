# Bigdata MCP Grounding Rules — Airline Dashboard

This file defines how to query Bigdata.com MCP tools and ground all dashboard
data in verifiable sources. Read this at the start of every Cowork cycle.

---

## Principles (zero fabrication)

1. **No hallucinated numbers** — If you cannot tie a figure to a retrieved MCP chunk
   (or tearsheet field) with a **verbatim quote** or structured field reference, you
   must **not** publish that figure as fact. Use the `GROUNDED_DATA` workflow in
   `skills/data-pipeline.md` and gate publishing per `update-dashboard.md` Step 5.
2. **Airline-level grounding** — Hedge %, tenor, horizon, and policy wording must come
   from a document that **names that carrier** (issuer annual report, IR release,
   SEC/20-F, earnings transcript) or clearly attributes the fact to that airline.
   Generic industry articles are **CAUTION** at best; they cannot alone justify a
   precise hedge percentage for a named carrier.
3. **Subsidiaries** — For airlines under a parent group (e.g. BA and Iberia under IAG),
   search and cache chunks under **both** subsidiary and parent. Prefer the **most
   recent issuer document** over older snippets or third-party summaries.
4. **Every AUDIT_CHUNKS entry** must cite a real source with `date`, `source`, `company`
   and a **verbatim** `quote` from the chunk (not paraphrased numbers).
5. **Never fabricate** URLs, document IDs, dates, or publisher names.
6. **Static "HEDGING_FACTS" in this file are not authoritative** — They are **search
   seeds and hypotheses only**. Published `AIRLINES` values must be justified from
   **cached MCP results** (or tearsheet) and recorded in `GROUNDED_DATA`. Do not copy
   percentages from the table below into the dashboard without a matching chunk quote.

### Example (Finnair)

If the latest financial statements / risk management disclosure state a **24-month**
horizon and a **~82.5% target** hedge ratio for part of the program, the dashboard
must reflect **those** figures only after they appear in a **saved** `bigdata_search`
chunk (or tearsheet) with `chunk_id` and verbatim text — not legacy 60% / 6 mo estimates
from memory or old briefs.

---

## MCP Tools Used

| Tool | Purpose | When |
|------|---------|------|
| `find_companies` | Resolve airline name → entity_id | Step 2 (entity resolution) |
| `bigdata_search` | Search filings, transcripts, news | Steps 3 & 4 |
| `bigdata_company_tearsheet` | Structured financials for public carriers | Step 5 |

---

## Entity Resolution Caching

All entity data lives in the SQLite database (`output/bigdata_cache.db`, `entities` table).

Before calling `find_companies`, check the DB cache:
```bash
python3 -c "
from output.cache_helper import get_entity
import json
result = get_entity('LOOKUP_NAME')
print(json.dumps(result) if result else 'MISS')
"
```

To check which lookups are NOT cached (bulk):
```bash
python3 output/cache_helper.py uncached 'Delta Air Lines' 'Ryanair Holdings' 'Deutsche Lufthansa'
```

If HIT: skip the API call, use cached entity_id.
If MISS: call `find_companies`, then save:
```bash
python3 -c "
from output.cache_helper import save_entity
save_entity('LOOKUP_NAME', 'THE_ENTITY_ID', 'Public', 'The Resolved Name')
print('saved')
"
```

To list all cached entities:
```bash
python3 output/cache_helper.py entities
```

Entity IDs rarely change — cache is safe for weeks.

---

## Search Result Caching (SQLite)

Before running searches, check cache state:
```bash
python3 output/cache_helper.py stats
```

Returns: `{ "total_chunks": N, "cached_entities": N, "last_run": "ISO_TIMESTAMP", ... }`

### Incremental Pull Strategy (only when `last_run` exists **and** `total_chunks` > 0)

The cache **accumulates** across all runs. Never re-fetch old data.

**If `python3 output/cache_helper.py stats` shows `total_chunks: 0` but `last_run` is set:**
a previous run finished without persisting search rows (wrong API call or skipped saves).
Treat searches as **cold start**: run full-history `bigdata_search` with **no** `published_after`
for all airlines and all 7 supplementary queries, then save every response. See
`update-dashboard.md` → Step 2C.

When `total_chunks` > 0 and `last_run` exists:

1. Get `last_run` timestamp from stats
2. For **airlines with cached chunks**: pass `published_after: "<last_run date>"`
   to `bigdata_search` — only fetches documents published SINCE the last run
3. For **airlines with 0 cached chunks** (newly added): search WITHOUT
   `published_after` to get full history for that airline
4. For **supplementary searches**: always pass `published_after: "<last_run date>"`
5. The SQLite cache deduplicates by stable chunk id — overlapping results are harmlessly skipped

Check which airlines have cached data:
```bash
python3 output/cache_helper.py airlines-with-chunks
```

Quick row count:
```bash
python3 output/cache_helper.py chunks
```

### Cold Start (first run, no last_run)

Run all searches WITHOUT `published_after` to build the initial cache.

### Saving Results (MANDATORY — correct signature)

`save_search_chunks` takes **four** arguments in this order:

1. `run_id` — string from `start_run`
2. `query` — exact query string sent to `bigdata_search`
3. `airline` — airline display name string, or **`None`** for supplementary / industry-wide queries
4. `chunks` — **list** of chunk dicts from the MCP tool response

**Wrong (will error or do nothing useful):** `save_search_chunks([{...}])` — single list argument.

**Right:**
```python
from output.cache_helper import save_search_chunks
saved = save_search_chunks(run_id, query_used, "Delta Air Lines", mcp_response_chunks)
# Supplementary query:
saved = save_search_chunks(run_id, query_used, None, mcp_response_chunks)
```

Chunk dicts from MCP may use `id`, `chunk_id`, or `document_id` for deduplication; the helper
normalizes these. If none exist, a synthetic id is derived from `url` + `timestamp` + `headline`.

Shell one-liner pattern (see `update-dashboard.md` Step 4A for full `json.loads` example):
```bash
python3 -c "
from output.cache_helper import save_search_chunks
saved = save_search_chunks('RUN_ID', 'the query', 'Airline Name', chunks)
print(f'Saved {saved} new chunks')
"
```

### Using Cached Data for Extraction

In Step 5, always query the FULL cache (not just the current run):
```bash
python3 -c "
from output.cache_helper import get_all_chunks_for_airline
import json
chunks = get_all_chunks_for_airline('Delta Air Lines')
print(f'{len(chunks)} cached chunks')
print(json.dumps(chunks[:3], indent=2))
"
```

---

## Search Query Templates

### Per-Airline (4 queries each, max_chunks: 20)

```
1. "{airline} fuel cost per available seat mile CASM fuel expense gallon"
2. "{airline} revenue per available seat mile RASM PRASM TRASM unit revenue yield"
3. "{airline} fuel hedge hedging program crude oil jet fuel derivative contract"
4. "{airline} Iran oil price Middle East crude supply disruption energy cost"
```

For European carriers, use "per available seat kilometre" in query 1.

### Supplementary (broad market, 7 queries)

```
1. "airline hedging strategies fall short jet fuel price surges Iran oil"
2. "Asian airlines fuel cost Iran Middle East oil crisis impact"
3. "Gulf carriers route disruption Iran conflict airspace closure"
4. "airline fuel hedge percentage 2026 crude oil forward contract"
5. "IATA airline fuel cost forecast 2026 Iran geopolitical risk"
6. "jet fuel crack spread refinery Iran conflict all-time high"
7. "China airline fuel hedging ban CAAC regulatory 2026"
```

---

## Hedging facts reference (SEED ONLY — not publishable without MCP proof)

**Do not paste these numbers into `AIRLINES` without validating against fresh MCP chunks
per airline and logging evidence in `GROUNDED_DATA`.** Use this table only to craft
`bigdata_search` queries and to know what to look for in filings.

Historical reference as of internal review — **always supersede** with issuer documents
retrieved via MCP when they differ (e.g. policy updates, new tenors).

### Zero Hedge (confirmed — current airline list)
| Airline | Reason | Source |
|---------|--------|--------|
| DAL, UAL, AAL | Terminated ~2015, fully spot-exposed | SEC 10-K filings |
| LUV | Terminated Q2 2025, saving ~$150M/yr in premiums | Q2 2025 earnings |
| JBLU | No contracts as of Dec 31, 2025 | 2025 annual report |
| ALK | Suspended 2023, all settled by end 2025 | FY2025 filing |

### Hedged (confirmed — current airline list)
| Airline | Coverage | Price | Tenor | Instruments | Caveat |
|---------|----------|-------|-------|-------------|--------|
| Ryanair | 84% | $77/bbl Brent | 12 mo | Swaps, call options | FY26 coverage at Dec 31, 2025 |
| IAG group (BA, Iberia) | 62% | $745/mt | 12 mo | Swaps, collars, call options | 3-year rolling; Q1 at 75% |
| Lufthansa | 76% | $846/mt jet fuel | 24 mo | Gasoil/Brent options + jet futures | Target 85% for passenger airlines |
| Air France-KLM | 62% | $778/mt | 24 mo | Brent/gasoil/jet CIF swaps+options | New 24-month policy from Dec 2025 |
| Air Canada | 8.5% | $0.51/L jet fuel | 3 mo | Jet fuel swaps | H1 2026 only; H2 unhedged |
| Finnair | 65% | ~$677-698/mt | 24 mo | Jet CIF NWE forward contracts/options | H1 79%, H2 51%; horizon extended Dec 2025 |
| Aegean Airlines | ~30% | — | ~6 mo | Estimated | CAUTION — no primary doc retrieved |

---

## Audit Chunk Schema

For the Evidence & Audit tab:
```js
{
  date: "2026-03-15",           // ISO date of the source document
  source: "Reuters",            // publisher / filing type
  company: "Southwest Airlines", // airline name or "Industry" for broad
  riskFactor: "Hedge Termination", // category tag
  headline: "Southwest terminates all fuel hedges",
  quote: "The exact verbatim quote from the source document...",
  motivation: "Confirms LUV fully spot-exposed since Q2 2025",
  tag: "CONFIRM",               // "CONFIRM" or "CAUTION"
  tagColor: "#34d399"           // green for CONFIRM, orange for CAUTION
}
```

Target: 15–25 high-quality chunks covering key facts.

---

## Source Attribution

When populating AUDIT_CHUNKS from MCP results, map fields:
```
MCP result.headline  → chunk.headline
MCP result.source.name → chunk.source
MCP result.timestamp → chunk.date (extract date part)
MCP result snippet   → chunk.quote (verbatim extract)
```

For tearsheet data, use:
```js
{ source: "Bigdata.com Company Tearsheet", company: "DAL", ... }
```
