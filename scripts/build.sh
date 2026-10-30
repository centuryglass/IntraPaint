#!/bin/bash
# Builds the pre-packaged IntraPaint distribution file for the current platform.
# On Windows, run it from Git Bash.
set -e
python setup.py build_ext --inplace
pyinstaller --noconfirm IntraPaint.spec
