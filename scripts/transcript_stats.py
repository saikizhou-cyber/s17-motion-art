"""Measured retrospective numbers from Claude Code transcripts: time, user messages, turns, tokens per model.

usage: python transcript_stats.py [<transcripts_dir>] [--since ISO] [--until ISO] [--gap 30] [--messages out.md]

<transcripts_dir> defaults to <config dir>/projects/<slug of the current directory> (config dir =
$CLAUDE_CONFIG_DIR, else ~/.claude; the slug is the absolute path with every non-alphanumeric character
replaced by '-'). Top-level <session>.jsonl files are the main conversations;
<session>/subagents/**/agent-*.jsonl are sub-agents and workflow agents.
Times without a timezone are read in the local timezone, e.g. --until 2026-10-02T17:55:25.
--messages writes your raw prompts verbatim; keep that file out of any public bundle or repo.

What is counted, and the traps found in the case study:
  * user messages come in three shapes: `user` records (start of a turn), `attachment.queued_command`
    (sent while the agent was working) and `queue-operation enqueue`. A queued message WITH SCREENSHOTS
    stores its prompt as a block list (image + text) and its enqueue record has no text: read the list,
    or every screenshot message is lost (36 of 113 were missed this way once). Duplicates of the same text
    within 10 minutes are merged; task notifications, slash-command echoes and the automatic
    "I hit my usage limit..." resume are dropped.
  * assistant turns are deduplicated by message.id (one reply is split over several lines that repeat
    the usage); `<synthetic>` placeholder turns are skipped.
  * active time = sum of gaps shorter than --gap minutes between consecutive records of each file, summed
    over files. It includes time the agents worked alone; it is not the user's screen time.
  * wall clock = first -> last main-conversation record inside the window, i.e. it runs up to --until
    (the last record before it), or to the last record when --until is omitted.
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
from collections import defaultdict

SKIP = ('<task-notification', '<system-reminder', '<command-name', '<command-message', '<local-command', '[SYSTEM NOTIFICATION',
        'This session is being continued', '[Request interrupted', '<ci-monitor', '<scheduled', '<user-prompt-submit',
        'I hit my usage limit', '[Usage limit', '[Earlier usage-limit', '[Image:', 'Caveat:')
F = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')
LOCAL = dt.datetime.now().astimezone().tzinfo


def ts(s):
    t = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    return t if t.tzinfo else t.replace(tzinfo=LOCAL)


def text_and_images(content):
    """(text, n_images) of a message content; text None if it is a tool result."""
    if isinstance(content, str):
        return content, 0
    if not isinstance(content, list):
        return None, 0
    parts, imgs = [], 0
    for b in content:
        if not isinstance(b, dict):
            continue
        if b.get('type') == 'tool_result':
            return None, 0
        if b.get('type') == 'text':
            parts.append(b.get('text', ''))
        elif b.get('type') == 'image':
            imgs += 1
    return '\n'.join(parts), imgs


def hm(sec):
    sec = int(sec)
    return f'{sec // 3600}h{sec % 3600 // 60:02d}m'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('dir', nargs='?')
    ap.add_argument('--since')
    ap.add_argument('--until')
    ap.add_argument('--gap', type=float, default=30, help='minutes; longer gaps do not count as active')
    ap.add_argument('--messages', help='write the recovered user messages to this markdown file')
    a = ap.parse_args()
    cfg = os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude')
    d = a.dir or os.path.join(cfg, 'projects', re.sub(r'[^A-Za-z0-9]', '-', os.getcwd()))
    try:
        since = ts(a.since) if a.since else None
        until = ts(a.until) if a.until else None
    except ValueError as e:
        ap.error(f'--since/--until must be ISO date-times like 2026-10-02T17:55:25 ({e})')
    inside = lambda t: (since is None or t >= since) and (until is None or t <= until)

    mains = sorted(glob.glob(os.path.join(d, '*.jsonl')))
    subs = sorted(p for p in glob.glob(os.path.join(d, '*', 'subagents', '**', '*.jsonl'), recursive=True)
                  if os.path.basename(p).startswith('agent-'))
    if not mains:
        raise SystemExit(f'no transcripts in {d}: run from the project folder you worked in, or pass the folder: '
                         'python transcript_stats.py ~/.claude/projects/<slug>')

    msgs, turns, active, span = [], {}, defaultdict(float), [None, None]
    for path in mains + subs:
        scope = 'main' if path in mains else 'sub'
        sid = os.path.basename(path)[:8]
        stamps = []
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln, line in enumerate(f):
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if not o.get('timestamp'):
                    continue
                t = ts(o['timestamp'])
                if not inside(t):
                    continue
                stamps.append(t)
                typ = o.get('type')
                if typ == 'assistant':
                    m = o.get('message') or {}
                    u, model = m.get('usage'), m.get('model', '?')
                    if not u or model == '<synthetic>':
                        continue
                    key = m.get('id') or o.get('requestId') or o.get('uuid')
                    rec = turns.setdefault(key, {'scope': scope, 'model': model, **{k: 0 for k in F}})
                    for k in F:
                        rec[k] = max(rec[k], u.get(k) or 0)
                    continue
                if scope != 'main':
                    continue
                txt, imgs = None, 0
                if typ == 'user' and not o.get('isSidechain') and not o.get('isMeta'):
                    txt, imgs = text_and_images((o.get('message') or {}).get('content'))
                elif typ == 'attachment' and (o.get('attachment') or {}).get('type') == 'queued_command':
                    txt, imgs = text_and_images(o['attachment'].get('prompt'))
                elif typ == 'queue-operation' and o.get('operation') == 'enqueue':
                    txt = o.get('content') if isinstance(o.get('content'), str) else None
                if txt and txt.strip() and not txt.strip().startswith(SKIP):
                    msgs.append({'t': t, 'sid': sid, 'line': ln, 'imgs': imgs, 'text': txt.strip()})
        stamps.sort()
        active[scope] += sum(g for g in ((b - a_).total_seconds() for a_, b in zip(stamps, stamps[1:])) if g < a.gap * 60)
        if scope == 'main' and stamps:
            span[0] = min(span[0] or stamps[0], stamps[0])
            span[1] = max(span[1] or stamps[-1], stamps[-1])

    msgs.sort(key=lambda r: (r['t'], -r['imgs']))
    kept, last = [], {}
    for r in msgs:
        k = (r['sid'], re.sub(r'\s+', '', r['text'])[:200])
        prev = last.get(k)
        if prev and (r['t'] - prev['t']).total_seconds() < 600:
            prev['imgs'] = max(prev['imgs'], r['imgs'])
            continue
        last[k] = r
        kept.append(r)

    print(f'transcripts: {len(mains)} main, {len(subs)} sub-agent   ({d})')
    if span[0]:
        print(f'wall clock: {span[0].astimezone(LOCAL):%m-%d %H:%M} -> {span[1].astimezone(LOCAL):%m-%d %H:%M}  = {hm((span[1] - span[0]).total_seconds())}')
    print(f'active (gaps < {a.gap:g} min): main {hm(active["main"])}, sub-agents {hm(active["sub"])} (agents run in parallel)')
    print(f'user messages: {len(kept)}  ({sum(1 for r in kept if r["imgs"])} with screenshots, {sum(r["imgs"] for r in kept)} images)')
    agg = defaultdict(lambda: defaultdict(int))
    for r in turns.values():
        g = agg[(r['scope'], r['model'])]
        g['turns'] += 1
        for k in F:
            g[k] += r[k]
    tot_out = sum(g['output_tokens'] for g in agg.values()) or 1
    print(f'\n{"scope":6} {"model":28} {"turns":>7} {"output":>12} {"share":>6} {"cache read":>15} {"cache write":>13} {"input":>10}')
    for (scope, model), g in sorted(agg.items()):
        print(f'{scope:6} {model:28} {g["turns"]:7,} {g["output_tokens"]:12,} {g["output_tokens"] / tot_out:6.1%} '
              f'{g["cache_read_input_tokens"]:15,} {g["cache_creation_input_tokens"]:13,} {g["input_tokens"]:10,}')
    print(f'{"total":35} {sum(g["turns"] for g in agg.values()):7,} {tot_out:12,}')

    if a.messages:
        with open(a.messages, 'w', encoding='utf-8') as f:
            f.write(f'# User messages ({len(kept)})\n\n')
            for i, r in enumerate(kept, 1):
                img = f'  (+{r["imgs"]} img)' if r['imgs'] else ''
                f.write(f'### #{i:03d}  {r["t"].astimezone(LOCAL):%Y-%m-%d %H:%M:%S}  [{r["sid"]} L{r["line"]}]{img}\n{r["text"]}\n\n')
        print(f'\nmessages -> {a.messages}')


if __name__ == '__main__':
    main()
