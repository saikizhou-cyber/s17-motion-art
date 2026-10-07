# Deliver mode: render, master, verify, bundle

Use when a Remotion project's shots are approved and the film must be rendered, accepted and handed over. It takes the output of any mode; checks marked (ref) need a reference video (rebuild). `R§n` = section n of `pipeline-recipes.md` (full commands: R§7 render and delivery, R§8 retrospective). Run from the Remotion project root; the tools assume composition `PV`, 1280x720, 30 fps (`render-chunks.mjs` reads `PV_COMP`, `compare.py` takes `--comp`). Cross-mode iron rules (show results not process, say what was not verified) are in SKILL.md.

## 1. Render in chunks

- Never render the whole film in one go: a single long render stalled near frame 725 (heavy WebGL scene). Render frame ranges, e.g. `PV_SCALE=1.5 PV_CONC=2 node $SKILL/scripts/render-chunks.mjs 0-359 360-719 720-899 900-1078`. All ranges are checked before the first render; each segment is silent (`--muted`) and lands as `out/seg_<from>.mp4`.
- `PV_SCALE=1.5` re-rasterises every layer (1280x720 → 1920x1080); it is not an upscale.
- Time budget: 720p full render ~1.5 min, 1080p chunked ~4-5 min.
- A chunk that dies (timeout, `write EOF`): re-render only that chunk, smaller range, `PV_CONC=2`. Do not edit sources while a chunk is bundling. After a one-shot fix, re-render only its chunk and re-join.

## 2. Join and music

- `PV_AUDIO=<track> PV_LUFS=-14 node $SKILL/scripts/render-chunks.mjs --join` → `out/pv.mp4`. `PV_LUFS` masters loudness (two-pass loudnorm, -1 dBTP). `--join` counts frames and refuses segments that do not run straight into each other.
- Segments are silent, so a music swap is a re-join with another `PV_AUDIO`, never a re-render (a 5-second remux).
- Before cutting to a new track: `beat_check.py grid <music>` (tempo grid; on-onset below 60 % means no steady pulse: cut on phrases and hits). After a swap: `beat_check.py check <music>` (cut offsets to the nearest accent, unused strong accents). The reference's own cuts sit within +-2 frames of its accents 40 times in 56; a new track should come close to that, or move the hits.
- The reference's track is used for local timing only and must be replaced before anything is published.

## 3. Acceptance

| Check | Command | Pass |
|---|---|---|
| Size, frames, duration | `ffprobe -v error -show_entries stream=width,height,nb_frames -show_entries format=duration -of compact out/pv.mp4` | expected resolution, `nb_frames` = `DURATION_FRAMES`, duration = frames / 30 |
| A/V sync (ref) | `audio_offset.py <ref> out/pv.mp4` | 0 ms; only meaningful while the film still carries the reference track |
| Freezes, black, flash frames | `film_scan.py out/pv.mp4 --ref <ref>` | every `OURS ONLY` event explained or fixed; `both` = intended; also covers chunk seams |
| Per-shot motion vs the reference (ref) | same `film_scan.py --ref` run (needs `src/core/timeline.ts`) | no shot flagged much stiller or busier |
| Cuts vs music accents | `beat_check.py check <music>` | close to the +-2-frame baseline in section 2 |
| Sharpness | 100% crop of a few frames | no soft or re-scaled layers |

- `film_scan.py` ignores freezes under 0.2 s (stepped holds on 2s are not flagged); a flash is a frame brighter than 150 (of 255) whose luma is >= 60 above the frames two either side. Without `--ref` (and with `REF_VIDEO` unset) it lists events only: judge each against intent.
- Motion comparison uses mean frame difference and the share of near-still frames per shot (cut frames excluded). Stiller = a layer stopped, a clip ended early, a hold left in. Busier = jitter, drift, an AI clip moving more than the reference. Case study: it flagged S36 / S38 (42 % → 79 % and 33 % → 91 % still), S27 (stiller), S49 / S50 (busier) and nothing else.
- Report what was and was not checked; look at a few frames yourself, a scan nobody read verifies nothing.

## 4. Delivery bundle

- Include: final film, silent segments (music swaps later), the project without `node_modules` or venvs (export `pip freeze` instead), AI originals with their prompts, a short retrospective.
- Exclude login and credential files (the Jimeng CLI keeps an auth file in its working folder); scan the bundle for token-like strings before zipping. Redact `state_*.json` / `run_*.json` (project, node and resource ids, signed URLs) before sharing.
- Private bundle only (they embed reference frames): ref|ours sheets, `out/review/ref360`, `out/cmp`, side-by-side videos. Never publish the reference video or its music.
- **Publish check (rebuild):** list the reference's signature elements (logo / title lockup, badges, UI, signature props, effect shapes) and write down how ours differs in shape, not just in words.

## 5. Retrospective

Measure it with `transcript_stats.py` (R§8), do not estimate: `--until <time of the final delivery> --messages ../messages.md`. It reads the Claude Code transcripts (all three user-message record shapes, screenshots included) and gives wall clock, active time, user messages, turns and tokens per model for the main loop and sub-agents. `messages.md` holds your raw prompts: review it before sharing, never put it in a bundle or repo. Credits are derived from the generation state files (successful items × price): say so, it is not an account ledger.

## Known failure modes (deliver)

| Symptom | Cause | Fix |
|---|---|---|
| Render freezes near one frame / `write EOF` | long headless render, heavy WebGL scene | chunks; lower concurrency; smaller range |
| A shot silently stops moving for a second | a layer or clip ends early, a hold left in | `film_scan.py --ref` flags freezes the reference does not have |
| Retrospective undercounts user messages | screenshot messages stored as block lists | `transcript_stats.py` (reads all three record shapes) |

Multi-aspect reflow (9:16 / 1:1): to be added later.
