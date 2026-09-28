# Decisions ledger — settled calls (do not re-open)

Short, dated record of decisions already made, so downstream analysis reports and delegated
agents don't waste effort re-litigating them or contradict each other. Pair with
`_codebase_map.md`. Add a line whenever a call is settled; if a decision is genuinely reversed,
edit it here rather than leaving stale guidance.

Format: `[YYYY-MM-DD] Topic — decision. (rationale / where documented)`

---

## Undo system
- [2026-08-10] Replace hand-rolled `UndoStack` with Qt's `QUndoStack` — **yes**, via a
  compatibility **wrapper** that preserves the current public API (minimal call-site churn), not
  a native-`QUndoCommand` migration of every call site. Full plan in `UndoStack.md`.
- [2026-08-10] Global time-based **auto-merge** — **defer** (Phase 3). It's glitchy as-is; we
  want to support it eventually but will ship the migration without it first, relying on explicit
  `combining_actions` macros + `mergeWith` coalescing for "one drag = one undo."
- [2026-08-10] `AppConfig.max_undo` being unwired, and `undo_in_progress` sticking `True` on an
  empty-stack undo — confirmed **bugs**, to be fixed as part of the migration (not preserved).

## Concurrency (from concurrency_model.md, A5)
- [2026-08-10] **Verified fact:** `AsyncTask` finish/result handlers run on the **main thread**
  (its sender objects are constructed on the main thread → cross-thread signal delivery is queued
  to main). So filters and generation commit model/undo changes on the GUI thread.
- [2026-08-10] Undo ↔ concurrency dependency **downgraded**: because of the above, the QUndoStack
  migration's "main-thread only" requirement is already met on the paths that matter. A5 is a
  *parallel cleanup*, no longer a hard prerequisite for the undo work. (Supersedes the "prerequisite"
  framing in UndoStack.md risk #1 and architecture_review §5.)
- [2026-08-10] Governing Qt rule (verified): a cross-thread signal connected to a **bare callable**
  runs on the **sender's** owning thread; connected to a **QObject method**, it runs on that
  object's thread. New `moveToThread` workers must use QObject slots / QueuedConnection, not closures.
- [2026-08-10] Target discipline: **all model/config/undo/UI mutation on the GUI thread; workers
  produce data only and hand back via main-thread-affinity signals.** `Config.set` to become
  main-thread-only (removes a confirmed off-main deadlock, concurrency_model.md F1).
- [2026-08-10] `spacenav` confirmed **known-broken** (per maintainer); its off-main threading bug
  (F3) is documented but not an active fix.

## Rendering (from rendering_pipeline.md, A6)
- [2026-08-10] **Verified fact / correction:** on-screen rendering = the model's authoritative
  composite. The scene holds only two items (selection + root layer group); the root group's
  `get_qimage()`/`render()` composites all children (incl. isolate + custom blend ops) and the view
  shows that single pixmap. There is **no per-layer QGraphicsView compositing** and **no
  on-screen/export divergence** — supersedes the tentative "per-layer lifecycle / divergence"
  framing in architecture_review §5.
- [2026-08-10] **Keep QGraphicsView** — it's the viewport/overlay layer, not the compositor. The
  rendering investment is **region-aware / tiled compositing** in `LayerGroup` (recomposite only the
  changed rect; the dirty QRect already rides on `content_changed` but is currently discarded — the
  group cache is all-or-nothing). This is the large-image perf fix and the **shared substrate for
  OQ4 and A2** — they must build on it, not invent parallel solutions.
- [2026-08-10] The partial-alpha "GraphicsView glitch" (TODO) is **misattributed**: it's a
  model-compositor / cache-invalidation / premultiplied-alpha bug in `image/`, not a QGraphicsView
  issue. Needs a repro (rendering_pipeline.md R2). Do NOT switch to per-layer scene items as an
  "optimization" — that would reintroduce real divergence (R4).

## Backend auto-install (from backend_autoinstall.md, OQ3)
- [2026-08-10] **Verified fact:** IntraPaint is **client-only today** — no code launches, installs, or
  manages a backend process (no subprocess/QProcess in `src/`); generators only connect to a URL and
  hand the user a rich-text install guide. That guide is the adoption barrier.
- [2026-08-10] **Reframing:** the barrier is two problems — **configuration** (wiring an existing
  backend, cheap) and **installation from zero** (Python env + multi-GB PyTorch/GPU build + multi-GB
  model, hard). Front-load the configuration win.
- [2026-08-10] **Direction:** a pluggable **backend-provisioner** subsystem targeting **ComfyUI only**
  (per OQ5), with: (1) **detect-and-reuse existing installs first** (Stability Matrix / portable /
  existing model dirs) — zero-download config fix; (2) a **ManagedComfyUI lifecycle** (spawn as child
  process, health-check via existing `get_system_stats`, auto-launch branch in `configure_or_connect`);
  (3) fresh-install engines = **drive the official `comfy-cli`** (never hand-roll the torch/GPU matrix)
  + a **Windows-portable** fast-path (self-contained, the default for PyInstaller bundles); (4) honest
  model story (curated **ungated** list + first-class BYO + **deep-link** gated, never scrape).
- [2026-08-10] All long-running install work runs in **AsyncTask workers streaming to the setup
  window's Status pane** (concurrency_model.md §5 — no GUI-thread blocking). UI hook = one "Set up
  automatically" button in `GeneratorSetupWindow` + one branch in `configure_or_connect`; rest of app
  undisturbed. A1111/Forge get **detection only, no auto-install** (OQ5 downgrade). GLID untouched.
- [2026-08-10] **Hands packaging constraints to A7** (bundled builds have no user Python → portable
  engine default; install lives in a `platformdirs` user data dir, outside the app bundle).

## Selection-layer performance (from selection_layer_perf.md, OQ4)
- [2026-08-10] **Verified facts:** the selection layer's data is truly 1-bit (alpha hard-thresholded
  to 0/255 every change, selection_layer.py:220) yet stored as a full-size 32-bit ARGB QImage (32×
  overhead); its bitmap is **never displayed** — its `LayerGraphicsItem` is opacity-0
  (layer_graphics_item.py:38) and the visible selection is the vector outline overlay; and it is
  **not** part of the root-group composite (standalone item), so OQ4 is **independent of R1** and can
  land first.
- [2026-08-10] Fix direction — **staged, API-preserving.** Stage 1 (low-risk): drop the phantom
  opacity-0 pixmap, store the mask as `Format_Alpha8` (4× memory cut) with a lazily-synthesized ARGB
  view, and bound the remaining whole-image passes to `change_bounds`. Stage 2 (structural): a **tiled
  binary mask on R1's tile grid** + **`QRegion`** as authoritative geometry for boolean/morphology ops
  and outline generation (replaces the np.kron×9 + cv2.findContours path, also fixing the "outline
  fails to join sections" bug). Keep the full public API as thin facades.
- [2026-08-10] **Reuse R1's tiling, don't invent a parallel one** (per rendering_pipeline.md §6). No
  antialiasing/feathering is lost — softness is applied downstream by blurring the exported mask.

## Transform tool (from transform_tool_redesign.md, A2)
- [2026-08-10] **Diagnosis:** the tool's bugs stem from **three separate state holders with no single
  source of truth** — the model `QTransform` (6-DOF), the `TransformOutline` (5 decomposed params +
  mutable origin + its own matrix, the "hub"), and the panel (7 redundant spinboxes). The hub
  re-derives its state by round-tripping the matrix through a **lossy, shear-dropping,
  origin-dependent decomposition** (`extract`/`combine_transform_parameters`) on every event, so drift
  accumulates and float-equality guards misfire. Center-of-rotation is buggy because
  `transformation_origin` is clamped inside the rect and moving it **re-decomposes the same matrix**
  about the new origin (transform_outline.py:289). Confirmed bug: `LayerTransformToolPanel.layer_height`
  getter returns the width box (layer_transform_tool_panel.py:350).
- [2026-08-10] **Direction:** single authoritative **`TransformState`** (base_rect, translation,
  scale, rotation, **first-class pivot** in image space) owned by one **presenter** that is the sole
  writer of state and of `layer.transform`; the canvas outline and panel become **views** that render
  from state and emit **semantic intents** (not matrices). Matrix is a **one-directional pure
  projection** of state; `matrix→state` runs **only once** on layer adoption (documented canonical
  form). Moving the pivot = change pivot + adjust translation to keep the layer fixed (pure, exact).
  Resolve panel convention mismatch (position rotation-inclusive vs size rotation-exclusive) and
  width/height↔scale redundancy. **Undo = one explicit `combining_actions` macro per gesture** (drop
  the `try/except RuntimeError` non-undoable fallback; don't rely on the deferred time-based
  auto-merge). **Live-preview during drag, commit `set_transform` once** (A6 §6). Model API
  (`TransformLayer.transform`/`set_transform`) and the geometry helpers stay; change is contained to
  the tool+outline+panel triad.

## Config system (from config_system.md, A4)
- [2026-08-10] `config_from_key` / cross-file key exclusivity — **RESOLVED**: enforce exclusivity
  via a **shared key→owning-Config registry** populated at construction (duplicate key raises at
  startup); keep `config_from_key` but make it an O(1) registry lookup. Do NOT scrap it — generic
  code (settings modal, menu_builder) legitimately needs owner-lookup from a bare key.
- [2026-08-10] Config change-notification — **direction**: replace the reflection-based arity
  dispatch + `'already deleted'` exception-string lifetime handling with **per-entry Qt signals**.
  This is the keystone config change; it also fixes A5 F2 (off-main callbacks) and
  architecture_review §3.4.
- [2026-08-10] Config/Parameter → UI **dependency inversion** confirmed (`config.py` and
  `util/parameter.py` import `ui/input_fields`). Direction: extract a UI-side widget factory; keep
  `Config`/`Parameter` UI-free. (architecture-level, larger blast radius.)
- [2026-08-10] Config persistence to become **atomic** (temp + os.replace) and **main-thread-only**
  (removes A5 F1 deadlock). Data-driven definition model + ConfigEntry↔Parameter reuse: **keep**.

## Testing
- [2026-08-10] Existing `test/` suite — may be **refactored/extended significantly**; not frozen.
  Don't redesign coverage for areas already adequately served (see `test-wip/README.md` status
  table: `geometry_utils`, `image_fill` are adequate).
- [2026-08-10] Tool-test harness default base — the **lighter combo** (`ImageStack` +
  `ImageViewer`/`ImagePanel` + `ToolController`), not the full `AppController`.
- [2026-08-10] Tool-output tests — **pixel goldens preferred**. Accepted workflow when output
  changes trivially: visually confirm the new `*_tested.png`, then replace the committed golden.
- [2026-08-10] `test-wip/` is an **outline only** (class names + docstrings, zero test logic);
  existing tests are imported, not replaced.
- [2026-08-10] (from testing_strategy.md, A1) **CI-time culprit verified:**
  `geometry_utils_test.test_transform_parameters` is a single brute-forced sweep of ~1.1M
  `QTransform` iterations (2×6×6×8×8×240) — it *is* the ~4-min run. **Reshape** to a coarse grid +
  explicit adversarial table, dense fuzz behind `@pytest.mark.slow`. This is the first CI action,
  done before adding coverage so nothing inherits the 4-min floor. (Reshape is a perf change, not a
  coverage redesign — coverage stays ADEQUATE.)
- [2026-08-10] **Build infra before breadth:** three shared pieces gate all new tests and are built
  first — `IntraPaintTestCase` base (singleton reset in `setUp`+`tearDown`), `assert_image_matches_golden`
  helper (writes `*_tested.png` on failure; the sole golden code path), and the light-combo tool
  harness. Then Tier 0 safety nets (undo / transform-state / selection-layer) *before* the UndoStack,
  A2, OQ4 refactors execute; known bugs encoded as `xfail(strict=True)`.
- [2026-08-10] **Flaky-Qt policy = prevent-by-construction, not quarantine.** Banned in tests:
  real event-loop waits (`qWait`/`processEvents` spin), wall-clock timing, live network/real backend
  (use `--mode mock`). No `@pytest.mark.flaky`-retry (a retried flake is a silenced detector); the
  only sanctioned markers are `skip(reason+issue)` and `xfail(strict=True)`. Global-state bleed is
  solved structurally by the resetting base fixture; `pytest-xdist` only *after* ordering-independence
  is proven.
- [2026-08-10] **No coverage-percentage gate** while coverage is being built out (it pressures
  low-value UI pixel tests to hit a number); revisit once Tiers 1–3 exist. Golden-image endian/format
  normalization (`Format_ARGB32`) is mandatory before pixel compare. Tier-4 API-client tests are
  **provisional pending OQ5** (the `intrapaint_api` swap) — write against the surviving surface or
  defer; effort may shrink to adapter tests since the library ships its own client tests.

## Generation-area / context-control UX (from generation_area_ux.md, OQ6)
- [2026-08-10] **Diagnosis:** context control is clunky because the generation **area** (image-space
  rect) and generation **resolution** (`GENERATION_SIZE`) are two independent values whose ratio (the
  scale factor — the whole point of the downscaling-for-detail workflow) is **never displayed** and is
  reconciled by hand via two "match" buttons that decay after every area edit. Compounded by: three
  overlapping size names — `EDIT_SIZE` is a **redundant bidirectional shadow** of the area size
  (image_stack.py:119-123, 352-353) yet `MIN_/MAX_EDIT_SIZE` are what clamp the area; controls
  **scattered** across the Gen-Area tool panel, SD panel, and selection panels (resolution +
  inpaint-full-res each duplicated); a **non-standard handle-less gizmo** (left=teleport top-left /
  right=resize-from-top-left-only, generation_area_tool.py:56-75); and **no preview** of the tensor
  the backend actually receives.
- [2026-08-10] **Direction (low-risk → structural):** P1 collapse the vocabulary to two names and
  demote/remove `EDIT_SIZE`; P2 a live **scale badge** (area→res + Nx factor, model-band color cue,
  aspect-mismatch flag); P3 replace the manual match buttons with an **aspect/size link toggle +
  model-aware resolution presets**; P4 a **handled bounding-box gizmo reusing A2's outline machinery**
  (the only OQ6 item gated on an upstream dep); P5 **promote the inpaint-full-res crop overlay to the
  main canvas** with directly-draggable padding (retire the 1px-dot trick as the only path); P6 the
  flagship **"model's-eye" WYSIWYG preview** driven by a **single shared crop+scale+fill function**
  that both the preview and the real request builders call (A6 single-source-of-truth — preview and
  actual can't diverge). Consolidate P2/P3/P5/P6 into one context surface; the SD panel references
  shared control widgets rather than duplicating them.
- [2026-08-10] **Scope:** model API unchanged except optional `EDIT_SIZE` removal + an additive
  `ImageStack.generation_input(...)` helper; no backend/undo/generator-selection changes. **Feeds OQ2**
  (the mouse scheme + triple naming are concrete editor-norm idiosyncrasies to cite, not re-derive).

## Responsive layout / small displays (from responsive_layout.md, OQ1)
- [2026-08-10] **Verified:** three *uncoordinated* responsive systems already exist — (a) draggable-
  tab redistribution across four boxes keyed on magic window-height thresholds (1200/1600,
  main_window.py:57-58, `_prepare_for_tab_box_open` overflow heuristic), (b) `ReactiveLayoutWidget`
  per-widget px-range mode-swap + visibility limits, (c) `ToolPanel` orientation flip. Keep all
  three (the four-box tab model is a genuine strength) — the fix is **coordinating** them, not
  replacing them.
- [2026-08-10] **Root cause = bottom-up min-size accumulation with no global budget.** Every panel
  declares its own min-size; they sum upward and nothing asserts the assembled UI fits a target W×H,
  so any added control can silently push the small-screen minimum past the available space
  (TODO.md:5). Secondary faults: uncoordinated hand-tuned thresholds; reactive modes **freeze
  silently on a range gap** (reactive_layout_widget.py:55-62 logs + keeps last mode); screen size
  trusted as a hard sizing input yet unreliable (`availableGeometry` misses OS toolbars — the app
  both fills-on-launch, app_controller.py:275-281, *and* clamps-on-move, main_window.py:503-515 →
  off-screen overflow + the monitor-move glitch TODO.md:18); no DPI awareness (fixed 10pt font);
  overflow clips instead of scrolling.
- [2026-08-10] **Direction:** replace bottom-up accumulation with a **top-down space budget** and make
  *"usable at target-minimum size N"* an **enforced, testable invariant**. Phased (low→structural):
  **P1** make `ReactiveLayoutWidget` fall back to the nearest mode instead of freezing + require a
  default mode; add a window size-sweep characterization test (asserts `minimumSizeHint ≤ budget`, no
  "no mode in range", every reactive widget resolves a mode) built on A1's base; stop auto-filling the
  screen on launch. **P2** pick a real target-min (confirm with maintainer, ~1024×600) and audit/cap
  every min-size hint to fit it. **P3** universal scroll fallback so overflow is survivable; debounce
  the move→clamp→re-layout cascade + allow a manual usable-area override for bad `availableGeometry`.
  **P4** unify (a)+(b) under one coordinator driven by measured child min-sizes (not magic px); DPI-
  normalized thresholds + an "auto" font default from `logicalDotsPerInch`. UI-only; no model/undo/
  generator/config-schema changes (one additive font-mode option + a couple Cache keys is the
  ceiling). Strong synergy with OQ6 (its gen-area control consolidation relieves the min-size budget);
  R7 depends on A1 test infra; feeds OQ2 (fixed font / off-screen clipping / four-box tabs =
  editor-norm idiosyncrasies).

## Scope / boundaries
- [2026-08-10] `src/glid_3_xl/` + GLID generators/server — **legacy, don't touch** unless actively
  broken (per CLAUDE.md).
- [2026-08-10] Vendored/symlinked root dirs (`latent-diffusion`, `taming-transformers`,
  `pyspacenav`, `lib`, `colabFiles`) — not app source; don't modify.
- [2026-08-10] Git — **no commits/pushes/PRs unless explicitly asked**; the maintainer inspects
  every diff. Changes reach `master` only via PR immediately before a release; side branches are
  experiments to ignore.

## API library swap (from api_library_swap.md, OQ5)
- [2026-08-10] **Replace `src/api` with the `intrapaint_api` standalone library — yes.** The library
  is a decoupled extraction of `src/api` (shared git ancestry) that removed the two couplings making
  `src/api` awkward: **no Qt** (QImage→PIL, QSize→`Size`) and **no hidden config** (Cache/AppConfig
  reads → explicit pydantic params). Method surfaces are near-identical supersets.
- [2026-08-10] Migration shape — **direct rebind + thin IntraPaint-side adapters, NOT a
  compatibility shim.** Add: a `params_adapter` (Cache→pydantic, the bulk of the work), image adapter
  (QImage↔PIL), a main-thread-marshalling `credentials_provider` (replaces the in-`src/api`
  `LoginModal` — fixes an existing `src/api`→`src/ui` violation), and a progress bridge. Delete the
  `src/api` backend-client tree; **relocate** `control_parameter.py` (a Qt widget) into `src/ui` as a
  widget factory built from the library's pydantic `ParameterDef` (do this with A4's Config/Parameter→UI
  inversion). Only six files outside `src/api` consume it.
- [2026-08-10] Async reconciliation — the library's `GenerationHandle` slots into the existing
  `AsyncTask` envelope: run `handle.wait(on_progress=…)` **inside** the worker; `on_progress` emits
  the existing main-affinity `status_signal`; results marshal via the existing
  `QTimer.singleShot`/`_cache_generated_image` path. Net *less* concurrency code (deletes
  `_repeated_progress_check`); no off-main model/UI mutation. Honors `concurrency_model.md` §5.
- [2026-08-10] **Backend strategy CONFIRMED:** standardize on `intrapaint_api` with **ComfyUI as
  primary** (migrate first). "Downgrade A1111/Forge" = don't build new A1111-specific IntraPaint code
  — the library already gives WebUI ComfyUI-parity cancellation for free via its client-side dispatch
  queue, so keep A1111 working at no marginal cost. GLID stays legacy/untouched.
- [2026-08-10] Library-side asks (separate repo — proposals): add packaging (`pyproject.toml`) + a
  curated public API export, an optional "run on caller thread" WebUI mode, and finish the flagged
  in-progress paths (ComfyUI node pydantic migration, tiled/ultimate upscaling) before IntraPaint
  deletes those `src/api` equivalents.

## Direction hints (not yet firm decisions — treat as leanings)
- ComfyUI-default / A1111-downgrade — **now confirmed** (see API library swap above); this hint is
  superseded.
- A WIP standalone API wrapper at `../sd-api-standalone` — **decision made** to adopt it (above).
</content>
