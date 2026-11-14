"""Generate the PWA icons with the standard library only (no Pillow required).

Draws the JanVaani UP mark - a microphone on a deep-green gradient tile - at any
requested size and writes a PNG. Run with:

    py scripts/make_icons.py
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "frontend" / "public"

SS = 3  # supersampling factor for anti-aliasing

BRAND_TOP = (6, 95, 70)      # #065F46
BRAND_BOTTOM = (16, 185, 129)  # #10B981
ACCENT = (245, 158, 11)      # #F59E0B
WHITE = (255, 255, 255)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def rounded_rect_contains(x: float, y: float, x0: float, y0: float, x1: float, y1: float, r: float) -> bool:
    if x < x0 or x > x1 or y < y0 or y > y1:
        return False
    cx = min(max(x, x0 + r), x1 - r)
    cy = min(max(y, y0 + r), y1 - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def capsule_contains(x: float, y: float, cx: float, cy: float, half_w: float, half_h: float) -> bool:
    """Rounded rectangle with fully rounded left/right ends (a capsule)."""
    dx = abs(x - cx) - (half_w - half_h)
    dy = abs(y - cy)
    if dx <= 0:
        return dy <= half_h
    return dx * dx + dy * dy <= half_h * half_h


def draw_mic(x: float, y: float, size: float) -> tuple[int, int, int] | None:
    """Return the mic colour at (x, y) in icon space, or None."""
    s = size
    cx = s / 2

    # Capsule body of the microphone.
    body_top = s * 0.22
    body_bottom = s * 0.58
    body_cx = cx
    body_hw = s * 0.115
    body_hh = (body_bottom - body_top) / 2
    body_cy = (body_top + body_bottom) / 2
    if capsule_contains(x, y, body_cx, body_cy, body_hw, body_hh):
        return WHITE

    # Arc cradle around the microphone.
    arc_cy = s * 0.54
    arc_r = s * 0.20
    thickness = s * 0.055
    dist = math.hypot(x - cx, y - arc_cy)
    if abs(dist - arc_r) <= thickness / 2 and y >= arc_cy:
        return WHITE

    # Stem.
    if abs(x - cx) <= s * 0.028 and arc_cy <= y <= s * 0.735:
        return WHITE

    # Base.
    if s * 0.30 <= x <= s * 0.70 and abs(y - s * 0.735) <= s * 0.028:
        return WHITE

    # Saffron sound-wave accent on the right side.
    for radius, arc_cx in ((s * 0.27, cx), (s * 0.345, cx)):
        dist = math.hypot(x - arc_cx, y - s * 0.40)
        if abs(dist - radius) <= s * 0.022 and x > cx + s * 0.02 and abs(y - s * 0.40) < radius:
            return ACCENT

    return None


def render(size: int) -> bytes:
    """Render the icon at `size` pixels and return raw RGBA bytes."""
    total = size * SS
    rows: list[bytes] = []
    radius = total * 0.22

    for py in range(total):
        row = bytearray()
        for px in range(total):
            x = px + 0.5
            y = py + 0.5

            if not rounded_rect_contains(x, y, 0, 0, total, total, radius):
                row += bytes((0, 0, 0, 0))
                continue

            t = y / total
            base = (
                int(lerp(BRAND_TOP[0], BRAND_BOTTOM[0], t)),
                int(lerp(BRAND_TOP[1], BRAND_BOTTOM[1], t)),
                int(lerp(BRAND_TOP[2], BRAND_BOTTOM[2], t)),
            )

            mic = draw_mic(x, y, total)
            if mic is not None:
                base = mic
            row += bytes((base[0], base[1], base[2], 255))
        rows.append(bytes(row))

    # Downsample (box filter) to the requested size.
    out: list[bytes] = []
    for y in range(size):
        out_row = bytearray()
        for x in range(size):
            r = g = b = a = 0
            for dy in range(SS):
                for dx in range(SS):
                    offset = (x * SS + dx) * 4
                    px = rows[y * SS + dy][offset : offset + 4]
                    r += px[0]
                    g += px[1]
                    b += px[2]
                    a += px[3]
            count = SS * SS
            out_row += bytes((r // count, g // count, b // count, a // count))
        out.append(bytes(out_row))

    raw = b"".join(b"\x00" + row for row in out)
    return raw


def write_png(path: Path, size: int, raw: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size, name in ((192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")):
        raw = render(size)
        target = OUT_DIR / name
        write_png(target, size, raw)
        print(f"wrote {target} ({target.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
