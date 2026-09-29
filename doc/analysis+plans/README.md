# Analysis + Plans
Claude-generated advice for possible improvements, added features, code cleanup, and other sub-projects

These are preliminary recommendations from an earlier model, mostly written without running the code. Verify a
claim before acting on it, and override a recommendation when the evidence points elsewhere. Known corrections are
recorded in _decisions_ledger.md.

Shared substrate (read these first):
- _codebase_map.md: Orientation map — subsystems, gravitational centers, cross-cutting patterns, where to start reading per topic.
- _decisions_ledger.md: Dated record of the reports' calls, so reports don't duplicate or contradict each other, with corrections where later work overturned one.
- _execution_plan.md: End-to-end plan for answering the open questions — sequence, dependencies, and optional context/model tactics.
- briefs/: Paste-ready prompts for delegating not-yet-written reports to fresh sessions/agents (e.g. briefs/api_library_swap.brief.md for OQ5).

Reports:
- architecture_review.md: Umbrella software-architecture assessment — what's good, what's ill-advised, deviations from normal practice, prioritized fixes.
- concurrency_model.md: Threading/async audit (A5) — the one-thread discipline, a confirmed Config.set deadlock, and why the undo migration isn't gated on it.
- config_system.md: Config architecture evaluation (A4) — keep the data-driven model; fix the model→UI inversion, the reflection callbacks (→ Qt signals), key exclusivity, and non-atomic writes.
- rendering_pipeline.md: Rendering/compositing audit (A6) — the view shows the model's single composite (keep QGraphicsView); the real fix is region-aware/tiled compositing (substrate for OQ4 & A2).
- api_library_swap.md: `src/api` → `intrapaint_api` migration (OQ5) — swap is clean; the library is a decoupled (no-Qt, no-config) extraction of `src/api`. Direct rebind + thin adapters; ComfyUI confirmed primary. Unblocks OQ3.
- selection_layer_perf.md: Selection-layer bitmap efficiency (OQ4) — the 1-bit mask is stored as full-size 32-bit ARGB and its (never-displayed) pixmap is rebuilt per edit. Staged fix: Alpha8 + drop phantom pixmap → tiled binary mask + QRegion. Independent of R1; reuses its tiling.
- transform_tool_redesign.md: Transform tool shared-state (A2) — three state holders and a lossy origin-dependent decomposition as the hub cause the center-of-rotation and canvas↔panel sync bugs. Fix: one authoritative TransformState + presenter (sole writer) + views-emit-intents + first-class pivot + one-directional matrix projection + per-gesture undo macro.
- backend_autoinstall.md: Push-button backend install (OQ3) — IntraPaint is client-only today. Strategy: a ComfyUI-only provisioner that detects-and-reuses existing installs first (zero download), owns a managed-instance lifecycle, and drives comfy-cli + a Windows-portable fast-path for fresh installs. Obeys the AsyncTask discipline; hands packaging to A7.
- UndoStack.md: Feasability and strategies for replacing the hand-rolled UndoStack with Qt's QUndoStack.
- generation_area_ux.md: Generation-area / context-control UX (OQ6) — the area↔resolution scale
  relationship is invisible and hand-reconciled, size vocabulary is triplicated (`EDIT_SIZE` is a
  redundant shadow), controls are scattered, the gizmo is handle-less, and there's no preview of the
  backend's actual input. Fix: two names, a live scale badge + link/presets, one consolidated context
  surface, a canvas-level inpaint-crop overlay, A2's handled gizmo, and a shared-code "model's-eye"
  preview.
- responsive_layout.md: Responsive layout / small displays (OQ1) — three uncoordinated responsive
  systems already exist (four-box draggable tabs, per-widget mode-swap, orientation flip); the real
  bug is bottom-up min-size accumulation with no global budget, so any added control can silently
  break small screens. Fix: a top-down space budget + a testable "usable at target-min N" invariant;
  phased P1 reactive gap-fallback + size-sweep test → P2 enforce the budget → P3 scroll fallback +
  screen-detection hardening → P4 unify the systems + DPI awareness.
- testing_strategy.md: Long-term testing strategy (A1/OQ8) — coverage priorities (ratifies the test-wip tiers, promotes undo/transform/selection safety-nets to the front), the shared base-fixture + golden-helper + tool-harness infra to build first, the golden re-bless workflow, a prevent-by-construction flaky-Qt policy, and CI economics (the one geometry test is the ~4-min hog; reshape it before adding coverage).
