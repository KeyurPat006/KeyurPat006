#!/usr/bin/env python3
"""ASCII portrait generator: photo -> cutout -> tone curve -> character grid -> animated SVG."""
import argparse
import io
import sys

import cv2
import numpy as np
from PIL import Image

from font_embed import font_face_css

RAMP = " .`:-=+*cs#%@"

FONT_SIZE = 12.9
CHAR_W = round(FONT_SIZE * 0.600, 3)   # 7.74 — matches Liberation/DejaVu/Noto Sans Mono advance
LINE_H = round(FONT_SIZE * 1.250, 3)   # 16.125 — 0.6/1.25 = 0.48 aspect factor


def remove_background(img_rgb: np.ndarray) -> np.ndarray:
    from rembg import remove

    buf = io.BytesIO()
    Image.fromarray(img_rgb).save(buf, format="PNG")
    cut = remove(buf.getvalue())
    cutout = Image.open(io.BytesIO(cut)).convert("RGBA")

    white_bg = Image.new("RGBA", cutout.size, (255, 255, 255, 255))
    composited = Image.alpha_composite(white_bg, cutout).convert("RGB")

    alpha = np.array(cutout)[:, :, 3]
    return np.array(composited), alpha


def crop_to_subject(rgb: np.ndarray, alpha: np.ndarray, pad_frac: float = 0.06) -> np.ndarray:
    ys, xs = np.where(alpha > 10)
    if len(xs) == 0:
        return rgb
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    h, w = rgb.shape[:2]
    pad_x = int((x1 - x0) * pad_frac)
    pad_y = int((y1 - y0) * pad_frac)
    x0 = max(0, x0 - pad_x)
    x1 = min(w, x1 + pad_x)
    y0 = max(0, y0 - pad_y)
    y1 = min(h, y1 + pad_y)
    return rgb[y0:y1, x0:x1]


def tone_map(gray: np.ndarray, alpha: np.ndarray, gamma: float, clahe_clip: float) -> np.ndarray:
    smoothed = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    # Stretch contrast using the foreground's own range, not the whole
    # canvas (which includes the forced-white background at 255 and would
    # otherwise skew any global normalization).
    fg = smoothed[alpha > 10]
    lo, hi = np.percentile(fg, [2, 98])
    stretched = np.clip((smoothed.astype(np.float32) - lo) / max(hi - lo, 1) * 255.0, 0, 255).astype(np.uint8)

    clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8, 8))
    contrasted = clahe.apply(stretched)
    curved = (np.power(contrasted.astype(np.float32) / 255.0, gamma) * 255.0).astype(np.uint8)
    return curved


def to_ascii_grid(gray: np.ndarray, cols: int) -> list[str]:
    h, w = gray.shape
    rows = max(1, round(cols * (h / w) * 0.48))
    small = cv2.resize(gray, (cols, rows), interpolation=cv2.INTER_AREA)
    n = len(RAMP) - 1
    idx = np.round((255 - small.astype(np.float32)) / 255.0 * n).astype(np.int32)
    idx = np.clip(idx, 0, n)
    return ["".join(RAMP[i] for i in row) for row in idx]


def build_svg(rows: list[str], fill: str = "var(--ink)", stagger: float = 0.09, dur: float = 0.5) -> str:
    cols = max(len(r) for r in rows)
    width = cols * CHAR_W
    height = len(rows) * LINE_H

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} {height:.2f}" '
        f'width="{width:.2f}" height="{height:.2f}" font-family="\'JetBrains Mono\', ui-monospace, '
        f'\'Liberation Mono\', \'DejaVu Sans Mono\', \'Noto Sans Mono\', monospace">'
    )
    parts.append(font_face_css("JetBrains Mono", [("400", "normal", "ramp.woff2")]))
    parts.append(
        '<style>:root{--ink:#1f2328;}'
        '@media (prefers-color-scheme: dark){:root{--ink:#e6edf3;}}'
        f'text{{font-size:{FONT_SIZE}px; fill:{fill};}}</style>'
    )

    for i, row in enumerate(rows):
        row_w = len(row) * CHAR_W
        y_top = i * LINE_H
        y_baseline = y_top + LINE_H * 0.82
        begin = round(i * stagger, 3)
        clip_id = f"clip{i}"
        parts.append(f'<clipPath id="{clip_id}">')
        parts.append(
            f'<rect x="0" y="{y_top:.2f}" width="0" height="{LINE_H:.2f}">'
            f'<animate attributeName="width" from="0" to="{row_w:.2f}" '
            f'begin="{begin}s" dur="{dur}s" fill="freeze" calcMode="spline" '
            f'keySplines="0.25 0.1 0.25 1" keyTimes="0;1"/>'
            f'</rect>'
        )
        parts.append('</clipPath>')
        safe = row.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        parts.append(f'<g clip-path="url(#{clip_id})">')
        parts.append(
            f'<text x="0" y="{y_baseline:.2f}" xml:space="preserve" '
            f'textLength="{row_w:.2f}" lengthAdjust="spacingAndGlyphs">{safe}</text>'
        )
        parts.append('</g>')
        cursor_y = y_top + LINE_H * 0.12
        cursor_h = LINE_H * 0.7
        parts.append(
            f'<rect x="0" y="{cursor_y:.2f}" width="{CHAR_W:.2f}" height="{cursor_h:.2f}" '
            f'fill="{fill}" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{begin}s"/>'
            f'<animate attributeName="x" from="0" to="{max(row_w - CHAR_W, 0):.2f}" '
            f'begin="{begin}s" dur="{dur}s" fill="freeze" calcMode="spline" '
            f'keySplines="0.25 0.1 0.25 1" keyTimes="0;1"/>'
            f'<animate attributeName="opacity" from="1" to="0" '
            f'begin="{begin + dur}s" dur="0.15s" fill="freeze"/>'
            f'</rect>'
        )

    parts.append('</svg>')
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", default="assets/portrait.svg")
    ap.add_argument("--cols", type=int, default=90)
    ap.add_argument("--debug-png", default=None, help="also dump the tone-mapped grayscale for inspection")
    ap.add_argument("--gamma", type=float, default=1.3, help="darkening curve exponent, tune per-photo")
    ap.add_argument("--clahe-clip", type=float, default=2.0, help="local contrast strength, tune per-photo")
    ap.add_argument("--cache-cutout", default=None, help="reuse a previously computed rembg cutout PNG (RGBA) to skip re-running the model")
    args = ap.parse_args()

    img = Image.open(args.input).convert("RGB")
    rgb = np.array(img)

    print(f"input: {rgb.shape[1]}x{rgb.shape[0]}", file=sys.stderr)
    if args.cache_cutout:
        import os
        if os.path.exists(args.cache_cutout):
            cutout = Image.open(args.cache_cutout).convert("RGBA")
        else:
            from rembg import remove
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            cutout = Image.open(io.BytesIO(remove(buf.getvalue()))).convert("RGBA")
            cutout.save(args.cache_cutout)
        white_bg = Image.new("RGBA", cutout.size, (255, 255, 255, 255))
        cut_rgb = np.array(Image.alpha_composite(white_bg, cutout).convert("RGB"))
        alpha = np.array(cutout)[:, :, 3]
    else:
        cut_rgb, alpha = remove_background(rgb)
    cropped = crop_to_subject(cut_rgb, alpha)
    crop_alpha = crop_to_subject(alpha, alpha)
    print(f"cropped to subject: {cropped.shape[1]}x{cropped.shape[0]}", file=sys.stderr)

    gray = cv2.cvtColor(cropped, cv2.COLOR_RGB2GRAY)
    toned = tone_map(gray, crop_alpha, args.gamma, args.clahe_clip)

    if args.debug_png:
        Image.fromarray(toned).save(args.debug_png)

    rows = to_ascii_grid(toned, args.cols)
    print(f"grid: {len(rows[0])} cols x {len(rows)} rows", file=sys.stderr)

    svg = build_svg(rows)
    with open(args.output, "w") as f:
        f.write(svg)
    print(f"wrote {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
