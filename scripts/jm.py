"""Unicode-safe wrapper around the Jimeng canvas CLI (Git Bash mangles CJK argv).

  python scripts/jm.py <args...>         # args passed verbatim to dreamina-canvas (path: $JIMENG_CLI, else ~/bin/dreamina-canvas)
  python scripts/jm.py node create image ... --prompt @path/to/prompt.txt     # or --prompt=@path/to/prompt.txt
An argument of the form @file (after --prompt/--title, or as --prompt=@file / --title=@file) is replaced
by that file's UTF-8 text. Always adds --format json; prints the JSON response.
"""
import json
import os
import shutil
import subprocess
import sys

EXE = os.environ.get('JIMENG_CLI') or os.path.expanduser('~/bin/dreamina-canvas' + ('.exe' if os.name == 'nt' else ''))


def read(path):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read().strip()
    except OSError as e:
        sys.exit(f'cannot read {path}: {e.strerror}')


def main() -> int:
    args = sys.argv[1:]
    if not args or args in (['-h'], ['--help']):
        sys.exit(__doc__)
    if not (os.path.isfile(EXE) or shutil.which(EXE)):
        sys.exit(f'Jimeng CLI not found: {EXE} (install it, or set JIMENG_CLI to its path)')
    out = []
    for i, a in enumerate(args):
        if a.startswith('@') and i > 0 and args[i - 1] in ('--prompt', '--title'):
            a = read(a[1:])
        elif a.startswith(('--prompt=@', '--title=@')):
            k, _, v = a.partition('=')
            a = f'{k}={read(v[1:])}'
        out.append(a)
    r = subprocess.run([EXE, '--format', 'json', *out], capture_output=True)
    text = r.stdout.decode('utf-8', 'replace') or r.stderr.decode('utf-8', 'replace')
    sys.stdout.reconfigure(encoding='utf-8')
    print(text)
    return r.returncode


if __name__ == '__main__':
    sys.exit(main())
