---
name: reference-video-rebuild
description: Rebuild a reference video (game PV, trailer, motion-graphics piece) shot-for-shot as an editable Remotion project with ORIGINAL characters, copy and art, then deliver a 1080p film. Covers shot breakdown and measuring against the reference, per-act parallel builds with sub-agents, per-shot character art/video slots, AI-generated props and poses (Jimeng/即梦 canvas CLI or any image/video generator) plus cutout and keying tools, side-by-side QA, chunked 1080p rendering, music swap without re-rendering, delivery bundle and a measured retrospective. Use for "复刻PV", "1比1复刻原片", "换成我自己的角色", "做成可换角色的模板", "按原视频做动效和排版", "recreate this trailer with my own characters", or any request to recreate a video's structure, motion and layout while swapping the content.
license: MIT
---

# Reference Video Rebuild (Remotion + AI assets)

Measured on one real run (36 s game PV, 57 shots, 8 acts, 1080p delivered): ~66.7 h wall clock, ~18.8 h active, 113 user messages, 11,467 model turns, 13.4 M output tokens, 130 AI generations (1,184 Jimeng credits). Full story: `references/case-study-gamepv.md`. Commands: `references/pipeline-recipes.md`. Tools: `scripts/` (table below).

## Non-negotiables

1. **Judge against the ORIGINAL reference, never against your previous version.** "1:1" means pose, composition, position, size, perspective, colour and timing match. Measure (full-resolution frames, `scripts/frame_measure.py`, homography fits); do not eyeball "similar".
2. **Original content only.** Never generate, cut out, trace or imitate a franchise character, logo, wordmark or title lockup, UI skin, signature prop or emblem, custom lettering, lyric or music, even when asked; offer an original design in the same style. "1:1" applies to measured layout, size, timing and palette, never to copied outlines or glyph construction. Reference frames are never fed to a generator: describe motion in text or upload a self-drawn pose guide. The reference's music is for local timing checks only. Before anything is published, check every lockup, badge and effect shape against the reference for lookalikes.
3. **Static first, then motion.** Lock each shot's still side by side with the reference; generate a video only for a pose the user accepted (5 of 9 clips in the case study were never used).
4. **Sub-agents run on a mid-tier model** (`model: 'sonnet'` on every `agent()` call in Claude Code workflows). Keep root cause, design and accepting results in the main model. In the case study, sub-agents that silently inherited Opus produced 84% of sub-agent output tokens and hit the usage limit 5 times.
5. **Budget generation credits explicitly** before spending (image 8, 4 s video 24 on Jimeng seedream 5.0 pro / seedance 2.0 mini at the time) and report spend as derived from files, not as an account ledger.
6. **One placement per figure across a sequence.** When the same character appears in consecutive shots, drive all of them (including 1–2-frame flashes and transitional silhouettes) from one shared constant (face point, face height, lean). Separate numbers per shot drift and the figure visibly jumps.
7. **Show results, not process**, unless the user asks for the process. Verify before saying "done" and say what was not verified.

## Workflow

1. **Break the reference down.** The tools assume 16:9 at 30 fps; conform other sources first (`ffmpeg -i in.mp4 -vf fps=30,scale=1280:720 -an reference.mp4`). Cut list (frame-accurate), per-shot layout, flat colours, type, motion and cadence into `docs/shot-breakdown.md`; cache 640x360 reference frames (`out/review/ref360/r_%04d.jpg`, file index = frame + 1). Group shots into acts.
2. **Pick the stack.** Remotion + zod (React, TypeScript): composition `PV`, 1280x720, 30 fps (or pass `--comp` / `PV_COMP`); one folder and one schema per act, all defaults original, one `defaultConfig` so a swap is one edit. Keep the cut list in `src/core/timeline.ts`, one shot per line in seconds, e.g. `{id: 'S01', start: 0.0, end: 0.933, act: 'act1', kind: 'digital clock'},` (the last may use `end: DURATION_S`), plus `export const DURATION_FRAMES = <n>;`. The QA scripts parse it.
3. **Build per act in parallel.** One agent per act owning only its files; `npx tsc --noEmit` green before and after. Split big builds into batches that each persist to disk (a 14-agent build was once lost whole to a usage limit).
4. **Per-shot art slots.** `characters.*.shots[]`: `src, mode cutout|frame, focus, flip, overlays, alt, front, video, videoStart, videoRate, key, hair, skin`, all optional so defaults render unchanged; acts read the slot's own focus, so a swapped character needs no per-act code.
5. **Static design boards.** Render each shot's key frame next to the reference (`compare.py`, `shotsheet.py`) and get approval per shot before animating.
6. **AI assets** for what code draws badly (props, concept cards, desk plates, character poses, short clips): generate, cut out (`cutout.py` + `cleanedge.py`), key flat backdrops (`bluekey.py`), then stylise in code (gradient map to the shot palette). Slow motion = optical-flow interpolation, never plain slow playback.
7. **QA loop = pipeline(implement → critique → refine)** per task, files owned per agent. Critics never edit; they build ref|ours sheets (`grid.py`, `shotsheet.py`, `strip.py`) and list concrete defects; the main model verifies before accepting.
8. **Triage feedback** from screenshots into a per-shot tracker (shot, note, owner, status). Feedback arrives mid-turn: tell agents to ignore relayed messages that are not their task. Sample colours and shapes on the real frame, not on the user's screenshot (viewer gamma lifts black to grey).
9. **Render in chunks** (`render-chunks.mjs`): a single long render stalled near frame 725. 1.5x scale re-rasterises every layer (1280x720 → 1920x1080). Verify size, frame count, duration, audio sync (`audio_offset.py`, expect 0 ms) and seam frames. Segments are silent, so music is swapped by re-joining, never by re-rendering.
10. **Deliver and look back.** Bundle film, silent segments, project (no `node_modules`, no venvs), AI originals with their prompts and a short retrospective; exclude login/credential files. ref|ours sheets, `out/review/ref360`, `out/cmp` and side-by-side videos embed reference frames: keep them in a private bundle only, never in anything shared publicly, and never publish the reference or its music. Redact generation state/run files (project, node and resource ids) before sharing. Measure the retrospective with `transcript_stats.py` instead of estimating.

## Model and cost policy

| Work | Model |
|---|---|
| Per-act implementation, critique, refine, bulk fixes, fact gathering, document drafts | mid-tier (Sonnet) |
| Root cause, design decisions, measuring the reference, accepting results, final QA | main model |

Benchmarks from the case study: main loop 1,102 turns / 1.13 M output tokens; sub-agents 10,365 turns / 12.3 M output tokens; ~2.56 B cache-read tokens. A 720p full render takes ~1.5 min, a 1080p chunked render ~4–5 min; a Jimeng image 60–100 s, a 4 s clip ~110 s.

## Review checklist (each shot)

- **Geometry:** pose, size, position, crop vs the reference at full resolution; same figure = same numbers across shots.
- **Colour:** modal flat colours of backdrop, skin, shadow (`frame_measure.py colors`); one theme change can shift 20+ shots, re-measure per act.
- **Type:** same face and weight, square punctuation if the reference has it, perspective plane, no outline unless the reference has one.
- **Effect shapes** (streaks, slashes, shards): measure footprint, angle, timing and palette from the reference frame (`frame_measure.py components/bbox`), then draw your OWN shape in that footprint; use `iou` to check size and placement, not to clone an outline.
- **Motion:** stepped cadence (the reference often holds on 2s), no invented jitter on character art, optical-flow slow motion.
- **Edges:** keyed clips need their border clipped; skin flattening must composite arithmetically; look for 1-px lines at frame edges.

## Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Whole build returns empty | usage limit mid-workflow | batch the work, persist per batch, resume |
| User keeps rejecting "similar" shots | eyeballing | measure; overlay or IoU against the reference |
| Figure jumps between consecutive shots | per-shot placement numbers | one shared placement constant |
| Agents redo stale requests | feedback relayed mid-turn | per-agent scope; "ignore unrelated relayed messages" |
| AI clip with the wrong pose, cropped figure | video before an approved still | approve the still; zoomed-out still; pose guide image |
| Half-transparent edges show the backdrop | `merge` composite in a skin filter | arithmetic composite |
| 1-px dark line on a keyed clip | edge pixels mixed with the key when scaled | clip the border (`clip-path: inset(0.6%)`) |
| Render freezes near one frame / `write EOF` | long headless render, heavy WebGL scene | chunks; lower concurrency; smaller range |
| Retrospective undercounts user messages | screenshot messages stored as block lists | `transcript_stats.py` (reads all three record shapes) |
| A motif the reference does not have (e.g. clocks) | the builder's own theme leaked in | check every motif against the reference |
| Own brand lockup reads as the original's logo | "1:1" applied to glyph construction (pixel letters, stencil line, bevelled slab) | match only position, size and timing; design the letterforms from scratch |

## Scripts

| Script | Purpose |
|---|---|
| `compare.py` | render chosen frames and pair them with the reference: `out/cmp/<tag>/compare.jpg` |
| `shotsheet.py`, `grid.py`, `strip.py` | ref\|ours sheets: one row per shot, all shots at a glance, a frame range of one shot |
| `side-by-side.mjs` | ref\|ours video for timing (local only) |
| `frame_measure.py` | frame grab, modal colours, blobs, edge runs, figure bbox, IoU |
| `cutout.py`, `cleanedge.py`, `bluekey.py` | rembg cutout, de-halo, flat-backdrop key |
| `hairfix.py`, `irisglow.py` | colour fixes on AI clips (hair drift, iris lighting timed to the eyes opening) |
| `jm.py`, `jimeng_batch_run.py`, `jimeng_video_run.py` | Jimeng canvas CLI: Unicode-safe wrapper, budgeted image and video batches |
| `render-chunks.mjs` | chunked render and join with any music (`PV_AUDIO`) |
| `audio_offset.py` | A/V sync check by cross-correlation |
| `transcript_stats.py` | retrospective numbers from Claude Code transcripts |

Python 3.10+ with Pillow, NumPy, SciPy; `cutout.py` needs `rembg` (install it in its own venv). ffmpeg/ffprobe on PATH; Node 18+ for Remotion.
