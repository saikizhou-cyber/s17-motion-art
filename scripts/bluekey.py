"""Key the flat blue background out of a generated 16:9 frame (soft colour-distance matte).

usage: python scripts/bluekey.py <in.png> <out.png> [d0=38] [d1=80]
The key colour is the median of the image border; alpha ramps from 0 at colour
distance d0 to 1 at d1 (0-255 RGB units); edge pixels are un-mixed from the key.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter

if len(sys.argv) < 3 or sys.argv[1] in ('-h', '--help'):
    sys.exit(__doc__)
src, dst = sys.argv[1], sys.argv[2]
d0 = float(sys.argv[3]) if len(sys.argv) > 3 else 38
d1 = float(sys.argv[4]) if len(sys.argv) > 4 else 80
a = np.asarray(Image.open(src).convert('RGB')).astype(np.float32)
h, w = a.shape[:2]
border = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3), a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
# the border also crosses the subject: keep the dominant (bluest) cluster
blueish = border[(border[:, 2] > border[:, 0] + 40)]
key = np.median(blueish if len(blueish) > 50 else border, 0)
d = np.sqrt(((a - key) ** 2).sum(2))
al = np.clip((d - d0) / (d1 - d0), 0, 1)
A = Image.fromarray((al * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.6))
al = np.asarray(A).astype(np.float32) / 255
un = (a - (1 - al[..., None]) * key) / np.maximum(al[..., None], 0.05)
rgb = np.where(((al > 0.02) & (al < 0.98))[..., None], np.clip(un, 0, 255), a)
Image.fromarray(np.dstack([rgb, al * 255]).astype(np.uint8)).save(dst)
print(dst, 'key', key.round(1))
