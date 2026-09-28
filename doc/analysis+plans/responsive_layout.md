# Responsive layout / small displays (OQ1)

**Question (open_questions.txt:1):** Layout issues are a persistent hassle and making everything fit
cleanly on small displays is challenging. How should this be addressed at application scope?

**Substrate:** `_codebase_map.md` §2/§7, `_decisions_ledger.md`. Cross-refs: OQ6
(`generation_area_ux.md` — the gen-area controls are among the worst space hogs), A1
(`testing_strategy.md` — responsive layout has almost no tests), OQ7 (`architecture_review.md`).
Feeds OQ2 (fixed-point font, off-screen clipping, and no auto-scaling are concrete editor-norm
deviations).

**Scope:** UI-only. No model / undo / generator / config-schema changes are required by the core
fix (one additive font-mode option and a couple of new Cache keys are the ceiling). GLID windows
untouched.

---

## 1. What exists today (verified)

IntraPaint already has *three* separate responsive mechanisms. The problem is not their absence —
it's that they're uncoordinated, locally-tuned, and driven bottom-up instead of by a shared space
budget.

**(a) Tab redistribution across four boxes (`ui/window/main_window.py`).** The window is a
`QVBoxLayout` of: top tab box → image panel (with its own left/right tab boxes) → lower tab box →
bottom tab box, dividers between (main_window.py:184-202). Tool / generator / controlnet panels live
in draggable `Tab`s that the user (or the app) moves between boxes. Default placement of a new tab
is chosen by **window height against two magic thresholds** — `AUTO_TAB_MOVE_THRESHOLD = 1200`,
`USE_LOWER_CONTROL_TAB_THRESHOLD = 1600` (main_window.py:57-58, `add_tab` 337-342). Opening a box
runs `_prepare_for_tab_box_open` (426-501), a ~75-line heuristic that sums `sizeHint()`s of the
perpendicular/parallel boxes plus a reserved `size // 6` for the image view and force-closes other
boxes if the arithmetic says the window would overflow.

**(b) Per-widget mode-swap (`ui/layout/reactive_layout_widget.py`).** `ReactiveLayoutWidget` holds a
list of named layout "modes," each with a `(min_size, max_size)` **pixel** range; on resize it picks
the mode whose range contains the current size and re-runs that mode's `setup()` closure. It also has
per-child `visibility_limit`s (hide a child below a min size). Used by `ToolPanel` (tool-label
visibility, tool-control box) and `layer_transform_tool_panel.py` (wide/extra-wide/tall/extra-tall
matrix, panel:212-280).

**(c) Panel orientation flip.** `ToolPanel.set_orientation` (tool_panel.py:155) rebuilds itself
horizontal↔vertical (`QHBoxLayout`↔`QVBoxLayout`) depending on which tab box holds it, re-flowing the
tool-button grid (8×2 vs 2×8, `_build_tool_button_layout` 192-226).

**(d) Screen fitting.** `display_size.get_screen_bounds` returns `screen.availableGeometry()` for the
display the window most overlaps (display_size.py:11-37). On launch the window is sized to **fill the
whole available screen** (`app_controller.py:275-281`), and every move/resize clamps the window back
inside the screen (`_size_and_bounds_updates`, main_window.py:503-515).

**(e) Font.** A single global `AppConfig.FONT_POINT_SIZE` (default **10**, definitions:22-28) applied
app-wide (`app_controller.py:412-418`). Fixed value, user-tuned, "may require restart." No DPI-based
default.

---

## 2. Root causes of the fragility

### C1 — Bottom-up min-size accumulation with no global budget *(the core problem)*
Every panel and control declares its own `minimumSizeHint` / `setMinimumSize` (a dozen call sites,
plus everything inheriting Qt defaults). Those minimums sum upward through the nested layouts
(`tab_box.minimum_active_size` explicitly adds content + chrome, tab_box.py:81-97). The window sets
`setMinimumSize(0, 0)` (main_window.py:143) but the *effective* floor is whatever the child tree
demands. **Nothing anywhere asserts "the whole assembled UI fits in W×H."** The reactive modes and
tab heuristics each try to shrink *locally*, but no authority guarantees the sum fits the screen.
This is exactly the maintainer's report: *"too many conditions where a UI tweak still pushes minimum
window size beyond the available space"* (TODO.md:5) — adding one control anywhere can silently blow
the small-screen budget, and no test or invariant catches it.

### C2 — Two uncoordinated responsive systems with hand-tuned magic thresholds
Mechanism (a) keys off **window height in raw px** (1200 / 1600); mechanism (b) keys off **each
widget's own px ranges**. Neither knows about the other, and neither is driven by "does the whole
thing currently fit." Both sets of numbers were tuned on the developer's displays. On an off-nominal
size you can land in a combination neither anticipated — e.g. tabs auto-placed for a "tall" window
while a child panel is stuck in its widest mode.

### C3 — Reactive modes fail silently on gaps, and freeze
`add_layout_mode` *raises* if two ranges overlap (reactive_layout_widget.py:37-40), forcing exhaustive
hand-maintained coverage. Worse, if a size falls in a **gap** between ranges and no default mode is
registered, `resizeEvent` logs `"no layout mode in range"` and **does nothing** — the widget stays
frozen in whatever mode it last applied (reactive_layout_widget.py:55-62). So a window size between
two panels' bands = wrong layout, no recovery. (The `sizeHint()` → `QSize()` null-return hack at
line 25-27 exists specifically to stop Qt from blocking these transitions — a symptom of fighting the
layout engine rather than working with it.)

### C4 — Screen-size detection is trusted as a hard input, and is unreliable
`availableGeometry()` *should* exclude taskbars/docks, but the maintainer reports it *"can't tell when
there's an OS toolbar blocking screen real estate in many circumstances"* (TODO.md:5) — global menu
bars, autohide docks, Wayland, fractional/multi-monitor scaling all defeat it. Because the app both
**fills** the screen on launch (app_controller.py:275-281) and **clamps** to it on every move
(main_window.py:503-515), a wrong reading directly produces a window larger than the usable area — and
with the C1 min-size floor unable to yield, controls get pushed off-screen instead of shrinking. The
"weird resize glitch when moving between monitors" (TODO.md:18) is this interacting with the
orientation flip (c): a move fires `moveEvent`→clamp→resize→re-layout→orientation change→resize…, an
un-debounced cascade.

### C5 — No DPI / physical-size awareness
All decisions are in raw device-independent pixels and a fixed font point size. A physically tiny
high-DPI laptop panel and a large low-DPI monitor with the same pixel count are treated identically,
so the px thresholds mis-classify real usable area. Nothing consults `logicalDotsPerInch` or physical
screen size.

### C6 — Overflow degrades by clipping, not scrolling
Only a few containers wrap content in a `QScrollArea` (`tool_panel`, `settings_modal`, `layer_panel`,
`text_tool_panel`, `extra_network_window`). Elsewhere, when min-size > available space the window
clamps down but children don't yield → dividers become unreachable, controls clip. There's no
universal "when short on space, scroll" fallback, so the failure mode is *broken* rather than
*cramped-but-usable*.

---

## 3. Direction

**Reframe:** replace *bottom-up min-size accumulation + scattered local heuristics* with a **top-down
space budget**, and make **"the UI is usable at target minimum size N" an enforced, testable
invariant** rather than an emergent hope. Small-display support becomes a property you can regression-
test, not a whack-a-mole.

### R1 — Pick a real target-minimum size and make everything fit it by construction *(keystone)*
Choose an explicit budget — the old laptop's usable resolution, e.g. **1024×600** (confirm the actual
target with the maintainer). Then audit every `setMinimumSize`/`minimumSizeHint` (the call sites in
§1 + Qt defaults) and cap them so the fully-assembled window's `minimumSizeHint()` is **≤ the
budget**. Anything that genuinely can't shrink that far goes behind a scroll area (R2) or a collapse.
This is the direct fix for TODO.md:5 and the single highest-value structural move.

### R2 — Universal scroll fallback so overflow is always survivable
Ensure every panel / tab-box content area lives in a scroll area (extend the pattern `ToolPanel`
already uses for its control box). Then when space is short the user **scrolls** rather than the
window growing off-screen or content clipping. Combined with R1 this guarantees the app is *usable*
at the target min even when not comfortable — converting C6's broken state into a cramped-but-working
one.

### R3 — One responsive coordinator instead of two independent systems
Introduce a single responsive-layout owner observing the **actual central-widget size** that both
(a) drives tab distribution and (b) is the source ReactiveLayoutWidget consults — so the two
mechanisms share one notion of "what fits now." At minimum, **derive the thresholds from measured
child min-sizes** (`minimum_active_size` already exists on tab boxes) instead of the hard-coded
1200/1600 constants tuned to one monitor. This removes C2's mis-classification.

### R4 — Make ReactiveLayoutWidget robust to gaps *(cheap, high value)*
`resizeEvent` should fall back to the **nearest** mode (clamp the query size to the closest range)
rather than freezing and logging an error when nothing matches; and a default mode should be
*required*, not optional. Eliminates the C3 "stuck in the wrong layout" class outright with a few
lines.

### R5 — Stop treating screen size as a hard sizing input; harden and debounce
- On launch, **don't auto-fill the screen** (app_controller.py:275-281); prefer remembered bounds,
  else a sane default at/near the R1 budget. A window that starts maximized-to-a-bad-reading is the
  worst case.
- **Debounce** the move/resize→clamp→re-layout→orientation cascade (C4/TODO.md:18): react to
  `QWindow.screenChanged` / `QScreen.availableGeometryChanged` signals with coalescing, instead of
  recomputing inside every `moveEvent`.
- Treat a suspicious `availableGeometry` defensively (e.g. keep a manual "usable area" override in
  Cache for environments where detection is known-bad), rather than assuming it's correct.

### R6 — DPI / physical awareness for thresholds and font
Offer an **"auto" font default** derived from `logicalDotsPerInch` instead of a fixed 10pt, and
express the R3 thresholds in a **DPI-normalized unit** so usable *physical* area — not raw pixels —
classifies the display. This is the C5 fix and the deepest change; do it last.

### R7 — Make small-display support testable *(ties to A1)*
Responsive layout has "almost none" of the test coverage (testing_strategy.md, TODO.md:46), which is
why silent regressions (C1) survive. The offscreen platform makes this cheap. Add characterization
tests that instantiate the window across a **matrix of sizes** (including the R1 budget and just
above/below every reactive band) and assert:
1. `window.minimumSizeHint()` ≤ the target budget (guards C1 — *this* is the test that turns "a UI
   tweak silently broke small screens" into a red build);
2. no `"no layout mode in range"` error fires at any swept size (guards C3);
3. every `ReactiveLayoutWidget` resolves to a mode at every swept size;
4. the tab-open heuristic never leaves total min-size > window.

Build this on A1's `IntraPaintTestCase` base; it's a natural Tier-0 safety net to land **before** R1/R3
refactors touch the layout.

---

## 4. Prioritization (low-risk → structural)

| Phase | Items | Why here |
|---|---|---|
| **P1** | R4 (reactive gap fallback + required default) · R7 (size-sweep test harness) · R5(a) (don't auto-fill screen on launch) | Cheap, self-contained, and immediately stop the two silent-breakage classes; R7 gives the regression net every later phase leans on. |
| **P2** | R1 (pick + enforce the target-min budget; audit min-size hints) | The real fix for "min window size beyond available space." Bounded once R7 exists to verify it. |
| **P3** | R2 (universal scroll fallback) · R5(b/c) (debounce + defensive screen detection) | Makes overflow survivable and kills the monitor-move glitch. |
| **P4** | R3 (unify the two responsive systems) · R6 (DPI-normalized thresholds + auto font) | Largest blast radius; do last, on top of a tested, budgeted base. |

---

## 5. Interactions & boundaries

- **OQ6 synergy (strong):** the generation-area / SD panels are among the biggest min-size
  contributors, and OQ6 already proposes consolidating their scattered, duplicated controls into one
  context surface. That consolidation *directly* relieves C1's min-size pressure — sequence OQ6's P1
  (collapse duplicated controls) alongside R1's audit.
- **A1 dependency:** R7 builds on the shared test base; land that infra first.
- **Feeds OQ2:** the fixed-point font with no auto-scaling (C5/R6), the off-screen clipping instead
  of graceful degradation (C6/R2), and the non-standard four-box draggable-tab model are concrete
  editor-norm idiosyncrasies for OQ2 to cite rather than re-derive.
- **Out of scope:** no changes to the model, undo, generators, or the config schema beyond one
  additive font-mode option and a couple of Cache keys (usable-area override, R5c). The draggable
  four-box tab system is kept — it's a genuine strength; the fix is *coordinating* it, not replacing
  it.
