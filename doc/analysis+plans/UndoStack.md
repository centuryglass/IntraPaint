# Replacing the hand-rolled `UndoStack` with Qt's `QUndoStack`

Feasibility analysis and a phased replacement plan for `src/undo_stack.py`.

**Verdict:** feasible and reasonably clean — a bounded refactor behind a compatibility wrapper,
not a rewrite. Estimate ~1–2 focused days for the core swap + tests, *excluding* faithful
auto-merge (deferred, see Phase 3).

---

## 1. Why consider this

`src/undo_stack.py` is a hand-rolled singleton undo/redo engine (`UndoStack`, `_UndoAction`,
`_UndoGroup`). It works, but:

- It reimplements things Qt already provides: an undo-limit cap, action grouping (macros),
  action coalescing (mergeWith/id), and change signals.
- It has known rough edges:
  - **`AppConfig.max_undo` is not wired in** — the stack is bounded by the module constant
    `MAX_UNDO = 50`, and the config value does nothing. (Confirmed bug.)
  - **`undo()` on an empty stack early-returns without resetting `_undo_in_progress`**, leaving
    the flag stuck `True`. (Confirmed bug — `image_layer.py` reads this flag.)
  - The **time-based auto-merge** in `commit_action` is glitchy in practice and needs finessing.

Migrating lets us delete custom machinery, inherit Qt's well-tested behavior, and fix the two
bugs along the way.

## 2. Current design (what must keep working)

Public API of `UndoStack` (singleton):

| Member | Purpose |
|---|---|
| `commit_action(action, undo_action, action_type, action_data=None, skip_initial_call=False)` | Run `action` now (unless skipped), push an undo entry. Auto-merges with the previous entry if within `UNDO_MERGE_INTERVAL`. |
| `combining_actions(action_type)` (context mgr) | Group every `commit_action` inside the block into one undo entry. |
| `last_action(action_type)` (context mgr) | Yield the top entry so callers can coalesce a continuous change in place. |
| `undo()` / `redo()` / `clear()` | Standard stack ops. |
| `undo_count()` / `redo_count()` | Stack sizes. |
| `undo_count_changed` / `redo_count_changed` (signals, `int`) | Emitted on size changes. |
| `undo_in_progress` (property) | True while an undo is running. |

Internal: `_UndoAction` (one redo/undo pair + type + `action_data` + timestamp), `_UndoGroup`
(a list of pairs undone/redone together), a re-entrancy lock that raises on concurrent changes.

### Usage surface (grep over `src/`, 14 files)

- `commit_action` — **35** call sites
- `combining_actions` — **13** call sites
- `last_action` — **2** real call sites (`layer.py:584`, `image_stack.py:357`)
- `undo_in_progress` — **1** reader (`image_layer.py:315`, for alpha-lock handling)
- `skip_initial_call` — **1** user (`image_layer.py:188`, `borrow_image`)
- `action_data` — used only by the 2 `last_action` coalescing sites
- `undo_count` / `redo_count` / the two signals — counts + UI/menu enablement

Files: `controller/app_controller.py`, `controller/image_generation/{sd_generator,sd_webui_generator}.py`,
`image/filter/filter.py`, `image/layers/{image_layer,image_stack,image_stack_utils,layer,layer_group,text_layer}.py`,
`tools/{layer_transform_tool,text_tool}.py`, `ui/graphics_items/path_creation_item.py`,
`ui/widget/color_picker/palette_widget.py`.

## 3. Feature-by-feature mapping to Qt

`QUndoStack` / `QUndoCommand` / `beginMacro` cover almost everything. Key fact: `QUndoStack.push()`
calls `command.redo()` immediately — matching `commit_action`'s "run the action now" model.

| Custom feature | Qt equivalent | Cleanliness |
|---|---|---|
| `commit_action(do, undo, type, data)` | `push(_CallableCommand(do, undo, ...))` | **Clean** — one adapter command wraps two callables; keeps closure style, no call-site rewrites |
| `combining_actions` | `beginMacro()/endMacro()` | **Very clean**, ~1:1 |
| `last_action` in-place coalescing | `QUndoCommand.mergeWith()` + `id()` | **Clean** — mergeWith/id exist for exactly this |
| time-based global auto-merge | mergeWith + shared `id()` + timestamp | **Fiddly** — deferred to Phase 3 |
| `MAX_UNDO` cap | `setUndoLimit(n)` | **Clean** — wire in `AppConfig.max_undo` here |
| `undo_count()` / `redo_count()` | `index()` / `count() - index()` | **Clean** |
| `undo_count_changed` / `redo_count_changed` | `indexChanged` / `canUndoChanged` | Re-emit as shims to keep the existing signal names |
| `undo_in_progress` | not exposed | Track with a flag around wrapped `undo()/redo()` — also fixes the stuck-flag bug |
| `skip_initial_call` | — | `first_redo_is_noop` flag on the adapter command |
| re-entrancy lock / RuntimeError guard | none in Qt | Drop, or keep as a wrapper assert (low risk; main-thread only) |

### The `last_action` coalescing pattern (the only non-obvious mapping)

Two call sites (`Layer._apply_combinable_change`, `ImageStack` generation-area setter) currently
peek at the top entry and, if it's the same type/target within the merge interval, **mutate its
`redo` closure to the latest value and re-run it** — keeping the original `undo`. Net effect: a
continuous drag (opacity slider, generation-area handle) collapses into a single undo back to the
value before the drag started.

In Qt this becomes a mergeable `QUndoCommand`:
- `id()` returns a stable value per coalescing kind (e.g. hash of `action_type`, or one shared id
  with a type check inside `mergeWith`).
- On `push(new)`, Qt runs `new.redo()` (applies the new value), then — if `top.id() == new.id()`
  and not in a macro — calls `top.mergeWith(new)`. Implement `mergeWith` to absorb `new`'s
  "new value" into `top` while keeping `top`'s original "old value", returning `True` only when
  the same-target + interval condition holds. Qt then discards `new`.

This reproduces the current behavior with Qt's own mechanism instead of hand-mutating the stack.

## 4. Replacement plan (phased)

### Phase 0 — De-risk with a behavioral spec (do first)
Turn `test-wip/undo_stack_test.py` into a **real** test suite against the *current* `UndoStack`
public API (commit/undo/redo accounting, `combining_actions` grouping, redo invalidation on new
commit, cap enforcement, signals, `undo_in_progress`). These become the regression gate the
replacement must pass identically. Skip/adjust only the two known-bug assertions (max_undo,
empty-undo flag) — encode the *intended* behavior there so the new implementation is held to the
fixed contract, not the buggy one.

### Phase 1 — Compatibility wrapper over `QUndoStack`
Rewrite `src/undo_stack.py` internals while keeping the **exact public API**:
- `UndoStack` stays a singleton, now wrapping a `QUndoStack`.
- Add `_CallableCommand(QUndoCommand)`: holds `redo_fn` / `undo_fn`, a `first_redo_is_noop` flag
  (for `skip_initial_call`), and an `action_type`/`text`.
- `commit_action(...)` → build a `_CallableCommand` and `push()` it. **No auto-merge yet**
  (each commit is its own entry — see Phase 3).
- `combining_actions(...)` → `beginMacro()` / `endMacro()`.
- `undo()/redo()/clear()` → delegate; wrap `undo()/redo()` to set/clear `undo_in_progress`
  correctly (fixing the stuck-flag bug — always reset in a `finally`).
- `undo_count()/redo_count()` → derive from `index()`/`count()`.
- Re-emit `undo_count_changed`/`redo_count_changed` from `indexChanged`.
- `setUndoLimit(AppConfig.max_undo)` and reconfigure on that config value changing (fixes the
  unwired-config bug).
- Keep a lightweight re-entrancy assert if cheap; otherwise drop.

Outcome: ~12 of the 14 call-site files are untouched. The 2 `last_action` sites still work
because `last_action` can remain a thin shim in Phase 1 (peek the top command), OR be moved to
mergeWith in Phase 2.

### Phase 2 — Port `last_action` coalescing to `mergeWith`
Convert the 2 coalescing sites to push a mergeable `_CallableCommand` (id + timestamp + target in
`mergeWith`) and retire the `last_action` context manager + `action_data`. This is the idiomatic
Qt form and removes the last bit of hand-managed stack mutation.

### Phase 3 — (Long-term) faithful global auto-merge
Re-introduce the "coalesce any consecutive commits within `UNDO_MERGE_INTERVAL`" behavior — but
better than today. Options:
- A mergeable "group" command that appends (redo, undo) pairs in `mergeWith` when the interval
  condition holds (essentially porting `_UndoGroup` into a `QUndoCommand`), with all commits
  sharing an id so Qt attempts the merge.
- Or a short-lived timer/macro that auto-opens on the first commit and auto-closes after the
  interval.

**Decision:** auto-merge is glitchy as-is and is a long-term goal that needs finessing. **Ship
Phases 0–2 without it** — undo granularity becomes finer for rapid *unrelated* edits, but the
explicit `combining_actions` macros and the Phase-2 `mergeWith` coalescing preserve the important
"one drag = one undo" behavior. Revisit Phase 3 once the rest is stable.

## 5. Risks & things to verify

1. **Threading.** `QUndoStack` expects the main (GUI) thread; the current stack uses a lock
   because `Config.set` can run off-thread. Confirm no `commit_action` ever fires off the main
   thread (call sites look main-thread-only — verify `filter.py`'s AsyncTask path and the
   generator upscale paths, which run work in worker threads but should commit on `finish`).
2. **Command lifetime / memory.** Qt (C++) owns pushed commands; closures capturing `QImage`s
   live until trimmed by the undo limit — same memory profile as today.
3. **Macro context-manager quirk.** Two `combining_actions` sites chain context managers with
   `and` (`with combining_actions(...) and self.all_signals_delayed():`). Re-express these as
   nested `with` / `ExitStack` when moving to `beginMacro/endMacro`.
4. **Signal-shape parity.** Anything connected to `undo_count_changed/redo_count_changed`
   (menu/toolbar enablement) must keep receiving an `int`; the re-emit shims handle this, but
   double-check emission timing (Qt emits `indexChanged` slightly differently than the custom
   per-push logic).
5. **`clear()` semantics.** The custom `clear()` emits count-changed only when counts were
   nonzero; replicate to avoid spurious UI churn (tests permitting, this is minor).

## 6. Recommendation

Proceed via the **wrapper** (Phases 0→1→2), fixing the `max_undo` and `undo_in_progress` bugs as
part of Phase 1. Defer faithful global auto-merge (Phase 3). Do Phase 0 first so the migration is
guarded by a behavioral spec that must pass identically before and after.

## Appendix — key source references

- `src/undo_stack.py` — the implementation being replaced.
- `src/image/layers/layer.py:565` (`_apply_combinable_change`) — primary `last_action` coalescer.
- `src/image/layers/image_stack.py:345` — generation-area `last_action` coalescer.
- `src/image/layers/image_layer.py:188` (`skip_initial_call`), `:315` (`undo_in_progress`).
- `test-wip/undo_stack_test.py` — outline to promote into the Phase 0 behavioral spec.
</content>
