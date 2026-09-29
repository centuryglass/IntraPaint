# OQ4 — Selection-layer bitmap efficiency

Deep-dive on the "huge bitmap for a 1-bit selection layer" performance question. Builds directly on
`rendering_pipeline.md` (A6) — especially R1 and the §6 hand-off — and reads on top of
`_codebase_map.md` (§4 selection layer) and `_decisions_ledger.md`.

Evidence cited as `file:line`. `[inferred]` marks reasoning not confirmed line-by-line. **Analysis
only — no code changed.**

---

## 1. Summary verdict

The complaint is **correct and the fix is unusually clean**, because the selection layer has three
properties the current implementation doesn't exploit:

1. **Its data is genuinely 1-bit.** Every content change hard-thresholds alpha to
   `0` or `255` (selection_layer.py:220-227), so the layer is a binary mask stored as a full-size
   **32-bit** `ARGB32_Premultiplied` `QImage` — a **32× bit-depth overhead** on the information it
   carries.
2. **Its bitmap is never displayed.** The selection's `LayerGraphicsItem` is drawn at
   `setOpacity(0)` (layer_graphics_item.py:38); what the user actually sees is the vector **outline
   overlay** (`SelectionOutline`, image_viewer.py:249). So the full-size pixmap that gets rebuilt on
   every edit (`QPixmap.fromImage`, layer.py:308, via the item's `_update_pixmap`) **renders
   nothing** — it's pure waste.
3. **It's decoupled from the main image composite.** The selection layer is a standalone top-level
   item, *not* a child of the root `LayerGroup` (image_stack.py:134; scene-added separately at
   image_viewer.py:103). So — unlike A6/R1 — selection edits don't recomposite the image. The lag is
   **self-contained** to the selection layer's own per-edit work, which makes OQ4 fixable
   independently of R1.

The cost has two parts: **memory** (a full W×H×4 buffer, plus a second full-size `QPixmap` that's
invisible) and **per-edit CPU** (whole-image numpy passes and a `cv2` contour re-vectorization that
allocates **9× the pixel area**). Both scale with total canvas size regardless of how small the edit
was — exactly the reported "significant lag on very large images."

**Recommendation (staged, least-disturbance-first):**
- **Stage 1 (low-risk, big constant-factor win):** drop the phantom pixmap; store the mask as
  **`Format_Alpha8`** (4× memory cut) with a lazily-synthesized ARGB/`mask_image` view; bound the two
  remaining whole-image passes to the change rect. Public API unchanged.
- **Stage 2 (structural, A6-aligned):** back the selection with a **tiled binary mask** (same tile
  grid A6/R1 introduces) plus a **`QRegion`** as the authoritative geometry for boolean ops and
  outline generation. This bounds memory to the *selected* area, makes select-all/clear/invert
  O(tiles), and replaces the fragile `cv2` outline path (which also fixes the "outline fails to join
  sections" bug, `_codebase_map.md` §7).

Keep the whole external API surface intact throughout (§6) — the ~20 members other code calls are all
preservable as thin facades over either representation.

---

## 2. How the selection layer works today

`SelectionLayer` (selection_layer.py:34) is an `ImageLayer` subclass whose `_image` is a full-size
`ARGB32_Premultiplied` `QImage` (image_layer.py:52,98). It is created once, sized to the image, and
resized to match (image_stack.py:134). Invariants (docstring, selection_layer.py:37-51): exactly one
exists, always image-sized, pixels are `#00000000` or `#FFFF0000` (1-bit), never copied, never saved,
always on top, never the active layer.

**Write path.** Selection tools paint through the normal layer machinery: the selection brush uses a
`QtPaintBrush` on `image_stack.selection_layer` (selection_brush_tool.py:11,65), which mutates via
`ImageLayer.borrow_image(change_bounds)` (image_layer.py:154-190) — so strokes *do* carry a dirty
`change_bounds`. `select_all` / `invert_selection` / `grow_or_shrink_selection`
(selection_layer.py:131-173) instead replace the whole `self.image`.

**On every change**, `_handle_content_change(image, last, change_bounds)`
(selection_layer.py:186-267) runs and does four things:
1. `self._update_bounds(np_image)` — recomputes the masked bounding box (selection_layer.py:208).
2. `image_is_fully_transparent(np_image)` — **whole-image** transparency scan
   (selection_layer.py:209; image_utils.py:37).
3. **Binary color/alpha enforcement** — threshold alpha `>0`, force `#FF0000`/`255` else `0`
   (selection_layer.py:220-227). Bounded by `change_bounds` *when present* (line 213-215), else
   whole-image.
4. **Outline re-vectorization** — `np.kron(alpha, ones(3,3))` upscales the mask **3× per axis (9×
   area)** then `cv2.findContours` (selection_layer.py:261-267). Bounded to the change rect ∪
   intersecting existing polygons *when* `change_bounds` is set (line 234-256); **whole-image** on any
   full replace (line 257-259).

**Display path.** The selection's `LayerGraphicsItem` sits in the scene at `setOpacity(0)`
(layer_graphics_item.py:35-38) and still runs `_update_pixmap` → `self._layer.pixmap` →
`QPixmap.fromImage(full_image)` (layer.py:303-308) on every change. The **visible** selection is the
`SelectionOutline` polygon item, refreshed from `selection_layer.outline` (image_viewer.py:238-249),
plus the "inpaint full-res" generation-area outline.

**Read path (why the pixmap data still matters).** Consumers need pixels in three places:
- **Inpainting mask:** `mask_image` / `pil_mask_image` crop the buffer to the generation area
  (selection_layer.py:176-184), later Gaussian-blurred before use (image_generator.py:163).
- **"Selection only" edits:** brushes/filters read the mask to constrain writes (`filter.py`,
  `qt_paint_brush.py`, image_stack copy/clear-selected).
- **Geometry queries:** `generation_area_is_empty`, `generation_area_fully_selected`,
  `get_selection_gen_area`, `get_content_bounds` (selection_layer.py:117-353).

So the buffer is a *model + mask source + outline source* — **never a display source.**

---

## 3. Where the cost actually is

### 3.1 Memory — a 32× overhead plus an invisible duplicate. **HIGH.**
The mask needs 1 bit/pixel; it's stored at **32 bits/pixel**. At 8000×8000 that's **256 MB** for the
selection `QImage` alone — and the opacity-0 item forces a **second** full-size `QPixmap`
(`QPixmap.fromImage`, layer.py:308) that is **never drawn**, roughly doubling it. Every full-image
numpy op below also allocates transient full-size arrays.

### 3.2 Per-edit CPU that ignores edit size. **HIGH.**
Even for a small brush dab, `_handle_content_change` runs:
- a **whole-image** `image_is_fully_transparent` scan (selection_layer.py:209) — O(W·H) every time,
  never bounded by `change_bounds`;
- the opacity-0 **`QPixmap.fromImage`** rebuild over the full image (layer.py:308) — O(W·H), for
  nothing;
- `_update_bounds`, bounded to the generation area but still a numpy pass (selection_layer.py:99-115).

The color-enforcement and outline steps *are* change-bounds-aware for brush strokes — good — but the
outline step still does the **9× `np.kron` upscale + `cv2.findContours`** on that region
(selection_layer.py:261), which is the single most expensive operation per stroke.

### 3.3 Whole-canvas operations are worst-case on every axis. **HIGH.**
`select_all` (selection_layer.py:131), `invert_selection` (:137), and `grow_or_shrink_selection`
(:147) each allocate a **full-size** buffer, run full-image numpy / `cv2.dilate|erode` with a
`|num_pixels|·3` kernel, and — because they replace `self.image` with **no `change_bounds`** — trigger
the **whole-image** branch of `_handle_content_change`, i.e. a full 9×-area `cv2.findContours` over the
entire canvas (selection_layer.py:257-267). On a large image these are multi-hundred-millisecond,
allocation-heavy operations for what are conceptually trivial region ops (fill-all, XOR, morphology).

### 3.4 The outline vectorizer is both slow and buggy. **MED.**
`np.kron(...×9) → cv2.findContours → per-point QPolygonF` (selection_layer.py:261-267) is the hot path
*and* the source of the "outline occasionally fails to join sections" issue in `_codebase_map.md` §7
`[inferred: same code]`. Replacing it (Stage 2) removes a cost and a bug together.

---

## 4. The key insight that makes this easy

Because **the bitmap is never displayed** (§1.2) and **the data is truly binary** (§1.1), the
selection layer does not need to *be* a full-color raster. It needs to (a) answer "is pixel/region
selected?", (b) export a mask raster for the generation area, (c) support boolean/morphology ops, and
(d) produce an outline. All four are better served by a **compact binary representation** than by a
32-bit image — and its **only** on-screen product is the vector outline, which is cheap.

Equally important: the selection is **not** part of the root-group composite (§1.3), so this fix is
**orthogonal to R1** and can ship on its own timeline. It should still *reuse* R1's tile
infrastructure rather than invent a parallel one (per A6 §6).

---

## 5. Design options

| Option | Memory | Boolean/morph ops | Outline | Mask export | API disturbance | Verdict |
|---|---|---|---|---|---|---|
| **A. Keep ARGB32 QImage** (today) | W·H·4 + phantom pixmap | numpy/cv2 whole-image | cv2 ×9 | crop | — | baseline, the problem |
| **B. `Format_Alpha8` QImage** | W·H·1 (4× cut), no pixmap | numpy/cv2, bounded | cv2 (smaller) | crop + synth ARGB | **minimal** | **Stage 1** |
| **C. Tiled binary mask** (A6 tile grid) | ∝ selected area | per-tile | per-dirty-tile, cached | assemble tiles | moderate | **Stage 2 core** |
| **D. `QRegion` authoritative geometry** | scanline-RLE (tiny) | native `unite/intersect/subtract/xor` | `QRegion → QPainterPath` (native, fixes §3.4) | rasterize region→mask | moderate | **Stage 2 geometry** |
| E. RLE / quadtree hand-rolled | small | custom | custom | custom | high | not worth it vs C+D |

**Why C+D over a hand-rolled sparse structure (E):** Qt already ships the two primitives. `QRegion`
is a scanline-compressed integer region with fast native boolean ops and direct conversion to a
`QPainterPath` (→ outline polygons, replacing §3.4 wholesale). Tiles align the mask with A6/R1 so a
single tiling mechanism serves both compositing and selection. Rolling our own RLE/quadtree
(E) reintroduces exactly the kind of home-grown mechanism the architecture review warns against.

**On antialiasing/feathering:** none is lost. The stored selection is *already* hard-thresholded to
binary (selection_layer.py:220), and softness is applied downstream by blurring the exported mask
(image_generator.py:163). A binary region/tile model preserves current behavior exactly. `[If a
future soft-selection feature is wanted, keep an optional 8-bit tile payload — the tile model
accommodates it; QRegion alone would not.]`

---

## 6. Recommended plan (preserve the public API)

The external surface is small and every member is a thin facade over either representation. Members
called outside the class (verified by grep): `image`, `mask_image`/`pil_mask_image`, `outline`,
`position`, `get_selection_gen_area`, `content_changed`, `clear`, `visible`, `transform`/`set_transform`,
`adjust_local_bounds`, `invert_selection`, `grow_or_shrink_selection`, `get_content_bounds`,
`generation_area_is_empty`, `generation_area_fully_selected`, `select_all`, `borrow_image`,
`image_bits_readonly`, `map_rect_from_image`, `save_state`/`restore_state`. **Keep all of them**;
change only the storage behind them.

### Stage 1 — constant-factor win, minimal disturbance (do first)
1. **Kill the phantom pixmap.** For the selection's `LayerGraphicsItem`, skip `_update_pixmap` /
   pixmap construction entirely (it's opacity 0). Either short-circuit `pixmap` for `SelectionLayer`
   or don't add it as a rendered item at all — the outline is a separate overlay already. Removes a
   full-size `QPixmap.fromImage` per edit and one full-size allocation. **Zero API change.**
2. **Store the mask as `Format_Alpha8`** internally; synthesize the ARGB `#FFFF0000` image only when
   `image`/`mask_image` is actually read (they're comparatively rare, and generation blurs the result
   anyway). 4× memory cut; numpy ops get simpler (single channel). Consumers still receive a `QImage`.
3. **Bound the whole-image passes to `change_bounds`.** Make `image_is_fully_transparent` track a
   running "any-selected" count / dirty union instead of rescanning the full image
   (selection_layer.py:209), and never take the whole-image outline branch for a bounded edit.
4. **Reuse the dirty rect A6/R1 standardizes** (`content_changed`'s `QRect`) so selection and
   compositor speak the same "changed region" language.

Stage 1 alone removes the two full-size allocations per stroke and cuts memory 4× with essentially no
blast radius — a safe first PR.

### Stage 2 — structural, A6-aligned (the real fix)
5. **Introduce a tiled binary mask** on the A6/R1 tile grid: a sparse map of occupied tiles; empty
   tiles cost nothing; a "fully selected" flag gives select-all/clear O(1)-ish. Memory becomes
   proportional to the *selected* area, not the canvas.
6. **Adopt `QRegion` as the authoritative geometry** for `select_all` (region = full rect),
   `invert_selection` (`region.xored(fullRect)`), and `grow_or_shrink_selection` (region grow/shrink,
   or morphology per dirty tile) — all native, allocation-light, and edit-sized.
7. **Generate outlines from the region** via `QRegion → QPainterPath → polygons`, cached per dirty
   tile so untouched tiles keep their polygons. Deletes the `np.kron`/`cv2.findContours` path
   (§3.4) and its join bug.
8. **Export the inpaint mask** by rasterizing only the generation-area tiles/region — `mask_image`
   assembles from tiles instead of cropping a full buffer.

Stages can ship independently; Stage 1 delivers most of the felt latency win, Stage 2 delivers the
memory-scaling win and the outline-bug fix.

---

## 7. Relationship to A6 / R1 (don't build a parallel solution)

Per A6 §6, OQ4 must **reuse** R1's dirty-region/tile machinery, not invent its own. Concretely:
- **Tile grid & size:** adopt whatever R1/mypaint uses (mypaint already tiles the active stroke,
  A6 §4) so there's one tiling notion across compositing and selection.
- **Dirty `QRect`:** both consume `content_changed`'s rect; Stage 1.3-1.4 makes the selection
  change-bounds-clean, which is a prerequisite R1 also needs.
- **Independence:** because the selection isn't in the group composite (§1.3), OQ4 can land *before*
  R1 — but design the tile model as the *shared* one so R1 slots onto it, rather than R1 shipping a
  different tile abstraction later.

`[If R1's tiling isn't built yet when OQ4 starts, Stage 1 + the QRegion geometry (6-7) still stand
alone; only the tiled raster (5,8) should wait to align with R1's tile type.]`

---

## 8. Testing

- **Golden mask/outline tests:** for each op (brush dab, select-all, invert, grow, shrink, clear,
  generation-area change), assert the exported `mask_image` and `outline` polygons match the current
  implementation's output — the migration must be behavior-preserving. Use small fixtures; add one
  large-canvas case to guard the perf path.
- **Boolean-op equivalence:** property-test `QRegion` results against the current numpy/cv2 results
  on random masks (invert∘invert == identity; grow then shrink ⊇ original; select-all fully selected).
- **Perf regression guard:** time a fixed brush stroke and a select-all on a large canvas
  (e.g. 8000×8000) before/after; the whole-image passes should drop out. (Keep it a coarse threshold,
  not a flaky micro-benchmark.)
- **Consumer smoke tests:** inpaint mask round-trip (blurred mask still correct), "selection only"
  filter/brush masking, copy/clear-selected in `image_stack`.
- Existing selection tools + the `test_generator` mask path exercise the envelope; keep them green
  per stage. Coverage here is currently thin (A1), so add these as part of the change.

---

## 9. Risks & sequencing

- **R1-alpha thresholding assumptions.** Some consumers may read intermediate non-binary alpha before
  `_handle_content_change` re-thresholds. Verify the mask is always observed post-threshold; the
  binary model depends on it. **Low, but confirm.**
- **`image`/`mask_image` format expectations.** Consumers expect `#FFFF0000` ARGB. Synthesize exactly
  that in the lazy view (Stage 1.2). Golden tests (§8) cover it.
- **`borrow_image` semantics.** Tools mutate via `borrow_image` returning the live `QImage`
  (image_layer.py:154). Under a tiled/region model this needs a compatibility path (hand back a
  rasterized tile buffer, re-ingest on release) — a real design point for Stage 2; Stage 1 keeps
  `borrow_image` trivial since storage is still a (smaller) QImage.
- **`save_state`/`restore_state` & transforms.** Selection participates in undo and can be
  transformed (`adjust_local_bounds`, `set_transform`); the region/tile model must serialize and
  transform correctly. Region transforms are integer-only — fine for the current axis-aligned use;
  flag if arbitrary-matrix selection transforms are ever needed.

**Sequence:** Stage 1 (phantom-pixmap removal → Alpha8 → bound whole-image passes) as one low-risk PR;
then Stage 2 geometry (QRegion for ops + outlines) ; then the tiled raster aligned with R1. Land Stage
1 regardless of R1 status.

---

## 10. Doc updates warranted

- `_decisions_ledger.md`: record that (a) the selection bitmap is truly 1-bit and never displayed
  (opacity-0 item; outline is the visible product), (b) the fix is a staged Alpha8→tiled-binary +
  `QRegion` migration that **reuses R1's tiling**, and (c) OQ4 is independent of R1 and can land
  first.
- `_execution_plan.md`: mark OQ4 done; note it shares the tile substrate with R1 and feeds A2 only
  loosely.
- `rendering_pipeline.md` §6 hand-off is satisfied by this report; no correction needed.
