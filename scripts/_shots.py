"""Shared helpers for the QA sheet scripts (grid.py, shotsheet.py, strip.py).

The Remotion project keeps its cut list in src/core/timeline.ts as lines like
    {id: 'S01', start: 0.0, end: 0.933, act: 'act1', kind: 'digital clock'},
    {id: 'S57', start: 34.033, end: DURATION_S, ...},
and the composition length in `export const DURATION_FRAMES = 1079;`.
Reference frames are cached as 640x360 JPEGs, file index = frame + 1.
"""
import os
import re
import subprocess
import sys

FPS = 30
# tolerant: any spacing after the colons, single or double quotes
SHOT_RE = re.compile(r"""id:\s*['\"](S\d+)['\"]\s*,\s*start:\s*([\d.]+)\s*,\s*end:\s*([\w.]+)""")


def project_root(arg=None):
    """--root, else $PV_ROOT, else the current directory."""
    return os.path.abspath(arg or os.environ.get('PV_ROOT') or os.getcwd())


def reference_video(arg=None):
    ref = arg or os.environ.get('REF_VIDEO')
    if not ref:
        raise SystemExit('reference video unknown: pass --ref <file> or set REF_VIDEO')
    return ref


def load_shots(root, fps=FPS):
    """[(shot_id, first_frame, last_frame)] from src/core/timeline.ts."""
    p = os.path.join(root, 'src', 'core', 'timeline.ts')
    if not os.path.exists(p):
        raise SystemExit(f'{p} not found: run from the Remotion project root or pass --root')
    src = open(p, encoding='utf-8').read()
    m = re.search(r'DURATION_FRAMES\s*=\s*(\d+)', src)
    total = int(m.group(1)) if m else None
    shots = []
    for m in SHOT_RE.finditer(src):
        start = float(m.group(2))
        end = float(m.group(3)) if m.group(3)[0].isdigit() else (total / fps if total else None)
        if end is None:
            raise SystemExit(f'{m.group(1)}: symbolic end and no DURATION_FRAMES in timeline.ts')
        f0 = round(start * fps)
        shots.append((m.group(1), f0, max(f0, round(end * fps) - 1)))
    n_id = len(re.findall(r"""\bid:\s*['\"]""", src))
    if n_id != len(shots):
        print(f'warning: timeline.ts has {n_id} quoted id: entries but {len(shots)} shots were parsed: check the lines SHOT_RE misses', file=sys.stderr)
    if not shots:
        raise SystemExit('no shots found in src/core/timeline.ts')
    return shots


def ref_frames(root, ref=None):
    """Directory of cached 640x360 reference frames (extracted on first use)."""
    d = os.path.join(root, 'out', 'review', 'ref360')
    if not os.path.isdir(d) or not os.listdir(d):
        os.makedirs(d, exist_ok=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', reference_video(ref), '-vf', 'scale=640:360', '-q:v', '3',
                        os.path.join(d, 'r_%04d.jpg')], check=True)
    return d


def ours_frame(ours_dir, f):
    """Our rendered frame `f` from a `remotion render --sequence` folder (element-<n>.jpeg, any zero padding)."""
    for w in range(1, 7):
        for ext in ('jpeg', 'jpg', 'png'):
            p = os.path.join(ours_dir, f'element-{f:0{w}d}.{ext}')
            if os.path.exists(p):
                return p
    return None


def report_missing(missing):
    """Say on stderr which of our frames were absent (their half of the sheet stays blank)."""
    if missing:
        print(f'missing ours frames: {len(missing)} (first: f{missing[0]})', file=sys.stderr)
