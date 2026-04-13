# How It Works — Airline Iran-Exposure Dashboard

> This document is **static reference**. It does not need to be regenerated.
> Last updated: 2026-04-13

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              AI Agent (Cursor or Claude Cowork)           │
│                                                          │
│  1. Read config/tickers.json (airline list)               │
│  2. Resolve entities via Bigdata.com find_companies       │
│  3. Search filings/transcripts via bigdata_search         │
│  4. Pull tearsheets via bigdata_company_tearsheet         │
│  5. Build GROUNDED_DATA, then AIRLINES per skills/*.md   │
│  6. Generate dist/index.html (single self-contained file)│
│  7. Git commit & push → GitHub Actions → GitHub Pages    │
│                                                          │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┼──────────────┐
        ▼             ▼              ▼
  config/        skills/              dist/
  tickers.json   *.md specs          index.html ──→ GitHub Pages
```

---

## Data Flow

### Input: `config/tickers.json`
- North American and European public airlines with name, ticker, country, lookup string
- 4 scenario definitions (Current, Moderate, Severe, Extreme)
- Country → region mapping (NA, EU)
- Country → flag emoji mapping

### Caching (optional)

When running in **Claude Cowork**, an SQLite cache (`output/bigdata_cache.db`)
can accumulate search results across runs for incremental updates. When running
in **Cursor**, data is collected fresh each session — no local cache required.

### Processing: `skills/*.md`

| Skill File | What It Defines |
|------------|-----------------|
| `frontend-design.md` | Visual spec: colors, fonts, CDN order, component contracts, layout |
| `data-pipeline.md` | Data schema, formulas, scenarios, region codes, validation checklist |
| `bigdata-mcp-grounding.md` | MCP query templates, caching protocol, **grounding rules (no fabrication)**, hedging seed table (non-authoritative), audit schema |

These files are **read by the agent** at the start of each cycle. They are NOT
regenerated — they define the contract that the generated `index.html` must follow.

### Output: `dist/index.html`
- Single self-contained HTML file (~70–180 KB with `GROUNDED_DATA` provenance)
- React 18 + Recharts loaded from CDN
- All JSX inlined (no external .jsx files)
- All data baked in (no runtime API calls)
- Works on `file://` and via HTTPS (GitHub Pages)

**Grounding:** `GROUNDED_DATA` in the same file lists per-airline evidence (`chunk_id`,
verbatim quotes). See `skills/data-pipeline.md`. Static hedging tables in the MCP skill
are seeds only — not a substitute for carrier-specific retrieved documents.

---

## Adjusted Spread Formula

The core metric ranking airlines by fuel-cost resilience:

```
Adjusted Spread = (TRASM − Fuel CASM) − Net Fuel Hit

where:
  Raw Spread    = TRASM − Fuel CASM
  Fuel Increase = Fuel CASM × jetPctUp (scenario multiplier)
  Tenor Discount = max(0, 1 − (24 − hedgeTenor) × 0.008)
  Hedged Protection = Fuel Increase × hedgePct × Tenor Discount
  Net Fuel Hit  = Fuel Increase − Hedged Protection
```

**Interpretation:**
| Value | Meaning |
|-------|---------|
| Positive (green) | Airline covers fuel shock, remains profitable per seat-mile |
| Near zero (yellow) | Break-even — barely covering fuel costs |
| Negative (red) | Losing money on every seat-mile flown |

---

## Scenarios Explained

| Scenario | Jet Fuel Change | What It Means |
|----------|----------------|---------------|
| **Current (+100%)** | Doubled from baseline | **This is TODAY** — actual market as of the latest data refresh |
| **Moderate (+50%)** | +50% from baseline | **DEESCALATION** — prices *fall* ~25% from current levels |
| **Severe (+150%)** | +150% from baseline | **ESCALATION** — Hormuz closure, prices rise ~25% above current |
| **Extreme (+200%)** | Tripled from baseline | **WORST CASE** — full blockade + Iranian export halt |

> **Key insight**: Moderate is *better* than current (deescalation), not worse.
> The dashboard clearly labels this with a ↓ arrow.

---

## Dashboard Tabs

### 1. Resilience Ranking
Sortable table ranking all airlines by Adjusted Spread under the selected scenario.
Shows rank medals, hedge coverage bars, tenor, TRASM, Fuel CASM, and status badges.

### 2. Hedge Positions
Card grid showing each airline's fuel risk management details — coverage %,
forward tenor, strike price, instrument type, and policy description.

### 3. Risk vs Spread (Scatter)
Recharts ScatterChart plotting hedge coverage (X) vs adjusted spread (Y).
Bubble size = √ASMs. Top-right = best positioned; bottom-left = most vulnerable.

### 4. Margin Impact (Bar Chart)
Grouped bar chart showing adjusted spread across all 4 scenarios for every airline.
Carriers with consistent bars = well-insulated from fuel shocks.

### 5. Region View
Cards grouping airlines by geography with aggregated stats — average spread,
average hedge, and count of carriers at risk (negative adjusted spread).

### 6. Operating Metrics
Full table with raw unit economics for all carriers: TRASM, PRASM, CASM,
Fuel CASM, CASM-Ex, $/gallon, ASMs, load factor, hedge coverage, tenor.

### 7. Evidence & Audit
Source documents backing each data point — filings, transcripts, news articles.
Each chunk tagged as CONFIRM (verified) or CAUTION (estimated/caveated).
Filterable by airline, tag, and free-text search.

---

## Deployment

```
Push to main branch
    → .github/workflows/deploy.yml triggers
    → Uploads dist/ as GitHub Pages artifact
    → Deploys to https://Bigdata-com.github.io/bigdata-dashboard-airline/
```

No build step required — the HTML file is the build artifact.

---

## Refresh Cycle

### From Cursor (recommended)

1. Open repo in Cursor with [Bigdata.com](https://bigdata.com) MCP connector enabled
2. Agent reads `config/tickers.json` + `skills/*.md` for instructions
3. Calls MCP tools to resolve entities, search filings, pull tearsheets
4. Generates fresh `dist/index.html` with updated data
5. Commit and push → auto-deploys via GitHub Actions

Typical run: ~90 MCP calls for 14 airlines (cold start, ~10–15 minutes).

### From Claude Cowork (alternative)

1. Cowork runs on schedule, reads `update-dashboard.md`
2. Checks `output/bigdata_cache.db` → only queries what's missing/stale
3. Generates `dist/index.html` and commits

Incremental cycle with cache: ~3–5 minutes.
