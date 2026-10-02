"""Measure frames instead of eyeballing them ("1:1" means numbers, not "looks similar").

usage:
  python frame_measure.py frame <video> <n> <out.png>                  # exact frame n, full resolution
  python frame_measure.py colors <img> [--region x0,y0,x1,y1] [--top 6]  # modal flat colours (backdrop, skin, shadow)
  python frame_measure.py components <img> [--thr 110] [--dark] [--region ...] [--min 6]
                                                                       # blobs of a bright (or dark) mask: bbox + area
  python frame_measure.py runs <img> --axis col|row --from A --to B [--step 5] [--thr 110] [--dark] [--region ...]
                                                                       # per column: y-runs of the mask (per row: x-runs)
  python frame_measure.py bbox <img> --color R,G,B [--tol 40] [--region ...]
                                                                       # where a flat-coloured figure sits: bbox, 1-99 % extents
  python frame_measure.py iou <ref.png> <ours.png> [--thr 110] [--dark] [--region ...]
                                                                       # mask overlap of the same frame, ours vs reference

Typical uses:
  * measure an effect's footprint (bbox, angle, timing, palette) with `components` / `bbox` and draw your OWN
    shape in that footprint; use `iou` to check size and placement, not to clone someone else's outline;
  * keep a figure the same size and place across shots: `bbox` on each shot's frame, then drive every
    shot from ONE shared placement constant;
  * sample colours on the real frame, not on a screenshot: a viewer's gamma can show pure black as grey.
"""
import argparse
import os
import subprocess
import sys

import numpy as np
from PIL import Image


def load(p):
    if not os.path.exists(p):
        sys.exit(f'image not found: {p}')
    return np.asarray(Image.open(p).convert('RGB')).astype(int)


def crop(a, region):
    if not region:
        return a, 0, 0
    try:
        x0, y0, x1, y1 = (int(v) for v in region.split(','))
    except ValueError:
        sys.exit('--region must be x0,y0,x1,y1 (integers)')
    if min(x0, y0) < 0 or x1 <= x0 or y1 <= y0:
        sys.exit('--region must be x0,y0,x1,y1 with 0 <= x0 < x1 and 0 <= y0 < y1')
    c = a[y0:y1, x0:x1]
    if not c.size:
        sys.exit(f'--region {region} is outside the {a.shape[1]}x{a.shape[0]} image')
    return c, x0, y0


def mask(a, thr, dark):
    lum = a.mean(-1)
    return lum < thr if dark else lum > thr


def runs1d(v, off):
    idx = np.nonzero(v)[0]
    if not len(idx):
        return []
    out, st, pr = [], idx[0], idx[0]
    for i in idx[1:]:
        if i != pr + 1:
            out.append((int(st + off), int(pr + off)))
            st = i
        pr = i
    out.append((int(st + off), int(pr + off)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['frame', 'colors', 'components', 'runs', 'bbox', 'iou'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--region')
    ap.add_argument('--thr', type=float, default=110)
    ap.add_argument('--dark', action='store_true', help='measure dark pixels instead of bright ones')
    ap.add_argument('--min', type=int, default=6, help='smallest component area to list')
    ap.add_argument('--axis', choices=['col', 'row'], default='col')
    ap.add_argument('--from', dest='frm', type=int)
    ap.add_argument('--to', type=int)
    ap.add_argument('--step', type=int, default=5)
    ap.add_argument('--color')
    ap.add_argument('--tol', type=float, default=40)
    ap.add_argument('--top', type=int, default=6)
    a = ap.parse_args()

    sig = {'frame': '<video> <n> <out.png>', 'iou': '<ref.png> <ours.png>'}.get(a.cmd, '<img>')
    if len(a.args) != len(sig.split()):
        ap.error(f'usage: frame_measure.py {a.cmd} {sig} [options]')

    if a.cmd == 'frame':
        video, n, out = a.args
        try:
            n = int(n)
        except ValueError:
            ap.error(f'frame number must be an integer, got {n!r}')
        if not os.path.exists(video):
            sys.exit(f'video not found: {video}')
        base, ext = os.path.splitext(out)
        tmp = f'{base}.part{ext}'  # a stale out.png must not pass for the new frame
        if os.path.exists(tmp):
            os.remove(tmp)
        try:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-vf', f'select=eq(n\\,{n})', '-frames:v', '1', tmp], check=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            sys.exit(f'ffmpeg failed: {e}')
        if not os.path.exists(tmp):
            sys.exit(f'frame {n} is past the end of {video}')
        os.replace(tmp, out)
        print(out)
        return
    img, ox, oy = crop(load(a.args[0]), a.region)
    if a.cmd == 'colors':
        px = img.reshape(-1, 3)
        # bin to 4 levels per channel, then report the true mean of the pixels in each bin (not the bin floor)
        key = ((px[:, 0] >> 2) << 12) | ((px[:, 1] >> 2) << 6) | (px[:, 2] >> 2)
        _, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
        inv = inv.ravel()
        mean = np.stack([np.bincount(inv, weights=px[:, c], minlength=len(cnt)) for c in range(3)], 1) / cnt[:, None]
        for i in np.argsort(-cnt)[:a.top]:
            r, g, b = (int(round(v)) for v in mean[i])
            print(f'#{r:02x}{g:02x}{b:02x}  rgb({r},{g},{b})  {cnt[i] / len(px):.1%}')
    elif a.cmd == 'components':
        from scipy import ndimage as nd
        lab, _ = nd.label(mask(img, a.thr, a.dark))
        for i, s in enumerate(nd.find_objects(lab), 1):
            area = int((lab[s] == i).sum())
            if area >= a.min:
                print(f'#{i}  x {s[1].start + ox}-{s[1].stop - 1 + ox}  y {s[0].start + oy}-{s[0].stop - 1 + oy}  area {area}')
    elif a.cmd == 'runs':
        if a.step < 1:
            sys.exit('--step must be >= 1')
        m = mask(img, a.thr, a.dark)
        # valid coordinates of the (cropped) image along the scan axis
        r0, r1 = (ox, ox + m.shape[1] - 1) if a.axis == 'col' else (oy, oy + m.shape[0] - 1)
        lo = a.frm if a.frm is not None else r0
        hi = a.to if a.to is not None else r1
        if lo < r0 or hi > r1:
            print(f'note: --from/--to clamped to the {a.axis} range {r0}-{r1} of the image/region', file=sys.stderr)
        lo, hi = max(lo, r0), min(hi, r1)
        if lo > hi:
            sys.exit(f'--from/--to are outside the {a.axis} range {r0}-{r1}')
        for v in range(lo, hi + 1, a.step):
            line = m[:, v - ox] if a.axis == 'col' else m[v - oy, :]
            print(v, runs1d(line, oy if a.axis == 'col' else ox))
    elif a.cmd == 'bbox':
        if not a.color:
            sys.exit('--color R,G,B required')
        try:
            c = np.array([int(v) for v in a.color.split(',')])
        except ValueError:
            c = []
        if len(c) != 3:
            sys.exit('--color must be R,G,B (three integers)')
        m = np.sqrt(((img - c) ** 2).sum(-1)) < a.tol
        ys, xs = np.nonzero(m)
        if not len(xs):
            sys.exit('no pixels of that colour')
        print(f'bbox x {xs.min() + ox}-{xs.max() + ox}  y {ys.min() + oy}-{ys.max() + oy}  px {len(xs)}')
        print(f'1-99%  x {np.percentile(xs, 1) + ox:.0f}-{np.percentile(xs, 99) + ox:.0f}  y {np.percentile(ys, 1) + oy:.0f}-{np.percentile(ys, 99) + oy:.0f}')
    elif a.cmd == 'iou':
        other, _, _ = crop(load(a.args[1]), a.region)
        if other.shape != img.shape:
            sys.exit(f'size mismatch {img.shape} vs {other.shape}: scale ours to the reference size first')
        r, o = mask(img, a.thr, a.dark), mask(other, a.thr, a.dark)
        print(f'ref px {int(r.sum())}  ours px {int(o.sum())}  IoU {(r & o).sum() / max(1, (r | o).sum()):.3f}')


if __name__ == '__main__':
    main()
