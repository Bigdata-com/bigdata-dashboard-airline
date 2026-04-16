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

### Running the update

Open this repository in Cursor and paste a prompt like the one below (adjust if your
`.env` or airline list differs). 

```
Run the airline dashboard pipeline from the repo root.

1. Use airlines/scenarios from config/tickers.json (edit that file if the list should change).
2. Ensure .env has BIGDATA_API_KEY and any LLM/Vertex variables you use for labeling.
3. Run: uv sync && uv run python -m app.main

Expect app/data/*.json caches and dist/index.html. If a step fails mid-run, fix the
cause and continue with: uv run python -m app.main --step <step> (use --help for step names).

Optional context: skills/data-pipeline.md and skills/frontend-design.md describe
grounding rules and UI expectations. The MCP tools used under the hood are find_companies,
bigdata_search, and bigdata_company_tearsheet.
```

What the pipeline does (same order as `app/main.py`):

1. **Resolve entities** — `find_companies` for each airline `lookup` in `config/tickers.json`
2. **Collect data** — `bigdata_search` plus `bigdata_company_tearsheet` per carrier
3. **Label & extract** — LLM labels chunks, then grounded metrics are built
4. **Calculate & export** — scenario math and `app/data/dashboard_data.json`
5. **Dashboard** — renders `dist/index.html` (self-contained bundle)

### Tips

- **Cold start vs incremental:** The first run fetches everything fresh. Subsequent
  runs can reuse the existing `dist/index.html` data and only refresh stale fields.
- **Token budget:** Each tearsheet is large. For 14 airlines, expect ~90 MCP calls.
  Batch entity resolution and search queries in parallel to save time.
- **Add/remove airlines:** Edit `config/tickers.json` and re-run. All airline names
  use the `lookup` field for entity resolution (works better than tickers for non-US stocks).
- **Subsidiaries:** For airlines under a parent group (e.g., British Airways and
  Iberia under IAG), search both the subsidiary name and parent group for filing data.

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
- After generating, run: git add dist/ && git commit && git push origin main
```

The shipped artifact is a **single self-contained** [`dist/index.html`](dist/index.html)
(React + Recharts + data inlined per `skills/frontend-design.md`). Commit and push
from an environment with Git credentials when you want GitHub Pages to update.

## Repository Structure

```
├── config/tickers.json          ← Airline list, scenarios, region mapping
├── skills/
│   ├── frontend-design.md       ← Visual spec (colors, fonts, components)
│   ├── data-pipeline.md         ← Data schema, formulas, validation
│   └── bigdata-mcp-grounding.md ← MCP queries, caching, verified facts
├── dist/
│   └── index.html               ← The dashboard (single file, deployed)
├── update-dashboard.md          ← Claude Cowork runbook
└── HOW_IT_WORKS.md              ← Architecture documentation
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
