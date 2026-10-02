"""Per-shot contact sheet: reference (left) vs ours (right), one row per shot.

usage: python shotsheet.py <ours_dir> <out_prefix> [--per 10] [--which mid|first|last] [--root .] [--ref ref.mp4]

<ours_dir> holds `npx remotion render PV <ours_dir> --sequence --image-format=jpeg` output
(full film or the frames you need). Writes <out_prefix>_01.jpg, _02.jpg ...
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

from _shots import FPS, load_shots, ours_frame, project_root, ref_frames, report_missing

ap = argparse.ArgumentParser()
ap.add_argument('ours_dir')
ap.add_argument('prefix')
ap.add_argument('--per', type=int, default=10, help='shots per sheet')
ap.add_argument('--which', choices=['mid', 'first', 'last'], default='mid')
ap.add_argument('--root')
ap.add_argument('--ref')
a = ap.parse_args()
if not os.path.isdir(a.ours_dir):
    sys.exit(f'ours_dir not found: {a.ours_dir} (the folder of `remotion render --sequence` frames)')
root = project_root(a.root)
rows = [(sid, {'mid': (f0 + f1) // 2, 'first': f0, 'last': f1}[a.which]) for sid, f0, f1 in load_shots(root)]
refdir = ref_frames(root, a.ref)
W, H = 640, 360
missing = []
for k in range(0, len(rows), a.per):
    chunk = rows[k:k + a.per]
    sheet = Image.new('RGB', (W * 2 + 10, (H + 4) * len(chunk)), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    for i, (sid, f) in enumerate(chunk):
        y = i * (H + 4)
        sheet.paste(Image.open(os.path.join(refdir, 'r_%04d.jpg' % (f + 1))).resize((W, H)), (0, y))
        p = ours_frame(a.ours_dir, f)
        if p:
            sheet.paste(Image.open(p).convert('RGB').resize((W, H)), (W + 10, y))
        else:
            missing.append(f)
        d.rectangle([0, y, 150, y + 22], fill=(0, 0, 0))
        d.text((4, y + 4), f'{sid} f{f} t={f / FPS:.2f}', fill=(255, 255, 0))
    out = f'{a.prefix}_{k // a.per + 1:02d}.jpg'
    sheet.save(out, quality=82)
    print(out)
report_missing(missing)
