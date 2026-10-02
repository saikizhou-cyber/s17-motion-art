"""Re-time the iris glow of the S49 eye clip: dull before the eyes open, ignites when they do.

Case-specific example (red iris): for another character, adjust the hue and threshold
constants in fix().

usage: python scripts/irisglow.py <in.mp4> <out.mp4> [t_dark_end=0.95] [t_open=1.2]
The iris is found by colour (strongly red pixels, no registration needed, so camera
pushes in the clip don't matter): before `t_dark_end` it is pulled to a dull maroon, from
`t_dark_end` to `t_open+0.3` it ramps up, flares once at `t_open+0.25`, then keeps an extra
bloom. Times are clip seconds.
"""
import json, subprocess, sys
import numpy as np
from PIL import Image, ImageFilter

if len(sys.argv) < 3 or sys.argv[1] in ('-h', '--help'):
    sys.exit(__doc__)
src, dst = sys.argv[1], sys.argv[2]
t_dark = float(sys.argv[3]) if len(sys.argv) > 3 else 0.95
t_open = float(sys.argv[4]) if len(sys.argv) > 4 else 1.2
info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate', '-of', 'json', src]))['streams'][0]
w, h = info['width'], info['height']
num, den = info['r_frame_rate'].split('/')
fps = float(num) / float(den)


def ss(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def blur(m, s):
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(s))).astype(np.float32) / 255


def fix(a, t):
    f = a.astype(np.float32) / 255
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    m = np.clip((r - 1.6 * np.maximum(g, b) - 0.05) / 0.25, 0, 1)
    dim = 1 - ss(t_dark, t_open + 0.3, t)               # 1 = dull, 0 = lit
    glow = ss(t_dark + 0.1, t_open + 0.35, t)
    flare = float(np.exp(-(((t - (t_open + 0.25)) / 0.11) ** 2)))
    out = f.copy()
    lum = 0.3 * r + 0.55 * g + 0.15 * b
    if dim > 0.01:
        # dull, almost black maroon: the iris reads as dead before the eyes open
        dull = np.stack([r * 0.16 + lum * 0.08, g * 0.12, b * 0.12], -1)
        k = (dim * 0.92 * m)[..., None]
        out = out * (1 - k) + dull * k
    lit = glow * (0.45 + 0.9 * flare)
    if lit > 0.01:
        # keep the painted iris detail; lift it a little and add light around it
        out = out * (1 + (0.35 * lit * m)[..., None] * np.array([1.0, 0.25, 0.25], np.float32))
        bloom = blur(m, 7) * 0.9 + blur(m, 22) * 0.7
        add = np.stack([bloom * (0.85 + 0.5 * flare) * glow, bloom * 0.18 * glow, bloom * 0.16 * glow], -1)
        out = 1 - (1 - np.clip(out, 0, 1)) * (1 - np.clip(add, 0, 1))
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-',
                        '-c:v', 'libx264', '-crf', '14', '-preset', 'slow', '-pix_fmt', 'yuv420p', dst], stdin=subprocess.PIPE)
n = 0
while True:
    buf = dec.stdout.read(w * h * 3)
    if len(buf) < w * h * 3:
        break
    enc.stdin.write(fix(np.frombuffer(buf, np.uint8).reshape(h, w, 3), n / fps).tobytes())
    n += 1
enc.stdin.close(); enc.wait(); dec.wait()
print(f'{n} frames -> {dst}')
