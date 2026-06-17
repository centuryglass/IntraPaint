#!/bin/bash
# Builds the pre-packaged IntraPaint distribution file
python setup.py build_ext --inplace
pyinstaller IntraPaint-linux.spec
