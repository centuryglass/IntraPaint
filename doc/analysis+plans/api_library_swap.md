# OQ5 — Replacing `src/api` with the `intrapaint_api` standalone library

Cross-repo migration analysis. Reads on top of `_codebase_map.md` (§5 generation backends),
`_decisions_ledger.md`, `architecture_review.md` §5, and `concurrency_model.md` (the threading
contract the library must fit).

Two repos are referenced:
- **IntraPaint** — `/home/anthony/Workspace/ML/IntraPaint` (cited `src/...:line`).
- **Library** — `/home/anthony/Workspace/ML/sd-api-standalone`, package `intrapaint_api`
  (cited `lib:intrapaint_api/...:line`).

`[inferred]` marks reasoning not confirmed line-by-line. **Analysis only — no code was modified in
either repo.**

---

## 1. Summary verdict

**The swap is feasible and desirable, and most of the hard work is already done.** The library is a
direct extraction of `src/api` (shared git ancestry — `lib` commit `aec654c "Initial commit"` is a
copy of `src/api`) that has since been decoupled along exactly the two axes that make `src/api`
architecturally awkward: it **removed the Qt dependency** (QImage→PIL, QSize→`Size`, no cv2/numpy)
and **removed the hidden config layer** (Cache/AppConfig reads → explicit pydantic params). Both
changes align with directions the other reports already recommend (arch §5 api-swap; A4's
Config/Parameter→UI dependency inversion).

The method surfaces are near-identical supersets: the library's `ComfyUiWebservice` and
`A1111Webservice` have the same public method set as `src/api`'s plus new `submit_*` entry points
(§3). So this is **not a reimplementation to integrate against — it's the same client with its
IntraPaint-specific couplings lifted out to the caller.**

**The single biggest obstacle is not the API surface — it's the two couplings the library
deliberately severed, which IntraPaint must now supply itself:**

1. **The config→params translation.** `src/api` reads generation parameters straight out of
   `Cache()`/`AppConfig()` in five files (§2). The library requires those parameters to arrive as
   populated pydantic models (`DiffusionParams` / `DiffusionRequestBody` / `ComfyUIDiffusionParams`).
   Building that "Cache → pydantic" adapter is the bulk of the migration work. It is also a *net
   improvement* (removes hidden global state from the API boundary), so it's effort well spent, not
   throwaway glue.

2. **The Qt-bound ControlNet UI piece.** `src/api/controlnet/control_parameter.py` is a
   `QObject`/widget factory (imports `PySide6` + `src.ui.input_fields`, control_parameter.py:5-15)
   that has **no equivalent in the library** — the library kept the *data* (`ParameterDef`, a pydantic
   model, lib:.../controlnet/controlnet_preprocessor.py:21) but dropped the widget. IntraPaint's
   ControlNet panel and image-scale modal depend on the widget, so a small Qt widget factory must be
   built IntraPaint-side that consumes `ParameterDef`.

Neither obstacle is a blocker; both are bounded. The async model reconciles cleanly (§5) — the
library's `GenerationHandle` slots into IntraPaint's existing `AsyncTask` envelope with *less*
bespoke code than today, and without violating the main-thread discipline from `concurrency_model.md`.

**Recommendation: rebind the generators directly to `intrapaint_api` behind thin IntraPaint-side
adapters (params / image / auth / progress), delete the backend-client half of `src/api`
wholesale, and relocate only the Qt-bound UI pieces into `src/ui`. Do NOT build a compatibility shim
that preserves `src/api`'s Cache-reading signatures — that would fight the library's core design.**

---

## 2. The current seam — what generators call into `src/api`

Only **six** files outside `src/api` import it (verified, full list):

| Consumer | Imports from `src/api` | Role |
|---|---|---|
| `src/controller/image_generation/sd_generator.py:12-17` | `AuthError`, controlnet model/preprocessor/unit/constants, `WebService` | Shared SD generator base |
| `src/controller/image_generation/sd_comfyui_generator.py:11-18` | `ComfyUiWebservice`, `AsyncTaskProgress/Status`, `ImageFileReference`, ultimate-upscale node name, controlnet, `WebService` | ComfyUI backend |
| `src/controller/image_generation/sd_webui_generator.py:12-16` | `A1111Webservice`, `AuthError`, `ULTIMATE_UPSCALE_SCRIPT`, controlnet, `WebService` | A1111/Forge backend |
| `src/config/a1111_config.py:7` | `A1111Webservice` (type only, `load_all`/`save_all`, a1111_config.py:34,81) | A1111 settings sync |
| `src/ui/panel/controlnet_panel.py:14-19` | controlnet constants/model/preprocessor/unit + `webui_constants` | ControlNet UI |
| `src/ui/modal/image_scale_modal.py:12-17` | `control_parameter.DynamicControlFieldWidget`, controlnet model/preprocessor/unit, `webui_constants` | Upscale-with-CN modal |

So the seam is **the three SD generator classes** (the real turn of the swap) plus **two UI files +
one config file** that lean on the ControlNet data model and the one Qt widget.

**How a generation actually runs today** (the pattern the swap must preserve):
`ImageGenerator.start_and_manage_image_generation` (image_generator.py:140) wraps the work in an
`AsyncTask` (`_AsyncInpaintTask`, image_generator.py:174) constructed **on the main thread**, whose
`generate()` body runs on a `QThreadPool` worker. Inside the worker:
- ComfyUI: `self._webservice.txt2img/img2img/inpaint(...)` queues a job, then
  `_repeated_progress_check` (sd_comfyui_generator.py:459-508) **blocks in a websocket + poll loop**
  (`webservice.check_queue_entry`, `thread.usleep`, `external_status_signal.emit({'progress': ...})`),
  then `webservice.download_images(...)` (sd_comfyui_generator.py:634).
- WebUI: the `A1111Webservice.txt2img/img2img` call blocks until images return.

Progress is emitted via a Qt `Signal` on the `AsyncTask` (sender has main affinity → delivered on
main, per `concurrency_model.md` §2). Results are handed to the UI via
`_cache_generated_image` → `QTimer.singleShot(0, self._window, ...)` (image_generator.py:258-265),
i.e. marshalled to the main thread. **This envelope is exactly where the library's handle plugs in.**

**Crucially, `src/api` today is NOT Qt-free or config-free:**
- Config reads live *inside* `src/api`: `Cache`/`AppConfig` are read in `a1111_webservice.py:248,340`,
  `comfyui/diffusion_workflow_builder.py:38`, `comfyui_webservice.py:36`,
  `webui/diffusion_request_body.py:14-15`, `webui/controlnet_webui_utils.py:18`.
- Qt/UI reaches *into* `src/api`: `a1111_webservice.py:32` imports `src.ui.modal.login_modal`,
  `diffusion_workflow_builder.py:39` imports `src.ui.window.extra_network_window` (`LORA_KEY_PATH`),
  and `control_parameter.py:5-15` is a full `QObject` + `src.ui.input_fields` widget factory.
- `QImage`/PySide6 appear in 10 `src/api` files (grep). Image encode/decode uses `QImage`
  (`a1111_webservice.py:33` → `src.util.visual.image_utils.image_to_base64/qimage_from_base64`).

The library severs all three. That is the whole point of the migration, and the whole cost of it.

---

## 3. Library capability survey

**Package** (`lib:intrapaint_api/`): mirrors `src/api`'s tree, plus a new **`api/shared_data/`**
backend-agnostic layer and per-backend **generation handles**. Runtime deps: `pillow`, `requests`,
`platformdirs`, `websocket-client`, `pydantic` (lib:requirements.txt). **Python 3.11+.** No Qt, no
numpy, no cv2 (lib:README.md "Design notes").

**Two hard constraints** (lib:CLAUDE.md): (a) no Qt/cv2/numpy — images are `PIL.Image` normalized to
RGBA, sizes use `util/geometry.Size`, `_tr()` is a no-op shim; (b) no config layer — params are
explicit pydantic models, never read from a singleton.

**API surface (method-set diff vs `src/api`):**
- `ComfyUiWebservice`: identical public set **plus** `submit_txt2img/img2img/inpaint`
  (lib:.../comfyui_webservice.py:625-635) returning a `ComfyGenerationHandle`, `remove_from_queue`,
  and pydantic-shaped internals. The low-level `txt2img/img2img/inpaint(diffusion_params)` still
  exist (lib:396,441,457) but now take a `DiffusionParams` model instead of reading Cache.
- `A1111Webservice`: identical set **plus** `submit_txt2img/img2img`
  (lib:.../a1111_webservice.py:120,135) returning a `WebUIGenerationHandle` via a lazily-created
  `WebUIDispatcher` (lib:113-117). Low-level blocking `txt2img/img2img(request_body)` remain
  (lib:240,208).

**The backend-agnostic generation handle** (the crux — lib:.../shared_data/generation_handle.py):
- Design principle: *"async is the primitive, blocking is derived"* (module docstring). Abstract
  `GenerationHandle` with `poll() -> GenerationProgress`, `_build_result() -> GenerationResult`,
  `cancel() -> bool`, and a concrete `wait(timeout, poll_interval, on_progress)` implemented once in
  terms of `poll()` (generation_handle.py:145-176).
- `GenerationStatus` (PENDING/ACTIVE/FINISHED/FAILED/CANCELLED/NOT_FOUND, with `is_terminal`),
  `GenerationProgress` (`progress∈[0,1]`, `queue_index`, `eta_seconds`, `preview: PIL.Image`,
  `text_info`), `GenerationResult` (`images: list[PIL.Image]`, `info`, `seed`, `task_id`).
- **ComfyUI handle** (lib:.../comfyui/comfyui_generation_handle.py): `poll()` wraps
  `check_queue_entry`, `_build_result()` downloads finished refs, `cancel()` drops a queued job or
  interrupts the running one — and *infers* CANCELLED (ComfyUI has no cancelled state) and smooths
  post-submit registration lag (docstring lines 14-24). **No client-side thread — the server is the
  queue.**
- **WebUI handle** (lib:.../webui/webui_generation_handle.py): because the WebUI blocks and can't
  cancel a *specific queued* job, the library runs a **client-side single-slot dispatch queue**
  (`WebUIDispatcher`, a background daemon thread, lines 227-339). A submitted job sits PENDING
  (unsent, instantly cancellable) until the worker POSTs it (ACTIVE → interrupt-cancellable). It even
  waits for the server to drain before dispatching (`_await_server_idle`). This *lifts WebUI up to
  ComfyUI's inspectable/cancellable-queue capability* rather than dragging the interface down.

**Data-type boundary:** `PIL.Image` in and out, RGBA-normalized (lib:util/visual/image_utils.py);
`Size` value class instead of `QSize`. Auth via a `credentials_provider` callback instead of a Qt
dialog (lib:README §Authentication; `WebService._handle_auth_error`).

**ControlNet:** backend-agnostic `ControlNetUnit` + `ControlNetModel` + `ControlNetPreprocessor`
under `shared_data/controlnet/`, with the UI-facing parameter metadata preserved as a **pydantic
`ParameterDef`** (lib:.../controlnet_preprocessor.py:21) and `PreprocessorParams` (line 70).
Serialization round-trips pinned by `tests/unit/test_controlnet_serialization.py`.

**Maturity:** offline unit tests cover workflow building, request bodies, controlnet serialization,
the ComfyUI handle, and preprocessor params (lib:tests/unit/, 6 files); live integration tests cover
a1111 + comfyui generation/controlnet/metadata/auth/async (lib:tests/, 10 files). Self-described
status (lib:README "Status", CLAUDE.md): *core txt2img/img2img/inpaint/ControlNet work end-to-end on
both backends; the ComfyUI node classes' pydantic migration and tiled upscaling are still in
progress.* **→ Treat tiled/ultimate upscaling as the one path to verify carefully before deleting the
`src/api` equivalent.**

---

## 4. Gap analysis

For each capability IntraPaint relies on from `src/api`, does the library cover it?

| IntraPaint need | Library coverage | Notes |
|---|---|---|
| ComfyUI txt2img/img2img/inpaint | **Full** | `submit_*` → handle, or low-level `*(diffusion_params)` (lib:comfyui_webservice.py:396-635) |
| WebUI txt2img/img2img/inpaint | **Full** | `submit_*` → handle, or blocking `*(request_body)` (lib:a1111_webservice.py:120-240) |
| `DiffusionWorkflowBuilder` / `ComfyNodeGraph` (subsume `src/api/comfyui`) | **Full** | Present verbatim + params now pydantic (`ComfyUIDiffusionParams`); `src/api/comfyui/**` can be **deleted** |
| WebUI request/response bodies (`src/api/webui`) | **Full** | Present; `DiffusionRequestBody` now pydantic; deletable |
| ControlNet data model (unit/model/preprocessor/constants) | **Full** | Moved to `shared_data/controlnet/`; identical semantics |
| ControlNet **UI widget** (`control_parameter.DynamicControlFieldWidget`) | **Missing (by design)** | Library keeps `ParameterDef` data only → **build a Qt widget factory IntraPaint-side** |
| Progress / preview streaming | **Full, improved** | Unified `GenerationProgress` (progress/eta/preview/text); replaces bespoke `_repeated_progress_check` |
| Cancellation | **Full, improved** | Uniform `handle.cancel()` for both backends (today only ComfyUI has `cancel_generation`, sd_comfyui_generator.py:344) |
| Auth (A1111 login) | **Partial — mechanism changed** | `credentials_provider` callback replaces `LoginModal`; IntraPaint supplies a main-thread-marshalling provider (§5) |
| Config→params | **Missing (by design)** | `src/api` read Cache directly; library requires populated pydantic params → **build the adapter** (the big work item) |
| Image types | **Adapter needed** | Library is PIL/RGBA; IntraPaint is QImage. Converters already exist: `src/util/visual/pil_image_utils.pil_image_to_qimage/qimage_to_pil_image` |
| `Size`/geometry | **Adapter needed (trivial)** | `Size` ↔ `QSize` one-liners |
| Interrogate / model & sampler & scheduler lists / system stats / free-memory | **Full** | Same webservice methods (method-set diff shows parity) |
| Tiled / ultimate upscaling | **Partial [per lib status]** | Library flags this as in-progress → **verify against a live backend before deleting the `src/api` path** |
| `LORA_KEY_PATH` coupling (builder → `src.ui.window.extra_network_window`) | **Removed in library** | Library builder takes lora info as data → IntraPaint passes it in |

Net: **~everything IntraPaint calls is covered**; the only genuine *missing* pieces are the two
IntraPaint deliberately-external concerns (config→params, the CN widget), plus one *maturity* caveat
(tiled upscaling).

---

## 5. Async-model reconciliation (the crux)

**The contract to honor** (`concurrency_model.md` §5): *all image-model / config / undo / UI mutation
happens on the GUI thread; workers only produce data and hand results back via a signal whose sender
lives on the main thread (or a QObject slot on the main thread).* `AsyncTask` already satisfies this
because its instances are constructed on the main thread (finish/result signals queue to main).

**What the library adds:** its own threading in two shapes —
1. **ComfyUI handle:** no threads of its own. `poll()` and `wait()` run on *whatever thread calls
   them*; the server is the queue.
2. **WebUI handle:** a `WebUIDispatcher` daemon thread runs the blocking POST
   (lib:webui_generation_handle.py:271-301). That thread **only produces an `ImageResponse` and stores
   it on the handle** — it never touches Qt, the model, or config. `on_progress` callbacks passed to
   `wait()` fire on the *calling* thread, not the dispatcher thread.

**The clean integration pattern (recommended):** keep `AsyncTask` as the sole boundary between worker
and GUI, and run the handle's blocking `wait()` *inside* the existing worker action:

```
# runs on the AsyncTask QThreadPool worker (as generate() does today):
params  = build_params_from_cache(...)          # IntraPaint adapter (§6) — pure, no Qt
handle  = service.submit_txt2img(params)         # returns immediately (both backends)
result  = handle.wait(on_progress=_emit_progress)  # blocks THIS worker thread
# result.images : list[PIL.Image]  → convert to QImage, hand back via existing path
```

- `_emit_progress(progress)` runs **on the worker thread** (the thread in `wait()`), so it must not
  touch the UI. It does exactly what the code does today: `status_signal.emit({...})` on the
  `AsyncTask`'s Qt signal — whose sender has main affinity, so the slot (`_apply_status_update`,
  image_generator.py:267) runs on **main**. The live-preview `progress.preview` (PIL) is converted
  and marshalled the same way. **No new marshalling primitive is needed** — the existing
  signal+`QTimer.singleShot(0, window, …)` envelope already does it.
- The final `GenerationResult.images` (PIL) are converted with `pil_image_to_qimage` and passed to
  `_cache_generated_image` (image_generator.py:258) → already marshals to main. Unchanged.
- This **deletes** `_repeated_progress_check` (sd_comfyui_generator.py:459-508) and the bespoke
  websocket loop — the library's `wait()`/`poll()` subsumes it. Net *less* IntraPaint concurrency
  code.

**Why this is safe:** the WebUI dispatcher thread is a *third* thread, but it is discipline-compliant
— it produces data only, mutates nothing shared. IntraPaint's own worker blocks on `wait()`; the GUI
thread is never blocked (the whole thing is already inside `AsyncTask`). No off-main model/UI/config
mutation is introduced.

**Two crux sub-points that need explicit handling:**

- **Auth callback fires off-main.** `credentials_provider` is invoked from inside the blocking call
  (on the worker/dispatcher thread) when the server returns 401. IntraPaint's provider must therefore
  **marshal to the main thread to show `LoginModal` and block for the answer** — e.g. a
  `threading.Event` + `QTimer.singleShot(0, window, show_login)` that sets the result, or
  `QMetaObject.invokeMethod(..., Qt.BlockingQueuedConnection)`. This replaces today's direct
  `LoginModal` construction inside `a1111_webservice.py` (which was itself an
  `src/api`→`src/ui` violation). *This is the one genuinely new bit of thread plumbing the swap
  requires.* `[inferred: modest — a dozen lines in a shared helper.]`

- **Double-threading for WebUI is redundant but harmless.** Since IntraPaint already runs generation
  in its own `AsyncTask` worker, the `WebUIDispatcher`'s extra daemon thread is not strictly needed
  for the single-job case — IntraPaint *could* call blocking `txt2img` directly on its worker. But
  using the unified `submit_*`/handle API is worth it for **uniform cancellation and queue
  introspection** across both backends. Accept the extra daemon thread (it's cheap, daemon, idle when
  unused), or see the §7 library suggestion for an optional "run on caller thread" mode.

---

## 6. Migration strategy

**Chosen approach: direct rebind + thin adapters, not a compatibility shim.** A shim that preserved
`src/api`'s Cache-reading signatures would re-import the hidden-config coupling the library exists to
remove — negative value. Instead, bind the generators to `intrapaint_api` and add four small,
well-named IntraPaint-side adapters.

**What gets DELETED from IntraPaint** (superseded by the library):
- `src/api/comfyui/**` (node graph, workflow builders, node classes) — **all** of it.
- `src/api/webui/**` (request/response formats, diffusion_request_body, controlnet webui utils/consts).
- `src/api/controlnet/**` **except** the UI concern (see "relocate").
- `src/api/webservice.py`, `a1111_webservice.py`, `comfyui_webservice.py`.
- `src/util/visual/image_utils.image_to_base64/qimage_from_base64` usage from the API (library owns
  its own PIL-based version).

**What gets RELOCATED (Qt-bound, has no library home):**
- `src/api/controlnet/control_parameter.py` → becomes a **widget factory in `src/ui`** (e.g.
  `src/ui/panel/controlnet/preprocessor_param_widgets.py`) that builds `src.ui.input_fields`
  widgets from the library's pydantic `ParameterDef`/`PreprocessorParams`. This is the *same* UI
  factory extraction A4 recommends for the Config/Parameter→UI inversion — do them together.

**What gets ADDED IntraPaint-side (the real work):**
1. **`params_adapter`** — pure functions `build_comfy_params(cache, edit_mode, seed, …) ->
   ComfyUIDiffusionParams` and `build_webui_body(...) -> DiffusionRequestBody`, reading `Cache`/
   `AppConfig` on the **main thread** (or from a snapshot captured on main) and returning pydantic
   models. This is where the five deleted in-`src/api` Cache reads move to. It is pure and unit-testable
   without a server.
2. **`image_adapter`** — QImage↔PIL and QSize↔`Size` at the boundary (wrap existing
   `pil_image_utils`).
3. **`auth_provider`** — the main-thread-marshalling `credentials_provider` (§5).
4. **`progress_bridge`** — trivial: map `GenerationProgress` → the `{'progress','seed',...}` dict the
   existing `status_signal` path expects (or migrate `_apply_status_update` to consume
   `GenerationProgress` directly).

**Staged plan (backend-by-backend, ComfyUI first per §8):**
1. **Vendor the library** (§7 — add packaging; pin as a path/git dependency). Get it importable.
2. **Migrate the ComfyUI generator** (`sd_comfyui_generator.py`): swap `self._webservice` to
   `intrapaint_api`'s `ComfyUiWebservice`, build params via the adapter, replace
   `_repeated_progress_check` with `handle.wait(on_progress=…)`, convert PIL→QImage on results. Keep
   `test_generator` (mock) green throughout. This is the default backend, so land it first.
3. **Migrate the WebUI generator** (`sd_webui_generator.py`): same pattern; add the auth provider;
   rewire `src/config/a1111_config.py:7` import to the library's `A1111Webservice` (type-only change,
   a1111_config.py:34,81).
4. **Migrate the ControlNet UI** (`controlnet_panel.py`, `image_scale_modal.py`): point at
   `shared_data/controlnet` models; replace `DynamicControlFieldWidget` with the relocated widget
   factory.
5. **Delete `src/api`** once nothing imports it (the six consumers in §2 are the complete list) and
   integration round-trips pass.
6. **Verify tiled/ultimate upscaling** against a live backend before trusting the deletion of that
   path (library flags it in-progress).

**Shared base note:** `sd_generator.py` holds the controlnet/webservice-agnostic logic; most of its
`src/api` imports (sd_generator.py:12-17) are the controlnet data model + `WebService`/`AuthError`,
which map 1:1 to library symbols — a mechanical import redirect.

---

## 7. Recommended changes — to each repo

### 7a. To the LIBRARY (`sd-api-standalone`) — proposals, not edits (separate repo)

1. **Add packaging.** There is no `pyproject.toml`/`setup.py` (lib:top-level). Add one so IntraPaint
   can `pip install` it (path/git dependency) with a pinned version, instead of `sys.path` hacks.
2. **Add a curated public API.** `intrapaint_api/__init__.py` and `api/__init__.py` are empty
   docstrings (lib). Export the intended surface (`ComfyUiWebservice`, `A1111Webservice`,
   `DiffusionParams` & subclasses, `ControlNetUnit`/model/preprocessor, `GenerationHandle` +
   status/progress/result) so IntraPaint imports a stable façade, not deep module paths — this keeps
   IntraPaint insulated from the library's ongoing internal refactor (its status says the ComfyUI node
   pydantic migration is in flight).
3. **Optional "run on caller thread" mode for the WebUI handle.** For hosts (like IntraPaint) that
   already own a worker thread, allow `submit_*` to skip the `WebUIDispatcher` daemon and run the
   blocking POST on the caller — avoids a redundant thread (§5). Keep the dispatcher as the default.
4. **Finish the flagged in-progress paths** before IntraPaint deletes their `src/api` equivalents:
   ComfyUI node pydantic migration + tiled/ultimate upscaling (lib:README "Status").
5. **Keep the no-Qt / no-config constraints intact** (lib:CLAUDE.md) — they are the reason the swap is
   clean; don't let IntraPaint-specific concerns leak back in.

### 7b. To INTRAPAINT

1. Add the four adapters + the relocated CN widget factory (§6).
2. Delete the `src/api` backend-client tree (§6); update the six consumers (§2).
3. Move the five deleted in-`src/api` Cache reads into the `params_adapter`, read on the main thread —
   which also advances `concurrency_model.md`'s "config read/write on the main thread" goal and A4's
   "keep the API free of hidden config" direction.
4. Replace the in-`src/api` `LoginModal` construction with the main-thread-marshalling auth provider
   (fixes an existing `src/api`→`src/ui` layering violation).
5. Add the library to `requirements.txt` (pinned) and to the PyInstaller specs' hidden imports /
   data — note the library **drops** IntraPaint's `cv2`/`numpy`-in-API usage but **adds** `pydantic`
   and `platformdirs` as deps (packaging/A7 hand-off).

---

## 8. Backend strategy (ComfyUI default, A1111/Forge downgrade)

Per the decisions-ledger leaning (ComfyUI trending default; A1111/Forge lower priority), the swap
*supports* this rather than complicating it:

- **Migrate ComfyUI first** and treat it as the reference path (§6 step 2). It's already the more
  natural fit for the async handle (native queue).
- **Don't over-invest in A1111-only sophistication.** The library already did the hard A1111 work for
  free — the `WebUIDispatcher` client-side queue + idle-wait
  (lib:webui_generation_handle.py:227-339) gives WebUI ComfyUI-parity cancellation with **zero**
  IntraPaint effort. So "downgrade A1111" here means *don't build new A1111-specific IntraPaint code*,
  not *drop A1111* — keep it working through the same unified handle at no marginal cost.
- **GLID generators stay legacy/untouched** (`_decisions_ledger.md` scope) — they don't use `src/api`
  and are out of scope.
- The unified `GenerationHandle` means IntraPaint's generator code becomes **backend-symmetric**: the
  same `submit_* → wait(on_progress) → convert` flow for both, with per-backend differences confined
  to the params adapter. That symmetry is itself the strongest argument for the library.

---

## 9. Testing the swap

**Both repos have suites; use them at different layers:**
- **Library unit tests (offline, deterministic)** pin the *wire output*: workflow-builder graph
  structure, request-body shaping, controlnet serialization, the ComfyUI handle, preprocessor params
  (lib:tests/unit/). A change that alters an emitted request fails here. **Run these as the contract
  the migration must not break.**
- **IntraPaint side:** add unit tests for the new `params_adapter` — assert that a given `Cache`
  state produces the expected `ComfyUIDiffusionParams`/`DiffusionRequestBody`. Because the library's
  params are pure pydantic, this is server-free and fast (the "pure builders make it easy" point).
- **Golden-image path unchanged:** IntraPaint's `test_generator`/`--mode mock` (test_generator.py)
  and existing golden comparisons still exercise the generator envelope; keep them green through each
  stage.
- **Live round-trip once per backend:** run the library's `pytest tests/ --run-generation` (lib:CLAUDE.md)
  against a real ComfyUI and a real A1111/Forge, plus one manual IntraPaint inpaint per backend,
  before deleting the corresponding `src/api` path. **Mandatory for the tiled/ultimate-upscale path**
  (library's flagged-incomplete area).
- The library's ControlNet integration test has a **silent-failure detector** (same seed with/without
  a unit must differ, lib:CLAUDE.md) — rely on it when validating the CN model rebind.

---

## 10. Risks, sequencing, and hand-off to OQ3

**Risks:**
- **R1 — tiled/ultimate upscaling is library-incomplete.** Verify live before deleting the `src/api`
  equivalent; if not ready, keep *only* that path on `src/api` temporarily behind a feature check.
  Medium likelihood, contained.
- **R2 — auth marshalling.** The off-main `credentials_provider` is the one new thread-plumbing bit;
  get it right (main-thread modal, blocking result) or A1111 auth hangs/crosses threads. Low
  likelihood with the §5 pattern, high visibility if wrong.
- **R3 — library churn.** Its own status says internals are refactoring. **Mitigate with 7a.1/7a.2**
  (packaging + curated public API + a pinned version) so IntraPaint depends on a stable façade.
- **R4 — image round-trip fidelity.** QImage↔PIL RGBA normalization must preserve premultiplied-alpha
  expectations IntraPaint relies on downstream (relates to the rendering report's alpha caveat).
  Cover with a golden round-trip test in the `image_adapter`.
- **R5 — packaging deltas.** New runtime deps (`pydantic`, `platformdirs`) and the library-as-dependency
  must reach the PyInstaller bundles — a packaging (A7) concern, flagged here.

**Sequencing:** 7a.1 (packaging) → ComfyUI generator → WebUI generator + auth → ControlNet UI →
delete `src/api` → live verification. The CN widget factory can be built in parallel with the
generator work.

**Hand-off to OQ3 (backend auto-install):** this report standardizes IntraPaint on **`intrapaint_api`
as the single backend client, with ComfyUI as the primary target.** OQ3's push-button installer
should therefore aim at **provisioning a ComfyUI instance** and pointing `ComfyUiWebservice` at it,
reusing the library's `is_available`/`get_system_stats` for readiness checks. Because the library is
Qt-free and pip-installable (once 7a.1 lands), an installer helper could even drive it headlessly.
OQ3 builds directly on the client this swap makes canonical.
