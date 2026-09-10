"""Prepare the cork board photo for the app: patch out the generator's mark, encode WebP.

The source is a generated 2296x1856 PNG weighing 8.4MB, with the image tool's four-point
star laid over the frame's right edge near the bottom corner (x 2040..2100, y 1573..1659,
measured by looking for near-white low-saturation pixels — the wood and cork around it are
both strongly saturated, so saturation separates the mark better than brightness does).

Cropping it away would have cost 12% of the width and taken the right-hand frame with it,
so it is patched instead: the frame's right edge runs vertically through that corner, so
the same edge from 270px higher up lines up exactly. The clone is level-matched to the
ring of pixels around the hole before it goes down, then feathered, which is what keeps
the join from showing as a step in the wood's lighting.

    python scripts/prepare-cork-board.py
"""

from PIL import Image, ImageDraw, ImageFilter
import os

SRC = os.path.join(os.path.expanduser('~'), 'Downloads',
                   'Gemini_Generated_Image_9ocig79ocig79oci.png')
OUT = os.path.join('public', 'assets', 'board')
NAME = 'cork-board'

# The mark, with margin. Wider than the detector's own x 2040..2100: the star's arm tips
# fall on cork, which is dark enough that they sit under the brightness cut that found the
# body — patching only what was detected left two pale slivers behind. Wider again after
# that: an arm tip 5px inside the edge fell in the feather band and came out half-covered,
# so the box has to clear the mark by more than FEATHER on every side.
HOLE = (1986, 1538, 2136, 1692)
# How far above to take the clone from. The frame edge is vertical here, so only y moves.
LIFT = 270
FEATHER = 9


def ring_mean(img, box, pad=7):
    """Mean colour of a band just outside `box` — what the patch has to match."""
    x0, y0, x1, y1 = box
    outer = img.crop((x0 - pad, y0 - pad, x1 + pad, y1 + pad))
    px = outer.load()
    w, h = outer.size
    vals = []
    for y in range(h):
        for x in range(w):
            inside = pad <= x < w - pad and pad <= y < h - pad
            if not inside:
                vals.append(px[x, y])
    return tuple(sum(v[c] for v in vals) / len(vals) for c in range(3))


board = Image.open(SRC).convert('RGB')
x0, y0, x1, y1 = HOLE

patch = board.crop((x0, y0 - LIFT, x1, y1 - LIFT))

# Level-match the clone to its destination, per channel.
want = ring_mean(board, HOLE)
have = ring_mean(board, (x0, y0 - LIFT, x1, y1 - LIFT))
shift = [want[c] - have[c] for c in range(3)]
patch = Image.merge('RGB', [
    ch.point(lambda v, s=shift[c]: max(0, min(255, round(v + s))))
    for c, ch in enumerate(patch.split())
])

mask = Image.new('L', patch.size, 0)
ImageDraw.Draw(mask).rectangle(
    (FEATHER, FEATHER, patch.width - 1 - FEATHER, patch.height - 1 - FEATHER), fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(FEATHER * 0.6))
board.paste(patch, (x0, y0), mask)

os.makedirs(OUT, exist_ok=True)
webp = os.path.join(OUT, f'{NAME}.webp')
board.save(webp, 'WEBP', quality=86, method=6)

# Did the mark go? Same detector as the one that found it.
px = board.load()
left = sum(1 for y in range(1540, 1695) for x in range(2000, 2135)
           if px[x, y][0] > 196 and max(px[x, y]) - min(px[x, y]) < 46)
print(f'{webp}  {board.width}x{board.height}  {os.path.getsize(webp) / 1024:.0f} KB'
      f'   (source {os.path.getsize(SRC) / 1024:.0f} KB)')
print(f'mark pixels remaining in the patched area: {left}')
