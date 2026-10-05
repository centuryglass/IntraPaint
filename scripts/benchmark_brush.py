"""Benchmark for the smudge, draw, eraser and MyPaint brushes: times long, fast strokes on a large layer.

The test suite never measures wall-clock time, so brush performance is checked here instead. Each case draws one
stroke whose input points are far apart, as a fast mouse drag produces. Input arrives every INPUT_INTERVAL_SECONDS,
and the Qt event loop runs in between, so the brush's buffer timer fires as it would during a real drag. The MyPaint
brush's buffer timer is its surface's timer for writing changed tiles to the layer. The report covers:
- draw ms: time spent in brush calls (stroke_to, the buffer timer's slot and end_stroke) for the whole stroke.
- per unit us: draw time divided by the stroke's work units. A smudge stroke's unit is one one-pixel smudge step, and
  a draw, eraser or MyPaint stroke's unit is one input event.
- worst call: the longest single brush call. Qt can't repaint the window or take input while one runs, so this is the
  lag a user sees.

Run it before and after a change to a brush, on the same machine, and compare.

Usage: python scripts/benchmark_brush.py [--brush {smudge,draw,eraser,mypaint,all}] [--repeats N]
"""
import argparse
import os
import shutil
import sys
import tempfile
import time
from typing import Callable, NamedTuple

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# pylint: disable=wrong-import-position
from PySide6.QtCore import QPoint, QSize, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.image.brush.layer_brush import LayerBrush
from src.image.brush.mypaint_layer_brush import MyPaintLayerBrush
from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.brush.smudge_brush import SmudgeBrush
from src.image.layers.image_layer import ImageLayer
from src.undo_stack import UndoStack
from test.image.brush.brush_test_case import brush_test_pattern, line_points

# Time between input events. Each case's point spacing over this interval sets the drag speed.
INPUT_INTERVAL_SECONDS = 0.005


class Case(NamedTuple):
    """One benchmark stroke. MyPaint cases ignore hardness and antialiasing, and only MyPaint cases use brush_file."""
    description: str
    size: int
    hardness: float
    antialiasing: bool
    start: QPoint
    end: QPoint
    spacing: int  # Distance between input events, in pixels
    brush_file: str = ''


class BrushBenchmark(NamedTuple):
    """The benchmark cases for one brush type."""
    layer_size: QSize
    create_brush: Callable[[ImageLayer], LayerBrush]
    # Applies a case's settings to a new brush:
    configure: Callable[[LayerBrush, Case], None]
    # Returns the brush's buffer timer and the slot its timeout calls:
    buffer_timer: Callable[[LayerBrush], tuple[QTimer, Callable[[], None]]]
    # Returns a case's work unit count from its input event count:
    unit_count: Callable[[Case, int], int]
    cases: list[Case]


def _smudge_steps(case: Case, _event_count: int) -> int:
    return max(abs(case.end.x() - case.start.x()), abs(case.end.y() - case.start.y()))


def _create_draw_brush(layer: ImageLayer) -> LayerBrush:
    brush = QtPaintBrush(layer)
    brush.brush_color = QColor(30, 90, 200)
    return brush


def _create_eraser_brush(layer: ImageLayer) -> LayerBrush:
    brush = QtPaintBrush(layer)
    brush.eraser = True
    return brush


def _create_mypaint_brush(layer: ImageLayer) -> LayerBrush:
    brush = MyPaintLayerBrush(layer)
    brush.brush_color = QColor(30, 90, 200)
    return brush


def _configure_qt_brush(opacity: float) -> Callable[[LayerBrush, Case], None]:
    def _configure(brush: LayerBrush, case: Case) -> None:
        brush.opacity = opacity  # type: ignore[attr-defined]
        brush.hardness = case.hardness  # type: ignore[attr-defined]
        brush.antialiasing = case.antialiasing  # type: ignore[attr-defined]
    return _configure


def _configure_mypaint_brush(brush: LayerBrush, case: Case) -> None:
    assert isinstance(brush, MyPaintLayerBrush)
    brush.brush_path = os.path.join(PROJECT_ROOT, 'resources', 'brushes', case.brush_file)


# pylint: disable=protected-access
def _qt_buffer_timer(brush: LayerBrush) -> tuple[QTimer, Callable[[], None]]:
    return brush._buffer_timer, brush._draw_buffered_events  # type: ignore[attr-defined]


def _mypaint_buffer_timer(brush: LayerBrush) -> tuple[QTimer, Callable[[], None]]:
    assert isinstance(brush, MyPaintLayerBrush)
    surface = brush._mp_surface
    return surface._pending_tile_timer, surface.apply_pending_tile_updates
# pylint: enable=protected-access


def _event_count(_case: Case, event_count: int) -> int:
    return event_count


BENCHMARKS = {
    'smudge': BrushBenchmark(QSize(2400, 1200), SmudgeBrush, _configure_qt_brush(0.7), _qt_buffer_timer,
                             _smudge_steps, [
        Case('hard, size 40', 40, 1.0, True, QPoint(100, 600), QPoint(2300, 600), 30),
        Case('soft, size 40', 40, 0.3, True, QPoint(100, 600), QPoint(2300, 600), 30),
        Case('hard, size 150', 150, 1.0, True, QPoint(100, 600), QPoint(2300, 600), 30),
        Case('soft, size 150, diagonal', 150, 0.5, False, QPoint(100, 100), QPoint(2300, 1100), 40),
        Case('soft, size 300', 300, 0.5, True, QPoint(100, 600), QPoint(2300, 600), 60),
    ]),
    'draw': BrushBenchmark(QSize(1600, 800), _create_draw_brush, _configure_qt_brush(0.8), _qt_buffer_timer,
                           _event_count, [
        Case('hard, size 40', 40, 1.0, False, QPoint(100, 400), QPoint(1500, 400), 8),
        Case('soft, size 40', 40, 0.4, True, QPoint(100, 400), QPoint(1500, 400), 8),
        Case('soft, size 150', 150, 0.4, True, QPoint(100, 400), QPoint(1500, 400), 8),
        Case('soft, size 150, diagonal', 150, 0.4, True, QPoint(100, 100), QPoint(1500, 700), 8),
        Case('soft, size 300', 300, 0.4, True, QPoint(100, 400), QPoint(1500, 400), 8),
    ]),
    'eraser': BrushBenchmark(QSize(1600, 800), _create_eraser_brush, _configure_qt_brush(0.8), _qt_buffer_timer,
                             _event_count, [
        Case('hard, size 40', 40, 1.0, False, QPoint(100, 400), QPoint(1500, 400), 8),
        Case('soft, size 150', 150, 0.4, True, QPoint(100, 400), QPoint(1500, 400), 8),
    ]),
    'mypaint': BrushBenchmark(QSize(1600, 800), _create_mypaint_brush, _configure_mypaint_brush, _mypaint_buffer_timer,
                              _event_count, [
        Case('bulk, size 40', 40, 1.0, True, QPoint(100, 400), QPoint(1500, 400), 8, 'classic/bulk.myb'),
        Case('bulk, size 150', 150, 1.0, True, QPoint(100, 400), QPoint(1500, 400), 8, 'classic/bulk.myb'),
        Case('charcoal, size 150', 150, 1.0, True, QPoint(100, 400), QPoint(1500, 400), 8, 'classic/charcoal.myb'),
        Case('blend+paint, size 40', 40, 1.0, True, QPoint(100, 400), QPoint(1500, 400), 8,
             'classic/blend+paint.myb'),
        Case('blend+paint, size 150', 150, 1.0, True, QPoint(100, 400), QPoint(1500, 400), 8,
             'classic/blend+paint.myb'),
        Case('blend+paint, size 150, diagonal', 150, 1.0, True, QPoint(100, 100), QPoint(1500, 700), 8,
             'classic/blend+paint.myb'),
    ]),
}


def _timed(call: Callable[[], None], durations: list[float]) -> None:
    start = time.perf_counter()
    call()
    durations.append(time.perf_counter() - start)


def run_case(benchmark: BrushBenchmark, layer: ImageLayer, case: Case) -> tuple[float, float, int]:
    """Draws one stroke, then undoes it. Returns draw seconds, worst call seconds, and work unit count."""
    brush = benchmark.create_brush(layer)
    benchmark.configure(brush, case)
    brush.brush_size = case.size
    durations: list[float] = []
    timer, timer_slot = benchmark.buffer_timer(brush)
    timer.timeout.disconnect()
    timer.timeout.connect(lambda: _timed(timer_slot, durations))
    points = line_points(case.start, case.end, case.spacing)
    brush.start_stroke()
    for point in points:
        _timed(lambda p=point: brush.stroke_to(p[0], p[1], None, None, None), durations)
        next_input_time = time.perf_counter() + INPUT_INTERVAL_SECONDS
        while time.perf_counter() < next_input_time:
            QApplication.processEvents()
    _timed(brush.end_stroke, durations)
    brush.connect_to_layer(None)
    UndoStack().undo()
    return sum(durations), max(durations), benchmark.unit_count(case, len(points))


def main() -> None:
    """Runs every case and prints the best of several repeats."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n', maxsplit=1)[0])
    parser.add_argument('--brush', choices=[*BENCHMARKS, 'all'], default='all', help='Brush to benchmark.')
    parser.add_argument('--repeats', type=int, default=3, help='Runs per case. The fastest run is reported.')
    args = parser.parse_args()
    _ = QApplication.instance() or QApplication(sys.argv)
    config_dir = tempfile.mkdtemp(prefix='intrapaint-benchmark-config-')
    try:
        config_path = os.path.join(config_dir, 'app_config.json')
        shutil.copyfile(os.path.join(PROJECT_ROOT, 'test', 'resources', 'app_config_test.json'), config_path)
        AppConfig(config_path)
        brush_names = list(BENCHMARKS) if args.brush == 'all' else [args.brush]
        print(f"{'case':<44}{'draw ms':>10}{'per unit us':>13}{'worst call ms':>15}")
        for brush_name in brush_names:
            benchmark = BENCHMARKS[brush_name]
            layer = ImageLayer(brush_test_pattern(benchmark.layer_size), 'benchmark layer')
            for case in benchmark.cases:
                runs = [run_case(benchmark, layer, case) for _ in range(args.repeats)]
                total = min(run[0] for run in runs)
                worst = min(run[1] for run in runs)
                unit_count = runs[0][2]
                description = f'{brush_name}: {case.description}'
                print(f'{description:<44}{total * 1000:>10.1f}{total * 1e6 / unit_count:>13.1f}'
                      f'{worst * 1000:>15.1f}')
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)


if __name__ == '__main__':
    main()
