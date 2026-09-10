"""Crop the three star renders to a common body-relative frame, re-tint them, encode.

Each render puts its star in a 1254px frame with a soft glow around it, but the
body-to-glow ratio differs wildly between them (the small star's halo is 3.7x its body,
the large one's 1.6x). Rendered as delivered, a small star on screen would wear a
bigger halo than a big one. Cropping each to "body plus 40% of the body width on every
side" normalises that, so the three keep their own shapes and share one glow ratio: the
body is 1/1.8 of the frame in all three.

The re-tint takes the palette off the reference constellation, whose shapes we are not
copying but whose colour we are. Measured there against measured here:

    body   reference (253, 242, 183)   these renders (251, 248, 204)
    glow   reference  1 : 0.80 : 0.31  these renders  1 : 0.97 : 0.45

The glow figures are ratios, not colours: a glow is additive over the wall behind it, so
what was measured is the reference glow's brightest pixel minus the wall beside it, which
leaves alpha times the glow's own colour. As a ratio it says the reference glow is amber
where these are lemon — nearly as much green as red, and half again as much blue.

Correcting that needs two different corrections, since the body wants less blue and the
glow wants more, and no single per-channel factor does both. What separates them is
alpha, not colour, so the factor is interpolated by alpha: solid pixels get the body's
factor, faint ones the glow's, and everything between is mixed. Each pixel keeps its own
value and only its tint moves, which is what preserves the paper grain inside the stars —
replacing colour outright by alpha would have flattened it.
"""

from PIL import Image
import os

SRC = r"C:\Users\SSAFY\Downloads"
OUT = r"C:\Users\SSAFY\Desktop\특화_프로젝트\S15P21E206\frontend\public\assets\trend"
MARGIN = 0.40
FRAME = 240

# Measured mean of this batch of renders where alpha is solid, and where it is mid.
MEASURED_BODY = (251, 248, 204)
MEASURED_GLOW = (236, 228, 106)
# The reference's body, and its glow scaled to the same red as the measurement above so
# the ratio is all that carries over.
TARGET_BODY = (253, 242, 183)
TARGET_GLOW = (255, 204, 79)

BODY_FACTOR = tuple(t / m for t, m in zip(TARGET_BODY, MEASURED_BODY))
GLOW_FACTOR = tuple(t / m for t, m in zip(TARGET_GLOW, MEASURED_GLOW))


def retint(im):
    """Scale every pixel's channels by a factor chosen from its own alpha."""
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            t = a / 255
            f = tuple(gf + (bf - gf) * t for gf, bf in zip(GLOW_FACTOR, BODY_FACTOR))
            px[x, y] = (
                min(255, round(r * f[0])),
                min(255, round(g * f[1])),
                min(255, round(b * f[2])),
                a,
            )
    return im

# kind -> the render whose star body is the size the kind wants
PICKS = {
    'star-event': 'ChatGPT Image 2026년 9월 9일 오후 02_35_12.png',
    'star-statement': 'ChatGPT Image 2026년 9월 9일 오후 02_34_57 (3).png',
    'star-entity': 'ChatGPT Image 2026년 9월 9일 오후 02_34_56 (2).png',
}

for name, src in PICKS.items():
    im = Image.open(os.path.join(SRC, src)).convert('RGBA')
    # The body is where alpha is near-solid; the rest is glow.
    body = im.getchannel('A').point(lambda v: 255 if v > 200 else 0).getbbox()
    bw, bh = body[2] - body[0], body[3] - body[1]
    cx, cy = (body[0] + body[2]) / 2, (body[1] + body[3]) / 2
    half = max(bw, bh) / 2 * (1 + MARGIN)
    crop = (round(cx - half), round(cy - half), round(cx + half), round(cy + half))
    assert crop[0] >= 0 and crop[1] >= 0 and crop[2] <= im.width and crop[3] <= im.height, (name, crop)

    tile = retint(im.crop(crop).resize((FRAME, FRAME), Image.LANCZOS))
    path = os.path.join(OUT, f'{name}.webp')
    tile.save(path, 'WEBP', quality=88, method=6)

    # Report what the tint actually landed on, so a re-run is checkable against the
    # numbers in the docstring rather than taken on trust.
    px = tile.load()
    body = [px[x, y][:3] for y in range(0, FRAME, 2) for x in range(0, FRAME, 2) if px[x, y][3] > 245]
    glow = [px[x, y][:3] for y in range(0, FRAME, 2) for x in range(0, FRAME, 2) if 40 < px[x, y][3] < 120]
    mean = lambda s: tuple(round(sum(v[c] for v in s) / len(s)) for c in range(3))
    bm, gm = mean(body), mean(glow)
    print(f'{name:16} body {bw}x{bh} -> {FRAME}px  {os.path.getsize(path)/1024:5.1f} KB'
          f'   body {bm}  glow {gm} = 1 : {gm[1]/gm[0]:.2f} : {gm[2]/gm[0]:.2f}')
