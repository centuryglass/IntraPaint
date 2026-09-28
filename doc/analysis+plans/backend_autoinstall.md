# OQ3 — Push-button backend auto-install

Strategy report for OQ3: *"Asking users to install stability-matrix and worry about backend
configuration is a major barrier to adoption. I don't want to bundle a full Stable Diffusion install,
but ideally there should be at least one way to just push a button and have the backend stuff install
itself with minimal user intervention. What would be the best path for implementing that?"*

Builds on **OQ5** (`api_library_swap.md`) — which standardized IntraPaint on **ComfyUI as the primary
backend** behind the `intrapaint_api` client — and on `concurrency_model.md` (the threading contract
any long-running install must obey). Reads on top of `_codebase_map.md` (§5) and
`_decisions_ledger.md`. Evidence cited as `file:line`. `[inferred]` marks reasoning not confirmed by
running code. **Analysis only — no code changed.**

---

## 1. Summary verdict

Today IntraPaint is a **pure client**: there is no code anywhere that launches, installs, or manages a
backend process (verified — no `subprocess`/`QProcess`/`comfy-cli` usage in `src/`). Generators only
*connect to a URL* (`is_available()` pings `get_system_stats`, sd_comfyui_generator.py:395;
`configure_or_connect()` prompts for a URL, sd_generator.py:338) and, when nothing is reachable,
hand the user a multi-screen rich-text install guide pointing at Stability Matrix / portable ZIPs /
manual Python (sd_comfyui_generator.py:69-130; `doc/stable_diffusion_setup.md`). *That guide is the
barrier the question is about.*

**The single most important reframing:** the adoption barrier is **two different problems wearing one
coat**, and they have very different costs —
1. **Configuration** — "I have (or could get) a backend, but wiring it to IntraPaint is fiddly." This
   is cheap to solve and solves a large fraction of real cases: **detect existing installs and
   launch/point at them**, no download.
2. **Installation from zero** — Python env + the correct multi-GB PyTorch build for the user's GPU +
   at least one multi-GB model. This is genuinely hard and is where "push a button" gets expensive.

**Recommended path:** introduce a small **pluggable backend-provisioner** subsystem (detection +
managed-lifecycle + install engines) that targets **ComfyUI only** (per OQ5), with a **staged**
rollout that front-loads the cheap, high-value wins:

- **Do not hand-roll the PyTorch/GPU matrix.** Drive the ComfyUI project's **official `comfy-cli`**
  installer as the default fresh-install engine, plus a **Windows-portable** fast-path (self-contained
  embedded Python+torch) for bundled builds. Both are officially maintained and cross the
  GPU/accel matrix you never want to own.
- **Detect and reuse first.** Before offering any download, scan for existing ComfyUI / Stability
  Matrix / portable installs and existing model directories; offer to *use* them. Many target users
  already have Stability Matrix — for them the fix is pure configuration + auto-launch, zero bytes
  downloaded.
- **Own the lifecycle.** A "managed instance" concept lets IntraPaint start/stop/health-check the
  backend as a child process, turning "install stability-matrix and configure it" into "IntraPaint
  launched it for you."
- **Be honest about models.** A model download is unavoidable and licensing is real; offer a curated
  **ungated** short-list + first-class "bring your own file," and deep-link (don't silently scrape)
  anything gated.

All long-running work runs in `AsyncTask` workers streaming progress to the setup window's existing
status pane — never on the GUI thread (concurrency_model.md §5). The whole subsystem plugs in behind
one new button in `GeneratorSetupWindow` and one new branch in the ComfyUI generator's
`configure_or_connect`, so the rest of the app is undisturbed.

---

## 2. What exists today (the seam an installer plugs into)

- **Connection model.** Generators hold a `server_url` (default `http://localhost:8188`,
  sd_comfyui_generator.py) and test reachability with `ComfyUiWebservice.get_system_stats()`
  (sd_comfyui_generator.py:395-410). `configure_or_connect()` loops a `QInputDialog` for the URL until
  `is_available()` (sd_generator.py:338-352). **No process is ever spawned.**
- **Selection/auto-detect.** At startup `--mode auto` probes generators by availability and falls back
  to the `NullGenerator` when none respond (app_controller.py:490-527). So "no backend" is already a
  graceful, first-class state.
- **The setup UI.** `GeneratorSetupWindow` (generator_setup_window.py) already has exactly the surface
  an installer needs: a **Setup** rich-text tab (`get_setup_text()`, :142), a **Status** pane with a
  live `_update_status_text` hook (:112), and an **Activate** button row (:97-100). An
  "Install / Set up automatically" button belongs right next to Activate, and install progress belongs
  in the Status pane.
- **Distribution.** Two shapes: source/pip installs (a real user Python is present) and **PyInstaller
  bundles** (`is_pyinstaller_bundle()` gates GLID out, app_controller.py:498) where **no user Python is
  guaranteed** — this split drives the engine choice in §4.

Net: the codebase is *client-only* but the connection check (`get_system_stats`) and the setup
window's status/button scaffolding are exactly the hooks a provisioner reuses. Nothing structural
blocks this.

---

## 3. Decomposing "install the backend"

Four independent sub-problems, each with its own difficulty and failure modes:

| Sub-problem | Difficulty | Notes |
|---|---|---|
| **A. ComfyUI app + deps** | Low–Med | git clone / pip / portable ZIP. Well-trodden. |
| **B. Correct PyTorch build** | **High** | CUDA vs ROCm vs CPU vs MPS; driver/version matched; multi-GB. **The part to never hand-roll.** |
| **C. ≥1 model checkpoint** | Med | Multi-GB download; **licensing/HF gating**; user preference. |
| **D. Launch + lifecycle** | Med | Spawn as subprocess, health-check, stop cleanly, surface logs. |

The question's constraint ("don't bundle a full SD install") means B and C are **downloaded on
demand**, not shipped. B is the reason the answer must lean on an existing installer rather than a
bespoke script; C is the reason "minimal user intervention" has an irreducible floor (a several-GB
download and possibly one license click).

---

## 4. Design options for the install engine

| Option | Cross-platform | Handles torch/GPU (B) | Bundled-build fit | Maintenance | Verdict |
|---|---|---|---|---|---|
| **A. Drive `comfy-cli`** | Win/Linux/mac | **Yes (official)** | Needs a Python to host it | Low (upstream owns B) | **Default engine** |
| **B. Windows-portable ZIP** | Windows only | Yes (embedded) | **Excellent (self-contained)** | Low (track release URL) | **Windows / bundled fast-path** |
| **C. Hand-rolled venv+git+pip** | Yes | **You own the matrix** | Needs Python | **High** | Avoid as primary |
| **D. Docker image** | Yes (if Docker) | Yes | Poor (Docker is itself a barrier) | Med | Advanced/opt-in only |

**Recommendation:** a thin **engine abstraction** with `comfy-cli` as the default and the
Windows-portable package as a fast-path (and the natural choice for PyInstaller bundles, since it
carries its own Python+torch and needs no user Python). Docker stays an advanced opt-in. Hand-rolled
venv is explicitly rejected — re-implementing the PyTorch/GPU selection that `comfy-cli` already
maintains is exactly the "home-grown mechanism duplicating an existing one" the architecture review
warns against.

---

## 5. Recommended architecture

A new, self-contained subsystem — **`src/controller/image_generation/backend_install/`** — with four
collaborators behind one facade:

### 5.1 Environment detection (`BackendDetector`)
- **Find existing backends first:** scan known locations (Stability Matrix data dir, ComfyUI portable
  folders, prior IntraPaint-managed installs) and existing model directories; probe common ports. If a
  reachable or launchable ComfyUI is found, the "install" flow short-circuits to *use this* (§5.3).
- **Profile the machine:** OS, GPU vendor/driver (`nvidia-smi` / `rocminfo` / Apple Silicon), free
  disk, presence of a usable Python. Feeds sane defaults (accel type, install location) and gates
  which engines are offered.

### 5.2 Install engines (`InstallEngine` interface)
`comfy_cli_engine`, `windows_portable_engine`, `docker_engine` (opt-in). Each exposes
`plan()` (what it will do / download size / target dir) and `run(progress_cb)` (idempotent, resumable
where possible). All I/O and subprocess work happens on a worker thread (§6); `progress_cb` emits
lines to the Status pane. Version/URL manifests are **fetched**, not hard-coded, so releases don't rot
the button.

### 5.3 Managed instance + lifecycle (`ManagedComfyUI`)
The keystone that fixes "configuration" independent of "installation":
- Records an install location + launch command + port in `Cache` (new keys).
- `start()` spawns ComfyUI as a **child process** (`QProcess`/`subprocess`), `wait_until_ready()`
  polls `get_system_stats()` (reusing the generator's existing check), `stop()` terminates it on app
  exit, and logs stream to the Status pane.
- The ComfyUI generator's `configure_or_connect()` gains a branch: *if no server is reachable but a
  managed instance exists, auto-start it before prompting for a URL.* So returning users get
  transparent auto-launch; first-timers get the install button.

### 5.4 Model acquisition (`ModelProvisioner`)
- A curated short-list of **ungated, permissively-licensed** checkpoints with direct URLs + checksums,
  downloaded with a resumable progress bar into the ComfyUI `models/checkpoints` dir.
- **First-class "use an existing model file / point at an existing models dir"** (symlink or config) —
  for the many users who already have checkpoints.
- Gated models (HF license click-through) are **deep-linked, not scraped**: open the license page,
  let the user accept, then resume with their token. Never silently fetch gated weights.

### 5.5 UI integration (minimal)
One **"Set up automatically"** button in `GeneratorSetupWindow` next to Activate (generator_setup_window.py:97),
opening a short confirm dialog (install location, accel default from detection, model choice), then
streaming `plan()`/`run()` progress into the existing Status pane and flipping to **Activate** on
success. No new window needed.

---

## 6. Threading (must obey the concurrency contract)

Installs are minutes-long subprocess pipelines — they **cannot** touch the GUI thread. Per
`concurrency_model.md` §5:
- Wrap each engine `run()` in an **`AsyncTask` constructed on the main thread** (so its finish/status
  signals deliver on main). The worker only spawns/monitors the subprocess and **emits stdout lines
  via a Qt signal**; the Status pane updates on the main thread (the same pattern generators already
  use for progress, image_generator.py:267).
- **Cancellation** = terminate the child process from the worker; finalize CANCELLED on the finish
  handler.
- `ManagedComfyUI.start()`/health-poll likewise run off-main and report readiness back via a
  main-affinity signal. **No `Config.set`/model/UI mutation on the worker thread.**

This is the same discipline the OQ5 generation handles use, so the installer reuses an established,
audited pattern rather than inventing threading.

---

## 7. Alignment with OQ5 and backend strategy

- **ComfyUI only.** OQ5 confirmed ComfyUI as primary and downgraded A1111/Forge; the installer targets
  **ComfyUI exclusively**. A1111/Forge get **detection** (discover an existing WebUI and point at it)
  but **no auto-install** — consistent with "don't invest in A1111-specific paths."
- **Reuse the client.** Readiness checks reuse `intrapaint_api`'s `get_system_stats()`/`is_available`
  (OQ5 §10 explicitly hands off to this report on that basis). The provisioner produces a URL +
  managed process; the generator connects exactly as it does today.
- **GLID untouched** (legacy, per ledger).

---

## 8. Packaging interplay (hand-off to A7, not yet written)

The provisioner introduces real packaging constraints A7 must account for:
- **Bundled builds have no user Python** → the **Windows-portable engine is the default there** (it
  carries its own Python+torch). `comfy-cli` needs a host Python, so on bundles it requires either a
  small embedded Python or the portable path. Flag this as an explicit A7 input.
- New optional runtime touchpoints: ability to spawn subprocesses, network downloads with
  checksum/resume, and disk-space checks. None are heavy deps, but the download/verify helper should
  be shared with any future updater.
- Keep install **outside** the app bundle (a user data dir via `platformdirs`, already a dep,
  requirements.txt) so reinstalling/updating IntraPaint doesn't nuke a multi-GB backend.

---

## 9. Risks

- **GPU/driver detection is imperfect** → always offer a manual accel override; default from detection
  but let the user correct it.
- **Huge, flaky downloads** (torch + model, many GB) → resumable transfers, checksums, retries, clear
  disk-space preflight; never leave a half-written model that reads as "installed."
- **Licensing/gating** → curated ungated defaults + deep-linked gated flow; never auto-accept a
  license on the user's behalf.
- **Windows SmartScreen / AV** on downloaded executables → prefer official sources, verify
  checksums/signatures, document the prompt.
- **Supply-chain / executing downloaded code** → pin `comfy-cli`/portable versions via a fetched
  manifest, verify checksums, use only official upstream URLs. Treat this as a security-relevant
  surface.
- **URL/version rot** → fetch a version manifest at runtime rather than hard-coding release URLs (the
  current guide already hard-codes links that will age).
- **Partial-install recovery** → engines must be idempotent/resumable and able to detect and repair a
  broken prior attempt.

---

## 10. Staged plan (front-load the cheap wins)

1. **Detection + auto-launch of existing installs (`BackendDetector` + `ManagedComfyUI`).** Highest
   value-to-effort: solves the *configuration* half for everyone who already has ComfyUI/Stability
   Matrix, with **zero downloads** and low risk. Auto-start a known install and health-check it.
2. **Managed-instance lifecycle** for a user-pointed install dir (start/stop/health/logs, auto-launch
   branch in `configure_or_connect`). Now "no server running" self-heals.
3. **`comfy-cli` fresh-install engine + Windows-portable fast-path**, progress streamed to the Status
   pane. This is the literal "push button to install from zero."
4. **`ModelProvisioner`** (curated ungated list + BYO + gated deep-link).
5. **Docker engine** (advanced, opt-in).

Stages 1–2 deliver most of the felt improvement (the barrier is mostly configuration for users who
already dabble in SD); Stages 3–4 serve true first-timers. Each stage is independently shippable and
testable.

---

## 11. Testing

- **Detection** unit tests over fixture filesystem layouts (Stability Matrix / portable / none) and
  mocked `nvidia-smi`/`rocminfo` outputs → correct engine offering + defaults.
- **Engine `plan()`** tests (pure: given env → planned actions/URLs/sizes) without executing anything.
- **Lifecycle** tests with a **stub server** (a tiny process exposing a fake `get_system_stats`) to
  exercise start → ready → stop → crash-detection without a real ComfyUI/GPU.
- **Threading**: assert the install `AsyncTask` streams status on the main thread and cancellation
  terminates the child (reuse concurrency_model.md's verification approach).
- **Manual/CI-gated** end-to-end install on each OS is the real proof and can't be fully mocked — keep
  one opt-in E2E per platform, like the library's `--run-generation` tests (OQ5 §9).

---

## 12. Doc updates warranted

- `_decisions_ledger.md`: record (a) IntraPaint is client-only today (no launch/install code), (b) the
  auto-install strategy — ComfyUI-only pluggable provisioner (detect-and-reuse first, `comfy-cli` +
  Windows-portable engines, managed-instance lifecycle, honest model story), (c) that it obeys the
  AsyncTask main-thread discipline and hands packaging constraints to A7.
- `_execution_plan.md`: mark OQ3 done; note the A7 (packaging) dependency it creates and that it
  consumes OQ5's ComfyUI-primary decision. **Phase 2 complete** (OQ4, A2, OQ3 all done).
- `README.md`: index this report.
