# IntraPaint codebase map — shared substrate for analysis reports

**Purpose:** a single orientation doc so each analysis/plan report can build on a common
understanding instead of re-deriving it. Read this first; cite it rather than re-mapping the
tree. Pair it with `_decisions_ledger.md` (settled calls not to re-open).

**Confidence markers:** unmarked statements are verified from source or `CLAUDE.md`. `[inferred]`
= reasoned from structure/naming, not line-by-line confirmed — verify before relying on it for a
consequential recommendation.

---

## 1. What it is (one paragraph)

IntraPaint is a PySide6 (Qt) desktop image editor combining conventional painting/editing tools
with Stable Diffusion generation & inpainting via pluggable backends (ComfyUI, Forge/A1111).
Python 3.11+, Windows + Linux primary (macOS manual). Entry point `IntraPaint.py` (222 lines):
sets up logging/translations, auto-builds the Cython `image_fill` module if missing, then
constructs `AppController`. AI features need a running SD backend with `--api`; without one, all
manual tools still work.

## 2. Gravitational centers (where the mass and risk concentrate)

| Module | Lines | Role |
|---|---|---|
| `src/image/layers/image_stack.py` | 1705 | The layer-tree model + most editing operations (canvas resize, crop, merge, copy/paste/clear-selected, generation area). The heaviest single file. |
| `src/controller/app_controller.py` | 1536 | Central coordinator: config init, ImageStack ownership, main window, menu structure, tool controller, generator selection, image I/O, settings. |
| `src/config/config.py` | 660 | Typed JSON-backed config base (get/set/connect/options/persistence). |
| `src/image/layers/layer.py` | 592 | Base `Layer` contract inherited by every layer type. |
| `src/ui/window/main_window.py` | 572 | Top-level window + panel/dock layout. |
| `src/controller/tool_controller.py` | 310 | Tool registry, active-tool state, event routing, hotkey + delegation. |
| `src/ui/image_viewer.py` | 311 | Canvas widget: renders the stack, zoom/pan, widget↔scene coordinate mapping. |

Most cross-cutting behavior routes through `AppController` and `ImageStack`.

## 3. Layout of `src/`

- **`controller/`** — `app_controller` (coordinator), `tool_controller`, `spacenav_manager`,
  and `image_generation/` (the pluggable generator backends).
- **`config/`** — `config.py` base + four singletons (`AppConfig`, `Cache`, `KeyConfig`,
  `A1111Config`) + `config_entry` + `config_from_key`. Backed by the four
  `resources/config/*_definitions.json` files, which are the source of truth for what options
  exist.
- **`image/`** — the image model:
  - `layers/` — `layer` (base), `image_layer`, `layer_group`, `selection_layer`, `text_layer`,
    `transform_layer`, `transform_group`, `image_stack`, `image_stack_utils`.
  - `filter/` — `filter` (base `ImageFilter`) + blur/brightness_contrast/invert/posterize/
    rgb_color_balance/saturation/sharpen. PIL-backed; applied per-layer with selection/active
    masking; undoable; async via `AsyncTask`.
  - `brush/` — brush engines: `layer_brush` (base), `qt_paint_brush`, `mypaint_layer_brush`,
    `smudge_brush`, `clone_stamp_brush`, `filter_brush`.
  - `mypaint/` — libmypaint bindings + tile/surface machinery.
  - `open_raster.py`, `text_rect.py`, `composite_mode.py`.
- **`tools/`** — 20 tools on `base_tool.BaseTool`: draw/brush/eraser/fill/filter/smudge/clone/
  eyedropper/text/shape/transform + selection tools (brush/fill/free/shape) + generation-area.
- **`api/`** — external backend clients: `comfyui/` (node-graph workflow builders),
  `webui/` (A1111/Forge request/response bodies), `controlnet/` (backend-agnostic CN model),
  plus `webservice.py` / `a1111_webservice.py` / `comfyui_webservice.py` HTTP layers.
- **`ui/`** — `window/`, `panel/` (incl. `layer_ui/`, `tool_control_panels/`, `generators/`),
  `modal/`, `widget/` (incl. `color_picker/`), `input_fields/`, `layout/`, `graphics_items/`,
  `image_viewer.py`.
- **`util/`** — helpers: `undo_stack` (see ledger), `parameter`, `validation`, `math_utils`,
  `key_code_utils`, `cached_data`, `async_task`, `menu_builder`, `application_state`,
  `arg_parser`, `singleton`, and `visual/` (geometry, image_utils, image_fill (Cython),
  image_format_utils, pil_image_utils, shape_mode, contrast_color, display_size, ...).
- **`glid_3_xl/`** — legacy GLID-3-XL. **Don't touch** unless actively broken (per CLAUDE.md).

## 4. Cross-cutting patterns (the ones every report will hit)

- **Singletons** (`metaclass=Singleton`, from `util/singleton`): `AppConfig`, `Cache`,
  `KeyConfig`, `A1111Config`, `UndoStack`, `AppStateTracker` (`util/application_state`). Global
  mutable state accessed as `AppConfig().get(...)` etc. Tests reset them via `._reset()`.
- **Config-as-data**: options are defined in JSON, not code. Each key `foo` becomes a class
  attribute `Class.FOO == 'foo'` (dynamically injected at load; there are hand-maintained typing
  stub lists, e.g. in `key_config.py`). `get()/set()/connect()` with change signals; `set()`
  can run off the main thread and writes JSON via a `QTimer` (or directly if off-thread).
- **Undo model**: reversible edits go through `UndoStack().commit_action(do, undo, type, ...)`;
  property setters on `Layer` register undo entries and emit signals, while parallel `set_*`
  functions mutate without undo. Grouping via `combining_actions`, coalescing via `last_action`.
  (Full analysis + replacement plan in `UndoStack.md`.)
- **Layer signals**: `Layer` emits `content_changed`, `visibility_changed`, `opacity_changed`,
  `size_changed`, `composition_mode_changed`, `z_value_changed`, `lock_changed`, `name_changed`.
  `LayerGroup` adds `layer_added/removed`, `bounds_changed`, `isolate_changed`. `ImageStack`
  re-broadcasts stack-level versions. UI + tools subscribe heavily.
- **Rendering**: layers composite through a QGraphicsScene/QGraphicsView pipeline
  (`ui/graphics_items/`, `image_viewer`). Groups support isolate + nested transforms; the render
  path is exercised by golden-image tests. `[inferred: partial-alpha compositing glitches noted
  in TODO stem from this pipeline.]`
- **Translation**: user-facing strings wrap `QApplication.translate` via a per-file `TR_ID` +
  local `_tr()`. Every new user-visible string must follow this.
- **Async**: off-thread work via `util/async_task.AsyncTask` (filters, generation). Results are
  applied back on the main thread / via signals. This is the main concurrency surface.
- **Selection layer**: a single always-present `SelectionLayer` (an `ImageLayer` subclass) is the
  mask for inpainting and every "selection only" edit. Documented invariant: pixels are either
  fully transparent or the selection color (effectively 1-bit), backed by a full-size bitmap
  (the inefficiency called out in `open_questions.txt`).

## 5. Generation backends (pluggable)

`controller/image_generation/`: `image_generator` (base) → `sd_generator` (SD shared) →
`sd_comfyui_generator`, `sd_webui_generator`; plus `null_generator` (no backend, manual editing
only), `test_generator` (deterministic, used by `--mode mock` in tests), and the legacy GLID
generators. Active backend chosen by availability + `--mode`.

- **ComfyUI path**: `api/comfyui/` builds a JSON node-graph workflow. `ComfyNodeGraph` assembles
  `ComfyNode`s (keys start at "3"); `DiffusionWorkflowBuilder` emits txt2img/img2img/inpaint
  workflows; separate upscale + preprocessor-preview builders. Pure/deterministic — server-free
  to test.
- **WebUI path**: `api/webui/` builds request bodies + parses responses (A1111/Forge REST).
- **ControlNet**: `api/controlnet/` models a unit (model + preprocessor + params + image)
  independent of backend; each backend serializes it its own way.

`[context: TODO.md leans toward making ComfyUI the default and downgrading A1111/Forge; the user
has a WIP standalone API library at ../sd-api-standalone intended to replace src/api.]`

## 6. Tooling, tests, build

- **Tests**: `unittest.TestCase` classes under `test/`, run headless via `pytest` (`conftest.py`
  forces Qt offscreen; `pytest.ini` scopes to `test/`). ~11 files today — sparse. `test-wip/` in
  the repo root holds an outline for a comprehensive suite (see its README + tiers). Golden-image
  comparison is the established pattern for pixel output. `geometry_utils_test.py` dominates
  runtime (~4 min).
- **Lint**: `scripts/pylint.sh` + `.pylintrc`. **Types**: mypy run ad hoc, not enforced.
- **Native/build**: Cython `util/visual/image_fill` (auto-built on launch or
  `setup.py build_ext --inplace`); libmypaint native libs per-platform; PyInstaller specs
  (`IntraPaint-linux.spec`, `IntraPaint.spec`); `scripts/build.sh`.
- **Docs**: workflow/usage docs under `doc/`; task backlog in `doc/TODO.md`; these analysis
  reports in `doc/analysis+plans/`.

## 7. Known rough edges relevant across reports (from TODO.md + observed)

- Responsive layout on small displays is fragile; display-size tracking can't detect OS toolbars.
- Transform tool: center-of-rotation + canvas↔panel field sync are buggy (redesign expected).
- Selection layer uses large bitmaps → lag on big images; outline vectorization occasionally
  fails to join sections.
- Partial-alpha compositing glitches `[inferred: QGraphicsView rendering]`.
- `QColor.isValidColor(str)` is deprecated in current PySide6, called in several places
  (`config.py`, `color_button.py`, `qt_paint_brush_tool.py`, `selection_outline.py`, …) → ~250
  warnings/run, will eventually hard-break on a Qt upgrade.
- All QImage indexing assumes little-endian.
- `AppConfig.max_undo` is unwired; `undo_in_progress` can stick True (see `UndoStack.md`).

## 8. Where to start reading, per report topic

- Architecture / config / concurrency / rendering: §2, §4; then `app_controller.py`,
  `image_stack.py`, `config.py`, `async_task.py`, `image_viewer.py` + `ui/graphics_items/`.
- Transform tool: `tools/layer_transform_tool.py`, `image/layers/transform_layer.py` +
  `transform_group.py`, `ui/panel/tool_control_panels/layer_transform_tool_panel.py`,
  `ui/graphics_items/transform_*`.
- Non-destructive layers / ORA: `image/open_raster.py`, `image/layers/text_layer.py`,
  `image/text_rect.py`.
- API library swap: `src/api/**` + `../sd-api-standalone`.
- Generation-area UX: `tools/generation_area_tool.py`, `image_stack.py` (generation area),
  `doc/` workflow docs.
- Packaging: `setup.py`, `*.spec`, `scripts/build.sh`, `src/image/mypaint/`,
  `util/visual/image_fill`.
- Testing: `test-wip/README.md`, existing `test/`, `conftest.py`, `pytest.ini`.
- Color subsystem: `ui/widget/color_picker/`, `ui/widget/color_button.py`, `Cache` color keys.
</content>
