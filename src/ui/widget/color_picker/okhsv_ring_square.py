"""An OKHSV hue ring around an OKHSV saturation/value square.

OKHSV maps the whole sRGB gamut onto a full square for every hue, so every pixel of the square is a real color while hue
steps and lightness stay perceptually even (see `src.util.visual.color_math`). The widget keeps its own hue,
saturation and value, so dragging value to black or saturation to gray doesn't lose the hue.

Dragging emits `color_changed`; releasing the mouse emits `color_committed`, which callers use to record a finished
choice (see `src.controller.color_controller`).
"""
import math
from enum import Enum
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QPointF, QRectF, QSize, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget, QSizePolicy

from src.util.visual import color_math

DEFAULT_SIZE = 200
MIN_SIZE = 120

# Space around the ring, in pixels.
MARGIN = 2.0
# Ring width as a fraction of its outer radius, and its minimum in pixels.
RING_FRACTION = 0.16
MIN_RING_WIDTH = 10.0
# Space between the ring and the square's corners, in pixels.
SQUARE_GAP = 4.0

# Precomputed ring colors per hue step.
RING_HUE_STEPS = 720

SV_MARKER_RADIUS = 5.0

# Saturation below this counts as gray, and value below this as black: their hue (and black's saturation) is kept.
ACHROMATIC_THRESHOLD = 1e-6


class _DragTarget(Enum):
    RING = 0
    SQUARE = 1


class OkhsvRingSquare(QWidget):
    """An OKHSV hue ring around an OKHSV saturation/value square."""

    color_changed = Signal(QColor)
    color_committed = Signal(QColor)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred))
        self._hue = 0.0
        self._saturation = 0.0
        self._value = 0.0
        self._alpha = 255
        self._drag_target: Optional[_DragTarget] = None
        self._square_image: Optional[QImage] = None
        self._square_image_key: Optional[tuple[float, int]] = None
        self._ring_image: Optional[QImage] = None
        self._ring_image_key: Optional[tuple[int, int]] = None

    # Size and geometry:

    def sizeHint(self) -> QSize:
        """Defaults to a medium square."""
        return QSize(DEFAULT_SIZE, DEFAULT_SIZE)

    def minimumSizeHint(self) -> QSize:
        """Small enough for a narrow side panel.

        The ring and square fit the smaller of the widget's width and height, centered. The widget doesn't report
        height-for-width: in a scroll area that would make the color panel as tall as it is wide, so the panel's
        layout choice would never see the space it has.
        """
        return QSize(MIN_SIZE, MIN_SIZE)

    def outer_radius(self) -> float:
        """Returns the ring's outer radius."""
        return max(min(self.width(), self.height()) / 2 - MARGIN, 1.0)

    def inner_radius(self) -> float:
        """Returns the ring's inner radius."""
        outer = self.outer_radius()
        return max(outer - max(outer * RING_FRACTION, MIN_RING_WIDTH), 1.0)

    def center(self) -> QPointF:
        """Returns the center of the ring and square."""
        return QPointF(self.width() / 2, self.height() / 2)

    def square_bounds(self) -> QRectF:
        """Returns the saturation/value square's bounds, inscribed inside the ring."""
        half_side = max(self.inner_radius() - SQUARE_GAP, 1.0) / math.sqrt(2)
        center = self.center()
        return QRectF(center.x() - half_side, center.y() - half_side, half_side * 2, half_side * 2)

    def point_for_hue(self, hue: float) -> QPointF:
        """Returns the point midway across the ring at a hue. Hue 0 is at the right, increasing counterclockwise."""
        radius = (self.outer_radius() + self.inner_radius()) / 2
        angle = math.radians(hue)
        center = self.center()
        return QPointF(center.x() + radius * math.cos(angle), center.y() - radius * math.sin(angle))

    def point_for_saturation_value(self, saturation: float, value: float) -> QPointF:
        """Returns the square's point for a saturation and value: saturation increases rightward, value upward."""
        bounds = self.square_bounds()
        return QPointF(bounds.left() + saturation * bounds.width(), bounds.top() + (1.0 - value) * bounds.height())

    # Color access:

    @property
    def hue(self) -> float:
        """OKHSV hue in degrees, 0.0-360.0."""
        return self._hue

    @property
    def saturation(self) -> float:
        """OKHSV saturation, 0.0-1.0."""
        return self._saturation

    @property
    def value(self) -> float:
        """OKHSV value, 0.0-1.0."""
        return self._value

    def color(self) -> QColor:
        """Returns the selected color, with its alpha."""
        rgb = color_math.okhsv_to_srgb((self._hue, self._saturation, self._value))
        red, green, blue = (int(round(channel * 255)) for channel in rgb)
        return QColor(red, green, blue, self._alpha)

    def set_okhsv(self, hue: float, saturation: float, value: float) -> None:
        """Sets the selected OKHSV components without emitting signals."""
        self._hue = hue % 360.0
        self._saturation = min(max(saturation, 0.0), 1.0)
        self._value = min(max(value, 0.0), 1.0)
        self.update()

    def set_color(self, color: QColor) -> None:
        """Sets the selected color without emitting signals.

        A color that converts to the current selection keeps the current components, and a gray or black keeps the
        current hue, so 8-bit rounding never makes the markers jump.
        """
        self._alpha = color.alpha()
        if color.rgb() == self.color().rgb():
            self.update()
            return
        hue, saturation, value = color_math.srgb_to_okhsv((color.redF(), color.greenF(), color.blueF()))
        if value < ACHROMATIC_THRESHOLD:
            hue, saturation = self._hue, self._saturation
        elif saturation < ACHROMATIC_THRESHOLD:
            hue = self._hue
        self.set_okhsv(float(hue), float(saturation), float(value))

    # Input:

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Starts dragging the hue on the ring or the saturation and value in the square."""
        assert event is not None
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = event.position()
        if self.square_bounds().contains(point):
            self._drag_target = _DragTarget.SQUARE
        else:
            center = self.center()
            distance = math.hypot(point.x() - center.x(), point.y() - center.y())
            if self.inner_radius() - SQUARE_GAP <= distance <= self.outer_radius() + MARGIN:
                self._drag_target = _DragTarget.RING
        if self._drag_target is not None:
            self._drag_to(point)

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Continues a drag started on the ring or the square, even outside it."""
        assert event is not None
        if self._drag_target is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self._drag_to(event.position())

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Ends a drag and commits the color."""
        assert event is not None
        if event.button() != Qt.MouseButton.LeftButton or self._drag_target is None:
            return
        self._drag_to(event.position())
        self._drag_target = None
        self.color_committed.emit(self.color())

    def _drag_to(self, point: QPointF) -> None:
        last_color = self.color()
        if self._drag_target == _DragTarget.RING:
            center = self.center()
            hue = math.degrees(math.atan2(center.y() - point.y(), point.x() - center.x()))
            self.set_okhsv(hue, self._saturation, self._value)
        elif self._drag_target == _DragTarget.SQUARE:
            bounds = self.square_bounds()
            saturation = (point.x() - bounds.left()) / bounds.width()
            value = 1.0 - (point.y() - bounds.top()) / bounds.height()
            self.set_okhsv(self._hue, saturation, value)
        color = self.color()
        if color != last_color:
            self.color_changed.emit(color)

    # Rendering:

    def _get_square_image(self) -> QImage:
        side = max(int(round(self.square_bounds().width())), 1)
        key = (self._hue, side)
        if self._square_image is None or self._square_image_key != key:
            steps = np.linspace(0.0, 1.0, side)
            rgb = color_math.okhsv_plane_to_srgb(self._hue, steps, steps[::-1])
            self._square_image = _rgb_to_qimage(rgb, np.full(rgb.shape[:2], 1.0))
            self._square_image_key = key
        return self._square_image

    def _get_ring_image(self) -> QImage:
        key = (self.width(), self.height())
        if self._ring_image is None or self._ring_image_key != key:
            hue_colors = color_math.okhsv_to_srgb(np.stack((np.linspace(0.0, 360.0, RING_HUE_STEPS, endpoint=False),
                                                            np.ones(RING_HUE_STEPS),
                                                            np.ones(RING_HUE_STEPS)), axis=-1))
            center = self.center()
            y, x = np.mgrid[0:self.height(), 0:self.width()] + 0.5
            dx = x - center.x()
            dy = center.y() - y
            distance = np.hypot(dx, dy)
            hue_index = np.round(np.degrees(np.arctan2(dy, dx)) % 360.0 * RING_HUE_STEPS / 360.0).astype(int)
            rgb = hue_colors[hue_index % RING_HUE_STEPS]
            coverage = np.clip(np.minimum(self.outer_radius() - distance, distance - self.inner_radius()) + 0.5,
                               0.0, 1.0)
            self._ring_image = _rgb_to_qimage(rgb, coverage)
            self._ring_image_key = key
        return self._ring_image

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws the ring, the square, and markers on the selected hue, saturation and value."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(0, 0, self._get_ring_image())
        painter.drawImage(self.square_bounds(), self._get_square_image())

        ring_marker_radius = (self.outer_radius() - self.inner_radius()) * 0.35
        _draw_marker(painter, self.point_for_hue(self._hue), ring_marker_radius)
        _draw_marker(painter, self.point_for_saturation_value(self._saturation, self._value), SV_MARKER_RADIUS)
        painter.end()


def _rgb_to_qimage(rgb: np.ndarray, alpha: np.ndarray) -> QImage:
    """Converts float sRGB with shape (height, width, 3) and float alpha with shape (height, width) to a QImage."""
    height, width = alpha.shape
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[..., :3] = np.round(rgb * 255)
    rgba[..., 3] = np.round(alpha * 255)
    return QImage(rgba.tobytes(), width, height, width * 4, QImage.Format.Format_RGBA8888).copy()


def _draw_marker(painter: QPainter, center: QPointF, radius: float) -> None:
    """Draws a circle that stays visible on any color: black inside a wider white outline."""
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(Qt.GlobalColor.white, 3))
    painter.drawEllipse(center, radius, radius)
    painter.setPen(QPen(Qt.GlobalColor.black, 1))
    painter.drawEllipse(center, radius, radius)
