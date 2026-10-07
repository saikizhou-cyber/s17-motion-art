---
name: s17-motion-art
description: Make PV, trailer and motion-graphics films with CODE (Remotion, React + TypeScript). From an idea, a world or a song to three creative directions, a beat-cut shot list and an animatic; animate kinetic type, transitions, camera moves and rhythm in code; realize shots with the user's own characters, props and scenes through asset cards (AI only for still art); rebuild a reference video 1:1 by measuring its cuts, colours and motion (easing / spring / perspective fits); deliver 1080p with music swap, loudness and automatic QA. Use for "做PV", "做动效", "动态字", "卡点剪辑", "预告片", "用我的角色/道具/场景做画面", "复刻PV", "1比1复刻原片", "按原视频做动效和排版", "make a trailer / motion graphics", or any request to design or animate a short film in code.
license: MIT
---

# PV motion in code (Remotion)

Motion is code: kinetic type, transitions, camera, effects and rhythm are Remotion components driven by the frame number, cut to a beat grid. AI only makes still art that code draws badly (characters, props, plates), and only when the user has none. Measured on one real 36 s / 57-shot PV (66.7 h wall clock, 18.8 h active, 13.4 M output tokens): `references/case-study-gamepv.md`. Every command: `references/pipeline-recipes.md`.

## Pick the mode

| Mode | When | Read |
|---|---|---|
| **create** | an idea, a world or a song, no reference: directions → style bible → beat-cut shot list → animatic → film | `references/create.md` |
| **realize** | the user's own characters, props or scenes must appear exactly as specified | `references/asset-cards.md` |
| **rebuild** | a reference video whose structure, motion and layout are reproduced 1:1 with original content | `references/rebuild.md` |
| **deliver** | every film ends here: chunked render, music swap, loudness, QA, bundle, retrospective | `references/deliver.md` |

Modes combine: create or rebuild for the film, realize for its assets, deliver to finish.

## Rules for every mode

1. **Motion is code, and deterministic.** Everything is a function of the frame (seeded randomness, no wall clock, no CSS animations). AI generates still assets only; an AI clip is a last resort for one pose the user already approved as a still.
2. **Original content only.** Never generate, cut out, trace or imitate a franchise character, logo, wordmark or title lockup, UI skin, signature prop, custom lettering, lyric or music, even when asked; offer an original design in the same style. Learn grammar (layout, timing, palette), never copy pictures or glyph construction.
3. **Still before motion.** Approve the direction, the animatic and the key static boards before animating; build the climax first, it takes the most rounds.
4. **Measure, don't eyeball.** Frames and colours (`frame_measure.py`), moves (`motion_fit.py`: easing, spring, perspective depth, cadence), music (`beat_check.py`), the render (`film_scan.py`). Same figure in consecutive shots = one shared placement constant.
5. **Builders don't judge their own work.** Sub-agents build on a mid-tier model (`model: 'sonnet'`); the main model decides. Critics look only at the render (with the reference or the approved boards), compare two versions in both orders to cancel position bias, report what they see rather than how to fix it, and every accepted fix comes with a before/after frame.
6. **Budget before spending:** AI credits and render time up front; report spend as measured from files.
7. **Show results, not process.** Verify before saying "done", and say what was not verified.

## Scripts

| Job | Scripts |
|---|---|
| Measure | `frame_measure.py` (frame, colours, blobs, bbox, IoU) · `motion_fit.py` (a move → Remotion `interpolate`/`spring` code) · `cut_detect.py` (cuts + review sheets) |
| Compare with a reference | `compare.py` · `shotsheet.py` · `grid.py` · `strip.py` · `side-by-side.mjs` (local only) |
| Music and timing | `beat_check.py` (tempo grid; cuts vs accents) · `audio_offset.py` (A/V sync) · `animatic.py` (boards + music → rough cut) |
| Still assets | `cutout.py` · `cleanedge.py` · `bluekey.py` · `hairfix.py` · `irisglow.py` · `jm.py` · `jimeng_batch_run.py` · `jimeng_video_run.py` |
| Render and QA | `render-chunks.mjs` (chunks, join, `PV_AUDIO`, `PV_LUFS`) · `film_scan.py` (freezes, black, flashes, motion vs reference) |
| Retrospective | `transcript_stats.py` (time, messages, tokens per model) |

Python 3.10+ with Pillow, NumPy, SciPy; `cutout.py` needs `rembg` in its own venv. ffmpeg/ffprobe on PATH; Node 18+ for Remotion.
