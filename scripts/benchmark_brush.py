"""Benchmark for the smudge brush: times long, fast strokes on a large layer.

The test suite never measures wall-clock time, so smudge performance is checked here instead. Each case draws one
stroke whose input points are far apart, as a fast mouse drag produces. Input arrives every INPUT_INTERVAL_SECONDS,
and the Qt event loop runs in between, so the brush's buffer timer fires as it would during a real drag. The report
covers:
- draw ms: time spent in brush calls (stroke_to, the buffer timer's slot and end_stroke) for the whole stroke.
- per point: draw time divided by the number of one-pixel smudge steps.
- worst call: the longest single brush call. Qt can't repaint the window or take input while one runs, so this is the
  lag a user sees.

Run it before and after a change to the smudge brush, on the same machine, and compare.

Usage: python scripts/benchmark_smudge.py [--repeats N]
"""
import argparse
import os
import shutil
import sys
import tempfile
import time
from typing import Callable

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# pylint: disable=wrong-import-position
from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.image.brush.smudge_brush import SmudgeBrush
from src.image.layers.image_layer import ImageLayer
from src.undo_stack import UndoStack
from test.image.brush.brush_test_case import brush_test_pattern, line_points

LAYER_SIZE = QSize(2400, 1200)
# Time between input events. Each case's point spacing over this interval sets the drag speed.
INPUT_INTERVAL_SECONDS = 0.005
# (description, brush size, hardness, antialiasing, start, end, input event spacing in pixels)
CASES = [
    ('hard, size 40', 40, 1.0, True, QPoint(100, 600), QPoint(2300, 600), 30),
    ('soft, size 40', 40, 0.3, True, QPoint(100, 600), QPoint(2300, 600), 30),
    ('hard, size 150', 150, 1.0, True, QPoint(100, 600), QPoint(2300, 600), 30),
    ('soft, size 150, diagonal', 150, 0.5, False, QPoint(100, 100), QPoint(2300, 1100), 40),
    ('soft, size 300', 300, 0.5, True, QPoint(100, 600), QPoint(2300, 600), 60),
]


def _timed(call: Callable[[], None], durations: list[float]) -> None:
    start = time.perf_counter()
    call()
    durations.append(time.perf_counter() - start)


def run_case(layer: ImageLayer, size: int, hardness: float, antialiasing: bool, start: QPoint, end: QPoint,
             spacing: int) -> tuple[float, float, int]:
    """Draws one stroke, then undoes it. Returns draw seconds, worst call seconds, and smudge step count."""
    brush = SmudgeBrush(layer)
    brush.brush_size = size
    brush.opacity = 0.7
    brush.hardness = hardness
    brush.antialiasing = antialiasing
    durations: list[float] = []
    # pylint: disable=protected-access
    timer_slot = brush._draw_buffered_events
    brush._buffer_timer.timeout.disconnect()
    brush._buffer_timer.timeout.connect(lambda: _timed(timer_slot, durations))
    brush.start_stroke()
    for point in line_points(start, end, spacing):
        _timed(lambda p=point: brush.stroke_to(p[0], p[1], None, None, None), durations)
        next_input_time = time.perf_counter() + INPUT_INTERVAL_SECONDS
        while time.perf_counter() < next_input_time:
            QApplication.processEvents()
    _timed(brush.end_stroke, durations)
    UndoStack().undo()
    step_count = max(abs(end.x() - start.x()), abs(end.y() - start.y()))
    return sum(durations), max(durations), step_count


def main() -> None:
    """Runs every case and prints the best of several repeats."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n', maxsplit=1)[0])
    parser.add_argument('--repeats', type=int, default=3, help='Runs per case. The fastest run is reported.')
    args = parser.parse_args()
    _ = QApplication.instance() or QApplication(sys.argv)
    config_dir = tempfile.mkdtemp(prefix='intrapaint-benchmark-config-')
    try:
        config_path = os.path.join(config_dir, 'app_config.json')
        shutil.copyfile(os.path.join(PROJECT_ROOT, 'test', 'resources', 'app_config_test.json'), config_path)
        AppConfig(config_path)
        layer = ImageLayer(brush_test_pattern(LAYER_SIZE), 'benchmark layer')
        print(f'{"case":<28}{"draw ms":>10}{"per point us":>14}{"worst call ms":>15}')
        for description, size, hardness, antialiasing, start, end, spacing in CASES:
            runs = [run_case(layer, size, hardness, antialiasing, start, end, spacing) for _ in range(args.repeats)]
            total = min(run[0] for run in runs)
            worst = min(run[1] for run in runs)
            point_count = runs[0][2]
            print(f'{description:<28}{total * 1000:>10.1f}{total * 1e6 / point_count:>14.1f}{worst * 1000:>15.1f}')
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)


if __name__ == '__main__':
    main()
