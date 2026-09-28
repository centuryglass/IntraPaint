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
```

- On launch, `IntraPaint.py` auto-builds the Cython `image_fill` module if it's missing. To build it
  manually: `python setup.py build_ext --inplace`.
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

## Conventions

- **Translate all user-facing strings.** Wrap them in the Qt translation helper — files define a
  `TR_ID` and a local `_tr()` wrapper around `QApplication.translate`. Follow the existing pattern in
  the file you're editing; don't emit raw user-visible text.
- Match the surrounding code's style, naming, and structure.

## Testing

- Run the whole suite headlessly from the CLI with `pytest` (or `python -m pytest`). `conftest.py`
  forces Qt's offscreen platform before PySide6 loads, so no display is required; `pytest.ini`
  scopes collection to `test/`. Override with `QT_QPA_PLATFORM=xcb pytest ...` to watch a test render.
- Tests are `unittest.TestCase` classes in `test/`, named `<name>_test.py`.
- CI (`.github/workflows/test.yml`) runs the suite on PRs to `master` and on manual dispatch.
- Coverage is sparse (~11 test files) — treat it as a partial safety net, not an authoritative gate.
  The full run takes ~4 min, dominated by `geometry_utils_test.py`.

## Type checking

The codebase aims to be well-typed, but strict mypy cleanliness isn't fully enforced — numpy, C
bindings, and one-off cases make some gaps unavoidable. mypy is run manually from time to time to fix
what's feasible. Improving typing is welcome but not a priority; don't block work on a clean mypy run.

## Lint

`scripts/pylint.sh` (uses `.pylintrc`). Keep new code clean against it.

## Git & releases

- **Hard rule:** changes only reach `master` via PR, immediately before a release. The many side
  branches (`comfyui`, `sd-windows`, `zoomMode`, `dev`, etc.) are experiments/one-offs — ignore them.

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
