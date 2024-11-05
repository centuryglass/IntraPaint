"""Widget used to adjust a tablet pressure curve."""
import logging
from typing import Optional

from PySide6.QtCore import Signal, QRect, QSize, QPoint
from PySide6.QtGui import QPaintEvent, QPainter, QMouseEvent, Qt, QAction
from PySide6.QtWidgets import QFrame, QApplication

from src.util.math_utils import clamp
from src.util.signals_blocked import signals_blocked

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.pressure_curve_input'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


LABEL_TEXT_PRESSURE_CONVERSION = _tr('Input: {input_fraction}, Output: {output_fraction}')
MENU_OPTION_RESET = _tr('Reset')


CURVE_POINT_COUNT = 11
POINT_SIZE = 15
MARGIN = 4

MIN_SIZE = QSize(200, 200)
PREFERRED_SIZE = QSize(400, 400)

logger = logging.getLogger(__name__)


class PressureCurveInput(QFrame):
    """Widget used to adjust a tablet pressure curve."""

    valueChanged = Signal(list)

    def __init__(self, curve_values: Optional[list[float]] = None) -> None:
        super().__init__()
        self._pressure_curve: list[float] = []
        self._drag_point: Optional[int] = None
        if curve_values is not None:
            try:
                self.setValue(curve_values)
            except ValueError as err:
                logger.error(f'Invalid initial curve values: {err}')
                curve_values = None
        if curve_values is None:
            self._set_defaults()
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self._reset_action = QAction(MENU_OPTION_RESET)
        self._reset_action.triggered.connect(self._set_defaults)
        self.addAction(self._reset_action)

    def value(self) -> list[float]:
        """Access the pressure curve values."""
        return list(self._pressure_curve)

    def setValue(self, curve_values: list[float]) -> None:
        """Updates pressure curve values."""
        if len(curve_values) != CURVE_POINT_COUNT:
            raise ValueError(f'Expected {CURVE_POINT_COUNT} pressure curve points, got {len(curve_values)}')
        curve_values[0] = 0.0
        curve_values[-1] = 1.0
        if curve_values == self._pressure_curve:
            return
        last_curve = self._pressure_curve
        last_value = 0.0
        self._pressure_curve = []
        for value in curve_values:
            if value < last_value or value > 1.0:
                self._pressure_curve = last_curve
                raise ValueError(f'invalid curve value {value}, last was {last_value}')
            self._pressure_curve.append(value)
            last_value = value
        self.valueChanged.emit(self.value())
        self.update()

    def sizeHint(self) -> QSize:
        """Use a fixed preferred size."""
        return QSize(PREFERRED_SIZE)

    def minimumSizeHint(self) -> QSize:
        """Use a fixed minimum size."""
        return QSize(MIN_SIZE)

    def _set_defaults(self) -> None:
        curve = []
        for i in range(CURVE_POINT_COUNT):
            curve.append(1.0 / (CURVE_POINT_COUNT - 1) * i)
        self.setValue(curve)

    def _paint_bounds(self) -> QRect:
        return self.rect().adjusted(MARGIN, MARGIN, -MARGIN, -MARGIN)

    def _point_rect(self, idx: int) -> QRect:
        if idx < 0 or idx >= CURVE_POINT_COUNT:
            raise ValueError(f'invalid curve point {idx}')
        point_half = POINT_SIZE // 2
        bounds = self._paint_bounds().adjusted(point_half, point_half, -point_half, -point_half)
        x = bounds.x() + round(bounds.width() * idx / (CURVE_POINT_COUNT - 1))
        y = bounds.y() + round(bounds.height() * (1.0 - self._pressure_curve[idx]))
        return QRect(x - point_half, y - point_half, POINT_SIZE, POINT_SIZE)

    def _point_value(self, pos: QPoint) -> float:
        point_half = POINT_SIZE // 2
        bounds = self._paint_bounds().adjusted(point_half, point_half, -point_half, -point_half)
        pressure_value = 1.0 - ((pos.y() - bounds.y()) / bounds.height())
        return float(clamp(pressure_value, 0.0, 1.0))

    def _set_index_value(self, idx: int, value: float) -> None:
        if idx < 0 or idx >= CURVE_POINT_COUNT:
            raise ValueError(f'invalid curve point {idx}')
        if value < 0.0 or value > 1.0:
            raise ValueError(f'invalid value {value}')
        if self._pressure_curve[idx] == value:
            return
        curve = self.value()
        curve[idx] = value
        last = value
        for i in range(idx + 1, CURVE_POINT_COUNT):
            if curve[i] < last:
                curve[i] = last
            last = curve[i]
        last = value
        for i in reversed(range(idx)):
            if curve[i] > last:
                curve[i] = last
            last = curve[i]
        self.setValue(curve)
        self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:
        """Draw the pressure grid."""
        painter = QPainter(self)
        palette = self.palette()
        assert palette is not None
        fill_color = palette.color(self.backgroundRole())
        line_color = palette.color(self.foregroundRole())
        point_color = fill_color.lighter() if fill_color.lightness() < 128 else fill_color.darker()
        painter.setPen(line_color)
        bounds = self._paint_bounds()
        painter.fillRect(bounds, fill_color)
        painter.drawRect(bounds.adjusted(0, 0, -1, -1))
        last_rect: Optional[QRect] = None
        for i in range(CURVE_POINT_COUNT):
            point_rect = self._point_rect(i)
            if last_rect is not None:
                painter.drawLine(last_rect.center(), point_rect.center())
            painter.fillRect(point_rect, point_color)
            painter.drawRect(point_rect.adjusted(0, 0, -1, -1))
            last_rect = point_rect
        if self._drag_point is not None:
            idx = self._drag_point
            value = self._pressure_curve[idx]
            x_str = str(round(1.0 / (CURVE_POINT_COUNT - 1) * idx, 2))
            y_str = str(round(value, 2))
            drag_text = LABEL_TEXT_PRESSURE_CONVERSION.format(input_fraction=x_str, output_fraction=y_str)
            text_bounds = bounds.adjusted(MARGIN, MARGIN, 0, 0)
            painter.drawText(text_bounds, Qt.AlignmentFlag.AlignTop, drag_text)
        painter.end()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Check if points should be dragged."""
        if event is None or event.buttons() != Qt.MouseButton.LeftButton:
            return
        for i in range(CURVE_POINT_COUNT):
            point_rect = self._point_rect(i)
            if point_rect.contains(event.pos()):
                self._drag_point = i
                return

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Update values if dragging a curve point."""
        if self._drag_point is None or event is None:
            return
        drag_value = self._point_value(event.pos())
        with signals_blocked(self):
            self._set_index_value(self._drag_point, drag_value)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Stop dragging and send change signal on release."""
        if self._drag_point is not None:
            self._drag_point = None
            self.valueChanged.emit(self.value())
            self.update()
