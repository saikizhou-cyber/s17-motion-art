# Create mode: from a line, a world or a song to an executable PV plan

Use when there is no reference video to rebuild. Output: `docs/direction.md` (options, then the chosen one), `docs/style-bible.md`, `docs/shot-list.md`, a rough-cut animatic, then the film. The rules in SKILL.md (original content, static before motion, measure, mid-tier sub-agents, explicit credit budget) apply unchanged.

**Stance.** This skill makes motion with code. Kinetic type, transitions, camera moves, effects and rhythm are Remotion (React + TypeScript), cut to a beat grid. AI generates only static assets that code draws badly (character art, props, plates). An AI video clip is an optional extra for a pose the user already approved as a still, never the default; a plan that only works with generated clips gets redesigned.

## 1. Brief intake

Ask all five in ONE message, each with its default. Anything unanswered takes the default and is listed under "assumed" at the top of `direction.md`; do not block on it.

| # | Item | Ask | Default |
|---|---|---|---|
| 1 | World | one-sentence premise, genre, 3 mood words | write the premise from the user's line; if there is none, an original near-future action fantasy |
| 2 | Cast | who, age/role, one silhouette trait, one signature prop | 1 hero + 1 rival, original designs; the hero's prop returns in every act |
| 3 | Brand | name, wordmark text, tagline, partner line | invented placeholder name (<= 8 letters), tagline <= 4 words, lettering designed from scratch; mark it "placeholder" |
| 4 | Music | a track the user owns or licensed / tempo and mood / none | track: go to section 4 with it. None: plan on a 120 BPM grid (15 frames per beat at 30 fps), render silent, re-snap with `beat_check.py check` when music arrives |
| 5 | Format | platform, aspect, length | 16:9, 30 fps, composition 1280x720 rendered at 1.5x, 30-40 s. Other aspects: compose natively (e.g. 720x1280) and keep type inside safe margins |

## 2. Three directions (gate 1)

Give every direction a value on each of seven axes:

1. **Palette**: dominant + accent + neutrals as hex, and the accent's share of the frame.
2. **Type**: face class, weight, case, layout logic (flat, perspective plane, stacked, vertical).
3. **Motion grammar and rhythm**: the verbs (snap, slide, stamp, glitch, wipe) and the unit they move in (every frame, on 2s, on the beat).
4. **Camera**: locked, push-in, whip, orbit, parallax; flat 2D or perspective.
5. **Motif prop**: the one object that recurs and how it changes across the film.
6. **Texture and finish**: flat colour, grain, halftone, paper, scanlines; what the post pass adds.
7. **Music temperament**: tempo range, steady or broken pulse, section shape.

Rules:
- Three directions differ on at least 3 axes (not only palette). Compare row by row; if two agree on 5 or more axes, replace one.
- Every choice reads "because <a fact about the cast, world or music>, so <this treatment>". Bare adjectives ("cool", "premium", "cinematic") are not allowed; write numbers (hex, px at 720p, frames, shots per second).
- Anti-repetition: read earlier `docs/direction.md` files and PVs in the repo; the new directions may not repeat the last film's accent + type class + motion verb. Also off the table by default: navy + cyan/magenta neon, glass cards, a centred sans title with a lens flare.
- Borrow grammar, never pictures. A known PV may teach a single accent colour on black and white, type on a perspective plane, shot lengths rounded to beats, a 1-frame black flash before the climax, ID cards. Its characters, logo shapes, lettering and compositions stay out (SKILL.md rule 2).
- Spread the risk: one direction fits the music most safely, one is bold, one is an outside bet.

Template for `docs/direction.md` (one block per direction):

```markdown
## Direction A: <2-3 word name>
<one line: what it looks and feels like>
| Axis | Choice (numbers) | Because ... so ... |
|---|---|---|
| Palette | bg #0B0B0F, ink #F2EFE6, accent #FF3B2E (<= 12% of frame) | because the hero's flare is red, so red appears only where the flare is |
| Type | ... | ... |
| Motion and rhythm | ... | ... |
| Camera | ... | ... |
| Motif prop | ... | ... |
| Texture and finish | ... | ... |
| Music | ... | ... |
Differs from B on: palette, camera, texture (3).  Risk: ...  Cost: tier mix from section 5.
```

Show the three side by side and let the user pick one, or mix by axis ("A's type, B's camera"). Non-interactive run: pick the direction with the lowest asset cost that fits the music, and write why.

## 3. Style bible (after the pick)

`docs/style-bible.md`, one page, mirrored in `src/core/style.ts` so every act reads the same tokens.

```markdown
# Style bible: <title>
Palette: bg #…  ink #…  accent #…  shadow #…   accent <= N% of any frame
Type: display <font, weight>, body <font>; sizes at 720p: title / word / caption; tracking; case; fonts checked for licence
Motion: tick = 2 frames (every duration is a multiple); in = <named cubic-bezier>, glitch = steps(); <= 1 overshoot; character art holds on 2s
Shot lengths: x% = 1 beat, y% = 2 beats, z% = 4 beats, at most one hold over 8 beats (the hero)
Camera: allowed moves <list>; max zoom per shot <n>x; shake only on hit frames, +-3 px for 4 frames
Motif: <prop>, four stages: close-up -> silhouette -> tinted -> shards, placed in acts <..>
Forbidden: <list>
Assets: cast cards, prop sheet, plates (file names)
```

Forbidden always includes: franchise characters, emblems or lettering; building the brand wordmark with a known logo's construction (pixel glyphs, stencil line, bevelled slab), so design the letterforms from scratch; any motif not in the bible (a theme leaking from earlier work counts); default gradients; stock lens flare or particles; unlicensed fonts.

## 4. Music-first shot list (gate 2)

1. Beat grid: `python $SKILL/scripts/beat_check.py grid music.wav --json out/beats.json` gives BPM, frames per beat, on-onset share and `beat_frames`.
2. Cut on `beat_frames` entries, never on `frames_per_beat * n` (fractional beats drift). The film starts at frame 0 and the first entry is the first cut point; after that a shot is the gap between two entries, so its length is a whole number of beats. Put the 1-frame black flash on the frame before the drop beat; the next shot starts on the drop.
3. On-onset below 60% (the script says "weak pulse"): the pulse is not steady, so do not force a grid. Trial-cut on phrase starts and heavy hits and run `beat_check.py check music.wav --frames <f1>,<f2>,...`; it flags cuts far from an accent and lists the strongest accents no cut uses. Lengths stay whole ticks, not whole beats.
4. Mark sections (intro, verse, build, drop, outro) with frame ranges at the top of the shot list; acts follow the sections. A starting skeleton for 30-40 s, to adapt rather than copy:
   - Act 1 hook: black, one hit, the motif's first close-up (2-4 beats).
   - Act 2 world: place and premise in two or three type slams.
   - Act 3 cast: one ID card per character, same card layout, different pose and number.
   - Act 4 brand: the wordmark slams in on a downbeat, with the partner line.
   - Act 5 systems: kinetic words and prop close-ups, cuts get shorter.
   - Act 6 build: the motif as a silhouette, then tinted; densest cutting so far.
   - Act 7 climax and end: 1-frame black, the motif in shards, the final lockup held.
5. Each cut carries one continuity element: screen direction, a shape, a colour or a sound hit. Consecutive shots of one figure use one shared placement constant (SKILL.md rule 4).
6. Write `docs/shot-list.md`, then mirror it into `src/core/timeline.ts` (`start` = frame / 30) so `beat_check.py check`, `film_scan.py` and `animatic.py` can read it. One shot per line, with `id`, `start`, `end` in that order (seconds; ids S01, S02 ...; the last `end` may be `DURATION_S`), plus the frame total: `{id: 'S01', start: 0.0, end: 0.5, act: 'act1', kind: 'flare'},` and `export const DURATION_FRAMES = <n>;`

```markdown
| Shot | Beats / frames | Picture | Text | Motion (code) | Asset card | Transition |
|---|---|---|---|---|---|---|
| S01 | 1 / 15 | black, red flare rises bottom-right | none | flare y-lift on 2s | prop-flare | hard cut on beat |
| S02 | 2 / 30 | hero ID card, flat | "KUROKI / 07" | card slams in 4 frames, 1 overshoot | cast-hero | match cut: card edge = next shot's slash |
```

7. Animatic: give every shot one still named after its shot id (`out/boards/S01.png`, `S02.jpg` ...; a flat board with its number and text drawn in code is enough) and run `python $SKILL/scripts/animatic.py --root . --images out/boards --music music.wav --beats out/beats.json -o out/animatic.mp4` (reads `timeline.ts`; or `--shots shots.csv` with id, image, seconds/frames; `--beats` snaps each cut to the nearest beat within 6 frames and prints every move; missing boards become numbered grey cards). It writes a rough cut with shot numbers burned in. Judge rhythm and length only. Re-cutting costs nothing; generate no assets before the user accepts the pacing.

## 5. Gates and workload

Each gate ends with an explicit approval. Do not start the next one without it.

| Gate | Deliverable | Command / how | Decides |
|---|---|---|---|
| 1 | style direction (section 2) | `docs/direction.md` | the look |
| 2 | beat map + shot list + animatic (section 4) | `beat_check.py`, `animatic.py` | rhythm, length, budget |
| 3 | 12 key static boards (opening, cast cards, brand lockup, motif stages, climax hit, end card) | `npx remotion still PV out/boards/B01.png --frame=N`, then `ffmpeg -y -i out/boards/B%02d.png -vf "scale=480:-1,tile=4x3" -frames:v 1 out/boards/sheet.png` | palette, type, art; AI stills are made and approved here |
| 4 | a 5 s sample of the densest passage, final quality, with music | `npx remotion render PV out/c_v.mp4 --frames=270-419 --muted`, then `ffmpeg -y -i out/c_v.mp4 -ss 9 -t 5 -i music.wav -map 0:v -map 1:a -c:v copy -c:a aac -shortest out/c.mp4` (-ss = first frame / 30) | motion grammar; build the other acts only after this, in parallel per act (`pipeline-recipes.md` section 9) |
| 5 | full 720p preview with music | `PV_AUDIO=music.wav node $SKILL/scripts/render-chunks.mjs 0-<last>`, then the same with `--join`; check `film_scan.py out/pv.mp4` and `beat_check.py check music.wav` | go to delivery (deliver mode, `PV_SCALE=1.5`) |

Estimate before gate 3 and show it with the animatic. Tag every shot A, B or C:

| Tier | Typical shot | Assets | Estimating rule |
|---|---|---|---|
| A | kinetic type, colour-block or wipe transition, flash | none, code only | one build pass plus one fix; 0 credits |
| B | a shot with a character or prop image | 1 still per pose, plus placement in the per-shot slot | credits = accepted stills x 2-3 attempts x 8; two critique rounds |
| C | climax, multi-layer effect, perspective type, WebGL, particles | code, plus art for any prop | 3+ refine rounds, built first, the main model owns it; render in chunks, concurrency 2 |

Image price and timing from the case study: 8 credits and 60-100 s per 2K image, 4-5 minutes for a chunked 1080p render of a 36 s film. Prices change, so confirm them with the user's account. Clips default to 0 (24 credits each, and 5 of 9 went unused). Example: 2 cast x 3 poses + 1 prop sheet + 3 plates = 10 accepted stills x 2.5 attempts x 8 = about 200 credits. Write the tier count and the credit total at the top of `shot-list.md`; the user approves the spend.

## 6. Anti-AI-look rules

Run this list on the boards (gate 3), the sample (gate 4) and the preview (gate 5). Each item is checkable. They fit a fast-cut PV: fast is allowed, mush is not.

1. **One focal point per shot.** Name it in three words; only it carries the accent colour or the highest contrast.
2. **Type outranks decoration.** No ornament larger than the word it dresses; at most 4 words on screen per shot.
3. **One rhythm unit.** Every tween length is a multiple of the bible's tick, and every hit (slam, stamp, cut) lands on a `beat_frames` entry; exceptions are listed in the bible.
4. **Palette budget.** At most 3 hues plus neutrals in the whole film; every colour sampled with `frame_measure.py colors` is in the bible.
5. **No default look.** `grep -rE "linear-gradient|box-shadow|blur\(" src` and justify every hit in the bible; no glow on everything, no glass, no drop shadows on flat shapes.
6. **Cut or snap, do not dissolve.** No crossfades unless the bible allows one; entrances take 2-6 frames; a hold is stillness, not a slow drift (no Ken Burns on every still).
7. **Scale steps.** Consecutive shots change subject size by at least 1.5x or switch angle; two similar framings in a row is a bug. At least 3 extreme close-ups or oversized type frames per film.
8. **Specific beats generic.** Invent concrete details (ID numbers, dates, coordinates, serials) and trace every prop and word to the brief. "Lorem", "YOUR TEXT", stock icons and unnamed placeholders are defects.
9. **Grid and asymmetry.** Type sits on a declared grid, deliberately off-centre; centred layouts only on the title card. AI stills carry no text, and are restyled in code (flat tones or gradient map into the palette) until no raw render gloss or soft glow shows.
10. **Density curve.** Count cuts per second per act: the lead-in is the sparsest, the climax act the densest, with one near-empty beat or the 1-frame black right before it. A film equally busy everywhere reads as generated.
