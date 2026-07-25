"""Stylesheet for the dashboard.

Light and dark are two selected token sets from the same ramps. The dark values
are declared under both the OS media query and the explicit theme class, so the
in-app toggle wins in either direction.
"""

STYLESHEET = """
.viz-root {
  color-scheme: light;
  --surface-1: #fcfcfb;
  --page: #f9f9f7;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --muted: #898781;
  --grid: #e1e0d9;
  --border: rgba(11,11,11,0.10);
  --accent: #2a78d6;
  --warning: #fab219;
}
@media (prefers-color-scheme: dark) {
  .viz-root:not(.theme-light) {
    color-scheme: dark;
    --surface-1: #1a1a19;
    --page: #0d0d0d;
    --text-primary: #ffffff;
    --text-secondary: #c3c2b7;
    --muted: #898781;
    --grid: #2c2c2a;
    --border: rgba(255,255,255,0.10);
    --accent: #3987e5;
  }
}
.viz-root.theme-dark {
  color-scheme: dark;
  --surface-1: #1a1a19;
  --page: #0d0d0d;
  --text-primary: #ffffff;
  --text-secondary: #c3c2b7;
  --muted: #898781;
  --grid: #2c2c2a;
  --border: rgba(255,255,255,0.10);
  --accent: #3987e5;
}

body { margin: 0; background: var(--page); }
.viz-root {
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  background: var(--page);
  color: var(--text-primary);
  min-height: 100vh;
  padding: 20px 24px 48px;
  box-sizing: border-box;
}

.app-header { display: flex; justify-content: space-between; align-items: flex-start; }
.app-title { margin: 0; font-size: 22px; font-weight: 600; letter-spacing: -0.01em; }
.app-subtitle { margin: 2px 0 0; font-size: 13px; color: var(--text-secondary); }

.banner {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  margin: 16px 0 20px; padding: 10px 14px;
  border: 1px solid var(--border); border-left: 3px solid var(--warning);
  border-radius: 8px; background: var(--surface-1);
}
.banner-tag {
  font-size: 11px; font-weight: 700; letter-spacing: 0.06em;
  padding: 3px 8px; border-radius: 4px;
  background: var(--warning); color: #0b0b0b;
}
.banner-text { font-size: 12.5px; color: var(--text-secondary); }

.kpi-row {
  display: grid; gap: 12px; margin-bottom: 20px;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
}
.kpi-card {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px; display: flex; flex-direction: column; gap: 3px;
}
.kpi-label { font-size: 12px; color: var(--text-secondary); }
.kpi-value { font-size: 26px; font-weight: 600; color: var(--text-primary); line-height: 1.15; }
.kpi-detail { font-size: 12px; color: var(--muted); }
.kpi-note { font-size: 11px; color: var(--muted); font-style: italic; margin-top: 4px; }

.filter-bar {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px; margin-bottom: 12px;
}
.filter-grid {
  display: grid; gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}
.filter-label {
  display: block; font-size: 11px; color: var(--text-secondary);
  margin-bottom: 4px; font-weight: 500;
}
.filter-actions { display: flex; gap: 8px; margin-top: 12px; }
.ghost-button {
  font-family: inherit; font-size: 12px; padding: 7px 14px;
  border: 1px solid var(--border); border-radius: 6px;
  background: transparent; color: var(--text-primary); cursor: pointer;
}
.ghost-button:hover { background: var(--grid); }

.result-count { font-size: 12.5px; color: var(--text-secondary); margin: 0 0 16px 2px; }

.chart-grid {
  display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
}
.card {
  background: var(--surface-1); border: 1px solid var(--border);
  border-radius: 10px; padding: 14px 16px;
}
.card-full { grid-column: 1 / -1; margin-top: 12px; }
.card-title { margin: 0; font-size: 14px; font-weight: 600; }
.card-subtitle { margin: 3px 0 8px; font-size: 12px; color: var(--muted); }
.card-toggle { font-size: 12px; color: var(--text-secondary); margin-bottom: 6px; }
.card-toggle label { margin-right: 14px; }

.limitations { margin: 6px 0 0; padding-left: 18px; }
.limitations li { font-size: 12.5px; color: var(--text-secondary); margin-bottom: 6px; }

.Select-control, .Select-menu-outer { font-size: 12px; }
"""
