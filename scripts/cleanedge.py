"""Clean a rembg cutout's edge: remove the light background halo and tiny detached specks.

usage: python scripts/cleanedge.py <original.png> <cut.png> <out.png> [erode=1]
The background colour is read from the original's corners; semi-transparent edge
pixels are un-mixed from it (decontaminated), then alpha is eroded by `erode` px.
Finally alpha > 8 is split into connected blobs (8-connected) and every blob smaller
than 1% of the largest one is cleared.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as nd

if len(sys.argv) < 4 or sys.argv[1] in ('-h', '--help'):
    sys.exit(__doc__)
src, cut, dst = sys.argv[1], sys.argv[2], sys.argv[3]
erode = int(sys.argv[4]) if len(sys.argv) > 4 else 1
o = np.asarray(Image.open(src).convert('RGB')).astype(np.float32)
c = Image.open(cut).convert('RGBA')
a = np.asarray(c).astype(np.float32)
h, w = o.shape[:2]
k = max(8, min(h, w) // 40)
bg = np.median(np.concatenate([o[:k, :k].reshape(-1, 3), o[:k, -k:].reshape(-1, 3), o[-k:, :k].reshape(-1, 3), o[-k:, -k:].reshape(-1, 3)]), 0)
al = a[..., 3] / 255
rgb = a[..., :3]
m = (al > 0.02) & (al < 0.98)
un = (rgb - (1 - al[..., None]) * bg) / np.maximum(al[..., None], 0.05)
rgb = np.where(m[..., None], np.clip(un, 0, 255), rgb)
A = Image.fromarray((al * 255).astype(np.uint8))
for _ in range(erode):
    A = A.filter(ImageFilter.MinFilter(3))
alpha = np.asarray(A).copy()
# drop specks: blobs of alpha > 8 under 1% of the largest blob's area
lab, n = nd.label(alpha > 8, structure=np.ones((3, 3)))
dropped = 0
if n > 1:
    area = np.bincount(lab.ravel())[1:]
    small = np.concatenate([[False], area < 0.01 * area.max()])
    alpha[small[lab]] = 0
    dropped = int(small.sum())
out = np.dstack([rgb, alpha.astype(np.float32)]).astype(np.uint8)
Image.fromarray(out).save(dst)
print(dst, 'bg', bg.round(1), 'specks removed', dropped)
