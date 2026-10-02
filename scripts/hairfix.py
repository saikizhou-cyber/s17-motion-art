"""Darken drifted brown hair in an AI clip back toward the locked dark brown-black.

Case-specific example (dark hair): for another character, adjust the hue and threshold
constants in fix(). Only dark, saturated orange pixels move (hair); light skin, the white shirt, the
black coat and the blue key background are left alone.
usage: python scripts/hairfix.py <in.mp4> <out.mp4> [strength=0.5]
"""
import json, subprocess, sys
import numpy as np

if len(sys.argv) < 3 or sys.argv[1] in ('-h', '--help'):
    sys.exit(__doc__)
src, dst = sys.argv[1], sys.argv[2]
k = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,r_frame_rate', '-of', 'json', src]))['streams'][0]
w, h, fps = info['width'], info['height'], info['r_frame_rate']


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def fix(a):
    a = a.astype(np.float32) / 255
    mx, mn = a.max(2), a.min(2)
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    # smooth hue weight around orange-brown (≈15°, ±45°): no hard gate, so codec noise can't make blocks
    hue = np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b))
    hw = np.clip(np.cos(np.radians(np.clip((hue - 15) * 2, -180, 180))), 0, 1)
    wgt = hw * ss(0.6, 0.3, mx) * ss(0.1, 0.3, s)
    v2 = mx * (1 - k * wgt)
    s2 = s * (1 - 0.6 * k * wgt)
    # rebuild rgb with the same hue: scale channel offsets from the max
    scale = np.where(mx > 0, v2 / np.maximum(mx, 1e-6), 0)[..., None]
    base = a * scale
    # desaturate toward grey of the new value
    grey = v2[..., None] * (1 - s2[..., None])
    mix = np.where(s[..., None] > 0, (s2 / np.maximum(s, 1e-6))[..., None], 1)
    out = grey + (base - v2[..., None] * (1 - s[..., None])) * mix
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', fps, '-i', '-',
                        '-c:v', 'libx264', '-crf', '14', '-preset', 'slow', '-pix_fmt', 'yuv420p', dst], stdin=subprocess.PIPE)
n = 0
while True:
    buf = dec.stdout.read(w * h * 3)
    if len(buf) < w * h * 3:
        break
    enc.stdin.write(fix(np.frombuffer(buf, np.uint8).reshape(h, w, 3)).tobytes())
    n += 1
enc.stdin.close(); enc.wait(); dec.wait()
print(f'{n} frames -> {dst}')
