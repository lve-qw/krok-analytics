"""Stylesheet for the dashboard.

Two decisions drive everything below.

**One source of truth for the theme.** The theme is a class on `#viz-root`,
written by the toggle callback and read by the CSS. There is no
`prefers-color-scheme` rule: when the OS said "dark" and the store still said
"light", the page went dark while Plotly kept drawing on white paper and the
table drew white text on white cells. A media query cannot see the store, so
the query had to go rather than the store.

**The table is inside the token system.** Dash renders `DataTable` cells with
its own colours, so the style props in `layout.py` hand it `var(--…)` values.
Custom properties inherit through the DOM, which means the table follows the
theme class with no callback of its own.

The type has one idea: numbers are set with tabular figures so a column of
percentages lines up, and micro-labels are the only uppercase text on the page,
which is what makes them read as labels without a box or a rule around them.
"""

LIGHT_TOKENS = """
  color-scheme: light;
  --surface-1: #fcfcfb;
  --surface-2: #f3f3ef;
  --page: #f9f9f7;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --muted: #898781;
  --grid: #e1e0d9;
  --border: rgba(11,11,11,0.10);
  --border-strong: rgba(11,11,11,0.18);
  --accent: #2a78d6;
  --accent-soft: rgba(42,120,214,0.10);
  --warning: #fab219;
  --warning-ink: #0b0b0b;
  --shadow: 0 1px 2px rgba(11,11,11,0.04);
"""

DARK_TOKENS = """
  color-scheme: dark;
  --surface-1: #1a1a19;
  --surface-2: #242422;
  --page: #0d0d0d;
  --text-primary: #ffffff;
  --text-secondary: #c3c2b7;
  --muted: #898781;
  --grid: #2c2c2a;
  --border: rgba(255,255,255,0.10);
  --border-strong: rgba(255,255,255,0.20);
  --accent: #3987e5;
  --accent-soft: rgba(57,135,229,0.16);
  --warning: #fab219;
  --warning-ink: #0b0b0b;
  --shadow: none;
"""

# The tokens are declared twice from one source. On `.viz-root` they are
# guaranteed; on `body:has(...)` they also reach the dropdown menus, which Dash
# renders in a portal outside the root and which would otherwise fall back to
# their built-in light colours on a dark page.
_TOKENS = f"""
.viz-root.theme-light {{{LIGHT_TOKENS}}}
.viz-root.theme-dark {{{DARK_TOKENS}}}
body:has(.viz-root.theme-light) {{{LIGHT_TOKENS}}}
body:has(.viz-root.theme-dark) {{{DARK_TOKENS}}}
"""

STYLESHEET = _TOKENS + """
body { margin: 0; background: var(--page); }
.viz-root {
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  background: var(--page);
  color: var(--text-primary);
  min-height: 100vh;
  padding: 18px 24px 40px;
  box-sizing: border-box;
  font-size: 14px;
}
.viz-root * { box-sizing: border-box; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

/* ---------- header ---------------------------------------------------- */

.app-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 16px; flex-wrap: wrap;
}
.app-title { margin: 0; font-size: 24px; font-weight: 650; letter-spacing: -0.02em; }
.app-subtitle { margin: 3px 0 0; font-size: 14px; color: var(--text-secondary); }
.header-actions { display: flex; gap: 8px; align-items: center; }

/* The eyebrow is the only uppercase text on the page, which is what lets it
   label a block without needing a rule or a box. */
.eyebrow {
  font-size: 11px; font-weight: 600; letter-spacing: 0.09em;
  text-transform: uppercase; color: var(--muted);
}

/* ---------- provenance strip ------------------------------------------ */

.provenance {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  margin: 14px 0 16px; padding: 10px 14px;
  border: 1px solid var(--border); border-left: 3px solid var(--warning);
  border-radius: 8px; background: var(--surface-1);
}
.banner-tag {
  font-size: 11px; font-weight: 700; letter-spacing: 0.07em;
  padding: 4px 9px; border-radius: 4px;
  background: var(--warning); color: var(--warning-ink); white-space: nowrap;
}
.provenance-text { font-size: 13px; color: var(--text-secondary); }
.provenance-chain {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  font-size: 13px; color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
.provenance-chain b { color: var(--text-primary); font-weight: 620; }
.provenance-arrow { color: var(--muted); }

/* ---------- tabs ------------------------------------------------------- */

.tabs-bar { border-bottom: 1px solid var(--border); margin: 0 0 16px; }
.tabs-inner { display: flex !important; justify-content: flex-start !important; }
.tab { flex: 0 0 auto !important; }
.tab {
  font-family: inherit; font-size: 14px; font-weight: 500;
  padding: 9px 16px !important; cursor: pointer;
  background: transparent !important; color: var(--text-secondary) !important;
  border: none !important; border-bottom: 2px solid transparent !important;
}
.tab:hover { color: var(--text-primary) !important; }
.tab--selected {
  color: var(--text-primary) !important; font-weight: 620;
  border-bottom: 2px solid var(--accent) !important;
  background: transparent !important;
}
.tab-content { padding-top: 2px; }

/* ---------- KPI ------------------------------------------------------- */

/* Twelve columns, three cards per row at span 4. With the five-card set that
   leaves two on the second row, which are widened to span 6 so the row fills
   exactly — a lone trailing card reads as something the layout forgot.
   Seven equal cards in one strip is what made the numbers small. */
.kpi-row { display: grid; grid-template-columns: repeat(12, 1fr); gap: 12px; margin-bottom: 18px; }
.kpi-card {
  grid-column: span 4;
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px 15px;
  display: flex; flex-direction: column; gap: 2px;
  box-shadow: var(--shadow); min-width: 0;
}
.kpi-card:nth-child(n+4) { grid-column: span 6; }
.kpi-head { display: flex; align-items: baseline; gap: 6px; justify-content: space-between; }
.kpi-label { font-size: 13px; color: var(--text-secondary); line-height: 1.25; }
.kpi-value {
  font-size: 34px; font-weight: 620; color: var(--text-primary);
  line-height: 1.1; letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums; margin-top: 4px;
}
.kpi-unit { font-size: 15px; font-weight: 500; color: var(--muted); margin-left: 4px; letter-spacing: 0; }
.kpi-detail { font-size: 12.5px; color: var(--muted); font-variant-numeric: tabular-nums; }

/* ---------- info tooltip ---------------------------------------------- */

/* CSS-only: a demo laptop should not depend on a tooltip library, and the
   caveats have to be readable on a projector, which a native title= is not. */
.info {
  position: relative; flex: 0 0 auto;
  width: 16px; height: 16px; border-radius: 50%;
  border: 1px solid var(--border-strong); color: var(--muted);
  font-size: 10px; font-weight: 700; line-height: 14px; text-align: center;
  cursor: help; user-select: none;
}
.info:hover, .info:focus-visible { color: var(--text-primary); border-color: var(--accent); }
.info::after {
  content: attr(data-tip);
  /* Anchored by its LEFT edge so the box opens into the page. Anchoring it
     right put the tip of a left-hand card 300px off the left of the viewport,
     where it was simply unreadable. `.info--end` flips it for controls that
     sit near the right edge. */
  position: absolute; top: calc(100% + 8px); left: -4px; right: auto; z-index: 40;
  width: max-content; max-width: min(320px, calc(100vw - 32px));
  padding: 9px 11px; border-radius: 8px;
  background: var(--surface-2); color: var(--text-primary);
  border: 1px solid var(--border-strong); box-shadow: 0 6px 20px rgba(0,0,0,0.18);
  font-size: 12.5px; font-weight: 400; line-height: 1.45; text-align: left;
  white-space: pre-line; letter-spacing: 0;
  opacity: 0; visibility: hidden; transition: opacity 120ms ease;
}
.info--end::after { left: auto; right: -4px; }
.info:hover::after, .info:focus-visible::after { opacity: 1; visibility: visible; }

/* ---------- filters --------------------------------------------------- */

.filter-bar {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 10px; padding: 13px 16px 14px; margin-bottom: 12px;
  box-shadow: var(--shadow);
}
.filter-grid { display: grid; gap: 10px 12px; grid-template-columns: repeat(5, 1fr); }
.filter-label {
  display: block; font-size: 11.5px; color: var(--text-secondary);
  margin-bottom: 4px; font-weight: 500;
}
.filter-more { margin-top: 12px; }
.filter-more > summary {
  font-size: 13px; color: var(--accent); cursor: pointer;
  list-style: none; display: inline-flex; align-items: center; gap: 6px;
  padding: 2px 0;
}
.filter-more > summary::-webkit-details-marker { display: none; }
.filter-more > summary::before { content: "▸"; font-size: 10px; }
.filter-more[open] > summary::before { content: "▾"; }
.filter-more .filter-grid { margin-top: 10px; }
.filter-actions {
  display: flex; gap: 8px; margin-top: 13px; align-items: center; flex-wrap: wrap;
}
.ghost-button {
  font-family: inherit; font-size: 13px; padding: 7px 14px;
  border: 1px solid var(--border-strong); border-radius: 6px;
  background: transparent; color: var(--text-primary); cursor: pointer;
  transition: background 120ms ease;
}
.ghost-button:hover { background: var(--surface-2); }

/* ---------- chips ------------------------------------------------------ */

.chip-row {
  display: flex; gap: 7px; flex-wrap: wrap; align-items: center;
  margin: 0 0 14px 2px; min-height: 24px;
}
/* The chips render into their own container so the clear button can live in
   the initial layout, but they still need to flow in the same wrapping row. */
.chip-list { display: contents; }
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12.5px; padding: 4px 10px; border-radius: 20px;
  background: var(--surface-2); border: 1px solid var(--border);
  color: var(--text-secondary);
}
.chip b { color: var(--text-primary); font-weight: 600; }
.chip-none { font-size: 12.5px; color: var(--muted); }

/* The selection chip is a button because clicking it clears the selection —
   the one place on the page where a chip is not just a readout. */
.chip-selection {
  font-family: inherit; font-size: 13px; padding: 5px 8px 5px 12px;
  display: inline-flex; align-items: center; gap: 10px;
  border-radius: 20px; cursor: pointer;
  background: var(--accent-soft); border: 1px solid var(--accent);
  color: var(--text-primary);
}
.chip-selection:hover { background: var(--accent); color: #ffffff; }
.chip-selection .chip-x {
  font-size: 14px; line-height: 1; opacity: 0.8;
  border-left: 1px solid var(--border-strong); padding-left: 9px;
}

.result-count {
  font-size: 13px; color: var(--text-secondary); margin: 0 0 14px 2px;
  font-variant-numeric: tabular-nums;
}

/* ---------- cards & chart grid ---------------------------------------- */

.chart-grid { display: grid; gap: 12px; grid-template-columns: repeat(2, 1fr); }
.card {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px 10px; min-width: 0;
  box-shadow: var(--shadow);
}
.card-full { grid-column: 1 / -1; }
/* The note sits beside its title, not floated to the far edge of the card,
   so it is obvious which heading it explains. */
.card-head { display: flex; align-items: center; gap: 7px; justify-content: flex-start; }
.card-title { margin: 0; font-size: 15px; font-weight: 620; letter-spacing: -0.01em; }
.card-subtitle { margin: 3px 0 8px; font-size: 12.5px; color: var(--muted); line-height: 1.4; }
.card-toggle { font-size: 13px; color: var(--text-secondary); margin: 2px 0 6px; }
.card-toggle label { margin-right: 16px; cursor: pointer; }
.card-toggle input { margin-right: 5px; }
.card-hint { font-size: 12px; color: var(--muted); margin: 2px 0 6px; }
.chart-controls {
  display: flex; align-items: flex-start; gap: 24px; flex-wrap: wrap;
  margin: 6px 0 2px;
}
.chart-control { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.control-label {
  color: var(--muted); font-size: 11.5px; font-weight: 600;
  letter-spacing: 0.02em;
}
.assumption-control {
  max-width: 620px; padding: 8px 8px 18px; margin: 4px 0 2px;
}
.assumption-control .control-label { display: block; margin-bottom: 11px; }
.assumption-control .rc-slider-rail { background: var(--grid); }
.assumption-control .rc-slider-track { background: var(--accent); }
.assumption-control .rc-slider-handle {
  border-color: var(--accent); background: var(--surface-1); opacity: 1;
}
.assumption-control .rc-slider-mark-text { color: var(--muted); font-size: 11px; }
.assumption-control .rc-slider-tooltip-inner {
  background: var(--text-primary); color: var(--surface-1); box-shadow: none;
}
.assumption-control .rc-slider-tooltip-arrow { border-top-color: var(--text-primary); }

/* ---------- drill-down table ------------------------------------------ */

/* Dash paints the table with its own colours, so these three rules put the
   scrollers and the sticky header back on the surface tokens. The cell colours
   themselves are set as var() in the DataTable style props. */
.records .dash-spreadsheet-container,
.records .dash-spreadsheet-inner,
.records .dash-freeze-top { background: var(--surface-1) !important; }
.records .dash-cell-value { color: var(--text-primary) !important; }
.records .dash-table-container .previous-next-container {
  color: var(--text-secondary); font-size: 13px; padding-top: 8px;
}
.records .dash-table-container .previous-next-container .page-number .current-page,
.records input.current-page {
  color: var(--text-primary) !important; background: var(--surface-2) !important;
  border-bottom-color: var(--border-strong) !important;
}
.records .dash-table-container .previous-next-container button {
  color: var(--text-secondary) !important;
}
.records .column-header--sort svg { fill: var(--muted); }

/* ---------- limitations ----------------------------------------------- */

.limitations { margin: 6px 0 4px; padding-left: 18px; }
.limitations li { font-size: 13px; color: var(--text-secondary); margin-bottom: 7px; line-height: 1.45; }

/* ---------- dropdown internals ---------------------------------------- */

/* Dash 4 draws its dropdown with built-in light colours. Left alone, the
   selected value came out near-black on the dark surface and the control read
   as an empty box — the same failure as the table, in another component. */
.dash-dropdown {
  background: var(--surface-1) !important;
  border-color: var(--border-strong) !important;
  color: var(--text-primary) !important;
  font-size: 13px !important;
}
.dash-dropdown:hover { border-color: var(--border-strong) !important; }
.dash-dropdown[data-state="open"] { border-color: var(--accent) !important; }
.dash-dropdown-value, .dash-dropdown-value-item { color: var(--text-primary) !important; }
.dash-dropdown-placeholder { color: var(--muted) !important; }
.dash-dropdown-trigger-icon { color: var(--muted) !important; }
.dash-dropdown-content, .dash-dropdown-options {
  background: var(--surface-1) !important;
  border-color: var(--border-strong) !important;
  color: var(--text-primary) !important;
  font-size: 13px !important;
}
.dash-options-list-option { color: var(--text-primary) !important; }
.dash-options-list-option:hover,
.dash-options-list-option[data-highlighted] { background: var(--surface-2) !important; }
.dash-options-list-option[aria-selected="true"] { background: var(--accent-soft) !important; }
.dash-dropdown-search-container { background: var(--surface-1) !important; }
.dash-dropdown-search {
  background: var(--surface-2) !important;
  color: var(--text-primary) !important;
  border-color: var(--border-strong) !important;
}
.dash-dropdown-search::placeholder { color: var(--muted) !important; }
.dash-dropdown-search-icon { color: var(--muted) !important; }
.dash-dropdown-actions { background: var(--surface-1) !important; }
.dash-dropdown-action-button { color: var(--accent) !important; }
.dash-options-list-option-text { color: var(--text-primary) !important; }

/* ---------- responsive ------------------------------------------------- */

/* Desktop presentation is the target; these two steps keep 1280 and 1024
   readable rather than pretending the page is a phone. */
@media (max-width: 1400px) {
  .filter-grid { grid-template-columns: repeat(4, 1fr); }
}
@media (max-width: 1120px) {
  .viz-root { padding: 16px 16px 32px; }
  .chart-grid { grid-template-columns: 1fr; }
  .filter-grid { grid-template-columns: repeat(3, 1fr); }
  /* The 3 + 2 KPI grid survives down to 1024; only below that does a card get
     too narrow for its label, and only then does it drop to two across. */
  .kpi-value { font-size: 30px; }
}
@media (max-width: 1000px) {
  .kpi-card, .kpi-card:nth-child(n+4) { grid-column: span 6; }
}
@media (max-width: 820px) {
  .filter-grid { grid-template-columns: repeat(2, 1fr); }
  .kpi-card, .kpi-card:nth-child(n+4) { grid-column: span 12; }
}

@media (prefers-reduced-motion: reduce) {
  .viz-root *, .viz-root *::after { transition: none !important; animation: none !important; }
}
"""
