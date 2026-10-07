"""Animatic: static keyframes held for their shot durations, with temp music, to lock the rhythm before any motion work.

usage:
  python animatic.py --shots shots.json  --images keyframes/ [--music m.wav] [--beats beats.json] -o animatic.mp4
  python animatic.py --root . --images keyframes/            [--music m.wav] [--beats beats.json] -o animatic.mp4

shots   --shots FILE: JSON (a list, or {"shots": [...]}) or CSV with a header. One row per shot:
          id (shot/name), image (img/path/file/src, optional), seconds (sec/duration/dur) or frames (f/n).
          frames wins when both are given. Relative image paths resolve against --images, then the file's folder.
        --root DIR (or $PV_ROOT, or the current directory when --shots is absent): the cut list of the Remotion
          project, src/core/timeline.ts, read with _shots.load_shots; a shot lasts until the next shot starts.
images  when a shot has no image of its own, --images DIR is searched for <id>.png / .jpg / .jpeg / .webp / .bmp
        (case-insensitive). A shot with no image gets a grey placeholder card (alternating tones so a cut between
        two cards stays visible). Keyframes are letterboxed into --size (--fit cover crops instead).
labels  every frame carries the shot id, its length (frames, seconds) and frame range, drawn with Pillow (no ffmpeg
        drawtext: fonts fail on Windows). --kenburns [ZOOM] adds a slow push-in (default 0.06 = 6 %) to the stills.
beats   --beats beats.json (the `beat_check.py grid --json` output, key beat_frames) snaps each shot's start (except
        the first) to the nearest beat frame within --snap-tol frames (default 6) and prints every adjustment. The
        total length does not change; a shot keeps at least 1 frame. --json writes the final shot table.
music   --music FILE is mixed in (AAC) from t=0, padded with silence or cut to the video length.

Frames are piped to ffmpeg as raw RGB, so the output (H.264, yuv420p, BT.709) holds exactly the sum of the shots'
frames; the script re-counts them with ffprobe and exits non-zero on a mismatch.
Needs Pillow, ffmpeg/ffprobe on PATH; --root also needs _shots.py (same folder).
"""
import argparse
import csv
import json
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
ALIAS = {'id': ('id', 'shot', 'name'), 'image': ('image', 'img', 'path', 'file', 'src'),
         'seconds': ('seconds', 'sec', 's', 'duration', 'dur'), 'frames': ('frames', 'frame', 'f', 'n')}
BG = (16, 16, 18)
CARD = ((86, 90, 98), (118, 122, 130))
FONTS_BOLD = ('arialbd.ttf', 'consolab.ttf', 'DejaVuSans-Bold.ttf', 'Helvetica.ttc')
FONTS_REG = ('arial.ttf', 'consola.ttf', 'DejaVuSans.ttf', 'Helvetica.ttc')


# ---------------------------------------------------------------- shot table

def pick(row, key):
    low = {str(k).strip().lower(): v for k, v in row.items()}
    for name in ALIAS[key]:
        v = low.get(name)
        if v not in (None, ''):
            return v
    return None


def shots_from_file(path, fps):
    """[{id, image, frames}] from a JSON or CSV shot list."""
    if not os.path.exists(path):
        sys.exit(f'shots file not found: {path}')
    if path.lower().endswith('.csv'):
        with open(path, encoding='utf-8-sig', newline='') as fh:
            rows = list(csv.DictReader(fh))
    else:
        with open(path, encoding='utf-8-sig') as fh:
            data = json.load(fh)
        rows = data.get('shots') if isinstance(data, dict) else data
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            sys.exit(f'{path}: expected a list of objects (or {{"shots": [...]}}) with id and seconds/frames')
    shots = []
    for i, r in enumerate(rows, 1):
        sid, fr, sec = pick(r, 'id'), pick(r, 'frames'), pick(r, 'seconds')
        if sid is None or (fr is None and sec is None):
            sys.exit(f'{path}: row {i} needs an id and a duration (seconds or frames): {r}')
        try:
            n = int(float(fr)) if fr is not None else round(float(sec) * fps)
        except ValueError:
            sys.exit(f'{path}: row {i} ({sid}): duration is not a number: {r}')
        if n < 1:
            sys.exit(f'{path}: row {i} ({sid}): duration is under one frame')
        shots.append({'id': str(sid), 'image': pick(r, 'image'), 'frames': n})
    if not shots:
        sys.exit(f'{path}: no shots')
    return shots


def shots_from_root(root, fps):
    """Shots of src/core/timeline.ts; a shot lasts until the next one starts (the last one to its own end)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _shots import load_shots
    raw = load_shots(root, fps)
    if raw[0][1] != 0:
        print(f'warning: the first shot ({raw[0][0]}) starts at frame {raw[0][1]}, not 0: the animatic starts at its first shot', file=sys.stderr)
    shots = []
    for k, (sid, f0, f1) in enumerate(raw):
        end = raw[k + 1][1] if k + 1 < len(raw) else f1 + 1
        if end <= f0:
            sys.exit(f'{sid}: starts at frame {f0} but the next shot starts at {end}: timeline.ts is not in order')
        if k + 1 < len(raw) and f1 + 1 != end:
            print(f'warning: {sid} ends at frame {f1}, the next shot starts at {end}: holding {sid} until then', file=sys.stderr)
        shots.append({'id': sid, 'image': None, 'frames': end - f0})
    return shots


def index_images(d):
    """{lower-case stem: path} of the images in a folder (png before jpg ...)."""
    if not os.path.isdir(d):
        sys.exit(f'--images folder not found: {d}')
    found = {}
    for ext in reversed(EXTS):  # earlier extensions overwrite later ones
        for fn in os.listdir(d):
            stem, e = os.path.splitext(fn)
            if e.lower() == ext:
                found[stem.lower()] = os.path.join(d, fn)
    return found


def resolve_images(shots, images_dir, shots_dir):
    """Set shot['path'] (an existing file or None)."""
    index = index_images(images_dir) if images_dir else {}
    for s in shots:
        s['path'] = None
        if s['image']:
            cands = [s['image']] if os.path.isabs(s['image']) else \
                [os.path.join(d, s['image']) for d in (images_dir, shots_dir) if d]
            s['path'] = next((c for c in cands if os.path.isfile(c)), None)
            if not s['path']:
                print(f'warning: {s["id"]}: image {s["image"]!r} not found: placeholder card', file=sys.stderr)
        if not s['path']:
            s['path'] = index.get(s['id'].lower())


# ---------------------------------------------------------------- beat snapping

def load_beats(path, fps):
    if not os.path.exists(path):
        sys.exit(f'beats file not found: {path}')
    with open(path, encoding='utf-8-sig') as fh:
        data = json.load(fh)
    frames, src_fps, bpm = (data, fps, None) if isinstance(data, list) else \
        (data.get('beat_frames'), float(data.get('fps', fps)), data.get('bpm'))
    if not frames:
        sys.exit(f'{path}: no beat_frames (expected the output of `beat_check.py grid --json`)')
    if abs(src_fps - fps) > 1e-6:
        print(f'note: beats were computed at {src_fps:g} fps, converting to {fps:g} fps')
        frames = [round(b * fps / src_fps) for b in frames]
    return sorted(set(int(b) for b in frames)), bpm


def snap_starts(starts, total, beats, tol):
    """Move starts[1:] onto the nearest beat within tol frames; each shot keeps >= 1 frame, the total is unchanged.
    Returns [(orig, new, nearest_beat, status)] per shot; status is snap, far (no beat within tol) or blocked
    (the beats within tol would squeeze a neighbouring shot). The first shot stays at 0."""
    n = len(starts)
    out = [(0, 0, None, 'first')]
    for k in range(1, n):
        orig = starts[k]
        lo, hi = out[-1][1] + 1, total - (n - k)
        nearest = min(beats, key=lambda b: (abs(b - orig), b))
        near = [b for b in beats if abs(b - orig) <= tol]
        ok = sorted((b for b in near if lo <= b <= hi), key=lambda b: (abs(b - orig), b))
        if ok:
            out.append((orig, ok[0], ok[0], 'snap'))
        else:
            out.append((orig, min(max(orig, lo), hi), nearest, 'blocked' if near else 'far'))
    return out


def apply_beats(shots, beats, bpm, tol):
    starts, t = [], 0
    for s in shots:
        starts.append(t)
        t += s['frames']
    total = t
    res = snap_starts(starts, total, beats, tol)
    print(f'beat snap: {len(beats)} beats' + (f', {bpm:g} BPM' if bpm else '') + f', tolerance {tol:g} frames')
    print(f'{"shot":8} {"start":>6} {"beat":>6} {"new":>6} {"delta":>6}')
    moved = []
    for s, (orig, new, nb, st) in zip(shots[1:], res[1:]):
        print(f'{s["id"]:8} {orig:6d} {nb:6d} {new:6d} {new - orig:+6d}'
              + {'snap': '', 'far': '  (no beat within tolerance)', 'blocked': '  (blocked by a neighbouring shot)'}[st])
        if st == 'snap':
            moved.append(abs(new - orig))
    for k, s in enumerate(shots):
        s['frames'] = (res[k + 1][1] if k + 1 < len(shots) else total) - res[k][1]
    if moved:
        print(f'{len(moved)}/{len(shots) - 1} starts on a beat (mean |delta| {sum(moved) / len(moved):.1f} frames, max {max(moved)}); '
              f'{len(shots) - 1 - len(moved)} left where they were\n')
    else:
        print('no shot start could be snapped to a beat\n')


# ---------------------------------------------------------------- drawing

def font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def fit_image(path, W, H, mode):
    im = ImageOps.exif_transpose(Image.open(path))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGBA', im.size, BG + (255,))
        im = Image.alpha_composite(bg, im)
    im = im.convert('RGB')
    if mode == 'cover':
        return ImageOps.fit(im, (W, H), Image.LANCZOS)
    k = min(W / im.width, H / im.height)
    im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    out = Image.new('RGB', (W, H), BG)
    out.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    return out


def placeholder(W, H, sid, idx):
    im = Image.new('RGB', (W, H), CARD[idx % 2])
    d = ImageDraw.Draw(im)
    d.text((W / 2, H / 2), sid, font=font(FONTS_BOLD, int(H * 0.28)), fill=(235, 235, 238), anchor='mm')
    d.text((W / 2, H * 0.72), 'no keyframe', font=font(FONTS_REG, int(H * 0.05)), fill=(205, 207, 212), anchor='mm')
    return im


def label_layers(s, idx, n, fps, W, H):
    """[(RGBA image, (x, y))]: top-left id + length, bottom-left frame range, bottom-right shot counter."""
    u = H / 720
    f_big, f_mid, f_small = font(FONTS_BOLD, round(44 * u)), font(FONTS_REG, round(22 * u)), font(FONTS_REG, round(18 * u))
    pad, layers = round(10 * u), []

    def box(lines):
        meas = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        w = max(round(meas.textlength(t, font=f)) for t, f in lines) + 2 * pad
        h = sum(round(f.size * 1.25) for _, f in lines) + pad
        im = Image.new('RGBA', (w, h), (0, 0, 0, 165))
        d, y = ImageDraw.Draw(im), pad // 2
        for t, f in lines:
            d.text((pad, y), t, font=f, fill=(255, 236, 90) if f is f_big else (240, 240, 240))
            y += round(f.size * 1.25)
        return im

    n_f, f0 = s['frames'], s['start']
    layers.append((box([(s['id'], f_big), (f'{n_f}f  {n_f / fps:.3f}s', f_mid)]), (0, 0)))
    b = box([(f'f{f0}-{f0 + n_f - 1}   {f0 / fps:.3f}-{(f0 + n_f) / fps:.3f}s', f_small)])
    layers.append((b, (0, H - b.height)))
    c = box([(f'{idx + 1}/{n}', f_small)])
    layers.append((c, (W - c.width, H - c.height)))
    return layers


def stamp(im, layers):
    for lay, xy in layers:
        im.paste(lay, xy, lay)
    return im


def shot_frames(s, idx, n, W, H, fps, fit, kb):
    """Yield s['frames'] raw RGB frames of one shot (the same bytes object for a still)."""
    base = fit_image(s['path'], W, H, fit) if s['path'] else placeholder(W, H, s['id'], idx)
    layers = label_layers(s, idx, n, fps, W, H)
    if not kb:
        data = stamp(base, layers).tobytes()
        for _ in range(s['frames']):
            yield data
        return
    last = max(1, s['frames'] - 1)
    for i in range(s['frames']):
        z = 1 + kb * i / last
        w, h = W / z, H / z
        x, y = (W - w) / 2, (H - h) / 2
        yield stamp(base.resize((W, H), Image.BICUBIC, box=(x, y, x + w, y + h)), layers).tobytes()


# ---------------------------------------------------------------- ffmpeg

def has_audio(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a', '-show_entries', 'stream=index', '-of', 'csv=p=0', path],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def probe(path):
    """(video packets, container duration s, audio codec or None)"""
    def run(*args):
        return subprocess.run(['ffprobe', '-v', 'error', *args, path], capture_output=True, text=True).stdout.strip()
    n = run('-select_streams', 'v:0', '-count_packets', '-show_entries', 'stream=nb_read_packets', '-of', 'csv=p=0')
    dur = run('-show_entries', 'format=duration', '-of', 'csv=p=0')
    ac = run('-select_streams', 'a:0', '-show_entries', 'stream=codec_name', '-of', 'csv=p=0')
    return int(n), float(dur), ac or None


def encode(shots, W, H, fps, out, music, fit, kb):
    total = sum(s['frames'] for s in shots)
    cmd = ['ffmpeg', '-v', 'error', '-nostats', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-framerate', f'{fps:g}', '-i', '-']
    if music:
        cmd += ['-i', music]
    cmd += ['-map', '0:v:0']
    if music:
        cmd += ['-map', '1:a:0', '-af', 'apad', '-c:a', 'aac', '-b:a', '192k', '-t', f'{total / fps:.6f}']
    cmd += ['-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
            '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-r', f'{fps:g}', '-frames:v', str(total),
            '-movflags', '+faststart', out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i, s in enumerate(shots):
            for data in shot_frames(s, i, len(shots), W, H, fps, fit, kb):
                p.stdin.write(data)
        p.stdin.close()
    except OSError:  # ffmpeg quit early (BrokenPipeError, or EINVAL on Windows): its stderr says why
        pass
    err = p.stderr.read().decode('utf-8', 'replace').strip()
    if p.wait():
        sys.exit(f'ffmpeg failed:\n{err[-600:]}')
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--shots', help='JSON or CSV shot list (id, image, seconds or frames)')
    ap.add_argument('--root', help='Remotion project root with src/core/timeline.ts (default when --shots is absent: $PV_ROOT or cwd)')
    ap.add_argument('--images', help='folder of keyframes named <id>.png/.jpg ...')
    ap.add_argument('-o', '--out', default='animatic.mp4')
    ap.add_argument('--music', help='audio (or a video carrying it) mixed in from t=0')
    ap.add_argument('--beats', help='beats.json from `beat_check.py grid --json`: snap shot starts to beats')
    ap.add_argument('--snap-tol', type=float, default=6.0, help='largest start move in frames when snapping (default 6)')
    ap.add_argument('--fps', type=float, default=30.0)
    ap.add_argument('--size', default='1280x720', help='WxH, both even (default 1280x720)')
    ap.add_argument('--fit', choices=['contain', 'cover'], default='contain')
    ap.add_argument('--kenburns', nargs='?', type=float, const=0.06, default=0.0, metavar='ZOOM', help='slow push-in on stills (default off; bare flag = 0.06)')
    ap.add_argument('--json', help='write the final shot table (id, start, end, frames, seconds, image) as JSON')
    a = ap.parse_args()

    try:
        W, H = (int(x) for x in a.size.lower().split('x'))
    except ValueError:
        sys.exit(f'--size must look like 1280x720, got {a.size!r}')
    if W % 2 or H % 2 or W < 16 or H < 16:
        sys.exit('--size must be even in both dimensions (yuv420p)')
    if a.fps <= 0:
        sys.exit('--fps must be positive')
    if a.music and not os.path.exists(a.music):
        sys.exit(f'music not found: {a.music}')
    if a.music and not has_audio(a.music):
        sys.exit(f'{a.music}: no audio stream')

    if a.shots:
        shots, shots_dir = shots_from_file(a.shots, a.fps), os.path.dirname(os.path.abspath(a.shots))
    else:
        root = os.path.abspath(a.root or os.environ.get('PV_ROOT') or os.getcwd())
        shots, shots_dir = shots_from_root(root, a.fps), None
    resolve_images(shots, a.images, shots_dir)
    if a.beats:
        beats, bpm = load_beats(a.beats, a.fps)
        apply_beats(shots, beats, bpm, a.snap_tol)
    t = 0
    for s in shots:
        s['start'] = t
        t += s['frames']
    total = t

    print(f'{"shot":8} {"start":>6} {"end":>6} {"frames":>6} {"seconds":>8}  image')
    for s in shots:
        print(f'{s["id"]:8} {s["start"]:6d} {s["start"] + s["frames"] - 1:6d} {s["frames"]:6d} {s["frames"] / a.fps:8.3f}  '
              f'{os.path.basename(s["path"]) if s["path"] else "(placeholder)"}')
    n_ph = sum(1 for s in shots if not s['path'])
    print(f'{len(shots)} shots, {total} frames = {total / a.fps:.3f} s at {a.fps:g} fps, {n_ph} placeholder(s)')

    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)), exist_ok=True)
        with open(a.json, 'w', encoding='utf-8') as fh:
            json.dump([{'id': s['id'], 'start': s['start'], 'end': s['start'] + s['frames'] - 1, 'frames': s['frames'],
                        'seconds': round(s['frames'] / a.fps, 4), 'image': s['path']} for s in shots], fh, indent=1)
        print(f'-> {a.json}')

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    encode(shots, W, H, a.fps, a.out, a.music, a.fit, a.kenburns)
    n, dur, ac = probe(a.out)
    print(f'-> {a.out}: {n} frames, {dur:.3f} s, audio {ac or "none"}')
    if n != total:
        sys.exit(f'frame count mismatch: wrote {total}, ffprobe counts {n}')
    if a.music and not ac:
        sys.exit('music was requested but the output has no audio stream')


if __name__ == '__main__':
    main()
