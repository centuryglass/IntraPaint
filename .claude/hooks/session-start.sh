#!/bin/bash
# Starts every Claude Code session by refreshing the GitHub issue cache and printing its index as session context (see
# AGENTS.md, "Tracking open work").
#
# A Claude Code on the web session is also prepared to run the test suite and the lint check: the system libraries
# headless Qt needs, a Python 3.13 virtual environment with requirements-dev.txt, and the compiled image_fill module.
# Python 3.13 matches CI's lint job, since scripts/pylint_baseline.json is only valid for the Python version it was
# generated with.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-.}"

# Uses gh when it's on PATH and authenticated, and the REST API otherwise; scripts/issues.py covers tokens and rate
# limits. Either fetch is best-effort, since a rate-limited or failed one must not fail session start. When both fail,
# an agent runs `scripts/issues.py --from-json` by hand with issue JSON from the GitHub MCP tools.
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  issue_source=--fetch
else
  issue_source=--fetch-api
fi
python3 scripts/issues.py "$issue_source" && cat .claude/cache/issues/index.md || true

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
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
