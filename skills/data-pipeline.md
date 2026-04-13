# Data Pipeline Specification — Airline Dashboard

This file defines the data extraction, normalization, and output schema.
Read this at the start of every Cowork cycle. Do NOT regenerate it.

---

## Pipeline Overview

```
config/tickers.json       ← airline list, regions, scenarios (READ ONLY)
        │
        ▼
  ┌─────────────┐
  │ Step 2:     │── output/bigdata_cache.db → entities table
  │ Resolve     │   (check DB before calling find_companies API)
  │ Entities    │
  └─────┬───────┘
        ▼
  ┌─────────────┐
  │ Steps 3-5:  │── output/bigdata_cache.db → search_results table
  │ Search &    │   (SQLite, incremental, dedup by chunk_id)
  │ Tearsheets  │
  └─────┬───────┘
        ▼
  ┌─────────────┐
  │ Step 6:     │── GROUNDED_DATA → then AIRLINES (see GROUNDED_DATA section)
  │ Normalize   │
  └─────┬───────┘
        ▼
  ┌─────────────┐
  │ Step 7:     │── dist/index.html (SINGLE output file)
  │ Generate    │
  │ Dashboard   │
  └─────────────┘
```

---

## Airline Data Schema

Each airline in the `AIRLINES` array must have ALL of these fields:

```js
{
  name:        String,   // Display name (e.g. "Delta Air Lines")
  ticker:      String,   // Stock ticker (e.g. "DAL", "RYAAY")
  country:     String,   // Country name
  region:      String,   // One of: "NA", "EU", "MENA", "Asia", "Oceania", "LATAM"
  flag:        String,   // Emoji flag (e.g. "🇺🇸")
  trasm:       Number,   // Total Revenue per ASM (US cents)
  fuelCasm:    Number,   // Fuel Cost per ASM (US cents)
  casmEx:      Number,   // CASM excluding fuel (US cents)
  casm:        Number,   // Total CASM (US cents)
  prasm:       Number,   // Passenger Revenue per ASM (US cents)
  fuelGal:     Number,   // Fuel cost per gallon (USD)
  asm:         Number,   // Available Seat Miles (billions)
  loadFactor:  Number,   // Load factor (%)
  hedgePct:    Number,   // Hedge percentage as decimal (0.0 to 1.0)
  hedgePrice:  String,   // Hedge price description
  hedgeTenor:  Number,   // Months of hedge coverage (integer)
  instruments: String,   // Hedging instruments used
  policy:      String,   // 1-2 sentence hedging policy
  tenorLabel:  String,   // Human-readable: "12 mo", "None", etc.
  isPrivate:   Boolean,  // true if subsidiary without independent filings
  parentGroup: String|null // Parent group name (e.g. "IAG Group") or null
}
```

---

## GROUNDED_DATA (mandatory — anti-hallucination)

Before you populate `AIRLINES`, build a **`GROUNDED_DATA`** structure: one record per
airline, each **material** field tied to evidence. Nothing in `AIRLINES` may contradict
`GROUNDED_DATA`; if evidence is missing, **do not invent** plausible numbers.

### Confidence levels

| Level | Meaning |
|-------|---------|
| `CONFIRM` | Issuer or regulatory primary document (10-K, 20-F, annual report, IR PDF, official earnings transcript) with **verbatim** quote in `verbatim_quote`. |
| `CAUTION` | Credible secondary (Reuters, Bloomberg, etc.) with verbatim quote and date — use for display only if primary not available; prefer upgrading to CONFIRM next run. |
| `UNVERIFIED` | No acceptable chunk this cycle — **do not** fill the corresponding `AIRLINES` field with a guess. Use prior run values **only** if the prior run’s `GROUNDED_DATA` for that field was CONFIRM/CAUTION and you explicitly carry forward with `"[STALE — same citation as prior run]"` in notes. Otherwise omit update or block publish (see runbook). |

### Per-field evidence object (repeat for each populated metric)

```js
{
  value: Number | String,       // Must match what you write into AIRLINES
  confidence: "CONFIRM" | "CAUTION" | "UNVERIFIED",
  chunk_id: String | null,      // From SQLite search_results or MCP chunk (required if CONFIRM/CAUTION)
  source_name: String,          // e.g. "Finnair Financial Statements Release 2025"
  document_date: String,        // ISO date of the document (from chunk or filing)
  url: String | null,
  verbatim_quote: String,       // Exact text supporting the value (not paraphrase)
  notes: String                 // Optional: e.g. "tiered program — value is headline target band"
}
```

### Required grounding (client-facing builds)

For **each** airline, before generating `dist/index.html`:

1. **`hedgePct` / `hedgeTenor` / `tenorLabel`** — Must have `CONFIRM` or `CAUTION`
   evidence from a **carrier-specific** saved chunk (or tearsheet line cited by field
   name). If only `UNVERIFIED`, do **not** ship new hedge numbers; keep last CONFIRM/CAUTION
   pair from previous `GROUNDED_DATA` or stop and report in Step 8.
2. **`trasm`, `fuelCasm`, `prasm`, `casm`, `casmEx`, `fuelGal`, `asm`, `loadFactor`**
   — Each must have at least one evidence object per cycle **or** explicit carry-forward
   from last run’s grounded citation (documented in `notes`).
3. **`policy` (text)** — Must summarize only what the citations support; no speculative
   sentences without a chunk.

### Derived fields

- **`adj` / adjusted spread** — Not separately grounded; provenance is the list of field
  keys used in `calcAdjSpread` (`trasm`, `fuelCasm`, `hedgePct`, `hedgeTenor`, scenario).

### Output embedding

Generated `dist/index.html` MUST include, in the same `<script type="text/babel">` block
as `AIRLINES`:

```js
const GROUNDED_DATA = [
  {
    name: "Finnair",
    hedgePct: { value: 0.825, confidence: "CONFIRM", chunk_id: "…", source_name: "…", document_date: "2025-12-31", url: "…", verbatim_quote: "…", notes: "" },
    hedgeTenor: { value: 24, confidence: "CONFIRM", … },
    trasm: { … },
    // … other fields as needed
  },
  // … all airlines from config/tickers.json
];
```

The **Evidence & Sources** tab (Tab 7, see `skills/frontend-design.md`) renders
`GROUNDED_DATA` interactively with expandable citations, confidence badges, and
source links. The `GROUNDED_DATA` array must also remain in the `<script>` block
so it is accessible via DevTools for programmatic audit.

---

## Region Mapping

Use `config/tickers.json → regions` to map `country → region code`.

| Code | Countries |
|------|-----------|
| NA | USA, Canada |
| EU | Ireland, UK, France, Germany, Switzerland, Spain, Finland, Austria, Greece, Sweden, Poland |
| MENA | Turkey, Qatar, UAE, Saudi Arabia, Oman, Bahrain, Ethiopia, Kazakhstan |
| Asia | Japan, South Korea, Singapore, Hong Kong, China, Taiwan, India, Thailand, Vietnam, Indonesia |
| Oceania | Australia, New Zealand, Fiji |
| LATAM | Chile |

---

## Currency Conversion Rates

| Currency | To USD |
|----------|--------|
| EUR | × 1.08 |
| GBP | × 1.26 |
| JPY | ÷ 150 |
| SGD | × 0.74 |
| AUD | × 0.65 |
| INR | ÷ 83 |
| KRW | ÷ 1350 |
| TWD | ÷ 32 |
| THB | ÷ 35 |
| VND | ÷ 24500 |
| IDR | ÷ 15800 |
| BRL | ÷ 5.0 |

ASK → ASM conversion: multiply ASKs (kilometers) by **0.6214** to get ASMs (miles).

---

## Adjusted Spread Formula

```js
function calcAdjSpread(airline, scenario) {
  const { trasm, fuelCasm, hedgePct, hedgeTenor } = airline;
  const { jetPctUp } = scenario;
  const rawSpread = trasm - fuelCasm;
  const fuelIncrease = fuelCasm * jetPctUp;
  const tenorDiscount = hedgeTenor > 0
    ? Math.max(0, 1 - (24 - hedgeTenor) * 0.008)
    : 1;
  const hedgedProtection = fuelIncrease * hedgePct * tenorDiscount;
  const netFuelHit = fuelIncrease - hedgedProtection;
  return rawSpread - netFuelHit;
}
```

**Interpretation:**
- Positive adjSpread → airline covers fuel cost increase, remains profitable per ASM
- Negative adjSpread → airline loses money per ASM under this scenario
- Higher hedgePct + longer tenor → more protection → higher adjSpread

---

## Scenario Definitions

| ID | Label | jetPctUp | Direction vs Today |
|----|-------|----------|-------------------|
| current | Current (+100%) | 1.00 | ▶ THIS IS TODAY — actual market state |
| moderate | Moderate (+50%) | 0.50 | ↓ DEESCALATION — prices fall ~25% from current |
| severe | Severe (+150%) | 1.50 | ↑ Escalation — prices rise ~25% above current |
| extreme | Extreme (+200%) | 2.00 | ↑↑ Worst case — full Hormuz blockade |

---

## Scenarios Array (exact)

```js
const SCENARIOS = [
  { id:"current",  label:"Current (+100%)",  jetPctUp:1.00, color:"#ef4444",
    desc:"ACTUAL state — jet fuel DOUBLED from pre-conflict baseline.",
    directionNote:"▶ Current market state" },
  { id:"moderate", label:"Moderate (+50%)",   jetPctUp:0.50, color:"#f97316",
    desc:"Deescalation — jet fuel falls ~25% from current to +50% above baseline.",
    directionNote:"↓ Deescalation — prices BELOW current" },
  { id:"severe",   label:"Severe (+150%)",    jetPctUp:1.50, color:"#dc2626",
    desc:"Hormuz closure + regional refinery disruption.",
    directionNote:"↑ Escalation beyond current" },
  { id:"extreme",  label:"Extreme (+200%)",   jetPctUp:2.00, color:"#7f1d1d",
    desc:"Full blockade + total Iranian export halt.",
    directionNote:"↑↑ Worst-case scenario" },
];
```

---

## Market Snapshot Tiles

```js
const MARKET_TILES = [
  { label:"Brent Crude",      value:"$98.40/bbl",    sub:"Iran conflict premium +$34/bbl" },
  { label:"Jet Fuel NW EU",   value:"$1,730/mt",     sub:"All-time high; +100% vs pre-conflict" },
  { label:"Jet Crack Spread", value:"$38.50/bbl",    sub:"vs historical avg $8–12/bbl" },
  { label:"Hormuz Status",    value:"RESTRICTED",    sub:"Military conflict active" },
  { label:"Carriers at Risk", value:"[N]/[TOTAL]",    sub:"Negative unit economics at current" },
  { label:"Unhedged Carriers", value:"[N]/[TOTAL]",  sub:"Zero derivative protection" },
];
```

Update values from MCP data each cycle. Tiles 5-6 are computed from AIRLINES.

---

## Column Tooltips (exact text)

```js
const TOOLTIPS = {
  trasm:     "Total Revenue per ASM (¢). All passenger + cargo + ancillary revenue ÷ total capacity.",
  prasm:     "Passenger Revenue per ASM (¢). Fare revenue only, excluding cargo and ancillaries.",
  casm:      "Total Cost per ASM (¢). All operating costs ÷ ASMs. Lower = more efficient operator.",
  fuelCasm:  "Fuel Cost per ASM (¢). This component doubles under Current (+100%) scenario.",
  casmEx:    "CASM excluding fuel (¢). Labor, maintenance, airports, admin — not directly fuel-impacted.",
  fuelGal:   "Pre-conflict base fuel price per US gallon used to derive Fuel CASM.",
  asm:       "Available Seat Miles (billions). Size proxy. Larger bubble in scatter = bigger carrier.",
  lf:        "Load Factor — % of seats occupied. Higher LF dilutes fixed costs per passenger.",
  hedgePct:  "% of annual fuel hedged with derivatives. Bar: green ≥60%, orange 30-59%, red 0-29%.",
  tenor:     "How far forward hedges extend. 12mo = covered through ~same month next year.",
  adjSpread: "Adjusted Spread = (TRASM−FuelCASM) − net unhedged fuel increase. Green = profit/ASM.",
  region:    "Geographic classification. NA = North America (US+Canada).",
};
```

---

## Output Validation Checklist

Before committing, verify:
- [ ] `dist/index.html` is the ONLY output file (no App.jsx)
- [ ] `const GROUNDED_DATA` exists with entries matching `config/tickers.json`, names match `AIRLINES`
- [ ] Every `AIRLINES[i].hedgePct` / `hedgeTenor` / `tenorLabel` matches `GROUNDED_DATA[i]` and has `CONFIRM` or `CAUTION` (not `UNVERIFIED`) unless explicitly carried stale with note
- [ ] No `verbatim_quote` is empty for any CONFIRM/CAUTION hedge field
- [ ] All airlines from `config/tickers.json` present in AIRLINES array
- [ ] All required tabs render per `skills/frontend-design.md` (currently 6 if Evidence is hidden)
- [ ] Region codes are "NA" not "US"
- [ ] Timestamp reads "Using Bigdata.com data as of: ..."
- [ ] Moderate scenario labeled as deescalation with ↓ arrow
- [ ] prop-types CDN loaded before Recharts
- [ ] function App() — no "export default"
- [ ] No <script src="./App.jsx"> — all JSX inlined
- [ ] File size 70–140 KB (may grow slightly with GROUNDED_DATA)
