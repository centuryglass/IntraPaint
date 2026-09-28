# IntraPaint — concurrency & threading model audit (A5)

Deep-dive handed off from `architecture_review.md` §5. Reads on top of `_codebase_map.md` and
`_decisions_ledger.md`. Evidence cited as `file:line`; claims about Qt threading behavior were
**verified empirically** (see §2), not assumed.

---

## 1. Summary verdict

The app has **no single threading discipline** — it uses at least four distinct async/deferral
mechanisms — but the situation is **better than the architecture review feared in one respect and
worse in another**:

- **Better:** the dominant mechanism, `AsyncTask`, delivers its finish/result handlers on the
  **main thread** (verified). So filters and image generation — the big long-running operations —
  commit their model/undo changes on the GUI thread. The QUndoStack migration's "main-thread only"
  prerequisite is therefore **already satisfied on the paths that matter**, not a blocker.
- **Worse:** `Config.set` contains a **confirmed re-entrant-lock deadlock** on any save-triggering
  call from a non-main thread, and it runs change-callbacks + file I/O on the caller's thread — so
  it is **not safe to call off the main thread**, yet worker code can reach it. (`spacenav_manager`
  has the same class of off-main bug — a worker-thread closure mutating the model and calling
  `repaint()` — but it's a known-broken optional subsystem, so it's a worked example rather than an
  active fix; see F3.)

The core problem is **fragility, not chaos**: correctness currently depends on an invisible Qt
rule (which thread a signal's slot runs on depends on the *sender's* thread affinity for bare
callables). It works for `AsyncTask` by accident of where those objects are constructed, and fails
for `spacenav` for the same reason. One documented rule + a couple of targeted fixes resolves it.

## 2. Method — the Qt rule this audit rests on (verified)

Qt's `AutoConnection` picks queued-vs-direct delivery from the **receiver's** thread affinity.
The subtlety that governs this codebase: when a signal is connected to a **bare Python callable**
(lambda/closure/free function — no receiver `QObject`), there is no receiver affinity, and PySide6
falls back to the **sender's** thread affinity. Verified with two minimal reproductions of the
actual patterns in the code:

- **`AsyncTask` pattern** (sender constructed on main thread, `emit` from a `QThreadPool` worker):
  a bare-closure `finish_signal` slot ran on the **main** thread. Safe.
- **`moveToThread` pattern** (sender moved onto a `QThread`, `emit` from that thread): a
  bare-closure slot ran on the **worker** thread; a `QObject` bound-method slot ran on the **main**
  thread. Unsafe for the closure.

Rule of thumb for the whole codebase: **a cross-thread signal connected to a bare callable runs on
the sender's owning thread; connected to a QObject's method, it runs on that QObject's thread.**

## 3. The concurrency surface (what exists)

Four distinct mechanisms, plus two lock-guarded singletons:

1. **`AsyncTask`** (`util/async_task.py`) — a `QRunnable` on the global `QThreadPool`; runs
   `action(*signals())` then emits `finish_signal` (async_task.py:37-40). This is the **primary**
   mechanism: filters (`filter.py:285`) and, via subclassing, essentially all generator work —
   inpaint (`image_generator.py:174`), preview/upscale/loading (`sd_generator.py:508,568,645`),
   interrogate/progress/settings (`sd_webui_generator.py:559,618,510`). Subclasses override
   `signals()` to expose `status_signal`/`error_signal`/`image_ready`/etc.
2. **`moveToThread` worker** (`spacenav_manager.py:205-208`) — a persistent `QThread` with a
   worker `QObject`, shared `ThreadData` guarded by a `Lock` (spacenav_manager.py:63). The
   idiomatic Qt long-lived-worker pattern — but see F3.
3. **Off-main-thread file writes in `Config`** (`config.py:371-383`) — `set()` writes JSON
   directly when called off the main thread, "because timers can't be started from other threads."
4. **`QTimer`-based deferral/coalescing** — render timers (`image_stack.py:127`,
   `layer_group.py:41`), save timer (`config.py:86`), selection-update timer
   (`image_stack.py:137`), brush buffer timers (`qt_paint_brush.py:38`, `smudge_brush.py:29`),
   mypaint tile timer, etc. **This is single-thread event-loop deferral, not concurrency** — safe
   as long as it's only touched on the main thread, which it is. Called out only because it's
   easily conflated with the real threading above.

Lock-guarded singletons: `Config._lock` (config.py:85) and `UndoStack._access_lock`
(undo_stack.py:65, with a re-entrancy guard that raises).

## 4. Findings (ranked)

### F1 — `Config.set` deadlocks on any save-triggering call from a worker thread. **HIGH, confirmed.**
`set()` acquires `self._lock` (config.py:372) and, on the non-main-thread branch, calls
`self._write_to_json()` (config.py:375) — which itself does `with self._lock:` (config.py:639).
`self._lock` is a plain `threading.Lock` (config.py:85), which is **non-reentrant**, so the second
acquisition blocks forever. Worse, the deadlocked thread is holding the lock, so the next
main-thread config access blocks too → **whole-app freeze**.
- **Trigger:** an off-main `set(..., save_change=True)` while `_save_timer` is inactive. Worker
  actions (filters, generators) run off-main and have full access to `Cache()`/`AppConfig()`, so
  this is reachable, not theoretical.
- **Fix:** don't call `_write_to_json()` while holding the lock (release first), or make `_lock` an
  `RLock`, or — better, per §5 — never mutate config off the main thread at all.

### F2 — `Config.set` runs change-callbacks + file I/O on the caller's thread. **HIGH, confirmed (design).**
Beyond F1, `set()` invokes all connected callbacks synchronously on the calling thread
(config.py:385-402) and (main-thread branch) schedules a `QTimer`. Callbacks are frequently UI
updates (widget `setValue`, control refreshes via `get_control_widget`, config.py:257). So a
worker-thread `set()` runs **UI mutation on the worker thread** — undefined behavior in Qt.
- The off-main-thread branch (F1's location) exists precisely because the author hit "timers can't
  start off-thread" — i.e. this is a patch on the symptom of the deeper "`set` assumes main
  thread" problem.
- **Verify next:** audit which keys worker actions actually `set()` and whether those keys have
  UI-affecting callbacks. `[inferred: at least some do]`.

### F3 — spacenav's `nav_event` handler runs on the worker thread and touches the GUI. **LOW (subsystem known-broken).**
The worker is `moveToThread`'d (spacenav_manager.py:206) and emits `nav_event_signal` from its run
loop; it's connected to a **bare closure** `handle_nav_event` (spacenav_manager.py:198), which by
the §2 rule runs on the **worker thread**. That closure sets `image_stack.generation_area` and
calls `self._window.repaint()` (spacenav_manager.py:195-196) — model mutation and painting off the
GUI thread. `repaint()` off-thread is especially dangerous, and this off-main delivery is a
plausible contributor to the breakage.
- **`spacenav` is a known-broken, optional subsystem (per maintainer)** — so this is **not an
  active-priority fix**. Capture it as a known issue: if/when spacenav is revived, connect
  `nav_event_signal` to a `QObject` slot (or `Qt.QueuedConnection` / a context object) so it lands
  on the main thread, and never call `repaint()` off-thread. It's also a clean worked example of
  the §5 discipline.

### F4 — No unifying discipline; safety depends on an invisible construction detail. **Design, the root issue.**
`AsyncTask` is safe only because its instances are constructed on the main thread (main affinity →
queued delivery). `spacenav` is unsafe only because its worker is moved. Nothing at the call sites
makes this visible or enforced; a future `AsyncTask` constructed on a worker, or a new
`moveToThread` worker with a closure slot, silently reintroduces off-main execution. The model is
correct-by-accident, not correct-by-design.

### F5 — `AsyncTask` finish/result handlers are main-thread. **Reassurance / correction.**
Verified (§2): filters (`filter.py` `_finish`, which commits undo and calls `layer.set_image`) and
generator finish handlers (which insert generated images, change app state, update UI) run on the
**main thread**. This **corrects** the architecture review's implication (§5) that these mutate the
model off-main, and it means the QUndoStack migration is not gated on a concurrency fix (see §6).

## 5. Recommended discipline (one rule, documented)

Adopt and document a single model, matching what `AsyncTask` already does by luck:

> **All image-model, config, and undo mutation — and all UI/painting — happens on the GUI
> (main) thread. Worker threads may only (a) do CPU/IO work on data they own, and (b) hand results
> back via a signal whose sender lives on the main thread, or a `QObject` slot that lives on the
> main thread. Worker threads must never call `Config.set`, mutate a `Layer`/`ImageStack`, touch
> `UndoStack`, or call any `QWidget` method directly.**

Concrete mechanisms to standardize on:
- Keep `AsyncTask` as the worker primitive, but **document that its subclasses must be constructed
  on the main thread** (they are today) — that's what makes finish delivery safe. Consider asserting
  `QThread.currentThread() is qApp.thread()` in `AsyncTask.__init__` to make the contract enforced,
  not incidental.
- For any `moveToThread` worker (spacenav), connect its cross-thread signals to **`QObject` slots**
  (or `Qt.QueuedConnection`), never bare closures.
- Provide one tiny helper for "run this on the main thread" (`QTimer.singleShot(0, main_qobject,
  fn)` — the pattern already used correctly at `image_generator.py:265`) and route any worker-side
  need to touch model/UI/config through it.
- Make `Config.set` **main-thread-only**: assert it, and have worker code stage values to apply in
  the finish handler. That removes F1 and F2 outright and lets the off-main branch (config.py:374)
  be deleted.

## 6. Impact on the QUndoStack migration

Given F5, the concurrency prerequisite flagged in `UndoStack.md` (risk #1) and `architecture_review`
§5 is **largely already met**: undo commits happen in `AsyncTask` finish handlers, which run on the
main thread. The remaining work is **preventive**, not corrective:
- Enforce (assert) that `UndoStack`/`QUndoStack` is only touched on the main thread.
- Once F1/F2 are fixed (config main-thread-only) and F4's discipline is documented, the QUndoStack
  swap can proceed without a separate concurrency remediation.

→ **Recommendation:** downgrade "concurrency audit" from *blocking prerequisite* to *parallel
cleanup* for the undo work. They no longer need to be strictly sequenced.

## 7. Prioritized fixes

1. **F1 — fix the `Config.set` off-main deadlock.** Low effort, HIGH severity. Simplest correct
   fix: release `self._lock` before calling `_write_to_json()` (or switch to `RLock`), but prefer
   #2 below which removes the branch entirely.
2. **F2/F4 — make `Config.set` main-thread-only + document the one-rule discipline.** Medium effort;
   removes the off-main config branch (which also eliminates F1), adds a main-thread assertion to
   `AsyncTask.__init__` and `Config.set`, and writes the rule into `CLAUDE.md`. This is the durable
   fix.
3. **Enforce main-thread `UndoStack` access** (assertion) as part of the QUndoStack migration.
4. **Optional:** an `AsyncTask` docstring + assertion making "construct on the main thread" explicit.
5. **Deferred (spacenav revival only):** F3 — route `nav_event` to the main thread. Not worth doing
   while the subsystem is broken/disabled; keep it on the list for whenever spacenav is revisited.

## 8. Cross-references / doc updates warranted

- `_decisions_ledger.md`: record the verified fact "AsyncTask finish/result handlers run on the
  main thread" and the downgrade of the undo↔concurrency dependency.
- `UndoStack.md` risk #1 and `architecture_review.md` §5: their concurrency framing should be read
  in light of F5/§6 (prerequisite → parallel cleanup). Not wrong, just softened.
- `_execution_plan.md`: A5→undo is no longer a hard gate; note it.
</content>
