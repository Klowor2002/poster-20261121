#!/usr/bin/env python3
"""LUMINARA — a travel poster for a place that isn't there.

A harbour town where the aurora touches the sea. Drawn entirely with
PIL shapes and gradients: no external images, no network, fully
deterministic (fixed seed, no timestamps, no unseeded randomness).

Writes one image to $MAKEFUN_OUTPUT_DIR/entry.png (default /output).
Canvas 768 x 1024 portrait, PNG, under 1 MiB.
"""

import os
import math
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 768, 1024
SEED = 20261121

CREAM = (250, 238, 210)
TEAL_DEEP = (4, 38, 48)
INDIGO = (24, 32, 78)
HORIZON = (46, 96, 110)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vertical_gradient(size, stops):
    """stops: list of (y_fraction, color)."""
    w, h = size
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        f = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            f0, c0 = stops[i]
            f1, c1 = stops[i + 1]
            if f0 <= f <= f1:
                t = 0.0 if f1 == f0 else (f - f0) / (f1 - f0)
                col = lerp(c0, c1, t)
                break
        else:
            col = stops[-1][1]
        for x in range(w):
            px[x, y] = col
    return img


def draw_title(draw, font, text, cx, y, spacing):
    """Letterspaced caps, centred on cx, drawn char by char."""
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = cx - total / 2
    for ch, wd in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=CREAM)
        x += wd + spacing
    return total


def main():
    rng = random.Random(SEED)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)

    # ---- sky: deep teal at top -> indigo -> soft teal glow at horizon ----
    horizon_y = 640
    img = vertical_gradient(
        (W, H),
        [(0.0, TEAL_DEEP), (0.42, INDIGO), (0.62, (34, 74, 96)),
         (0.66, HORIZON), (1.0, (8, 44, 58))],
    )
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # ---- stars (upper sky only) ----
    for _ in range(240):
        x = rng.uniform(0, W)
        y = rng.uniform(0, horizon_y - 90)
        r = rng.choice([0.7, 0.9, 1.1, 1.4])
        a = rng.randint(90, 235)
        od.ellipse([x - r, y - r, x + r, y + r], fill=(255, 250, 230, a))
    # a few bright stars with a cross sparkle
    for _ in range(14):
        x = rng.uniform(20, W - 20)
        y = rng.uniform(20, horizon_y - 160)
        L = rng.uniform(4, 9)
        od.line([x - L, y, x + L, y], fill=(255, 250, 230, 200), width=1)
        od.line([x, y - L, x, y + L], fill=(255, 250, 230, 200), width=1)

    # ---- aurora ribbons: layered translucent sine bands ----
    ribbons = [
        # (base_y, amplitude, wavelength, thickness, color, alpha)
        (150, 46, 420, 34, (64, 224, 178), 26),
        (210, 60, 360, 44, (84, 214, 190), 22),
        (270, 52, 300, 36, (150, 120, 235), 20),
        (330, 40, 480, 28, (58, 226, 196), 18),
    ]
    for base_y, amp, wl, thick, color, alpha in ribbons:
        pts_top, pts_bot = [], []
        for x in range(0, W + 8, 8):
            yc = base_y + amp * math.sin(2 * math.pi * x / wl + base_y)
            yc += 14 * math.sin(2 * math.pi * x / (wl * 0.37) + 1.3)
            pts_top.append((x, yc - thick / 2))
            pts_bot.append((x, yc + thick / 2))
        od.polygon(pts_top + pts_bot[::-1], fill=color + (alpha,))

    img = Image.alpha_composite(img.convert("RGBA"), overlay)

    # ---- sea: calm water from the horizon down ----
    sea = Image.new("RGBA", (W, H - horizon_y), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sea)
    for y in range(H - horizon_y):
        t = y / max(1, H - horizon_y - 1)
        col = lerp((52, 108, 122), (6, 30, 44), t)
        sd.line([(0, y), (W, y)], fill=col + (255,))
    # gentle horizontal swell lines
    for _ in range(46):
        y = rng.uniform(8, H - horizon_y - 8)
        x0 = rng.uniform(0, W - 180)
        ln = rng.uniform(50, 200)
        a = rng.randint(18, 60)
        sd.line([(x0, y), (x0 + ln, y)], fill=(170, 225, 215, a), width=2)
    img.paste(Image.alpha_composite(img.crop((0, horizon_y, W, H)),
                                    sea).convert("RGB"), (0, horizon_y))
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img)

    # ---- light path: the lighthouse beam reflected on the water ----
    # soft, jittered dashes that widen and fade toward the viewer
    lx = 384  # lighthouse centre x
    path = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(path)
    for i in range(30):
        y = horizon_y + 12 + i * 12
        half = 10 + i * 4.2 + rng.uniform(-4, 4)
        a = max(0, 155 - i * 5)
        pd.line([(lx - half, y), (lx + half, y)],
                fill=(250, 232, 190, a), width=4)
    path = path.filter(ImageFilter.GaussianBlur(2))
    img = Image.alpha_composite(img, path)
    draw = ImageDraw.Draw(img)

    # ---- rocky islet ----
    rock = [(lx - 118, horizon_y + 4), (lx - 88, horizon_y - 34),
            (lx - 40, horizon_y - 52), (lx + 8, horizon_y - 44),
            (lx + 62, horizon_y - 30), (lx + 118, horizon_y + 4)]
    draw.polygon(rock, fill=(16, 30, 40, 255))
    draw.line(rock, fill=(90, 130, 130, 255), width=2, joint="curve")
    # a few pale rock highlights
    draw.line([(lx - 88, horizon_y - 34), (lx - 40, horizon_y - 52)],
              fill=(120, 165, 160, 255), width=3)

    # ---- crystal lighthouse: tapered tower + glowing lamp room ----
    tower_base = horizon_y - 44
    tower_top = horizon_y - 300
    tower = [(lx - 34, tower_base), (lx - 20, tower_top),
             (lx + 20, tower_top), (lx + 34, tower_base)]
    # tower glow halo (soft, behind the tower)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([lx - 150, tower_top - 130, lx + 150, tower_top + 130],
               fill=(190, 240, 225, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(38))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)
    draw.polygon(tower, fill=(214, 232, 228, 255))
    draw.polygon(tower, outline=(120, 160, 155, 255))
    # crystal facets: vertical light seams
    for dx, wd in ((-12, 5), (0, 7), (12, 5)):
        draw.line([(lx + dx, tower_top + 8), (lx + dx + (4 if dx < 0 else -4
                  if dx > 0 else 0), tower_base - 4)],
                  fill=(255, 255, 255, 220), width=wd)
    # gallery + lamp room
    draw.rectangle([lx - 30, tower_top - 16, lx + 30, tower_top + 2],
                   fill=(30, 52, 66, 255))
    draw.rectangle([lx - 18, tower_top - 52, lx + 18, tower_top - 16],
                   fill=(255, 226, 150, 255))
    draw.rectangle([lx - 18, tower_top - 52, lx + 18, tower_top - 16],
                   outline=(90, 70, 30, 255), width=2)
    # dome
    draw.pieslice([lx - 22, tower_top - 76, lx + 22, tower_top - 40],
                  180, 360, fill=(30, 52, 66, 255))
    draw.line([(lx, tower_top - 76), (lx, tower_top - 88)],
              fill=(30, 52, 66, 255), width=3)
    draw.ellipse([lx - 3, tower_top - 92, lx + 3, tower_top - 86],
                 fill=(255, 226, 150, 255))

    # ---- light beams sweeping over the water ----
    beam = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(beam)
    bd.polygon([(lx, tower_top - 34), (30, horizon_y - 150),
                (30, horizon_y - 60)], fill=(255, 240, 190, 42))
    bd.polygon([(lx, tower_top - 34), (W - 30, horizon_y - 150),
                (W - 30, horizon_y - 60)], fill=(255, 240, 190, 42))
    beam = beam.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, beam)
    draw = ImageDraw.Draw(img)

    # ---- distant headland silhouette (left) for depth ----
    draw.polygon([(0, horizon_y), (0, horizon_y - 58), (70, horizon_y - 96),
                  (150, horizon_y - 52), (210, horizon_y - 70),
                  (250, horizon_y), (0, horizon_y)],
                 fill=(10, 26, 40, 255))
    # tiny harbour lights on the headland
    for hx, hy in ((58, horizon_y - 78), (96, horizon_y - 62),
                   (140, horizon_y - 58), (176, horizon_y - 60)):
        draw.ellipse([hx - 2, hy - 2, hx + 2, hy + 2],
                     fill=(255, 214, 130, 255))

    # ---- title: LUMINARA, large letterspaced warm-cream caps ----
    # Auto-fit: shrink until the letterspaced title fits with margins.
    font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "DejaVuSans-Bold.ttf")
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    title_size, spacing = 92, 30
    title_font = None
    while title_size >= 40:
        try:
            cand = ImageFont.truetype(font_path, title_size)
        except Exception:
            cand = ImageFont.load_default()
            break
        total_w = (sum(probe.textlength(ch, font=cand) for ch in "LUMINARA")
                   + spacing * 7)
        if total_w <= W - 72:
            title_font = cand
            break
        title_size -= 4
        spacing = max(14, spacing - 2)
    if title_font is None:
        title_font = ImageFont.load_default()
    title_y = 64
    # soft shadow for legibility against the aurora
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shd = ImageDraw.Draw(shadow)
    draw_title(shd, title_font, "LUMINARA", W // 2 + 3, title_y + 4, spacing)
    shadow = shadow.filter(ImageFilter.GaussianBlur(3))
    # recolor shadow dark
    dark = Image.new("RGBA", (W, H), (4, 20, 30, 0))
    mask = shadow.split()[3]
    dark.putalpha(mask.point(lambda v: min(200, v)))
    img = Image.alpha_composite(img, dark)
    draw = ImageDraw.Draw(img)
    draw_title(draw, title_font, "LUMINARA", W // 2, title_y, spacing)
    # thin rule under the title, echoing the horizon
    draw.line([(W // 2 - 130, title_y + 128), (W // 2 + 130, title_y + 128)],
              fill=(250, 238, 210, 255), width=3)

    img.convert("RGB").save(os.path.join(out_dir, "entry.png"),
                            optimize=True)


if __name__ == "__main__":
    main()
