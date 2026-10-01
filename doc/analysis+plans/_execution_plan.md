# Execution plan — answering the open questions

Living coordination doc for the analysis/plan reports. Sequences the work, records
dependencies, and notes *optional* context-management moves (branch / reset / smaller model).

**These context tricks are optimizations, not requirements.** The simplest valid path is: do the
reports one at a time, each in a fresh session that first reads `_codebase_map.md` +
`_decisions_ledger.md` + any prior report it depends on, and write the result to a file. The
branch/reset/model notes below just make that cheaper. Because **every report is a durable file**,
context lives on disk — resetting between reports loses almost nothing.

Legend: **Executor** = warm (fork the session holding architecture context) / cold (fresh
session + brief) / here (the current context-rich session). **Model** = Opus (judgment-heavy) /
Sonnet (survey-heavy).

---

## Question inventory

IDs: `OQ#` = lines in `open_questions.txt`; `A#` = suggested additions (adopt as desired).

| ID | Topic | Status | Depends on | Executor | Model | Output file |
|----|-------|--------|-----------|----------|-------|-------------|
| OQ7 | Architecture review | **DONE** | — | here | Opus | architecture_review.md |
| — | Undo → QUndoStack (sub-project) | planned | ~~A5~~ (see note) | — | Opus | UndoStack.md (done) |
| A5 | Concurrency / threading audit | **DONE** | OQ7 | here | Opus | concurrency_model.md |
| A4 | Config system evaluation | **DONE** | OQ7 | here | Opus | config_system.md |
| A6 | Rendering pipeline & compositing | **DONE** | OQ7 | here | Opus | rendering_pipeline.md |
| OQ5 | src/api → ../sd-api-standalone | **DONE** | OQ7 | here | Opus | api_library_swap.md |
| OQ4 | Selection-layer bitmap efficiency | **DONE** | A6 | here | Opus | selection_layer_perf.md |
| A2 | Transform tool + panel redesign | **DONE** | A6 (loose) | here | Opus | transform_tool_redesign.md |
| OQ3 | Backend auto-install (push-button) | **DONE** | OQ5 (done) | here | Opus | backend_autoinstall.md |
| A1 | Testing strategy | **DONE** | OQ7; refs A4 | here | Opus | testing_strategy.md |
| OQ6 | Generation-area / context-control UX | **DONE** | — (reads doc/) | here | Opus | generation_area_ux.md |
| OQ1 | Responsive layout / small displays | **DONE** | — | here | Opus | responsive_layout.md |
| A3 | Non-destructive layer persistence | **DONE** | — | cold | Opus | nondestructive_layers.md |
| A7 | Cross-platform packaging & native deps | todo | — | cold | **Sonnet** | packaging.md |
| A8 | Color management subsystem | todo | — | cold | **Sonnet** | color_subsystem.md |
| OQ2 | Editor-norm idiosyncrasies (synthesis) | todo | OQ1, OQ6, A8, OQ7 | cold | Opus | editor_norms.md |

\* OQ5 leans on the external `../sd-api-standalone` repo more than on this session's context, so a
cold session + brief + repo access is fine; warm isn't needed.

Folded (don't make standalone unless you want to): backend-strategy/ComfyUI-default → into **OQ5**;
PySide6 forward-compat sweep → covered in **OQ7 §3.6**, or spin out as a tiny Sonnet task.

## Dependency graph

```
OQ7 (done)
 ├── A5 concurrency ──────────► Undo/QUndoStack execution (main-thread rule)
 ├── A4 config
 ├── A6 rendering ──┬─► OQ4 selection-perf
 │                  └─► A2 transform-tool
 └── OQ5 api-swap ──► OQ3 backend-autoinstall

Independent (no upstream): OQ6, OQ1, A3, A7, A8, A1(refs A4)

OQ2 (synthesis) ◄── OQ1, OQ6, A8, OQ7   (do last)
```

## Phased sequence

### Phase 0 — Substrate ✅ DONE
`_codebase_map.md`, `_decisions_ledger.md`, `architecture_review.md`. Everything below cites these.

### Phase 1 — Coupled architecture cluster (do next, WARM)
`A5`, `A4`, `A6` (+ `OQ5` in parallel). These take detail from the umbrella and are the
dependency root for Phase 2. Best done **warm** (fork this session) so they inherit the
architecture context instead of re-deriving it — all Opus.
- Suggested internal order: **A5 → A4 → A6** (A5 is the prerequisite for the undo migration and
  governs everything that mutates the model; A4 is independent of A5 so A4∥A5 is fine; A6 unblocks
  the most Phase-2 work, so if you want Phase 2 sooner, promote A6 first).
- `OQ5` can run any time in this phase as a **cold** task (needs the external repo, not this
  context).
- **After Phase 1, the warm context is spent** — its value was the architecture cluster. From here
  on, cold sessions reading the committed docs are as good as warm.

### Phase 2 — Depends on Phase 1 (COLD, seeded with the relevant Phase-1 report)
- `OQ4` (needs A6's position on large-image perf/compositing).
- `A2` (benefits from A6's graphics-item lifecycle view).
- `OQ3` (needs OQ5's backend direction).
- Undo/QUndoStack **execution** (not a report) unblocks once A5 lands.

### Phase 3 — Independent reports (COLD, parallelizable, model-mixed)
Run any time after Phase 0; no cross-dependencies, so ideal for batching and for a **context reset
per report**. Keep batches small (2–3) to stay limit-friendly.
- `A1` testing — Opus, or Sonnet-draft/Opus-review (test-wip is on disk). Can start now.
- `OQ6` gen-area UX — Opus (design judgment); reads `doc/` workflow docs.
- `OQ1` responsive layout — Opus (genuinely tricky).
- `A3` non-destructive layers — Opus; touches open_raster + text_layer.
- `A7` packaging — **Sonnet** (survey/catalogue of specs + native deps).
- `A8` color subsystem — **Sonnet** draft, optional Opus polish.

### Phase 4 — Synthesis (LAST, COLD)
- `OQ2` editor-norm idiosyncrasies. Reads OQ1, OQ6, A8, and OQ7's deviations section, then
  synthesizes a norm-conformance report + implementation sketches. Do it last so it can cite the
  others rather than duplicate them.

## Context-management cheat-sheet (optional)

- **Branch/fork points:** fork the architecture-holding session **once per Phase-1 report** (A5,
  A4, A6). Nothing after Phase 1 needs a fork — cold + docs suffices.
- **Reset points:** reset (or new session) freely **after any committed report**, and especially
  before Phase 3/4 (independent work shouldn't carry Phase 1/2 context). The map+ledger+target
  report's dependencies are the only context a fresh report needs.
- **Model-switch points:** drop to **Sonnet** for `A7` (packaging) and `A8` (color), and the
  optional PySide6 sweep — bounded survey/catalogue work. Everything else stays Opus because a
  wrong architectural/UX call is costly and hard to detect. `A1` (testing) is the one genuine
  toss-up (Sonnet-draft/Opus-review is reasonable since `test-wip/` already scaffolds it).
- **Durability rule (applies always):** every agent/session writes its report to its output file
  directly and treats "file committed" as done — don't rely on relaying long output back through a
  parent, which is lossy if the parent is reset or hits a limit.

## Where to start executing early

Phase 1 is both the dependency root and the part that most benefits from *this* session's warm
context — so it's the natural place to begin now, before any reset. Recommended first report:
**A5 (concurrency)**, because it gates the undo migration and underpins every model-mutation path,
or **A6 (rendering)** if the priority is unblocking the most Phase-2 work soonest.

## Status log
- 2026-08-10: Phase 0 complete (map, ledger, architecture review). Plan created.
- 2026-08-10: A5 (concurrency) complete → concurrency_model.md. Key result: AsyncTask handlers run
  on the main thread (verified), so **A5→undo is no longer a hard gate** — the undo/QUndoStack work
  can proceed in parallel. Confirmed off-main deadlock in `Config.set` (F1). spacenav confirmed
  known-broken; its threading bug (F3) parked. Remaining Phase 1: A4 (config), A6 (rendering),
  OQ5 (api-swap).
- 2026-08-10: A4 (config) complete → config_system.md. Resolved the open config_from_key question
  (enforce exclusivity via a shared key registry). Keystone recommendation: per-entry Qt signals
  (also fixes A5 F2 + arch §3.4). Flagged a model→UI dependency inversion (config.py & util/parameter.py
  import ui/input_fields). Remaining Phase 1: A6 (rendering), OQ5 (api-swap).
- 2026-08-10: A6 (rendering) complete → rendering_pipeline.md. Correction to arch §5: on-screen =
  the model's single authoritative composite (scene has only 2 items), no per-layer compositing / no
  divergence. Keep QGraphicsView. Real issue = whole-image recomposite per edit (R1) → the shared
  substrate OQ4 and A2 must build on. Partial-alpha glitch is a model/cache bug, not QGraphicsView
  (R2, needs repro). **Phase 1 nearly done — only OQ5 (api-swap) remains, and it's a cold task
  (needs ../sd-api-standalone), so the warm run can stop here.**
- 2026-08-10: OQ5 brief written → briefs/api_library_swap.brief.md. Confirmed the library exists
  (../sd-api-standalone, separate git repo, package `intrapaint_api`, has A1111+ComfyUI tests and a
  "backend-agnostic async generation handle"). Ready for a cold Opus session with access to both
  repos. Warm Phase-1 run ends here.
- 2026-08-10: OQ5 (api-swap) complete → api_library_swap.md. Verdict: swap is feasible and desirable
  — the library is a decoupled extraction of `src/api` (near-identical superset surface) that removed
  Qt + hidden-config. Biggest work item = a Cache→pydantic `params_adapter`; only two genuine gaps
  (that adapter + relocating the Qt `control_parameter` widget). Async reconciles cleanly inside the
  existing `AsyncTask` envelope (deletes `_repeated_progress_check`). **Backend strategy confirmed:
  ComfyUI-primary.** Decision recorded in `_decisions_ledger.md`. **OQ3 (backend auto-install) is now
  unblocked** — it should target provisioning ComfyUI + `intrapaint_api`. Phase 1 fully complete.
- 2026-08-10: OQ4 (selection-layer perf) complete → selection_layer_perf.md. Key findings: the
  selection is truly 1-bit but stored as full-size 32-bit ARGB (32× overhead); its pixmap is never
  displayed (opacity-0 item, outline is the visible product); and it's decoupled from the group
  composite, so **OQ4 is independent of R1 and can land first**. Recommended staged fix: Stage 1
  (drop phantom pixmap, Alpha8, bound whole-image passes) → Stage 2 (tiled binary mask on R1's grid +
  QRegion geometry/outlines). Reuses R1's tiling; preserves the public API. Recorded in ledger.
- 2026-08-10: A2 (transform tool) complete → transform_tool_redesign.md. Diagnosis: three state
  holders (model matrix / TransformOutline hub / panel) with no single source of truth; the hub
  round-trips the matrix through a lossy, origin-dependent decomposition every event, and moving the
  rotation origin re-decomposes it — the root of the center-of-rotation and canvas↔panel bugs. Found
  a live bug (layer_height getter returns the width box). Direction: one authoritative TransformState
  + presenter (sole writer) + views-emit-intents + first-class pivot + one-directional matrix
  projection + per-gesture undo macro + live-preview commit. Contained to the tool+outline+panel
  triad; model API and geometry helpers unchanged. Recorded in ledger. Remaining Phase 2: OQ3
  (backend auto-install, unblocked by OQ5).
- 2026-08-10: OQ3 (backend auto-install) complete → backend_autoinstall.md. Verified IntraPaint is
  client-only (no launch/install code). Reframed the barrier as configuration (cheap) vs install-from-
  zero (hard), and recommended a ComfyUI-only pluggable provisioner: detect-and-reuse existing installs
  first (zero download), a ManagedComfyUI lifecycle (spawn + health-check via existing get_system_stats
  + auto-launch branch), and fresh-install engines driving official comfy-cli + a Windows-portable
  fast-path; honest model story. Obeys AsyncTask main-thread discipline; one setup-window button + one
  configure_or_connect branch. Consumes OQ5's ComfyUI-primary call; **creates an A7 (packaging)
  dependency** (bundled builds lack a user Python → portable engine default). **Phase 2 complete**
  (OQ4, A2, OQ3 all done). Remaining: Phase 3 independents (A1, OQ6, OQ1, A3, A7, A8) + Phase 4
  synthesis (OQ2).
- 2026-08-10: A1 (testing strategy) complete → testing_strategy.md. Ratifies the test-wip/ tier
  order as the coverage roadmap and adds an imminent-regression-risk multiplier: promotes undo /
  transform-state / selection-layer characterization tests to a "Tier 0" front, so they exist as
  safety nets *before* the UndoStack, A2, and OQ4 refactors execute (encode the known bugs as
  xfail(strict=True)). Three shared infra pieces to build first: an IntraPaintTestCase base
  (singleton reset in setUp/tearDown), a golden-image helper (writes *_tested.png on failure, one
  code path for the re-bless workflow), and the light-combo tool harness (per ledger, not
  AppController). **Verified the CI-time culprit:** geometry_utils_test's single
  test_transform_parameters runs ~1.1M QTransform iterations (2×6×6×8×8×240) — reshape to coarse
  sweep + adversarial table (dense fuzz behind @pytest.mark.slow) drops the ~4-min run to seconds
  *before* adding coverage. Flaky-Qt policy = prevent-by-construction (ban event-loop/wall-clock
  waits + live network; reset singletons structurally); xdist only after ordering-independence
  lands. Tier-4 API tests flagged provisional pending OQ5 (intrapaint_api swap). Remaining Phase 3:
  OQ6, OQ1, A3, A7, A8; Phase 4: OQ2.
- 2026-08-10: OQ6 (generation-area / context-control UX) complete → generation_area_ux.md. Root
  cause: area and resolution are two independent rectangles reconciled by hand ("match" buttons that
  decay), the ratio (scale factor) is never shown, three overlapping size names exist (`EDIT_SIZE` is
  a redundant bidirectional shadow of the area size), controls scatter across the tool/SD/selection
  panels (resolution + inpaint-full-res each duplicated), the on-canvas gizmo is handle-less and
  non-standard (left=teleport / right=resize-from-top-left, generation_area_tool.py:56-75), and
  there's no preview of what the backend actually receives. Proposal (low→structural): P1 collapse to
  two names / demote EDIT_SIZE; P2 live scale badge; P3 link-toggle + resolution presets replacing the
  match buttons; P4 handled gizmo **reusing A2's outline** (only OQ6 item with an upstream dep); P5
  promote the inpaint-full-res crop overlay to the main canvas with draggable padding; P6 flagship
  "model's-eye" WYSIWYG preview driven by a **single shared crop+scale+fill function** (A6
  single-source-of-truth) so preview/actual can't diverge. Feeds OQ2 (idiosyncrasies). Remaining
  Phase 3: OQ1, A3, A7, A8; Phase 4: OQ2.
- 2026-08-10: OQ1 (responsive layout / small displays) complete → responsive_layout.md. Verified
  three uncoordinated responsive systems already exist: (a) tab redistribution across four boxes on
  magic height thresholds (1200/1600, main_window.py:57-58), (b) ReactiveLayoutWidget per-widget
  px-range mode-swap, (c) ToolPanel orientation flip. Root cause = **bottom-up min-size accumulation
  with no global budget** (nothing asserts the assembled UI fits W×H, so any added control silently
  blows the small-screen floor — #13), compounded by uncoordinated hand-tuned thresholds,
  reactive modes that **freeze silently on a range gap** (reactive_layout_widget.py:55-62),
  screen-size trusted as a hard input yet unreliable (availableGeometry misses OS toolbars; app both
  fills-on-launch and clamps-on-move → off-screen overflow + the monitor-move glitch), no DPI
  awareness (fixed 10pt font), and clip-not-scroll overflow. Direction: **top-down space budget** +
  make "usable at target-min N" an enforced, testable invariant. Phased: P1 reactive gap-fallback +
  size-sweep test harness + stop auto-filling screen; P2 pick+enforce the min-size budget (audit
  min-size hints); P3 universal scroll fallback + debounce/defensive screen detection; P4 unify the
  two systems + DPI-normalized thresholds/auto font. Strong synergy with OQ6 (gen-area panels are top
  min-size hogs) and A1 (R7 test harness). Feeds OQ2. Remaining Phase 3: A3, A7, A8; Phase 4: OQ2.
</content>
