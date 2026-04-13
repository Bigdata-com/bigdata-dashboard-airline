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
4. Enter the server URL: `https://mcp.bigdata.com/sse`
5. Cursor will prompt you to authenticate — sign in with your
   [Bigdata.com](https://bigdata.com) account or API key
6. Once connected, verify the tools are available by asking the agent:
   *"Can you call find_companies for Delta Air Lines?"*

### Running the update

Open this repository in Cursor and give the agent this prompt:

```
Read the plan in .cursor/plans/run_dashboard_update_ba6a0bca.plan.md
(or use the attached plan file). Execute it against the airlines in
config/tickers.json.

The three Bigdata.com MCP tools you need are:
- find_companies — resolve airline name → entity ID
- bigdata_search — semantic search across filings, transcripts, news
- bigdata_company_tearsheet — structured financial data for public carriers

Follow the specs in skills/ for output format and data schema.
Generate dist/index.html as the final artifact.
```

The agent will:

1. **Resolve entities** — call `find_companies` for each airline's `lookup` field
2. **Collect data** — run `bigdata_search` queries for hedging, fuel costs, revenue,
   and Iran exposure; pull `bigdata_company_tearsheet` for each public carrier
3. **Build GROUNDED_DATA** — extract metrics with source attribution per
   `skills/data-pipeline.md`
4. **Generate `dist/index.html`** — single self-contained React dashboard per
   `skills/frontend-design.md`
5. **Validate** — check file size, CDN order, region codes, data completeness

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
