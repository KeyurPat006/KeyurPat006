#!/usr/bin/env python3
"""Section heading as an SVG image: the only way to put a custom typeface on
a README heading, since GitHub strips <style>, class, and inline <svg> text
styling from markdown. Costs the heading its anchor link in GitHub's outline;
the alt text carries the label for screen readers.
"""
import argparse
import os

from font_embed import font_face_css

INK = "var(--ink)"
RULE = "var(--rule)"
WIDTH = 696.6  # matches the portrait's natural viewBox width (90 cols * 7.74)
HEIGHT = 28.0
FONT_SIZE = 13.0


def build(label: str, headings_font: str) -> str:
    pad = 2.0
    text_w = len(label) * FONT_SIZE * 0.62  # rough advance for the heading weight
    rule_x = pad + text_w + 10
    y_baseline = HEIGHT * 0.68
    y_rule = HEIGHT * 0.55
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH:.2f} {HEIGHT:.2f}" '
        f'width="{WIDTH:.2f}" height="{HEIGHT:.2f}">'
        f'{font_face_css("JetBrains Mono", [("700", "normal", headings_font)])}'
        '<style>:root{--ink:#1f2328;--rule:#d0d7de;}'
        '@media (prefers-color-scheme: dark){:root{--ink:#e6edf3;--rule:#3d444d;}}</style>'
        f'<text x="{pad}" y="{y_baseline:.2f}" font-family="\'JetBrains Mono\', ui-monospace, monospace" '
        f'font-weight="700" font-size="{FONT_SIZE}" letter-spacing="0.5" fill="{INK}">{label}</text>'
        f'<line x1="{rule_x:.2f}" y1="{y_rule:.2f}" x2="{WIDTH - pad:.2f}" y2="{y_rule:.2f}" '
        f'stroke="{RULE}" stroke-width="1"/>'
        f'</svg>'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--font", default="headings.woff2")
    args = ap.parse_args()
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w") as f:
        f.write(build(args.label, args.font))


if __name__ == "__main__":
    main()
