"""Shared visual language for the generated SVGs: one font stack, one ink color, one ramp."""
from __future__ import annotations

from font_embed import font_face_css

FONT_STACK = (
    "'JetBrains Mono', ui-monospace, 'Liberation Mono', 'DejaVu Sans Mono', "
    "'Noto Sans Mono', monospace"
)
INK = "#1f2328"
DIM = "#6b7280"
RULE = "#d0d7de"
RAMP = " .`:-=+*cs#%@"

# name -> [(weight, style, woff2 filename), ...]
FONT_SUBSETS = {
    "ramp": [("400", "normal", "ramp.woff2")],
    "basic": [("400", "normal", "basic-regular.woff2"), ("700", "normal", "basic-bold.woff2")],
    "headings": [("400", "normal", "headings.woff2")],
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_open(width: float, height: float, font_subset: str | None = None) -> str:
    out = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} {height:.2f}" '
        f'width="{width:.2f}" height="{height:.2f}" font-family="{FONT_STACK}">'
    )
    if font_subset:
        out += font_face_css("JetBrains Mono", FONT_SUBSETS[font_subset])
    out += f'<rect x="0" y="0" width="{width:.2f}" height="{height:.2f}" fill="white"/>'
    return out


def svg_close() -> str:
    return "</svg>"


def ramp_index(value: float, vmax: float) -> int:
    """Map value in [0, vmax] to a RAMP character index, 0 = blank."""
    if vmax <= 0 or value <= 0:
        return 0
    import math

    frac = min(1.0, math.log1p(value) / math.log1p(vmax))
    return 1 + round(frac * (len(RAMP) - 2))
