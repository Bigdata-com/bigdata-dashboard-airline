# Update Dashboard — Claude Cowork Runbook

You are a automation agent executing a scheduled update cycle for the
**Global Airlines Iran-Exposure Dashboard**. There is no traditional backend — you ARE the backend.

**This document is your complete instruction set.** Read the referenced skill files before acting.

---

## Pre-Flight: Read These Files

Read these files in parallel BEFORE doing anything else:

| File | Purpose |
|------|---------|
| `skills/frontend-design.md` | Visual spec: colors, fonts, CDN order, component contracts, column definitions |
| `skills/data-pipeline.md` | Data schema, **GROUNDED_DATA** contract, formulas, validation checklist |
| `skills/bigdata-mcp-grounding.md` | MCP query templates, caching protocol, verified hedging facts |
| `config/tickers.json` | Airline list, region mapping, scenario definitions |

Then run: `date -u '+%Y-%m-%d %H:%M UTC'` to get the current timestamp.

---

## Step 1 — Check Cache State

**⚠️ MANDATORY**: You MUST use the SQLite cache for ALL entity resolutions and search
results. NEVER skip the cache — it prevents redundant API calls across runs and stores
data that persists locally in `output/bigdata_cache.db`.

Run cache diagnostics:
```bash
python3 output/cache_helper.py stats
```

This returns: `{ "total_chunks": N, "unique_airlines": N, "completed_runs": N, "last_run": "ISO_TIMESTAMP" }`

Record `last_run` timestamp — you'll need it in every subsequent step.

**Decision tree:**
- If `last_run` is null (first ever run) → **COLD START** mode (Step 2B)
- If `last_run` exists **and** `total_chunks` > 0 → **INCREMENTAL** mode (Step 2A)
- If `last_run` exists **but** `total_chunks` is 0 → **SEARCH COLD START** (Step 2C): entities may
  already be cached from a prior incomplete run; you MUST still run full-history searches
  (no `published_after`) and save every chunk. Do **not** use incremental-only filters or you
  will persist zero rows again.

Also check entity cache (stored in same DB):
```bash
python3 output/cache_helper.py entities
```

---

## Step 2A — Incremental Mode (prior run exists)

### Entity Resolution
Check DB for cached entities. Only call `find_companies` for airlines NOT in cache:
```bash
python3 output/cache_helper.py uncached "Delta Air Lines" "Ryanair Holdings" ...
```
Save any new resolutions to the DB (see `skills/bigdata-mcp-grounding.md` for exact commands).

### Search — Per-Airline
Check which airlines already have cached chunks:
```bash
python3 output/cache_helper.py airlines-with-chunks
```

**Airlines WITH cached chunks:** run the same 4 queries per airline BUT pass
`published_after: "<last_run ISO date>"` to `bigdata_search`. This fetches only
documents published SINCE the last run. The cache deduplicates by `chunk_id`,
so re-fetched overlaps are harmlessly skipped.

**Airlines with 0 cached chunks (new additions):** run 4 queries WITHOUT
`published_after` (full history pull for that airline only).

### Search — Supplementary
Run the 7 broad market queries with `published_after: "<last_run ISO date>"`.
This only pulls new industry-wide data since the last run.

### Tearsheets
Call `bigdata_company_tearsheet` only if `last_run` > 7 days ago.
Otherwise skip — tearsheet financials rarely change within a week.

After **every** `bigdata_search` response, call `save_search_chunks` with the **correct
signature** (see Step 4A example). Verify before leaving search steps:
```bash
python3 output/cache_helper.py chunks
```

Jump to **Step 5**.

---

## Step 2C — Search cold start (`last_run` set but `total_chunks` == 0)

Skip entity cold start (entities may already be populated). Do **not** jump to incremental
search with `published_after` only.

1. Start a new run and print `run_id` (same as Step 2B `start_run` snippet).
2. Run **Step 4A** (per-airline, 4 queries each, **no** `published_after`) and **Step 4B**
   (7 supplementary, **no** `published_after`).
3. After **each** MCP `bigdata_search`, call `save_search_chunks(RUN_ID, query, airline, chunks)`
   (see Step 4A — correct 4-argument call).
4. **Step 4D** `finish_run` with accurate `chunks_count`.
5. `python3 output/cache_helper.py chunks` → `search_results_rows` must be > 0.

Then continue at **Step 5**.

---

## Step 2B — Cold Start (first run ever, no prior data)

**⚠️ MANDATORY**: Even on cold start, you MUST save every entity resolution and
every search chunk to the SQLite cache. This ensures subsequent runs can use
INCREMENTAL mode and skip redundant API calls.

### Generate run ID
```bash
python3 -c "
from output.cache_helper import start_run
from datetime import datetime, timezone
run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
start_run(run_id)
print(run_id)
"
```

---

## Step 3 — Resolve Entities (Cold Start only)

For each airline in `config/tickers.json → airlines`:
1. Check DB via `get_entity(lookup)` — if HIT, skip API call
2. Find all uncached lookups in bulk: `python3 output/cache_helper.py uncached "name1" "name2" ...`
3. Call `find_companies(lookup)` in batches of 5-8 for uncached only
4. **MUST** save every new resolution immediately:
```bash
python3 -c "
from output.cache_helper import save_entity
save_entity('Airline Name', 'ENTITY_ID', 'company_type', 'Resolved Name')
"
```

**Verify** entities were saved:
```bash
python3 output/cache_helper.py entities
```

See `skills/bigdata-mcp-grounding.md` for exact commands.

---

## Step 4 — Search & Tearsheets (Cold Start only)

### 4A. Per-Airline Searches
For each airline, run 4 queries (see `skills/bigdata-mcp-grounding.md` for templates).
No `published_after` filter — pull full history on first run.
Batch by region: NA → EU → MENA → Asia → Oceania → LATAM.
Use `max_chunks: 20` per query.

**MUST** save ALL chunks to SQLite after **each** `bigdata_search` call. The Python API is
**four arguments** — `(run_id, query, airline_name_or_None, list_of_chunk_dicts)`:

```bash
python3 -c "
import json
from output.cache_helper import save_search_chunks

RUN_ID = 'PASTE_RUN_ID_FROM_start_run'
QUERY = 'the exact query string passed to bigdata_search'
AIRLINE = 'Delta Air Lines'  # or None for supplementary / industry-wide queries
# Paste the chunks array from the MCP tool JSON response (list of objects):
RAW = '''
[{"id":"...","headline":"...","timestamp":"...","url":"...","snippet":"...","source":{"name":"..."}}]
'''
chunks = json.loads(RAW)
n = save_search_chunks(RUN_ID, QUERY, AIRLINE, chunks)
print(f'inserted {n} new rows')
"
```

Inside Cursor/Cowork you can pass `chunks` from the tool result without JSON round-trip;
the critical rule is: **never** call `save_search_chunks` with a single list — that is invalid.

If the MCP payload uses `chunk_id` or `document_id` instead of `id`, `cache_helper` still
deduplicates (see `output/cache_helper.py` → `_chunk_identifier`).

### 4B. Supplementary Deep Searches
Run 7 broad market queries (see `skills/bigdata-mcp-grounding.md`).
No `published_after` filter on first run.
After each search: `save_search_chunks(RUN_ID, query, None, chunks)` — **airline must be `None`**.

### 4C. Tearsheets
Call `bigdata_company_tearsheet(interval:"quarter")` for all public carriers in
`config/tickers.json`. Use each airline's `lookup` field for entity resolution.

### 4D. Finish Run

**MUST** call finish_run to mark this run as complete in the DB:
```bash
python3 -c "
from output.cache_helper import finish_run
finish_run('RUN_ID', airlines_count=len(airlines), chunks_count=TOTAL_CHUNKS)
"
```

**Verify** cache was populated (MUST show non-zero counts):
```bash
python3 output/cache_helper.py stats
```

---

## Step 5 — GROUNDED_DATA first, then AIRLINES (no hallucination)

From the FULL cache (`output/bigdata_cache.db` → `search_results`, plus tearsheets),
build **`GROUNDED_DATA`** **before** you write any numbers into `AIRLINES`. Follow
`skills/data-pipeline.md` → **GROUNDED_DATA (mandatory)** for the exact schema and
confidence rules.

**Hard rules:**
1. **Never** invent hedge %, tenor, TRASM, CASM, or ASM — each published value needs a
   `CONFIRM` or `CAUTION` evidence block with `chunk_id` (or tearsheet field reference in
   `notes`) and a **verbatim** `verbatim_quote` from the retrieved text.
2. The static tables in `skills/bigdata-mcp-grounding.md` are **SEED ONLY** — not a source
   of truth for `AIRLINES`. Every number must be justified from **saved MCP chunks** for
   that airline (subsidiary + parent searches where applicable).
3. If a carrier-specific primary document is missing for hedge metrics, mark
   `UNVERIFIED` and **do not** fabricate — either carry forward the previous run’s grounded
   values (document in `notes`) or **do not** deploy updated figures for that airline; report
   the gap in Step 8.
4. After `GROUNDED_DATA` is complete, copy values into `AIRLINES` so each field matches
   its evidence object’s `value`.
5. Use "NA" for region code (never "US"). FX rates: `skills/data-pipeline.md`.

**AUDIT_CHUNKS** (if used in the build): 15–25 entries, each tied to real chunks with
verbatim quotes — same grounding standard as `GROUNDED_DATA`.

---

## Step 6 — Generate dist/index.html

Write ONE file: `dist/index.html` — fully self-contained, no external .jsx files.

### CRITICAL RULES (from skills/frontend-design.md):

1. **Script order in `<head>`**: Google Fonts → react → react-dom → **prop-types** → babel → recharts
2. **ALL JSX inlined** in one `<script type="text/babel">` block — NO `<script src="./App.jsx">`
3. **`function App() { ... }`** — NO `export default`
4. Bootstrap: `ReactDOM.createRoot(...).render(React.createElement(App))`

### MUST include (from skills/frontend-design.md):

- **Column definitions inside MethodBox** — every table tab (Resilience Ranking, Operating Metrics) must have a column legend table inside the `<MethodBox>`. Mark derived columns with *Derived.* prefix and show formula. Do NOT use `?` tooltip icons on table headers (CSS tooltips break inside sticky + overflow containers)
- **MethodBox** component for methodology panels on every tab
- **Sortable tables with asc/desc toggle** — Resilience Ranking and Operating Metrics tabs MUST support clicking column headers to sort. First click = descending, second click = ascending. Show `▲`/`▼` arrow. Use `SortTh` helper pattern (see skill file). Plain text headers, no `?` icons.
- **Resilience Ranking default sort:** `hedgePct` descending (`useState("hedgePct")` + `useState(false)` for sort direction). Mention default in MethodBox.
- **Operating Metrics: ALL columns sortable** including Airline (alphabetical), Rgn (alphabetical), Ticker (alphabetical).
- **Region View: column headers** — each region card must have AIRLINE / HEDGE / SPREAD column labels above the airline rows
- **Scenario direction labels**: Moderate = `↓ Deescalation`, Severe = `↑ Escalation`, etc.
- **6 market snapshot tiles** with sub-descriptions
- **Tabs**: per `skills/frontend-design.md` (Evidence & Audit may be omitted if product policy hides it)
- **Column definitions** in MethodBox for every table tab (with all metric descriptions and formulas for derived values)
- **Status badges**: PRIVATE, SUB, UNHEDGED, PARTIAL, HEDGED, CAUTION
- **Timestamp**: `Using Bigdata.com data as of: {GEN_TS}` (NOT "Generated" or "Live")
- **Region codes**: NA (not US), with `REGION_LABELS` map

### Data arrays to generate:

```js
const GROUNDED_DATA = [ /* one object per airline — full provenance per data-pipeline.md */ ];
const AIRLINES = [ /* one entry per airline in tickers.json; every numeric must match GROUNDED_DATA */ ];
const SCENARIOS = [ /* 4 scenarios with dir/dirClass fields */ ];
const AUDIT_CHUNKS = [ /* optional: 15-25 evidence entries, verbatim quotes */ ];
const REGION_LABELS = { NA:"North America", EU:"Europe", MENA:"MENA", Asia:"Asia-Pacific", Oceania:"Oceania", LATAM:"Lat Am & Africa" };
```

Add a short global disclaimer in the header or MethodBox: figures are derived from MCP-retrieved
sources recorded in `GROUNDED_DATA` (auditable in page source).

### Methodology panels (one per tab):

Each tab opens with a `<MethodBox>` explaining:
- What the tab shows and how to read it
- How values are calculated / scored
- Key caveats (crude-only hedges, estimates, CAAC ban)
- Scenario direction reminder when relevant

### Size target: 70-140 KB

---

## Step 7 — Validate

Run through the checklist in `skills/data-pipeline.md → Output Validation Checklist`.

Quick checks:
```bash
wc -c dist/index.html    # should be 70K-140K
grep -c "function App()" dist/index.html   # should be 1
grep -c "prop-types" dist/index.html       # should be ≥1
grep -c "export default" dist/index.html   # should be 0
grep -c "src=\"./App.jsx\"" dist/index.html # should be 0
grep -c "GROUNDED_DATA" dist/index.html    # should be ≥1
grep -c "MethodBox" dist/index.html        # should match tab count per frontend-design.md
grep -c '"NA"' dist/index.html             # should be ≥1 (region code)
grep -c '"US"' dist/index.html             # should be 0 for region code
```

---

## Step 8 — Report

Report:
- Total airlines processed (should match config/tickers.json count)
- Cache mode used (INCREMENTAL, COLD START, or SEARCH COLD START per Step 2C)
- Entities: cached vs freshly resolved
- Search: total cached chunks, new chunks fetched this run, `published_after` filter used
- Audit chunks collected (target: 15-25)
- `dist/index.html` file size
- All required tabs confirmed present (per `skills/frontend-design.md`)
- `GROUNDED_DATA` present; hedge fields CONFIRM/CAUTION or explicit stale carry-forward
- Validation check results
- Paths to updated artifacts (`dist/index.html`, `config/tickers.json` if changed)

Note: `output/` is git-ignored — SQLite cache stays local-only. Automated `git push` is not part of this runbook; commit and push from an environment with Git credentials when you want GitHub Pages to update.

Dashboard URL (after deploy): https://Bigdata-com.github.io/bigdata-dashboard-airline/
