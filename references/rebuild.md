# Rebuild mode: 1:1 reproduction of a reference video

Use when the user supplies a reference video and wants its structure, motion and layout reproduced with ORIGINAL characters, copy and art as an editable Remotion project. `R§n` = section n of `pipeline-recipes.md` (all commands live there; `R§0` = its preamble). Finish with `deliver.md`. Cross-mode iron rules (original content only, static first then motion, mid-tier sub-agents, credit budget, show results not process) are in SKILL.md and apply here.

**Motion is code.** Transitions, kinetic type, camera moves, cadence and rhythm are Remotion (React + TypeScript). AI makes still assets only (poses, props, plates, cards). An AI clip in a `video` slot is an optional extra for a few hero shots, never the default: if a shot can be animated in code, do that.

## Rebuild-only rules

1. **Judge against the ORIGINAL reference, never against your previous version.** "1:1" means pose, composition, position, size, perspective, colour and timing match. Measure it (full-resolution frames, `frame_measure.py`, homography fits; R§2). Do not eyeball "similar".
2. **"1:1" is about measured layout, size, timing and palette, never copied construction.** Never carry over outlines or glyph construction of logos, lettering, signature props or effect shapes: measure the footprint, then draw your OWN shape in it (`iou` checks size and placement, not outline cloning).
3. **Reference frames never go into a generator.** Describe motion in text or upload a self-drawn pose guide (R§4). The reference's music is for local timing checks only and is replaced before delivery (`deliver.md`).
4. **One placement per figure across a sequence.** When the same character appears in consecutive shots (including 1-2-frame flashes and transitional silhouettes), drive all of them from one shared constant (face point, face height, lean), e.g. `export const CLIMAX_HERO = {face: [275, 492], faceH: 34.3, lean: 6};` (R§2). Separate numbers per shot drift and the figure visibly jumps.
5. **Lookalike check before anything is published**: every lockup, badge and effect shape against the reference (procedure in `deliver.md`, Publish check).

## Workflow

1. **Break the reference down.** The tools assume 16:9 at 30 fps; conform other sources first (R§0). Build the cut list frame-accurately: start from `cut_detect.py`, then confirm every cut and each review window on the actual frames (R§1). Record per-shot layout, flat colours, type, motion and cadence in `docs/shot-breakdown.md`. Cache 640x360 reference frames at `out/review/ref360/r_%04d.jpg` (file index = frame + 1). Group shots into acts.
2. **Pick the stack.** Remotion + zod (React, TypeScript): composition `PV`, 1280x720, 30 fps (other ids: `PV_COMP` for `render-chunks.mjs`, `--comp` for `compare.py`); one folder and one schema per act; all defaults original; one `defaultConfig` so a character swap is one edit. Keep the cut list in `src/core/timeline.ts`, one shot per line in seconds (the last may use `end: DURATION_S`), plus the frame total; the QA scripts parse it:
   `{id: 'S01', start: 0.0, end: 0.933, act: 'act1', kind: 'digital clock'},` and `export const DURATION_FRAMES = <n>;`
3. **Build per act in parallel.** One agent per act owning only its files (sub-agents on a mid-tier model); `npx tsc --noEmit` green before and after. Split big builds into batches that each persist to disk (a 14-agent build was once lost whole to a usage limit). Workflow pattern: R§9.
4. **Per-shot art slots.** `characters.*.shots[]`: `src, mode cutout|frame, focus, flip, overlays, alt, front, video, videoStart, videoRate, key, hair, skin`, all optional so defaults render unchanged. Acts read the slot's own `focus`, so a swapped character needs no per-act code (R§3).
5. **Static design boards before motion.** Render each shot's key frame next to the reference (`compare.py`, `shotsheet.py`; R§1) and get approval per shot before animating; bring the climax shots to final quality first, they take the most rounds. Generate a clip only for a pose the user already accepted as a still (5 of 9 clips in the case study were never used). Timing against the reference: `side-by-side.mjs` (local only).
6. **AI assets** for what code draws badly (props, concept cards, desk plates, character poses): budget credits first (Jimeng at the time: image 8, 4 s clip 24; image 60-100 s, clip ~110 s), generate with `jm.py` / `jimeng_batch_run.py` / `jimeng_video_run.py` (R§4), cut out (`cutout.py` + `cleanedge.py`), key flat backdrops (`bluekey.py`) (R§5), then stylise in code (gradient map to the shot palette). If a clip is used: colour fixes `hairfix.py` / `irisglow.py`; slow motion = optical-flow interpolation, never plain slow playback (R§6).
7. **QA loop = pipeline(implement → critique → refine)** per task, files owned per agent (R§9). Critics never edit: they build ref|ours sheets (`grid.py`, `shotsheet.py`, `strip.py`) and list concrete defects; the main model verifies before accepting. Open the sheets and LOOK. When two versions compete, ask "which is closer to the reference" twice with the order swapped; accept a fix only with its before/after frames.
8. **Triage feedback** from screenshots into a per-shot tracker (shot, note, owner, status). Feedback arrives mid-turn: tell agents to ignore relayed messages that are not their task. Sample colours and shapes on the real frame, not on the user's screenshot (viewer gamma lifts black to grey).

## Review checklist (each shot)

- **Geometry:** pose, size, position, crop vs the reference at full resolution; same figure = same numbers across shots.
- **Colour:** modal flat colours of backdrop, skin, shadow (`frame_measure.py colors`); one theme change can shift 20+ shots, re-measure per act.
- **Type:** same face and weight, square punctuation if the reference has it, perspective plane, no outline unless the reference has one.
- **Effect shapes** (streaks, slashes, shards): measure footprint, angle, timing and palette from the reference frame (`frame_measure.py components/bbox`), then draw your OWN shape in that footprint; use `iou` to check size and placement, not to clone an outline.
- **Motion:** measure each move of the reference with `motion_fit.py` (R§2) and paste its `interpolate`/`spring` code instead of guessing easing; it also reports cadence (held on 2s) and perspective fly-ins (`--channel z`). No invented jitter on character art; optical-flow slow motion.
- **Edges:** keyed clips need their border clipped; skin flattening must composite arithmetically; look for 1-px lines at frame edges.

## Known failure modes (rebuild)

| Symptom | Cause | Fix |
|---|---|---|
| Whole build returns empty | usage limit mid-workflow | batch the work, persist per batch, resume |
| User keeps rejecting "similar" shots | eyeballing | measure; overlay or IoU against the reference |
| Figure jumps between consecutive shots | per-shot placement numbers | one shared placement constant |
| Agents redo stale requests | feedback relayed mid-turn | per-agent scope; "ignore unrelated relayed messages" |
| AI clip with the wrong pose, cropped figure | video before an approved still | approve the still; zoomed-out still; pose guide image |
| Half-transparent edges show the backdrop | `merge` composite in a skin filter | arithmetic composite |
| 1-px dark line on a keyed clip | edge pixels mixed with the key when scaled | clip the border (`clip-path: inset(0.6%)`) |
| A motif the reference does not have (e.g. clocks) | the builder's own theme leaked in | check every motif against the reference |
| Own brand lockup reads as the original's logo | "1:1" applied to glyph construction (pixel letters, stencil line, bevelled slab) | match only position, size and timing; design the letterforms from scratch |

Render and delivery failures (freezes, `write EOF`, stalled shots, retrospective miscount): `deliver.md`.
