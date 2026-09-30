# Generation-area / context-control UX (OQ6)

**Question (OQ6):** One of IntraPaint's biggest strengths is fine-grained context control — managing
exactly what parts of the image the diffusion backend sees, and at what scale. The controls for
managing this are still clunky. Review the workflow docs and propose an improved interface.

**Substrate:** builds on `_codebase_map.md` (§4 selection layer, §5 generators) and
`_decisions_ledger.md`. Cross-refs A6 (rendering — single-source-of-truth compositing), A2
(transform tool — the on-canvas gizmo machinery this report reuses), OQ4 (selection layer),
and the workflow docs `doc/inpainting_guide.md`, `doc/tool_guide.md`, `doc/controls.md`,
`doc/menu_options.md`. Verified against source; `[inferred]` marks anything reasoned but not
line-confirmed.

---

## 0. Revision after a workflow interview with the maintainer (2026-09-30)

The sections below were written from the docs alone. Talking through how the maintainer actually works
changed the priorities. An interactive mockup of the resulting options is in
`mockups/generation_area/index.html`; open it in a browser.

**How the tool is really used**
- Inpaint Full Resolution is nearly always on. The generation area acts as the outer limit and aspect
  template, and **padding is the working zoom control**. The full-res crop grows to the area's aspect
  ratio (`selection_layer.py:321-345`), so padding is aspect-safe; resizing the area directly is not.
- The 1px selection-brush trick is used constantly: for asymmetric padding, and because one right-click
  on something the model should see is faster than a slider. Padding clipped at the area edge is not a
  problem.
- Typical 1024×768 routine: full image with resolution matched, then a 768² area with resolution
  matched for detail work, switching back now and then. Resolution rises above the area size only for
  areas smaller than the model handles well. Resolution changes every few minutes.
- The area gets moved mostly by left-clicking in the small Navigation *tab*, almost never resized there.
  Click-to-center is probably a little better than today's top-left placement. The G tool is opened
  mostly to reach its panel.
- **Biggest pain point: changing resolution/aspect** (full image ↔ square) takes too many clicks for a
  predictable step.
- Following the selection automatically would be right ~99% of the time. The hard case is a selection
  bigger than the area: sometimes it should grow, sometimes not, and no simple rule tells them apart.

**Effect on the proposals below**
- **Drop P2 (scale badge) and P6 (model's-eye preview).** The canvas and navigation outlines already
  show exactly what the model sees, and numbers don't help.
- **P3 becomes "frames + a resolution rule":** one-click area sizes (full image, largest square,
  recently used), a key to flip to the previous frame, and a rule ("match area, at least 512") that
  replaces the two match buttons.
- **P5 becomes "context pins":** make the 1px trick official as right-click pins / right-drag boxes
  that extend the crop without being inpainted, optionally cleared after each generate, plus a
  modifier+scroll padding shortcut that works over the canvas and navigation panel.
- **New: follow-selection**, with the overflow case left to the user (inline prompt, keep and outline
  the overflow, or grow with undo). Growth keeps the area's aspect ratio.
- **New: context bar**, which puts full-res, padding, frames and follow in one place for every tool, so
  changing them doesn't mean switching to G.
- **P4 (handles) is lower priority.** Canvas behavior may change freely, but left-click must keep
  moving the area in the navigation panel.
- Not yet designed: moving the area to a layer's bounds (useful but rare).

---

## 1. What "context control" actually is today

The set of controls that jointly decide **what pixels the backend receives and at what scale**:

| Concept | Config key | Meaning | Where it's set |
|---|---|---|---|
| **Generation area** | (image-space `QRect`, not a config key) | The rectangle of the image the backend operates on. | Generation-Area tool (`generation_area_tool.py`), tool panel X/Y/W/H, arrow keys, "Select full image", crop-to-area menu. |
| **Generation resolution** | `Cache.GENERATION_SIZE` ("Generation size:") | The pixel resolution actually sent to the model; output is *scaled* to the area if they differ. | Gen-Area tool panel **and** the SD generation panel (`stable_diffusion_panel.py:99`). |
| **Editing size** | `Cache.EDIT_SIZE` ("Editing size:") | A near-duplicate of the generation-area *size*, auto-synced both ways. | Implicit — no direct control; mirrors the area. |
| **Selection (mask)** | `SelectionLayer` | Which pixels *within* the area get changed (inpaint only). | Selection tools. |
| **Inpaint Full Resolution** | `Cache.INPAINT_FULL_RES` | Silently re-crop to the selection bounding box + padding for higher detail. | SD panel (`stable_diffusion_panel.py:124`) and selection-tool panels (per `inpainting_guide.md`). |
| **Full-res padding** | `Cache.INPAINT_FULL_RES_PADDING` | Pixels of context kept around the selection when full-res is on. | SD panel (`:127`); also nudged by a 1px selection-brush dot trick. |
| **Denoising strength** | `Cache.DENOISING_STRENGTH` | How much image context vs prompt dominates. | SD panel. |
| **Follow / zoom-to area** | view state | Whether the viewport tracks the area. | "Z" key, zoom toggle, `image_viewer.follow_generation_area`. |

The relationship between area and resolution is the crux: `image_stack.generation_area` setter
auto-writes `EDIT_SIZE` (`image_stack.py:352-353`), and `EDIT_SIZE` changes push back into the area
(`image_stack.py:119-123`) — but `GENERATION_SIZE` (the resolution actually sent) is **fully
decoupled**. The doc devotes an entire section to reconciling them by hand
(`inpainting_guide.md` §"Selecting generation resolution", §"Generation Area control"). That manual
reconciliation is the clunkiness.

---

## 2. Diagnosis — where the friction is

### F1. Two independent rectangles, reconciled by hand, with invisible consequences *(root cause)*
The generation **area** (image-space rect) and generation **resolution** (`GENERATION_SIZE`) are
independent values whose *ratio* is a scale factor applied to the output — the single most
consequential quantity in this workflow (the guide's downscaling-for-detail technique is entirely
about deliberately setting resolution > area). Yet:
- The scale factor is **never displayed**. The user computes "280→640 = 2.3× upscale" in their head.
- Keeping them related is two **manual buttons** — "Gen. area size to resolution" and "Resolution to
  gen. area size" (`generation_area_tool_panel.py:74-99`) — that must be re-pressed after every area
  change. Nothing maintains the relationship live.
- Aspect mismatch silently **non-uniformly distorts** output; the guide warns of it, the UI neither
  flags nor prevents it.

### F2. Three overlapping size concepts with inconsistent names
"Generation area size", "Generation size / resolution" (`GENERATION_SIZE`), and "Editing size"
(`EDIT_SIZE`) coexist. `EDIT_SIZE` is effectively a shadow of the area size (auto-synced both
directions) yet `MIN_/MAX_EDIT_SIZE` are what actually clamp the area
(`generation_area_tool_panel.py:236-239`). The labels disagree across surfaces: the tool panel says
"Image generation area" + "Image generation resolution", the config calls the same things "Editing
size" + "Generation size". A newcomer cannot tell "editing size", "generation size", and "generation
area" apart — and two of them are the same thing.

### F3. Controls for one logical operation are scattered across ≥3 surfaces
To set up a single generation context the user touches:
- the **Gen-Area tool panel** (geometry + resolution + match buttons),
- the **SD generation panel** (resolution *again*, inpaint-full-res, padding, denoising),
- the **selection-tool panels** (inpaint-full-res *again*, per the guide).

Resolution and inpaint-full-res each appear in two places; visibility is further gated by hidden
mode state (`_edit_mode_control_update`, `stable_diffusion_panel.py:155-164` shows/hides full-res +
padding based on `EDIT_MODE`). Discovery is poor and the same value edited in two spots invites
confusion about which is authoritative.

### F4. Inpaint Full Resolution is a hidden second crop with weak canvas feedback
Full-res silently re-crops to the selection bounding box + padding. Its only visualization is an
inner "padding rectangle" outline that today is described mainly for the **navigation window**
(`menu_options.md:221`, `controls.md:19`) — the main-canvas story is thin. Padding is partly adjusted
by a genuinely hidden trick: "right-click with the selection brush to add a single pixel outside the
selection" (`inpainting_guide.md` §"Generation Area control"). The user never sees the actual
post-crop, post-scale pixels the model will receive.

### F5. The on-canvas gizmo is non-standard and lossy
`GenerationAreaTool` uses **left-click = teleport top-left to cursor**, **right-click = resize
anchored to top-left only** (`generation_area_tool.py:56-75`). There are no handles; you can't drag a
corner or resize from any edge but bottom-right; fixed-aspect requires holding a modifier and borrows
`GENERATION_SIZE`'s ratio (`:66-71`). Every mainstream editor's marquee/crop tool has 8 handles and
drag-move-by-interior; this deviates from that norm (an OQ2 idiosyncrasy) and makes precise framing
awkward.

### F6. No "model's-eye view"
The highest-value affordance for this workflow — a WYSIWYG preview of the exact tensor the backend
gets (effective crop → scaled to resolution → masked-fill applied) — does not exist. Users iterate
blind and discover framing/scale mistakes only in the 8-image result grid. The pieces exist
(`ImageStack.qimage_generation_area_content()` `image_stack.py:538`; `SDGenerator.get_gen_area_image`
/ `get_gen_area_mask` `sd_generator.py:316-326`) but the full-res crop + scale + fill is applied
downstream in the backend request builders, so there is no single function that yields "the final
input image."

---

## 3. Proposed interface

Design principle (mirrors A6's single-source-of-truth stance): **make the invisible relationship
between area, resolution, selection, and scale visible and directly manipulable, in one place, with
one authoritative preview.** Ordered from lowest-risk/highest-leverage to structural.

### P1. Collapse the vocabulary; kill `EDIT_SIZE` as a distinct concept
Standardize on exactly two nouns everywhere (UI, config labels, docs):
- **Generation area** — the image-space rectangle (position + size).
- **Generation resolution** — the output pixel size (`GENERATION_SIZE`).

`EDIT_SIZE` is already a bidirectional shadow of the area size — demote it to an internal detail (or
remove it, folding `MIN_/MAX_EDIT_SIZE` clamps into the area directly). Rename the "Editing size:"
label and audit `generation_area_tool_panel.py` / `stable_diffusion_panel.py` / `doc/*` so a user
meets only two names. *Low risk, pure clarity win; unblocks everything below by giving the redesign a
stable vocabulary.*

### P2. A live **scale badge** wherever area & resolution are shown
Show the derived relationship as first-class text + color:

> `Area 280×280  →  Resolution 640×640   ·   2.3× upscale`

Color-cue the badge (neutral / caution) when the scale or the target resolution is outside the
sane band for the active model family (SD1.5 ≈512, SDXL ≈1024 — the guide already encodes these).
Flag aspect-ratio mismatch explicitly ("non-uniform scale — output will distort"). This alone
addresses F1's invisibility with no model changes.

### P3. Replace the two "match" buttons with a **link toggle + resolution presets**
Instead of manual "area→res" / "res→area" buttons that decay after each edit, offer:
- an **aspect/size link toggle** — when on, editing the area updates the resolution proportionally
  (snapped to the model's native band) and vice-versa, so the relationship is *maintained*, not
  re-established; and
- a small row of **model-aware resolution presets** (512², 640², 768², 1024²) so "generate this area
  at my model's native resolution" is one click.

Keep the explicit buttons available for power users, but the default path stops requiring them.

### P4. First-class on-canvas gizmo with handles — **reuse A2's outline machinery**
Replace the left=teleport / right=resize scheme (F5) with a proper bounding-box gizmo: 8 resize
handles, drag-the-interior to move, corner-drag with an **aspect-lock** that can bind to the
resolution aspect, arrow-key nudge retained. A2's transform-tool redesign is already rebuilding
exactly this (a `TransformOutline`-style views-emit-intents gizmo over an authoritative state); the
generation area should render through the **same** handle/outline component rather than growing a
parallel one. Keep the current mouse scheme as a fallback for one release to avoid muscle-memory
breakage. *(Depends on A2 landing its reusable outline; until then this is the one structural item
with an upstream dependency.)*

### P5. Make Inpaint Full Resolution visible and directly editable
- Always draw the **effective inpaint crop** (selection bbox + padding, clamped to the area) on the
  **main canvas** whenever full-res is on — promote the navigation-window-only outline
  (`controls.md:19`) to a first-class canvas overlay.
- Let padding be **dragged directly** on that inner rectangle's edges, retiring the 1px-dot trick
  (keep the trick working, but it's no longer the only way).
- Surface the **effective resolution** of the full-res crop in the scale badge (P2), since full-res
  changes what actually gets sent.

### P6. **Model's-eye-view preview** (the flagship feature)
A small docked/toggleable preview that renders **exactly** what the backend will receive: effective
crop (area, or full-res selection+padding) → scaled to generation resolution → masked-fill applied
(`Cache.MASKED_CONTENT`). Prerequisite and biggest payoff: **factor the crop+scale+fill into one
function** shared by the preview and the real request builders, so preview and actual can never
diverge (the A6 single-source-of-truth principle applied to generation input). This turns blind
iteration into WYSIWYG and is the direct answer to "the controls are clunky" — you see the result of
every context control instantly.

### Consolidation: one "Context" surface
P2/P3/P5/P6 want to live together. Co-locate area geometry, resolution + scale badge, link/presets,
inpaint-full-res + padding, denoising, and the model's-eye preview into **one** context panel (the
Gen-Area tool panel is the natural host), and have the SD generation panel *reference* rather than
*duplicate* those controls (shared widgets from the `Cache.get_control_widget` factory already make
this cheap — `stable_diffusion_panel.py:82`, `generation_area_tool_panel.py:87`). This resolves F3's
scatter.

---

## 4. Implementation sketches

Respecting conventions: config options are **data** (edit `resources/config/cache_value_definitions.json`,
not code — CLAUDE.md); every new string wrapped in the file's `_tr()`; singletons via `Cache()` /
`AppConfig()`.

**P1 — vocabulary / `EDIT_SIZE`:**
- Edit the `edit_size` label/description in `cache_value_definitions.json`; grep `EDIT_SIZE` usages
  (`image_stack.py:119-123, 352-353`, tool panel clamps `:236-239`) and decide: demote to internal or
  remove. If removed, move the min/max clamp to `_get_closest_valid_generation_area`
  (`image_stack.py:1534`). Update `doc/inpainting_guide.md`, `tool_guide.md`, `controls.md` labels.
- Low blast radius; do it first so later UI text is stable.

**P2 — scale badge:** a `QLabel` (or tiny custom widget) in `GenerationAreaToolPanel`, recomputed on
`image_stack.generation_area_bounds_changed` and `Cache.connect(..., Cache.GENERATION_SIZE, ...)`.
Model-band thresholds can start as constants keyed off the selected model name string (the guide's
512/640/768/1024 numbers); no backend call needed. Pure additive UI.

**P3 — link toggle + presets:** a checkbox + preset buttons in the panel. The link handler reuses the
existing `_area_to_res` / `_res_to_area` bodies (`generation_area_tool_panel.py:79-99`) but fires on
`valueChanged` instead of button clicks, guarded against signal loops (the panel already guards with
`if value != ctrl.value()` at `:261`). Presets just call `Cache().set(Cache.GENERATION_SIZE, QSize(n,n))`.

**P4 — gizmo:** blocked on A2 exposing a reusable handled-outline item. When available, swap
`GenerationAreaTool`'s `mouse_click`/`mouse_move` (`generation_area_tool.py:77-100`) to drive the
gizmo's intents (move / resize-from-handle / aspect-lock) and delete the top-left-anchored
`_resize_generation_area`. Until A2 lands, ship P1/P2/P3 and leave the mouse scheme as-is.

**P5 — inpaint crop overlay:** there is already a `_generation_area_selection_outline` and a
padding/inpaint outline in the viewer (`image_viewer.py:112`; navigation window per
`menu_options.md:221`). Promote/ensure it renders on the main canvas whenever
`Cache.INPAINT_FULL_RES` is on and a selection exists; add edge-drag handling for
`INPAINT_FULL_RES_PADDING`. Reuse `SelectionLayer.get_selection_gen_area()` for the bbox.

**P6 — preview + shared crop function:** extract a pure helper, e.g.
`ImageStack.generation_input(mask, full_res, padding, resolution, fill_mode) -> (QImage, QImage)`,
that produces the final (image, mask) pair; have `SDGenerator.get_gen_area_image` /
`get_gen_area_mask` (`sd_generator.py:316-326`) **and** the new preview widget call it. The preview is
a `QLabel`/graphics item refreshed on the relevant `Cache`/selection/area signals. This is the
largest item and the one that most changes the feel of the workflow.

**Suggested order:** P1 → P2 → P3 (quick, independent, immediately reduce friction) → P5 → P6
(structural, shared-code) → P4 (gated on A2). P6's shared-crop refactor should be verified against a
golden-image test (A1's `assert_image_matches_golden`) since it moves the real generation-input path.

---

## 5. Scope, dependencies, non-goals

- **Depends on:** A2 (for P4's reusable gizmo only — P1/P2/P3/P5/P6 are independent). Benefits from
  A1's golden helper for P6.
- **Feeds:** OQ2 (the left=move/right=resize scheme and the three-names confusion are concrete
  editor-norm idiosyncrasies OQ2 should cite from here).
- **Model API unchanged** except P1's optional `EDIT_SIZE` removal and P6's additive
  `generation_input` helper. No change to backends, undo, or the generator selection flow.
- **Non-goals:** ControlNet UX, prompt/preset management, the result-selection grid, and the
  denoising/sampler controls themselves (only denoising's *placement* moves under the consolidation).

---

## 6. One-line summary for the ledger

Context control is clunky because area and resolution are two independent rectangles reconciled by
hand with invisible scale consequences, three overlapping size names (`EDIT_SIZE` is a redundant
shadow), controls scattered across tool/SD/selection panels, a non-standard handle-less gizmo, and no
preview of what the model actually receives. Fix: collapse to two names, add a live scale badge +
link/presets, consolidate into one context surface, promote the inpaint-crop overlay to the canvas
with draggable padding, reuse A2's handled gizmo, and — the flagship — a WYSIWYG "model's-eye" preview
driven by a single shared crop+scale+fill function so preview and actual can't diverge.
