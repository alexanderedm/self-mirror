#!/usr/bin/env python3
"""Generate SelfMirror icons — mirror-themed SVG + PNG."""

import base64
import os
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# SVG template — a stylized mirror / "對鏡問話" mark
# ---------------------------------------------------------------------------

MIRROR_SVG = textwrap.dedent("""\
    <svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{w}" viewBox="0 0 {w} {w}">
      <defs>
        <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" style="stop-color:#1e2a4a"/>
          <stop offset="100%" style="stop-color:#2d4a7a"/>
        </linearGradient>
        <linearGradient id="gloss" x1="0%" y1="0%" x2="40%" y2="100%">
          <stop offset="0%" style="stop-color:#7ab8ff;stop-opacity:0.6"/>
          <stop offset="60%" style="stop-color:#4a90d9;stop-opacity:0.2"/>
          <stop offset="100%" style="stop-color:#1e2a4a;stop-opacity:0"/>
        </linearGradient>
      </defs>

      <!-- background circle -->
      <circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#bg)"/>

      <!-- outer ring -->
      <circle cx="{cx}" cy="{cy}" r="{r2}" fill="none" stroke="#6ab0ff" stroke-width="{sw}"/>

      <!-- inner mirror surface -->
      <circle cx="{cx}" cy="{cy}" r="{r3}" fill="#1a2f60" stroke="#4a90d9" stroke-width="{sw2}"/>

      <!-- gloss highlight -->
      <ellipse cx="{cx4}" cy="{cy4}" rx="{rx}" ry="{ry}" fill="url(#gloss)"/>

      <!-- stylized 鏡 character — minimal strokes -->
      <!-- 1. Left vertical -->
      <line x1="{cx_}" y1="{y1}" x2="{cx_}" y2="{y2}" stroke="#9dd0ff" stroke-width="{cw}" stroke-linecap="round"/>
      <!-- 2. Top horizontal -->
      <line x1="{cx_}" y1="{y1}" x2="{cx2_}" y2="{y1}" stroke="#9dd0ff" stroke-width="{cw}" stroke-linecap="round"/>
      <!-- 3. Middle horizontal -->
      <line x1="{cx_}" y1="{ym}" x2="{cx2_}" y2="{ym}" stroke="#9dd0ff" stroke-width="{cw}" stroke-linecap="round"/>
      <!-- 4. Right vertical (top) -->
      <line x1="{cx2_}" y1="{y1}" x2="{cx2_}" y2="{ym}" stroke="#9dd0ff" stroke-width="{cw}" stroke-linecap="round"/>
      <!-- 5. Bottom-right stroke (flipped 7) -->
      <polyline points="{cx2_},{ym} {cx3_},{ym} {cx3_},{y2}" fill="none" stroke="#9dd0ff" stroke-width="{cw}" stroke-linecap="round" stroke-linejoin="round"/>
      <!-- 6. Small horizontal on left -->
      <line x1="{cx_}" y1="{y3}" x2="{cx4_}" y2="{y3}" stroke="#9dd0ff" stroke-width="{cw}" stroke-linecap="round"/>

      <!-- handle at bottom -->
      <rect x="{hx}" y="{hy}" width="{hw}" height="{hh}" rx="{hr}" fill="#4a90d9"/>
    </svg>
""")

# ---------------------------------------------------------------------------
# Helper: write SVG
# ---------------------------------------------------------------------------

def write_svg(out_path: Path, size: int) -> None:
    w = size
    cx = size / 2
    cy = size / 2
    r = size * 0.46
    sw = max(1, size // 16)
    r2 = r - sw * 1.5
    r3 = r2 - sw
    cx4 = cx - r3 * 0.2
    cy4 = cy - r3 * 0.2
    rx = r3 * 0.55
    ry = r3 * 0.3
    cw = max(1, size // 10)
    cx_ = cx - r3 * 0.28
    cx2_ = cx + r3 * 0.28
    cx3_ = cx + r3 * 0.52
    cx4_ = cx - r3 * 0.05
    y1 = cy - r3 * 0.42
    y2 = cy + r3 * 0.35
    y3 = cy - r3 * 0.08
    ym = cy + r3 * 0.05
    hx = cx - size * 0.06
    hy = cy + r + sw * 0.5
    hw = size * 0.12
    hh = size * 0.14
    hr = hw / 2

    svg = MIRROR_SVG.format(
        w=w, cx=cx, cy=cy, r=r, r2=r2, r3=r3,
        cx4=cx4, cy4=cy4, rx=rx, ry=ry,
        cx_=cx_, cx2_=cx2_, cx3_=cx3_, cx4_=cx4_,
        y1=y1, y2=y2, y3=y3, ym=ym,
        sw=sw, sw2=sw * 0.6, cw=cw,
        hx=hx, hy=hy, hw=hw, hh=hh, hr=hr,
    )
    out_path.write_text(svg, encoding="utf-8")
    print(f"  wrote {out_path}")


# ---------------------------------------------------------------------------
# PNG via cairosvg (if available) or report
# ---------------------------------------------------------------------------

def try_convert_to_png(svg_path: Path, png_path: Path, size: int) -> bool:
    try:
        import cairosvg
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=size, output_height=size)
        print(f"  wrote {png_path}")
        return True
    except ImportError:
        return False


def main() -> None:
    icon_dir = Path(__file__).parent.parent / "icons"
    icon_dir.mkdir(exist_ok=True)

    sizes = [16, 32, 48, 128]
    has_cairo = True

    for size in sizes:
        svg_path = icon_dir / f"icon{size}.svg"
        png_path = icon_dir / f"icon{size}.png"

        # Always write SVG
        write_svg(svg_path, size)

        # Try to make PNG
        if try_convert_to_png(svg_path, png_path, size):
            svg_path.unlink()  # remove SVG if PNG succeeded
        else:
            if not has_cairo:
                continue
            # Try once to import, report
            print("  cairosvg not available — SVGs left in place; install with: pip install cairosvg")
            has_cairo = False

    print("\nDone. Icons in", icon_dir)


if __name__ == "__main__":
    main()
