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
