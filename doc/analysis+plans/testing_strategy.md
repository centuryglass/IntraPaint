# Testing strategy (A1 / OQ8)

Long-term testing strategy for IntraPaint: what to cover and in what order, the shared
fixture/base-class design, the golden-image maintenance workflow, how to keep Qt/UI tests from
going flaky, and how to keep CI time reasonable as coverage grows.

Reads: `_codebase_map.md` §6, `_decisions_ledger.md` (Testing section — settled calls), and
`test-wip/README.md` (the tier-ordered outline this report ratifies and refines). Cites but does not
duplicate them.

**Relationship to `test-wip/`:** the outline there is the *content plan* (which tests, in which
order); this report is the *strategy* around it (infrastructure, workflow, CI economics, flakiness
policy). They are meant to be read together — I adopt its tier ordering rather than re-derive one.

---

## 0. TL;DR

- **Adopt the `test-wip/` tier order as the coverage roadmap**, with two priority overrides driven
  by regression risk from the other reports: pull the **undo engine**, **transform math/state**, and
  **selection-layer invariants** to the very front, because A2/OQ4/UndoStack are all about to *change*
  those subsystems and the tests are the safety net that lets those refactors land.
- **Build the infrastructure before the tests.** Three shared pieces gate everything else and are
  currently copy-pasted per file: an `IntraPaintTestCase` base fixture, a golden-image assertion
  helper, and a lightweight tool-test harness. Write these first; every tier depends on them.
- **The single biggest CI win is not parallelism — it's `geometry_utils_test.py`.** One test
  (`test_transform_parameters`) runs ~1.1 million `QTransform` iterations and dominates the ~4 min
  run. Re-shape it (coarser sweep + a small explicit adversarial table) and total CI drops to well
  under a minute *before* any new tests are added. Do this first so new coverage doesn't inherit a
  4-minute floor.
- **Flakiness policy: forbid the usual Qt flake sources by construction** (no real event-loop waits,
  no wall-clock timing, no live network, deterministic `--mode mock`), rather than quarantining flaky
  tests after the fact.
- **Golden images: one helper, one committed-PNG-per-case convention, one documented "re-bless"
  ritual** (already the accepted workflow per the ledger — this report just makes it a single code
  path so it can't drift).

---

## 1. Where things stand (verified)

- **11 test files**, `unittest.TestCase` style, run headless via `pytest`. `conftest.py` forces
  `QT_QPA_PLATFORM=offscreen` before PySide6 imports and provides a session `QApplication`;
  `pytest.ini` scopes collection to `test/`, uses `-ra --strict-markers`.
- **CI** (`.github/workflows/test.yml`) runs the full suite on PRs to `master` and manual dispatch,
  on a **3.11 + 3.12 matrix**, Ubuntu, installing headless-Qt/libmypaint system libs and building the
  Cython extension ahead of time. No coverage gate, no parallelism, no test sharding.
- **Runtime is ~4 min, and it is almost entirely one test.** `test/util/geometry_utils_test.py`
  contains a single method whose six nested loops
  (`origin(2) × x_off(6) × y_off(6) × sx(8) × sy(8) × deg(240)`) enumerate ~1.1M matrices and run
  `extract`/`combine`/`transforms_approx_equal` on each. Everything else in the suite is fast.
- **Established patterns already in the tree** (don't reinvent):
  - Fixture idiom: `chdir` to project root → construct the config singletons from
    `test/resources/*_test.json` → `._reset()` each → `UndoStack().clear()` → build the unit under
    test. Copy-pasted into every `setUp`.
  - Golden-image idiom: render → save temp PNG → load committed golden → `assertEqual` → `os.remove`.
    Duplicated in `image_stack_test` and `brush_tool_test`.
  - Signal verification: `MagicMock` connected to the signal, then `assert_called*`.
  - Deterministic generation via `--mode mock` (`test_generator`).

These are good bones. The problem is **duplication** (no shared base) and **one pathological test**,
not the approach.

---

## 2. Coverage priorities

### 2.1 Guiding principle

Order by **(value of protected behavior) × (imminent regression risk) ÷ (cost to write)**. The
`test-wip/` tiers already encode value÷cost. This report adds the **imminent-regression-risk**
multiplier from the other analysis reports: the subsystems that A2, OQ4, and the UndoStack migration
are about to rewrite need their characterization tests *first*, because those tests are what make the
rewrites safe.

### 2.2 Priority overrides on top of the `test-wip/` tier order

Adopt Tiers 1–5 as written, with these promotions to the front (call it **Tier 0 — refactor safety
nets**):

| Test | Why promoted | Paired report |
|---|---|---|
| `undo_stack_test.py` | The UndoStack→QUndoStack migration replaces the engine behind a preserved public API. Characterization tests on the *current* public API are the migration's regression gate; they must exist and pass before and after. Also encodes the two known bugs being fixed (`max_undo` unwired, `undo_in_progress` sticking) as **currently-xfail → becomes-pass** markers. | UndoStack.md |
| `transform_layer_test.py` + a `TransformState`-level test | A2 introduces an authoritative `TransformState` + presenter and rewrites the decomposition hub. Lock down transformed-bounds math and the matrix↔state projection *before* the rewrite. The confirmed `layer_height`-returns-width bug (panel) gets a red test that the redesign turns green. | transform_tool_redesign.md |
| `selection_layer_test.py` | OQ4 changes the storage (ARGB→Alpha8→tiled) behind the same API. Tests must pin the **observable invariants** (1-bit thresholding, boolean/morphology results, outline geometry) so the storage swap is provably behavior-preserving. | selection_layer_perf.md |

Everything else follows the `test-wip/` tiers unchanged:

- **Tier 1** — core infra & data model (config, layer base/group, transform, selection, text,
  ORA round-trip). Highest ROI; every later tier reuses these fixtures.
- **Tier 2** — editing operations (tool controller + per-tool tests, filters, brush engines).
- **Tier 3** — utilities (pure functions; cheap, fast, high-confidence).
- **Tier 4** — generation backends & API clients (deterministic builders/serializers; no live
  server). **Note the moving target:** OQ5 replaces `src/api` with the `intrapaint_api` library, so
  Tier-4 tests for `api/comfyui`, `api/webui`, `api/controlnet` should be treated as **provisional**
  — write them against whichever surface will survive the swap, or defer until the swap lands so the
  effort isn't spent twice. The `test-wip/api/**` outlines already mirror the current `src/api` shape;
  re-point them at the library when OQ5 executes.
- **Tier 5** — UI widgets/panels/modals: **logic, not pixels**; do last; highest brittleness.

### 2.3 What *not* to invest in (per ledger)

`geometry_utils` and `image_fill` are **ADEQUATE** — don't redesign their coverage (but *do* re-shape
geometry's runtime, §5 — that's a performance change, not a coverage change). Don't build the full
`AppController` into tool tests; use the lighter combo harness (§4.3). `test-wip/` is an **outline
only** — fill it in, don't treat its stubs as passing tests.

---

## 3. Shared base-class / fixture design

Three shared pieces. Build them first (they are the "Tier 0 infrastructure" that even the safety-net
tests depend on), keep them in `test/` so both the existing suite and `test-wip/` migrations use one
code path.

### 3.1 `IntraPaintTestCase` (`test/base_test_case.py`)

Extracts the copy-pasted `setUp` boilerplate into one base. The dominant idiom becomes:

```python
class IntraPaintTestCase(unittest.TestCase):
    """Base for all IntraPaint tests: deterministic global state per test."""

    def setUp(self):
        os.chdir(PROJECT_ROOT)                      # config JSON paths are relative
        AppConfig(TEST_APP_CONFIG_PATH)._reset()    # construct-from-test-json + reset
        Cache(TEST_CACHE_PATH)._reset()
        KeyConfig(TEST_KEY_CONFIG_PATH)._reset()
        A1111Config(TEST_A1111_PATH)._reset()
        UndoStack().clear()
        AppStateTracker()._reset()                  # if it holds cross-test state

    def tearDown(self):
        UndoStack().clear()                         # ordering-independence, explicit

    # Helpers (thin, documented):
    def make_image_stack(self, size=DEFAULT) -> ImageStack: ...
    def make_mock_controller(self) -> AppController:   # --mode mock
        ...
```

Why this shape:
- **Singleton reset is the whole game.** Every `_decisions_ledger.md` decision about test isolation
  reduces to "the config/undo/state-tracker singletons carry state between tests." A base-class
  `setUp` *and* `tearDown` that reset them makes ordering-independence structural instead of relying
  on the next test's `setUp` to clean up the last test's mess.
- **`chdir` belongs here, once.** Config definition files load by relative path; forgetting the
  `chdir` is a classic "passes locally from repo root, fails in CI from elsewhere" trap.
- **Helpers, not inheritance trees.** Prefer `make_*` factory methods over deep subclassing so a test
  that needs a slightly different stack composes it rather than subclassing a variant base.

Migration: convert existing tests to the base opportunistically (they already do this by hand, so it's
a mechanical de-dup), and require it for all new tests.

### 3.2 Golden-image helper (`test/util/golden_image.py` or on the base)

One function replaces the save/load/compare/cleanup dance:

```python
def assert_image_matches_golden(self, actual: QImage, golden_path: str, *, tolerance=0):
    """Compare `actual` to the committed golden. On mismatch, write `<golden>_tested.png`
    next to the golden for eyeballing, then fail with a helpful message."""
```

Design points (this is also §6):
- **On failure, always drop a `*_tested.png` beside the golden** — this is what makes the "visually
  confirm then re-bless" workflow (ledger) a two-second diff instead of an archaeology dig.
- **Default `tolerance=0` (exact)**, matching the current `assertEqual`. Offer an opt-in perceptual
  tolerance (max per-channel delta or fraction-of-differing-pixels) *only* for cases with genuine
  cross-platform/Qt-version nondeterminism (antialiased text, some blends). Prefer exact; reach for
  tolerance only when a golden proves platform-fragile, and document why at the call site.
- **Comparison is on `QImage` bytes in a fixed format** (convert both to
  `Format_ARGB32` before compare) so endian/format drift can't cause spurious diffs.

### 3.3 Tool-test harness (`test/tools/_tool_harness.py`, outlined as `_tool_harness.md`)

Per ledger, the base for tool tests is the **lighter combo** (`ImageStack` +
`ImageViewer`/`ImagePanel` + `ToolController`), **not** a full `AppController`. Provide:

- A `ToolTestCase(IntraPaintTestCase)` that builds that combo in `setUp`.
- **Synthetic input helpers** that drive tools the way the app does — construct `QMouseEvent`/
  `QTabletEvent` and route them through the tool's handlers (or through `ToolController`), with
  scene↔widget coordinate mapping done by the real `ImageViewer` so tests exercise the true path.
  No `QTest.mouseClick` against a hidden offscreen widget (fragile); call the handler entry points
  with constructed events.
- A `paint_stroke(points)` convenience that emits press → N× move → release.
- Golden assertion wired to §3.2 for pixel-output tools.

This harness is the dependency for the entire Tier-2 block, so it's worth getting right once.

### 3.4 `conftest.py` additions

- Keep the offscreen force and session `QApplication` (already correct).
- Move the `QApplication.instance() or QApplication(sys.argv)` idiom fully into the session fixture so
  test modules stop constructing their own at import time.
- Add project-root to `sys.path` (already done) and expose `PROJECT_ROOT` / test-resource paths as
  importable constants so the base fixture and helpers share one definition.

---

## 4. Keeping CI time reasonable

Ordered by payoff. The first item alone is the difference between a 4-minute and a sub-minute suite.

### 4.1 Fix the geometry test (do this first, before adding any coverage)

`test_transform_parameters` is a **property test brute-forced as an exhaustive sweep** — ~1.1M
iterations to protect a decomposition function. It provides real value (it's the characterization
test for the exact `extract`/`combine` math A2 leans on) but is wildly over-sampled. Re-shape without
losing coverage:

1. **Coarsen the sweep** to a representative grid (e.g. `deg` step 15° not 1.5°, `sx/sy` step 1.0 not
   0.5). This drops iterations ~50–100× while still covering every sign/quadrant/mirror combination
   the branch logic cares about.
2. **Add a small explicit adversarial table** of the cases that actually stress the math — the
   sign-flip/mirror-equivalence boundaries the current code comments call out (both-negative,
   single-negative-with-angle≥180, near-singular, 0/90/180/270 exact). These are where bugs hide;
   pin them by hand so coarsening the sweep can't drop them.
3. Optionally mark the full dense sweep as a **`@pytest.mark.slow` fuzz test** excluded from default
   CI and run on-demand/nightly. Keep the fast coarse+table version as the always-on gate.

Result: the ~4-min hog becomes a few seconds; the property is still protected and the adversarial
boundaries are protected *better*.

### 4.2 Don't let new tests re-introduce a runtime floor

Two rules, enforced by convention + review:
- **No test may sweep >~10k iterations by default.** Parameter-space confidence comes from a coarse
  grid + adversarial table (the §4.1 pattern), with dense fuzzing behind `@pytest.mark.slow`.
- **Golden-image tests render the smallest image that demonstrates the behavior.** Compositing/blend
  correctness needs 64–256px canvases, not full-resolution goldens; small goldens are faster to
  render *and* faster to diff, and they keep the repo's committed-PNG weight down.

### 4.3 Prefer the light harness over `AppController`

Constructing a full `AppController` per test is the most expensive fixture in the suite (it wires the
whole app). The ledger already mandates the light combo for tool tests; extend that instinct
generally — only `app_controller_test.py` and genuine integration tests should pay for the full
controller.

### 4.4 Parallelism — later, and cautiously

`pytest-xdist` (`-n auto`) is the obvious lever but is **secondary** to §4.1 and comes with a
correctness precondition: the suite is built on **global singletons** (config, undo, state tracker).
xdist parallelizes across *processes* (each worker gets its own singletons, so it's safe) but **not**
within a process, and it reorders tests — which is exactly why the ordering-independence from the
§3.1 base fixture must land first. Sequence: fix geometry (§4.1) → land the resetting base fixture
(§3.1) → *then* enable `-n auto` if wall-clock still matters. Don't enable xdist while any test relies
on cross-test singleton bleed.

### 4.5 CI matrix

The 3.11+3.12 matrix is cheap and worth keeping (3.11 = documented floor, 3.12 = forward guard). If
runtime ever becomes the bottleneck again after §4.1, run the **full** suite on 3.11 and a **smoke
subset** on 3.12 rather than dropping a version. Consider adding a `slow`-marker nightly job for the
dense fuzz tests (§4.1.3) so they still run without taxing PR latency.

---

## 5. Flaky Qt/UI test policy

The strategy is **prevent by construction**, not **quarantine after the fact**. The offscreen
platform already removes the biggest source of GUI flakiness (no real window server). The remaining
flake sources and the rules that forbid them:

| Flake source | Rule |
|---|---|
| Real event-loop waits (`QTest.qWait`, `processEvents` spin-until) | **Banned.** Drive behavior synchronously: call handlers directly, and for `AsyncTask`/threaded work either run the worker body synchronously in-test or block on completion deterministically. Never "wait 100ms and hope." |
| Wall-clock timing (undo auto-merge windows, debounce timers) | **Banned in assertions.** The undo auto-merge is time-based and glitchy (ledger: deferred); test the *explicit* `combining_actions` macro path instead, and inject/patch any clock rather than sleeping. |
| Live network / real SD backend | **Banned.** Use `--mode mock` (`test_generator`) for generation paths and stub the `intrapaint_api`/`src/api` HTTP layer. API-client tests assert **request construction and response parsing** against fixtures, never a live server. |
| Endianness / QImage format assumptions | Normalize to `Format_ARGB32` before any pixel comparison (§3.2); the codebase assumes little-endian (map §7) so goldens must be format-pinned to stay CI-portable. |
| Font/text rendering nondeterminism | Text-layer goldens are the most platform-fragile. Prefer asserting **geometry/structure** (text rect bounds, layout) over exact glyph pixels; if a pixel golden is unavoidable, give it a documented perceptual tolerance (§3.2) and note the fragility at the call site. |
| Global-state bleed between tests | Solved structurally by the resetting base fixture (§3.1). This is the #1 cause of "passes alone, fails in suite" and "passes in suite, fails under xdist reordering." |
| Signal/slot ordering races | Verify signals with connected `MagicMock` + `assert_called*` (existing idiom) on the **main thread**; per the concurrency decisions, model/UI mutation is main-thread-only, so tests should never assert across a thread boundary. |

**If a test still flakes** despite the above, the response is **diagnose and fix or delete**, not
`@pytest.mark.flaky`-and-retry. A retried flaky test is a silenced bug detector. The one acceptable
marker is `@pytest.mark.skip(reason=...)` with a linked issue when a test documents a *known* bug not
yet fixed (or `xfail(strict=True)` so it flips to a failure the moment the bug is fixed — this is how
the known undo bugs from §2.2 should be encoded).

---

## 6. Golden-image maintenance workflow

Golden images are the established pixel-truth mechanism and the ledger already settled the
philosophy (**pixel goldens preferred**; **re-bless = visually confirm the new `*_tested.png`, then
replace the committed golden**). This section turns that into one repeatable ritual so it can't drift.

**Storage & naming.** Goldens live under `test/resources/test_images/`, one PNG per case, named for
the test (`<test_name>.png`). The failure artifact is `<test_name>_tested.png` written **next to** the
golden (never committed; add `*_tested.png` to `.gitignore`).

**The one code path.** All golden comparisons go through `assert_image_matches_golden` (§3.2). No test
hand-rolls save/load/compare. This guarantees every failure produces a diffable artifact and every
comparison uses the same format normalization and tolerance policy.

**Creating a golden (first time).** Run the test with no committed golden → helper writes
`<name>_tested.png` and fails → **inspect it by eye** → if correct, `git mv`/rename it to `<name>.png`
and commit. Never generate-and-commit blindly; a wrong first golden bakes in a bug as "expected."

**Re-blessing (intended change).** When an edit legitimately changes output: run → helper writes
`<name>_tested.png` and fails → **diff old vs new visually** → if the change is intended and correct,
replace the committed golden with the tested output and commit *in the same change* as the code that
caused it, with a message noting the visual delta. A golden update in a diff is a **review checkpoint**
— reviewers should look at the image diff, not rubber-stamp it.

**Watching a test render.** `QT_QPA_PLATFORM=xcb pytest test/...::case` renders on a real display for
debugging a golden mismatch (documented in CLAUDE.md/conftest).

**Guardrails.**
- Keep goldens small (§4.2) — cheaper to store, render, and diff.
- A golden that proves platform-fragile gets a documented tolerance or is downgraded to a
  structural/geometry assertion (§5) — don't let one flaky golden train people to ignore golden
  failures.
- Never `git add` a `*_tested.png`; if one shows up in `git status`, a re-bless was left half-done.

---

## 7. Concrete first steps (execution order)

This is the "if you do nothing else" sequence — infra and CI economics before breadth:

1. **Re-shape `geometry_utils_test.py`** (§4.1): coarse sweep + adversarial table; dense fuzz behind
   `@pytest.mark.slow`. *CI drops from ~4 min to seconds; nothing else you add inherits the floor.*
2. **Land `IntraPaintTestCase`** (§3.1) and migrate the 11 existing files onto it (mechanical de-dup).
3. **Land `assert_image_matches_golden`** (§3.2) and route `image_stack_test` + `brush_tool_test`
   through it; add `*_tested.png` to `.gitignore`.
4. **Land the tool harness** (§3.3).
5. **Tier 0 safety nets** (§2.2): `undo_stack_test`, `transform_layer`/`TransformState`,
   `selection_layer` — *before* the A2/OQ4/Undo refactors execute, encoding the known bugs as
   `xfail(strict=True)`.
6. **Proceed through `test-wip/` Tiers 1→3** (Tier 4 provisional pending OQ5; Tier 5 last).
7. **Optional:** add `pytest-xdist -n auto` (§4.4) once §5 ordering-independence is proven, and a
   nightly `slow` job (§4.5).

Steps 1–4 are pure infrastructure and unblock literally everything else; they're the highest-leverage
work in this whole report.

---

## 8. Open questions for the maintainer

- **`test-wip/` `OPEN QUESTION:` markers** throughout the outline flag intended-behavior assumptions
  that must be confirmed before a test encodes them. Those are the content-level unknowns; this report
  doesn't resolve them (they're per-test).
- **Coverage gate?** Currently none. Recommendation: **don't add a coverage-percentage gate** while
  coverage is being built out — it creates pressure to write low-value UI pixel tests to hit a number.
  Revisit once Tiers 1–3 exist and the number is meaningful.
- **Perceptual-tolerance threshold** for the rare fragile goldens (text) — pick a concrete
  max-per-channel-delta once the first fragile case appears, rather than guessing now.
- **When does OQ5 land relative to Tier 4?** If the `intrapaint_api` swap is near-term, defer Tier-4
  API tests until after it, and note that the library ships its own A1111+ComfyUI tests (per OQ5) — so
  IntraPaint's Tier-4 effort may shrink to *adapter* tests (params_adapter, image adapter, progress
  bridge) rather than re-testing the client internals.
</content>
</invoke>
