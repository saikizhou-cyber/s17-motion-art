"""
Side-by-side QA: reference video frame (left) vs our render (right).

  python compare.py --frames 120,126,133 --tag act2 --ref ../reference.mp4
  python compare.py --range 119-205 --every 6 --tag act2          # REF_VIDEO set in the environment

Run from the Remotion project root (or pass --root). Renders the needed frame range of
composition --comp (default PV) with `npx remotion render --sequence`, grabs the same frames
from the reference, and writes out/cmp/<tag>/compare.jpg (pairs kept in out/cmp/<tag>/pairs/).
Frames are 30 fps output frame numbers. A lock-file semaphore (PV_RENDER_SLOTS, default 3)
keeps parallel agents from running too many renders at once.
"""
import argparse
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

try:
    from _shots import SHOT_RE
except ImportError:  # copied without its sibling
    SHOT_RE = re.compile(r"""id:\s*['\"](S\d+)['\"]\s*,\s*start:\s*([\d.]+)\s*,\s*end:\s*([\w.]+)""")

ROOT = os.path.abspath(os.environ.get('PV_ROOT') or os.getcwd())
FPS = 30


def parse_frames(a):
    if a.frames:
        return sorted({int(x) for x in a.frames.split(',') if x.strip()})
    lo, hi = (int(x) for x in a.range.split('-'))
    return list(range(lo, hi + 1, a.every))


SLOTS = int(os.environ.get('PV_RENDER_SLOTS', '3'))
SLOT_DIR = os.path.join(ROOT, 'out', '.render-slots')
STALE_S = 15 * 60


def acquire_slot():
    """Block until one of SLOTS render slots is free (lock files; stale after 15 min)."""
    import time
    os.makedirs(SLOT_DIR, exist_ok=True)
    waited = 0
    while True:
        for i in range(SLOTS):
            p = os.path.join(SLOT_DIR, f'slot{i}.lock')
            try:
                if os.path.exists(p) and time.time() - os.path.getmtime(p) > STALE_S:
                    os.remove(p)
                fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return p
            except FileExistsError:
                continue
            except OSError:
                continue
        if waited % 30 == 0:
            print(f'waiting for a render slot ({SLOTS} busy)...', flush=True)
        time.sleep(2)
        waited += 2


def release_slot(p):
    try:
        os.remove(p)
    except OSError:
        pass


def shot_of(frame):
    # parse timeline.ts lazily for labels
    p = os.path.join(ROOT, 'src', 'core', 'timeline.ts')
    if not os.path.exists(p):
        return ''
    src = open(p, encoding='utf-8').read()
    t = frame / FPS
    for m in SHOT_RE.finditer(src):
        sid, st, en = m.group(1), float(m.group(2)), m.group(3)
        en = 99.0 if not en[0].isdigit() else float(en)
        if st <= t < en:
            return sid
    return '?'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--frames')
    ap.add_argument('--range')
    ap.add_argument('--every', type=int, default=5)
    ap.add_argument('--tag', default='cmp')
    ap.add_argument('--ref', default=os.environ.get('REF_VIDEO'), help='reference video (default: $REF_VIDEO)')
    ap.add_argument('--root', help='Remotion project root (default: $PV_ROOT or cwd)')
    ap.add_argument('--comp', default='PV', help='composition id')
    ap.add_argument('--scale', type=float, default=0.5)
    ap.add_argument('--cols', type=int, default=1, help='pairs per row')
    ap.add_argument('--no-render', action='store_true', help='reuse existing renders')
    a = ap.parse_args()
    if not a.frames and not a.range:
        ap.error('--frames or --range required')
    if not a.ref:
        ap.error('--ref <reference video> required (or set REF_VIDEO)')
    global ROOT, SLOT_DIR
    if a.root:
        ROOT = os.path.abspath(a.root)
        SLOT_DIR = os.path.join(ROOT, 'out', '.render-slots')
    try:
        frames = parse_frames(a)
    except ValueError:
        ap.error('bad --frames/--range: use --frames 120,126,133 or --range 119-205 (with --every >= 1)')
    if not frames:
        ap.error('no frames selected: check --range lo-hi (lo <= hi)')
    out = os.path.join(ROOT, 'out', 'cmp', a.tag)
    ours_dir = os.path.join(out, 'ours')
    ref_dir = os.path.join(out, 'ref')
    pairs_dir = os.path.join(out, 'pairs')
    for d in (ours_dir, ref_dir, pairs_dir):
        os.makedirs(d, exist_ok=True)

    lo, hi = min(frames), max(frames)
    if not a.no_render:
        # our render: one contiguous sequence render (fast, single bundle).
        # A machine-wide semaphore keeps parallel agents from exhausting RAM.
        for x in os.listdir(ours_dir):
            os.remove(os.path.join(ours_dir, x))
        slot = acquire_slot()
        try:
            cmd = f'npx remotion render {a.comp} "{ours_dir}" --sequence --frames={lo}-{hi} --image-format=jpeg --concurrency=2 --log=error'
            r = subprocess.run(cmd, shell=True, cwd=ROOT)
        finally:
            release_slot(slot)
        if r.returncode != 0:
            sys.exit('remotion render failed')
    # reference frames (drop the previous run's, or leftovers would pass the count check below)
    for x in os.listdir(ref_dir):
        if x.startswith('r_') and x.endswith('.jpg'):
            os.remove(os.path.join(ref_dir, x))
    sel = '+'.join(f'eq(n\\,{f})' for f in frames)
    subprocess.run(
        ['ffmpeg', '-hide_banner', '-v', 'error', '-i', a.ref, '-vf', f'select={sel}', '-vsync', '0', '-q:v', '2', '-y',
         os.path.join(ref_dir, 'r_%04d.jpg')],
        check=True,
    )
    got = sum(1 for x in os.listdir(ref_dir) if x.startswith('r_') and x.endswith('.jpg'))
    if got < len(frames):
        sys.exit('some requested frames are past the end of the reference video')
    W, H = int(1280 * a.scale), int(720 * a.scale)
    tiles = []
    for i, f in enumerate(frames):
        ref = Image.open(os.path.join(ref_dir, f'r_{i + 1:04d}.jpg')).convert('RGB').resize((W, H))
        # remotion zero-pads names to the width of the highest frame number
        cands = [x for x in os.listdir(ours_dir) if x.startswith('element-') and x[8:].split('.')[0].isdigit() and int(x[8:].split('.')[0]) == f]
        ours_path = os.path.join(ours_dir, cands[0]) if cands else None
        ours = Image.open(ours_path).convert('RGB').resize((W, H)) if ours_path else Image.new('RGB', (W, H), 'magenta')
        pair = Image.new('RGB', (W * 2 + 6, H + 22), (30, 30, 30))
        pair.paste(ref, (0, 22))
        pair.paste(ours, (W + 6, 22))
        d = ImageDraw.Draw(pair)
        d.text((6, 4), f'REF  f{f}  t={f / FPS:.3f}s  {shot_of(f)}', fill=(255, 220, 0))
        d.text((W + 12, 4), 'OURS', fill=(0, 220, 255))
        pair.save(os.path.join(pairs_dir, f'p_{f:04d}.jpg'), quality=90)
        tiles.append(pair)
    cols = max(1, a.cols)
    rows = (len(tiles) + cols - 1) // cols
    tw, th = tiles[0].size
    sheet = Image.new('RGB', (tw * cols, th * rows), (0, 0, 0))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * tw, (i // cols) * th))
    path = os.path.join(out, 'compare.jpg')
    sheet.save(path, quality=88)
    print(path)


if __name__ == '__main__':
    main()
