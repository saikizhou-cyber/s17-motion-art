# Case study: GamePV (36 s, 57 shots, 8 acts)

A 36-second game collaboration PV was rebuilt 1:1 in structure, motion and layout as a Remotion project whose characters, names and copy are original (hero: Rei Kuroki, number 7), and delivered as a 1080p film. One person directed; Claude Code (Opus 5.5 main loop, Sonnet 5.5 and Opus 5.5 sub-agents) built it; Jimeng (即梦) generated the character art, props and short clips.

Numbers are measured: time and tokens with `scripts/transcript_stats.py` over the Claude Code transcripts (cut-off: the packaging request), credits from the generation state files. **Credits are derived (successful items × price), not an account ledger; tokens are not converted to money.**

## Result

| | |
|---|---|
| Film | 1920×1080, 30 fps, 1079 frames, 35.97 s, H.264 + AAC |
| Project | `src/` 198 files / ~33.6 k lines (8 acts 165 files / 27.9 k lines); `public/` ~250 MB (99 character files incl. 9 clips, 21 props, 17 fonts) |
| Template | every shot reads a per-character slot; a new character = new images + focus values in one config file |

## Time

| | |
|---|---|
| Wall clock | 66 h 43 min (start → last film delivered) |
| Active | 18 h 47 min (gaps < 30 min between transcript records; includes time agents worked alone) |
| Sub-agent time | 50 h 39 min (parallel, summed) |
| User messages | 113, of which 44 carried screenshots (55 images) |
| Usage-limit interruptions | 5 |
| Render | 720p full film ~1.5 min; 1080p chunked ~4–5 min |
| Generation | image 60–100 s, 4 s clip ~110 s |

### Phases

| Phase | Active time | What happened |
|---|---|---|
| Breakdown, stack choice, scaffold, first parallel build | 1 h 28 min | ~65 cuts → 57 shots / 8 acts; 9 agents compared stacks; Remotion chosen. The first 14-agent build hit the usage limit and returned nothing usable |
| Recovery, second build, review/fix | 2 h 36 min | acts completed; 17 critic + 8 fix agents; all 57 shots in place |
| First full film | 6 min | original-character 720p version |
| Rejected direction | 41 min | the user asked for a franchise character; refused, rolled back, everything original |
| Jimeng setup, hero design, per-shot slots, removing an invented motif | 5 h 03 min | 5 hero iterations; per-shot slots; a clock motif that the reference does not have was removed everywhere |
| Five feedback rounds, optical-flow slow motion, 1080p | 5 h 14 min | ~60 notes from screenshots |
| Retrospective, publishing copy | 41 min | |
| Final alignment | 24 min | climax hero unified across 3 shots; one-frame bullet trace redrawn to the reference's footprint |
| (short gaps between phases) | 2 h 34 min | rows are rounded; they sum to the 18 h 47 min total |

## Cost

### Tokens

| Scope | Model | Turns | Output tokens | Cache read |
|---|---|---|---|---|
| Main loop | Opus 5.5 | 778 | 772,478 | 391 M |
| Main loop | Sonnet 5.5 | 324 | 359,285 | 172 M |
| Sub-agents | Opus 5.5 | 8,778 | 10,302,532 | 1,686 M |
| Sub-agents | Sonnet 5.5 | 1,587 | 1,982,888 | 315 M |
| **Total** | | **11,467** | **13,417,183** | **2,564 M** |

Opus produced 82.5% of all output tokens. Sub-agents inherited the main model until the user asked a second time for Sonnet; from then on every new sub-agent ran on Sonnet. Lesson: set `model` on every agent call from the start.

### Generation credits (Jimeng)

| Item | Count | Credits |
|---|---|---|
| Images (seedream 5.0 pro, 2K, 8 each) | 121 | 968 |
| Clips (seedance 2.0 mini, 720p, 4 s, 24 each) | 9 | 216 |
| **Total** | 130 | **1,184** |

Not used in the film: 5 of 9 clips (120 credits) and a 9-image cast batch replaced by a redesign (72 credits), so at least 192 credits (16%); most batches also had 2–4 alternates of which one was used. Not countable from files: 4 images made in the web UI.

## Structure

| Act | Time (s) | Shots | Content |
|---|---|---|---|
| 1 | 0–3.97 | S01–S08 | digital clock, moon, tower, summoning, tumbling cards |
| 2 | 3.97–6.83 | S09–S14 | six name cards, each with its own number |
| 3 | 6.83–12.23 | S15–S19 | logo slam, ring illustrations, partner lockup |
| 4 | 12.23–17.8 | S20–S28 | grey hall, kinetic words, clay-white 3D props, gallery |
| 5 | 17.8–20.5 | S29–S34 | card rush, poster, desk and stamped passbook |
| 6 | 20.5–25.43 | S35–S38 | visual-novel dialogue, weekday badges, night |
| 7 | 25.43–30.27 | S39–S48 | DRAW 1/2/3 step cards, wedge type, word wall |
| 8 | 30.27–35.97 | S49–S57 | eye close-up, pistol, bullet trace, ink slash, shard finale |

## What worked

1. Measuring the reference (frames, colours, homographies, blob edges) instead of judging by eye.
2. One folder and one zod schema per act; parallel agents with disjoint file ownership; `tsc` as the gate.
3. Per-shot character slots: a still or a 16:9 frame per shot, optional clip, key colour, hair matte and skin flattening, all optional.
4. AI for what code draws badly (props, cards, poses), then stylised in code into the shot's palette.
5. Critics that only build ref|ours sheets and list defects; the main model accepts or rejects.
6. Chunked rendering with silent segments: any chunk can be redone, and the music can be swapped by re-joining.

## Pitfalls (and what fixed them)

- **Empty first build**: a 14-agent workflow hit the usage limit and returned nothing. → batches that persist to disk; resume.
- **"Similar" is not 1:1**: early shots were rejected again and again. → measure; side-by-side at full resolution.
- **A franchise character was requested**: refused generating, cutting out or imitating it; the template stayed original.
- **An invented motif**: clocks came from the builder's own earlier theme, not from the reference. → check every motif against the reference.
- **Feedback arrives mid-turn**: ~60 notes landed while agents were working; some agents acted on stale requests. → strict per-agent scope.
- **AI clips**: wrong poses, cropped figures. → approve a zoomed-out still first; a self-drawn grey pose guide for exact poses; 5 of 9 clips were wasted before this rule.
- **Slow motion**: 0.35x playback stutters. → `ffmpeg minterpolate` optical flow, then play at 1x.
- **Filters**: a skin-flattening filter using `merge` let the backdrop show through soft edges (→ arithmetic composite); a keyed clip scaled up showed a 1-px dark line (→ clip the border).
- **Renders**: the full render froze near frame 725; one 1080p chunk died with `write EOF`. → chunks, concurrency 2.
- **The figure jumped between shots**: the same hero had separate placement numbers in three consecutive shots plus the flash frames between them; four rounds of "same size, same place" followed. → one shared constant for the whole sequence.
- **A one-frame effect drawn from memory** did not match. → measured from the reference frame (blob bboxes and edges) and rebuilt as polygons (IoU 0.83). For anything distinctive, stop at the footprint and draw your own shape: tracing someone else's artwork is copying, not rebuilding.
- **The brand lockup borrowed the reference logo's construction** (pixel glyphs, stencil line, bevelled slab) while only the words were changed; a review before release flagged it as a trade-dress risk and it was kept out of the public demo. → match a logo's position, size and timing, never its letterforms.
- **A screenshot lied about colour**: the user's screenshot showed a grey background; the decoded frame was pure black. → sample the real frame.
- **Retrospective miscount**: messages with screenshots are stored as block lists in queued-message records; a first count missed 36 of 113. → `transcript_stats.py`.
- **Music**: the reference's track was used for timing during the build; it must be replaced before publishing. Silent segments made that a 5-second remux.
