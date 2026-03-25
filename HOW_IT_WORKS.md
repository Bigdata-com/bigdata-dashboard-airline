# How It Works — Airline Iran-Exposure Dashboard

> This document is **static reference**. It does not need to be regenerated.
> Last updated: 2026-03-24

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Claude Cowork (Agent)                    │
│                                                          │
│  1. Read config/tickers.json (50 airlines)               │
│  2. Check output/bigdata_cache.db → entities table       │
│  3. Check output/bigdata_cache.db → search_results       │
│  4. Call Bigdata.com MCP for fresh/missing data           │
│  5. Build GROUNDED_DATA, then AIRLINES per skills/*.md   │
│  6. Generate dist/index.html (single self-contained file)│
│  7. Git commit & push → GitHub Actions → GitHub Pages    │
│                                                          │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┼──────────────┐
        ▼             ▼              ▼
  config/        output/              dist/
  tickers.json   bigdata_cache.db    index.html ──→ GitHub Pages
                 cache_helper.py
```

---

## Data Flow

### Input: `config/tickers.json`
- 50 airlines with name, ticker, country, lookup string, parent group
- 4 scenario definitions (Current, Moderate, Severe, Extreme)
- Country → region mapping (NA, EU, MENA, Asia, Oceania, LATAM)
- Country → flag emoji mapping

### Caching Layer: `output/`

Everything is stored in a single SQLite database. The `output/` folder is
**git-ignored** — it's a local-only cache that the agent rebuilds as needed.

| Resource | SQLite Table | Persistence |
|----------|-------------|-------------|
| Entity resolution (`find_companies` results) | `entities` | Weeks (entity IDs stable) |
| Search result chunks | `search_results` | Grows across runs, deduped by chunk_id |
| Run history | `run_log` | Tracks start/finish/status per cycle |
| `cache_helper.py` | — | Python helper, lives alongside DB |

The cache **accumulates** — data from every prior run is preserved and reused.
The agent only fetches what's new:
- **Entity resolution**: If airline exists in `entities` table, skip `find_companies`
- **Search results**: For airlines with cached chunks, pass `published_after`
  (last run timestamp) to only fetch documents published since then.
  Airlines with 0 cached chunks get a full history pull.
- **Supplementary searches**: Always filtered by `published_after` to avoid refetching
- **Tearsheets**: Only re-pulled if last run > 7 days ago

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
Flags crude-only hedgers (e.g. Cathay Pacific) with a warning badge.

### 3. Risk vs Spread (Scatter)
Recharts ScatterChart plotting hedge coverage (X) vs adjusted spread (Y).
Bubble size = √ASMs. Top-right = best positioned; bottom-left = most vulnerable.

### 4. Margin Impact (Bar Chart)
Grouped bar chart showing adjusted spread across all 4 scenarios for the top 15
airlines by ASMs. Carriers with consistent bars = well-insulated from fuel shocks.

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

1. Claude Cowork runs on schedule (configurable, default every few hours)
2. Reads `config/tickers.json` + `skills/*.md` for instructions
3. Checks entity & search caches → only queries what's missing/stale
4. Generates fresh `dist/index.html` with updated data
5. Commits and pushes → auto-deploys via GitHub Actions

Average incremental cycle: ~3-5 minutes (only new documents since last run).
Cold start (first ever run, no cache): ~15-20 minutes for 50 airlines × 4 queries each.
Subsequent runs get faster as the cache grows — most chunks are already stored.
