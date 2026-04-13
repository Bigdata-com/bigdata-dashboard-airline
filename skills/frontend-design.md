# Frontend Design Specification — Airline Dashboard

This file is the **authoritative visual contract** for `dist/index.html`.
Read this file at the start of every Cowork cycle. Do NOT regenerate it.

---

## Fonts

| Usage | Family | CDN |
|-------|--------|-----|
| Body / UI / labels | **DM Sans** (300–700) | Google Fonts |
| Numbers / prices / code / monospace | **JetBrains Mono** (400–600) | Google Fonts |

Load via `<link>` in `<head>`. Never add Google Fonts inside `<script>`.

---

## Color Palette

```js
const COLORS = {
  bg:       "#0a0a0a",   // page background
  card:     "#0f172a",   // card / panel background — FLAT, no gradient, no box-shadow
  border:   "#1e293b",   // card borders, dividers
  borderHi: "#1e3a5f",   // active / hover border
  text:     "#e5e7eb",   // primary text
  textMid:  "#94a3b8",   // secondary text
  textDim:  "#64748b",   // muted text
  textDark: "#475569",   // footnotes, labels
  accent:   "#60a5fa",   // blue accent, links, active tab underline
  green:    "#34d399",   // positive values, hedged badge
  yellow:   "#facc15",   // caution, partial hedge
  orange:   "#f97316",   // partial badge, moderate scenario
  red:      "#ef4444",   // negative values, unhedged, current scenario
  darkRed:  "#7f1d1d",   // extreme scenario
  regionNA: "#3b82f6",   // North America
  regionEU: "#8b5cf6",   // Europe
  regionMENA:"#f59e0b",  // Middle East & Africa
  regionAsia:"#10b981",  // Asia-Pacific
  regionOC: "#06b6d4",   // Oceania
  regionLA: "#ec4899",   // Latin America
};
```

---

## CDN Script Order (in `<head>`)

1. Google Fonts `<link>` (DM Sans + JetBrains Mono)
2. `react@18/umd/react.production.min.js`
3. `react-dom@18/umd/react-dom.production.min.js`
4. `prop-types@15.8.1/prop-types.min.js` — **REQUIRED** for Recharts UMD
5. `@babel/standalone/babel.min.js`
6. `recharts@2.12.7/umd/Recharts.js`

---

## HTML Structure

```
dist/index.html
├── <head>  — fonts, CDN scripts (order above)
├── <style> — scrollbar CSS, global resets
├── <body>
│   ├── <div id="root">
│   ├── <script type="text/babel">  — ALL JSX inlined here
│   │   ├── const GEN_TS = ...
│   │   ├── const GROUNDED_DATA = [...]   ← provenance per skills/data-pipeline.md
│   │   ├── const AIRLINES = [...]        ← values must match GROUNDED_DATA
│   │   ├── const SCENARIOS = [...]
│   │   ├── const AUDIT_CHUNKS = [...]    ← optional if Audit tab omitted
│   │   ├── helper functions (calcAdjSpread, etc.)
│   │   ├── sub-components (HedgeBar, SpreadChip, badges, MethodBox)
│   │   ├── tab components (6 or 7 tabs per product policy)
│   │   └── function App() { ... }  ← NO "export default"
│   └── <script type="text/babel">  — bootstrap
│       └── ReactDOM.createRoot(...).render(React.createElement(App))
```

**CRITICAL**: Do NOT use `<script src="./App.jsx">` — CORS blocks on `file://`.
All JSX must be inlined in `index.html`.

---

## Component Contracts

### Column Definitions in MethodBox (NOT tooltips on headers)

**Do NOT use `?` tooltip icons on table column headers.** CSS tooltips break
inside sticky `<th>` + `overflow-x: auto` containers (clipped by overflow).

Instead, put a **column definitions table** inside the `<MethodBox>` at the
top of each tab that has a data table. Format:

```jsx
<MethodBox>
  <strong>Tab Name</strong> description...<br/><br/>
  <strong>Column definitions:</strong>
  <table style={{width:"100%",margin:"8px 0",fontSize:11,borderCollapse:"collapse"}}>
    <tbody>
      <tr>
        <td style={{padding:"3px 8px",color:"#94a3b8",fontWeight:600,whiteSpace:"nowrap",borderBottom:"1px solid #1e293b"}}>COL NAME</td>
        <td style={{padding:"3px 8px",color:"#64748b",borderBottom:"1px solid #1e293b"}}>Description. Mark <em>Derived.</em> if calculated.</td>
      </tr>
      {/* ... more rows ... */}
    </tbody>
  </table>
</MethodBox>
```

Mark any calculated/derived column with `<em>Derived.</em>` prefix and
show the formula. Examples:
- **ADJ SPREAD**: *Derived.* = (TRASM − Fuel CASM) − (Fuel CASM × jetPctUp × (1 − hedgePct × tenorDiscount))
- **CASM**: *Derived.* = Fuel CASM + CASM-ex

Column headers themselves should be **plain text** with sort arrows only — no `?` icons.

### SpreadChip
Color thresholds: `val < -3` → red, `< 0` → orange, `< 3` → yellow, `≥ 3` → green.

### HedgeBar
Color thresholds: `pct ≥ 0.6` → green, `≥ 0.3` → orange, `< 0.3` → red.

### Status Badges
| Badge | Color | Background |
|-------|-------|------------|
| PRIVATE | `#fbbf24` | `#1a1200` |
| SUB | `#a78bfa` | `#1a0f2e` |
| UNHEDGED | `#ef4444` | `#2a0808` |
| PARTIAL | `#f97316` | `#1a0e00` |
| HEDGED | `#34d399` | `#001a0e` |

---

## Methodology Panels

Every tab starts with a collapsible methodology panel explaining:
- What the tab shows
- How values are calculated
- What the color coding means
- Key caveats (e.g. crude-only hedges, estimated data)

Style: `background: #080c14`, `border: 1px solid #1e293b`, `border-radius: 8px`,
`padding: 12px 16px`, `font-size: 12px`, `color: #64748b`, italic icon prefix.

---

## Scenario Direction Labels

| Scenario | jetPctUp | Direction vs Current |
|----------|----------|---------------------|
| Current (+100%) | 1.00 | ▶ THIS IS TODAY |
| Moderate (+50%) | 0.50 | ↓ Deescalation — prices FALL from current |
| Severe (+150%) | 1.50 | ↑ Escalation beyond current |
| Extreme (+200%) | 2.00 | ↑↑ Worst-case blockade |

**CRITICAL**: Moderate is a PRICE DECREASE from current. Label it clearly
with a green-tinted down arrow. Never imply "moderate increase."

---

## Market Snapshot Tiles

6 tiles in header. Each tile:
- **LABEL**: 10px uppercase, letterSpacing 0.8px, `#64748b`
- **VALUE**: 16px JetBrains Mono bold, `#f0f9ff`
- **SUB-DESCRIPTION**: 11px, contextual color (red for increases, orange for alerts)

---

## Region Codes

Use these throughout — never "US":
| Code | Full Name |
|------|-----------|
| NA | North America |
| EU | Europe |
| MENA | Middle East & Africa |
| Asia | Asia-Pacific |
| Oceania | Oceania |
| LATAM | Latin America |

---

## Timestamp Format

Display: `Using Bigdata.com data as of: 2026-03-24 14:30 UTC`
NOT: `Live Bigdata.com data · Generated ...`

---

## Seven Tabs

### 1. Resilience Ranking
Sortable table with rank medals, hedge bars, adj spread chips.
**ALL data columns must be sortable** (Rgn, Hedge %, Tenor, TRASM, Fuel CASM, Adj Spread).
Use `React.useState` for `sortKey` + `sortAsc`. **Default:** `sortKey` initial value
**`"hedgePct"`**, `sortAsc` **`false`** (Hedge % descending — highest hedge first).
Clicking a column header sorts descending first; clicking again toggles ascending.
Show `▲` / `▼` arrow on the active sort column.
**No `?` icons** — column definitions go in MethodBox (see Component Contracts above).
Use a `SortTh` helper component:
```jsx
function SortTh({k,label}) {
  return (
    <th onClick={()=>toggleSort(k)} style={{cursor:"pointer",userSelect:"none"}}>
      <span style={{color:sortKey===k?"#60a5fa":"#64748b"}}>{label}{arrow(k)}</span>
    </th>
  );
}
```
String columns (region) must use `localeCompare` for sorting.
MethodBox MUST include a column definitions table with: RGN, HEDGE %, TENOR,
TRASM, FUEL CASM, ADJ SPREAD (*Derived* — show formula), STATUS.

### 2. Hedge Positions
Card grid: coverage, tenor, price, instruments, policy.

### 3. Risk vs Spread
Recharts ScatterChart (X=hedge%, Y=adjSpread, Z=√ASMs).

### 4. Margin Impact
Recharts grouped BarChart, all 4 scenarios side-by-side.

### 5. Region View
Cards per region with aggregated stats (Avg Hedge, Avg Spread, Profitable count).
Each region card **MUST have a column header row** below the summary stats and above
the airline rows:
```
  AIRLINE              HEDGE    SPREAD
  🇬🇧 British Airways    75%    +15.0c
  ...
```
Header row style: `fontSize:10, fontWeight:600, color:#475569, textTransform:uppercase,
letterSpacing:0.5px`, with a `borderBottom: 1px solid #334155` separator.
Hedge and Spread values should be right-aligned with fixed widths (32px / 52px).

### 6. Operating Metrics
Full detail table with all unit economics.
**ALL columns must be sortable with asc/desc toggle** — including Airline (alphabetical),
Rgn (alphabetical), and Ticker (alphabetical). Use same `toggleSort` / `arrow` pattern.
**No `?` icons** — column definitions go in MethodBox (see Component Contracts above).
MethodBox MUST include a column definitions table with ALL columns:
AIRLINE, RGN, TICKER, TRASM, PRASM, FUEL CASM, CASM-EX,
CASM (*Derived* = Fuel CASM + CASM-ex), $/GAL, ASMS(B), LF %.
Mark CASM as *Derived* with formula. Include FX conversion rates in MethodBox.

### 7. Evidence & Sources (mandatory)
Interactive tab surfacing `GROUNDED_DATA` provenance for every airline and metric.
This tab MUST always be included — it is the user-facing audit trail.

**Layout:** One expandable card per airline (flag + name + ticker in header row).
Each card has rows for the key grounded fields: `hedgePct`, `hedgeTenor`, `trasm`.

**Per-field row (collapsed):** field label (uppercase) | value | `ConfBadge` | source name | document date.
**Per-field row (expanded on click):** verbatim quote in italic blockquote style
(`background:#080c14`, `borderRadius:6`, `padding:8px 12px`), notes line, and
clickable "View source document" link (opens URL in new tab) when `url` is present.

**Filter bar:** buttons for ALL / CONFIRM / CAUTION / UNVERIFIED with live counts.
Summary stats on the right showing percentage breakdown (e.g. "76% confirmed").

**`ConfBadge` component:** same color scheme as status badges:
- CONFIRM: green (`#34d399` on `#001a0e`)
- CAUTION: amber (`#fbbf24` on `#1a1200`)
- UNVERIFIED: red (`#ef4444` on `#1a0808`)

**MethodBox** must explain the three confidence levels and what they mean.

---

## GROUNDED_DATA & user-facing honesty

- Emit **`const GROUNDED_DATA`** (see `skills/data-pipeline.md`) before `AIRLINES`.
- In the page header subtitle, add a clickable link **“All figures sourced & cited”**
  that sets `activeTab` to the Evidence & Sources tab index (tab 7). Style:
  `color:#60a5fa, cursor:pointer, textDecoration:underline, textDecorationStyle:dotted`.
- The Evidence & Sources tab (Tab 7) renders `GROUNDED_DATA` interactively — see
  the tab spec above. This replaces the old “view page source” approach.
- Do not claim “verified” in UI unless the underlying `confidence` is `CONFIRM`.

---

## Size Budget

- `dist/index.html`: ~70–180 KB (data + JSX + `GROUNDED_DATA` inlined)
- Aim for ≤ 1100 lines of JSX when `GROUNDED_DATA` is full
- No external files required
