#!/bin/bash
# Run pylint to identify code style issues.
pylint --rcfile=.pylintrc src | less
