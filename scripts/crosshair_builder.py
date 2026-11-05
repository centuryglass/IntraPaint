"""Interactive builder for `src/ui/brush_crosshair.py` crosshair patterns.

A single-window PySide6 app. The left side is a 15x15 checkbox grid: a checked box is a '#' core pixel, an unchecked
one is '.'. The copy button writes the grid to the clipboard in the tuple format `_PATTERNS` uses, and paste reads that
format back. The right side previews the grid as a cursor over four backgrounds (solid black, solid white, the
transparency tile, and the Canny example image), drawn by `crosshair_pattern_image`, the same code the app builds its
cursors from. The mouse cursor is hidden over the preview, and the crosshair is drawn with its hotspot on the mouse.
The preview draws each pattern cell four pixels wide; the 'Actual size' toggle beside the clipboard buttons switches it
to the crosshair's true cursor size on the current screen.

Usage: python scripts/crosshair_builder.py
"""
import os
import re
import sys
from typing import Sequence

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# pylint: disable=wrong-import-position
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QGridLayout, QHBoxLayout, QMainWindow, QMessageBox, QPushButton,
                               QStyle, QVBoxLayout, QWidget)

# The private `_PATTERNS` dict is the thing this tool edits, so it reads the PLAIN pattern it seeds the grid with:
from src.ui.brush_crosshair import (CROSSHAIR_GRID_SIZE, CROSSHAIR_SIZE, CrosshairVariant, _PATTERNS,
                                    crosshair_pattern_image, crosshair_pixel_scale)
from src.util.visual.image_utils import get_transparency_tile_pixmap

GRID_SIZE = CROSSHAIR_GRID_SIZE
# Each pattern cell is drawn this many pixels wide in the preview, keeping the pattern and its halo readable.
PREVIEW_PIXEL_SCALE = 4
CANNY_IMAGE_PATH = os.path.join(PROJECT_ROOT, 'examples', 'controlnet_example_canny.png')


def _parse_pattern(text: str) -> tuple[str, ...] | None:
    """Parses a pattern in the `_PATTERNS` value format, or None if the text isn't one.

    Accepts 15 rows of 15 '#'/'.' characters, one row per line, optionally single- or double-quoted,
    comma-separated and wrapped in parentheses.
    """
    text = text.strip()
    if text.startswith('(') and text.endswith(')'):
        text = text[1:-1]
    rows = []
    for piece in re.split(r'[,\n]', text):
        row = piece.strip().strip('\'"')
        if row:
            rows.append(row)
    if len(rows) != GRID_SIZE:
        return None
    for row in rows:
        if len(row) != GRID_SIZE or any(char not in '#.' for char in row):
            return None
    return tuple(rows)


class CrosshairPreview(QWidget):
    """Paints the current pattern as a cursor over four backgrounds, at the mouse position while the mouse is inside.

    Top-left is solid black, top-right solid white, bottom-left the transparency tile and bottom-right the Canny
    example image, so the crosshair is previewed over dark, light, mid-gray and busy content.
    """

    _canny_pixmap_cache: QPixmap | None = None

    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)
        self.setMinimumSize(400, 320)
        # The pattern replaces the pointer, exactly as it does as a real cursor:
        self.setCursor(Qt.CursorShape.BlankCursor)
        self._tile_pixmaps: dict[tuple[int, int], QPixmap] = {}
        self._mouse_position: QPoint | None = None
        self._pattern_image: QImage | None = None

    def set_pattern_image(self, image: QImage) -> None:
        self._pattern_image = image
        self.update()

    def mouseMoveEvent(self, event) -> None:
        self._mouse_position = event.position().toPoint()
        self.update()

    def leaveEvent(self, event) -> None:
        self._mouse_position = None
        self.update()

    def _transparency_tile(self, size) -> QPixmap:
        key = (size.width(), size.height())
        pixmap = self._tile_pixmaps.get(key)
        if pixmap is None:
            pixmap = get_transparency_tile_pixmap(size)
            self._tile_pixmaps[key] = pixmap
        return pixmap

    @classmethod
    def _canny_pixmap(cls) -> QPixmap:
        # Loading needs a QApplication, so it happens on first paint, not at import time:
        if cls._canny_pixmap_cache is None:
            cls._canny_pixmap_cache = QPixmap(CANNY_IMAGE_PATH)
        pixmap = cls._canny_pixmap_cache
        assert pixmap is not None
        return pixmap

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        mid_x = self.width() // 2
        mid_y = self.height() // 2
        painter.fillRect(QRect(0, 0, mid_x, mid_y), QColor(0, 0, 0))
        painter.fillRect(QRect(mid_x, 0, self.width() - mid_x, mid_y), QColor(255, 255, 255))
        tile_bounds = QRect(0, mid_y, mid_x, self.height() - mid_y)
        painter.drawPixmap(tile_bounds.topLeft(), self._transparency_tile(tile_bounds.size()))
        canny_bounds = QRect(mid_x, mid_y, self.width() - mid_x, self.height() - mid_y)
        self._draw_image_fill(painter, canny_bounds, self._canny_pixmap())
        if self._mouse_position is not None and self._pattern_image is not None:
            image = self._pattern_image
            painter.drawImage(self._mouse_position - QPoint(image.width() // 2, image.height() // 2), image)

    @staticmethod
    def _draw_image_fill(painter: QPainter, bounds: QRect, pixmap: QPixmap) -> None:
        """Fills `bounds` with `pixmap`, scaling it to cover the area without distortion."""
        if pixmap.isNull():
            painter.fillRect(bounds, QColor(32, 32, 32))
            return
        scaled = pixmap.scaled(bounds.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
        painter.save()
        painter.setClipRect(bounds)
        painter.drawPixmap(bounds.center() - scaled.rect().center(), scaled)
        painter.restore()


class CrosshairBuilderWindow(QMainWindow):
    """The builder's single window: the pattern grid and clipboard buttons on the left, the cursor preview on the
    right."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Crosshair builder')
        self._boxes: list[list[QCheckBox]] = []
        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.addWidget(self._build_grid_panel())
        self._preview = CrosshairPreview()
        layout.addWidget(self._preview, 1)
        self.setCentralWidget(central)
        self.resize(720, 420)
        # Seed the grid with the PLAIN pattern so the preview shows a crosshair on launch:
        self._apply_pattern(_PATTERNS[CrosshairVariant.PLAIN])

    def _build_grid_panel(self) -> QWidget:
        panel = QWidget(self)
        panel_layout = QVBoxLayout(panel)
        grid_widget = QWidget(panel)
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        # Cells are exactly the indicator's size with no gap, so the grid is tight and still readable:
        grid.setSpacing(0)
        cell_size = QCheckBox(grid_widget).style().pixelMetric(QStyle.PixelMetric.PM_IndicatorWidth)
        self._boxes = []
        for y in range(GRID_SIZE):
            row = []
            for x in range(GRID_SIZE):
                box = QCheckBox(grid_widget)
                box.setFixedSize(cell_size, cell_size)
                box.stateChanged.connect(lambda *_: self._refresh_preview())
                grid.addWidget(box, y, x)
                row.append(box)
            self._boxes.append(row)
        panel_layout.addWidget(grid_widget)
        buttons = QHBoxLayout()
        copy_button = QPushButton('copy', panel)
        paste_button = QPushButton('paste', panel)
        copy_button.clicked.connect(self._copy_pattern)
        paste_button.clicked.connect(self._paste_pattern)
        self._actual_size_toggle = QCheckBox('Actual size', panel)
        self._actual_size_toggle.toggled.connect(lambda *_: self._refresh_preview())
        buttons.addStretch(1)
        buttons.addWidget(copy_button)
        buttons.addWidget(paste_button)
        buttons.addWidget(self._actual_size_toggle)
        buttons.addStretch(1)
        panel_layout.addLayout(buttons)
        return panel

    def _current_pattern(self) -> tuple[str, ...]:
        return tuple(''.join('#' if self._boxes[y][x].isChecked() else '.' for x in range(GRID_SIZE))
                     for y in range(GRID_SIZE))

    def _apply_pattern(self, pattern: Sequence[str]) -> None:
        for y, row in enumerate(pattern):
            for x, char in enumerate(row):
                self._boxes[y][x].setChecked(char == '#')
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        if self._actual_size_toggle.isChecked():
            # The crosshair at the size a real cursor has on this screen's density:
            scale = crosshair_pixel_scale(self._preview.devicePixelRatioF())
        else:
            scale = PREVIEW_PIXEL_SCALE
        self._preview.set_pattern_image(crosshair_pattern_image(self._current_pattern(), scale))

    def _copy_pattern(self) -> None:
        lines = ['(']
        lines.extend(f"    '{row}'," for row in self._current_pattern())
        lines.append(')')
        QApplication.clipboard().setText('\n'.join(lines))

    def _paste_pattern(self) -> None:
        pattern = _parse_pattern(QApplication.clipboard().text())
        if pattern is None:
            QMessageBox.critical(
                self, 'Invalid pattern',
                'The clipboard does not contain a crosshair pattern. Copy one with the copy button, or paste a '
                'parenthesised, comma-separated list of 15 quoted 15-character rows of \'#\' and \'.\'.')
            return
        self._apply_pattern(pattern)


def main() -> None:
    app = QApplication(sys.argv)
    window = CrosshairBuilderWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
