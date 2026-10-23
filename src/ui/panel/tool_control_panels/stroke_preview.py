"""Stroke previews for the Qt brush tool panels.

`StrokePreview` is the shared base: it draws one sample stroke with a layer brush on a scratch `ImageLayer`, so a
preview honors the same settings as the canvas. A tool's preview is a subclass that overrides the hooks `_new_layer`,
`_new_brush`, `_configure_brush` and `_finish`, and adds the inputs those hooks read to `_inputs`. A panel builds its
preview and passes it to `StrokeBlock`.
"""
import math
from collections.abc import Hashable
from typing import Any, Optional

from PySide6.QtCore import QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPalette
from PySide6.QtWidgets import QSizePolicy, QWidget

from src.config.cache import Cache
from src.image.brush.qt_paint_brush import QtPaintBrush
from src.image.brush.smudge_brush import SmudgeBrush
from src.image.layers.image_layer import ImageLayer
from src.ui.input_fields.fill_style_combo_box import BRUSH_PATTERN_SOLID, FillStyleComboBox
from src.ui.panel.tool_control_panels.brush_preview import BrushPreview
from src.ui.panel.tool_control_panels.preview_backdrop import backdrop_image
from src.undo_stack import UndoStack
from src.util.visual.contrast_color import contrast_ratio
from src.util.visual.keycap import keycap_colors
from src.util.visual.image_utils import tile_pattern_fill

PREVIEW_MIN_SIZE = QSize(120, 72)
PREVIEW_MAX_SIZE = QSize(400, 160)
PREVIEW_STAMP_SPACING = 0.2
PREVIEW_CHECKER_TILE_SIZE = 6


class StrokePreview(BrushPreview):
    """Previews a sample stroke of the size, opacity, hardness and antialiasing in `Cache`.

    Subclasses change what is drawn and how it is shown through `_new_layer`, `_configure_brush` and `_finish`, and
    list the `Cache` keys they add in `extra_keys` and their values in `_inputs`.
    """

    def __init__(self, size_key: str, opacity_key: Optional[str], hardness_key: Optional[str],
                 antialias_key: Optional[str] = None, extra_keys: tuple[Optional[str], ...] = (),
                 parent: Optional[QWidget] = None, render_timer: Optional[QTimer] = None) -> None:
        self._size_key = size_key
        self._opacity_key = opacity_key
        self._hardness_key = hardness_key
        self._antialias_key = antialias_key
        super().__init__((size_key, opacity_key, hardness_key, antialias_key, *extra_keys), parent, render_timer)
        self.setMinimumSize(PREVIEW_MIN_SIZE)
        self.setMaximumSize(PREVIEW_MAX_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        """Returns a short, wide area."""
        return PREVIEW_MIN_SIZE

    def _value(self, key: Optional[str], default: Any) -> Any:
        return default if key is None else Cache().get(key)

    def _inputs(self) -> Hashable:
        return (self._value(self._size_key, 1), self._value(self._opacity_key, 1.0),
                self._value(self._hardness_key, 1.0), self._value(self._antialias_key, False))

    def _new_layer(self, size: QSize) -> ImageLayer:
        """Returns the scratch layer the stroke is drawn on. The default is transparent."""
        return ImageLayer(size, 'brush preview')

    def _new_brush(self, layer: ImageLayer) -> Any:
        """Returns the brush that draws the stroke on `layer`. The default is a `QtPaintBrush`."""
        return QtPaintBrush(layer)

    def _configure_brush(self, brush: Any) -> None:
        """Applies the preview's settings to the brush, except its size. Subclasses extend this."""
        brush.opacity = float(self._value(self._opacity_key, 1.0))
        brush.hardness = float(self._value(self._hardness_key, 1.0))
        brush.antialiasing = bool(self._value(self._antialias_key, False))

    def _finish(self, layer_image: QImage) -> QImage:
        """Returns the image to show for the drawn layer. The default is the layer itself."""
        return layer_image

    def _sample_stroke(self, size: QSize) -> tuple[float, list[QPointF]]:
        """Returns the brush diameter shrunk to fit, and points along a wave at the brush's stamp spacing."""
        margin = 6.0
        available = max(size.height() - 2 * margin, 1.0)
        diameter = max(1.0, min(float(self._value(self._size_key, 1)), available * 0.5))
        radius = diameter / 2
        left, right = margin + radius, size.width() - margin - radius
        if right <= left:
            return diameter, []
        amplitude = max((available - diameter) / 2, 0.0)
        spacing = max(1.0, diameter * PREVIEW_STAMP_SPACING)
        center_y = size.height() / 2
        span = max(right - left, 1.0)
        points = []
        x = left
        while x <= right:
            points.append(QPointF(x, center_y + amplitude * math.sin((x - left) / span * 2 * math.pi)))
            x += spacing
        return diameter, points

    def _render(self, size: QSize) -> QImage:
        """Draws the sample stroke with a `QtPaintBrush` on a scratch layer, keeping its edits out of undo history."""
        diameter, points = self._sample_stroke(size)
        with UndoStack().unrecorded():
            layer = self._new_layer(size)
            brush = self._new_brush(layer)
            brush.brush_size = round(diameter)
            self._configure_brush(brush)
            brush.start_stroke()
            for point in points:
                brush.stroke_to(point.x(), point.y(), None, None, None)
            brush.end_stroke()
            brush.connect_to_layer(None)
            return self._finish(layer.image)


class DrawStrokePreview(StrokePreview):
    """Previews painting: the stroke in the tool's color and pattern, over the preview background."""

    def __init__(self, size_key: str, opacity_key: Optional[str], hardness_key: Optional[str],
                 color_key: Optional[str], pattern_key: Optional[str] = None, antialias_key: Optional[str] = None,
                 parent: Optional[QWidget] = None, render_timer: Optional[QTimer] = None) -> None:
        self._color_key = color_key
        self._pattern_key = pattern_key
        super().__init__(size_key, opacity_key, hardness_key, antialias_key, (color_key, pattern_key), parent,
                         render_timer)

    def _color(self) -> QColor:
        color = QColor(self.palette().color(QPalette.ColorRole.Text))
        if self._color_key is not None:
            color = Cache().get_color(self._color_key, color)
        return color

    def _background(self) -> QColor:
        """Returns the panel background or the keycap fill, whichever contrasts more with the brush color."""
        panel_background = super()._background()
        keycap_fill = keycap_colors(self.palette())[0]
        color = self._color()
        if contrast_ratio(keycap_fill, color) > contrast_ratio(panel_background, color):
            return keycap_fill
        return panel_background

    def _inputs(self) -> Hashable:
        return (super()._inputs(), self._color().name(QColor.NameFormat.HexArgb),
                self._value(self._pattern_key, BRUSH_PATTERN_SOLID))

    def _configure_brush(self, brush: Any) -> None:
        super()._configure_brush(brush)
        brush.brush_color = self._color()
        pattern = self._value(self._pattern_key, BRUSH_PATTERN_SOLID)
        try:
            style = FillStyleComboBox.get_style(pattern)
        except KeyError:
            style = Qt.BrushStyle.SolidPattern
        brush.set_pattern_brush(None if style == Qt.BrushStyle.SolidPattern else QBrush(style))


class EraseStrokePreview(StrokePreview):
    """Previews erasing: the stroke is erased from a layer filled with the preview background, and the result is
    shown over a transparency checkerboard."""

    def _backdrop_color(self) -> QColor:
        """Returns the fill the eraser removes: the background the other previews draw on."""
        return QColor(self.palette().color(QPalette.ColorRole.Base))

    def _inputs(self) -> Hashable:
        return super()._inputs(), self._backdrop_color().name(QColor.NameFormat.HexArgb)

    def _new_layer(self, size: QSize) -> ImageLayer:
        backdrop = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
        backdrop.fill(self._backdrop_color())
        return ImageLayer(backdrop, 'brush preview')

    def _configure_brush(self, brush: Any) -> None:
        super()._configure_brush(brush)
        brush.eraser = True

    def _finish(self, layer_image: QImage) -> QImage:
        result = QImage(layer_image.size(), QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(result)
        tile_pattern_fill(painter, result.rect(), PREVIEW_CHECKER_TILE_SIZE, Qt.GlobalColor.lightGray,
                          Qt.GlobalColor.darkGray)
        painter.drawImage(0, 0, layer_image)
        painter.end()
        return result


class SmudgeStrokePreview(StrokePreview):
    """Previews smudging: a `SmudgeBrush` drags the stroke across the shared sample backdrop."""

    def _new_layer(self, size: QSize) -> ImageLayer:
        return ImageLayer(backdrop_image(size), 'brush preview')

    def _new_brush(self, layer: ImageLayer) -> SmudgeBrush:
        return SmudgeBrush(layer)
