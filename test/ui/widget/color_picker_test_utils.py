"""Synthetic mouse input and signal recording shared by the color picker widget tests."""
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget


def send_mouse(widget: QWidget, event_type: QEvent.Type, point: QPointF) -> None:
    """Sends a left-button mouse event to a widget, holding the button for presses and moves."""
    button = Qt.MouseButton.NoButton if event_type == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
    buttons = Qt.MouseButton.NoButton if event_type == QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
    event = QMouseEvent(event_type, point, widget.mapToGlobal(point), button, buttons,
                        Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, event)


def press(widget: QWidget, point: QPointF) -> None:
    """Presses the left button at a point."""
    send_mouse(widget, QEvent.Type.MouseButtonPress, point)


def move(widget: QWidget, point: QPointF) -> None:
    """Moves the mouse to a point with the left button held."""
    send_mouse(widget, QEvent.Type.MouseMove, point)


def release(widget: QWidget, point: QPointF) -> None:
    """Releases the left button at a point."""
    send_mouse(widget, QEvent.Type.MouseButtonRelease, point)


class SignalRecorder:
    """Records the values a signal emits, copying colors so later changes to them don't alter the record."""

    def __init__(self, signal) -> None:
        self.values: list = []
        signal.connect(lambda value: self.values.append(QColor(value) if isinstance(value, QColor) else value))

    @property
    def colors(self) -> list[QColor]:
        """The recorded values, for signals that emit colors."""
        return self.values
