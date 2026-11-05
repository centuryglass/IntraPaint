"""The two marks a settings row shows while its value differs from the shipped default.

- `ModifiedLabel` is the row's label with a dot in a reserved left margin, drawn only while modified.
- `ResetButton` is a small flat button with a circular-arrow icon, drawn only while modified. It keeps its size while
  hidden, so a row's field doesn't move when the mark appears.
Both draw in palette colors, so every theme gets the right contrast. The dot is a shape, so the mark doesn't depend on
the accent color being distinguishable.
"""
import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QToolButton, QWidget

DOT_DIAMETER = 6
DOT_MARGIN = 4
BUTTON_SIZE = 22
ARROW_INSET = 6
ARROW_START_DEGREES = 90
ARROW_SWEEP_DEGREES = 300
ARROW_HEAD = 4.0
ARROW_HEAD_SPREAD = math.radians(40)


class ModifiedLabel(QLabel):
    """A row label that draws a dot in its left margin while `set_modified(True)`."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self._modified = False
        self.setContentsMargins(DOT_DIAMETER + DOT_MARGIN * 2, 0, 0, 0)

    def is_modified(self) -> bool:
        """Returns whether the dot is shown."""
        return self._modified

    def set_modified(self, modified: bool) -> None:
        """Shows or hides the dot."""
        if modified != self._modified:
            self._modified = modified
            self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the label, then the dot when modified."""
        super().paintEvent(event)
        if not self._modified:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        painter.setBrush(self.palette().color(group, QPalette.ColorRole.Highlight))
        top = (self.height() - DOT_DIAMETER) / 2
        painter.drawEllipse(QRectF(DOT_MARGIN, top, DOT_DIAMETER, DOT_DIAMETER))
        painter.end()


class ResetButton(QToolButton):
    """A flat button with a circular-arrow icon that is invisible, but still takes up room, while not applicable."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedSize(QSize(BUTTON_SIZE, BUTTON_SIZE))
        policy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(policy)

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the button background for hover and press states, then the arrow."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        color = self.palette().color(group, QPalette.ColorRole.ButtonText)
        painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        bounds = QRectF(self.rect()).adjusted(ARROW_INSET, ARROW_INSET, -ARROW_INSET, -ARROW_INSET)
        # An open circle that starts at the top and runs counterclockwise, ending in an arrowhead:
        path = QPainterPath()
        path.arcMoveTo(bounds, ARROW_START_DEGREES)
        path.arcTo(bounds, ARROW_START_DEGREES, ARROW_SWEEP_DEGREES)
        end = path.currentPosition()
        painter.drawPath(path)
        # The arc runs counterclockwise (in Qt's y-down coordinates) and ends at this angle, so the arrowhead's two
        # strokes go back from the end at an angle to the direction of travel:
        end_angle = math.radians(ARROW_START_DEGREES + ARROW_SWEEP_DEGREES)
        tangent = QPointF(-math.sin(end_angle), -math.cos(end_angle))
        head = QPainterPath()
        for turn in (ARROW_HEAD_SPREAD, -ARROW_HEAD_SPREAD):
            cos, sin = math.cos(turn), math.sin(turn)
            back = QPointF(-(tangent.x() * cos - tangent.y() * sin), -(tangent.x() * sin + tangent.y() * cos))
            head.moveTo(end)
            head.lineTo(end + back * ARROW_HEAD)
        painter.drawPath(head)
        painter.end()
