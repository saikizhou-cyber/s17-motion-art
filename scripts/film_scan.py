"""Scan a rendered film for freezes, black frames and white flashes, and say which ones the reference does not have.

usage: python film_scan.py <ours.mp4> [--ref reference.mp4 (default $REF_VIDEO)] [--root .] [--freeze-min 0.2] [--freeze-noise 0.003]

A frame-by-frame review of sheets catches what is wrong inside a shot, not a picture that silently stopped
moving for a second, a stray black frame at a chunk seam or a flash nobody planned. One ffmpeg pass per video
(freezedetect, blackdetect, per-frame luma) finds them. With --ref (or $REF_VIDEO) the same scan runs on the reference and
every event is labelled: `OURS ONLY` (likely a defect), `both` (intended: the reference does it too) or
`ref only` (the reference holds / flashes / goes black here and we do not). Times are mapped to shot ids when
src/core/timeline.ts is found under --root (default $PV_ROOT or cwd).

Freezes shorter than --freeze-min (default 0.2 s = 6 frames) are ignored, so held-on-2s animation is not
flagged. A flash is a frame brighter than 150 (of 255) whose luma is >= 60 above both frames two either side.

With --ref and a timeline it also compares how much each shot MOVES (mean frame difference and the share of
near-still frames, cut frames excluded) and lists the shots that are much stiller (a layer stopped, a clip
ended early, a hold left in) or much busier (jitter, drift, an AI clip moving more than the reference).
On the case study this flagged S36 / S38 (42 % -> 79 % and 33 % -> 91 % still frames), S27 (stiller) and
S49 / S50 (busier), and no other shot.
Idea after the time overview of Zane-0x5a/remotion-director (MIT); this is an independent implementation.
"""
import argparse
import os
import re
import subprocess
import sys

import numpy as np

_FREEZE_S = re.compile(r'freeze_start:\s*([\d.]+)')
_FREEZE_E = re.compile(r'freeze_end:\s*([\d.]+)')
_BLACK = re.compile(r'black_start:([\d.]+)\s+black_end:([\d.]+)')
_PTS = re.compile(r'pts_time:\s*(\S+)')
_YAVG = re.compile(r'lavfi\.signalstats\.YAVG=(\S+)')


def scan(video, noise, freeze_min):
    vf = (f'freezedetect=n={noise}:d={freeze_min},blackdetect=d=0.03:pix_th=0.10,'
          'scale=160:-2,signalstats,metadata=mode=print:key=lavfi.signalstats.YAVG')
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', video, '-map', '0:v:0', '-vf', vf, '-f', 'null', '-'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        sys.exit(f'ffmpeg failed on {video}: {r.stderr.strip()[-300:]}')
    log = r.stderr
    dur = float(re.search(r'Duration:\s*(\d+):(\d+):([\d.]+)', log).group(3)) + \
        60 * float(re.search(r'Duration:\s*(\d+):(\d+)', log).group(2)) + 3600 * float(re.search(r'Duration:\s*(\d+)', log).group(1))
    starts = [float(x) for x in _FREEZE_S.findall(log)]
    ends = [float(x) for x in _FREEZE_E.findall(log)]
    freezes = [(s, ends[i] if i < len(ends) else dur) for i, s in enumerate(starts)]
    blacks = [(float(a), float(b)) for a, b in _BLACK.findall(log)]
    luma, t = [], None
    for line in log.splitlines():
        m = _PTS.search(line)
        if m:
            t = float(m.group(1))
            continue
        m = _YAVG.search(line)
        if m and t is not None:
            luma.append((t, float(m.group(1))))
            t = None
    return {'freeze': freezes, 'black': blacks, 'flash': flashes(luma, 60, 150)}, dur, luma


def flashes(luma, jump, floor):
    out = []
    for i in range(2, len(luma) - 2):
        t, y = luma[i]
        if y > floor and y - max(luma[i - 2][1], luma[i + 2][1]) >= jump:
            out.append((t, t + 1 / 30))
    return out


def overlaps(a, b, slack=2 / 30):
    return a[0] < b[1] + slack and b[0] < a[1] + slack


def gray(video, w=160, h=90):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vf', f'scale={w}:{h}', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'],
                       capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w).astype(np.int16)


def motion_report(ours_video, ref_video, shots):
    """Shots whose amount of motion differs strongly from the reference's."""
    o, r = gray(ours_video), gray(ref_video)
    out = []
    for sid, f0, f1 in shots:
        if f1 - f0 < 6 or f1 >= min(len(o), len(r)):
            continue
        do = np.abs(np.diff(o[f0 + 1:f1 + 1], axis=0)).mean((1, 2))  # skip the cut frame itself
        dr = np.abs(np.diff(r[f0 + 1:f1 + 1], axis=0)).mean((1, 2))
        ratio = (do.mean() + 0.4) / (dr.mean() + 0.4)
        so, sr = (do < 0.3).mean(), (dr < 0.3).mean()
        if ratio < 0.6 or so - sr >= 0.35:
            out.append((sid, f0, f1, dr.mean(), do.mean(), sr, so, 'OURS STILLER'))
        elif ratio > 2.0 or (sr - so >= 0.35 and ratio > 1.3):
            out.append((sid, f0, f1, dr.mean(), do.mean(), sr, so, 'OURS BUSIER'))
    return out


def load_timeline(root):
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from _shots import load_shots
        return load_shots(root)
    except BaseException:
        return None


def shot_namer(shots):
    if not shots:
        return lambda t: ''
    return lambda t: next((sid for sid, f0, f1 in shots if f0 <= round(t * 30) <= f1), '')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ours')
    ap.add_argument('--ref', default=os.environ.get('REF_VIDEO'), help='reference video (default: $REF_VIDEO)')
    ap.add_argument('--root')
    ap.add_argument('--freeze-min', type=float, default=0.2, help='shortest freeze reported, seconds')
    ap.add_argument('--freeze-noise', type=float, default=0.003, help='freezedetect noise tolerance')
    a = ap.parse_args()
    for v in (a.ours, a.ref):
        if v and not os.path.exists(v):
            sys.exit(f'not found: {v}')
    shots = load_timeline(os.path.abspath(a.root or os.environ.get('PV_ROOT') or os.getcwd()))
    shot = shot_namer(shots)
    ours, dur, ours_luma = scan(a.ours, a.freeze_noise, a.freeze_min)
    ref, ref_luma = None, None
    if a.ref:
        ref, _, ref_luma = scan(a.ref, a.freeze_noise, a.freeze_min)
    # matching uses a looser flash test on the other film, so a flash just under the threshold on one
    # side does not show up as a difference
    loose = {'ours': flashes(ours_luma, 30, 120), 'ref': flashes(ref_luma, 30, 120) if ref_luma else []}
    rows = []
    for kind, events in ours.items():
        for e in events:
            other = ref[kind] + (loose['ref'] if kind == 'flash' else []) if ref is not None else []
            tag = '' if ref is None else ('both' if any(overlaps(e, r) for r in other) else 'OURS ONLY')
            rows.append((e[0], kind, e, tag))
    if ref is not None:
        for kind, events in ref.items():
            other = ours[kind] + (loose['ours'] if kind == 'flash' else [])
            for e in events:
                if not any(overlaps(e, o) for o in other):
                    rows.append((e[0], kind, e, 'ref only'))
    rows.sort()
    print(f'{os.path.basename(a.ours)}: {dur:.2f} s' + (f'  vs  {os.path.basename(a.ref)}' if a.ref else ''))
    print(f'{"time (s)":>15}  {"frames":>11}  {"kind":6}  {"len":>6}  {"shot":5}  status')
    for _, kind, (s, e), tag in rows:
        print(f'{s:7.2f}-{e:7.2f}  {round(s * 30):5d}-{round(e * 30):5d}  {kind:6}  {e - s:5.2f}s  {shot(s):5}  {tag}')
    if ref is not None:
        bad = sum(1 for r in rows if r[3] == 'OURS ONLY')
        print(f'\n{bad} event(s) the reference does not have; check each one on the frames.')
        if shots:
            moves = motion_report(a.ours, a.ref, shots)
            print(f'\nmotion vs reference: {len(moves)} shot(s) differ' + (' (mean frame diff / share of still frames)' if moves else ''))
            for sid, f0, f1, mr, mo, sr, so, tag in moves:
                print(f'  {sid:5} {f0:5d}-{f1:5d}  ref {mr:5.2f} / {sr:4.0%} still   ours {mo:5.2f} / {so:4.0%} still   {tag}')


if __name__ == '__main__':
    main()
