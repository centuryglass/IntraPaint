"""A horizontal slider whose track shows a color gradient.

The track shows what the color would become at each slider position, so callers recompute the gradient whenever the
other components change. Transparent gradient samples show the track background: a checkerboard when
`checkerboard` is set, for alpha tracks. Otherwise they mark positions with no valid color, drawn as diagonal hatching
with a solid edge line where the valid range ends, and the handle's outline turns dashed while it sits in one.

Dragging emits `value_changed`; releasing the mouse emits `value_committed`. Arrow keys emit both.
"""
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QRectF, QSize, Signal, QPointF
from PySide6.QtGui import QBrush, QImage, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPen, QPalette
from PySide6.QtWidgets import QWidget, QSizePolicy

from src.util.visual.image_utils import tile_pattern_fill

DEFAULT_WIDTH = 160
MIN_WIDTH = 60
HEIGHT = 20
HANDLE_WIDTH = 6.0
CHECKER_TILE_SIZE = 4
# Gradient samples with alpha below this are positions with no valid color.
VALID_ALPHA_THRESHOLD = 0.5
# Arrow keys move the value by this fraction of the range, unless a step is given.
DEFAULT_STEP_FRACTION = 0.01


class GradientSlider(QWidget):
    """A horizontal slider whose track shows a color gradient."""

    value_changed = Signal(float)
    value_committed = Signal(float)

    def __init__(self, minimum: float, maximum: float, parent: Optional[QWidget] = None, checkerboard: bool = False,
                 step: Optional[float] = None) -> None:
        super().__init__(parent)
        assert maximum > minimum
        self._minimum = minimum
        self._maximum = maximum
        self._value = minimum
        self._step = step if step is not None else (maximum - minimum) * DEFAULT_STEP_FRACTION
        self._checkerboard = checkerboard
        self._dragging = False
        self._gradient: Optional[np.ndarray] = None
        self._gradient_image: Optional[QImage] = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        """Wide enough to read the gradient."""
        return QSize(DEFAULT_WIDTH, HEIGHT)

    def minimumSizeHint(self) -> QSize:
        """Narrow enough for a small side panel."""
        return QSize(MIN_WIDTH, HEIGHT)

    @property
    def minimum(self) -> float:
        """The value at the left end of the track."""
        return self._minimum

    @property
    def maximum(self) -> float:
        """The value at the right end of the track."""
        return self._maximum

    @property
    def dragging(self) -> bool:
        """Whether the mouse is dragging the handle."""
        return self._dragging

    def value(self) -> float:
        """Returns the slider value."""
        return self._value

    def set_value(self, value: float) -> None:
        """Sets the value, clamped to the slider range, without emitting signals."""
        value = min(max(value, self._minimum), self._maximum)
        if value != self._value:
            self._value = value
            self.update()

    def set_gradient(self, rgba: np.ndarray) -> None:
        """Sets the track colors from float RGBA samples with shape (n, 4), left to right, channels 0.0-1.0."""
        self._gradient = np.clip(np.asarray(rgba, dtype=np.float64), 0.0, 1.0)
        self._gradient_image = None
        self.update()

    def has_color_at(self, value: float) -> bool:
        """Returns whether the gradient has a valid color at a value, which is true everywhere without a gradient."""
        if self._gradient is None or self._checkerboard:
            return True
        positions = np.linspace(self._minimum, self._maximum, self._gradient.shape[0])
        return bool(np.interp(value, positions, self._gradient[:, 3]) >= VALID_ALPHA_THRESHOLD)

    def _invalid_edge_positions(self) -> list[float]:
        """Returns the x-coordinates where the gradient crosses between valid and invalid colors."""
        if self._gradient is None or self._checkerboard or self._gradient.shape[0] < 2:
            return []
        alpha = self._gradient[:, 3]
        valid = alpha >= VALID_ALPHA_THRESHOLD
        track = self.track_bounds()
        edges = []
        for index in np.flatnonzero(valid[:-1] != valid[1:]):
            left_alpha, right_alpha = alpha[index], alpha[index + 1]
            offset = (VALID_ALPHA_THRESHOLD - left_alpha) / (right_alpha - left_alpha)
            edges.append(track.left() + (index + offset) / (alpha.shape[0] - 1) * track.width())
        return edges

    def _get_gradient_image(self) -> Optional[QImage]:
        """Returns the gradient resampled to the track's pixel size, premultiplied so transparent samples don't blend
        their color into their neighbors."""
        if self._gradient is None:
            return None
        track = self.track_bounds().toAlignedRect()
        width, height = max(track.width(), 1), max(track.height(), 1)
        if self._gradient_image is not None and self._gradient_image.size() == QSize(width, height):
            return self._gradient_image
        premultiplied = self._gradient.copy()
        premultiplied[:, :3] *= premultiplied[:, 3:]
        sample_positions = np.linspace(0.0, premultiplied.shape[0] - 1, width)
        row = np.stack([np.interp(sample_positions, np.arange(premultiplied.shape[0]), premultiplied[:, channel])
                        for channel in range(4)], axis=-1)
        pixels = np.repeat(np.round(row * 255).astype(np.uint8)[np.newaxis, :, :], height, axis=0)
        self._gradient_image = QImage(np.ascontiguousarray(pixels).tobytes(), width, height, width * 4,
                                      QImage.Format.Format_RGBA8888_Premultiplied).copy()
        return self._gradient_image

    def track_bounds(self) -> QRectF:
        """Returns the gradient track's bounds. The handle's center spans its full width."""
        return QRectF(HANDLE_WIDTH / 2, 1.0, max(self.width() - HANDLE_WIDTH, 1.0), max(self.height() - 2.0, 1.0))

    def x_for_value(self, value: float) -> float:
        """Returns the x-coordinate of a value's position on the track."""
        track = self.track_bounds()
        return track.left() + (value - self._minimum) / (self._maximum - self._minimum) * track.width()

    def _value_at(self, x: float) -> float:
        track = self.track_bounds()
        fraction = min(max((x - track.left()) / track.width(), 0.0), 1.0)
        return self._minimum + fraction * (self._maximum - self._minimum)

    def _change_value(self, value: float) -> bool:
        last_value = self._value
        self.set_value(value)
        if self._value != last_value:
            self.value_changed.emit(self._value)
            return True
        return False

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Moves the handle to the pressed point and starts dragging it."""
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._change_value(self._value_at(event.position().x()))

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Drags the handle."""
        assert event is not None
        if self._dragging:
            self._change_value(self._value_at(event.position().x()))

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Ends the drag and commits the value."""
        assert event is not None
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._change_value(self._value_at(event.position().x()))
            self._dragging = False
            self.value_committed.emit(self._value)

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:
        """Left/Down and Right/Up step the value; Home and End jump to the ends."""
        assert event is not None
        targets = {
            Qt.Key.Key_Left: self._value - self._step,
            Qt.Key.Key_Down: self._value - self._step,
            Qt.Key.Key_Right: self._value + self._step,
            Qt.Key.Key_Up: self._value + self._step,
            Qt.Key.Key_Home: self._minimum,
            Qt.Key.Key_End: self._maximum,
        }
        key = Qt.Key(event.key())
        if key not in targets:
            super().keyPressEvent(event)
            return
        if self._change_value(targets[key]):
            self.value_committed.emit(self._value)

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the track background, the gradient, and the handle."""
        painter = QPainter(self)
        track = self.track_bounds()
        if self._checkerboard:
            tile_pattern_fill(painter, track.toAlignedRect(), CHECKER_TILE_SIZE, Qt.GlobalColor.lightGray,
                              Qt.GlobalColor.darkGray)
        else:
            painter.fillRect(track, self.palette().color(QPalette.ColorRole.Mid))
            painter.setBrushOrigin(track.topLeft())
            painter.fillRect(track, QBrush(self.palette().color(QPalette.ColorRole.Dark), Qt.BrushStyle.BDiagPattern))
        gradient_image = self._get_gradient_image()
        if gradient_image is not None:
            painter.drawImage(track.toAlignedRect(), gradient_image)
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.WindowText), 1))
        for edge_x in self._invalid_edge_positions():
            x = int(edge_x)
            painter.drawLine(x, int(track.top()), x, int(track.bottom()))
        painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Dark), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(track)

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = self.x_for_value(self._value)
        handle = QRectF(QPointF(x - HANDLE_WIDTH / 2, 0.5), QPointF(x + HANDLE_WIDTH / 2, self.height() - 0.5))
        painter.setPen(QPen(Qt.GlobalColor.black, 3))
        painter.drawRoundedRect(handle, 2, 2)
        inner_style = Qt.PenStyle.SolidLine if self.has_color_at(self._value) else Qt.PenStyle.DashLine
        painter.setPen(QPen(Qt.GlobalColor.white, 1, inner_style))
        painter.drawRoundedRect(handle, 2, 2)
        if self.hasFocus():
            painter.setPen(QPen(self.palette().color(QPalette.ColorRole.Highlight), 1, Qt.PenStyle.DotLine))
            painter.drawRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        painter.end()
