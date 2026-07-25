"""Colour tokens for the dashboard.

The page is an instrument console, not a report. A dark measured surface, one
signal colour, and everything else in steel. Amber is the signal: it belongs to
the same family as the КРОК copper mark, and unlike phosphor green it does not
turn the page into a hacker prop. Steel blue carries the measurements, so a
bright element always means "look here" rather than "this is series two".

Light is the same instrument printed on paper: identical structure, ink instead
of glow, the amber pulled down to hold 4.5:1 on a pale surface.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    #: The background a panel sits on.
    page: str
    #: Panel surface.
    surface: str
    #: A panel lifted above the surface: filter bar, table header, hover state.
    raised: str
    text_primary: str
    text_secondary: str
    muted: str
    grid: str
    axis: str
    border: str
    #: The one accent, reserved for the mark that carries the current answer.
    signal: str
    signal_soft: str
    #: Data marks in order of use.
    series: tuple[str, str, str]
    sequential: tuple[str, ...]
    good: str
    warning: str
    critical: str
    #: Marks outside the current selection. Selection is a state, so it
    #: de-emphasises everything else rather than recolouring the chosen mark.
    dim: str
    #: Reference lines: median splits, thresholds. Recessive on purpose.
    guide: str


DARK = Theme(
    name="dark",
    page="#080D12",
    surface="#0F1720",
    raised="#17222E",
    text_primary="#E9EFF5",
    text_secondary="#9DACBC",
    muted="#6C7C8D",
    grid="rgba(233,239,245,0.07)",
    axis="rgba(233,239,245,0.14)",
    border="rgba(233,239,245,0.10)",
    signal="#F2A93B",
    signal_soft="rgba(242,169,59,0.14)",
    series=("#6FA5FF", "#F2A93B", "#4FC4A8"),
    sequential=("#12325F", "#17427D", "#1D549C", "#2668BE", "#3D82DA", "#6FA5FF", "#A6C8FF"),
    good="#4FC4A8",
    warning="#F2A93B",
    critical="#F0655A",
    dim="#25313D",
    guide="#41525F",
)

LIGHT = Theme(
    name="light",
    page="#E7EBEF",
    surface="#F8FAFC",
    raised="#EDF1F5",
    text_primary="#0D1620",
    text_secondary="#4A5A67",
    muted="#77879A",
    grid="rgba(13,22,32,0.08)",
    axis="rgba(13,22,32,0.16)",
    border="rgba(13,22,32,0.12)",
    signal="#B4700F",
    signal_soft="rgba(180,112,15,0.12)",
    series=("#2B5FD9", "#B4700F", "#12796A"),
    sequential=("#D6E4FB", "#AFCBF6", "#87B0EE", "#5F94E4", "#3E78D6", "#2B5FD9", "#1C43A0"),
    good="#12796A",
    warning="#B4700F",
    critical="#C4392E",
    dim="#CBD5DF",
    guide="#9CAAB8",
)

THEMES = {"dark": DARK, "light": LIGHT}


def get_theme(name: str | None) -> Theme:
    return THEMES.get((name or "dark").lower(), DARK)
