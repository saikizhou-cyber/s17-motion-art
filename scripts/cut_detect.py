"""Shot cuts of a reference video, plus the windows a human or agent must still look at.

usage: python cut_detect.py <video> [--out cuts.json] [--sheets DIR] [--truth] [--root .] [--hard 10] [--soft 4]

One ffmpeg pass (scdet + mafd). A fixed threshold is wrong both ways on fast PVs (it misses cuts in
dark shots and splits fast single shots), so a frame is a cut when its scdet score is >= --hard, or
>= --soft while being at least 2x every other frame within 0.3 s (adjacent frames excluded: they carry
the cut's after-image). Candidates that fail the rule are not thrown away: they become review windows,
and --sheets writes one contact sheet per window (every frame, numbered) so the misses get checked by eye.
The detector gives a first cut list to correct, not the final one: confirm every cut on the frames.

--truth compares with the hand cut list in src/core/timeline.ts (recall / precision at +-1 frame), e.g.
to audit an existing breakdown. Measured on the case-study reference (36 s, 56 cuts, many 1-2 frame
shots and white flashes): recall 0.77, precision 0.88 with the defaults, and the review windows held
most of the misses.

Cut rule ported from zenstory-ai/video-recap-skills, skills/video-reference/scripts/reference_measure.py
(commit 2d2b183), MIT License, Copyright (c) 2026 PiteChen.
"""
import argparse
import bisect
import json
import os
import re
import subprocess
import sys

ISOLATION_RATIO = 2.0
ISOLATION_WINDOW_S = 0.3
SCORE_FLOOR = 2.0
REVIEW_PAD_S = 0.2
REVIEW_JOIN_S = 0.5
EDGE_S = 0.05
_SCDET = re.compile(r"lavfi\.scd\.score\s*[:=]\s*(-?\d+(?:\.\d+)?)\s*,?\s*lavfi\.scd\.time\s*[:=]\s*(-?\d+(?:\.\d+)?)")
_PTS = re.compile(r"pts_time:\s*(\S+)")
_MAFD = re.compile(r"lavfi\.scd\.mafd=(\S+)")


def probe(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate:format=duration',
                        '-of', 'json', video], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'ffprobe failed on {video}: {r.stderr.strip()[:200]}')
    info = json.loads(r.stdout)
    num, den = info['streams'][0]['r_frame_rate'].split('/')
    return float(num) / float(den), float(info['format']['duration'])


def sides(series, times, i, adjacent):
    """Highest value before and after series[i] within the isolation window, adjacent frames excluded."""
    t = series[i][0]
    lo = bisect.bisect_left(times, t - ISOLATION_WINDOW_S - 1e-9)
    hi = bisect.bisect_right(times, t + ISOLATION_WINDOW_S + 1e-9)
    return (max((v for u, v in series[lo:i] if t - u > adjacent), default=0.0),
            max((v for u, v in series[i + 1:hi] if u - t > adjacent), default=0.0))


def scan(video, duration):
    vf = f'scale=320:-2,scdet=threshold={SCORE_FLOOR:g},metadata=mode=print:key=lavfi.scd.mafd'
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', video, '-map', '0:v:0', '-vf', vf, '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        sys.exit(f'ffmpeg failed: {r.stderr.strip()[-300:]}')
    scores = {}
    for m in _SCDET.finditer(r.stderr):
        s, t = float(m.group(1)), round(float(m.group(2)), 3)
        if EDGE_S < t < duration - EDGE_S:
            scores[t] = max(s, scores.get(t, s))
    mafd, t = [], None
    for line in r.stderr.splitlines():
        m = _PTS.search(line)
        if m:
            t = float(m.group(1))
            continue
        m = _MAFD.search(line)
        if m and t is not None:
            mafd.append((round(t, 3), float(m.group(1))))
            t = None
    return [[t, scores[t]] for t in sorted(scores)], mafd


def detect(scores, mafd, fps, duration, hard, soft):
    adjacent = 1.5 / fps
    times = [t for t, _ in scores]
    cuts, suppressed = [], []
    for i, (t, s) in enumerate(scores):
        if s < soft:
            continue
        if s < hard and s < ISOLATION_RATIO * max(sides(scores, times, i, adjacent)):
            suppressed.append(t)
            continue
        if cuts and t - cuts[-1][0] <= adjacent:  # one cut spread over two frames
            if s > cuts[-1][1]:
                cuts[-1] = (t, s)
            continue
        cuts.append((t, s))
    # a cut out of fast motion scores low; a one-sided mafd peak still marks it for review
    mt = [u for u, _ in mafd]
    for i, (t, v) in enumerate(mafd):
        if v < SCORE_FLOOR or not EDGE_S < t < duration - EDGE_S:
            continue
        before, after = sides(mafd, mt, i, adjacent)
        if v >= max(before, after) and v >= ISOLATION_RATIO * min(before, after):
            suppressed.append(t)
    cut_t = [t for t, _ in cuts]
    windows = []
    for t in sorted(set(suppressed)):
        if any(abs(t - c) <= adjacent for c in cut_t):
            continue
        if windows and t - windows[-1][1] <= REVIEW_JOIN_S:
            windows[-1][1] = t
        else:
            windows.append([t, t])
    windows = [[round(max(0.0, a - REVIEW_PAD_S), 2), round(min(duration, b + REVIEW_PAD_S), 2)] for a, b in windows]
    return cuts, windows


def sheets(video, windows, fps, out_dir):
    """One labelled contact sheet per review window: every frame at 320 px, frame number in the corner."""
    from PIL import Image, ImageDraw
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for k, (a, b) in enumerate(windows, 1):
        f0, f1 = int(a * fps), int(b * fps)
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vf', f"select='between(n\\,{f0}\\,{f1})',scale=320:180",
                            '-vsync', '0', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
        frame_bytes = 320 * 180 * 3
        tiles = [Image.frombytes('RGB', (320, 180), r.stdout[i:i + frame_bytes]) for i in range(0, len(r.stdout) - frame_bytes + 1, frame_bytes)]
        if not tiles:
            continue
        cols = min(8, len(tiles))
        rows = (len(tiles) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * 322, rows * 182), (30, 30, 30))
        d = ImageDraw.Draw(sheet)
        for i, im in enumerate(tiles):
            x, y = (i % cols) * 322, (i // cols) * 182
            sheet.paste(im, (x, y))
            d.rectangle([x, y, x + 44, y + 14], fill=(0, 0, 0))
            d.text((x + 3, y + 2), f'f{f0 + i}', fill=(255, 220, 0))
        p = os.path.join(out_dir, f'review_{k:02d}_f{f0}-{f1}.jpg')
        sheet.save(p, quality=85)
        paths.append(p)
    return paths


def compare(cut_frames, root, fps):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _shots import load_shots
    truth = sorted({f0 for _, f0, _ in load_shots(root, fps) if f0 > 0})
    used, missed = set(), []
    for g in truth:
        near = [p for p in cut_frames if abs(p - g) <= 1 and p not in used]
        if near:
            used.add(min(near, key=lambda p: abs(p - g)))
        else:
            missed.append(g)
    extra = [p for p in cut_frames if p not in used]
    tp = len(truth) - len(missed)
    print(f'vs timeline.ts: {len(truth)} cuts, found {tp}  recall {tp / max(1, len(truth)):.2f}  '
          f'precision {tp / max(1, len(cut_frames)):.2f}')
    print(f'  missed (frames): {missed}')
    print(f'  extra  (frames): {extra}')
    return missed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--out', help='write cuts and review windows as JSON')
    ap.add_argument('--sheets', help='folder for one contact sheet per review window')
    ap.add_argument('--truth', action='store_true', help='compare with src/core/timeline.ts')
    ap.add_argument('--root', help='Remotion project root for --truth (default: $PV_ROOT or cwd)')
    ap.add_argument('--hard', type=float, default=10.0, help='scdet score that is always a cut')
    ap.add_argument('--soft', type=float, default=4.0, help='scdet score that is a cut when isolated')
    a = ap.parse_args()
    if not os.path.exists(a.video):
        sys.exit(f'not found: {a.video}')
    if not SCORE_FLOOR * ISOLATION_RATIO <= a.soft <= a.hard:
        sys.exit(f'need {SCORE_FLOOR * ISOLATION_RATIO:g} <= --soft <= --hard')
    fps, duration = probe(a.video)
    scores, mafd = scan(a.video, duration)
    cuts, windows = detect(scores, mafd, fps, duration, a.hard, a.soft)
    frames = [round(t * fps) for t, _ in cuts]
    print(f'{len(cuts)} cuts, {len(windows)} review windows ({sum(b - a for a, b in windows):.1f} s to check) in {duration:.2f} s @ {fps:g} fps')
    print('cuts (frame: score): ' + ', '.join(f'{f}:{s:.0f}' for f, (_, s) in zip(frames, cuts)))
    print('review windows (s): ' + ', '.join(f'{x:.2f}-{y:.2f}' for x, y in windows))
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump({'fps': fps, 'duration_s': duration, 'settings': {'hard': a.hard, 'soft': a.soft},
                       'cuts': [{'frame': fr, 'time_s': t, 'score': s} for fr, (t, s) in zip(frames, cuts)],
                       'review_windows_s': windows}, f, indent=1)
        print(f'-> {a.out}')
    if a.sheets and windows:
        for p in sheets(a.video, windows, fps, a.sheets):
            print(f'-> {p}')
    if a.truth:
        root = os.path.abspath(a.root or os.environ.get('PV_ROOT') or os.getcwd())
        compare(frames, root, fps)


if __name__ == '__main__':
    main()
