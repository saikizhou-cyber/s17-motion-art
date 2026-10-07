# Pipeline recipes

Commands that worked in the case study. Run from the Remotion project root unless noted. Paths use forward slashes (Git Bash on Windows, or any POSIX shell). `python` means a Python 3.10+ with Pillow, NumPy, SciPy (`python3` on macOS/Linux). The tools assume a 16:9, 30 fps reference and a 1280x720 composition named `PV`.

```bash
export SKILL="$HOME/.claude/skills/s17-motion-art"   # or <project>/.claude/skills/s17-motion-art
export REF_VIDEO=../reference.mp4                              # used by compare.py and the sheet scripts
# conform a reference that is not 16:9 / 30 fps
ffmpeg -i in.mp4 -vf fps=30,scale=1280:720 -an ../reference.mp4
```

## 1. Reference frames and comparison

```bash
# first cut list + one labelled sheet per window that still needs a look (misses hide there)
python $SKILL/scripts/cut_detect.py "$REF_VIDEO" --out cuts.json --sheets out/review/cuts
python $SKILL/scripts/cut_detect.py "$REF_VIDEO" --truth            # audit an existing timeline.ts
# 640x360 reference frames, file index = frame + 1 (the sheet scripts create these on first use)
mkdir -p out/review/ref360
ffmpeg -v error -y -i "$REF_VIDEO" -vf scale=640:360 -q:v 3 out/review/ref360/r_%04d.jpg
# one exact frame at full resolution, and our render of it
python $SKILL/scripts/frame_measure.py frame "$REF_VIDEO" 985 ref_985.png
npx remotion still PV ours_985.png --frame=985

# chosen frames, ref | ours
python $SKILL/scripts/compare.py --frames 534,540,546 --tag act4
python $SKILL/scripts/compare.py --range 900-1000 --every 10 --tag act8

# whole-film sheets from a sequence render
npx remotion render PV out/seq --sequence --image-format=jpeg
python $SKILL/scripts/grid.py out/seq out/review/grid --which first      # every shot, 3 per row
python $SKILL/scripts/shotsheet.py out/seq out/review/shots --which mid   # one row per shot
python $SKILL/scripts/strip.py out/seq out/review/s54.jpg 940 950 1       # motion of one passage
node $SKILL/scripts/side-by-side.mjs "$REF_VIDEO" out/pv.mp4               # timing, local only
```

Always LOOK at the images; a sheet nobody opened verifies nothing.

## 2. Measuring instead of guessing

```bash
python $SKILL/scripts/frame_measure.py colors ref_985.png --region 0,0,1280,80     # backdrop colour
python $SKILL/scripts/frame_measure.py bbox ours_985.png --color 50,50,55 --tol 60  # where the grey figure sits
python $SKILL/scripts/frame_measure.py components ref_942.png --thr 110            # white blobs: bbox + area
python $SKILL/scripts/frame_measure.py iou ref_942.png ours_942.png                 # overlap of the bright masks
# a move -> Remotion code: tracks a flat-coloured element, fits easing / spring, reports cadence
python $SKILL/scripts/motion_fit.py "$REF_VIDEO" --from 785 --to 805 --color 254,30,32 --region 0,300,1280,720
python $SKILL/scripts/motion_fit.py "$REF_VIDEO" --from 789 --to 801 --color 254,30,32 --channel z   # perspective fly-in
```

- **Effect shapes** (a bullet trace, a slash, a shard): `components` gives each part's footprint (bbox, size), and the angle and timing come from the frames around it. Draw your OWN shape in that footprint (SVG polygons; fur or teeth as thin slivers along an edge with a seeded RNG), render, and use `iou` only to check size and placement. Do not trace the outline of someone else's artwork.
- **The same figure across shots**: measure the bbox in every shot, choose one target from the reference, then put the numbers in one shared constant, e.g.
  `export const CLIMAX_HERO = {face: [275, 492], faceH: 34.3, lean: 6};` and use it in each shot (and in the flash frames between them) instead of per-shot copies.
- **Colours from the real frame.** A user's screenshot may be gamma-lifted (pure black looked like #111); sample the decoded frame.
- **Text planes**: fit a homography to the four corners of the reference's text block and apply it as a CSS `matrix3d`.

## 3. Per-shot art slot (character swap)

```ts
shots: [{shot: 'S55', src: 'characters/hero/H32_recoil.png', mode: 'cutout', focus: {...}, video: 'characters/hero/V5_recoil_slowmo.mp4',
         videoStart: 0, videoRate: 1, key: '#267dae', hair: 'characters/hero/H32_recoil_hair.png', skin: ['#f0e8e4', '#c4c2c4']}]
```

- `cutout`: placed by `focus` (face centre, hairline-to-chin, eye line, hand/prop point); `frame`: a 16:9 composition drawn whole.
- `video` + `key` (flat backdrop colour; make it ~15% greyer than the measured clip colour) plays a clip in the same framing as the still.
- `hair`: a soft matte for a hair-only flutter on stills (skipped when a clip plays).
- `skin: [lit, shadow]` flattens warm pixels into two tones, e.g. a reference's flat grey skin.

## 4. AI generation (Jimeng / 即梦 canvas CLI)

The CLI is `dreamina-canvas`. Official installers: `curl -fsSL https://jimeng.jianying.com/canvas-cli/install.sh | bash` (macOS/Linux) or `irm https://jimeng.jianying.com/canvas-cli/install.ps1 | iex` (Windows PowerShell). The scripts look for `~/bin/dreamina-canvas(.exe)`; point `JIMENG_CLI` at it if it lives elsewhere. The user logs in themself (`auth login` gives a device challenge, finish with `auth wait --device-code`). Set `JIMENG_PROJECT_ID` to your canvas project.

Job files: `jobs.json` = `[{"key": "hero_hit_a", "mode": "t2i", "ratio": "3:4", "prompt": "...", "refs": ["node_xxx"]}]` (`mode` t2i or i2i; `refs` optional); `jobs_v.json` = `[{"key": "V1_recoil", "ratio": "16:9", "ref": "node_xxx", "prompt": "describe the motion"}]`.

```bash
python $SKILL/scripts/jm.py node create image --project-id $JIMENG_PROJECT_ID --mode t2i --model seedream_5.0_pro \
  --ratio 3:4 --resolution 2K --prompt @prompt.txt --run --credit-ceiling 8 --wait      # @file = UTF-8 prompt
python $SKILL/scripts/jm.py resource download <resourceId> --project-id $JIMENG_PROJECT_ID -o out.png

python $SKILL/scripts/jimeng_batch_run.py jobs.json --tag hero_hit --budget 40          # images, 8 credits each
python $SKILL/scripts/jimeng_video_run.py jobs_v.json --budget 48                       # 4 s clips, 24 credits each

# your own pose guide as a reference image (never a reference frame)
python $SKILL/scripts/jm.py resource upload --file pose.png --project-id $JIMENG_PROJECT_ID
python $SKILL/scripts/jm.py node create image --project-id $JIMENG_PROJECT_ID --resource-id <rid> --import-kind local_upload
```

- Always go through `jm.py` or the batch runners: Git Bash mangles CJK arguments.
- Use a new `--tag` per batch; the runner counts spend from `state_<tag>.json`, so a shared state file eats the next budget.
- Prompting that worked: reference the face node and the prop node with `{{node:id}}`; ask for a flat grey or blue backdrop for easy cutout; "单一角色，无文字，无水印"; state hands and fingers; say what must NOT change when editing a pose. Pose control: draw a grey stick figure with PIL, upload it, and write "严格按照示意图的姿势".
- Props as "白色哑光陶土材质的3D渲染" on a neutral grey background cut out cleanly and map to a two-tone toon palette in code.
- Any other generator works the same way: our stills in, motion described in words, never the reference's frames.

## 5. Cutting out, keying, clip fixes

```bash
tools/.venv-cutout/Scripts/python $SKILL/scripts/cutout.py in.png cut.png   # POSIX: tools/.venv-cutout/bin/python
python $SKILL/scripts/cleanedge.py in.png cut.png out.png 1           # de-halo + erode 1 px
python $SKILL/scripts/bluekey.py frame.png out.png 38 80              # flat-blue 16:9 frame -> alpha
python $SKILL/scripts/hairfix.py in.mp4 out.mp4 0.55                  # pull drifted brown hair back to near-black
python $SKILL/scripts/irisglow.py in.mp4 out.mp4 0.95 1.2             # dull iris before the eyes open, ignite after
```

Install rembg in an isolated venv: `python -m venv tools/.venv-cutout`, then `tools/.venv-cutout/Scripts/pip install "rembg[cpu]"` (POSIX: `tools/.venv-cutout/bin/pip`). A global install broke Pillow for other tools. The first cutout downloads the isnet-anime model (~170 MB) into `~/.u2net`, so it needs network access.

## 6. Slow motion

```bash
ffmpeg -i clip.mp4 -an -vf "setpts=PTS/0.35,minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:scd=none" \
  -c:v libx264 -crf 14 -pix_fmt yuv420p slow.mp4
```

Play the result at rate 1. Check interpolated frames for ghosting around hair; feather the clip border into the key colour so scaling does not leave a 1-px dark line.

## 7. Rendering and delivery

```bash
PV_SCALE=1.5 PV_CONC=2 node $SKILL/scripts/render-chunks.mjs 0-359 360-719 720-899 900-1078
PV_AUDIO=public/audio/bgm.wav PV_LUFS=-14 node $SKILL/scripts/render-chunks.mjs --join   # -> out/pv.mp4, music mastered
ffprobe -v error -show_entries stream=width,height,nb_frames -show_entries format=duration -of compact out/pv.mp4
python $SKILL/scripts/audio_offset.py "$REF_VIDEO" out/pv.mp4      # 0 ms while timing against the reference track
python $SKILL/scripts/film_scan.py out/pv.mp4 --ref "$REF_VIDEO"   # freezes / black / flashes the reference lacks
python $SKILL/scripts/beat_check.py grid music.wav                 # tempo grid before cutting to new music
python $SKILL/scripts/beat_check.py check music.wav                # after a music swap: cuts vs accents
```

- A chunk that fails with a timeout or `write EOF`: re-render only that chunk, smaller range, `PV_CONC=2`. Do not edit sources while a chunk is bundling. After a one-shot fix, re-render only its chunk and re-join.
- Check a 100% crop for sharpness; `film_scan.py` covers the chunk seams.
- **Swap the music without re-rendering**: segments are rendered `--muted`, so `--join` again with another `PV_AUDIO`. The reference's own cuts sit within +-2 frames of its accents 40 times in 56; a new track should come close to that, or move the hits.

- **Delivery bundle**: final film + silent segments (music swaps later) + project without `node_modules`/venvs (export `pip freeze` instead) + AI originals with their prompts + a short retrospective. Exclude login and credential files (the Jimeng CLI keeps an auth file in its working folder); scan the bundle for token-like strings before zipping. ref|ours sheets, `out/review/ref360`, `out/cmp` and side-by-side videos embed reference frames: private bundle only, never shared publicly. Redact `state_*.json` / `run_*.json` (project, node and resource ids, signed URLs) before sharing. Keep the reference video and its music out of anything public.

## 8. Retrospective numbers

```bash
python $SKILL/scripts/transcript_stats.py --until 2026-01-31T18:00:00 --messages ../messages.md
```

Reads `~/.claude/projects/<slug of cwd>/` (or a folder you pass): wall clock, active time, user messages (all three record shapes, screenshots included), turns and tokens per model for the main loop and sub-agents. The wall clock runs to `--until` (or the last record); pass the time of the final delivery to measure the project itself. `messages.md` holds your raw prompts: review it before sharing, never put it in a delivery bundle or a repo. Credits are derived from the generation state files (successful items × price); say so, it is not an account ledger.

## 9. Workflow script pattern (Claude Code sub-agents)

Pseudo-code for Claude Code's Workflow tool (`pipeline` and `agent` exist only inside a workflow script). Without it, run the same three steps by hand as sub-agents (Agent tool) with `model: sonnet` and the same prompt rules.

```js
const results = await pipeline(TASKS,
  t => agent(implPrompt(t), {model: 'sonnet', label: `impl:${t.key}`, phase: 'Implement', schema: RESULT}),
  (r, t) => agent(critPrompt(t, r), {model: 'sonnet', label: `crit:${t.key}`, phase: 'Critique', schema: CRIT}).then(c => ({impl: r, crit: c})),
  (r, t) => r.crit.verdict === 'good' ? r : agent(refinePrompt(t, r), {model: 'sonnet', label: `refine:${t.key}`, phase: 'Refine', schema: RESULT}))
```

Prompt rules: list the files each agent may edit and forbid the rest; give render/compare commands and frame numbers; require `tsc` green; put required outside changes into `outside_requests`; tell agents to ignore unrelated relayed user messages; ask critics to check every numbered user note.
