"""Generate a batch of images on the Jimeng (即梦) canvas, sequentially, under a credit ceiling.

usage: python jimeng_batch_run.py <jobs.json> [--tag run1] [--budget 80] [--project <id>]

jobs.json: [{"key": "hero_hit_a", "mode": "t2i"|"i2i", "ratio": "3:4", "prompt": "...{{node:node_xxx}}...",
             "refs": ["node_xxx"]}, ...]   (key, mode, ratio and prompt are required; keys must be unique)
Each finished image is downloaded next to jobs.json as <key>.png. Progress is kept in
state_<tag>.json, so a rerun skips finished keys (resource recorded AND <key>.png present) and counts
credits already spent: use a NEW --tag for a new run with its own budget (a shared state file eats the
budget). A key whose resource is recorded but whose file is missing is only downloaded again: no credits.
Model seedream_5.0_pro, 2K, 8 credits per image (as priced when this was written; check yours).
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

COST = 8
ap = argparse.ArgumentParser()
ap.add_argument('jobs')
ap.add_argument('--tag', default='all')
ap.add_argument('--budget', type=int, default=80, help='credit ceiling for this tag')
ap.add_argument('--project', default=os.environ.get('JIMENG_PROJECT_ID'))
ap.add_argument('--model', default='seedream_5.0_pro')
ap.add_argument('--resolution', default='2K')
a = ap.parse_args()
if not a.project:
    sys.exit('Jimeng project id missing: --project <id> or set JIMENG_PROJECT_ID')
exe = os.environ.get('JIMENG_CLI') or os.path.expanduser('~/bin/dreamina-canvas' + ('.exe' if os.name == 'nt' else ''))
if not (os.path.isfile(exe) or shutil.which(exe)):
    sys.exit(f'Jimeng CLI not found: {exe} (install it, or set JIMENG_CLI to its path)')
B = os.path.dirname(os.path.abspath(a.jobs))
jobs = json.load(open(a.jobs, encoding='utf-8'))
if not isinstance(jobs, list):
    sys.exit(f'{a.jobs}: expected a JSON list of jobs')
errs, seen = [], set()
for i, j in enumerate(jobs):
    miss = [x for x in ('key', 'mode', 'ratio', 'prompt') if not (isinstance(j, dict) and j.get(x))]
    if miss:
        errs.append(f'job {i}: missing {", ".join(miss)}')
    elif j['key'] in seen:
        errs.append(f'job {i}: duplicate key {j["key"]}')
    else:
        seen.add(j['key'])
if errs:
    sys.exit(f'{a.jobs}: bad jobs, nothing was run:\n  ' + '\n  '.join(errs))
state_path = os.path.join(B, f'state_{a.tag}.json')
state = json.load(open(state_path, encoding='utf-8')) if os.path.exists(state_path) else {}
spent = sum(COST for v in state.values() if v.get('resource'))


def save():
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=1)


def fetch(resource, path):
    """Download a resource; True only if a non-empty file was written just now (not a stale one)."""
    t0 = time.time()
    subprocess.run([exe, '--format', 'json', 'resource', 'download', resource, '--project-id', a.project, '-o', path], capture_output=True)
    return os.path.isfile(path) and os.path.getsize(path) > 0 and os.path.getmtime(path) >= t0 - 2


stopped = False
for j in jobs:
    k = j['key']
    png = os.path.join(B, f'{k}.png')
    e = state.get(k) or {}
    if e.get('resource'):
        if e.get('downloaded') is not False and os.path.isfile(png) and os.path.getsize(png) > 0:
            continue  # done (a recorded failed download means any file there is stale)
        e['downloaded'] = fetch(e['resource'], png)  # already paid for: download only
        state[k] = e
        save()
        print(k, 'downloaded again' if e['downloaded'] else f'GENERATED but download failed: resource {e["resource"]}', flush=True)
        continue
    if spent + COST > a.budget:
        if not stopped:
            print('budget reached, stop')
            stopped = True
        continue
    args = [exe, '--format', 'json', 'node', 'create', 'image', '--project-id', a.project, '--mode', j['mode'], '--model', a.model,
            '--ratio', j['ratio'], '--resolution', a.resolution, '--title', f'{a.tag}-{k}', '--prompt', j['prompt'], '--run',
            '--credit-ceiling', str(COST), '--wait', '--timeout', '8m']
    for rid in j.get('refs', []):
        args += ['--ref', f'node:{rid}']
    r = subprocess.run(args, capture_output=True)
    out = r.stdout.decode('utf-8', 'replace')
    res = re.findall(r'"resourceId":\s*"([0-9a-f-]{36})"', out)
    node = re.findall(r'"nodeId":\s*"(node_[a-z0-9]+)"', out)
    err = re.findall(r'"code":\s*"([^"]+)"', out)
    entry = {'node': node[0] if node else None, 'resource': res[-1] if res else None, 'error': err[:2] if not res else None}
    if entry['resource']:
        spent += COST
        entry['downloaded'] = fetch(entry['resource'], png)
        if not entry['downloaded']:
            print(f'GENERATED but download failed: resource {entry["resource"]} (rerun to download it again, no credits)', flush=True)
    state[k] = entry
    save()
    print(k, entry, 'spent', spent, flush=True)
print('done, spent', spent)
