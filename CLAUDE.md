# CLAUDE.md

Guidance for working in the IntraPaint codebase.

## What this is

IntraPaint is a free/open-source desktop image editor built on **PySide6 (Qt)**. It combines
conventional digital painting and editing tools with AI image generation and inpainting via Stable
Diffusion backends (ComfyUI, Forge/Automatic1111 WebUI). Python **3.11+**, targeting Windows and
Linux (macOS works with manual setup/compilation).

## Running

```
pip install -r requirements.txt
python IntraPaint.py            # --help for options; --mode selects the generation backend
pip install -r requirements-dev.txt   # for development: adds pytest, pylint, pyinstaller and pur
```

- On launch, `IntraPaint.py` auto-builds the Cython `image_fill` module if it's missing. To build it
  manually: `python setup.py build_ext --inplace`. The build output is gitignored; don't commit it.
- Dependency versions are pinned exactly. Dependabot proposes bumps for most of them; numpy,
  setuptools and pyinstaller are bumped by hand with `pur` (`.github/dependabot.yml` explains why).
- AI features need a running Stable Diffusion client (ComfyUI / Forge / A1111) with `--api` enabled.
  Without one, all manual editing tools still work.
- `IntraPaint_server.py` is a separate, legacy GLID-3-XL generation server (see "Legacy" below).

## Architecture

- **Entry point:** `IntraPaint.py` sets up logging/translations/import paths, then constructs
  `AppController`.
- **`src/controller/app_controller.py` — `AppController`** is the central coordinator: config init,
  image data (`ImageStack`), main window, menu structure, tool controller, generator selection,
  image I/O, and settings. Most cross-cutting behavior routes through here. It's large (~1500 lines);
  `src/image/layers/image_stack.py` (~1700) is the other gravitational center.
- **`src/controller/image_generation/`** — pluggable image generator backends behind a common
  interface (`sd_comfyui_generator`, `sd_webui_generator`, `null_generator`, `test_generator`, the
  GLID ones). The active generator is chosen by availability and the `--mode` flag.
- **`src/api/`** — client code for external backends: `comfyui/`, `webui/`, `controlnet/`.
- **`src/image/`** — image model: `layers/` (layer stack, groups, transforms), `mypaint/`
  (libmypaint brush engine bindings), `filter/`, `brush/`.
- **`src/tools/`** — the editing tools (brush, selection, text, shapes, fill, etc.).
- **`src/ui/`** — Qt UI: `window/`, `panel/`, `modal/`, `widget/`, `input_fields/`, `layout/`,
  `graphics_items/`.
- **`src/util/`** — helpers, including `visual/image_fill` (Cython-compiled).

## Config system (important)

Config is JSON-backed and typed, with `get()` / `set()` / `connect()` (signal on change).

- **`resources/config/*.json` are the source of truth** for what options exist and what they do.
  When adding or changing a config option, edit the relevant definition file there:
  - `application_config_definitions.json` → `AppConfig` (application settings)
  - `cache_value_definitions.json` → `Cache` (persisted state/values)
  - `key_config_definitions.json` → `KeyConfig` (keybindings)
  - `a1111_setting_definitions.json` → `A1111Config`
- `src/config/config_from_key.py` maps a key to its owning config singleton. Each config class is a
  singleton accessed like `AppConfig().get(key)`. A missing key raises `KeyError` at runtime.
- Singletons (the config classes, `UndoStack`) bind to the arguments of their first construction and
  ignore them afterwards, so `AppConfig('other.json')` returns the existing instance. `conftest.py`
  relies on this to back every test's config with temporary copies.

## Conventions

- **Translate all user-facing strings.** Wrap them in the Qt translation helper — files define a
  `TR_ID` and a local `_tr()` wrapper around `QApplication.translate`. Follow the existing pattern in
  the file you're editing; don't emit raw user-visible text. Pass `_tr` a single-quoted or
  triple-double-quoted literal: `scripts/build_translations.py` only extracts `_tr('` and `_tr("""`.
- Match the surrounding code's style, naming, and structure.

## Testing

- Run the whole suite headlessly from the CLI with `pytest` (or `python -m pytest`), after installing
  `requirements-dev.txt` and building `image_fill` (tests import it). `pytest.ini` scopes collection
  to `test/`. `conftest.py`:
  - forces Qt's offscreen platform before PySide6 loads, so no display is required. Override with
    `QT_QPA_PLATFORM=xcb pytest ...` to watch a test render.
  - creates the config singletons from temporary copies of `test/resources/*_test.json` before
    collection, so tests can't rewrite the committed fixtures.
  - fails any test that opens a modal dialog or menu, which would otherwise block forever offscreen.
    Mock the dialog, or avoid the code path.
- Tests are `unittest.TestCase` classes in `test/`, named `<name>_test.py`. Test `setUp` methods
  `chdir` up to a directory named `IntraPaint`, so the checkout must have that name.
- Tests share one process, so state left in a singleton (config values, the undo stack) leaks into
  later tests. Reset it in `setUp` the way the existing tests do. Write test output to a temporary
  directory, never the working tree.
- CI (`.github/workflows/ci.yml`) runs on every push and pull request: the suite on Python 3.11-3.14,
  plus the lint check below. Its `ci` job is the single check to require for merging.
- Coverage is sparse (14 test files) — treat it as a partial safety net, not an authoritative gate.
  The full run takes about 90 seconds.

## Type checking

The codebase aims to be well-typed, but strict mypy cleanliness isn't fully enforced — numpy, C
bindings, and one-off cases make some gaps unavoidable. mypy is run manually from time to time to fix
what's feasible. Improving typing is welcome but not a priority; don't block work on a clean mypy run.

## Lint

`scripts/pylint.sh` shows the full report (uses `.pylintrc`). Keep new code clean against it.

`python scripts/pylint_check.py` is CI's lint gate. The code isn't pylint-clean yet, so it fails only
when a file gains messages beyond `scripts/pylint_baseline.json`, or when fixed messages leave the
baseline too high. After fixing messages, rerun it with `--update-baseline` and commit the baseline.
Run it with Python 3.13: the baseline is only valid for the version it was generated with.

## Git & releases

- **Hard rule:** `integration` is the development branch. Changes only reach it via PR; direct pushes
  are blocked. Branch from `integration` and target PRs at it.
- **Hard rule:** `master` is only updated via a PR from `integration`, when creating a new release.
  Never open a PR from any other branch into `master`.
- The many other side branches (`comfyui`, `sd-windows`, `zoomMode`, `dev`, etc.) are
  experiments/one-offs — ignore them.
- Agents may commit and push to their working branch, open PRs, and create GitHub issues without
  asking first. A bug found during other work gets fixed in the same pass if the fix is trivial, and
  otherwise gets an issue saying what was observed, how to reproduce it, and what's ruled out.

## Tracking open work

- Open work lives only in [GitHub issues](https://github.com/centuryglass/IntraPaint/issues).
- Open issues are usually already in context. The `SessionStart` hook (`.claude/hooks/session-start.sh`)
  runs `scripts/issues.py`, which writes `.claude/cache/issues/` (`index.md` plus one file per issue) and
  prints the index. The cache is generated and gitignored; never edit it or treat it as the source of
  truth. `scripts/issues.py`'s docstring covers the fetch paths and `INTRAPAINT_ISSUES_TOKEN`.
- When the hook produced nothing (rate-limited, no token, or an agent that doesn't run Claude Code
  hooks), build the cache by hand before concluding no issue covers something: fetch the issue list with
  whatever tool you have (the GitHub MCP `list_issues`, `gh issue list --json ...`), save it as JSON, run
  `python3 scripts/issues.py --from-json <path>`, then read `.claude/cache/issues/index.md`.

## Cloud sessions

`.claude/hooks/session-start.sh` refreshes the issue cache in every session (see "Tracking open work").
At the start of a Claude Code on the web session it also installs the system libraries CI installs,
creates `.venv` with Python 3.13 and `requirements-dev.txt`, builds `image_fill`, and puts `.venv/bin`
first on `PATH`, so `pytest` and `scripts/pylint_check.py` work without further setup.

## Planning docs

`doc/analysis+plans/` is preliminary analysis written by an earlier model. Verify its claims against
the code before acting on them, and override its recommendations when the evidence points elsewhere.

## Legacy / don't-touch

- **`src/glid_3_xl/`** and the GLID-3-XL generators/server are legacy. Assume they won't be touched
  unless something there is actively broken.
- The project root contains a few vendored/symlinked library directories (e.g. `latent-diffusion`,
  `taming-transformers`, `pyspacenav`, `lib`, `colabFiles`) that are not part of the app's own source
  — don't treat them as code to modify.

## Packaging

- `scripts/build.sh` → builds the Cython extension then runs `pyinstaller IntraPaint-linux.spec`
  (Windows uses `IntraPaint.spec`). Output lands in `dist/`. `scripts/clean.sh` removes `build/` and
  `dist/`.
