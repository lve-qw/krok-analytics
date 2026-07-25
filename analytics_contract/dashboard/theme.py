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


LIGHT = Theme(
    name="light",
    surface="#fcfcfb",
    page="#f9f9f7",
    text_primary="#0b0b0b",
    text_secondary="#52514e",
    muted="#898781",
    grid="#e1e0d9",
    axis="#c3c2b7",
    border="rgba(11,11,11,0.10)",
    series=("#2a78d6", "#eb6834", "#1baf7a"),
    sequential=("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#256abf", "#184f95"),
    good="#0ca30c",
    warning="#fab219",
    critical="#d03b3b",
)

DARK = Theme(
    name="dark",
    surface="#1a1a19",
    page="#0d0d0d",
    text_primary="#ffffff",
    text_secondary="#c3c2b7",
    muted="#898781",
    grid="#2c2c2a",
    axis="#383835",
    border="rgba(255,255,255,0.10)",
    series=("#3987e5", "#d95926", "#199e70"),
    sequential=("#0d366b", "#104281", "#184f95", "#256abf", "#2a78d6", "#3987e5", "#6da7ec"),
    good="#0ca30c",
    warning="#fab219",
    critical="#d03b3b",
)

THEMES = {"light": LIGHT, "dark": DARK}


def get_theme(name: str | None) -> Theme:
    return THEMES.get((name or "light").lower(), LIGHT)
