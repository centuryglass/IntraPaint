#!/bin/bash
# Run with profiling, then open profile for visualization.
if ! type "snakeviz" > /dev/null; then
    echo 'snakeviz not found'
    exit
fi
python -m cProfile -o intrapaint_profile IntraPaint.py --init_image test/resources/test_images/layer_blend_test.ora --mode none
snakeviz intrapaint_profile
