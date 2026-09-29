# A2 — Transform tool: shared-state architecture redesign

Design report for OQ9: *"The transform tool's center-of-rotation and the two-way sync between
on-canvas manipulation and the numeric panel fields are buggy and probably need a redesign. What's
the right architecture for that shared transform state so the canvas, the panel, and the layer
transform stay consistent?"*

Reads on top of `_codebase_map.md` (§7 transform rough edges), `_decisions_ledger.md`,
`architecture_review.md` (§3.4/§3.5 home-grown signal mechanisms), `rendering_pipeline.md` (A6 §6
transform hand-off), and `UndoStack.md` (gesture macros). Evidence cited as `file:line`. `[inferred]`
marks reasoning not confirmed by running the code. **Analysis only — no code changed.**

---

## 1. Summary verdict

The transform tool is buggy for one structural reason: **there are three separate holders of the
same state and no single source of truth, and the "hub" that ties them together re-derives its state
by round-tripping through a lossy matrix decomposition on every event.** The center-of-rotation bugs
and the panel↔canvas desync are both symptoms of that.

The three holders:
- **Model** — `TransformLayer._transform`, a full 6-DOF affine `QTransform`, undo-tracked
  (transform_layer.py:33-50). The persistent truth.
- **Canvas hub** — `TransformOutline`, which stores a rect **plus** five decomposed parameters
  (`_x_offset, _y_offset, _x_scale, _y_scale, _degrees`) **plus** a mutable `transformation_origin`
  **plus** its own base-class `QTransform` (transform_outline.py:69-88). It is simultaneously the
  interactive manipulator *and* the conversion layer between matrix and parameters.
- **Panel** — seven spinboxes (x, y, w, h, x-scale, y-scale, angle), each its own widget state, with
  width/height redundant against scale (layer_transform_tool_panel.py:82-98).

The tool wires these together as a manual signal mesh with float-equality guards, `signals_blocked`,
and disconnect/reconnect dances (layer_transform_tool.py:280-307, 259-277). Because the canonical
editing state is **5 parameters about a moving origin** while the model is a **6-DOF matrix**, and
because every `setTransform` does `matrix → extract_transform_parameters → combine → matrix`
(transform_outline.py:146-151), the state is continuously laundered through a decomposition that
**cannot represent shear, is non-unique, and depends on the origin** (geometry_utils.py:193-231).
Float drift and origin-dependence then make the equality guards misfire.

**The fix is architectural, not a patch:** establish **one authoritative, explicitly-decomposed
transform state** owned by a single presenter; make the canvas outline and the panel pure **views**
that render from that state and emit *intents* (not matrices); make the `QTransform` a **derived,
one-directional projection** of the state (never re-extracted mid-gesture); and make the **pivot
(center of rotation) first-class independent state** rather than a value clamped inside the rect and
retro-fitted by re-decomposition. Commit to undo **once per gesture** via an explicit macro, which
also removes a latent undo-loss bug and lines up with `UndoStack.md`.

This is contained to the tool + outline + panel triad. The model API
(`TransformLayer.transform`/`set_transform`) and the `extract`/`combine` helpers stay; only their
*role* changes (extraction becomes a one-time import, not a per-event round-trip).

---

## 2. How it works today

**Flow (panel edit):** a spinbox emits → `LayerTransformToolPanel.<field>_changed` →
`LayerTransformTool.set_*` (layer_transform_tool.py:64-70, 127-157) → a `TransformOutline` property
setter (e.g. `width.setter`, transform_outline.py:202-212) → `combine_transform_parameters(...)` →
`setTransform(matrix)` → `extract_transform_parameters(matrix, origin)` → `_set_transform_by_parameters`
(transform_outline.py:113-144) which mutates the 5 params, calls the base `setTransform`, and **emits
`transform_changed`/`pos_changed`/`scale_changed`/`angle_changed`**.

**Flow (those signals back out):** the tool's `_transform_change_slot` writes the model
(`layer.transform = transform`, layer_transform_tool.py:269-277); `_pos_change_slot`/
`_scale_change_slot`/`_angle_change_slot` push values into the panel widgets (layer_transform_tool.py:291-302)
via `signals_blocked` setters (layer_transform_tool_panel.py:322-386).

**Flow (canvas drag):** `TransformOutline` mouse handlers move handles/offset (transform_outline.py:358-468),
going through the same `_set_transform_by_parameters` path.

**Flow (model → tool):** `layer.transform_changed` → `_layer_transform_change_slot`, guarded by
`if transform != self._transform_outline.transform()` (layer_transform_tool.py:259-262).

So `TransformOutline` is the hub: everything converges on its 5-param state, and every write
round-trips a matrix through `extract`/`combine`.

**The decomposition** (geometry_utils.py:193-231): given a matrix and an origin, it returns
`(dx, dy, sx, sy, angle)` by de-rotating and reading `m11`/`m22`. It asserts no perspective
(`m13==m23==0`, `m33==1`) and **silently assumes no shear** — `sx=m11`, `sy=m22` after removing
rotation is exact only for `translate ∘ rotate ∘ axis-scale` in the exact order `combine` builds
(`T(-origin)·S·R·T(offset+origin)`, geometry_utils.py:240-244). Any other factorization, or float
error, does not round-trip.

---

## 3. Findings (the concrete bugs, ranked)

### F1 — Canonical state is a lossy, origin-dependent decomposition, re-derived every event. **HIGH, root cause.**
Every `setTransform` extracts params about the *current* `transformation_origin`
(transform_outline.py:150). The 6-DOF matrix → 5-param map drops shear and is non-unique; the inverse
depends on the origin. So repeated edits (especially non-uniform scale + rotation) accumulate drift,
and the model matrix and the outline's params can disagree while both believe they're authoritative.
This is the engine under every other symptom.

### F2 — Center of rotation is not independent state; moving it re-decomposes the matrix. **HIGH (the named bug).**
`transformation_origin` is **clamped inside the rect** (transform_outline.py:282-283) — so you cannot
rotate about an external point — and changing it calls `self.setTransform(self.transform())`
(transform_outline.py:289), i.e. re-extracts the *same* matrix about the *new* origin, yielding
different `(dx, dy, angle)` params. Because that factorization differs (and F1's decomposition is
lossy), moving the origin can shift or drift the layer instead of purely relocating the pivot. That
is exactly the "center-of-rotation is buggy" complaint.

### F3 — `x_pos`/`y_pos` use a different coordinate convention than `width`/`height`. **MED.**
`x_pos`/`y_pos` are the **post-rotation scene bounding-box min** (`min over corner points`,
transform_outline.py:171-195), while `width`/`height` are **pre-rotation** (`|rect.w × sx|`,
transform_outline.py:197-229). So the panel mixes a rotation-inclusive position with a
rotation-exclusive size: set X, rotate, and X reads differently; set width and X can jump. The two
numbers don't describe the same rectangle.

### F4 — Redundant panel state, including a live copy-paste bug. **MED (one real bug).**
Width/height and x-scale/y-scale encode the same two DOF and are hand-synced. Worse,
`LayerTransformToolPanel.layer_height` **getter returns the width box**
(`return self._width_box.value()`, layer_transform_tool_panel.py:350) — a copy-paste error, so height
reads are wrong wherever that property is used.

### F5 — Manual signal mesh with float-equality guards. **MED, fragility.**
Consistency depends on exact `QTransform`/float comparisons after lossy round-trips: the model-sync
guard `if transform != self._transform_outline.transform()` (layer_transform_tool.py:261), the
`reset` guard `if changed_transform != source_transform` (layer_transform_tool.py:191), and
`_update_control`'s disconnect/setValue/reconnect (layer_transform_tool.py:280-288). Post-F1 drift
makes these either miss updates or ping-pong. This is precisely the home-grown manual-sync pattern
`architecture_review.md` §3.4/§4 flagged.

### F6 — Per-gesture undo is downgraded and can silently escape the undo history. **MED, ties to UndoStack.**
`_transform_change_slot` does `try: layer.transform = transform  except RuntimeError:
layer.set_transform(transform)` (layer_transform_tool.py:273-276) — it catches the undo stack's
re-entrancy guard and falls back to a **non-undoable** set. The setter path relies on time-based
auto-merge (`UNDO_MERGE_INTERVAL` in `_apply_combinable_change`, layer.py:565+) to fold a drag into
one entry — the very auto-merge `_decisions_ledger.md` marks glitchy/deferred. So during fast drags
some intermediate transforms are committed non-undoably and the "one drag = one undo" grouping is
incidental, not guaranteed.

### F7 — Live drag recomposites the whole image every frame. **MED (perf), overlaps A6/R1.**
Each `set_transform` emits `signal_content_changed(self.bounds)` when visible
(transform_layer.py:49-50), which invalidates the group composite (A6 R1) — so every drag frame
triggers a full recomposite. A6 §6 already flagged that transform smoothness is partly gated on
incremental compositing.

---

## 4. Target architecture

One idea underlies all of it: **the editable transform state is authoritative and explicit; the
matrix and the widgets are projections of it.**

### 4.1 A single authoritative `TransformState`
Introduce one value object holding the parameters the user actually edits, in a **stable coordinate
space** (layer-local / image space, not scene-bounding-box space):

- `base_rect` (the layer's untransformed bounds),
- `translation` (tx, ty) — the position of a **defined anchor** (recommend: the image-space location
  of the layer origin, i.e. the translation component — rotation-independent and exact-round-tripping),
- `scale` (sx, sy),
- `rotation` θ,
- `pivot` — the center of rotation/scale, **in image space, unconstrained** (may lie outside the
  rect).

This is stored and mutated directly; it is **never re-derived from the matrix during editing.**

### 4.2 The matrix is a one-directional pure projection
`state → QTransform` is a single pure function (reuse `combine_transform_parameters`, generalized to
take the pivot). The model is written from it. The reverse (`matrix → state`) is needed **only once**,
when the tool adopts a layer whose `transform` was set elsewhere (menu rotate/flip, a loaded file) —
and there a *documented canonical decomposition* is acceptable because it's a one-time import, not a
per-event loop. This removes F1 entirely.

### 4.3 Pivot is first-class → center of rotation is stable
Because the pivot is explicit state (4.1), rotation and scale are defined about it directly; there's
no re-decomposition. Moving the pivot is a well-defined operation: **change `pivot`, and adjust
`translation` so the layer's current on-screen position is preserved** (keep the pre-image of the
pivot fixed) — a pure, exact computation, no matrix laundering. The pivot may be dragged outside the
rect. This resolves F2.

### 4.4 One presenter owns the state; canvas and panel are views
Ownership becomes a clean star, not a mesh:

```
            ┌─────────────── TransformPresenter ───────────────┐
            │  owns the single TransformState                  │
            │  the ONLY writer of state and of layer.transform │
            └───▲───────────────▲───────────────────▲──────────┘
        intents │           intents │        one-way │ render
                │                   │               state
     ┌──────────┴───┐     ┌─────────┴────┐   ┌────────┴─────────┐
     │ CanvasView   │     │  PanelView   │   │  Model layer     │
     │(TransformOut)│     │ (spinboxes)  │   │ (write-only sink)│
     └──────────────┘     └──────────────┘   └──────────────────┘
```

- **Views never talk to each other or to the layer.** They (a) render from the state via one
  `update_from_state(state)` method that sets all widgets/handles with signals blocked in a single
  place, and (b) emit **semantic intents** — `translate_by(dx,dy)`, `set_rotation(θ)`,
  `set_width(w)`, `move_pivot(p)`, `scale_about_pivot(...)` — not matrices.
- **The presenter is the only writer.** It applies an intent to the state, projects to a matrix,
  writes `layer.set_transform(...)`, and notifies views once. Deduping compares to its own last
  committed state with a **tolerance**, not exact float equality — killing F5.
- This is the standard "one model, many views, one controller" shape; it deletes the disconnect/
  reconnect and `!=`-guard machinery.

### 4.5 Resolve the panel conventions and redundancy (F3, F4)
- Pick **one** position convention and document it: X/Y = the chosen anchor from 4.1 (rotation-
  independent), with any "bounding-box left" shown only as a separate read-only readout if wanted.
- Eliminate the width/height ↔ scale redundancy: keep **one** editable pair and show the other
  read-only (recommend editable **width/height**, derived scale read-only — matches user mental
  model), which also disposes of the `layer_height` bug (F4) by construction.

### 4.6 Undo as an explicit per-gesture macro (F6)
The presenter brackets each gesture: on drag-start / spinbox focus-in it opens a
`combining_actions` macro (or a mergeable command under the QUndoStack migration); intermediate
updates use non-undoable `set_transform`; on release / commit it records **one** undo entry for the
whole gesture. Drop the `try/except RuntimeError` fallback. This is exactly the "one drag = one undo"
macro `UndoStack.md` and `_decisions_ledger.md` describe, and it stops relying on the deferred
time-based auto-merge.

### 4.7 Live preview instead of per-frame recomposite (F7)
During a gesture the presenter drives a **lightweight preview** — transform the layer's cached pixmap
via a graphics-item transform (the outline can host the preview) — and writes the real
`layer.set_transform` **once on commit**, so only one full recomposite happens per gesture. This is
A6 §6's recommendation; it depends on nothing in R1 but composes with it.

---

## 5. Why this stays consistent (the guarantees)

- **Single writer** (presenter) ⇒ canvas, panel, and model cannot diverge; there's nothing to
  reconcile.
- **State→matrix is total and one-directional** ⇒ no lossy round-trip in the edit loop; drift can't
  accumulate. `matrix→state` runs once per layer-adoption with a documented canonical form.
- **Pivot is explicit** ⇒ center of rotation is stable and can be external; moving it is a pure
  translation adjustment, never a re-decomposition.
- **Views emit intents, render from state** ⇒ no float-equality guards, no cross-view signals, no
  reentrancy dances.
- **One macro per gesture** ⇒ deterministic undo, no silent non-undoable writes.

---

## 6. Migration plan (contained; model API untouched)

Stage so each step is independently landable and testable:

1. **Fix F4 now** (the `layer_height` getter bug) — one line, independent of the redesign.
2. **Introduce `TransformState` + the pure `state→QTransform` projection** behind the existing tool,
   initially feeding the current outline/panel — no behavior change, just a seam.
3. **Make the presenter the sole writer:** route all panel/canvas edits through intents into the
   presenter; the presenter writes state → matrix → `layer.set_transform`. Delete the tool's
   per-slot panel-poking and the `!=` guards (F5).
4. **Promote the pivot to first-class state** and rework `transformation_origin` handling to 4.3;
   remove the in-rect clamp and the `setTransform(self.transform())` re-decomposition (F2).
5. **Turn `TransformOutline` into a pure view:** it renders handles/rect from the state and emits
   intents; it no longer stores the 5 params or does `extract`/`combine` internally (F1).
6. **Unify panel conventions / redundancy** (4.5) and add the **gesture macro** (4.6).
7. **Add the live-preview commit** (4.7).

Keep `TransformLayer.transform`/`set_transform` and `extract`/`combine_transform_parameters` as-is —
`rotate`/`flip` menu actions (transform_layer.py:91-114) already go straight to the model and are
unaffected. `TransformGroup` (the group-wrapping path, layer_transform_tool.py:171-172) rides the
same presenter unchanged.

---

## 7. Testing

The redesign makes the core logic **UI-free and unit-testable** — the biggest test win here (A1
flags transform as a near-zero-coverage, high-bug area):
- **State/matrix round-trip:** `state → matrix → (canonical) state` is identity within tolerance;
  property tests over random translate/scale/rotate/pivot.
- **Pivot invariance:** moving the pivot leaves every rendered corner fixed (the layer must not
  jump) — directly pins F2.
- **Convention consistency:** setting width then rotating leaves X unchanged; setting X then reading
  X is exact — pins F3.
- **Presenter is sole writer:** a fake layer records that each gesture yields exactly one
  `set_transform` commit and one undo entry — pins F5/F6.
- **Panel projection:** `update_from_state` sets all fields without re-emitting intents (no feedback
  loop); `layer_height` returns height — regression-guards F4.
- Keep a golden-image check for a representative transform (rotate+scale about an off-center pivot)
  through the existing render path.

Because the presenter/state carry no Qt-thread affinity concerns (all main-thread, per
`concurrency_model.md`), these are fast offscreen tests.

---

## 8. Risks & cross-references

- **R-1: canonical import decomposition.** The one remaining `matrix→state` (layer adoption) still
  can't represent shear. That's fine — the tool only ever *produces* shear-free transforms, and
  foreign shear (rare) can be preserved as an opaque residual matrix multiplied in, or rejected. Document it.
- **R-2: `TransformGroup` semantics.** Group transforms wrap child bounds (transform_group.py); verify
  the pivot/anchor conventions hold for the synthesized group rect (bounds_changed path,
  layer_transform_tool.py:244-248).
- **R-3: interplay with the QUndoStack migration.** Build the gesture macro against whatever
  `combining_actions` becomes post-migration (`UndoStack.md`); don't hard-code the current
  time-merge. Coordinate so A2 and the undo migration don't both rewrite the commit path.
- **Cross-refs:** `architecture_review.md` §3.4/§4 (this retires the flagged manual-signal-sync
  mechanism); `rendering_pipeline.md` §6 (live-preview/commit is the transform half of that
  hand-off); `UndoStack.md` (gesture macro, drop the `try/except`); `_decisions_ledger.md`
  (time-based auto-merge deferral — A2 must not depend on it).

---

## 9. Doc updates warranted

- `_decisions_ledger.md`: record (a) the diagnosis — three state holders, lossy origin-dependent
  decomposition as the hub, center-of-rotation re-decomposition — and (b) the direction: single
  authoritative `TransformState` + presenter-owns-state + views-emit-intents + first-class pivot +
  one-directional matrix projection + per-gesture undo macro + live-preview commit. Note the
  `layer_height` getter bug (F4) as a confirmed bug to fix.
- `_execution_plan.md`: mark A2 done; note it depends loosely on A6 (live preview) and coordinates
  with the UndoStack migration on the commit path.
- `README.md`: index this report.
