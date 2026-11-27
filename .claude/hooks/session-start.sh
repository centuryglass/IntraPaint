#!/bin/bash
# Starts every Claude Code session by refreshing the GitHub issue cache and printing its index as session context (see
# AGENTS.md, "Tracking open work"), and enabling the repository's git hooks.
#
# A Claude Code on the web session also gets the rest of the git history (the clone starts shallow) and is prepared to
# run the test suite and the lint check: the system libraries headless Qt needs, a Python 3.13 virtual environment with
# requirements-dev.txt, and the compiled image_fill module. Python 3.13 matches CI's lint job, since
# scripts/pylint_baseline.json is only valid for the Python version it was generated with.
#
# A new web session also fast-forwards its checkout to the newest origin/integration first (sync_new_web_session) and
# moves the local integration branch there too (update_local_integration), so a branch cut from either is current. A
# local session keeps whatever branch and commit it started on.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}"

# Reads the hook input's "source" field: startup, resume, clear or compact.
hook_source=""
if [ ! -t 0 ]; then
  hook_source="$(python3 -I -c 'import json, sys
try:
    print(json.load(sys.stdin).get("source", ""))
except ValueError:
    pass' 2>/dev/null || true)"
fi

# Fast-forwards a new web session's checkout, which can start behind origin/integration. Runs only at startup, so a
# resumed session's work is never moved. A branch that exists on the remote follows its own remote copy; any other
# branch, such as a harness-assigned one, follows origin/integration. It moves only when the tree is clean and the
# branch has no commits of its own; otherwise it prints how far behind the checkout is. Best-effort: any failure leaves
# the checkout as it is. Sets checkout_moved=1 when HEAD changes.
checkout_moved=0
sync_new_web_session() {
  local branch target before after behind
  branch="$(git symbolic-ref -q --short HEAD)" || { echo "Checkout is a detached HEAD; not syncing it." >&2; return 0; }
  if [ "$branch" != integration ] && git ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
    target="$branch"
  else
    target=integration
  fi
  git fetch -q origin "+refs/heads/$target:refs/remotes/origin/$target" \
    || { echo "git fetch of $target failed; the checkout may be behind origin/$target." >&2; return 0; }
  behind="$(git rev-list --count "HEAD..origin/$target")"
  [ "$behind" -eq 0 ] && return 0
  if ! git merge-base --is-ancestor HEAD "origin/$target"; then
    echo "Warning: $branch has commits that origin/$target lacks and is $behind commits behind it; not syncing it."
    return 0
  fi
  if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "Warning: $branch is $behind commits behind origin/$target, but has uncommitted changes; not syncing it."
    return 0
  fi
  before="$(git rev-parse HEAD)"
  git merge -q --ff-only "origin/$target" \
    || { echo "Fast-forward of $branch to origin/$target failed; it is $behind commits behind." >&2; return 0; }
  after="$(git rev-parse HEAD)"
  echo "Fast-forwarded $branch by $behind commits to origin/$target ($(git log -1 --format='%h %s' "$after"))."
  [ "$before" != "$after" ] && checkout_moved=1
  return 0
}

# Moves the local integration branch to origin/integration when it isn't checked out, so `git checkout -b <name>
# integration` starts from current code. The checked-out branch is sync_new_web_session's job. It moves only a branch
# that origin/integration descends from. Best-effort: any failure leaves the branch as it is.
update_local_integration() {
  git fetch -q origin "+refs/heads/integration:refs/remotes/origin/integration" \
    || { echo "git fetch of integration failed; the local integration branch may be behind." >&2; return 0; }
  [ "$(git symbolic-ref -q --short HEAD || true)" = integration ] && return 0
  if ! git show-ref --verify -q refs/heads/integration; then
    git branch -q integration origin/integration || true
    return 0
  fi
  if ! git merge-base --is-ancestor integration origin/integration; then
    echo "Warning: the local integration branch has commits that origin/integration lacks; not updating it."
    return 0
  fi
  [ "$(git rev-parse integration)" = "$(git rev-parse origin/integration)" ] && return 0
  git branch -q -f integration origin/integration \
    && echo "Moved the local integration branch to origin/integration ($(git log -1 --format='%h %s' integration))." \
    || echo "Could not move the local integration branch; it may be behind origin/integration." >&2
  return 0
}

if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ] && [ "$hook_source" = startup ] && [ -z "${SESSION_START_SYNCED:-}" ]; then
  sync_new_web_session
  update_local_integration
  # The fast-forward may have changed this script, so the rest of the start-up runs from the new copy.
  if [ "$checkout_moved" -eq 1 ]; then
    SESSION_START_SYNCED=1 exec "$0" </dev/null
  fi
fi

# Uses gh when it's on PATH and authenticated, and the REST API otherwise; scripts/issues.py covers tokens and rate
# limits. Either fetch is best-effort, since a rate-limited or failed one must not fail session start. When both fail,
# the hook prints no index, and AGENTS.md, "Tracking open work" says what the agent does then.
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  issue_source=--fetch
else
  issue_source=--fetch-api
fi
python3 scripts/issues.py "$issue_source" && cat .claude/cache/issues/index.md || true

# Commits regenerate and stage doc/file_map.md through .githooks/pre-commit.
git config core.hooksPath .githooks || true

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# The web session's clone is shallow. Fetching the rest of the history, with the release tags, takes seconds and about
# 80 MB. Best-effort, since a failed fetch must not fail session start.
if [ "$(git rev-parse --is-shallow-repository)" = "true" ]; then
  git fetch --unshallow --tags -q origin || echo "git fetch --unshallow failed; history stays shallow." >&2
fi

# The same packages as the "Install system libraries" step in .github/workflows/ci.yml.
SYSTEM_PACKAGES=(libegl1 libgl1 libopengl0 libxkbcommon0 libdbus-1-3 libglib2.0-0 libfontconfig1 libfreetype6 \
                 libjson-c5)
missing_packages=()
for package in "${SYSTEM_PACKAGES[@]}"; do
  # Ubuntu 24.04 renamed some libraries with a t64 suffix (libglib2.0-0 is libglib2.0-0t64). apt-get accepts the
  # old name, but dpkg doesn't.
  if ! dpkg -s "$package" >/dev/null 2>&1 && ! dpkg -s "${package}t64" >/dev/null 2>&1; then
    missing_packages+=("$package")
  fi
done
if [ ${#missing_packages[@]} -gt 0 ]; then
  SUDO=""
  if [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
  fi
  # An unreachable third-party apt source fails the update without affecting the Ubuntu packages needed here.
  $SUDO apt-get update -qq || true
  $SUDO apt-get install -y -qq --no-install-recommends "${missing_packages[@]}"
fi

python_command=python3.13
if ! command -v "$python_command" >/dev/null 2>&1; then
  python_command=python3
  echo "Python 3.13 isn't installed; using $($python_command --version). scripts/pylint_check.py may disagree" \
       "with its baseline." >&2
fi
if [ ! -x .venv/bin/python ]; then
  "$python_command" -m venv .venv
fi
.venv/bin/python -m pip install -q --upgrade pip
.venv/bin/python -m pip install -q -r requirements-dev.txt
.venv/bin/python setup.py -q build_ext --inplace

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi
