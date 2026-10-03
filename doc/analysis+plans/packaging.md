# Cross-platform packaging and native dependencies (A7)

**Question (open_questions.txt):** Distribution depends on per-platform native pieces - bundled libmypaint DLLs,
the Cython `image_fill` extension, PyInstaller specs - and macOS/ARM support is incomplete. What's the cleanest
strategy for packaging, building native deps, and supporting Windows/Linux/macOS (Intel+ARM) with minimal
per-platform maintenance?

**Substrate:** `_codebase_map.md` (native/build section), `_decisions_ledger.md`. Cross-refs: OQ3
(`backend_autoinstall.md` section 8 hands this report its constraints), A1 (`testing_strategy.md`). Issues: #8
(build the bundle in CI), #65 (libmypaint builds), #7 (`image_fill` build failure blocks startup), #40 (backend
auto-install), #35 (endianness, not a packaging concern on any target below: all are little-endian).

**Method.** Unlike most earlier reports, the main claims here were checked by running code on Linux x86_64 in a
cloud session (Python 3.13.14). Each section marks what was **verified** and what is **inferred**. Nothing was run
on Windows or macOS.

---

## 0. Summary

The packaging is a hand-run, Linux-and-Windows-only process that has drifted out of working order since the
dependency pins landed. The recommendation:

1. **Make the build reproducible in CI first** (#8): one workflow, a smoke test that launches the app, and a
   PyInstaller bump. With today's pins the Linux bundle builds but crashes on startup (section 2, P1).
2. **One spec file** that branches on `sys.platform`, with libmypaint passed as `binaries` from a per-platform
   folder `lib/<platform-tag>/`.
3. **Obtain libmypaint 1.6.1 once per platform, commit the results with a provenance manifest,** and rebuild only
   when the version changes. Windows comes from the MSYS2 package; Linux and macOS are built from the upstream
   release tarball by one script, with json-c linked in.
4. **Don't ship prebuilt `image_fill` binaries for source installs.** Fix #7 instead (fill tools degrade, app
   starts), and fix the auto-build's working-directory bug.
5. **macOS (both architectures) and Linux aarch64 come last,** as CI-built, unsigned, "untested" artifacts, until
   the maintainer decides whether they're worth supporting (section 6).

---

## 1. Current state inventory

### 1.1 Build entry points (verified by reading and running)

| Piece | What it does |
|---|---|
| `IntraPaint.spec` | Windows spec. One-file `EXE`, PyInstaller `Splash`, `console=True`, `upx=True`, PNG icon. |
| `IntraPaint-linux.spec` | Same as the Windows spec plus `a.exclude_system_libraries()` and one extra `excludes` entry (`cv2.ab13.so`). |
| `scripts/build.sh` | `python setup.py build_ext --inplace`, then `pyinstaller IntraPaint-linux.spec`. No Windows or macOS script. |
| `scripts/clean.sh` | Removes `build/` and `dist/`. |
| `setup.py` | `cythonize('src/util/visual/image_fill.py')`, path relative to the working directory. |
| `.github/workflows/ci.yml` | Tests and lint from source on Ubuntu only. No packaging job, no release workflow. |
| `.github/workflows/release-source.yml` | Branch-source guard for PRs into `master`. Builds nothing. |

Both specs collect `('resources', 'resources')` and `('lib', 'lib')` as `datas`, list one hidden import
(`src.tools.mypaint_brush_tool`) and exclude `PySide6.QtNetwork`, `PySide6.QtDBus` and `libKf6BreezeIcons.so.6`.

Releases are built by hand. GitHub shows v1.0.0, v1.1.0 and v1.2.0 (2026-06-23), each with a one-file
`IntraPaint-linux` (about 160 MB) and `IntraPaint.exe` (about 130 MB). The last macOS asset was v0.1.0 (2022), from
the legacy GLID-3-XL era.

### 1.2 Native piece: libmypaint (verified)

Checked in under `lib/` (one commit, 2024-10-09):

| File | Platform | Notes |
|---|---|---|
| `libmypaint.so` | Linux x86_64 | Soname `libmypaint.so.0`. Exposes the 1.5+/1.6 settings (`posterize` resolves to id 61, `paint_mode` to 63), so 64 settings. Needs `libjson-c.so.5`, `libglib-2.0.so.0`, `libgobject-2.0.so.0` and glibc 2.29 from the system. |
| `libmypaint-1-4-0.dll` | Windows x86_64 | libmypaint 1.4.0, MinGW build (links `msvcrt.dll`; `libintl-8`/`libiconv-2` naming matches MSYS2's mingw64 packages). Has `gridmap_*` but no `posterize`/pigment settings, hence 56 settings. |
| `libjson-c-2.dll`, `libintl-8.dll`, `libiconv-2.dll` | Windows x86_64 | Dependencies of the DLL above. |

There is no macOS dylib and no aarch64 build of any kind. No file records where these binaries came from or how they
were built.

Loading lives in `src/image/mypaint/libmypaint.py`, `load_libmypaint`, called at import time
(`libmypaint = load_libmypaint(DEFAULT_LIBRARY_PATH)`):

1. `ctypes.util.find_library('mypaint')`, so a system libmypaint wins over the bundled one when one is found.
2. Windows ignores step 1's result and preloads the four DLLs from `PROJECT_DIR/lib` by fixed name.
   `DEFAULT_LIBRARY_PATH` names `lib/libmypaint.dll`, which doesn't exist; it's unused on Windows.
3. Everything else (`os.name != 'nt'`, macOS included) loads `lib/libmypaint.so`. On macOS that file is an ELF
   binary and fails to load.
4. On `OSError`, every file in `AppConfig.LIBMYPAINT_LIBRARY_DIR` (default `DATA_DIR/libmypaint-lib-files`, created
   by `AppConfig._adjust_defaults`) is loaded, with the one whose name contains "mypaint" loaded last. This is the
   only path a macOS user has today.

The brush setting count is not read from the library. `mypaint_brush._get_max_setting_index` returns 56 on Windows
and 64 elsewhere, or probes in a child process when `DYNAMIC_MYPAINT_BRUSH_SETTINGS` is set.

Failure is contained: `ToolController` imports `MyPaintBrushTool` through `optional_import`, so a missing libmypaint
removes the MyPaint brush tool and nothing else (read, not reproduced).

### 1.3 Native piece: `image_fill` (verified)

`src/util/visual/image_fill.py` is Cython pure-Python mode and only works compiled (see #7).

- The generated C uses no numpy C-API, so the extension depends only on the CPython minor version and platform, not
  on the numpy version. It isn't built against the limited API, so there's one binary per Python minor version.
- `IntraPaint.py` builds it on first launch when not running from a bundle, with
  `subprocess.run([sys.executable, 'setup.py', 'build_ext', '--inplace'])`.
- In a bundle, PyInstaller collects whatever compiled module is present at build time. If the build step was
  skipped, it bundles the `.py`, which raises `ImportError` at startup (inferred from import precedence; the Windows
  spec has no script that runs the Cython build first).
- CI and the session hook build it explicitly before tests.

### 1.4 Python dependencies relevant to packaging (verified)

- `requirements.txt` pins `PySide6==6.11.2`, `numpy==2.4.6`, `opencv-python-headless==4.10.0.84` and
  `platformdirs==4.12.0`. It also pins `cython` and `setuptools`, which are needed only for the launch-time build.
- `requirements-dev.txt` pins `pyinstaller==6.11.0` for Python below 3.14. `.github/dependabot.yml` excludes
  pyinstaller from Dependabot; it's bumped by hand.
- Wheel tags in the session venv: PySide6 6.11.2 is `manylinux_2_34_x86_64`, numpy 2.4.6 is `manylinux_2_28`,
  opencv is `manylinux2014`. So any Linux bundle already needs glibc 2.34 or newer, whatever it's built on.
- `optional-requirements.txt` (themes, `spnav`, GLID) is not bundled. GLID is gated off in bundles by
  `is_pyinstaller_bundle()` in `IntraPaint.py` and `AppController`.

### 1.5 Platform-specific code paths (verified by grep)

Only three files branch on platform, all on `os.name == 'nt'`: `src/image/mypaint/libmypaint.py`,
`src/image/mypaint/mypaint_brush.py` (setting count) and `src/ui/widget/color_picker/screen_color.py`. Nothing
checks `sys.platform == 'darwin'` or the CPU architecture. User data goes through `platformdirs`:
`DATA_DIR = user_data_dir('IntraPaint', 'centuryglass')` and `LOG_DIR` in `src/util/shared_constants.py`. All
`PROJECT_DIR` uses read bundled resources; none write there.

---

## 2. Problems found

Filed as #84 (P1, P2) and #85 (libmypaint load order and bundle contents). The `image_fill` auto-build's
working-directory dependence is fixed in `IntraPaint.py`.

**P1. With today's pins, the Linux bundle crashes at startup (verified).** Built with `pyinstaller==6.11.0` from
`requirements-dev.txt` (Splash removed, see P2), the one-file binary fails on `import numpy` with
`ModuleNotFoundError: No module named 'numpy._core._exceptions'`, through `cv2` in `src/util/visual/image_utils.py`.
The same spec built with PyInstaller 6.22.3 runs: `--help` works, and an offscreen `--mode none` launch reaches
`State change: from init to editing` with the MyPaint tool loaded. The pins landed on 2026-09-28, after v1.2.0, so no
release has shipped with this combination. The minimal working PyInstaller version was not bisected. This is the
regression #8 is meant to catch.

**P2. The spec needs tkinter at build time (verified).** `Splash` aborts the build with "Your platform does not
support the splash screen feature, since tkinter is not installed". The Python 3.13 used here has no `tkinter`,
and nothing in the docs or requirements mentions it. Per the PyInstaller docs, `Splash` isn't supported on macOS at
all (not verified here), so a macOS build needs the spec to skip it.

**P3. Each bundle carries the other platform's libraries (verified on Linux).** `('lib', 'lib')` copies the whole
folder, so the Linux bundle contains all four Windows DLLs. The Windows bundle presumably contains the `.so` the same way.

**P4. The Linux bundle relies on the user's `libjson-c.so.5` and glib (verified by `readelf`).** `lib/` goes in as
`datas`, so PyInstaller doesn't analyze `libmypaint.so`'s dependencies, and `exclude_system_libraries()` would drop
them anyway. On a distro without json-c 5, the MyPaint brush tool silently disappears (inferred from the
`optional_import` path).

**P5. A system libmypaint takes priority over the bundled one, but the setting count assumes the bundled version
(read; not reproduced).** `load_libmypaint` tries `find_library('mypaint')` first, also inside a bundle. If that
finds a library with a different settings table, the hard-coded 56/64 from `_get_max_setting_index` doesn't
match it. On macOS, `find_library` searches `/usr/local/lib` but not `/opt/homebrew/lib`, so a Homebrew install
on Apple Silicon isn't found either way.

**P6. The `image_fill` auto-build depends on the working directory (verified).** Launching
`python /path/to/IntraPaint.py` from another directory prints `can't open file '<cwd>/setup.py'`. The return code
isn't checked, so startup goes on to the `ImportError` from #7. From the project directory, the same launch builds
the module and starts.

**P7. `DYNAMIC_MYPAINT_BRUSH_SETTINGS` fails under the `spawn` start method (verified).**
`_get_max_setting_index` passes a nested function to `multiprocessing.Process`. With `spawn` (the default on Windows
and macOS) it fails with `Can't get local object '_get_max_setting_index.<locals>.read_settings'`. Python 3.14 also
moves Linux off `fork`. Nothing calls `multiprocessing.freeze_support()`, which a frozen Windows or macOS build would
also need. The path is opt-in through an environment variable, so the impact is small.

**P8. The bundle collects packages it doesn't need (verified).** The Linux bundle contains Cython (78 modules) and
setuptools with its runtime hook, needed only for the source build. `excludes=['PySide6.QtNetwork']` drops the
Python module, but `libQt6Network.so.6` still ships as a Qt dependency, as do the QtQml/QtQuick libraries.
Unpacked, the one-file archive is about 350 MB of binaries and data. Startup to `--help` takes about 3 seconds,
including extraction.

**P9. Two specs, one script, no release process in the repo.** The specs differ by two lines but are maintained
separately. `scripts/build.sh` handles only Linux. Windows builds depend on the maintainer remembering to run
`setup.py build_ext` first (see 1.3). `upx=True` makes the output depend on whether UPX happens to be installed.

**Doc drift found during the survey (not bugs):**

- The README FAQ says the libmypaint directory setting is in the "system" category; its definition in
  `resources/config/application_config_definitions.json` puts it under "Files".
- The `src/ui/panel/mypaint_brush_panel.py` module docstring says libmypaint is "currently only true for x86_64
  Linux", but Windows has it too.
- #8 suggests smoke-testing `dist/IntraPaint/IntraPaint`. The specs build a one-file binary at `dist/IntraPaint`.

---

## 3. Recommended strategy

### 3.1 Principles

- **CI builds every shipped artifact.** A target that CI doesn't build and launch is not supported.
- **Native libraries are obtained rarely and committed.** libmypaint changes upstream about once every few years.
  Building it in every release job adds toolchains to the release path for no benefit, and source installs need
  the binaries in the tree anyway.
- **One spec, platform differences in code.** A spec is a Python file; it can branch on `sys.platform`.
- **Optional native pieces degrade.** Missing libmypaint already removes only the MyPaint tool; missing `image_fill`
  should remove only the fill tools (#7). This keeps "every manual editing tool works without a backend" true even on
  an unusual platform.

### 3.2 Target matrix

| Target | Runner | Format | Status |
|---|---|---|---|
| Windows x86_64 | `windows-latest` | one-file `IntraPaint.exe` | Supported (existing) |
| Linux x86_64 | `ubuntu-22.04` | one-file `IntraPaint-linux` | Supported (existing) |
| Linux aarch64 | `ubuntu-22.04-arm` | one-file `IntraPaint-linux-aarch64` | CI-built, untested |
| macOS arm64 | `macos-14` or newer | zipped one-folder `.app` | CI-built, untested |
| macOS x86_64 | GitHub's Intel macOS image (check the current label) | zipped one-folder `.app` | CI-built, untested, first to drop |

- Linux builds on 22.04 rather than `ubuntu-latest`: the bundle inherits the build machine's glibc, and 22.04's 2.35
  sits just above the PySide6 wheel's 2.34 floor (1.4). Building on 24.04 would raise the floor to 2.39 for no gain.
- macOS gets two per-architecture builds, not universal2: numpy and opencv publish per-architecture wheels
  (inferred from their usual wheel tags; not checked).
- macOS uses one-folder mode inside a `.app` because PyInstaller deprecates one-file app bundles and `Splash` is
  unavailable there. Windows and Linux keep one-file so the README's direct download links keep working.

### 3.3 Spec consolidation

Replace both specs with one `IntraPaint.spec`:

- `PLATFORM_TAG` from `sys.platform` and `platform.machine()` (`win-x86_64`, `linux-x86_64`, `linux-aarch64`,
  `macos-arm64`, `macos-x86_64`).
- libmypaint and its dependencies go in as `binaries` from `lib/<PLATFORM_TAG>/` to `lib/`. As binaries,
  PyInstaller analyzes their dependencies, and on macOS rewrites their install names and signs them.
- `exclude_system_libraries()` on Linux only, listing json-c in its exceptions if it's still a separate library.
- `Splash` only on Windows and Linux. On macOS, a `BUNDLE` step with an `.icns` icon generated from
  `resources/icons/app_icon.png`.
- Drop `upx`. Add `Cython`, `setuptools` and `pyximport` to `excludes`, then confirm with a launch test that nothing
  needs them at runtime.
- Remove the entries in `excludes` that name binaries (`libKf6BreezeIcons.so.6`, `cv2.ab13.so`). `excludes` takes
  module names, so these entries match nothing. Filtering `a.binaries` is the way to drop a library, if
  that's still wanted.

`scripts/build.sh` becomes platform-neutral (`build_ext`, then `pyinstaller IntraPaint.spec`), with a short PowerShell
twin or a note that Git Bash runs it on Windows. AGENTS.md "Packaging" and the `requirements-dev.txt` comment
change with it.

### 3.4 libmypaint per platform

Pin **libmypaint 1.6.1** on every target. That gives Windows the same 64-setting table as Linux and removes the
56/64 split.

- **Windows:** take the DLL and its dependencies from MSYS2's `mingw-w64-x86_64-libmypaint` (or the UCRT64
  equivalent), which matches where the current DLLs appear to come from. List the dependency DLLs from `ldd`
  output in the MSYS2 shell, not by hand.
- **Linux x86_64, Linux aarch64, macOS arm64, macOS x86_64:** one script, `scripts/build_libmypaint.sh`, that
  downloads the 1.6.1 release tarball and checks its sha256. It builds json-c as a static library and links it in,
  and disables i18n, introspection, GEGL and glib. The exact configure flags need checking against 1.6.1's
  `configure --help`. Without glib, the Linux library has no system dependency beyond libc and libm, which
  removes P4. On macOS, set `MACOSX_DEPLOYMENT_TARGET` (11.0 is the oldest that supports arm64).
- **Process:** a `workflow_dispatch` workflow, `native-libs.yml`, runs those builds on the five runners and uploads
  the results. The maintainer commits them through a normal PR to `lib/<PLATFORM_TAG>/`, along with
  `lib/MANIFEST.md` recording the version, source URL, sha256 of every file and the build flags. The workflow only
  reruns when the pinned version changes.

Loader changes in `src/image/mypaint/libmypaint.py`:

1. Load order: bundled `PROJECT_DIR/lib/<PLATFORM_TAG>/` first (`lib/` in a bundle), then the user's
   `LIBMYPAINT_LIBRARY_DIR`, then `find_library`. The bundled library is the one the app is tested against.
2. Replace the per-file Windows preload with "load every non-mypaint file in the folder, then the mypaint one". That
   is the existing fallback logic, so all platforms share one code path. On Windows, `os.add_dll_directory` lets
   the loader resolve dependencies without an exact preload order.
3. Read the setting count from the loaded library instead of from `os.name`. `mypaint_brush_setting_from_cname`
   returns -1 for an unknown name, so probing the newest setting names (`posterize`, `paint_mode`) identifies a
   1.4 vs 1.5+ table directly (verified on the Linux library: 61 and 63). This also removes the
   `multiprocessing` probe and P7.

The `lib/` directory is checked-in source of this project, not a vendored third-party tree. AGENTS.md "Legacy /
don't-touch" lists `lib` among directories not to modify; that bullet needs to change when this lands.

### 3.5 `image_fill`

- **Bundles:** build it in the release job right before PyInstaller (already the `scripts/build.sh` order), on the
  same Python. Fail the job if the compiled module isn't importable before running PyInstaller, so a bundle can't
  ship the `.py`.
- **Source installs:** fix #7 with its first option: import `image_fill` lazily and disable only the fill tools,
  with a message, when it's missing. Don't publish per-platform, per-Python binaries. Since the extension isn't
  limited-API, that would be 4 Python versions times 5 platforms of artifacts to maintain, for users who mostly
  have a compiler (Linux, macOS with Xcode tools) or should use the Windows bundle.
- **Fix P6 in the same change:** run `setup.py` with `cwd=PROJECT_DIR`, check the return code, and log the
  failure. (Moving the build out of `setup.py` into a `pyproject.toml` build would also work, but isn't needed.)

### 3.6 CI build workflow (#8)

A new `.github/workflows/build.yml`:

- **Triggers:** `workflow_dispatch`, PRs into `master` (release PRs), a weekly schedule, and PRs into `integration`
  that touch `requirements*.txt`, `*.spec`, `setup.py`, `lib/**`, `IntraPaint.py` or the workflow itself. P1 shows
  that dependency bumps are what break the bundle, and Dependabot PRs touch `requirements*.txt`.
- **Job per target** from the matrix in 3.2: install `requirements-dev.txt` on Python 3.13, build `image_fill`,
  run PyInstaller, smoke-test, upload the artifact.
- **Smoke test:** with `QT_QPA_PLATFORM=offscreen` and the `platformdirs` locations pointed at a temporary
  directory (`XDG_DATA_HOME`/`XDG_STATE_HOME` on Linux; Windows and macOS need `APPDATA`/`HOME` overrides), run
  `--help`, then launch with `--mode none` under a timeout and require the log line
  `State change: from init to editing`. `--help` alone only covers the imports before argument parsing, not
  `AppController`. Also fail if the log shows the MyPaint tool failed to load on a target that ships libmypaint.
  Verified on Linux; the Windows and macOS equivalents are untested.
- **Merge gate:** the Linux x86_64 job joins the `ci` job's `needs` with "skipped counts as passed", so a bundle
  regression blocks the PR that causes it. The other targets report but don't gate, because their runners are
  slower and macOS minutes cost more on private forks.
- **Publishing stays manual.** The maintainer downloads the artifacts or runs `gh release upload`. Automating
  release creation can come later.

Bump `pyinstaller` (by hand with `pur`, per AGENTS.md "Running") to a release that builds a working bundle with the
current pins and supports Python 3.14. 6.22.3 works on 3.13. Then drop the `python_version < "3.14"` marker and the
"needs a packaged build tested first" comment in `requirements-dev.txt`, since the workflow is that test.

### 3.7 Data directories and the backend auto-install constraints (#40)

`backend_autoinstall.md` section 8 passes three constraints. How the packaging satisfies each:

- **Install outside the bundle, in a `platformdirs` folder.** Already the pattern: `DATA_DIR` in
  `src/util/shared_constants.py`. Put backends in `DATA_DIR/backends/comfyui/`, behind a new `AppConfig` key for the
  location, since a multi-GB install often belongs on another drive. Never under `PROJECT_DIR`: in a one-file bundle
  that is PyInstaller's temporary extraction folder, deleted on exit (verified: the bundle's log shows
  `PROJECT_DIR` resolving to `/tmp/_MEI.../`).
- **No user Python in bundles.** `sys.executable` in a bundle is the IntraPaint binary itself. Any provisioner code
  that starts a Python subprocess must take its interpreter from the backend install, never from `sys.executable`.
  This is a hazard for whoever writes the provisioner; `IntraPaint.py`'s `image_fill` auto-build avoids it only
  because `is_pyinstaller_bundle()` gates it.
- **Portable ComfyUI as the bundle default.** That works on Windows only. For Linux and macOS bundles, ship
  detection of existing installs plus the guided manual setup first. A fresh install there needs a Python for
  `comfy-cli`. The clean way to get one is downloading a standalone CPython build into `DATA_DIR`, which adds a new
  external download source (maintainer decision, section 6).
- **Process spawning in a frozen app.** Call `multiprocessing.freeze_support()` at the top of `IntraPaint.py`'s
  main block if any code keeps using `multiprocessing`. Prefer `subprocess`/`QProcess` for backend processes.

### 3.8 macOS signing and Gatekeeper

Only as far as it affects the plan:

- PyInstaller ad-hoc signs the collected binaries on macOS, which is enough for arm64 to run them. It doesn't
  satisfy Gatekeeper for a downloaded app.
- An unsigned, un-notarized `.app` downloaded from GitHub is quarantined. On current macOS the user has to allow it
  under System Settings, Privacy & Security, "Open Anyway". The release notes and README need those steps.
- Notarization needs a paid Apple Developer account, signing secrets in CI and a `notarytool` step. Defer it until
  macOS has a tester; it's a maintainer decision.

---

## 4. Phased plan

| Phase | Work | Issues | Depends on |
|---|---|---|---|
| **P0: build works again** | Bump PyInstaller; document the tkinter build requirement; Linux x86_64 and Windows x86_64 jobs in `build.yml` with the launch smoke test; Linux job joins the `ci` gate. | #8 | - |
| **P1: startup robustness** | Lazy `image_fill` import (#7); fix the auto-build's working directory and return code (P6); libmypaint load order and setting-count probe (P5, P7). | #7, new | - |
| **P2: one spec, clean `lib/`** | Single `IntraPaint.spec` with `lib/<PLATFORM_TAG>/` as `binaries`, per-platform Splash, no UPX, bloat excludes; `scripts/build.sh` platform-neutral; AGENTS.md "Packaging" and "Legacy / don't-touch" updated. | #8 | P0 |
| **P3: libmypaint 1.6.1 everywhere** | `scripts/build_libmypaint.sh`, `native-libs.yml`, `lib/MANIFEST.md`; new Windows DLLs from MSYS2; json-c linked in on Linux (removes P4). | #65 | P2 |
| **P4: new targets** | Linux aarch64 and macOS arm64/x86_64 jobs, macOS `BUNDLE`, Gatekeeper notes in the README. Mark as untested in the release notes. | #65 | P3 |
| **P5: backend data dir** | Backend install location key and `DATA_DIR/backends/`, as part of #40's provisioner. | #40 | independent |

P0 and P1 are useful on their own and serve the maintainer's existing Windows and Linux workflow. P3 and P4 are
mostly for other users and the portfolio.

---

## 5. What was verified vs inferred

**Verified by running (Linux x86_64, Python 3.13.14, output kept outside the repo):**
- `pyinstaller IntraPaint-linux.spec` fails without tkinter (P2).
- With Splash removed: PyInstaller 6.11.0 produces a bundle that crashes on numpy import; 6.22.3 produces one that
  passes `--help` and launches offscreen to the editing state with the MyPaint tool loaded (P1).
- Bundle contents: the Windows DLLs, Cython, setuptools and `libQt6Network` are present; the compiled
  `image_fill` is collected (P3, P8).
- `readelf`/`objdump` of everything in `lib/`, and a ctypes probe of the Linux library's setting ids (1.2).
- The auto-build fails from another working directory and succeeds from the project root (P6).
- The `DYNAMIC_MYPAINT_BRUSH_SETTINGS` probe fails under `spawn` (P7).
- Wheel platform tags in the venv (1.4); release assets via the GitHub API (1.1).

**Inferred, not run:** anything on Windows or macOS; PyInstaller's macOS Splash and one-file app limitations
(from its documentation); the libmypaint 1.6.1 configure flags; MSYS2 package naming; GitHub runner labels for
Intel macOS and ARM Linux; the per-architecture numpy/opencv wheels on macOS; the effect of a system libmypaint
on brush settings (P5); the Windows bundle shipping the `.so` (P3, by symmetry with the shared `datas` entry).

---

## 6. Decisions for the maintainer

1. **Which targets to support.** Recommended: Windows and Linux x86_64 supported; Linux aarch64 and macOS published
   as CI-built and untested. CI coverage of five targets looks good in the portfolio but costs runner time and
   upkeep for platforms nobody tests. There's no Mac available (#65), so this is a direct trade between audiences.
2. **PyInstaller bump.** Manual by policy (`dependabot.yml`); needed to ship any build with the current pins.
3. **Committed libmypaint binaries in `lib/`** with a manifest, versus CI artifacts fetched at build time.
   Recommended: committed, as today.
4. **macOS notarization** (paid Apple account). Recommended: not now.
5. **A standalone Python download for backend installs** on Linux and macOS bundles (#40). It isn't a Python
   package dependency, but it adds an external download the app runs, which the dependency policy's spirit
   covers. Recommended: defer until Windows-portable auto-install exists and has users.

No new runtime Python dependency is proposed. The build workflow adds only CI-side tools (MSYS2 via its setup
action, autotools/CMake on the runners).
