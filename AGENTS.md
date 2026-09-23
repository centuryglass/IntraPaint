# AGENTS.md

Rules for coding agents working in this repo. Human-facing docs are
[`README.md`](README.md) (what it is and how to install it) and the guides
under [`doc/`](doc/help_index.md). Open work lives in
[GitHub issues](https://github.com/centuryglass/IntraPaint/issues) and, for
older items, [`doc/TODO.md`](doc/TODO.md) - see "Tracking open work".

## How to use this file

- **This file is for facts that cross files, and most changes add nothing
  to it.** A bullet here earns its place by biting someone who is editing a
  *different* file than the one the fact lives in. Before adding one, ask:
  - Is it relevant only within one file?
  - Would opening that file to make the edit surface it anyway?
  - Would a reader be better served finding it there?

  A yes to any of these means the fact goes in that file's own docstring or
  comment (confirm it is there, or add it). Here it gets at most a one-line
  pointer.
- **Edit by replacing, not appending.** When a change makes a bullet wrong,
  rewrite that bullet; don't add a second one that corrects the first. When
  the code a bullet describes is gone, delete the bullet.
- **Code comments cite this file's headings and bold lead phrases by name**
  (`AGENTS.md, "Singletons bind on first construction"`). Renaming one
  breaks those pointers: grep the repo for the old phrase and fix every hit
  in the same change.
- **`CLAUDE.md` is a symlink to this file.** Edit `AGENTS.md`.

## What this is

IntraPaint is a desktop image editor (PySide6/Qt 6) that combines
conventional painting and layer editing with AI image generation. Generation
runs through an external backend - Stable Diffusion via the Forge/A1111
WebUI API or ComfyUI, or the legacy GLID-3-XL model - and the editor is
fully usable with no backend at all (`--mode none`).

It ships to end users as prebuilt PyInstaller executables for Windows and
Linux (the releases page), and runs from source on any platform with
Python 3.11+.

## Two audiences

The project is a tool people use first. Their images (`.ora` files with
layers), their config and their keybindings must survive an update, and the
editor must keep working when every optional dependency and AI backend is
missing.

It is also the maintainer's software engineering portfolio. That reader is
a reviewer skimming the repo, and they look for the signals of a work
sample: CI that gates merges, a reproducible release build, tests that would
catch a real regression, and docs that let them trust the process without
reading the source. The project was built solo, before any of that was in
place, and is being brought up to that standard incrementally.

- When a change is ambiguous between what users need and what the
  portfolio needs, flag the tension to the maintainer. Don't quietly
  resolve it in either direction.
- A process or documentation gap that matters only for portfolio value gets
  its own GitHub issue, not bundled invisibly into unrelated work.

## Commands

There is no CI yet, so these are the whole gate. Run them before pushing.

```sh
pip install -r requirements.txt            # core runtime deps
pip install -r requirements-dev.txt        # pyinstaller, pur, pytest
pip install -r optional-requirements.txt   # themes, SpaceMouse, GLID-3-XL local mode
python setup.py build_ext --inplace        # compile the Cython fill module (see "Build and packaging")
python IntraPaint.py                       # run from source; --help lists options
python IntraPaint.py --mode none --dev     # no AI backend, stray-window crash check on
QT_QPA_PLATFORM=offscreen python -m pytest test   # the test suite, headless
./scripts/pylint.sh                        # pylint over src/ with .pylintrc
python scripts/build_translations.py       # regenerate resources/translations/main.ts
pyinstaller IntraPaint.spec                # packaged build into dist/
```

- **Run everything from the repo root.** Resource paths resolve from
  `PROJECT_DIR` (`src/util/shared_constants.py`), but tests and scripts use
  paths relative to the working directory (`test/resources/...`,
  `resources/translations/main.ts`).
- **Tests need a display or `QT_QPA_PLATFORM=offscreen`.** Every test
  module creates the process-wide `QApplication` at import time. On a
  minimal Linux container PySide6 also needs system libraries (`libEGL`,
  `libGL`, `libxkbcommon`, `libfontconfig`) before it imports at all.
- **Pylint is the style authority** (`.pylintrc`, 120-column lines).
  `# type: ignore` comments exist for type-checker compatibility, but no
  type checker is configured or run.
- **Ask the maintainer before adding or upgrading a dependency.**
  `requirements.txt` is mostly unpinned, so a fresh install tracks
  upstream: prefer a version bound over code that works around an
  upstream break.

## Layout

- `IntraPaint.py`: the GUI entry point - argument parsing, logging, splash,
  translations, GLID-3-XL path fixes, then `AppController`.
- `IntraPaint_server.py`, `colabFiles/`: the standalone GLID-3-XL server
  and its Colab notebooks.
- `src/controller/`: `AppController` (app lifetime, menus, file IO),
  `ToolController`, and `image_generation/` (one `ImageGenerator` subclass
  per backend, plus `TestGenerator` for `--mode mock`).
- `src/api/`: HTTP clients for the WebUI and ComfyUI APIs, including
  ComfyUI node graph builders and ControlNet support.
- `src/image/`: the document model. `layers/` (`ImageStack`, layer and
  group types, the selection layer), `open_raster.py` (the `.ora` format),
  `mypaint/` (libmypaint bindings), `brush/`, `filter/`.
- `src/tools/`: one `BaseTool` subclass per editing tool.
- `src/ui/`: widgets, panels, windows and modal dialogs.
- `src/config/`: the `Config` base class and its four JSON-defined
  singletons (see "Config").
- `src/util/`: shared helpers. `visual/image_fill.py` is Cython source.
- `src/glid_3_xl/`: vendored GLID-3-XL model code, under its own `LICENSE`.
- `resources/`: runtime assets - config definitions, icons, cursors,
  brushes, translations. `resources/unused+draft/` is not loaded.
- `lib/`: prebuilt libmypaint binaries for Windows and Linux.
- `pyspacenav/`: a git submodule (SpaceMouse support), empty unless cloned
  with `--recursive`.
- `test/`: `unittest`-style tests run with pytest, mirroring `src/`, with
  fixtures in `test/resources/`.
- `doc/`: user guides, `CHANGELOG.md` and `TODO.md`.
- `scripts/`: developer shell and Python helpers.

## Conventions

- **Python 3.11 is the floor.** `IntraPaint.py` checks it at startup.
  `match` statements and `X | Y` unions are in use throughout.
- **Imports are absolute from the repo root** (`from src.util... import`).
  Nothing is installed as a package, so the working directory must be the
  repo root.
- **Optional dependencies never import statically.** Theme packages,
  `spnav`, `torch` and the GLID-3-XL stack go through
  `src/util/optional_import.py`'s `optional_import`/`check_import`, and
  every caller handles `None`. Base editing must run with only
  `requirements.txt` installed.
- **Every user-visible string is translatable.** A module with UI text
  declares `TR_ID` and a module-local `_tr` helper wrapping
  `QApplication.translate`; see "Translations".
- **Docstrings use numpydoc sections** (`Parameters`, `Returns`) where a
  function takes non-obvious arguments. Every module opens with a docstring
  saying what it is for.
- **Formatting:** four-space indent, single quotes, 120-column lines.
  Follow the file you're in.
- **Don't restyle vendored code.** `src/glid_3_xl/` and `colabFiles/` follow
  their upstream shape; change them only to fix a bug.
- **Tests are `unittest.TestCase` classes in `test/<mirrored path>/
  <module>_test.py`**, run through pytest. Fixture images live in
  `test/resources/test_images/`.
- **A bug found during unrelated work gets fixed or filed, never just
  noticed.**
  - Trivial to fix (a wrong assertion, an off-by-one, a stale comment or
    pointer): fix it in the same pass.
  - Needs real investigation or design, or touches code you weren't already
    changing: open a GitHub issue (see "Tracking open work") with what was
    observed, how to reproduce it, and what is ruled out.
  - "Trivial" is about the fix, not the effort spent finding it.

## Comments and docs

**Comments are reference, not advocacy.** A comment tells the next reader
what is true of the code as it stands, quickly. It does not defend a design
to a skeptic or argue against the version it replaced. These rules apply to
docstrings, code comments, this file, and everything under `doc/`.

- **Lead with the rule.** Line 1 of a docstring or comment is a standalone
  summary; a reader who stops there must lose no invariant.
- **One fact, one home.** State a fact fully where the thing is defined.
  Elsewhere, point or stay silent. A pointer names a symbol or a section
  title, never a position ("see `ImageStack.merge_layer_down`", not "see
  the comment above"), and it must resolve - check every `see X` before
  committing, because a dangling pointer is a confident-looking lie.
- **Pin to a declaration, not a region.** One comment describes one thing
  below it. Split a paragraph that describes several things and re-attach
  each piece.
- **Keep hazards, drop ghosts.**
  - A hazard warns that a change here breaks something there. Keep it, as
    the main clause.
  - A ghost is prose about a design the code doesn't have: an argument
    against an alternative, or a note about a prior state ("X used to live
    in Y"). The alternative exists only in git.
  - Keep a history note only where a reader would otherwise trip: a
    redirect, a permanent alias, a compatibility shim for old saved files.
  - Before finishing, sweep the lines you touched for "used to", "instead
    of", "rather than", "no longer", "anymore", "previously", "now". Most
    hits are ghosts.
- **Length tracks risk, and terse has a floor.** A few lines is the default.
  More is earned only where deleting a clause would let a careful reader
  introduce a real bug. Never delete a hazard to look terse - condense or
  relocate it.
- **No color.** Leave out measurements, machine names, incident narrative
  and closed issue numbers unless the reader needs them to act. Cite an
  issue only when it is open and the reader should follow it.
- **Plain declaratives.**
  - No shouting caps, and no conviction words: "exactly", "really",
    "deliberately", "on purpose", "load-bearing". Emphasis comes from
    position and structure.
  - One clause per sentence, and real lists for list-shaped content.
  - Reference symbols, not their current values (`MAX_UNDO`, not "fifty").
- **ASCII hyphens, not em dashes,** in comments and markdown.
- **User guides are user-facing.** `doc/` and `README.md` describe what a
  user sees; engineering detail belongs in docstrings or here.

## Things that will bite you

### Singletons and global state

- **Singletons bind on first construction.** `AppConfig`, `KeyConfig`,
  `Cache`, `A1111Config`, `UndoStack` and `AppStateTracker` use
  `src/util/singleton.py`'s `Singleton` metaclass, which ignores the
  arguments of every call after the first. `AppConfig('x.json')` after
  anything has called `AppConfig()` returns the instance bound to the
  user's real config file.
  - Tests construct each config with its `test/resources/*_test.json`
    path in `setUp`, then call `_reset()`. A module-level `AppConfig()`
    call that runs at import time would bind every test to the real user
    config instead.
  - `_reset()` exists for tests only.
- **Undoable edits go through `UndoStack`.** A change to the document
  (layer content, layer properties, the selection) is committed with
  `UndoStack().commit_action(action, undo_action, type)`, and a multi-step
  edit wraps its commits in `combining_actions(...)` so one undo reverts
  all of it. A direct mutation that skips the stack leaves undo history
  pointing at state that no longer matches.
- **Which controls are enabled is driven by `AppStateTracker`.** Widgets and
  actions register the app states they are valid in with
  `AppStateTracker.set_enabled_states` (`src/util/application_state.py`).
  `AsyncTask(..., set_loading_state=True)` sets `APP_STATE_LOADING` but
  never clears it; the caller restores the next state on every exit path,
  failures included, or the UI stays disabled.
- **Qt objects belong to the main thread.** `AsyncTask` runs work on the
  global `QThreadPool`; results return to the UI through its signals, never
  by touching widgets or `ImageStack` from the worker.

### Config

- **A config key is defined in JSON, not Python.** Each `Config` subclass
  reads `resources/config/<name>_definitions.json`, and `Config.__init__`
  sets an uppercase class attribute per key at runtime
  (`AppConfig.THEME == 'theme'`). Adding a key means:
  1. add its definition (type, default, label, category, tooltip) to the
     JSON file;
  2. add the uppercase name to the class's `# DYNAMIC PROPERTIES:` block,
     which exists only for linters and IDEs. `scripts/
     dynamic_import_typing.py <module>` regenerates it;
  3. run `scripts/build_translations.py`, which extracts each definition's
     label, tooltip, category and options.
- **Saved config files outlive the code.** Keys missing from a user's
  `config.json` are filled from defaults, and unknown keys are dropped on
  load. Renaming a key silently resets every user's value for it; treat a
  rename as a migration.
- **User data lives under `platformdirs`**, not the repo: `DATA_DIR` and
  `LOG_DIR` in `src/util/shared_constants.py`. Importing that module creates
  both directories as a side effect.

### Translations

- **`scripts/build_translations.py` finds strings by text, not by parsing.**
  It rewrites the literal prefixes `_tr('` and `_tr("""` to
  `QApplication.translate('<TR_ID>', ...)` in temporary copies, then runs
  `pylupdate6`. So:
  - `TR_ID` must be assigned as `TR_ID = '<context>'` (single quotes).
  - A `_tr` call whose argument starts any other way (`_tr("x")`, a
    variable, an f-string) is never extracted and never translated.
  - `_tr` placeholders are filled with `.format(...)` after translation;
    an f-string bakes the value in before lookup.
- **Config strings use their definition file's path as context**, derived in
  `Config.__init__`. Moving a definitions file orphans its translations.
- **`resources/translations/*.qm` is loaded at startup** by
  `IntraPaint.py`, which asserts each one loads.

### Windows and widgets

- **`--dev` crashes on any unexpected top-level window.** `IntraPaint.py`'s
  `WindowEventFilter` exits when a parentless widget is shown that is not in
  its allowlist, which catches widgets that lose their parent and flash up
  as stray windows. A new top-level window or modal class must be added to
  that `isinstance` tuple, or every `--dev` run crashes on first show.

### Image data

- **QImage pixel indexing assumes little-endian byte order.** Numpy views
  of `Format_ARGB32` data (`src/util/visual/image_utils.py`) index channels
  as BGRA. A big-endian platform breaks every one of those call sites.
- **`.ora` is the lossless save format.** `src/image/open_raster.py` writes
  layers, groups, blend modes and text layers, and must keep reading files
  written by earlier releases. Other formats flatten.

### Build and packaging

- **`src/util/visual/image_fill.py` is Cython source in pure-Python mode.**
  Importing the `.py` directly raises `ImportError('Missing image_fill
  cython build')`; only the compiled extension works.
  - `IntraPaint.py` runs `setup.py build_ext --inplace` on launch when the
    import fails. Tests do not, so build it before running them.
  - The tracked `.so` is built for one CPython version (`cpython-313`). A
    local build writes `image_fill.c` and a `.so` for your interpreter
    beside it; don't commit them by accident.
  - The file compiles with Cython 3.2. Cython 3.3 rejects the
    `cython.declare` memoryview assignments.
- **`IntraPaint.spec` is the release build definition.** PyInstaller bundles
  `resources/` and `lib/` as data and needs `hiddenimports` for any module
  loaded dynamically (`src.tools.mypaint_brush_tool`). A module imported
  only by name at runtime works from source and is missing from the
  executable.
- **The bundle runs different startup code than source.**
  `is_pyinstaller_bundle()` (`src/util/pyinstaller.py`) skips the Cython
  build and the GLID-3-XL path fixes, and drops `glid-local` and `mock` from
  `--mode`'s help, since the bundle carries no `torch`. Test a
  bundling-sensitive change from a PyInstaller build, not only from
  source.
- **libmypaint is loaded from `lib/` or the configured
  `LIBMYPAINT_LIBRARY_DIR`.** The MyPaint brush tool is unavailable when
  neither loads, and the rest of the editor must not depend on it.

### Testing

- **The working directory must be named `IntraPaint`.** Test `setUp`
  methods walk up with `os.chdir('..')` until the directory basename is
  `IntraPaint`. A checkout cloned under another name fails every such test.
- **Tests share one `QApplication` and every singleton** across the process,
  so state a test leaves in a config or the undo stack leaks into the next
  one. Reset it in `setUp` the way the existing tests do.
- **The suite writes into the working tree.** Configs save back to their
  `test/resources/*_test.json` files, and `app_controller_test.py` and
  `image_fill_test.py` leave `save_test_*` and `mask_*.png` files in the
  repo root. Restore and delete
  them before staging; stage by explicit path.
- **Byte-exact image assertions depend on library versions.** Pillow, numpy
  and Qt versions are not pinned, and a rounding change upstream fails a
  pixel comparison with no code change here. Compare with a tolerance
  unless the operation is lossless by definition.
- **A test must never open a blocking dialog.** A modal `exec()` waits
  forever under `offscreen`. Patch the dialog or the file picker.
- **A green test that cannot fail is worse than none.** When you add or
  change one, break the code it covers and confirm it fails.

### Releases

- **Releases are cut by hand.** A release is a version heading in
  `doc/CHANGELOG.md` plus a GitHub release carrying the PyInstaller
  executables. Nothing automates either, so a user-visible change adds its
  changelog line in the same PR.

## Tracking open work

- **New work goes in
  [GitHub issues](https://github.com/centuryglass/IntraPaint/issues).**
  `doc/TODO.md` holds the backlog written before issues were in use; don't
  add to it.
- **A found bug that isn't a same-pass fix opens an issue**: what was
  observed, how to reproduce it, and what is ruled out.
- **A fact worth knowing is not a task.** It belongs in the owning module's
  docstring, or here.
- **A PR closing an issue says `Closes #NN` in its description.**

## Working with GitHub

- **The default branch is `master`.** Branch from it and open PRs against it.
- **Don't ask whether to subscribe to a PR you just opened.** If the
  maintainer wants it watched, they'll say so.
- **An issue or comment an AI agent writes under the maintainer's account
  ends with a footer marking it as AI-generated**, e.g.
  `_Drafted with AI assistance._`, so it doesn't read as the maintainer
  arguing with themselves. Keep it tool-agnostic ("AI assistance", never a
  product name), since the maintainer uses more than one agent.
