"""Render the pinboard: a framed cork board, straight on, nothing around it.

Drawn rather than photographed because that is what "the board itself" needs — the
reference photo is a board on a sunlit wall, shot at an angle, and no crop of it gives a
square-on object with no wall in it.

Colours are sampled from that reference rather than invented (see the numbers beside each
constant), with the sunlight taken back out: the photo's cork runs (152,99,62) in the sun
and (177,124,81) in shade, so the body here sits between them and the render carries only
a slight top-left lift instead of a window's worth of light.

Two things make cork read as cork, and the first attempt at this texture had neither. One
is granule size — packed flakes of about 16px at this resolution, which is a noise octave
at 1/16 rather than the fine grain that reads as sandpaper. The other is pores: cork is
full of small near-black specks, and without them a warm mottle looks like suede.

The frame is four mitred pieces, not one rectangle, because each piece's grain has to run
along its own length — that is what the diagonal seams at the corners are. Each is shaded
for a light above and to the left, and each carries a bevel across its width: a darker
outer arris, a bright face, and a dark inner lip that also drops a shadow onto the cork.

    python scripts/make-pinboard.py
"""

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
import os

OUT = os.path.join('public', 'assets', 'board')
NAME = 'pinboard'

W, H = 1800, 1200
FRAME = 58

# Cork body, dark end to light end. Between the reference's sunlit and shaded cork.
CORK_STOPS = [
    (0, (144, 105, 68)),
    (70, (174, 136, 94)),
    (140, (196, 160, 117)),
    (200, (212, 181, 141)),
    (255, (226, 200, 166)),
]
PORE = (74, 48, 28)
# Pale ash, from the reference's frame face with its inner lip excluded.
WOOD = (207, 176, 137)


def octave(size, scale, sigma, blur=0.0):
    w, h = size
    small = Image.effect_noise((max(2, w // scale), max(2, h // scale)), sigma)
    if blur:
        small = small.filter(ImageFilter.GaussianBlur(blur))
    return small.resize((w, h), Image.BICUBIC)


def ramp(stops):
    out = []
    for level in range(256):
        for i in range(len(stops) - 1):
            a, b = stops[i], stops[i + 1]
            if a[0] <= level <= b[0]:
                t = (level - a[0]) / (b[0] - a[0])
                out += [round(a[1][c] + (b[1][c] - a[1][c]) * t) for c in range(3)]
                break
    return out


def cork(size):
    w, h = size
    # Granules: one dominant octave with coarser patchiness under it and one finer on top.
    height = octave(size, 60, 84, 1.4)
    for scale, sigma, blur, weight in ((30, 76, 1.0, 0.42), (12, 70, 0.5, 0.54), (6, 60, 0.4, 0.28)):
        height = Image.blend(height, octave(size, scale, sigma, blur), weight)
    height = ImageOps.autocontrast(height, cutoff=1)
    height = height.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=2))

    indexed = Image.frombytes('P', size, height.tobytes())
    indexed.putpalette(ramp(CORK_STOPS))
    body = indexed.convert('RGB')

    # Pores. Thresholded high so only the peaks of a mid-fine octave survive, then broken
    # up so they come out as irregular specks instead of round dots.
    seed = octave(size, 4, 64, 0.3)
    spots = seed.point(lambda v: 255 if v > 206 else 0)
    spots = spots.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    spots = spots.filter(ImageFilter.GaussianBlur(0.6))
    coverage = sum(spots.resize((160, 100)).getdata()) / (160 * 100 * 255)
    # Blended rather than composited, and unevenly: a pore is a depression the light does
    # not reach, so some are darker than others and the granule under them still shows.
    depth = spots.point(lambda v: round(v * 0.82))
    board = Image.composite(Image.new('RGB', size, PORE), body, depth)

    # A slight lift toward the top left, so it is not perfectly flat.
    sw, sh = 60, 40
    lift = Image.new('L', (sw, sh))
    lp = lift.load()
    for y in range(sh):
        for x in range(sw):
            d = ((x / sw) ** 2 + (y / sh) ** 2) ** 0.5 / 1.414
            lp[x, y] = round(255 - 26 * d)
    lift = lift.resize(size, Image.BICUBIC)
    board = Image.merge('RGB', [ImageChops.multiply(ch, lift) for ch in board.split()])
    return board, coverage


def wood_piece(size, horizontal):
    """A length of moulding: grain along its length, bevel across its width."""
    w, h = size
    across = max(6, (h if horizontal else w) // 3)
    along = max(2, (w if horizontal else h) // 2)
    if horizontal:
        grain = Image.effect_noise((along, across), 30).resize((w, h), Image.BICUBIC)
    else:
        grain = Image.effect_noise((across, along), 30).resize((w, h), Image.BICUBIC)
    grain = grain.filter(ImageFilter.GaussianBlur(0.6))

    # Bevel profile across the width: outer arris, face, inner lip.
    n = h if horizontal else w
    prof = []
    for i in range(n):
        t = i / max(1, n - 1)
        if t < 0.10:
            v = 0.88 + 0.10 * (t / 0.10)
        elif t < 0.72:
            v = 0.98 + 0.06 * ((t - 0.10) / 0.62)
        else:
            v = 1.04 - 0.26 * ((t - 0.72) / 0.28)
        prof.append(v)
    bevel = Image.new('L', size)
    bp = bevel.load()
    for y in range(h):
        for x in range(w):
            bp[x, y] = round(min(255, 255 * prof[y if horizontal else x]))

    face = Image.new('RGB', size, WOOD)
    # Grain modulates by about a twentieth; any more and ash looks like oak.
    face = Image.merge('RGB', [
        ImageChops.multiply(ch, grain.point(lambda v: 226 + v * 29 // 255))
        for ch in face.split()
    ])
    return Image.merge('RGB', [ImageChops.multiply(ch, bevel) for ch in face.split()])


# ---- cork ----------------------------------------------------------------
inner = (W - 2 * FRAME, H - 2 * FRAME)
surface, pore_coverage = cork(inner)

# The frame's inner lip drops a shadow onto the cork, strongest at the top and left.
shade = Image.new('L', inner, 255)
sd = ImageDraw.Draw(shade)
REACH = 34
for i in range(REACH):
    t = i / REACH
    v = round(255 - 46 * (1 - t) ** 1.6)
    sd.line([(i, i), (i, inner[1] - 1 - i)], fill=v)          # left
    sd.line([(i, i), (inner[0] - 1 - i, i)], fill=v)          # top
for i in range(REACH // 2):
    t = i / (REACH // 2)
    v = round(255 - 22 * (1 - t) ** 1.6)
    sd.line([(inner[0] - 1 - i, i), (inner[0] - 1 - i, inner[1] - 1 - i)], fill=v)
    sd.line([(i, inner[1] - 1 - i), (inner[0] - 1 - i, inner[1] - 1 - i)], fill=v)
shade = shade.filter(ImageFilter.GaussianBlur(7))
surface = Image.merge('RGB', [ImageChops.multiply(ch, shade) for ch in surface.split()])

board = Image.new('RGB', (W, H), WOOD)
board.paste(surface, (FRAME, FRAME))

# ---- frame ---------------------------------------------------------------
# Light above and to the left: the top rail is brightest, the bottom darkest.
PIECES = [
    ('top', [(0, 0), (W, 0), (W - FRAME, FRAME), (FRAME, FRAME)], True, 1.05),
    ('left', [(0, 0), (FRAME, FRAME), (FRAME, H - FRAME), (0, H)], False, 1.00),
    ('right', [(W, 0), (W - FRAME, FRAME), (W - FRAME, H - FRAME), (W, H)], False, 0.92),
    ('bottom', [(0, H), (W, H), (W - FRAME, H - FRAME), (FRAME, H - FRAME)], True, 0.85),
]
for name, poly, horizontal, gain in PIECES:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    box = (min(xs), min(ys), max(xs), max(ys))
    size = (box[2] - box[0], box[3] - box[1])
    piece = wood_piece(size, horizontal)
    if name in ('bottom', 'right'):
        # These read from the inner edge outward, so the bevel runs the other way.
        piece = piece.transpose(Image.FLIP_TOP_BOTTOM if horizontal else Image.FLIP_LEFT_RIGHT)
    piece = Image.merge('RGB', [
        ch.point(lambda v, g=gain: max(0, min(255, round(v * g)))) for ch in piece.split()
    ])
    mask = Image.new('L', size, 0)
    ImageDraw.Draw(mask).polygon([(x - box[0], y - box[1]) for x, y in poly], fill=255)
    board.paste(piece, (box[0], box[1]), mask)

# A hairline at the very outside, so the board has an edge rather than fading into
# whatever it is placed on.
ImageDraw.Draw(board).rectangle((0, 0, W - 1, H - 1), outline=(150, 121, 88), width=2)

os.makedirs(OUT, exist_ok=True)
webp = os.path.join(OUT, f'{NAME}.webp')
board.save(webp, 'WEBP', quality=88, method=6)

small = board.crop((FRAME, FRAME, W - FRAME, H - FRAME)).resize((160, 100))
data = list(small.getdata())
mean = tuple(round(sum(p[c] for p in data) / len(data)) for c in range(3))
print(f'{webp}  {W}x{H}  frame {FRAME}px  {os.path.getsize(webp) / 1024:.0f} KB')
print(f'cork mean {mean}   pore coverage {pore_coverage * 100:.1f}%')
