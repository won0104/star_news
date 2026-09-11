"""Render a cork board surface.

Procedural rather than a photograph, for the same reason the rest of the room's paper is
generated: it can be re-rendered at any size, carries no licence, and weighs a few KB as
WebP against a megabyte of photo.

Cork is not a smooth material and not a noisy one either — it is packed granules of
several sizes. So the height map is a stack of noise octaves: coarse ones for the clumps
your eye reads first, fine ones for the grain inside them. A single octave of Gaussian
noise blurred to taste looks like paper or static, never like cork.

Colour comes from mapping that height map through a palette rather than tinting it. An
L-mode image reinterpreted as P-mode indexes the palette directly, one entry per level,
so the ramp is exact and there is no blending to muddy it.

Two things are added on top, both of which real cork has and noise does not: dark pores
(a sparse threshold of the finest octave) and a slight fall-off toward the edges, which
is what makes a flat fill read as a surface with a light above it.

    python scripts/make-cork-board.py
"""

from PIL import Image, ImageChops, ImageFilter, ImageOps
import os

OUT = os.path.join('public', 'assets', 'board')
NAME = 'cork'
# Matches public/assets/home/backdrop.png, so this can stand in for a room backdrop.
W, H = 1672, 941

# Dark pits to light flecks. Sampled to sit in the room's warm range rather than the
# orange most stock cork is: the app's paper is #fbf6ea and its brass #ba8538.
STOPS = [
    (0, (131, 93, 58)),
    (56, (167, 130, 89)),
    (118, (197, 164, 124)),
    (178, (214, 186, 149)),
    (222, (226, 202, 169)),
    (255, (238, 218, 190)),
]


def octave(scale, sigma, blur=0.0):
    """One layer of noise at 1/scale of the output, grown back up."""
    small = Image.effect_noise((max(2, W // scale), max(2, H // scale)), sigma)
    if blur:
        small = small.filter(ImageFilter.GaussianBlur(blur))
    return small.resize((W, H), Image.BICUBIC)


def ramp():
    """256 palette entries interpolated through STOPS."""
    out = []
    for level in range(256):
        for i in range(len(STOPS) - 1):
            a, b = STOPS[i], STOPS[i + 1]
            if a[0] <= level <= b[0]:
                t = (level - a[0]) / (b[0] - a[0])
                out += [round(a[1][c] + (b[1][c] - a[1][c]) * t) for c in range(3)]
                break
    return out


# ---- height map ----------------------------------------------------------
# Coarse first, then each finer octave blended in at a lower weight.
height = octave(40, 86, 1.2)
for scale, sigma, blur, weight in (
    (18, 78, 0.8, 0.42),
    (9, 70, 0.5, 0.40),
    (5, 64, 0.3, 0.34),
    (3, 56, 0.4, 0.20),
):
    height = Image.blend(height, octave(scale, sigma, blur), weight)

# Takes the edge off what the bicubic upscales leave behind, then puts the granule
# boundaries back. Blur alone left it reading as felt or fine sand: cork's granules meet
# at visible seams, and an unsharp pass at the granules' own radius is what draws them.
height = height.filter(ImageFilter.GaussianBlur(0.5))
height = height.filter(ImageFilter.UnsharpMask(radius=2, percent=115, threshold=2))

# The blending pulls everything toward mid grey; stretch it back to the full range or the
# palette above only ever gets used through its middle third.
height = ImageOps.autocontrast(height, cutoff=1)

# ---- pores ---------------------------------------------------------------
# The darkest few percent of a fine octave, as holes rather than shading.
fine = octave(2, 60).filter(ImageFilter.GaussianBlur(0.6))
pores = fine.point(lambda v: 0 if v < 74 else 255)
pores = pores.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.9))
height = ImageChops.multiply(height, pores.point(lambda v: 178 + v * 77 // 255))

# ---- colour --------------------------------------------------------------
indexed = Image.frombytes('P', height.size, height.tobytes())
indexed.putpalette(ramp())
board = indexed.convert('RGB')

# ---- light ---------------------------------------------------------------
# A wide, soft fall-off from a little above centre. Built small and grown, which is both
# faster and smoother than drawing the gradient at full size.
sw, sh = 84, 48
shade = Image.new('L', (sw, sh))
px = shade.load()
for y in range(sh):
    for x in range(sw):
        dx = (x - sw / 2) / (sw / 2)
        dy = (y - sh * 0.42) / (sh / 2)
        d = min(1.0, (dx * dx * 0.86 + dy * dy) ** 0.5)
        px[x, y] = round(255 - 44 * d ** 1.7)
shade = shade.resize((W, H), Image.BICUBIC)
board = Image.merge('RGB', [ImageChops.multiply(ch, shade) for ch in board.split()])

os.makedirs(OUT, exist_ok=True)
webp = os.path.join(OUT, f'{NAME}.webp')
board.save(webp, 'WEBP', quality=82, method=6)

# Report what came out, so a re-run is checkable.
small = board.resize((160, 90))
data = list(small.getdata())
mean = tuple(round(sum(p[c] for p in data) / len(data)) for c in range(3))
lo = min(sum(p) for p in data) // 3
hi = max(sum(p) for p in data) // 3
print(f'{webp}  {W}x{H}  {os.path.getsize(webp) / 1024:.0f} KB')
print(f'mean {mean}   range {lo}..{hi}')
