# IntraPaint — rendering pipeline & compositing (A6)

Deep-dive handed off from `architecture_review.md` §5. Reads on top of `_codebase_map.md` and
`_decisions_ledger.md`. Substrate for **OQ4** (selection-layer perf) and **A2** (transform tool).
Evidence cited as `file:line`.

**Correction up front:** the architecture review §5 speculated about "per-layer graphics-item
lifecycle" and possible divergence between on-screen and exported compositing. Reading the code
shows that's **not** how it works — there is a single authoritative compositor and the view
displays its output. The real issue is **performance, not architectural correctness**. Details
below; §8 records the correction.

---

## 1. Summary verdict

The rendering architecture is **better than expected and structurally sound**: one authoritative
compositor in the model (`LayerGroup.render`), and the `QGraphicsView` displays its cached output
as a single pixmap while owning only what it's good at — viewport, zoom/pan, coordinate mapping,
and overlays (outlines, selection, handles). **Keep `QGraphicsView`.** The genuine problem is that
**every content change recomposites the entire image** (the group image cache is all-or-nothing and
the per-edit dirty rectangle is discarded), which is the source of the large-image lag and the
substrate for OQ4. The reported partial-alpha "GraphicsView glitch" is almost certainly **not** a
QGraphicsView problem — it's in the model compositor / cache-invalidation / premultiplied-alpha
path, and needs a repro to pin (§4 R2).

## 2. How rendering actually works

Two distinct paths, and they **do not diverge** — the first is built from the second:

- **Authoritative compositor (model):** `LayerGroup.render` (layer_group.py:204) composites child
  layers into a `QImage` using `QPainter` with each layer's `qt_composite_mode()`, and for the
  blend modes Qt lacks, a `custom_composite_op()` (layer_group.py:293) — plus correct **isolate**
  handling (layer_group.py:257-278). `LayerGroup.get_qimage` caches the result in a `CachedData`
  (`_image_cache`, layer_group.py:194-201). This is also what filters (`filter.py`) and save/export
  use.
- **On-screen (view):** the scene contains **exactly two `LayerGraphicsItem`s** — the selection
  layer and the **root layer group** (image_viewer.py:103-104). There is **no `layer_added`
  wiring** and **no per-layer scene item**. The root group's item shows `layer.pixmap`, i.e.
  `QPixmap.fromImage(LayerGroup.get_qimage())` — the model composite. So *what you see is what the
  model renders*; the view is not doing its own layer compositing.

`QGraphicsView`/`PixmapItem` therefore handle: the composited pixmap, the selection overlay
(drawn at `setOpacity(0)` as an item, layer_graphics_item.py:38, with its outline drawn
separately), and all the non-content overlays. `PixmapItem.paint` does set a per-item
`CompositionMode` (pixmap_item.py:40-42), but since the only content item is the root group (mode
NORMAL), that path is inert today.

## 3. Strengths (keep these)

- **Single source of truth for compositing.** On-screen, filtered, and exported images all come
  from `LayerGroup.render`. No divergence to keep in sync — a real design win, and the thing the
  architecture review worried about but that is actually done right.
- **`QGraphicsView` used for what it's good at.** Viewport transform, zoom/pan, scene coordinate
  mapping (the tool system depends on it), and cheap overlay items. Appropriate tool.
- **Blend modes Qt can't do are handled** via `custom_composite_op` in the model path
  (composite_mode.py:54-, layer_group.py:293), and **group isolation** is implemented
  (layer_group.py:257-278) — both non-trivial and correct in the authoritative path.

## 4. Findings

### R1 — Every content change recomposites the whole image. **HIGH (performance), confirmed.**
`Layer.content_changed` carries a **dirty `QRect`**, but the group compositor ignores it: the
`_image_cache` is **all-or-nothing** (`invalidate()`, layer_group.py:617), so any child edit
invalidates the whole group image and the next `get_qimage()` **re-renders every layer across the
full bounds** (layer_group.py:194-201, render at :204), followed by a full `QImage`→`QPixmap`
conversion for the view (layer_graphics_item.py:66). A render timer (RENDER_DELAY_MS=10,
image_stack.py:127) only *coalesces* bursts; it doesn't reduce the per-render cost.
- **Consequence:** cost scales with total image size × layer count on *every* edit, independent of
  how small the change was. This is the large-image lag in TODO, and the general form of OQ4's
  "huge bitmap is slow" complaint (the selection layer is one instance of a full-size buffer
  recomputed wholesale).
- **Direction:** dirty-region / tiled compositing — recomposite and re-upload only the changed
  rect (the signal already carries it). The mypaint brush already tiles the *active stroke*; the
  gap is at the **group-composite** level. This is the strategic rendering investment; it directly
  enables OQ4 and helps A2.

### R2 — The partial-alpha "compositing glitch" is a model/cache bug, not QGraphicsView. **MED, hypothesis (needs repro).**
Because the view just shows the model composite (§2), the TODO glitch ("brush on alpha-locked
layer, partial alpha … seems like a GraphicsView rendering issue") is **misattributed** — there's
no per-layer QGraphicsView compositing to be wrong. Candidate real causes, in order of suspicion:
1. **Cache invalidation:** an alpha-locked partial-alpha edit not properly invalidating the layer
   pixmap cache and/or the group `_image_cache`, leaving a stale composite.
2. **Premultiplied-alpha handling:** partial-alpha results converting incorrectly through
   `Format_ARGB32_Premultiplied` in the compositor or the pixmap conversion.
3. **`custom_composite_op` / opacity interaction** for partial alpha.
- **Not asserted** — I did not reproduce it. **Recommended next step:** a minimal repro (alpha-lock
  a layer, paint partial alpha, compare `ImageStack.qimage()` bytes to the displayed pixmap) to
  localize it to compositor vs. cache vs. conversion. Whichever it is, the fix is in `image/`,
  not `ui/`.

### R3 — Manual signal wiring for the active layer. **LOW, confirmed.**
`image_viewer._active_layer_change_slot` manually disconnects/reconnects the previous/next active
layer's `transform_changed`/`size_changed` (image_viewer.py:216-235). It's limited in blast radius
today (few items), but it's the manual-connect/disconnect pattern the architecture review flagged
(§4) and a plausible source of the "nested layer selection state not updating" TODO item. A small
"track the current layer's signals" helper would remove the class of bug.

### R4 — Per-item `CompositionMode` is a latent trap if per-layer items are ever added. **NOTE.**
`PixmapItem.paint`'s `setCompositionMode` composites an item against **whatever is already in the
viewport** (background + other items), which is *not* isolated-layer compositing, and
`qt_composite_mode()` returns `None` for unsupported modes (composite_mode.py:55) → silently
Normal. Harmless now (only the NORMAL-mode root group is an item), but **if anyone "optimizes" by
switching to one item per layer, on-screen compositing would silently diverge from the model.**
Documented so that refactor isn't attempted naively — the correct optimization is R1 (tiling the
single composite), not per-layer items.

## 5. Position: keep QGraphicsView; invest in incremental compositing

`QGraphicsView` is the right foundation and should stay — the pressure to replace it that the
architecture review hedged on isn't warranted, because it isn't the compositor. The investment goes
into the **model-side compositor**:

1. **Dirty-region compositing (R1).** Give `LayerGroup` a region-aware cache: composite/refresh
   only the changed rect from `content_changed`, and update only that sub-rect of the displayed
   pixmap (`QPixmap` supports partial updates via re-blitting the region). Staged path: (a) track a
   dirty `QRect` union instead of a boolean cache flag; (b) recomposite only that rect; (c) update
   only that region of the view item.
2. **Optionally tile large images** (align with the mypaint tile size) so both compositing and
   view upload are bounded per edit — this is the shared mechanism OQ4 also wants.
3. **Leave overlays as-is** — outlines/handles/selection are cheap and correctly live in the scene.

## 6. Hand-offs

- **OQ4 (selection-layer perf):** the selection bitmap is a special case of R1 — a full-size buffer
  recomputed/recomposited wholesale. OQ4 should adopt the same dirty-region/tiled approach rather
  than inventing a separate one; a region-aware compositor benefits both. OQ4 can also consider a
  sparser selection representation (RLE/region/quadtree) feeding the same tiled update path.
- **A2 (transform tool):** transforms change a layer's `transform`, which invalidates the group
  composite (full re-render per drag frame under R1) — so the transform tool's live-drag smoothness
  is partly gated on R1. A2 should assume incremental compositing as the target and may want a
  lightweight live-preview item during the drag rather than recompositing each frame.

## 7. Prioritized recommendations

1. **R1 — region-aware group compositing.** HIGH value, medium/large effort; the load-bearing fix
   for large-image performance and the enabler for OQ4 and smoother A2. Stage it (dirty-rect cache
   → partial recomposite → partial view upload).
2. **R2 — reproduce and localize the partial-alpha glitch.** Low effort to repro; fix is in `image/`.
   Do this before R1 so R1's cache rework can incorporate the fix.
3. **R3 — extract an active-layer signal-tracking helper.** Low effort; removes a bug class.
4. **R4 — document "don't switch to per-layer items."** Zero effort; a comment + this note.

## 8. Cross-references / corrections

- **`architecture_review.md` §5 (rendering position):** correct the framing — there is no per-layer
  item lifecycle and no on-screen/export compositing divergence; the view shows the model composite.
  The real issue is whole-image recompositing (R1). "Keep QGraphicsView" stands and is
  strengthened.
- **`_decisions_ledger.md`:** record that on-screen rendering = model composite (single compositor),
  and that the rendering investment is region-aware/tiled compositing shared with OQ4.
- **OQ4 / A2:** see §6 — both should build on R1's incremental compositor, not parallel solutions.
</content>
