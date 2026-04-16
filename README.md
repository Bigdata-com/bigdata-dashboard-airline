# Global Airlines — Iran Conflict Exposure Dashboard

Interactive dashboard tracking NA & EU airline carriers' energy cost
resilience during the Iran conflict, powered by [Bigdata.com](https://bigdata.com).

**Dashboard:** https://Bigdata-com.github.io/bigdata-dashboard-airline/

## How It Works

1. An AI agent (Cursor or Claude Cowork) reads `skills/*.md` for visual, data, and grounding specs
2. Calls **[Bigdata.com](https://bigdata.com) MCP** tools to search SEC filings, earnings transcripts, and news
3. Extracts fuel cost/ASM, revenue/ASM, hedging positions, Iran impact data per airline
4. Builds `GROUNDED_DATA` with source attribution (CONFIRM / CAUTION / UNVERIFIED)
5. Generates a single self-contained `dist/index.html` (React + Recharts, all data baked in)
6. Push to this repo triggers GitHub Actions deploy to GitHub Pages

See [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for full architecture documentation.

## Running in Cursor with Bigdata.com MCP

This is the recommended way to run the dashboard update pipeline. Cursor's agent
mode can call the [Bigdata.com](https://bigdata.com) MCP tools directly — no Claude Cowork needed.

### Prerequisites

1. **Cursor IDE** with agent mode enabled
2. **[Bigdata.com](https://bigdata.com) MCP connector** added to Cursor (provides `find_companies`,
   `bigdata_search`, `bigdata_company_tearsheet`)

### Setting up the Bigdata.com MCP connector

1. Open **Cursor Settings** (gear icon or `Cmd+,`)
2. Navigate to **MCP** in the sidebar
3. Click **+ Add new MCP server**
4. Enter the server URL: `https://mcp.bigdata.com/` (site root; the old `/sse` path returns 404)
5. Cursor will prompt you to authenticate — sign in with your
   [Bigdata.com](https://bigdata.com) account or API key
6. Once connected, verify the tools are available by asking the agent:
   *"Can you call find_companies for Delta Air Lines?"*

### Cursor agent — fresh run (copy-paste this)

Paste the block below into **Cursor agent** with this repo open at the **repo root**.
It matches [`update-dashboard.md`](update-dashboard.md) (authoritative runbook).

````
You are refreshing the Global Airlines Iran-Exposure dashboard. Work from the repo root.

PRE-READ (in parallel): skills/frontend-design.md, skills/data-pipeline.md, skills/bigdata-mcp-grounding.md, config/tickers.json, update-dashboard.md (Steps 1–6 + “Static vs MCP-grounded”).

CACHE (mandatory — all entity + search results go to output/bigdata_cache.db):
1) Run: python3 output/cache_helper.py stats
   - If last_run is null → cold start (full entity + full search history per runbook Step 2B).
   - If last_run exists AND total_chunks > 0 → incremental (Step 2A: published_after since last_run where applicable).
   - If last_run exists BUT total_chunks == 0 → search cold start (Step 2C: full searches, no published_after-only).

ENTITIES:
2) python3 output/cache_helper.py entities  and  uncached for any missing lookups from config/tickers.json.
3) For each miss: MCP find_companies using the **lookup** field (not ticker), then save_entity per skills/bigdata-mcp-grounding.md.

SEARCHES:
4) Per airline: MCP bigdata_search (4 query templates per runbook); after EACH response call save_search_chunks(run_id, query, airline, chunks) with the 4-argument Python API from cache_helper.
   For British Airways and Iberia: also search under IAG / parent (subsidiary + parent).
5) Run supplementary broad queries; save with airline=None where the runbook says so.
6) finish_run(run_id, ...) when done. Verify: python3 output/cache_helper.py chunks  (search_results_rows > 0).

GROUNDED HTML:
7) From SQLite search_results (+ tearsheets if you ran them), update GROUNDED_DATA then AIRLINES in config/dashboard_template.html so numbers match evidence (chunk_id, verbatim_quote, confidence). Follow data-pipeline.md — no invented figures.

HEADER MACRO TILES (optional but avoids stale Brent/jet copy):
8) After picking trusted snippets, upsert dashboard_kv (tile_keys: brent_crude, jet_fuel_nw_eu, jet_crack_spread, hormuz_status) via cache_helper save_dashboard_tile or dashboard-tiles-import — see update-dashboard.md.

BUILD:
9) python3 scripts/build_dashboard.py  → writes dist/index.html (GEN_TS + STATIC_MARKET_TILES merge from dashboard_kv + defaults).

VALIDATE:
10) Run Step 7 checks in update-dashboard.md (wc, grep checklist).

BIGDATA MCP: find_companies (lookup field), bigdata_search, bigdata_company_tearsheet. Do not skip the SQLite cache.
````

**Optional batch search (REST, not MCP):** if `BIGDATA_API_KEY` is in `.env`, you can run
`python3 output/pull_searches.py <RUN_ID>` after `start_run` — still must `finish_run` and
keep the same `save_search_chunks` discipline. Prefer MCP in Cursor when the connector is available.

### Tips

- **Cold vs incremental:** Decided solely from `python3 output/cache_helper.py stats` (see runbook decision tree).
- **Token budget:** Tearsheets are large; run `bigdata_company_tearsheet` only when the runbook says (e.g. last_run older than 7 days).
- **Add/remove airlines:** Edit `config/tickers.json`, resolve new `lookup` values, then search + rebuild HTML.
- **Subsidiaries:** For BA and Iberia under IAG, search **both** subsidiary and parent group for filing-grade data.
- **Regenerate HTML only:** `python3 scripts/build_dashboard.py` (updates `GEN_TS`, merges `dashboard_kv` into header tiles; does not fetch Bigdata by itself).

## Claude Cowork Instruction (alternative)

Full automation steps live in [`update-dashboard.md`](update-dashboard.md) and [`skills/`](skills/). Use this brief as the Cowork task preamble:

```
ROLE: Financial data pipeline generating a React dashboard showing
airline exposure to the Iran conflict.

WORKING FOLDER: The bigdata-dashboard-airline repo root.
CONFIG: config/tickers.json — contains airlines, scenarios, regions, flags.
OUTPUT: dist/index.html (single self-contained file)

BIGDATA.COM MCP TOOLS AVAILABLE:
- find_companies — resolve airline name to entity_id (use the "lookup" field)
- bigdata_search — semantic search across filings, transcripts, news
- bigdata_company_tearsheet — get financial data for public companies

IMPORTANT:
- Use the "lookup" field (not ticker) for find_companies
- For subsidiaries (British Airways, Iberia under IAG):
  search BOTH the subsidiary name AND the parent group for filing data
```

The shipped artifact is a **single self-contained** [`dist/index.html`](dist/index.html)
(React + Recharts + data inlined per `skills/frontend-design.md`). Commit and push
from an environment with Git credentials when you want GitHub Pages to update.

## Repository Structure

```
├── config/
│   ├── tickers.json                 ← Airlines, scenarios, regions, flags
│   ├── dashboard_template.html      ← Source HTML for build_dashboard.py
│   └── example_dashboard_tiles.json ← Example dashboard_kv import
├── output/
│   ├── bigdata_cache.db             ← Local SQLite (gitignored); entities + search_results + dashboard_kv
│   ├── cache_helper.py              ← Cache API + CLI (tracked)
│   └── pull_searches.py             ← Optional REST batch search (tracked; needs BIGDATA_API_KEY)
├── scripts/
│   └── build_dashboard.py           ← Writes dist/index.html from template + DB
├── skills/
│   ├── frontend-design.md           ← Visual spec (colors, fonts, components)
│   ├── data-pipeline.md             ← Data schema, formulas, validation
│   └── bigdata-mcp-grounding.md     ← MCP queries, caching rules
├── dist/
│   └── index.html                   ← Deployed single-file dashboard
├── update-dashboard.md              ← Full Cowork / agent runbook
└── HOW_IT_WORKS.md                  ← Architecture documentation
```

## Coverage

14 public airlines across North America and Europe, ranked by energy cost resilience
under four Iran conflict fuel price scenarios.

## Configuration

Edit `config/tickers.json` to add, remove, or modify airlines, scenarios, or region mappings.

## Data Sources

- SEC 10-K / 6-K / 20-F filings
- Earnings call transcripts (Quartr, Captide)
- Financial news (Reuters, Bloomberg, FT, CNBC, etc.)
- All sourced via [Bigdata.com](https://bigdata.com) MCP tools ([docs](https://docs.bigdata.com/mcp-reference/))
