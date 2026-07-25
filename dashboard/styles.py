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
  --surface-1: #f9fafb;
  --surface-2: #e9edf1;
  --page: #f1f3f5;
  --text-primary: #121820;
  --text-secondary: #4b5663;
  --muted: #7b8794;
  --grid: #dce2e8;
  --border: rgba(18,24,32,0.11);
  --border-strong: rgba(18,24,32,0.22);
  --accent: #2557c7;
  --accent-soft: rgba(37,87,199,0.10);
  --copper: #a8663d;
  --ink-panel: #17212b;
  --ink-panel-text: #f4f6f8;
  --warning: #c99128;
  --warning-ink: #121820;
  --shadow: 0 14px 38px rgba(20,31,44,0.06);
"""

DARK_TOKENS = """
  color-scheme: dark;
  --surface-1: #171e26;
  --surface-2: #202a34;
  --page: #10151b;
  --text-primary: #f2f5f7;
  --text-secondary: #b8c1cb;
  --muted: #7f8c99;
  --grid: #2b3743;
  --border: rgba(242,245,247,0.10);
  --border-strong: rgba(242,245,247,0.21);
  --accent: #6d91f0;
  --accent-soft: rgba(109,145,240,0.14);
  --copper: #c47a4c;
  --ink-panel: #0c1117;
  --ink-panel-text: #f2f5f7;
  --warning: #d4a13d;
  --warning-ink: #10151b;
  --shadow: 0 18px 44px rgba(0,0,0,0.24);
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

/* ---------- observed data boundary ------------------------------------ */

.data-boundary {
  display: grid;
  grid-template-columns: minmax(190px, 0.8fr) minmax(360px, 1.5fr) minmax(260px, 1fr);
  gap: 18px;
  align-items: center;
  margin: 14px 0 16px;
  padding: 14px 16px;
  border: 1px solid var(--border-strong);
  border-left: 4px solid var(--accent);
  border-radius: 10px;
  background: var(--surface-1);
  box-shadow: var(--shadow);
}
.boundary-title { display: flex; flex-direction: column; gap: 3px; }
.boundary-title strong { font-size: 15px; font-weight: 650; }
.boundary-fields { display: flex; gap: 7px; flex-wrap: wrap; }
.boundary-fields code {
  padding: 4px 8px;
  border-radius: 5px;
  background: var(--surface-2);
  color: var(--text-primary);
  border: 1px solid var(--border);
  font-size: 12px;
}
.boundary-note {
  margin: 0;
  color: var(--text-secondary);
  font-size: 12.5px;
  line-height: 1.45;
}

/* ---------- KPI ------------------------------------------------------- */

/* Four measured cards, one row on the presentation viewport. */
.kpi-row { display: grid; grid-template-columns: repeat(12, 1fr); gap: 12px; margin-bottom: 18px; }
.kpi-card {
  grid-column: span 3;
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px 15px;
  display: flex; flex-direction: column; gap: 2px;
  box-shadow: var(--shadow); min-width: 0;
}
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
.filter-bar-simple {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
}
.filter-bar-simple .filter-cell { width: min(440px, 100%); }
.filter-bar-simple .filter-actions { margin-top: 0; }
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
.records-section { margin-top: 12px; }
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

/* ---------- executive telemetry composition --------------------------- */

.viz-root {
  width: min(1560px, 100%);
  margin: 0 auto;
  padding: 30px 38px 56px;
  font-family: "Avenir Next", "Segoe UI Variable", system-ui, sans-serif;
}
.app-header {
  align-items: flex-end;
  gap: 28px;
  padding: 2px 0 24px;
  border-bottom: 1px solid var(--border-strong);
}
.brand-block { display: flex; flex-direction: column; align-items: flex-start; }
.brand-mark {
  color: var(--copper);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.16em;
  margin-bottom: 10px;
}
.app-title {
  font-size: clamp(32px, 3vw, 46px);
  font-weight: 560;
  letter-spacing: -0.045em;
  line-height: 0.98;
}
.app-subtitle {
  margin-top: 12px;
  max-width: 620px;
  line-height: 1.5;
}
.header-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  padding-right: 16px;
  border-right: 1px solid var(--border-strong);
}
.header-meta-label {
  color: var(--muted);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.header-meta strong { margin-top: 4px; font-size: 13px; font-weight: 620; }
.theme-button { min-height: 38px; }
.provenance { margin: 16px 0; }

.data-boundary {
  margin: 18px 0;
  padding: 17px 18px;
  border: 1px solid rgba(255,255,255,0.10);
  border-left: 4px solid var(--copper);
  border-radius: 12px;
  background: var(--ink-panel);
  color: var(--ink-panel-text);
  box-shadow: 0 18px 48px rgba(12,17,23,0.14);
}
.boundary-title .eyebrow { color: rgba(244,246,248,0.50); }
.boundary-title strong { font-size: 16px; font-weight: 620; }
.boundary-fields {
  display: grid;
  grid-template-columns: repeat(4, minmax(100px, 1fr));
  gap: 1px;
  background: rgba(255,255,255,0.13);
  border: 1px solid rgba(255,255,255,0.13);
}
.boundary-field {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 9px 11px;
  background: var(--ink-panel);
}
.boundary-field code {
  color: var(--ink-panel-text);
  font-family: "SFMono-Regular", Menlo, Consolas, monospace;
  font-size: 11.5px;
}
.boundary-field small {
  color: rgba(244,246,248,0.48);
  font-size: 9.5px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.boundary-note {
  color: rgba(244,246,248,0.62);
  font-size: 12px;
}
.boundary-note strong { color: var(--ink-panel-text); font-weight: 600; }

.filter-bar {
  margin: 18px 0 12px;
  padding: 0;
  border: none;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}
.ghost-button {
  padding: 8px 14px;
  border-radius: 7px;
  font-size: 12.5px;
  font-weight: 550;
}

.kpi-row {
  gap: 0;
  margin: 0 0 18px;
  overflow: hidden;
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  background: var(--surface-1);
  box-shadow: var(--shadow);
}
.kpi-card {
  padding: 18px 20px 20px;
  border: none;
  border-right: 1px solid var(--border);
  border-radius: 0;
  box-shadow: none;
  gap: 4px;
}
.kpi-card:last-child { border-right: none; }
.kpi-identity { display: flex; flex-direction: column; gap: 8px; }
.kpi-source {
  color: var(--copper);
  background: transparent;
  font-family: "SFMono-Regular", Menlo, Consolas, monospace;
  font-size: 10px;
  letter-spacing: 0.04em;
}
.kpi-label { font-size: 12.5px; }
.kpi-value {
  margin-top: 10px;
  font-size: clamp(31px, 2.8vw, 43px);
  font-weight: 560;
  line-height: 1.05;
  letter-spacing: -0.045em;
}
.kpi-unit { font-size: 12px; font-weight: 550; }
.kpi-detail { font-size: 11.5px; }

.chart-grid {
  gap: 14px;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 0.85fr);
}
.card {
  padding: 20px 22px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 12px;
}
.section-kicker {
  display: block;
  margin-bottom: 8px;
  color: var(--copper);
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}
.card-title {
  font-size: 18px;
  font-weight: 590;
  letter-spacing: -0.025em;
}
.card-subtitle { margin: 5px 0 12px; font-size: 12px; line-height: 1.45; }
.card-toggle {
  display: inline-flex;
  margin: 2px 0 4px;
  padding: 3px;
  border-radius: 7px;
  background: var(--surface-2);
  font-size: 11.5px;
}
.card-toggle label {
  margin: 0;
  padding: 4px 9px;
  border-radius: 5px;
}
.card-toggle input { margin-right: 5px; accent-color: var(--accent); }
.records-section { margin-top: 30px; }
.section-heading { margin: 0 0 12px 2px; }
.section-heading .section-kicker { margin-bottom: 5px; }
.section-title {
  margin: 0;
  font-size: 22px;
  font-weight: 570;
  letter-spacing: -0.03em;
}

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
  .data-boundary { grid-template-columns: 1fr 2fr; }
  .boundary-note { grid-column: 1 / -1; }
  .kpi-value { font-size: 30px; }
}
@media (max-width: 1000px) {
  .kpi-card { grid-column: span 6; }
}
@media (max-width: 820px) {
  .filter-grid { grid-template-columns: repeat(2, 1fr); }
  .filter-bar-simple { align-items: stretch; flex-direction: column; }
  .data-boundary { grid-template-columns: 1fr; }
  .boundary-note { grid-column: auto; }
  .kpi-card { grid-column: span 12; }
}

@media (prefers-reduced-motion: reduce) {
  .viz-root *, .viz-root *::after { transition: none !important; animation: none !important; }
}
"""

# ---------- additions for the full metric page --------------------------
#
# The base sheet was written for one screen with two charts. The metric page
# adds sections, three-column rows and the small stat strips that carry the
# supporting numbers metrics.md lists next to each headline value.

STYLESHEET += """
.metric-section { margin-top: 26px; }
.metric-section .section-heading { margin-bottom: 10px; }

.chart-grid.chart-grid-even { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.chart-grid.chart-grid-three { grid-template-columns: repeat(3, minmax(0, 1fr)); }

/* ---------- filters ---------------------------------------------------- */

.filter-footer {
  display: flex; align-items: center; justify-content: space-between;
  gap: 16px; flex-wrap: wrap; margin-top: 12px;
}
.filter-footer .filter-actions { margin-top: 0; }
.flag-check {
  display: flex; gap: 6px 18px; flex-wrap: wrap;
  font-size: 12.5px; color: var(--text-secondary);
}
.flag-check label { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
.flag-check input { accent-color: var(--accent); margin: 0; }

/* ---------- supporting numbers under a chart --------------------------- */

/* These read as a caption, not as a second row of KPI cards: the label is the
   uppercase micro-type already used elsewhere, and the value is only slightly
   larger than body text so it cannot compete with the headline cards. */
.stat-strip { display: flex; flex-wrap: wrap; gap: 8px 26px; margin: 4px 2px 12px; }
.stat { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
.stat-value {
  font-size: 17px; font-weight: 600; letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums; color: var(--text-primary);
}
.stat-label {
  font-size: 9.5px; font-weight: 650; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--muted);
}

/* ---------- export warnings -------------------------------------------- */

.provenance-notes { display: flex; flex-direction: column; gap: 4px; }

.kpi-row + .kpi-row { margin-top: 12px; }

/* ---------- responsive (after the base rules, so these win) ------------- */

@media (max-width: 1250px) {
  .chart-grid.chart-grid-three { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filter-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 1120px) {
  .chart-grid,
  .chart-grid.chart-grid-even,
  .chart-grid.chart-grid-three { grid-template-columns: 1fr; }
}
@media (max-width: 820px) {
  .filter-grid { grid-template-columns: repeat(2, 1fr); }
  .filter-footer { align-items: stretch; flex-direction: column; }
}
"""
