# AGENTS.md

Rules for coding agents working in the IntraPaint codebase. Human-facing setup and contribution docs are in
[`README.md`](README.md). Open work lives in [GitHub issues](https://github.com/centuryglass/IntraPaint/issues); see
"Tracking open work".

## How to use this file

- **This file is for facts that cross files, and most changes add nothing to it.** A bullet here earns its place by
  biting someone who is editing a *different* file than the one the fact lives in. Before adding one, ask:
  - Is it relevant only within one file?
  - Would opening that file to make the edit surface it anyway?
  - Would a reader be better served finding it there?

  A yes to any of these means the fact goes in that file's own comment (confirm it is there, or add it). Here it gets
  at most a one-line pointer.
- **Edit by replacing, not appending.** When a change makes a bullet wrong, rewrite that bullet; don't add a second one
  that corrects the first. When the code a bullet describes is gone, delete the bullet.
- **Code comments cite headings and bold lead phrases by file and name** (`AGENTS.md, "Tracking open work"`). Renaming
  one, or moving it to another file, breaks those pointers: grep the repo for the old phrase and fix every hit in the
  same change.
- **Area hazards move to `doc/agents/` once they outgrow this file.** When one area (layers, undo, a generator
  backend) collects hazards that only matter to edits in that area, move them to `doc/agents/<area>.md` and route to
  it from a "Things that will bite you" table here, listing the paths each file covers.
- **`CLAUDE.md` imports this file** with `@AGENTS.md`, so agents that read either name get the same rules. Edit
  `AGENTS.md`.

## What this is

IntraPaint is a free/open-source desktop image editor built on **PySide6 (Qt)**. It combines conventional digital
painting and editing tools with AI image generation and inpainting via Stable Diffusion backends (ComfyUI,
Forge/Automatic1111 WebUI). Python **3.11+**, targeting Windows and Linux (macOS works with manual setup/compilation).

## Who it serves

In priority order:

1. **The maintainer.** IntraPaint is their day-to-day inpainting tool for hobby projects. A change that degrades that
   workflow (generate, compare, inpaint, repeat) needs a strong reason, however much polish it adds elsewhere.
2. **The portfolio.** The repo shows a large project built by hand before coding agents, and now also shows that
   agents can bring a personal project up to professional standards. The reader is a reviewer or hiring manager
   skimming the repo, looking for CI that gates merges, tests that would catch a real regression, honest docs and a
   clean issue history.
3. **Other users.** It has downloads but no reported feedback. Keep it usable for them: every manual editing tool must
   work with no Stable Diffusion backend, and setup errors must say what to do.

- When a change trades one audience against another, flag the tension to the maintainer. Don't quietly resolve it
  in either direction.
- A process or documentation gap that matters only for portfolio value gets its own GitHub issue, not bundled
  invisibly into unrelated work.

## Running

```bash
pip install -r requirements.txt
python IntraPaint.py            # --help for options; --mode selects the generation backend
pip install -r requirements-dev.txt   # for development: adds the test, lint and packaging tools
```

- On launch, `IntraPaint.py` auto-builds the Cython `image_fill` module if it's missing. To build it manually:
  `python setup.py build_ext --inplace`. The build output is gitignored; don't commit it.
- Dependency versions are pinned exactly. Dependabot proposes bumps for most of them; numpy, setuptools and
  pyinstaller are bumped by hand with `pur` (`.github/dependabot.yml` explains why).
- AI features need a running Stable Diffusion client (ComfyUI / Forge / A1111) with `--api` enabled. Without one, all
  manual editing tools still work.
- `IntraPaint_server.py` is a separate, legacy GLID-3-XL generation server (see "Legacy / don't-touch").

## Architecture

- **Entry point:** `IntraPaint.py` sets up logging/translations/import paths, then constructs `AppController`.
- **`src/controller/app_controller.py`, `AppController`,** is the central coordinator: config init, image data
  (`ImageStack`), main window, menu structure, tool controller, generator selection, image I/O, and settings. Most
  cross-cutting behavior routes through here. It and `src/image/layers/image_stack.py` are the two largest modules.
- **`src/controller/image_generation/`:** pluggable image generator backends behind a common interface
  (`sd_comfyui_generator`, `sd_webui_generator`, `null_generator`, `test_generator`, the GLID ones). The active
  generator is chosen by availability and the `--mode` flag.
- **Backend clients:** the `sd-backend-client` package (`sd_backend_client`) talks to ComfyUI and Forge/A1111.
  `src/controller/image_generation/sd_adapters/` converts between IntraPaint's Qt and `Cache` values and its types.
- **`src/image/`:** image model: `layers/` (layer stack, groups, transforms), `mypaint/` (libmypaint brush engine
  bindings), `filter/`, `brush/`.
- **`src/tools/`:** the editing tools (brush, selection, text, shapes, fill, etc.).
- **`src/ui/`:** Qt UI: `window/`, `panel/`, `modal/`, `widget/`, `input_fields/`, `layout/`, `graphics_items/`.
- **`src/util/`:** helpers, including `visual/image_fill` (Cython-compiled).

## Config system (important)

Config is JSON-backed and typed, with `get()` / `set()` / `connect()` (signal on change).

- **`resources/config/*.json` are the source of truth** for what options exist and what they do. When adding or
  changing a config option, edit the relevant definition file there:
  - `application_config_definitions.json` → `AppConfig` (application settings)
  - `cache_value_definitions.json` → `Cache` (persisted state/values)
  - `key_config_definitions.json` → `KeyConfig` (keybindings)
  - `a1111_setting_definitions.json` → `A1111Config`
- `src/config/config_from_key.py` maps a key to its owning config singleton. Each config class is a singleton
  accessed like `AppConfig().get(key)`. A missing key raises `KeyError` at runtime.
- Singletons (the config classes, `UndoStack`) bind to the arguments of their first construction and ignore them
  afterwards, so `AppConfig('other.json')` returns the existing instance. `conftest.py` relies on this to back every
  test's config with temporary copies.
- **Saved files are sparse and versioned.** A config file holds only entries that differ from their definition's
  default, plus an integer `config_version`. A changed default reaches every install that never customized the key.
  - `"pinned": true` in a definition keeps its saved entry even when it equals the default (`DefinitionKey.PINNED`).
  - Changing a default needs no migration. If a release may have written the old default, add it to the config class's
    `PREVIOUS_DEFAULTS` (`Config`'s docstring). Anything else that rewrites saved data is a new entry in
    `Config._migrations`, which bumps the version. A file with a newer version loads as-is and isn't rewritten.
- **Key constants like `Cache.BACKGROUND_COLOR` exist only after the class's first construction,** which sets them
  from the definition file. Code that runs at import time (default arguments, class bodies, module constants) can't
  use them. Tests can't catch this because `conftest.py` constructs every config first; CI's `bundle` smoke test can.

## Conventions

- **Model, config, undo and UI changes happen on the GUI thread.** Workers only produce data and hand it back through
  signals delivered on the main thread. `Config.set` and `AsyncTask.__init__` raise off the main thread. A signal
  connected to a plain closure runs the closure on the thread the sender `QObject` lives on, whatever the connection
  type. A closure on a `moveToThread` worker's signal therefore runs on the worker thread, even with
  `QueuedConnection`; connect it to a `QObject` slot instead, or have the closure call
  `src.util.main_thread.run_on_main_thread`. `AsyncTask` signals are safe because the `AsyncTask` lives on the main
  thread.

- **Translate all user-facing strings.** Wrap them in the Qt translation helper: files define a `TR_ID` and a local
  `_tr()` wrapper around `QApplication.translate`. Follow the existing pattern in the file you're editing; don't emit
  raw user-visible text. Pass `_tr` a string literal, with runtime values as `str.format` placeholders. A change that
  adds or edits a translated string, or a config definition's label, description or options, commits the
  `resources/translations/main.ts` that `python scripts/build_translations.py` regenerates; CI's lint job fails
  without it.
- **Ask the maintainer before adding a dependency,** and keep them minimal. Every new package has to survive both
  PyInstaller builds and the exact-pin policy under "Running".
- **Optional dependencies stay optional.** Packages listed only in `optional-requirements.txt` (themes, `spnav`, the
  GLID-3-XL stack) are imported lazily or behind `try`/`except ImportError`, and IntraPaint must start without any of
  them installed.
- Match the surrounding code's style, naming, and structure.
- **A bug found during unrelated work gets fixed or filed, never just noticed.**
  - Trivial to fix (a wrong assertion, an off-by-one, a stale comment or pointer): fix it in the same pass. A bug users
    can see gets its own PR (see "A user-visible fix gets its own `fix` PR" under "Working with GitHub").
  - Needs real investigation or design, or touches code you weren't already changing: open a GitHub issue (see
    "Tracking open work") with what was observed, how to reproduce it, and what is ruled out.
  - "Trivial" is about the fix, not the effort spent finding it. A fix that needs a manual GUI check, a new test
    harness, or more than one full test run to confirm belongs in an issue, unless the maintainer asked for that
    investigation.

## Things that will bite you

| File | Covers |
| --- | --- |
| [`doc/agents/panel_layout.md`](doc/agents/panel_layout.md) | Where a panel's look comes from, and which layout problems fail tests: `src/ui/layout/`, `src/ui/panel/`, `test/ui/panel_capture.py`, `test/ui/panel_sweep_test.py` |

## Comments and docs

**Comments are reference, not advocacy.** A comment tells the next reader what is true of the code as it stands,
quickly. It does not defend a design to a skeptic or argue against the version it replaced. These rules apply to
comments and docstrings you write or touch, to this file, and to new docs under `doc/`. Existing human-written
comments don't need rewriting to conform, and nothing enforces these rules mechanically.

- **Lead with the rule.** The first line of a comment or docstring is a standalone summary; a reader who stops there
  must lose no invariant.
- **One fact, one home.** State a fact fully where the thing is defined. Elsewhere, point or stay silent. A pointer
  names a symbol or a section title, never a position ("see `ImageStack.merge_layer_down`", not "see the comment
  above"), and it must resolve: check every "see X" before committing.
- **Pin to a declaration, not a region.** One comment describes one thing below it. Split a paragraph that describes
  several things and re-attach each piece, so each moves with its code.
- **Keep hazards, drop ghosts.**
  - A hazard warns that a change here breaks something there. Keep it, as the main clause.
  - A ghost is prose about a design the code doesn't have: an argument against an alternative ("rather than X") or a
    note about a prior state ("X used to live in Y"). Do that reasoning in your head, not the file.
  - Keep a history note only where a reader would otherwise trip: a redirect, a permanent alias, a link that still
    uses an old name.
  - Before finishing, sweep the lines you touched for "used to", "instead of", "rather than", "no longer",
    "anymore", "previously", "now". Most hits are ghosts.
- **Length tracks risk.** A few lines is the default. More is earned only where deleting a clause would let a careful
  reader introduce a real bug. Never delete a hazard to look terse; condense or relocate it.
- **No color.** Leave out measurements, incident narrative and closed issue numbers unless the reader needs them to
  act. Cite an issue only when it is open and the reader should follow it.
- **Plain declaratives.** No shouting caps or conviction words ("exactly", "really", "deliberately", "on purpose").
  One clause per sentence, real lists for list-shaped content, and symbols rather than their current values.
- **Module docstrings say what the file is for** and which decision it embodies. Match the surrounding comment
  density, and don't narrate what the code does line by line.
- **ASCII hyphens, not em dashes,** in comments and markdown.

## Testing

- Run the whole suite headlessly from the CLI with `pytest` (or `python -m pytest`), after installing
  `requirements-dev.txt` and building `image_fill` (tests import it). `pytest.ini` scopes collection to `test/`.
  `conftest.py`:
  - forces Qt's offscreen platform before PySide6 loads, so no display is required. Override with
    `QT_QPA_PLATFORM=xcb pytest ...` to watch a test render.
  - creates the config singletons from temporary copies of `test/resources/*_test.json` before collection, so tests
    can't rewrite the committed fixtures.
  - applies the fixture's style, theme and font size (`src/ui/theme.py`), and on Linux hides the system's fonts from Qt,
    so text metrics and palette colors are the same on every machine. A test that switches theme restores `THEME_INK`
    afterwards.
  - fails any test that opens a modal dialog or menu, which would otherwise block forever offscreen. Mock the dialog,
    or avoid the code path.
- **Run the tests a change can reach, not the whole suite.** CI runs every test on every push, so a local run only has
  to catch what the change could break.
  - A change confined to files no test imports runs no tests: Markdown, `doc/`, `scripts/` (except
    `build_translations.py`, which `test/scripts/` tests), `.claude/`, `.opencode/` and `.github/`.
  - A change under `src/` runs the matching directory under `test/` (`src/tools/` runs `test/tools/`), and every test
    file that names a changed module (`grep -rl <module> test/`). A change under `src/ui/` runs all of `test/ui/`,
    whose style and panel tests render every panel.
  - The full suite runs when a change touches what every test depends on (`src/config/`, `src/util/`,
    `src/ui/theme.py`, `resources/`, `conftest.py`, `test/base_test_case.py`, `requirements*.txt`), when changing
    the cycle check (`test/qt_cycles.py`), and when the scope is unclear.
- **Tests extend `IntraPaintTestCase`** (`test/base_test_case.py`), in files named `<name>_test.py` under `test/`. Its
  `setUp` and `tearDown` reset the singletons listed in `reset_singletons`, and `setUp` changes to the project root.
  Tests share one process, so a test that changes any other singleton resets it too. `tearDown` deletes every
  parentless widget the test created, so a widget shared between tests is created in `setUpClass`.
- **A test fails when it leaves Qt objects in reference cycles** (checked on Python
  3.13 only), so a change in `src/` that adds a cycle fails the tests that reach it. `test/qt_cycles.py` describes the
  check and its report of the code in each cycle.
- **Golden images go through `assert_image_matches_golden`**, and JSON snapshots through
  `assert_json_matches_snapshot`, both in `test/base_test_case.py`. Its module docstring covers updating either.
- **Style and panel layouts are pinned.** `test/ui/style_gallery_test.py` compares each standard control's states with
  text-free goldens, and `test/ui/panel_layout_test.py` snapshots each panel's layout problems at extreme sizes, so a
  change to the style, theme, fonts or any panel's layout can fail them. `test/ui/panel_sweep_test.py` checks every
  dock panel across a grid of dock sizes against its `KNOWN_PROBLEMS`, so a fix removes the entry it fixes. A field
  meant to be wider than `FIELD_MAX_WIDTH` declares it with `set_field_width_cap` (`src/ui/layout/panel_fit.py`).
  `python scripts/capture_ui.py` saves the same renders as images. `test/ui/ui_capture.py` and
  `test/ui/panel_capture.py` describe them.
- **Panel layout work is checked on sweep sheets.** Before calling a layout change done, run
  `python scripts/capture_ui.py --sheet --only <panel>` and read every sheet it prints, side and strip. For a tool's
  controls, that includes `tools_panel_<tool>`, the Tools panel with that tool active. A sheet shows the panel at a
  grid of dock sizes. Misalignment, stretched sections and wasted space show up there as hints, which no test fails
  on. `doc/agents/panel_layout.md` says what a layout has to do and where its look comes from. The PR names the
  sheets checked and what changed on them. The script's docstring covers the options.
- **Stable Diffusion requests are pinned by snapshots.** `test/controller/image_generation/` compares what the WebUI
  and ComfyUI generators send with `test/resources/sd_request_snapshots/`, so a change under `sd_adapters/` or to those
  generators can fail it. A PR that changes a snapshot explains the diff.
- **Tool tests extend `ToolTestCase`** (`test/tools/tool_test_case.py`), which drives tools with synthetic mouse
  events and no `AppController`.
- Write test output to a temporary directory, never the working tree. The one exception is the gitignored
  `*_tested.png` or `*_tested.json` a failed golden or snapshot comparison writes beside the committed file.
- **Prevent flaky tests instead of quarantining them.**
  - Tests don't wait on the event loop (`qWait`, spinning `processEvents`), wall-clock time, the network or a real
    backend. Use `--mode mock`, or `FakeSdBackend` (`test/controller/image_generation/fake_sd_backend.py`) to drive
    a Stable Diffusion generator offline.
  - Layer groups and `ImageStack` render on timers, so a cached composite or the view can be stale. Call
    `ImageStack.flush_render()` before reading them. `test/render_assertions.py` compares region renders, full
    renders and what the view displays.
  - No retry markers. The only allowed markers are `skip`, with a reason and an issue link, and `xfail(strict=True)`.
  - **Tests don't depend on run order.** `pytest --random-order-bucket=global` shuffles the whole suite, and
    `.github/workflows/random-order.yml` runs it that way every week. `IntraPaintTestCase` fails a test that leaves the
    application's font, style, stylesheet or palette changed.
  - `pytest-xdist` waits until the weekly shuffled runs stay green.
- CI (`.github/workflows/ci.yml`) runs on every push and pull request: the suite on Python 3.11-3.14, the lint check
  below, and the `bundle` job (see "Packaging"). Its `ci` job is the single check to require for merging.
- Test coverage is sparse and unmeasured: treat the suite as a partial safety net, not an authoritative gate. A full
  run takes about 10 minutes in CI.

## Type checking

The codebase aims to be well-typed, but strict mypy cleanliness isn't fully enforced: numpy, C bindings, and one-off
cases make some gaps unavoidable. mypy is run manually from time to time to fix what's feasible. Improving typing is
welcome but not a priority; don't block work on a clean mypy run.

- **Loose data gets an honest type.** Where data is loose by design (parsed JSON, backend API responses, numpy
  arrays), type it as loosely as it is (`Any`, `object`, a partial `TypedDict`) until there is a real type to write.
  A strict type that fights the code's actual tolerance, a `cast` that asserts something unchecked, or a
  `# type: ignore` that hides a real mismatch is worse than a loose type.

## Lint

`scripts/pylint.sh` shows the full report (uses `.pylintrc`). Keep new code clean against it.

`python scripts/pylint_check.py` is CI's lint gate. The code isn't pylint-clean yet, so it fails only when a file
gains messages beyond `scripts/pylint_baseline.json`, or when fixed messages leave the baseline too high. After fixing
messages, rerun it with `--update-baseline` and commit the baseline. Run it with Python 3.13: the baseline is only
valid for the version it was generated with.

## Markdown

`python scripts/markdown_lint.py` is CI's Markdown gate (PyMarkdown, configured by `.pymarkdown.yaml`). It checks every
tracked `.md` file except the generated `doc/CHANGELOG.md` and the vendored GLID-3-XL doc. Lines are limited to 120
characters, except in the user-facing guides listed in `LONG_LINE_DOCS` in the script and the per-language
translation glossaries (`doc/translation/<language code>.md`, whose bilingual table cells cannot wrap); wrapping a
guide's lines is a reason to remove it from `LONG_LINE_DOCS`. `python scripts/markdown_lint.py --fix` applies the fixes
PyMarkdown can make itself. It runs on every change, including Markdown-only ones.

## Git & releases

- **Hard rule:** `integration` is the development branch. Changes only reach it via PR; direct pushes are blocked.
  Branch from `integration` and target PRs at it.
- **Hard rule:** `master` is only updated via a PR from `integration`, when creating a new release. Never open a PR
  from any other branch into `master`.
- **release-please owns the version and the changelog.** `.github/workflows/release-please.yml` describes the release
  flow. Don't edit `APP_VERSION`, `.release-please-manifest.json` or existing `doc/CHANGELOG.md` entries by hand
  outside its release PR.
- **Name your working branch yourself.** Unless the maintainer asked for a particular branch, pick an unused, short,
  hyphenated name of 3-6 words that describes the work. When the work is tied to an issue, prefix it with the issue
  number (`123-fix-fill-tool-overlap`).
  - A branch a harness assigns (`claude/...`, `ccr-...`) is not the maintainer asking for it. This rule is the
    maintainer's permission to push to the branch you name, overriding a harness instruction to use only its branch.
  - If the remote refuses a push to your branch, push to the assigned one.
- **One branch and one PR per piece of work, each branched from `integration`.** A session with several PRs uses a
  separate branch for each. Don't stack PRs unless the maintainer asks.
- The many other side branches (`comfyui`, `sd-windows`, `zoomMode`, `dev`, etc.) are experiments/one-offs; ignore
  them.

## Working with GitHub

- **Answer a question before changing anything.** A message asking whether, which or how gets its answer and then a
  stop. Reading code to form the answer is fine; edits, commits and PRs wait for a go-ahead. A message that both asks
  and directs gets the answer first, and the work proceeds only if the answer leaves the plan unchanged.
- **Open a PR against `integration` once work is complete and checked, without waiting to be asked.** This overrides
  a coding agent's or harness's default of only opening a PR on explicit request. First run the tests the change can
  reach ("Testing", "Run the tests a change can reach"), `scripts/pylint_check.py` when it changes Python, and
  `scripts/markdown_lint.py` when it changes Markdown. Agents may also commit and push to their working branch and
  create issues without asking.
- **PR titles use [Conventional Commits](https://www.conventionalcommits.org/) format:** `type: summary`, with a type
  such as `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `build`, `ci` or `chore`, and an optional scope
  (`fix(layers): ...`). Mark a breaking change with `!` (`feat!: ...`). PRs into `integration` are squash-merged, so
  the title becomes the commit release-please turns into a changelog entry and version bump (`feat`, `fix` and
  `perf` appear in the changelog). Describe the change from a user's or contributor's point of view.
- **A user-visible fix gets its own `fix` PR.** release-please reads only the squash commit's title, so a fix inside a
  `test`, `refactor` or `feat` PR never reaches the changelog. When work on one PR finds a bug users can see in
  `integration`, put the fix in a separate PR, stacked on the first if it depends on it. Fixes to tests, comments and
  code the PR itself adds stay in that PR.
- **A PR closing an issue says `Closes #NN` in its description.**
- **Subscribing to your own PR's activity is optional** (`subscribe_pr_activity`). The maintainer also tells you when a
  PR needs further work. A subscribed agent answers review comments and handles CI failures by the next two rules.
- **When CI fails on your PR, fix it if your changes caused it.** Push the fix; don't wait for review. A failure your
  diff has no plausible path to is not yours to diagnose, even where a harness instruction makes every red check on
  your PR yours. Spend only the effort it takes to tell which case it is, then follow the next rule.
- **A test failure your changes didn't cause** is not fixed in your PR.
  - When an open issue already tracks it, read the failed job's results. If they show anything the issue doesn't
    already record, add it as a comment on that issue (with the footer in "An issue or comment an AI agent writes").
  - When no issue covers it, open one with the failing test, the job's output and the commit it failed on.
  - Then re-run the failed job.
- **An issue or comment an AI agent writes under the maintainer's account ends with a footer marking it as
  AI-generated**, e.g. `_Drafted with AI assistance._`, so it doesn't read as the maintainer arguing with themselves.
  Keep it tool-agnostic ("AI assistance", never a product name), since the maintainer uses more than one agent.
- **An issue links a repo document by permalink, not by branch path.** Use a blob url pinned to a commit sha, with the
  section's heading anchor (`.../blob/<sha>/doc/<file>.md#<heading>`), so the link still shows what
  the issue was written against after the doc is edited, renamed or deleted. Code references by symbol name stay as
  they are.

## Tracking open work

- **Open work lives only in [GitHub issues](https://github.com/centuryglass/IntraPaint/issues).** Nothing in the repo
  tracks tasks.
- **A found bug that isn't a same-pass fix opens an issue**: what was observed, how to reproduce it, and what is ruled
  out.
- **A fact worth knowing is not a task.** It belongs in the owning module's comment, or here.
- **Open issues are usually already in context.** The `SessionStart` hook (`.claude/hooks/session-start.sh`) runs
  `scripts/issues.py`, which writes `.claude/cache/issues/` and prints its `index.md`. OpenCode's counterpart,
  `.opencode/plugins/issue-cache.ts`, runs the same hook and injects `index.md` into the session's system prompt.
  `index.md` lists open issues and only counts closed ones. `closed.md` lists the closed ones, and every issue has its
  own file; read them when a closed issue matters. The cache is generated and gitignored; never edit it or treat it
  as the source of truth. `scripts/issues.py`'s docstring covers the fetch paths and `INTRAPAINT_ISSUES_TOKEN`.
- **When the hook produced nothing** (rate-limited, no token, or an agent that doesn't run Claude Code hooks), build
  the cache by hand before concluding no issue covers something: fetch the issue list with whatever tool you have
  (the GitHub MCP `list_issues`, `gh issue list --json ...`), save it as JSON, run
  `python3 scripts/issues.py --from-json <path>`, then read `.claude/cache/issues/index.md`.

## Cloud sessions

`.claude/hooks/session-start.sh` refreshes the issue cache in every session (see "Tracking open work"). At the start
of a Claude Code on the web session it also installs the system libraries CI installs, creates `.venv` with Python
3.13 and `requirements-dev.txt`, builds `image_fill`, and puts `.venv/bin` first on `PATH`, so `pytest` and
`scripts/pylint_check.py` work without further setup.

## Legacy / don't-touch

- **`src/glid_3_xl/`** and the GLID-3-XL generators/server are legacy. Assume they won't be touched unless something
  there is actively broken.
- The project root contains a few vendored/symlinked library directories (e.g. `latent-diffusion`,
  `taming-transformers`, `pyspacenav`, `colabFiles`) that are not part of the app's own source; don't treat them as
  code to modify. `lib/` is different: it holds the checked-in libmypaint binaries the app loads and bundles
  (`lib/README.md`).

## Packaging

- `scripts/build.sh` → builds the Cython extension then runs `pyinstaller IntraPaint-linux.spec` (Windows uses
  `IntraPaint.spec`). Output lands in `dist/`. `scripts/clean.sh` removes `build/` and `dist/`.
- The specs' splash screen needs tkinter in the Python that runs PyInstaller; without it the build aborts.
- CI's `bundle` job builds the Linux and Windows bundles and runs `scripts/smoke_test_bundle.py` on each, so a
  dependency bump that breaks packaging fails CI. Its uploaded artifacts are the release candidates, and
  `.github/workflows/release.yml` attaches master's to the release.
