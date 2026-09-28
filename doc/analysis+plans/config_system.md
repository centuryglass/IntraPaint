# IntraPaint — config system evaluation (A4)

Deep-dive handed off from `architecture_review.md` §5. Reads on top of `_codebase_map.md`,
`_decisions_ledger.md`, and `concurrency_model.md` (A5, which this overlaps in `config.py`).
Evidence cited as `file:line`. Resolves the open `config_from_key` / key-exclusivity question the
ledger parked for this report.

---

## 1. Summary verdict

The config system is **one of the codebase's genuine strengths and should be kept**, but it carries
four fixable liabilities: a **model→UI dependency inversion**, a **home-grown callback mechanism**
that reimplements (badly) what Qt signals already do, an **unenforced key-namespace** behind
`config_from_key`, and **non-atomic, not-thread-safe persistence** (the last overlapping A5's
`Config.set` findings). None require redesigning the data model. The single highest-leverage change
is replacing the reflection-based callback machinery with **per-entry Qt signals** — it
simultaneously fixes the callback fragility (architecture_review §3.4), the off-main-thread callback
hazard (concurrency_model F2), and the deleted-object string-matching, all at once.

## 2. Design overview

- **Config-as-data.** Four JSON definition files under `resources/config/` are the source of truth
  for what options exist, their type, default, range, options, category, and whether they persist.
  `Config` (`config/config.py`) loads them into typed `ConfigEntry` objects.
- **Four domain singletons**, split by purpose: `AppConfig` (settings), `Cache` (persisted
  transient state), `KeyConfig` (keybindings), `A1111Config`. All `metaclass=Singleton`.
- **`ConfigEntry` extends `Parameter`** (`config_entry.py:64`). This is good reuse: config values and
  filter/generator parameters share one typed-value abstraction (type detection, `validate`, range,
  options). The same machinery that validates a filter parameter validates a config value.
- **Typed API:** `get`/`set`/`connect`/`connect_to_option_changes`, options management, per-value
  metadata (label/category/tooltip), and `get_control_widget` which **auto-builds the correct
  editing widget** for a value (config.py:257). Change callbacks fire on `set`.
- **Persistence:** values marked `saved` are written to JSON, debounced through a 10 ms `QTimer`
  (config.py:383); load coerces types (`ConfigEntry.load_from_json_dict`, config_entry.py:205) and
  falls back to defaults on corrupt JSON.

## 3. Strengths (keep these)

- **The data-driven model itself.** Adding/changing a setting is a JSON edit, not code. Uniform
  type-safety, change notification, options, and persistence for four different concerns through one
  mechanism is a real design win.
- **`ConfigEntry`↔`Parameter` unification.** One typed-value/validation abstraction serving config,
  filters, and generator options avoids three parallel systems.
- **Auto-generated control widgets.** `get_control_widget` (config.py:257) means the settings UI and
  per-key controls are derived, not hand-maintained — though it comes at the cost of C1 below.
- **Clean domain separation.** Settings vs. cache vs. keybindings vs. a1111 are genuinely distinct
  concerns and are split accordingly.

## 4. Findings (ranked)

### C1 — Model→UI dependency inversion. **HIGH (architectural), confirmed.**
The config/parameter layer — which should be pure model/data — **imports and manufactures Qt
widgets**:
- `config.py:24-26` imports `CheckBox`/`ComboBox` from `ui/input_fields`, and `get_control_widget`
  builds widgets and wires two-way binding (config.py:257-305).
- Worse, **`util/parameter.py:8-16` imports ten widget classes** from `ui/input_fields` — a *utility*
  module depending on the *view* layer.
- `Cache` also tracks `QWidget` geometry (`cache.py:38-39`, `save_bounds`, `_geometry_timer`).

This inverts the intended layering (view depends on model, not the reverse), makes the config/param
layer un-importable without the UI, and is a latent import-cycle risk. **Fix:** move the
widget-factory out of `Config`/`Parameter` into a UI-side helper that *takes* a `ConfigEntry`/
`Parameter` and *returns* a widget (`ui/input_fields/field_factory.py` or similar). `Config`/
`Parameter` keep only data + metadata; the UI reaches in, not out.

### C2 — Home-grown callback machinery reimplements Qt signals, badly. **HIGH, confirmed.**
`Config.set` dispatches callbacks by **inspecting arity at call time** (`len(signature(callback)
.parameters)`, config.py:387) and **auto-disconnects dead Qt receivers by string-matching the
exception message** `'already deleted'` (config.py:396). Consequences: the callback contract is
implicit (0/1/2 args inferred), and the lifetime handling is tied to a Qt exception string that can
change across versions. It also runs callbacks synchronously on the caller's thread — the root of
**concurrency_model F2** (worker-thread `set()` → UI callback off the main thread).
- **Fix — the keystone change:** give each `ConfigEntry` a real `Signal(object)` (or one signal per
  Config keyed by name), and have `connect()` wrap Qt's signal/slot. Qt then handles: (a) automatic
  disconnection when a `QObject` receiver is destroyed (deletes the string-match), (b) correct
  cross-thread marshaling to the receiver's thread (fixes F2), and (c) an explicit slot signature
  (deletes the arity sniffing). This one change resolves C2 + architecture_review §3.4 + A5 F2.
  Note the inner-key/option-change callbacks need a small adapter, but the core dispatch becomes
  standard Qt.

### C3 — `config_from_key` key namespace is unenforced. **MED, confirmed — resolves the open question.**
`get_config_from_key` (`config_from_key.py:9`) does a **linear first-match** across the four
singletons (AppConfig → Cache → KeyConfig → A1111). If two definition files ever declare the same
key, the second is **silently shadowed**, and nothing checks for it. It exists for a real reason:
generic code (settings modal, `menu_builder` taking a bare `config_key`) needs to find a key's owner
without knowing it.
- **Decision (this report owns it per the ledger): enforce exclusivity, don't scrap.** Keep the
  dispatch capability generic code needs, but make it correct:
  - At construction, have each Config **register its keys into one shared `key → owning Config`
    map**; a duplicate registration **raises at startup** (turns silent shadowing into a loud,
    immediate error).
  - `get_config_from_key` becomes an **O(1)** map lookup instead of building/scanning four singletons.
  - This both closes the open question (exclusivity enforced) and upgrades `config_from_key` rather
    than removing a needed capability.

### C4 — Dynamic attribute injection + hand-generated typing stubs. **MED, confirmed.**
Keys become class attributes at load via `setattr(child_class, KEY, key)` (config.py:102), and the
typed stub lists are **regenerated by a script** and pasted into the classes (e.g.
`key_config.py:186-292`). Works, but adds a moving part (the generator) and a drift risk (stubs vs.
JSON). **Fix:** generate a real constants module (or `Enum`) from the JSON at build time as the
single source of truth for key names, replacing both the runtime `setattr` magic and the hand-pasted
stubs. Medium effort; removes two footguns.

### C5 — Persistence is not crash-safe. **MED, confirmed.**
`_write_to_json` does `open(path, 'w')` + `json.dump` (config.py:642-644) — **non-atomic**. A crash
or full disk mid-write truncates the file; `_read_from_json` then treats the corrupt file as invalid
and **silently falls back to defaults** (config.py:655-657), i.e. the user loses all their settings.
**Fix:** write to a temp file + `os.replace` (atomic on POSIX/Windows). Low effort, prevents silent
settings loss.

### C6 — `Config.set` is not thread-safe. **HIGH — see concurrency_model.md (A5).**
Covered in A5: the off-main-thread branch (config.py:374-375) calls `_write_to_json()` while holding
the non-reentrant `self._lock`, which `_write_to_json` re-acquires → **deadlock** (A5 F1); and
callbacks run on the caller's thread (A5 F2). **Fix converges with A4:** make `Config.set`
main-thread-only (delete the off-main branch, add an assertion), and let C2's Qt signals handle any
legitimate cross-thread notification. See A5 §5/§7.

### C7 — Minor cleanups. **LOW.**
- `ConfigEntry.save_to_json_dict` handles `QSize` in two branches (config_entry.py:184-185 and
  :200-201) — redundant/confusing, works.
- `load_from_json_dict` infers "this dict is a range-wrapper, not a value" heuristically (a dict
  under a non-dict type, config_entry.py:221) — brittle but contained.

## 5. Recommended target design

Keep the data model; change the plumbing around it:

1. **`Config`/`Parameter` become UI-free** — pure typed values + metadata + change signals. Widget
   construction moves to a UI-side factory that consumes them (C1).
2. **Change notification = per-entry Qt `Signal`** — deletes arity-sniffing, exception-string
   lifetime handling, and off-thread callback hazards in one move (C2, A5 F2).
3. **One shared key registry** populated at construction — enforces exclusivity and makes
   `config_from_key` an O(1) lookup (C3).
4. **Key names come from a generated constants module** built from the JSON (C4).
5. **Persistence is atomic and main-thread-only** — temp-file + `os.replace`, no off-thread writes
   (C5, C6).

The data-driven definitions, `ConfigEntry`↔`Parameter` reuse, and domain split are **unchanged** —
they're the parts worth keeping.

## 6. Prioritized fixes

1. **C6/A5 F1 — remove the `Config.set` off-main deadlock** (also tracked in A5). Low effort, HIGH.
2. **C2 — per-entry Qt signals** replacing the reflection/exception-string callbacks. Medium effort,
   HIGH value; also closes architecture_review §3.4 and A5 F2. The keystone change.
3. **C3 — shared key registry + startup exclusivity check.** Low/medium effort; closes the open
   `config_from_key` question.
4. **C5 — atomic config writes.** Low effort; prevents silent settings loss.
5. **C1 — extract the widget factory; make `Config`/`Parameter` UI-free.** Medium effort; the
   cleanest architectural win, but larger blast radius (touches every `get_control_widget`/
   `get_input_widget` caller).
6. **C4 — generated key-constants module.** Medium effort; retires the dynamic-attr + stub drift.
7. **C7 — minor cleanups.** Opportunistic.

## 7. Cross-references / doc updates

- `_decisions_ledger.md`: mark the `config_from_key` / key-exclusivity question **resolved** —
  decision: **enforce exclusivity via a shared key registry; keep (and speed up) `config_from_key`,
  don't scrap it.**
- `concurrency_model.md`: C2 (per-entry Qt signals) + C6 (main-thread-only `set`) are the config-side
  implementation of A5's discipline; F1/F2 fixes live here too.
- `architecture_review.md` §3.4: C2 is the concrete plan for that finding.
- The config-as-data strength (architecture_review §2) is reaffirmed — no change to the data model.
</content>
