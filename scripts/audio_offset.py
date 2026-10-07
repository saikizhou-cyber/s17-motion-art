"""Audio offset between two videos by cross-correlation (checks that the final mux is in sync).

usage: python audio_offset.py <reference.mp4> <ours.mp4> [--seconds 30]
Prints the lag of `ours` against the reference in milliseconds (0 ms = in sync) and the peak strength.
Positive = ours audio is late (starts after the reference), negative = early.
Only meaningful while both carry the same music (e.g. the reference track used for local timing checks).
"""
import argparse
import subprocess

import numpy as np

SR = 8000


def pcm(path, seconds):
    try:
        # a join without PV_AUDIO writes a silent file; say so instead of a cryptic ffmpeg error
        has_audio = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', path],
                                   capture_output=True, text=True)
        if has_audio.returncode == 0 and not has_audio.stdout.strip():
            raise SystemExit(f'{path}: no audio stream (was PV_AUDIO set for the join?)')
        r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-t', str(seconds), '-ac', '1', '-ar', str(SR), '-f', 's16le', '-'],
                           capture_output=True)
    except FileNotFoundError:
        raise SystemExit('ffmpeg not found on PATH')
    if r.returncode != 0:
        tail = r.stderr.decode('utf-8', 'replace').strip().splitlines()[-2:]
        raise SystemExit(f'ffmpeg failed on {path}: ' + ' | '.join(tail))
    if len(r.stdout) < 2:
        raise SystemExit(f'{path}: no audio found in the first {seconds:g} s')
    x = np.frombuffer(r.stdout, np.int16).astype(np.float32)
    return (x - x.mean()) / (x.std() + 1e-9)


ap = argparse.ArgumentParser()
ap.add_argument('ref')
ap.add_argument('ours')
ap.add_argument('--seconds', type=float, default=30)
a = ap.parse_args()
r, o = pcm(a.ref, a.seconds), pcm(a.ours, a.seconds)
n = 1 << int(np.ceil(np.log2(len(r) + len(o))))
c = np.fft.irfft(np.fft.rfft(o, n) * np.conj(np.fft.rfft(r, n)), n)
lag = int(np.argmax(c))
if lag > n // 2:
    lag -= n
print(f'ours is {lag / SR * 1000:+.1f} ms against the reference (peak {c.max() / min(len(r), len(o)):.2f})')
