"""Generate image-to-video clips on the Jimeng (即梦) canvas and download them.

usage: python jimeng_video_run.py <jobs_v.json> [--project <id>] [--budget 48]

jobs_v.json: [{"key": "V1_recoil", "ratio": "16:9", "ref": "node_xxx", "prompt": "describe the motion in words"}, ...]
`ref` is the canvas node of OUR approved still (never a reference frame). Each clip is saved next to
the jobs file as <key>.mp4; existing files are skipped. The raw CLI response goes to run_<key>.json.
If run_<key>.json already holds a resourceId but the mp4 is missing, only the download is retried (no
credits); delete that run file to force a new generation.
Model seedance_2.0_mini, 720p, 4 s, first_last_frame mode, 24 credits per clip (check current pricing).
Approve the still first: in the case study 5 of 9 clips were never used.
Project id: --project or $JIMENG_PROJECT_ID. The CLI path: $JIMENG_CLI or ~/bin/dreamina-canvas(.exe).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

COST = 24
RID = re.compile(r'"resourceId":\s*"([0-9a-f-]{36})"')
ap = argparse.ArgumentParser()
ap.add_argument('jobs')
ap.add_argument('--project', default=os.environ.get('JIMENG_PROJECT_ID'))
ap.add_argument('--budget', type=int, default=48, help='credit ceiling for this run')
ap.add_argument('--model', default='seedance_2.0_mini')
a = ap.parse_args()
if not a.project:
    sys.exit('Jimeng project id missing: --project <id> or set JIMENG_PROJECT_ID')
exe = os.environ.get('JIMENG_CLI') or os.path.expanduser('~/bin/dreamina-canvas' + ('.exe' if os.name == 'nt' else ''))
if not (os.path.isfile(exe) or shutil.which(exe)):
    sys.exit(f'Jimeng CLI not found: {exe} (install it, or set JIMENG_CLI to its path)')
B = os.path.dirname(os.path.abspath(a.jobs))
jobs = json.load(open(a.jobs, encoding='utf-8-sig'))
if not isinstance(jobs, list):
    sys.exit(f'{a.jobs}: expected a JSON list of jobs')
errs = []
for i, j in enumerate(jobs):
    miss = [x for x in ('key', 'ratio', 'ref', 'prompt') if not (isinstance(j, dict) and j.get(x))]
    if miss:
        errs.append(f'job {i}: missing {", ".join(miss)}')
if errs:
    sys.exit(f'{a.jobs}: bad jobs, nothing was run:\n  ' + '\n  '.join(errs))


def have(path):
    return os.path.isfile(path) and os.path.getsize(path) > 0


def fetch(resource, path):
    """Download a resource; True only if a non-empty file was written just now."""
    t0 = time.time()
    subprocess.run([exe, '--format', 'json', 'resource', 'download', resource, '--project-id', a.project, '-o', path], capture_output=True)
    return have(path) and os.path.getmtime(path) >= t0 - 2


spent = 0
stopped = False
for j in jobs:
    k = j['key']
    mp4 = os.path.join(B, f'{k}.mp4')
    run = os.path.join(B, f'run_{k}.json')
    if have(mp4):
        continue
    prev = RID.findall(open(run, encoding='utf-8', errors='replace').read()) if os.path.exists(run) else []
    if prev:
        ok = fetch(prev[-1], mp4)  # already generated and paid for: download only
        print(k, 'downloaded again' if ok else f'GENERATED but download failed: resource {prev[-1]}', flush=True)
        continue
    if spent + COST > a.budget:
        if not stopped:
            print('budget reached, stop')
            stopped = True
        continue
    args = [exe, '--format', 'json', 'node', 'create', 'video', '--project-id', a.project, '--mode', 'first_last_frame', '--model', a.model,
            '--ratio', j['ratio'], '--resolution', '720p', '--duration', '4', '--title', k, '--prompt', j['prompt'], '--ref', f"node:{j['ref']}",
            '--run', '--credit-ceiling', str(COST), '--wait', '--timeout', '15m']
    r = subprocess.run(args, capture_output=True)
    out = r.stdout.decode('utf-8', 'replace')
    open(run, 'w', encoding='utf-8').write(out + r.stderr.decode('utf-8', 'replace'))
    res = RID.findall(out)
    ok = False
    if res:
        spent += COST
        ok = fetch(res[-1], mp4)
        if not ok:
            print(f'GENERATED but download failed: resource {res[-1]}', flush=True)
    print(k, 'ok' if ok else 'FAILED', 'spent', spent, flush=True)
