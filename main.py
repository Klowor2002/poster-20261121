#!/usr/bin/env python3
"""Luminara — the harbour where the aurora touches the sea.

A travel poster for an invented place, drawn entirely with the Python 3.13
standard library (no third-party packages: hand-rolled PNG encoder, in-code
bitmap lettering). Writes one deterministic image to /output/entry.png.
"""
import binascii
import hashlib
import math
import os
import struct
import sys
import time
import zlib

W, H = 768, 1024
HORIZON = 620
OUT = "/output/entry.png"

# ---------------------------------------------------------------- framebuffer
buf = bytearray(W * H * 3)


def idx(x, y):
    return (y * W + x) * 3


def set_px(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = idx(x, y)
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b


def blend_px(x, y, r, g, b, a):
    """Alpha-blend a colour over the pixel at (x, y). a in [0, 1]."""
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        if a >= 1.0:
            set_px(x, y, r, g, b)
            return
        i = idx(x, y)
        buf[i] = int(r * a + buf[i] * (1.0 - a))
        buf[i + 1] = int(g * a + buf[i + 1] * (1.0 - a))
        buf[i + 2] = int(b * a + buf[i + 2] * (1.0 - a))


def fill_row(y, r, g, b):
    buf[y * W * 3:(y + 1) * W * 3] = bytes((r, g, b)) * W


def lerp(a, b, t):
    return int(a + (b - a) * t)


def lerp3(c1, c2, t):
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


# ------------------------------------------------------------------- randomness
_seed = [123456789]


def rnd():
    """Deterministic LCG, uniform in [0, 1). Same output on every run."""
    _seed[0] = (_seed[0] * 1103515245 + 12345) & 0x7FFFFFFF
    return _seed[0] / 0x7FFFFFFF


# ------------------------------------------------------------------------- sky
SKY_TOP = (7, 38, 54)
SKY_MID = (10, 30, 62)
SKY_HOR = (18, 24, 64)

for y in range(HORIZON):
    t = y / (HORIZON - 1)
    if t < 0.55:
        c = lerp3(SKY_TOP, SKY_MID, t / 0.55)
    else:
        c = lerp3(SKY_MID, SKY_HOR, (t - 0.55) / 0.45)
    fill_row(y, *c)

# Stars: scattered pinpricks, denser and brighter high in the sky.
for _ in range(260):
    sx = int(rnd() * W)
    sy = int(rnd() * 540)
    bright = 120 + int(rnd() * 135)
    dim = 0.45 + 0.55 * (1.0 - sy / 560.0)
    v = int(bright * dim)
    set_px(sx, sy, v, v, min(255, v + 18))
    if rnd() < 0.10:  # a few brighter stars get a tiny cross sparkle
        set_px(sx + 1, sy, v, v, min(255, v + 18))
        set_px(sx, sy + 1, v, v, min(255, v + 18))

# Pale moon, upper left, clear of the title lettering, with a soft halo.
MOON = (88, 108)
for dy in range(-70, 71):
    for dx in range(-70, 71):
        d = math.sqrt(dx * dx + dy * dy)
        if d <= 24:
            set_px(MOON[0] + dx, MOON[1] + dy, 232, 238, 244)
        elif d <= 70:
            a = 0.10 * (1.0 - (d - 24) / 46.0)
            blend_px(MOON[0] + dx, MOON[1] + dy, 200, 215, 235, a)

# ---------------------------------------------------------------------- aurora
# Three translucent ribbons, each a wavy band across the sky.
RIBBONS = [
    # base_y, amp, period, phase, width, strength, colour
    (150, 46, 520, 0, 16, 0.50, (64, 232, 168)),
    (250, 60, 640, 130, 22, 0.42, (46, 214, 196)),
    (330, 38, 430, 260, 13, 0.38, (140, 240, 190)),
]
for base, amp, period, phase, width, strength, col in RIBBONS:
    for x in range(W):
        centre = (base + amp * math.sin(2 * math.pi * (x + phase) / period)
                  + 9 * math.sin(2 * math.pi * (x * 3 + phase) / (period * 2.7)))
        lo = max(0, int(centre - 3 * width))
        hi = min(HORIZON - 1, int(centre + 3 * width))
        for y in range(lo, hi + 1):
            d = (y - centre) / width
            a = strength * math.exp(-d * d)
            if a > 0.01:
                blend_px(x, y, col[0], col[1], col[2], a)

# ------------------------------------------------------- distant headland (left)
for x in range(0, 320):
    top = HORIZON - 30 - int(14 * math.sin(x * 0.021 + 0.6)) - int(6 * math.sin(x * 0.057))
    for y in range(top, HORIZON):
        set_px(x, y, 9, 15, 32)

# ------------------------------------------------------------------------- sea
SEA_TOP = (13, 30, 52)
SEA_BOT = (5, 14, 30)
for y in range(HORIZON, H):
    t = (y - HORIZON) / (H - 1 - HORIZON)
    c = lerp3(SEA_TOP, SEA_BOT, t)
    fill_row(y, *c)
    # Faint green aurora glow reflected just below the horizon.
    if y < HORIZON + 170:
        glow = int(20 * math.exp(-(y - HORIZON) / 110.0))
        i = y * W * 3
        for x in range(W):
            buf[i + 1] = min(255, buf[i + 1] + glow)
            i += 3

# Horizontal shimmer streaks on the water.
for _ in range(90):
    sx = int(rnd() * (W - 140))
    sy = HORIZON + 8 + int(rnd() * (H - HORIZON - 16))
    ln = 20 + int(rnd() * 100)
    a = 0.08 + rnd() * 0.14
    for x in range(sx, min(W, sx + ln)):
        blend_px(x, sy, 150, 200, 220, a)

# ------------------------------------------------------------ lighthouse + islet
# Rocky islet: a low dark ellipse at the waterline.
ISLET_CX, ISLET_CY, ISLET_RX, ISLET_RY = 562, 620, 64, 24
for y in range(ISLET_CY - ISLET_RY, ISLET_CY + ISLET_RY + 1):
    dy = (y - ISLET_CY) / ISLET_RY
    hw = int(ISLET_RX * math.sqrt(max(0.0, 1.0 - dy * dy)))
    for x in range(ISLET_CX - hw, ISLET_CX + hw + 1):
        shade = 16 + int(6 * (1.0 - abs(dy)))
        set_px(x, y, shade, shade + 5, shade + 14)
# Pale highlight following the islet's curved top edge.
for x in range(ISLET_CX - 52, ISLET_CX + 53):
    dx = (x - ISLET_CX) / ISLET_RX
    top_y = ISLET_CY - int(ISLET_RY * math.sqrt(max(0.0, 1.0 - dx * dx)))
    blend_px(x, top_y, 90, 110, 130, 0.5)
    blend_px(x, top_y + 1, 90, 110, 130, 0.3)

# Tower: a tapered pale column, darker on its right side.
for y in range(524, 613):
    t = (y - 524) / (613 - 524)  # 0 at top, 1 at base
    half = int(10 + 6 * t)
    for x in range(562 - half, 562 + half + 1):
        shade = 214 - int(46 * max(0.0, (x - 562) / max(1, half)))
        set_px(x, y, shade, min(255, shade + 14), min(255, shade + 22))
# Gallery band and lamp room.
for y in range(520, 528):
    for x in range(548, 577):
        set_px(x, y, 30, 34, 44)
for y in range(506, 520):
    for x in range(552, 573):
        set_px(x, y, 255, 196, 110)
for y in range(510, 517):
    for x in range(556, 569):
        set_px(x, y, 255, 232, 170)
# Little domed roof.
for y in range(500, 506):
    half = int(3 + (506 - y) * 1.6)
    for x in range(562 - half, 562 + half + 1):
        set_px(x, y, 40, 46, 60)

# Two soft light beams sweeping down from the lamp, left and right.
for sign in (-1, 1):
    for step in range(0, 260, 2):
        bx = 562 + sign * int(step * 0.92)
        by = 514 + int(step * 0.30)
        hw = 4 + int(step * 0.12)
        a = 0.16 * math.exp(-step / 160.0)
        for x in range(bx - hw, bx + hw + 1):
            blend_px(x, by, 255, 220, 150, a)
            blend_px(x, by + 1, 255, 220, 150, a * 0.7)

# Golden light path on the water, straight below the lamp.
for y in range(HORIZON + 4, H):
    depth = (y - HORIZON) / (H - HORIZON)
    half = int(14 + 34 * depth)
    wob = int(8 * math.sin(y * 0.05) + 5 * math.sin(y * 0.13))
    a0 = 0.42 * math.exp(-(y - HORIZON) / 260.0) * (0.7 + 0.3 * math.sin(y * 0.11))
    for x in range(562 + wob - half, 562 + wob + half + 1):
        fall = 1.0 - abs(x - (562 + wob)) / max(1, half)
        blend_px(x, y, 255, 214, 140, a0 * fall)

# -------------------------------------------------------------- the name LUMINARA
# 5x7 hand-drawn bitmap letterforms, scaled up, warm cream, letterspaced.
GLYPHS = {
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
}
WORD = "LUMINARA"
SCALE = 9
SPACING = 14
GW, GH = 5 * SCALE, 7 * SCALE
total_w = len(WORD) * GW + (len(WORD) - 1) * SPACING
X0 = (W - total_w) // 2
Y0 = 64


def draw_word(ox, oy, colour):
    for li, ch in enumerate(WORD):
        gx = X0 + li * (GW + SPACING)
        rows = GLYPHS[ch]
        for r in range(7):
            for c in range(5):
                if rows[r][c] == "1":
                    for dy in range(SCALE):
                        for dx in range(SCALE):
                            set_px(gx + ox + c * SCALE + dx,
                                   Y0 + oy + r * SCALE + dy,
                                   *colour)


draw_word(3, 4, (8, 14, 30))        # soft dark offset, for legibility
draw_word(0, 0, (245, 230, 196))   # warm cream caps

# ---------------------------------------------------------------- PNG encoding
def chunk(ctype, data):
    out = struct.pack(">I", len(data)) + ctype + data
    out += struct.pack(">I", binascii.crc32(ctype + data) & 0xFFFFFFFF)
    return out


def encode_png():
    raw = bytearray()
    for y in range(H):
        row = bytes(buf[y * W * 3:(y + 1) * W * 3])
        # Try filter 0 (None) and filter 1 (Sub); keep the smaller residual.
        f0 = b"\x00" + row
        sub = bytearray(b"\x01")
        prev = 0
        for v in row:
            sub.append((v - prev) & 0xFF)
            prev = v
        score0 = sum(abs(b if b < 128 else b - 256) for b in row)
        score1 = sum(abs(b if b < 128 else b - 256) for b in sub[1:])
        raw += f0 if score0 <= score1 else bytes(sub)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def main():
    t0 = time.time()
    data = encode_png()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(data)
    sha = hashlib.sha256(data).hexdigest()
    print(f"wrote {OUT}: {len(data)} bytes sha256={sha} in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
