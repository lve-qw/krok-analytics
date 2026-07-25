"""Stylesheet for the dashboard.

The page is dressed as an instrument console. Three decisions carry it.

**One signal colour.** Amber marks the thing the reader is meant to act on and
nothing else. Measurements are steel blue, structure is hairline. A page where
every panel shouts is a page where nothing gets read first.

**Panels, not cards.** Boxes with borders and shadows turn a dashboard into a
tile grid where every block claims the same importance. Here a panel is a
surface separated from its neighbour by the page showing through, and it
answers to the pointer with a single amber rule on top.

**The rail is the signature.** A hairline with a comb of ticks runs under the
header and returns as the divider of every section. It draws itself once on
load, and under the header it carries an amber mark at the headline value, so
the page opens by measuring itself.

One source of truth for the theme: it is a class on `#viz-root`, written by the
toggle callback and read by the CSS. There is no `prefers-color-scheme` rule —
a media query cannot see the store, and when the two disagreed the page went
dark while Plotly kept drawing on white paper.
"""

#: Loaded from the CDN in ``app.index_string``. The fallbacks are system faces,
#: so a laptop with no network still renders a coherent page.
FONTS = (
    "https://fonts.googleapis.com/css2"
    "?family=Unbounded:wght@400;500;600"
    "&family=Golos+Text:wght@400;500;600"
    "&family=JetBrains+Mono:wght@400;500"
    "&display=swap"
)

DARK_TOKENS = """
  color-scheme: dark;
  --page: #080D12;
  --surface: #0F1720;
  --raised: #17222E;
  --text-primary: #E9EFF5;
  --text-secondary: #9DACBC;
  --muted: #6C7C8D;
  --hairline: rgba(233,239,245,0.10);
  --hairline-strong: rgba(233,239,245,0.20);
  --signal: #F2A93B;
  --signal-soft: rgba(242,169,59,0.14);
  --data: #6FA5FF;
  --data-alt: #4FC4A8;
  --alarm: #F0655A;
  --dim: #25313D;
"""

LIGHT_TOKENS = """
  color-scheme: light;
  --page: #E7EBEF;
  --surface: #F8FAFC;
  --raised: #EDF1F5;
  --text-primary: #0D1620;
  --text-secondary: #4A5A67;
  --muted: #77879A;
  --hairline: rgba(13,22,32,0.12);
  --hairline-strong: rgba(13,22,32,0.26);
  --signal: #B4700F;
  --signal-soft: rgba(180,112,15,0.12);
  --data: #2B5FD9;
  --data-alt: #12796A;
  --alarm: #C4392E;
  --dim: #CBD5DF;
"""

# Declared twice from one source: on `.viz-root` they are guaranteed, and on
# `body:has(...)` they also reach the dropdown menus, which Dash renders in a
# portal outside the root and which would otherwise fall back to their built-in
# light colours on a dark page.
_TOKENS = f"""
.viz-root.theme-dark {{{DARK_TOKENS}}}
.viz-root.theme-light {{{LIGHT_TOKENS}}}
body:has(.viz-root.theme-dark) {{{DARK_TOKENS}}}
body:has(.viz-root.theme-light) {{{LIGHT_TOKENS}}}
"""

STYLESHEET = _TOKENS + """
/* ---------- foundation ------------------------------------------------- */

body { margin: 0; background: var(--page); }
.viz-root {
  --display: "Unbounded", "Segoe UI Variable", system-ui, sans-serif;
  --body: "Golos Text", system-ui, -apple-system, sans-serif;
  --mono: "JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace;
  font-family: var(--body);
  background: var(--page);
  color: var(--text-primary);
  min-height: 100vh;
  width: min(1640px, 100%);
  margin: 0 auto;
  padding: 34px 40px 72px;
  box-sizing: border-box;
  font-size: 14px;
  line-height: 1.5;
}
.viz-root * { box-sizing: border-box; }
:focus-visible { outline: 2px solid var(--signal); outline-offset: 3px; }

/* Every micro-label on the page is mono, uppercase and tracked. That single
   device says "instrumentation", and it is why no label needs a box around it. */
.eyebrow, .section-kicker, .kpi-source, .stat-label, .header-meta-label,
.banner-tag, .card-toggle, .filter-label, .flag-check, .hero-tag {
  font-family: var(--mono);
  text-transform: uppercase;
  letter-spacing: 0.13em;
}

/* ---------- header ----------------------------------------------------- */

.app-header {
  display: flex; justify-content: space-between; align-items: flex-end;
  gap: 28px; flex-wrap: wrap; padding-bottom: 22px;
}
.brand-block { display: flex; flex-direction: column; align-items: flex-start; }
.brand-mark {
  font-family: var(--mono);
  color: var(--signal);
  font-size: 10.5px; font-weight: 500; letter-spacing: 0.22em;
  text-transform: uppercase; margin-bottom: 14px;
}
.app-title {
  margin: 0; font-family: var(--display);
  font-size: clamp(30px, 3.1vw, 46px);
  font-weight: 500; letter-spacing: -0.03em; line-height: 1.02;
}
.app-subtitle { margin: 14px 0 0; max-width: 60ch; font-size: 13.5px; color: var(--text-secondary); }
.header-actions { display: flex; gap: 20px; align-items: center; }
.header-meta { display: flex; flex-direction: column; align-items: flex-end; gap: 5px; }
.header-meta-label { font-size: 9px; color: var(--muted); }
.header-meta strong { font-family: var(--mono); font-size: 15px; font-weight: 500; }

/* ---------- the rail: signature ---------------------------------------- */

/* A measurement scale, not a divider: a hairline, a comb of ticks, and one
   amber mark that sits where the current headline value falls. Pure CSS, so
   the page carries no drawing library for one element. */
.rail { position: relative; height: 14px; margin-top: 4px; }
.rail::before {
  content: ""; position: absolute; inset: 0 0 auto 0; height: 1px;
  background: var(--hairline-strong); transform-origin: left center;
  animation: rail-draw 900ms cubic-bezier(0.22, 1, 0.36, 1) both;
}
.rail::after {
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 6px;
  background-image: repeating-linear-gradient(
    to right, var(--hairline-strong) 0 1px, transparent 1px 44px);
  opacity: 0; animation: tick-in 500ms ease 620ms both;
}
.rail-mark {
  position: absolute; top: 0; width: 2px; height: 13px;
  background: var(--signal); transform: translateX(-1px);
  opacity: 0; animation: tick-in 420ms ease 900ms both;
}
.rail-mark::after {
  content: attr(data-label);
  position: absolute; top: 16px; left: 0; transform: translateX(-50%);
  font-family: var(--mono); font-size: 9px; letter-spacing: 0.1em;
  color: var(--signal); white-space: nowrap;
}
@keyframes rail-draw { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes tick-in { to { opacity: 1; } }
.section-rail { margin-top: 46px; }

/* ---------- hero ------------------------------------------------------- */

.hero { padding: 28px 0 6px; }
.hero-body {
  display: grid; grid-template-columns: minmax(300px, 0.8fr) minmax(0, 1.2fr);
  gap: 48px; align-items: end;
}
.hero-tag { display: block; font-size: 9px; color: var(--signal); margin-bottom: 13px; }
.hero-line {
  margin: 0; font-family: var(--display);
  font-size: clamp(18px, 1.9vw, 26px);
  font-weight: 400; line-height: 1.3; letter-spacing: -0.025em; max-width: 30ch;
}
.hero-line b { font-weight: 600; color: var(--signal); }

/* The spend bar is the thesis of the page, so it is drawn in the document
   rather than by Plotly: full width, no axis, no legend, parts named on the
   mark itself. It grows from zero once — the page reading its own measurement. */
.spend { display: flex; flex-direction: column; gap: 14px; }
.spend-bar { display: flex; width: 100%; height: 52px; gap: 3px; }
.spend-part {
  min-width: 3px; border-radius: 1px; transform-origin: left center;
  animation: spend-grow 900ms cubic-bezier(0.22, 1, 0.36, 1) 200ms both;
}
.spend-part-0 { background: var(--signal); }
.spend-part-1 { background: var(--data); }
.spend-part-2 { background: var(--dim); }
@keyframes spend-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
.spend-legend { display: flex; gap: 30px; flex-wrap: wrap; }
.spend-item { display: flex; flex-direction: column; gap: 3px; }
.spend-item .key { font-family: var(--mono); font-size: 9px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); }
.spend-item .val { font-family: var(--display); font-size: 19px; font-weight: 500; letter-spacing: -0.03em; }
.spend-item .sub { font-family: var(--mono); font-size: 11px; color: var(--text-secondary); }
.spend-item-0 .val { color: var(--signal); }

/* ---------- warnings --------------------------------------------------- */

.provenance {
  display: flex; align-items: flex-start; gap: 16px; flex-wrap: wrap;
  margin: 28px 0 0; padding: 13px 16px;
  background: var(--surface); border-left: 2px solid var(--signal);
}
.banner-tag {
  font-size: 8.5px; font-weight: 500; padding: 5px 9px;
  background: var(--signal-soft); color: var(--signal); white-space: nowrap;
}
.provenance-notes { display: flex; flex-direction: column; gap: 5px; }
.provenance-text { font-size: 12.5px; color: var(--text-secondary); }

/* ---------- filters ---------------------------------------------------- */

.filter-bar { margin: 28px 0 0; padding: 18px 20px; background: var(--surface); }
.filter-grid { display: grid; gap: 14px 18px; grid-template-columns: repeat(5, 1fr); }
.filter-label { display: block; font-size: 8.5px; color: var(--muted); margin-bottom: 7px; }
.filter-footer {
  display: flex; align-items: center; justify-content: space-between;
  gap: 18px; flex-wrap: wrap; margin-top: 16px;
  padding-top: 14px; border-top: 1px solid var(--hairline);
}
.flag-check { display: flex; gap: 8px 22px; flex-wrap: wrap; font-size: 9px; color: var(--text-secondary); }
.flag-check label { display: inline-flex; align-items: center; gap: 7px; cursor: pointer; }
.flag-check input { accent-color: var(--signal); margin: 0; }
.filter-actions { display: flex; gap: 10px; align-items: center; }
.ghost-button {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em;
  text-transform: uppercase; padding: 9px 15px; border-radius: 0;
  border: 1px solid var(--hairline-strong);
  background: transparent; color: var(--text-primary); cursor: pointer;
  transition: border-color 140ms ease, color 140ms ease;
}
.ghost-button:hover { border-color: var(--signal); color: var(--signal); }

/* ---------- chips ------------------------------------------------------ */

.chip-row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin: 14px 0 0; min-height: 22px; }
.chip-list { display: contents; }
.chip, .chip-none { font-family: var(--mono); font-size: 10.5px; color: var(--text-secondary); }
.chip { padding: 5px 10px; background: var(--surface); border: 1px solid var(--hairline); }
.chip b { color: var(--text-primary); font-weight: 500; }
.chip-selection {
  font-family: var(--mono); font-size: 10.5px;
  display: inline-flex; align-items: center; gap: 10px;
  padding: 5px 8px 5px 11px; cursor: pointer; border-radius: 0;
  background: var(--signal-soft); border: 1px solid var(--signal); color: var(--text-primary);
}
.chip-selection:hover { background: var(--signal); color: var(--page); }
.chip-selection .chip-x { border-left: 1px solid var(--hairline-strong); padding-left: 9px; opacity: 0.75; }
.result-count { font-family: var(--mono); font-size: 11px; color: var(--muted); margin: 12px 0 0; }

/* ---------- gauges (KPI) ----------------------------------------------- */

/* No cards: the row is one surface cut by hairlines, the way a bank of
   instruments shares a single face. */
#kpi-container { margin-top: 28px; }
.kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); background: var(--surface); margin: 0; }
.kpi-row + .kpi-row { border-top: 1px solid var(--hairline); }
.kpi-card {
  padding: 20px 22px 22px; border-right: 1px solid var(--hairline);
  display: flex; flex-direction: column; gap: 3px; min-width: 0;
  transition: background 160ms ease;
}
.kpi-card:last-child { border-right: none; }
.kpi-card:hover { background: var(--raised); }
.kpi-head { display: flex; align-items: flex-start; gap: 8px; justify-content: space-between; }
.kpi-identity { display: flex; flex-direction: column; gap: 9px; }
.kpi-source { font-size: 8px; color: var(--signal); }
.kpi-label { font-size: 12.5px; color: var(--text-secondary); }
.kpi-value {
  font-family: var(--display); font-size: clamp(27px, 2.4vw, 37px);
  font-weight: 500; line-height: 1.06; letter-spacing: -0.05em;
  margin-top: 12px; font-variant-numeric: tabular-nums;
}
.kpi-unit {
  font-family: var(--mono); font-size: 10px; color: var(--muted);
  margin-left: 7px; letter-spacing: 0.08em; text-transform: uppercase;
}
.kpi-detail { font-size: 11.5px; color: var(--muted); margin-top: 3px; }

/* ---------- sections and panels ---------------------------------------- */

.section-heading { display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap; margin: 16px 0 16px; }
.section-kicker { font-size: 8.5px; color: var(--signal); }
.section-title { margin: 0; font-family: var(--display); font-size: 21px; font-weight: 500; letter-spacing: -0.035em; }

/* The 1px gap is the page showing between panels: it makes the grid read as one
   instrument face instead of a set of floating tiles. */
.chart-grid {
  display: grid; gap: 1px; background: var(--hairline);
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 0.85fr);
}
.chart-grid.chart-grid-even { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.chart-grid.chart-grid-three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.card {
  background: var(--surface); padding: 20px 22px 14px; min-width: 0;
  border-top: 2px solid transparent;
  transition: border-color 160ms ease, background 160ms ease;
}
.card:hover { border-top-color: var(--signal); }
.card-full { grid-column: 1 / -1; }
.card-head { display: flex; align-items: center; gap: 8px; }
.card-title { margin: 0; font-family: var(--display); font-size: 14.5px; font-weight: 500; letter-spacing: -0.02em; }
.card-subtitle { margin: 6px 0 10px; font-size: 12px; color: var(--muted); line-height: 1.45; max-width: 62ch; }
.card-toggle { display: inline-flex; gap: 2px; margin: 2px 0 8px; font-size: 9px; color: var(--text-secondary); }
.card-toggle label { padding: 5px 10px; cursor: pointer; border: 1px solid var(--hairline); }
.card-toggle input { margin-right: 6px; accent-color: var(--signal); }

/* ---------- supporting numbers ----------------------------------------- */

.stat-strip {
  display: flex; flex-wrap: wrap; gap: 10px 28px;
  margin: 6px 0 12px; padding-top: 12px; border-top: 1px solid var(--hairline);
}
.stat { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.stat-value {
  font-family: var(--display); font-size: 16px; font-weight: 500;
  letter-spacing: -0.03em; font-variant-numeric: tabular-nums; color: var(--text-primary);
}
.stat-label { font-size: 8px; color: var(--muted); letter-spacing: 0.1em; }

/* ---------- info tooltip ----------------------------------------------- */

/* CSS-only: a demo laptop should not depend on a tooltip library, and the
   caveats have to be readable on a projector, which a native title= is not. */
.info {
  position: relative; flex: 0 0 auto;
  width: 15px; height: 15px; border-radius: 50%;
  border: 1px solid var(--hairline-strong); color: var(--muted);
  font-family: var(--mono); font-size: 9px; line-height: 13px; text-align: center;
  cursor: help; user-select: none;
}
.info:hover, .info:focus-visible { color: var(--signal); border-color: var(--signal); }
.info::after {
  content: attr(data-tip);
  /* Anchored by its LEFT edge so the box opens into the page: anchored right,
     the tip of a left-hand panel landed off the viewport. */
  position: absolute; top: calc(100% + 9px); left: -4px; right: auto; z-index: 40;
  width: max-content; max-width: min(340px, calc(100vw - 32px));
  padding: 11px 13px;
  background: var(--raised); color: var(--text-primary);
  border: 1px solid var(--hairline-strong);
  font-family: var(--body); font-size: 12px; line-height: 1.5;
  text-align: left; text-transform: none; letter-spacing: 0;
  white-space: pre-line;
  opacity: 0; visibility: hidden; transition: opacity 120ms ease;
}
.info--end::after { left: auto; right: -4px; }
.info:hover::after, .info:focus-visible::after { opacity: 1; visibility: visible; }

/* ---------- table ------------------------------------------------------ */

/* Dash paints the table with its own colours, so these rules put the scrollers
   and the sticky header back on the tokens. The cell colours themselves are
   set as var() in the DataTable style props. */
.records .dash-spreadsheet-container,
.records .dash-spreadsheet-inner,
.records .dash-freeze-top { background: var(--surface) !important; }
.records .dash-cell-value { color: var(--text-primary) !important; }
.records .dash-table-container .previous-next-container {
  color: var(--text-secondary); font-family: var(--mono); font-size: 11px; padding-top: 10px;
}
.records .dash-table-container .previous-next-container .page-number .current-page,
.records input.current-page {
  color: var(--text-primary) !important; background: var(--raised) !important;
  border-bottom-color: var(--hairline-strong) !important;
}
.records .dash-table-container .previous-next-container button { color: var(--muted) !important; }
.records .column-header--sort svg { fill: var(--muted); }

/* ---------- dropdown internals ----------------------------------------- */

/* Dash draws its dropdown with built-in light colours. Left alone, the selected
   value came out near-black on the dark surface and the control read as an
   empty box — the same failure as the table, in another component. */
.dash-dropdown {
  background: var(--raised) !important;
  border-color: var(--hairline) !important;
  border-radius: 0 !important;
  color: var(--text-primary) !important;
  font-family: var(--body) !important;
  font-size: 12.5px !important;
}
.dash-dropdown:hover { border-color: var(--hairline-strong) !important; }
.dash-dropdown[data-state="open"] { border-color: var(--signal) !important; }
.dash-dropdown-value, .dash-dropdown-value-item { color: var(--text-primary) !important; }
.dash-dropdown-placeholder { color: var(--muted) !important; }
.dash-dropdown-trigger-icon { color: var(--muted) !important; }
.dash-dropdown-content, .dash-dropdown-options {
  background: var(--raised) !important;
  border-color: var(--hairline-strong) !important;
  border-radius: 0 !important;
  color: var(--text-primary) !important;
  font-size: 12.5px !important;
}
.dash-options-list-option { color: var(--text-primary) !important; }
.dash-options-list-option:hover,
.dash-options-list-option[data-highlighted] { background: var(--surface) !important; }
.dash-options-list-option[aria-selected="true"] { background: var(--signal-soft) !important; }
.dash-dropdown-search-container { background: var(--raised) !important; }
.dash-dropdown-search {
  background: var(--surface) !important; color: var(--text-primary) !important;
  border-color: var(--hairline) !important;
}
.dash-dropdown-search::placeholder { color: var(--muted) !important; }
.dash-dropdown-search-icon { color: var(--muted) !important; }
.dash-dropdown-actions { background: var(--raised) !important; }
.dash-dropdown-action-button { color: var(--signal) !important; }
.dash-options-list-option-text { color: var(--text-primary) !important; }

/* ---------- load sequence ---------------------------------------------- */

/* One orchestrated entrance rather than scattered effects: the rail measures
   itself, the gauges rise in order, the panels settle behind them. */
.kpi-card, .card { animation: settle 520ms cubic-bezier(0.22, 1, 0.36, 1) both; }
.kpi-card:nth-child(1) { animation-delay: 140ms; }
.kpi-card:nth-child(2) { animation-delay: 200ms; }
.kpi-card:nth-child(3) { animation-delay: 260ms; }
.kpi-card:nth-child(4) { animation-delay: 320ms; }
.metric-section .card:nth-child(1) { animation-delay: 60ms; }
.metric-section .card:nth-child(2) { animation-delay: 120ms; }
.metric-section .card:nth-child(3) { animation-delay: 180ms; }
@keyframes settle { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }

/* ---------- responsive -------------------------------------------------- */

/* Desktop presentation is the target; these steps keep 1280 and 1024 readable
   rather than pretending the page is a phone. */
@media (max-width: 1400px) {
  .filter-grid { grid-template-columns: repeat(3, 1fr); }
  .hero-body { grid-template-columns: 1fr; gap: 28px; align-items: start; }
}
@media (max-width: 1250px) {
  .chart-grid.chart-grid-three { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 1120px) {
  .viz-root { padding: 22px 18px 48px; }
  .chart-grid,
  .chart-grid.chart-grid-even,
  .chart-grid.chart-grid-three { grid-template-columns: 1fr; }
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
  .kpi-card:nth-child(2) { border-right: none; }
}
@media (max-width: 820px) {
  .filter-grid { grid-template-columns: repeat(2, 1fr); }
  .filter-footer { align-items: stretch; flex-direction: column; }
  .kpi-row { grid-template-columns: 1fr; }
  .kpi-card { border-right: none; border-bottom: 1px solid var(--hairline); }
}

@media (prefers-reduced-motion: reduce) {
  .viz-root *, .viz-root *::after { transition: none !important; animation: none !important; }
  .rail::before { transform: none; }
  .rail::after, .rail-mark { opacity: 1; }
  .spend-part { transform: none; }
  .kpi-card, .card { opacity: 1; transform: none; }
}
"""
