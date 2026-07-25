"""Colour tokens for the dashboard.

Light and dark are two selected sets of steps from the same hues, not an
automatic inversion. The three categorical slots used here were validated for
both surfaces (adjacent CVD dE 9.2 light / 9.4 dark, normal-vision 27.6 / 26.5).

Light-mode aqua sits below 3:1 against the light surface, so every chart that
uses it also carries direct labels or is backed by the drill-down table.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    surface: str
    page: str
    text_primary: str
    text_secondary: str
    muted: str
    grid: str
    axis: str
    border: str
    series: tuple[str, str, str]
    sequential: tuple[str, ...]
    good: str
    warning: str
    critical: str
    #: Colour for marks that are outside the current selection. Selection is a
    #: state, not an identity, so it is encoded by de-emphasising everything
    #: else rather than by giving the chosen mark a new hue.
    dim: str
    #: Reference lines (median splits, the 80% Pareto mark). Recessive on
    #: purpose: they orient the reader without competing with the data.
    guide: str


LIGHT = Theme(
    name="light",
    surface="#f9fafb",
    page="#f1f3f5",
    text_primary="#121820",
    text_secondary="#4b5663",
    muted="#7b8794",
    grid="#dce2e8",
    axis="#b9c2cc",
    border="rgba(18,24,32,0.11)",
    series=("#2557c7", "#a8663d", "#1f8c72"),
    sequential=("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#256abf", "#184f95"),
    good="#0ca30c",
    warning="#fab219",
    critical="#d03b3b",
    dim="#d4dae0",
    guide="#aeb8c2",
)

DARK = Theme(
    name="dark",
    surface="#171e26",
    page="#10151b",
    text_primary="#f2f5f7",
    text_secondary="#b8c1cb",
    muted="#7f8c99",
    grid="#2b3743",
    axis="#354351",
    border="rgba(242,245,247,0.10)",
    series=("#6d91f0", "#c47a4c", "#49aa8f"),
    sequential=("#0d366b", "#104281", "#184f95", "#256abf", "#2a78d6", "#3987e5", "#6da7ec"),
    good="#0ca30c",
    warning="#fab219",
    critical="#d03b3b",
    dim="#33404c",
    guide="#526170",
)

THEMES = {"light": LIGHT, "dark": DARK}


def get_theme(name: str | None) -> Theme:
    return THEMES.get((name or "light").lower(), LIGHT)
