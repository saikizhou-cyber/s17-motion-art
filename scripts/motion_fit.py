"""Measure how an element moves in a video and turn it into Remotion code (easing or spring).

usage:
  python motion_fit.py <video> --from F0 --to F1 --color R,G,B [--tol 40] [--region x0,y0,x1,y1] [--channel x|y|w|h|z] [--fps 30]
  python motion_fit.py <video> --from F0 --to F1 --thr 110 [--dark] [--region ...]

Per frame the element is a mask (pixels near --color, or brighter / darker than --thr) inside --region.
The script tracks its centre (x, y) and size (w, h, 1-99 % extents), picks the channel that changes most,
finds where the move starts and settles, and reports:
  * the cadence: whether the element moves every frame or holds on 2s / 3s (animation stepped on twos);
  * the best `Easing.bezier(...)` for an `interpolate()` over the measured span, and the best `spring()`
    config, each with its fit error, printed as ready-to-paste Remotion code.
Spring curves follow Remotion's own implementation exactly: under-damped springs are the analytic damped
oscillator; once damping reaches the critical value (zeta >= 1) Remotion uses the critically damped
solution, so only stiffness matters there and more damping changes nothing.
Measure the reference this way and drive the rebuild with the numbers instead of eyeballed easing.
A fit error above 0.05 (of the move) is reported as a poor fit: split compound moves into single ones.
A perspective fly-in eases its DEPTH and its size follows as 1/depth, so a width fit fails; when a size fit is
poor the script tries depth and says to use --channel z, which prints `scale = 1 / ...` (case study S40 fly-in:
width fit error 0.058, depth fit 0.012).
Strong ease-outs whose last frames move < 1 px get a shorter span; the fitted curve still renders the same.
Inspired by ljq-broll's motion forensics and apple-motion's spring fitting (both MIT); own implementation.
"""
import argparse
import os
import subprocess
import sys

import numpy as np
from scipy.optimize import minimize


def frames(video, f0, f1):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', video],
                       capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        sys.exit(f'cannot read {video}')
    w, h = (int(v) for v in r.stdout.strip().split(',')[:2])
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', video, '-vf', f"select='between(n\\,{f0}\\,{f1})'", '-vsync', '0',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    n = len(r.stdout) // (w * h * 3)
    if n == 0:
        sys.exit(f'no frames {f0}-{f1} in {video}')
    return np.frombuffer(r.stdout[:n * w * h * 3], np.uint8).reshape(n, h, w, 3)


def measure(fr, a):
    ox = oy = 0
    if a.region:
        x0, y0, x1, y1 = (int(v) for v in a.region.split(','))
        fr, ox, oy = fr[:, y0:y1, x0:x1], x0, y0
    out = []
    for im in fr.astype(np.int16):
        if a.color:
            c = np.array([int(v) for v in a.color.split(',')])
            m = np.sqrt(((im - c) ** 2).sum(-1)) < a.tol
        else:
            lum = im.mean(-1)
            m = lum < a.thr if a.dark else lum > a.thr
        ys, xs = np.nonzero(m)
        if len(xs) < 4:
            out.append((np.nan,) * 4)
            continue
        out.append((xs.mean() + ox, ys.mean() + oy, np.percentile(xs, 99) - np.percentile(xs, 1), np.percentile(ys, 99) - np.percentile(ys, 1)))
    return np.array(out)


def remotion_spring(n, fps, stiffness, damping, mass=1.0):
    """spring({frame: i, fps, config}) for i in 0..n-1, as Remotion computes it (from 0 to 1)."""
    t = np.arange(n) / fps
    w0 = np.sqrt(stiffness / mass)
    z = damping / (2 * np.sqrt(stiffness * mass))
    if z < 1:
        wd = w0 * np.sqrt(1 - z * z)
        return 1 - np.exp(-z * w0 * t) * (np.cos(wd * t) + z * w0 / wd * np.sin(wd * t))
    return 1 - np.exp(-w0 * t) * (1 + w0 * t)


def bezier(x, x1, y1, x2, y2):
    """CSS / Remotion Easing.bezier(x1, y1, x2, y2) evaluated at progress x (bisection on the x curve)."""
    lo, hi = np.zeros_like(x), np.ones_like(x)
    for _ in range(40):
        s = (lo + hi) / 2
        bx = 3 * (1 - s) ** 2 * s * x1 + 3 * (1 - s) * s ** 2 * x2 + s ** 3
        lo, hi = np.where(bx < x, s, lo), np.where(bx < x, hi, s)
    s = (lo + hi) / 2
    return 3 * (1 - s) ** 2 * s * y1 + 3 * (1 - s) * s ** 2 * y2 + s ** 3


def cadence(v):
    """Hold length while moving: 1 = every frame, 2 = on twos, 3 = on threes."""
    d = np.abs(np.diff(v))
    moving = d > 0.25
    if moving.sum() < 3:
        return None
    idx = np.nonzero(moving)[0]
    runs = np.diff(idx)
    return int(np.median(runs)) if len(runs) else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video')
    ap.add_argument('--from', dest='f0', type=int, required=True)
    ap.add_argument('--to', dest='f1', type=int, required=True)
    ap.add_argument('--color', help='R,G,B of the element')
    ap.add_argument('--tol', type=float, default=40)
    ap.add_argument('--thr', type=float, default=110)
    ap.add_argument('--dark', action='store_true')
    ap.add_argument('--region', help='x0,y0,x1,y1 to search in')
    ap.add_argument('--fps', type=float, default=30)
    ap.add_argument('--channel', choices=['x', 'y', 'w', 'h', 'z'], help='fit this instead of what changes most; z = depth of a perspective fly-in (1 / size)')
    ap.add_argument('--table', action='store_true', help='print the per-frame measurements')
    a = ap.parse_args()
    if not os.path.exists(a.video):
        sys.exit(f'not found: {a.video}')
    if a.f1 - a.f0 < 4:
        sys.exit('need at least 5 frames (--to - --from >= 4)')
    data = measure(frames(a.video, a.f0, a.f1), a)
    ok = ~np.isnan(data[:, 0])
    if ok.sum() < 5:
        sys.exit('element not found in enough frames: check --color/--tol or --thr and --region')
    names = ['x', 'y', 'w', 'h']
    if a.table:
        for i, row in enumerate(data):
            print(f'f{a.f0 + i:5d}  ' + '  '.join(f'{n} {v:8.2f}' for n, v in zip(names, row)))
    filled = np.array([np.interp(np.arange(len(data)), np.nonzero(ok)[0], data[ok, k]) for k in range(4)]).T
    span = filled.max(0) - filled.min(0)
    auto = names[int(np.argmax(span[:2] if span[:2].max() >= 0.5 * span[2:].max() else np.r_[0, 0, span[2:]]))]
    ch = a.channel or auto
    size = filled[:, 2] if ch in ('w', 'z') else filled[:, 3]
    v = 1.0 / np.maximum(size, 1.0) if ch == 'z' else filled[:, names.index(ch)]
    off = visible_from(size) if ch == 'z' else 0
    v, vsize = v[off:], size[off:]
    if len(v) < 5 or np.ptp(v) < (1e-3 if ch == 'z' else 2):
        sys.exit(f'the element barely moves (largest change {span.max():.1f} px)')
    r = fit(v, a.fps)
    report(r, ch, a.f0 + off, vsize, explicit=bool(a.channel))
    # a scale-in that fits badly is often a perspective fly-in: depth eases, the size goes as 1/depth
    if ch in ('w', 'h') and min(r['err_s'], r['err_b']) > 0.03:
        zo = visible_from(size)
        rz = fit(1.0 / np.maximum(size[zo:], 1.0), a.fps) if len(size) - zo >= 5 else {'err_s': 9, 'err_b': 9}
        if min(rz['err_s'], rz['err_b']) < 0.6 * min(r['err_s'], r['err_b']):
            print(f'\n   depth fits better ({min(rz["err_s"], rz["err_b"]):.3f} vs {min(r["err_s"], r["err_b"]):.3f}): '
                  'this is a perspective fly-in, rerun with --channel z')


def visible_from(size):
    """First frame where a growing element is really there (5 % of its largest size): before that 1/size explodes."""
    vis = np.nonzero(size >= 0.05 * size.max())[0]
    return int(vis[0]) if len(vis) else 0


def fit(v, fps):
    """Start / settle frames, overshoot, cadence and the best spring and bezier for one eased move in v."""
    v0, v1, sp = v[0], v[-1], np.ptp(v)
    rng = v1 - v0 if abs(v1 - v0) > 0.1 * sp else (v.max() - v0 if abs(v.max() - v0) > abs(v.min() - v0) else v.min() - v0)
    moved = np.nonzero(np.abs(v - v0) > 0.01 * abs(rng))[0]
    start = int(moved[0]) if len(moved) else 0
    settled = np.nonzero(np.abs(v - v1) > 0.005 * abs(rng))[0]  # tight: strong ease-outs creep in
    end = int(settled[-1]) + 1 if len(settled) else len(v) - 1
    p = (v - v0) / rng
    over = max(0.0, p.max() - 1)
    s0 = max(0, start - 1)  # last frame at rest
    pp = p[s0:]
    best_s = None
    for z in list(np.linspace(0.05, 0.99, 48)) + [1.0]:
        for w0 in np.linspace(2, 60, 233):
            err = np.sqrt(np.mean((remotion_spring(len(pp), fps, w0 * w0, 2 * z * w0) - pp) ** 2))
            if best_s is None or err < best_s[0]:
                best_s = (err, w0 * w0, 2 * z * w0, z)
    dur = max(1, end - s0)
    xs = np.arange(dur + 1) / dur
    target = np.clip(p[s0:s0 + dur + 1], -0.5, 1.5)

    def loss(q):
        if not (0 <= q[0] <= 1 and 0 <= q[2] <= 1):
            return 1e3
        return np.sqrt(np.mean((bezier(xs, *q) - target) ** 2))

    starts = [(0.25, 0.1, 0.25, 1), (0.42, 0, 0.58, 1), (0.16, 1, 0.3, 1), (0.7, 0, 0.84, 0), (0.33, 0, 0.67, 1)]
    bb = min((minimize(loss, q0, method='Nelder-Mead', options={'xatol': 1e-4, 'fatol': 1e-6, 'maxiter': 2000}) for q0 in starts),
             key=lambda res: res.fun)
    return {'v0': v0, 'rng': rng, 'start': start, 'end': end, 's0': s0, 'over': over, 'cad': cadence(v[start:end + 1]),
            'err_s': best_s[0], 'K': best_s[1], 'C': best_s[2], 'zeta': best_s[3], 'err_b': bb.fun, 'bez': bb.x}


def report(r, ch, f0, size, explicit):
    f_rest, f_end = f0 + r['s0'], f0 + r['end']
    v0, v1 = r['v0'], r['v0'] + r['rng']
    cad = r['cad']
    on = f', moves on {cad}s' if cad and cad > 1 else ''
    if ch == 'z':
        z0 = size[-1] / max(size[0], 1.0)  # depth relative to the end pose (1 = landed)
        print(f'depth (size {size[0]:.1f} -> {size[-1]:.1f} px): starts {z0:.2f}x as far as the end pose, '
              f'moves frames {f0 + r["start"]}-{f_end}{on}')
        lo, hi, pre = z0, 1.0, 'scale = 1 / '
    else:
        print(f'{ch}{"" if explicit else " changes most"}: {v0:.1f} -> {v1:.1f} ({v1 - v0:+.1f} px), starts frame {f0 + r["start"]}, '
              f'settles frame {f_end} ({r["end"] - r["start"] + 1} frames), overshoot {r["over"]:.0%}{on}')
        lo, hi, pre = v0, v1, ''
    z = r['zeta']
    damp = f'{r["C"]:.1f}' if z < 1 else f'{r["C"]:.1f} /* critical: any damping >= {r["C"]:.1f} gives the same curve */'
    kind = 'critically damped' if z >= 1 else f'damping ratio {z:.2f}'
    print(f'\nspring fit  (error {r["err_s"]:.3f} of the move, {kind})')
    print(f'  {pre}({lo:.2f} + {hi - lo:.2f} * spring({{frame: frame - {f_rest}, fps, config: {{stiffness: {r["K"]:.1f}, damping: {damp}, mass: 1}}}}))')
    x1, y1, x2, y2 = r['bez']
    print(f'bezier fit  (error {r["err_b"]:.3f} of the move, over frames {f_rest}-{f_end})')
    print(f"  {pre}interpolate(frame, [{f_rest}, {f_end}], [{lo:.2f}, {hi:.2f}], {{easing: Easing.bezier({x1:.3f}, {y1:.3f}, {x2:.3f}, {y2:.3f}), "
          "extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})")
    if min(r['err_s'], r['err_b']) > 0.05:
        print('-> POOR FIT: not one eased move. Narrow --from/--to to a single move (several moves = several interpolate() calls), '
              'track a rigid part with --region, or choose the channel with --channel (scale-in: w; perspective fly-in: z). See --table.')
    else:
        print(f'-> use the {"spring" if r["err_s"] < r["err_b"] else "bezier"} (lower error)'
              + ('; overshoot means a spring or an overshooting bezier (y > 1)' if r['over'] > 0.03 else ''))
    if cad and cad > 1:
        print(f'   the reference holds every {cad} frames: quantise the frame you feed it, e.g. Math.floor(frame / {cad}) * {cad}')

if __name__ == '__main__':
    main()
