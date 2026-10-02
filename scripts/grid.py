"""Compact overview: every shot as [ref | ours] at 256x144, 3 shots per row, 30 shots per sheet.

usage: python grid.py <ours_dir> <out_prefix> [--which first|last|mid] [--root .] [--ref ref.mp4]
Good for spotting which shots drift from the reference at a glance; use shotsheet.py / strip.py to zoom in.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

from _shots import load_shots, ours_frame, project_root, ref_frames, report_missing

ap = argparse.ArgumentParser()
ap.add_argument('ours_dir')
ap.add_argument('prefix')
ap.add_argument('--which', choices=['mid', 'first', 'last'], default='first')
ap.add_argument('--root')
ap.add_argument('--ref')
a = ap.parse_args()
if not os.path.isdir(a.ours_dir):
    sys.exit(f'ours_dir not found: {a.ours_dir} (the folder of `remotion render --sequence` frames)')
root = project_root(a.root)
shots = [(sid, {'mid': (f0 + f1) // 2, 'first': f0, 'last': f1}[a.which]) for sid, f0, f1 in load_shots(root)]
refdir = ref_frames(root, a.ref)
W, H, per = 256, 144, 30
missing = []
for k in range(0, len(shots), per):
    ch = shots[k:k + per]
    rows = (len(ch) + 2) // 3
    sh = Image.new('RGB', (3 * (2 * W + 12), rows * (H + 4)), (40, 40, 40))
    d = ImageDraw.Draw(sh)
    for i, (sid, f) in enumerate(ch):
        x, y = (i % 3) * (2 * W + 12), (i // 3) * (H + 4)
        sh.paste(Image.open(os.path.join(refdir, 'r_%04d.jpg' % (f + 1))).resize((W, H)), (x, y))
        p = ours_frame(a.ours_dir, f)
        if p:
            sh.paste(Image.open(p).convert('RGB').resize((W, H)), (x + W + 2, y))
        else:
            missing.append(f)
        d.rectangle([x, y, x + 70, y + 13], fill=(0, 0, 0))
        d.text((x + 2, y + 1), f'{sid} f{f}', fill=(255, 255, 0))
    out = f'{a.prefix}_{k // per + 1}.jpg'
    sh.save(out, quality=85)
    print(out)
report_missing(missing)
