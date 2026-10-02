"""Cut a character out of a picture with rembg (isnet-anime) and save a transparent PNG.
  <venv python> scripts/cutout.py <in> <out.png> [--model isnet-anime] [--max 3200] [--matting]
The first run downloads the isnet-anime model (about 170 MB) to ~/.u2net, so it needs network access.
"""
import argparse, os, sys
from PIL import Image
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--model', default='isnet-anime')
ap.add_argument('--max', type=int, default=3200, help='downscale longest side before cutting (memory)')
ap.add_argument('--matting', action='store_true', help='alpha matting for soft hair edges (slow)')
a = ap.parse_args()
from rembg import remove, new_session
im = Image.open(a.src).convert('RGB')
if max(im.size) > a.max:
    k = a.max / max(im.size); im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
sess = new_session(a.model)
out = remove(im, session=sess, alpha_matting=a.matting)
out.save(a.dst); print(a.dst, out.size)
