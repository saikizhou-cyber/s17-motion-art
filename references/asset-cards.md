# Asset cards and identity lock (realize mode)

In realize mode the user names the characters, props and scenes. This skill makes the motion in code (Remotion: camera, transitions, kinetic type, rhythm); AI only makes the still art. A **card** pins one character, prop or scene to a locked reference so every still generated for it stays the same thing across shots. Cards cover stills only. A generated clip is an optional small extra, and only from an approved still.

Anchors must be the user's own or original designs (SKILL.md: original content only); a frame of a reference video is never an anchor. "Recipes" below means `references/pipeline-recipes.md`; `$SKILL` is set there.

## 1. Identity card

One card per character, prop or scene. Keep them in `docs/asset-cards.yaml` and the images in `public/cards/<id>/`.

| Field | Content |
|---|---|
| `id` | short unique key; also the key of the Remotion slot (`characters.<id>`) |
| `anchor` | path of the locked reference image. Never overwritten; a better one is added as `anchor_v2` and the card switched deliberately |
| `palette` | 3-6 hex colours, taken from the anchor (below). Also feeds the code-side styling (gradient map, type colours) |
| `must_keep` | what must not change, as short phrases in the prompt language. Pasted verbatim into every generation prompt |
| `may_change` | what a shot may vary: pose, expression, lighting, camera angle, background |
| `refs` | canvas nodes passed as generation refs / `{{node:id}}` (anchor first, then the turnaround sheet) |
| `notes` | style line, forbidden additions, which shots adopted which stills |

```yaml
characters:
  wren:
    anchor: public/cards/wren/anchor.png
    palette: ["#1f2a44", "#e8d9b5", "#c2553a", "#8fb3a8", "#2b2b2f"]   # frame_measure.py colors on the anchor
    must_keep:            # written in the prompt language, pasted as-is
      - 银白色短波波头，左侧一缕细辫
      - 藏青色短夹克，锈红色围巾，奶油色长裤
      - 围巾上别一枚黄铜小罗盘；圆形琥珀色眼睛
      - 身形纤细，约七头身
    may_change: [pose, expression, lighting, camera angle, background]
    refs: [node_a1b2c3, node_d4e5f6]     # anchor, 3-column sheet
    notes: "flat-shaded anime look; no logos or text on clothing. S07, S12 adopted from wren_s07_b.png"
props:
  lantern:
    anchor: public/cards/lantern/anchor.png
    palette: ["#3b3a36", "#d9a441", "#f4e9c8"]
    must_keep: [六角形黄铜灯架, 磨砂玻璃灯罩, 顶部环形提手, 比例约 1:2.2 宽高]
    may_change: [angle, lit/unlit, background]
    refs: [node_g7h8i9]
scenes:
  harbor_dusk:
    anchor: public/cards/harbor_dusk/wide.png        # establishing view; camA.png and camB.png sit beside it
    palette: ["#27344d", "#d98c5f", "#f2cf9b", "#6a7f8f"]
    must_keep: [木栈桥从画面左下延伸到右中, 远处灯塔位于右三分线, 暖橙色低角度夕阳从左后方照来]
    may_change: [camera yaw, time within the dusk window, sea state]
    refs: [node_j0k1l2]
    notes: "empty of people; clear standing area at centre-left"
```

Rules:

- **Palette from the anchor:** crop to the part that carries the colour, so the backdrop does not dominate, and read the modal colours: `python $SKILL/scripts/frame_measure.py colors public/cards/wren/anchor.png --region x0,y0,x1,y1 --top 6`. Keep the 3-6 that matter.
- **Every generation cites the card:** the anchor goes in as a ref, and the card's `must_keep` lines are pasted into the prompt, plus one sentence on what `may_change` this time.
- **Check each result against the anchor before it is adopted:**
  1. Colour: run `frame_measure.py colors` on the same region of the anchor and the candidate and compare the hexes in `palette`. As a starting threshold, more than about 25 off in any channel on a `must_keep` colour is a fail; tune it per style.
  2. Outline and proportion: look at a side-by-side at equal height (`ffmpeg -i anchor.png -i cand.png -filter_complex "[0]scale=-2:768[a];[1]scale=-2:768[b];[a][b]hstack" -frames:v 1 side.png`; open it). For a number, run `frame_measure.py bbox <img> --color R,G,B` on one flat colour (hair, jacket) in both and compare the width-to-height ratio.
  3. Tick every `must_keep` line. Hands and fingers count.
- **Fail = re-roll the still, never the video.** A still costs 8 credits against 24 for a 4 s clip (recipes section 4, prices at the time). After three failed rolls, change the prompt or the refs (restate the failing `must_keep` line first, shrink `may_change`) instead of rolling again.
- **Near-frame carry:** the last frame of an adopted shot can be a secondary ref for the next shot, for continuity of pose and light (`ffmpeg -sseof -0.1 -i shot.mp4 -update 1 -frames:v 1 last.png`, or `npx remotion still PV last.png --frame=<n>`). The anchor stays the first ref. A carried frame that has drifted from the anchor is dropped; copies of copies drift.
- Canvas node ids are generation state: redact them before sharing (recipes section 7).

## 2. Prompt templates (Jimeng / 即梦, Chinese)

Upload the anchor (or pass its node as a ref, recipes section 4) with each prompt. Text in 【】 is a slot to fill. Generate with `jm.py ... --prompt @file` so the Chinese survives the shell.

### (a) Character three-column reference sheet

Purpose: a turnaround of one character on a continuous background, headless front, back, and a face close-up, used as a ref for later shots. The prompt below is the user's own text, kept word for word.

```text
请根据上传的参考图片，严格制作一张照片级真实感的三栏角色参考设定图。上传图片是角色身份的唯一判断依据，人物的身份、年龄、面部结构、发型、身体比例、肤色、服装设计、面料质感、颜色以及配饰，都必须严格以参考图为准，不允许重新设计，也不允许主观再诠释。
整体画面采用横向宽幅构图，从左到右依次排列为三个垂直区域。三个区域的高度必须完全一致，宽度也必须完全一致，每个区域正好占整张图宽度的三分之一。前两个区域为全身视图，第三个区域为脸部与上半身近景。三个区域必须共同组成一张连续、完整、无缝的画面，不能出现任何可见的分割线、边框、画框、留白间隔、面板缝隙、拼接感，背景也不能在三个区域之间发生变化。
第一栏为全身正面视图，但头部省略。角色需要以自然中立的姿势笔直站立，双臂自然垂放在身体两侧，正面面对镜头。服装要从颈部以下一直完整展示到鞋子。制作时，必须先按照与第二栏完全相同的全身比例和取景建立人物，再仅去除颈部以上的头部区域，让头部原本所在的位置保留自然的空白。不能出现任何砍头效果、伤口效果、断颈效果、超现实表现或解剖损伤感，而应呈现一种干净、专业的角色设计展示状态，让人一看就明白这是有意省略头部信息的服装参考展示。不能因为头部被省略，就放大身体、拉近镜头、重新构图、调整位置或重新裁切身体。
第二栏为全身背面视图。需要展示完全相同的角色，从正后方进行拍摄，保持同样的中立站姿和双臂自然下垂的状态。必须清楚呈现角色背面的整体轮廓、后脑勺与后方发型、服装背面的结构与缝线、下装的背面形态，以及鞋子的后部样貌，所有细节都要与参考图保持一致。
第一栏和第二栏的全身图必须严格锁定比例，呈现出像同一台固定在三脚架上的相机连续拍摄的效果。两张图必须拥有完全相同的焦距、机位高度、拍摄距离、人物尺寸和光照条件。画面中的肩宽、躯干长度、腿部长度、鞋子大小、肩膀到地面的距离以及左右留边都必须一致。两个人物必须站在同一条水平地面基准线上，肩线也必须处于同一水平位置，并且在各自区域中占据相同的画面高度比例。不能出现放大、缩小、裁切变化、上下偏移或任何身体尺寸差异。整体应带有接近正交视图的技术参考感，透视变形要尽量轻微。
```

补充（可选）：以下不是用户原文，而是为第三栏补写的要求，接在上面的提示词之后使用。

```text
第三栏为脸部与上半身近景。取景从头顶上方留少量空间开始，到胸口与腰线之间结束，人物居中，正面或轻微侧脸（偏转不超过十五度）面对镜头，视线平视，表情自然中性，嘴巴自然闭合。第三栏必须与前两栏采用相同的光照方向、色温和明暗关系，背景与前两栏连续一致，不能因为是近景就改变光线或背景。面部结构、五官比例、肤色、发型与发色、刘海与发丝走向、耳饰等配饰，以及领口和上半身服装的结构、颜色、面料质感，都必须严格以参考图为准，不允许美化、磨皮、改变年龄感或重新设计，也不要添加参考图中没有的妆容、饰品或表情。第三栏中头部与上半身的比例必须与前两栏全身图中的同一角色吻合，整张图仍然是无缝的连续画面，不出现分割线或边框。
```

风格化角色（二次元/赛璐璐）：把提示词中的"照片级真实感"替换为目标画风描述，例如"二次元赛璐璐平涂风格，清晰线稿，硬边分层阴影"。

### (b) Prop card

Purpose: a locked multi-view of one prop (front, side, back or top, plus one detail close-up) on a plain background, so any shot can quote the same object. Same wording discipline as (a). If the prop carries lettering, leave the text blank here and add it in code.

```text
请根据上传的参考图片，严格制作一张【照片级真实感 / 目标画风描述】的道具参考设定图。上传图片是该道具的唯一判断依据，道具的形状、比例、结构、材质、表面质感、磨损程度、颜色、图案与配件，都必须严格以参考图为准，不允许重新设计，也不允许主观再诠释。
整体画面采用横向宽幅构图，从左到右依次排列为四个区域。四个区域的高度和宽度必须完全一致，每个区域正好占整张图宽度的四分之一，并共同组成一张连续、完整、无缝的画面，不能出现任何分割线、边框、留白间隔或拼接感。背景为同一种纯色【与道具反差明显的中性灰或纯色】，没有渐变、地面纹理和环境物件，道具下方只允许有轻微的接触阴影。
第一栏为正视图，第二栏为【左侧 / 右侧】侧视图，第三栏为【背视图 / 顶视图，二选一】。这三个视图必须像同一台固定在三脚架上的相机连续拍摄：焦距、机位高度、拍摄距离、道具尺寸和光照条件完全相同，道具在三个视图中的长、宽、高必须互相吻合，并位于同一条水平基准线上，整体带有接近正交视图的技术参考感，透视变形尽量轻微。
第四栏为【细节部位】的特写，放大呈现该部位的材质纹理、接缝、磨损和结构细节，光照方向与前三栏一致，颜色与材质与前三栏中的同一部位完全一致。
画面中不得出现任何文字、数字、标识、水印或签名，不得出现手、人物或其他道具。
```

### (c) Scene card

Purpose: an empty, locked scene (establishing view plus two camera angles) with one light and colour spec, to use as the background plate with characters composited on top. Cut the three panels apart after generation and store them as `wide.png`, `camA.png`, `camB.png`.

```text
请根据上传的参考图片，严格制作一张【照片级真实感 / 目标画风描述】的空场景参考设定图。上传图片是该场景的唯一判断依据，场景的空间布局、建筑与陈设的形状和位置、材质、颜色、光照氛围、时间与天气，都必须严格以参考图为准，不允许重新设计，也不允许主观再诠释。
画面中不得出现任何人物、动物、角色、剪影、人影或倒影中的人，也不得出现文字、标识、水印。地面必须清晰完整，并保留一块没有大型遮挡物的可站立区域【位置，例如：画面中央偏左的地面】，以便后续合成角色。
整体画面采用横向宽幅构图，从左到右依次排列为三幅等宽等高的画面，画面之间留一条极窄的纯色间隔（约占整张图宽度的百分之一，颜色与场景明显区分），以便之后裁开。第一幅为建立镜头，使用广角，完整交代空间布局与主要陈设；第二幅为机位A，【描述，例如：从入口看向窗边】；第三幅为机位B，【描述，例如：从窗边回看入口】。
三幅画面必须来自同一场景中的同一相机高度【人眼高度 / 低机位】和同一焦距体系，相机只允许水平转向或前后移动，不允许改变高度或俯仰角度。因此地平线在三幅画面中必须位于相同的高度（画面高度的【二分之一】处），垂直线保持垂直，同一物体在不同机位中的形状、颜色和相对位置必须自洽。
光照与配色：光源为【方向与类型，例如：左后方的低角度夕阳】，色温【偏暖 / 偏冷】，阴影【柔和 / 清晰】。三幅画面的光照方向、色温和明暗关系必须完全一致。主色调【#hex】，辅色【#hex】，点缀色【#hex】，不得偏离。
```

## 3. From card to shot

1. **Prompt:** pass the anchor node of every card the shot uses (character, prop, scene) as refs and quote them with `{{node:id}}`; paste each card's `must_keep`; add the shot intent and the line "单一角色，无文字，无水印". For pose, draw a grey stick figure with PIL, upload it and write "严格按照示意图的姿势" (recipes section 4). For a cutout, ask for a flat grey or blue backdrop.
2. **Two routes.** *Cutout (default):* the character or prop on a flat backdrop, then `cutout.py` + `cleanedge.py` (or `bluekey.py` for a flat-blue 16:9 frame; recipes section 5), composited over the scene plate in Remotion, so camera moves, parallax, shadows, grading and every transition are code. *Frame:* character and scene drawn whole in one picture, only when their light interplay matters; identity drifts more, so run the section 1 checks harder.
3. **Gate:** compare against the anchor (section 1) before the still goes into the project. Composite the cutout on the plate and check edges at 100% (halo, 1-px lines).
4. **Slot:** record the adopted still in the project's per-shot slot: `characters.<id>.shots[]` with `shot, src, mode, focus` (recipes section 3). Props and scene plates mirror the same fields under their own keys in the zod config (`src, focus, flip, overlays`); do not invent a second convention. Consecutive shots of one figure share a single placement constant (SKILL.md rule 4).
5. **Motion stays in code:** animate the slot's layers in Remotion. Ask for a clip only for a pose the user has accepted as a still, and key it with `bluekey.py` (recipes sections 4 and 5).
