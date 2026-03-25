# Global Airlines — Iran Conflict Exposure Dashboard

Live interactive dashboard tracking 50 global airline carriers' energy cost
resilience during the Iran conflict, powered by [Bigdata.com](https://bigdata.com).

**Dashboard:** https://Bigdata-com.github.io/bigdata-dashboard-airline/

## How It Works

1. **Claude Cowork** runs `update-dashboard.md` on a scheduled cycle
2. Reads `skills/*.md` for visual, data, and grounding specifications
3. Checks `output/` cache — skips redundant API calls
4. Calls **Bigdata.com MCP** to search SEC filings, earnings transcripts, and news for all 50 airlines
5. Extracts fuel cost/ASM, revenue/ASM, hedging positions, Iran impact data
6. Generates a single self-contained `dist/index.html` (React + Recharts, all data baked in)
7. Pushes to this repo → GitHub Actions deploys to GitHub Pages

See [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for full architecture documentation.

## Claude Cowork Instruction

Full automation steps live in [`update-dashboard.md`](update-dashboard.md) and [`skills/`](skills/). Use this brief as the Cowork task preamble (or paste into the schedule instructions):

```
ROLE: Financial data pipeline generating a React dashboard showing
50 global airlines' exposure to the Iran conflict.

WORKING FOLDER: The bigdata-dashboard-airline repo root.
CONFIG: config/tickers.json — contains all 50 airlines, scenarios, regions, flags.
OUTPUT: dist/App.jsx and dist/index.html

BIGDATA.COM MCP TOOLS AVAILABLE:
- find_companies — resolve airline name to entity_id (use the "lookup" field from config)
- bigdata_search — semantic search across filings, transcripts, news
- bigdata_company_tearsheet — get financial data for public companies

IMPORTANT FOR THIS AIRLINE LIST:
- 50 airlines total: ~35 public, ~15 private
- Use the "lookup" field (not ticker) for find_companies — works better for non-US stocks
- For subsidiaries (Swiss, Austrian, British Airways, Iberia, Vueling, Scoot):
  search BOTH the subsidiary name AND the parent group for filing data
- Private carriers (Qatar, Emirates, Etihad, Saudia, etc.): search by name in
  bigdata_search — data comes from news, press releases, industry reports
- After generating, run: git add dist/ && git commit && git push origin main
```

In this repository the shipped artifact is a **single self-contained** [`dist/index.html`](dist/index.html) (React + Recharts + data inlined per `skills/frontend-design.md`); there is no separate `App.jsx` in the deploy path. Commit and push from an environment with Git credentials when you want GitHub Pages to update (Cowork may not have push access).

## Repository Structure

```
├── config/tickers.json       ← Airline list, scenarios, region mapping
├── skills/
│   ├── frontend-design.md    ← Visual spec (colors, fonts, components)
│   ├── data-pipeline.md      ← Data schema, formulas, validation
│   └── bigdata-mcp-grounding.md ← MCP queries, caching, verified facts
├── output/                       ← Local-only cache (git-ignored)
│   ├── cache_helper.py       ← SQLite helper (entities + search results)
│   └── bigdata_cache.db      ← All cached data (auto-created per run)
├── dist/
│   └── index.html            ← The dashboard (single file, deployed)
├── update-dashboard.md       ← Claude Cowork runbook
└── HOW_IT_WORKS.md           ← Architecture documentation
```

## Coverage

50 airlines across 6 regions: North America, Europe, MENA, Asia-Pacific, Oceania, Latin America.
Includes both public and private carriers.

## Configuration

Edit `config/tickers.json` to change airlines, scenarios, or parameters.

## Data Sources

- SEC 10-K / 6-K / 20-F filings
- Earnings call transcripts
- Financial news (Reuters, Bloomberg, FT, CNBC, etc.)
- All sourced via [Bigdata.com MCP](https://docs.bigdata.com/mcp-reference/) tools
