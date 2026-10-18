"""Saves screenshots of the style gallery, the main window and every panel at extreme sizes, with a layout report,
or sweep sheets that show panels across a grid of dock sizes.

The renders come from `test/ui/ui_capture.py`, the same code the style gallery and panel layout tests compare against
their goldens and snapshots. It runs offscreen in mock mode with the panel layout test's config setup, so screenshots
match what the tests check. The output directory gets:
- `index.html`: every image on one page, with each capture's layout problems listed under it.
- `gallery/<control>.png`: each control in every state, labeled.
- `panels/<panel>/<capture>.png`: each panel for each capture `PanelScene.captures` gives it, the main window
  included.
- `layout_report.json`: the size and layout problems of each capture.

With `--sheet`, it saves sweep sheets instead, for every panel scene and Tools panel scene (`tools_panel_scenes`) except
the main window:
- `sheets/<panel>/<orientation>.png`: one image per orientation the panel is told (`host_orientations`), with a cell
  for each size in `--widths` by `--heights`, all drawn at `--scale` so cells keep their real proportions. Each cell is
  framed at the panel's bounds and captioned with the orientation planning chose if it differs, and its problem
  count. Red marks problems. Gray marks a size below the panel's minimum size hint, which only a squeezed window
  reaches. `--overlay` outlines every widget `find_layout_problems` checks. For a readable close-up of one size, pass
  one width and height with `--scale 1`.
- `sheets/<panel>/<orientation>.json`: each cell's problems, by `<width>x<height>`.
- `index.html`: every sheet.

Usage: python scripts/capture_ui.py [--output DIR] [--only NAME_PART ...]
       python scripts/capture_ui.py --sheet [--only NAME_PART ...] [--widths W ...] [--heights H ...] [--scale S]
                                    [--overlay]
"""
import argparse
import html
import json
import os
import shutil
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
# Must be set before src.util.shared_constants is imported, so the run never writes to the real user data directories:
_USER_DIR_ROOT = tempfile.mkdtemp(prefix='intrapaint-capture-user-dirs-')
os.environ['INTRAPAINT_DATA_DIR'] = os.path.join(_USER_DIR_ROOT, 'data')
os.environ['INTRAPAINT_LOG_DIR'] = os.path.join(_USER_DIR_ROOT, 'logs')

# pylint: disable=wrong-import-position
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPalette, QPen
from PySide6.QtWidgets import QApplication

from src.ui.layout.dock_panel import DockPanel
from src.ui.layout.panel_fit import Orientation
from test.base_test_case import reset_singletons
from test.ui.ui_capture import (CELL_MARGIN, GALLERY_CONTROLS, SWEEP_HEIGHTS, SWEEP_WIDTHS, GalleryControl, PanelHost,
                                PanelScene, find_layout_problems, gallery_cell_rect, layout_report,
                                layout_widget_rects, mock_app_controller, panel_scenes, render_gallery_control,
                                tools_panel_scenes)

LABEL_WIDTH = 110
LABEL_HEIGHT = 20

SHEET_SCALE = 0.5
SHEET_GAP = 10
SHEET_AXIS_WIDTH = 48
SHEET_CAPTION_MIN_WIDTH = 96
SHEET_CAPTION_LINE = 13
SHEET_FONT_PIXELS = 11
PROBLEM_COLOR = QColor('#e0403a')
OVERLAY_COLOR = QColor(0, 160, 255, 140)


def labeled_gallery_image(control: GalleryControl) -> QImage:
    """Returns a control's gallery image with its state names above the columns and variant names left of the rows."""
    gallery = render_gallery_control(control)
    palette = QApplication.palette()
    image = QImage(gallery.size() + QSize(LABEL_WIDTH, LABEL_HEIGHT), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(palette.color(QPalette.ColorRole.Window))
    painter = QPainter(image)
    painter.drawImage(QPoint(LABEL_WIDTH, LABEL_HEIGHT), gallery)
    painter.setPen(palette.color(QPalette.ColorRole.WindowText))
    for column, state in enumerate(control.states):
        cell = gallery_cell_rect(control, 0, column)
        painter.drawText(QRect(LABEL_WIDTH + cell.x(), 0, cell.width(), LABEL_HEIGHT),
                         Qt.AlignmentFlag.AlignCenter, state.name)
    for row, variant in enumerate(control.variants):
        cell = gallery_cell_rect(control, row, 0)
        painter.drawText(QRect(CELL_MARGIN, LABEL_HEIGHT + cell.y(), LABEL_WIDTH - CELL_MARGIN, cell.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, variant)
    painter.end()
    return image


def _save(image: QImage, output_dir: str, relative_path: str) -> str:
    path = os.path.join(output_dir, relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not image.save(path):
        raise RuntimeError(f'Failed to save {path}')
    return relative_path


def _write_index(output_dir: str, gallery_paths: list[str], report: dict[str, dict[str, dict]]) -> None:
    window_color = QApplication.palette().color(QPalette.ColorRole.Window).name()
    text_color = QApplication.palette().color(QPalette.ColorRole.WindowText).name()
    parts = [f'<!doctype html><meta charset="utf-8"><title>IntraPaint UI captures</title><style>'
             f'body{{background:{window_color};color:{text_color};font-family:sans-serif;margin:16px}}'
             f'img{{border:1px dashed #888;display:block;margin:4px 0}}figure{{margin:0 0 24px}}'
             f'li{{font-family:monospace;font-size:12px}}</style><h1>IntraPaint UI captures</h1><h2>Style gallery</h2>']
    parts.extend(f'<figure><img src="{html.escape(path)}" alt=""><figcaption>{html.escape(path)}</figcaption></figure>'
                 for path in gallery_paths)
    for scene_name, captures in report.items():
        parts.append(f'<h2>{html.escape(scene_name)}</h2>')
        for size_case, capture in captures.items():
            width, height = capture['size']
            problems = ''.join(f'<li>{html.escape(problem)}</li>' for problem in capture['problems'])
            image_path = html.escape(capture['image'])
            problem_count = len(capture['problems'])
            parts.append(f'<figure><figcaption>{size_case}: {width}x{height}, {problem_count} '
                         f'problem(s)</figcaption><img src="{image_path}" alt=""><ul>{problems}</ul></figure>')
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as index_file:
        index_file.write('\n'.join(parts))


def _wanted(name: str, filters: list[str]) -> bool:
    return len(filters) == 0 or any(part in name for part in filters)


def _set_up_config(config_dir: str) -> None:
    """Sets up config the way the panel layout test does: conftest.py's fixture copies, then IntraPaintTestCase's
    reset."""
    # pylint: disable=import-outside-toplevel
    from src.config.application_config import AppConfig
    from src.config.cache import Cache
    from src.config.key_config import KeyConfig
    for config_class, file_name in ((AppConfig, 'app_config_test.json'), (KeyConfig, 'key_config_test.json'),
                                    (Cache, 'cache_test.json')):
        copy_path = os.path.join(config_dir, file_name)
        shutil.copyfile(os.path.join(PROJECT_ROOT, 'test', 'resources', file_name), copy_path)
        config_class(copy_path)
    reset_singletons()


def capture_all(output_dir: str, filters: list[str]) -> None:
    """Captures everything into output_dir. See the module docstring for its layout."""
    config_dir = tempfile.mkdtemp(prefix='intrapaint-capture-config-')
    try:
        _set_up_config(config_dir)
        controller = mock_app_controller()

        gallery_paths = [_save(labeled_gallery_image(control), output_dir, f'gallery/{control.name}.png')
                         for control in GALLERY_CONTROLS if _wanted(control.name, filters)]
        report: dict[str, dict[str, dict]] = {}
        for scene in panel_scenes(controller):
            if not _wanted(scene.name, filters):
                continue
            panel = scene.build(controller)
            if panel is None:
                continue
            report[scene.name] = {}
            with scene.context():
                host = PanelHost(panel)
                for name, (size, orientation) in scene.captures(panel).items():
                    image = host.capture(size, orientation)
                    report[scene.name][name] = {
                        **layout_report(size, find_layout_problems(panel)),
                        'image': _save(image, output_dir, f'panels/{scene.name}/{name}.png')}
                host.release()
        with open(os.path.join(output_dir, 'layout_report.json'), 'w', encoding='utf-8') as report_file:
            json.dump(report, report_file, indent=2)
        _write_index(output_dir, gallery_paths, report)
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)


def _sheet_font() -> QFont:
    font = QFont(QApplication.font())
    font.setPixelSize(SHEET_FONT_PIXELS)
    return font


def _draw_overlay(image: QImage, panel) -> None:
    painter = QPainter(image)
    painter.setPen(QPen(OVERLAY_COLOR, 1))
    for rect in layout_widget_rects(panel):
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
    painter.end()


def _cell_caption(chosen: Optional[Orientation], problem_count: int, below_minimum: bool) -> tuple[str, str]:
    first = 'below minimum' if below_minimum else ''
    if chosen is not None:
        first = f'{first}, as {chosen.value}' if first else f'as {chosen.value}'
    second = f'{problem_count} problem(s)' if problem_count > 0 else 'ok'
    return first, second


def sweep_sheet(host: PanelHost, orientation: Optional[Orientation], widths: list[int], heights: list[int],
                scale: float, overlay: bool) -> tuple[QImage, dict[str, dict]]:
    """Captures a hosted panel at every width by height and returns the sheet image and each cell's report.

    Rows are heights and columns are widths, swept row by row.
    """
    panel = host.panel
    palette = QApplication.palette()
    text_color = palette.color(QPalette.ColorRole.WindowText)
    dim_color = palette.color(QPalette.ColorRole.PlaceholderText)
    column_widths = [max(round(width * scale), SHEET_CAPTION_MIN_WIDTH) for width in widths]
    row_heights = [round(height * scale) + 2 * SHEET_CAPTION_LINE for height in heights]
    lefts = [SHEET_AXIS_WIDTH + sum(column_widths[:i]) + i * SHEET_GAP for i in range(len(widths))]
    tops = [LABEL_HEIGHT + sum(row_heights[:i]) + i * SHEET_GAP for i in range(len(heights))]
    sheet = QImage(lefts[-1] + column_widths[-1] + SHEET_GAP, tops[-1] + row_heights[-1] + SHEET_GAP,
                   QImage.Format.Format_ARGB32_Premultiplied)
    sheet.fill(palette.color(QPalette.ColorRole.Window))
    painter = QPainter(sheet)
    painter.setFont(_sheet_font())
    painter.setPen(text_color)
    for left, column_width, width in zip(lefts, column_widths, widths):
        painter.drawText(QRect(left, 0, column_width, LABEL_HEIGHT), Qt.AlignmentFlag.AlignLeft
                         | Qt.AlignmentFlag.AlignVCenter, f'w {width}')
    report: dict[str, dict] = {}
    for top, height in zip(tops, heights):
        painter.setPen(text_color)
        painter.drawText(QRect(0, top, SHEET_AXIS_WIDTH - 4, LABEL_HEIGHT), Qt.AlignmentFlag.AlignRight
                         | Qt.AlignmentFlag.AlignTop, f'h {height}')
        for left, column_width, width in zip(lefts, column_widths, widths):
            size = QSize(width, height)
            image = host.capture(size, orientation)
            problems = find_layout_problems(panel)
            minimum = panel.minimumSizeHint()
            below_minimum = minimum.isValid() and (width < minimum.width() or height < minimum.height())
            chosen = None
            if isinstance(panel, DockPanel) and orientation is not None and panel.orientation != orientation:
                chosen = panel.orientation
            if overlay:
                _draw_overlay(image, panel)
            target = QRect(left, top, max(round(width * scale), 1), max(round(height * scale), 1))
            if scale != 1:
                image = image.scaled(target.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
            painter.drawImage(target, image)
            flagged = bool(problems) and not below_minimum
            painter.setPen(QPen(PROBLEM_COLOR if flagged else dim_color, 2 if flagged else 1, Qt.PenStyle.DashLine))
            painter.drawRect(target.adjusted(0, 0, -1, -1))
            first, second = _cell_caption(chosen, len(problems), below_minimum)
            caption_top = target.bottom() + 1
            painter.setPen(dim_color if below_minimum else text_color)
            painter.drawText(QRect(left, caption_top, column_width, SHEET_CAPTION_LINE), Qt.AlignmentFlag.AlignLeft,
                             first)
            painter.setPen(PROBLEM_COLOR if flagged else (dim_color if below_minimum else text_color))
            painter.drawText(QRect(left, caption_top + (SHEET_CAPTION_LINE if first else 0), column_width,
                                   SHEET_CAPTION_LINE), Qt.AlignmentFlag.AlignLeft, second)
            report[f'{width}x{height}'] = {'below_minimum': below_minimum, 'problems': problems,
                                           **({'chosen_orientation': chosen.value} if chosen is not None else {})}
    painter.end()
    return sheet, report


def _write_sheet_index(output_dir: str, sheet_paths: list[str]) -> None:
    window_color = QApplication.palette().color(QPalette.ColorRole.Window).name()
    text_color = QApplication.palette().color(QPalette.ColorRole.WindowText).name()
    parts = [f'<!doctype html><meta charset="utf-8"><title>IntraPaint sweep sheets</title><style>'
             f'body{{background:{window_color};color:{text_color};font-family:sans-serif;margin:16px}}'
             f'img{{display:block;margin:4px 0}}figure{{margin:0 0 24px}}</style><h1>IntraPaint sweep sheets</h1>']
    parts.extend(f'<figure><figcaption>{html.escape(path)}</figcaption><img src="{html.escape(path)}" alt="">'
                 f'</figure>' for path in sheet_paths)
    with open(os.path.join(output_dir, 'index.html'), 'w', encoding='utf-8') as index_file:
        index_file.write('\n'.join(parts))


def capture_sheets(output_dir: str, filters: list[str], widths: list[int], heights: list[int], scale: float,
                   overlay: bool) -> list[str]:
    """Saves sweep sheets into output_dir and returns their paths. See the module docstring for its layout."""
    config_dir = tempfile.mkdtemp(prefix='intrapaint-capture-config-')
    sheet_paths: list[str] = []
    try:
        _set_up_config(config_dir)
        controller = mock_app_controller()
        scenes: list[PanelScene] = [scene for scene in panel_scenes(controller) + tools_panel_scenes(controller)
                                    if scene.fixed_sizes is None and _wanted(scene.name, filters)]
        for scene in scenes:
            panel = scene.build(controller)
            if panel is None:
                continue
            with scene.context():
                host = PanelHost(panel)
                try:
                    for orientation in scene.orientations(panel):
                        name = orientation.value if orientation is not None else 'undocked'
                        sheet, report = sweep_sheet(host, orientation, widths, heights, scale, overlay)
                        sheet_paths.append(_save(sheet, output_dir, f'sheets/{scene.name}/{name}.png'))
                        with open(os.path.join(output_dir, 'sheets', scene.name, f'{name}.json'), 'w',
                                  encoding='utf-8') as report_file:
                            json.dump(report, report_file, indent=2)
                finally:
                    host.release()
        _write_sheet_index(output_dir, sheet_paths)
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)
    return sheet_paths


def main() -> None:
    """Parses arguments and captures everything."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n', maxsplit=1)[0])
    parser.add_argument('--output', default=os.path.join(tempfile.gettempdir(), 'intrapaint-ui-captures'),
                        help='Directory to write captures into. Existing files there are overwritten.')
    parser.add_argument('--only', nargs='*', default=[],
                        help='Capture only gallery controls and panels whose names contain one of these.')
    parser.add_argument('--sheet', action='store_true',
                        help='Save sweep sheets of each panel across a grid of sizes instead.')
    parser.add_argument('--widths', nargs='+', type=int, default=list(SWEEP_WIDTHS), help='Sweep sheet widths.')
    parser.add_argument('--heights', nargs='+', type=int, default=list(SWEEP_HEIGHTS), help='Sweep sheet heights.')
    parser.add_argument('--scale', type=float, default=SHEET_SCALE, help='Sweep sheet scale.')
    parser.add_argument('--overlay', action='store_true', help='Outline each checked widget in sweep sheets.')
    args = parser.parse_args()
    _ = QApplication.instance() or QApplication(sys.argv)
    os.makedirs(args.output, exist_ok=True)
    try:
        if args.sheet:
            sheet_paths = capture_sheets(args.output, args.only, args.widths, args.heights, args.scale, args.overlay)
        else:
            capture_all(args.output, args.only)
    finally:
        shutil.rmtree(_USER_DIR_ROOT, ignore_errors=True)
    if args.sheet:
        for path in sheet_paths:
            print(os.path.join(os.path.abspath(args.output), path))
    index_path = os.path.join(os.path.abspath(args.output), 'index.html')
    print(f'Captures written to {index_path}')


if __name__ == '__main__':
    main()
