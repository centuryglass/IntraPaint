"""Saves screenshots of the style gallery, the main window and every panel at extreme sizes, with a layout report.

The renders come from `test/ui/ui_capture.py`, the same code the style gallery and panel layout tests compare against
their goldens and snapshots. It runs offscreen in mock mode with the panel layout test's config setup, so screenshots
match what the tests check. The output directory gets:
- `index.html`: every image on one page, with each capture's layout problems listed under it.
- `gallery/<control>.png`: each control in every state, labeled.
- `panels/<panel>/<size>.png`: each panel at each size `PanelScene.sizes` gives it, the main window included.
- `layout_report.json`: the size and layout problems of each capture.

Usage: python scripts/capture_ui.py [--output DIR] [--only NAME_PART ...]
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
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QPalette
from PySide6.QtWidgets import QApplication

from test.base_test_case import reset_singletons
from test.ui.ui_capture import (CELL_MARGIN, GALLERY_CONTROLS, GalleryControl, PanelHost, find_layout_problems,
                                gallery_cell_rect, layout_report, mock_app_controller, panel_scenes,
                                render_gallery_control)

LABEL_WIDTH = 110
LABEL_HEIGHT = 20


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


def capture_all(output_dir: str, filters: list[str]) -> None:
    """Captures everything into output_dir. See the module docstring for its layout."""
    # pylint: disable=import-outside-toplevel
    from src.config.application_config import AppConfig
    from src.config.cache import Cache
    from src.config.key_config import KeyConfig

    config_dir = tempfile.mkdtemp(prefix='intrapaint-capture-config-')
    try:
        # The same config setup as the panel layout test: conftest.py's fixture copies, then IntraPaintTestCase's reset.
        for config_class, file_name in ((AppConfig, 'app_config_test.json'), (KeyConfig, 'key_config_test.json'),
                                        (Cache, 'cache_test.json')):
            copy_path = os.path.join(config_dir, file_name)
            shutil.copyfile(os.path.join(PROJECT_ROOT, 'test', 'resources', file_name), copy_path)
            config_class(copy_path)
        reset_singletons()
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
                for size_case, size in scene.sizes(panel).items():
                    image = host.capture(size)
                    report[scene.name][size_case] = {
                        **layout_report(size, find_layout_problems(panel)),
                        'image': _save(image, output_dir, f'panels/{scene.name}/{size_case}.png')}
                host.release()
        with open(os.path.join(output_dir, 'layout_report.json'), 'w', encoding='utf-8') as report_file:
            json.dump(report, report_file, indent=2)
        _write_index(output_dir, gallery_paths, report)
    finally:
        shutil.rmtree(config_dir, ignore_errors=True)


def main() -> None:
    """Parses arguments and captures everything."""
    parser = argparse.ArgumentParser(description=__doc__.split('\n', maxsplit=1)[0])
    parser.add_argument('--output', default=os.path.join(tempfile.gettempdir(), 'intrapaint-ui-captures'),
                        help='Directory to write captures into. Existing files there are overwritten.')
    parser.add_argument('--only', nargs='*', default=[],
                        help='Capture only gallery controls and panels whose names contain one of these.')
    args = parser.parse_args()
    _ = QApplication.instance() or QApplication(sys.argv)
    os.makedirs(args.output, exist_ok=True)
    try:
        capture_all(args.output, args.only)
    finally:
        shutil.rmtree(_USER_DIR_ROOT, ignore_errors=True)
    index_path = os.path.join(os.path.abspath(args.output), 'index.html')
    print(f'Captures written to {index_path}')


if __name__ == '__main__':
    main()
