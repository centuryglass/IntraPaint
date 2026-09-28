# IntraPaint — software architecture review

Umbrella architecture assessment. Reads on top of `_codebase_map.md` and `_decisions_ledger.md`.
Cross-cutting subsystems that will get their own deep-dive reports (config, concurrency,
rendering, api-swap) are given a **position** here and the detail deferred to those reports.

Evidence is cited as `file:line`. `[inferred]` marks reasoning not confirmed line-by-line.

---

## 1. Summary verdict

IntraPaint is **architecturally above average for a solo project** — it has a real
model/controller/view/backend separation, a genuinely good config-as-data layer, and a clean
declarative menu system. The problems are not structural confusion; they're a small number of
**pervasive global-state and "clever mechanism" choices** that increase coupling, hurt
testability, and occasionally produce latent bugs. None require a rewrite. The highest-leverage
work is (a) loosening the singleton/global-state coupling and (b) retiring a few home-grown
mechanisms (custom undo — already decided; reflection-based config callbacks; the
context-manager-chaining idiom that is actively broken in three places).

## 2. What's legitimately good (preserve these)

- **Layered separation.** `image/` (model), `controller/`, `ui/`, and the backend split
  (`api/` + `controller/image_generation/`) are real, not nominal. Tools act on the model, the
  view subscribes to model signals. This discipline is uncommon in hobby codebases and is worth
  protecting.
- **Config-as-data.** The JSON definition files are the source of truth; `Config`
  (`config/config.py`) gives typed `get/set/connect`, options, ranges, persistence, *and*
  auto-generates the correct editing widget per value (`get_control_widget`, config.py:257).
  Adding a setting is a data edit, not a code change. This is a strong, cohesive design.
- **Declarative menu system.** `@menu_action` (`util/menu_builder.py:23`) binds a method to a
  menu path, pulls label/tooltip/shortcut from `KeyConfig`, auto-reconnects the shortcut when the
  binding changes (menu_builder.py:140), and ties enablement to `AppStateTracker` states
  (menu_builder.py:200). `AppController`'s ~50 menu methods are mostly thin, readable delegations
  because of it (app_controller.py:795+). This is idiomatic-Qt-plus-good-taste.
- **Tool abstraction.** `BaseTool` (`tools/base_tool.py`) is a well-documented interface with an
  explicit extend/integrate contract, the standard "handler returns bool to consume the event"
  model, a shared `validate_layer` gate, and a nice **tool-delegation** feature (hold a modifier
  to temporarily swap tools — tool_controller.py:174). Clean extension point.
- **Deliberate dual layer API.** `Layer` distinguishes the undoable/signalling *property*
  interface from the non-undoable `set_*` *function* interface, and documents why (layer.py:318).
  Signals are granular. This is a thoughtful, consistent contract inherited by every layer type.
- **Server-free generation builders.** `ComfyNodeGraph` / `DiffusionWorkflowBuilder`
  (`api/comfyui/`) produce the workflow as a pure, deterministic data structure, cleanly separated
  from the HTTP layer — easy to reason about and test without a backend.
- **Pragmatic performance escape hatch.** The one genuinely hot path is a Cython module
  (`util/visual/image_fill`) that auto-builds on launch if missing (IntraPaint.py:22). Right tool,
  right place, with a graceful fallback.
- **Headless test infra.** `conftest.py` forces Qt offscreen so the whole suite runs from
  `pytest`; golden-image comparison is the established pattern for pixel output. The *infra* is
  good even though *coverage* is thin.

## 3. What's ill-advised (ranked by cost × risk)

### 3.1 App-wide global state via a Singleton metaclass — **the biggest liability**
`Singleton` (`util/singleton.py`) stores one instance per class in a class-level dict, with no
lifecycle. Six services use it: `AppConfig`, `Cache`, `KeyConfig`, `A1111Config`, `UndoStack`,
`AppStateTracker`. Consequences:
- **Hidden coupling.** Almost any module can reach global config/undo/state
  (`UndoStack()` alone appears 54× in `src/`). Dependency flow is implicit; you can't tell what a
  class needs from its constructor.
- **Testability tax.** Isolation depends on a test-only back door, `Config._reset()`
  (config.py:177), plus careful `setUp` ordering — visible in every test's boilerplate.
- **Constructor-args footgun.** Because construction is memoized, `KeyConfig('some/path')` uses
  the path only on the *first* call and silently ignores it afterward (singleton.py:8-11). Any
  code that "constructs with args" is relying on being first.

This is the root cause of much of the testing friction and the reason so much of the codebase is
implicitly coupled. Fixable incrementally (see §6) but wide blast radius.

### 3.2 `AppController` concentration (1536 lines)
Not a pure god object — most menu methods delegate — but it owns several *distinct* concerns that
could be collaborators: theme/font/style application (app_controller.py:389-448), cursor policy
(app_controller.py:449+), image I/O with per-format handling (`save_image_as` alone is ~150 lines,
app_controller.py:824-973), metadata, and generator lifecycle. Extracting an `ImageIO` helper and
a `ThemeManager` would materially shrink it without disturbing the menu layer.

### 3.3 `ImageStack` concentration (1705 lines)
The model equivalent: it is both the layer-tree structure *and* a large operations toolbox
(resize/crop/merge/copy-paste-clear/generation-area). Some operations already live in
`image_stack_utils.py`, which shows the seam is recognized — the "tree vs. operations" split just
needs to go further.

### 3.4 Reflection-and-string-matching in the config callback system
`Config.set` dispatches callbacks by **inspecting their arity** at call time
(`len(signature(callback).parameters)`, config.py:387) and auto-disconnects dead Qt objects by
**string-matching the exception message** `'already deleted'` (config.py:396). Both are clever and
both are fragile: arity-sniffing makes the callback contract implicit, and matching Qt's exception
text is liable to break on a Qt/PySide upgrade. The idiomatic answer is real signals/slots (auto
disconnect on QObject destruction) or weakref callbacks.

### 3.5 The `with A and B:` context-manager idiom — **actively broken in 3 places**
`with UndoStack().combining_actions(...) and self.all_signals_delayed():` (layer_group.py:91,
layer_group.py:111, image_stack_utils.py:153). Because `A and B` evaluates to `B` when `A` is
truthy, **only `B` is entered — `combining_actions` never runs** (verified empirically). So the
undo grouping those call sites intend is silently a no-op; the flip/util operations get committed
as separate undo entries, only *appearing* grouped because the time-based auto-merge happens to
coalesce them. This is a real latent correctness bug wearing a style-issue costume.

### 3.6 Deprecated / non-portable API usage
`QColor.isValidColor(str)` is deprecated in current PySide6 and called in several places
(config.py:251, `color_button.py`, `qt_paint_brush_tool.py`, `selection_outline.py`, …),
generating ~250 warnings/run and a future hard break. QImage indexing assumes little-endian
throughout. Neither is architectural, but both are latent forward-compat debt.

### 3.7 Rolling a custom undo stack
Already analysed and decided (`UndoStack.md`: replace with `QUndoStack` via wrapper). Listed here
only as an instance of the recurring "home-grown mechanism where Qt already provides one" theme.

## 4. Deviations from normal practice (the "do I need to expand my knowledge?" section)

Direct answers, since you asked to be told what you might not know:

- **Singletons for app services → learn dependency injection.** The Singleton-metaclass approach
  is a well-known anti-pattern at application scale (global mutable state, implicit dependencies,
  hard testing). It's *everywhere* in hobby code and is not "wrong" at this size, but the
  mainstream alternative you should know is **dependency injection**: pass `config`/`undo`/`state`
  into constructors (or a single explicit `AppContext`), so dependencies are visible and tests can
  supply fakes without a `_reset()` back door. This one pattern, understood, would change how you'd
  design several subsystems.
- **Config key constants via dynamic `setattr` + generated typing stubs → unusual.** Keys become
  class attributes at load time (config.py:102), and the typed stubs are hand-regenerated by a
  script (key_config.py:186-292). It works, but most projects would generate a real
  constants/`Enum` module from the JSON at build time (or just hand-write constants). The current
  approach adds a moving part (the generator) and a drift risk (stubs vs. JSON). Not wrong — but
  you're carrying complexity most codebases avoid.
- **Arity-sniffing + exception-string matching for callback lifecycle → non-idiomatic.** See
  §3.4. Qt's signal/slot system already solves "call with the right args" and "disconnect when the
  receiver dies"; reimplementing it with `inspect.signature` and string-matched exceptions is the
  kind of thing that signals a gap in Qt signal-lifetime knowledge worth closing.
- **`with A and B:` → a genuine misconception, not a style quirk.** §3.5. The standard ways to
  combine context managers are nested `with`, comma-separated `with A, B:`, or
  `contextlib.ExitStack`. The `and` form silently drops the first manager. Worth internalizing
  because it has already cost you correctness.
- **Manual `connect`/`disconnect` bookkeeping for "the active layer's signals"**
  (image_viewer.py:216-235) → common in Qt, but under-abstracted here and a repeat bug source
  (the "nested layer selection state not updating" item in TODO smells like exactly this). A small
  "track signals of the current X" helper is the normal remedy. This feeds the rendering report.

Net: your *structure* is sound and in places genuinely good. The deviations cluster around
**global state** and **home-grown mechanisms that duplicate Qt/stdlib facilities** — that's the
area where broadening the reference points would pay off most.

## 5. Cross-cutting positions (detail deferred to the dedicated reports)

- **Config system:** keep the config-as-data design — it's a strength. But the config report
  should decide (a) the `config_from_key` / key-exclusivity question [open per ledger], (b) whether
  to retire the reflection/exception-string callback machinery (§3.4) in favour of signals/weakrefs,
  and (c) whether to replace dynamic-attr + generated stubs with generated constants.
- **Concurrency:** the model is ad hoc — `AsyncTask` for filters/generation, off-main-thread
  `Config.set` writes (config.py:371-383), the undo lock, `QTimer`-based deferred saves. **Position:**
  adopt one documented rule — *all model/undo mutation happens on the GUI thread; workers only
  produce data and commit on their finish signal.* This is also a **prerequisite** for the
  `QUndoStack` migration, which is main-thread-only. Defer specifics to the concurrency report.
- **Rendering:** QGraphicsScene/QGraphicsView is a **defensible** foundation for a layered editor;
  don't assume it must be replaced. But per-layer item lifecycle and outline management are manual
  and under-abstracted (image_viewer.py), and the partial-alpha compositing glitches
  (`[inferred]`) live here. **Position:** keep QGraphicsView, invest in a cleaner layer-item/scene
  sync abstraction, and investigate the compositing path. Defer to the rendering report.
- **API swap (`../sd-api-standalone`):** the builder-vs-HTTP separation is already clean, and the
  generator classes in `controller/image_generation/` are the seam. **Position:** feasible without
  disturbing the rest of the app; the standalone library should expose the backend behind roughly
  the current generator interface. Defer to that report.

## 6. Prioritized "actually fix this" list

Ordered by value-to-effort, with prerequisites noted.

1. **Fix the `with A and B:` undo-grouping bug (§3.5).** Low effort, real correctness win; convert
   the 3 sites to nested `with` / `ExitStack`. Do this now, independent of everything else.
2. **Deprecation + portability sweep (§3.6).** Low effort: replace `QColor.isValidColor`, add an
   endianness guard. Prevents a future hard break on a PySide6 upgrade.
3. **Undo → `QUndoStack` (already planned, `UndoStack.md`).** Medium effort; depends on the
   concurrency rule (#5) for thread-safety guarantees.
4. **Extract collaborators from `AppController` and split `ImageStack` (§3.2, §3.3).** Medium
   effort, contained blast radius; makes both testable and readable. Start with `ImageIO`.
5. **Adopt an explicit threading discipline (§5 concurrency).** Prerequisite for #3; mostly
   documentation + auditing the `AsyncTask`/generator/`Config.set` paths.
6. **Make the config/undo/state services injectable (§3.1).** Highest architectural value, largest
   blast radius — best done incrementally: keep the global accessors as thin shims over injectable
   instances, migrate constructors opportunistically. Treat as a long-term direction, not a single
   PR. This is the change that most improves testability and unlocks cleaner work everywhere else.
7. **Retire the reflection/exception-string config callbacks (§3.4).** Medium effort; fold into the
   config report's recommendations.

## 7. Challenges to settled decisions

None reversed. One emphasis: the **singleton/global-state issue (§3.1) is a larger architectural
liability than the custom undo stack**, and is worth putting on the roadmap alongside the (already
decided) undo migration rather than treating undo as the main cleanup. The two interact — a
`QUndoStack` behind an injectable service is cleaner than one behind another global singleton.
</content>
