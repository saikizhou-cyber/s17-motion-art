"""Frame strip of one passage: rows of [ref | ours] at 320x180 from frame f0 to f1 every `step` frames.

usage: python strip.py <ours_dir> <out.jpg> <f0> <f1> <step> [--root .] [--ref ref.mp4]
Use it for motion: cadence (does the reference hold on 2s?), easing, where a move starts and lands.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

from _shots import ours_frame, project_root, ref_frames, report_missing

ap = argparse.ArgumentParser()
ap.add_argument('ours_dir')
ap.add_argument('out')
ap.add_argument('f0', type=int)
ap.add_argument('f1', type=int)
ap.add_argument('step', type=int)
ap.add_argument('--root')
ap.add_argument('--ref')
a = ap.parse_args()
if not os.path.isdir(a.ours_dir):
    sys.exit(f'ours_dir not found: {a.ours_dir} (the folder of `remotion render --sequence` frames)')
refdir = ref_frames(project_root(a.root), a.ref)
fs = list(range(a.f0, a.f1 + 1, a.step))
W, H = 320, 180
sheet = Image.new('RGB', (W * 2 + 6, (H + 3) * len(fs)), (40, 40, 40))
d = ImageDraw.Draw(sheet)
missing = []
for i, f in enumerate(fs):
    y = i * (H + 3)
    sheet.paste(Image.open(os.path.join(refdir, 'r_%04d.jpg' % (f + 1))).resize((W, H)), (0, y))
    p = ours_frame(a.ours_dir, f)
    if p:
        sheet.paste(Image.open(p).convert('RGB').resize((W, H)), (W + 6, y))
    else:
        missing.append(f)
    d.text((3, y + 3), f'f{f}', fill=(255, 255, 0))
sheet.save(a.out, quality=85)
print(a.out)
report_missing(missing)
