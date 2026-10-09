"""Picks a color from anywhere on screen, ported from QColorDialog along with its Windows workaround."""
import os
from typing import Optional, cast

from PySide6.QtGui import QColor, QWindow, Qt, QMouseEvent, QKeyEvent, QKeySequence, QCursor
from PySide6.QtCore import QPoint, QTimer, QEvent, Signal, SignalInstance
from PySide6.QtWidgets import QApplication, QWidget


def grab_screen_color(pos: QPoint) -> QColor:
    """Picks a color from anywhere on-screen."""
    screen = QApplication.screenAt(pos)
    if screen is None:
        screen = QApplication.primaryScreen()
    screen_rect = screen.geometry()
    pixmap = screen.grabWindow(0, pos.x() - screen_rect.x(), pos.y() - screen_rect.y(), 1, 1)
    return pixmap.toImage().pixelColor(0, 0)


class ScreenColorWidget(QWidget):
    """Parent class for widgets handling screen color selection.

    `color_previewed` follows the cursor while picking, and `screen_color_picked` fires once with the chosen color.
    `color_selected` is for subclasses to report their own color changes; picking never emits it.
    """

    started_color_picking = Signal()
    stopped_color_picking = Signal()
    color_previewed = Signal(QPoint, QColor)
    screen_color_picked = Signal(QColor)
    color_selected = Signal(QColor)

    def __init__(self) -> None:
        super().__init__()
        self._active = False
        self._last_global_pos = QPoint()
        if os.name == 'nt':
            self._transparent_selection_window: Optional[QWindow] = QWindow()
            self._transparent_selection_window.resize(1, 1)
            self._transparent_selection_window.setFlag(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
            self._update_timer: Optional[QTimer] = QTimer()
            assert isinstance(self._update_timer.timeout, SignalInstance)
            self._update_timer.timeout.connect(self._update_color_picking_timeout)
        else:
            self._transparent_selection_window = None
            self._update_timer = None

    def start_screen_color_picking(self) -> None:
        """Begin screen color picking."""
        assert self._active is False
        self._active = True
        self.installEventFilter(self)
        self.grabMouse(Qt.CursorShape.CrossCursor)
        if os.name == 'nt':
            assert isinstance(self._update_timer, QTimer)
            assert isinstance(self._transparent_selection_window, QWindow)
            self._update_timer.start(30)
            self._transparent_selection_window.show()
        self.grabKeyboard()
        self.setMouseTracking(True)
        self.started_color_picking.emit()
        self.color_previewed.emit(QCursor.pos(), grab_screen_color(QCursor.pos()))

    def release_color_picking(self):
        """Exits screen color selection mode."""
        self.removeEventFilter(self)
        self.releaseMouse()
        if os.name == 'nt':
            assert isinstance(self._update_timer, QTimer)
            assert isinstance(self._transparent_selection_window, QWindow)
            self._update_timer.stop()
            self._transparent_selection_window.setVisible(False)
        self.releaseKeyboard()
        self.setMouseTracking(False)
        self._active = False
        self.stopped_color_picking.emit()

    @property
    def color_picking_active(self) -> bool:
        """Returns whether a screen color is currently being selected."""
        return self._active

    def update_color_picking(self, pos: QPoint) -> None:
        """Updates screen color picking with a new screen coordinate and color value."""
        color = grab_screen_color(pos)
        self.color_previewed.emit(pos, color)

    def handle_color_picking_mouse_move(self, event: QMouseEvent) -> bool:
        """Prepare to select a screen color."""
        assert event is not None
        self.update_color_picking(event.globalPos())
        return True

    def handle_color_picking_mouse_button_release(self, event: QMouseEvent) -> bool:
        """Selects the color covered by the cursor when the mouse button is released."""
        assert event is not None
        self.screen_color_picked.emit(grab_screen_color(event.globalPos()))
        self.release_color_picking()
        return True

    def handle_color_picking_key_press(self, event: QKeyEvent) -> bool:
        """Accept or cancel color selection when appropriate keys are clicked."""
        if event.matches(QKeySequence.StandardKey.Cancel):
            self.release_color_picking()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.screen_color_picked.emit(grab_screen_color(QCursor.pos()))
            self.release_color_picking()
        event.accept()
        return True

    def eventFilter(self, watched: QWidget, event: Optional[QEvent]) -> bool:
        """Handle input events when screen color picking."""
        assert event is not None
        assert watched is self
        if event.type() == QEvent.Type.MouseMove:
            return self.handle_color_picking_mouse_move(cast(QMouseEvent, event))
        if event.type() == QEvent.Type.MouseButtonRelease:
            return self.handle_color_picking_mouse_button_release(cast(QMouseEvent, event))
        if event.type() == QEvent.Type.KeyPress:
            return self.handle_color_picking_key_press(cast(QKeyEvent, event))
        return False

    def _update_color_picking_timeout(self):
        global_pos = QCursor.pos()
        if global_pos == self._last_global_pos:
            return
        self._last_global_pos = global_pos
        assert self._transparent_selection_window is not None
        self._transparent_selection_window.setPosition(global_pos)
        self.update_color_picking(global_pos)
