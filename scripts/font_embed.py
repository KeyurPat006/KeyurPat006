"""Base64-embed woff2 font subsets as @font-face rules.

An external font URL cannot work in a profile-README SVG: the file loads
through an <img> tag, and browsers refuse subresource fetches for image
documents. A data-URI @font-face does work, so every SVG carries its own
(small, per-role) subset inline.
"""
import base64
import os

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")


def _data_uri(woff2_name: str) -> str:
    path = os.path.join(_FONTS_DIR, woff2_name)
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:font/woff2;base64,{b64}"


def font_face_css(family: str, faces: list[tuple[str, str, str]]) -> str:
    """faces: list of (weight, style, woff2_filename)."""
    rules = []
    for weight, style, fname in faces:
        rules.append(
            f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"font-style:{style};src:url({_data_uri(fname)}) format('woff2');}}"
        )
    return "<defs><style>" + "".join(rules) + "</style></defs>"
