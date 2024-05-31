"""
Basic interface for tools that interact with image data.

Supports the following:
- Consumes key and mouse events with scene coordinates, use them to make arbitrary changes.
- Provide a tool panel widget with UI controls.
- Override the cursor when over the image viewer.
"""
from typing import Optional
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QPoint, QEvent
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QCursor, QPixmap, QMouseEvent, QTabletEvent, QKeyEvent, QWheelEvent, QIcon


class BaseTool(QObject):
    """
    Basic interface for tools that interact with image data.

    To extend:
    ----------
    1. Implement get_icon, get_label_text, and get_tooltip_text to provide descriptive information.

    2. If needed, implement on_activate to handle setup tasks and on_deactivate to handle cleanup tasks.

    3.  Implement all needed event handling functions, probably by acting on the LayerStack. All event handling
       functions receive the associated QEvent and the associated set of image coordinates if relevant. Event handlers
       should return True if the event was consumed, False if any default event handling should still take effect.
       Event handlers may be called without a QEvent to trigger their behavior manually.

    4.  If needed, override get_control_panel to return a QWidget with a UI for adjusting tool properties or reporting
       tool information.

    5.  If the tool should change the cursor, use `tool.cursor = cursor` to change the cursor when the tool is active
       and the pointer is over the image.  Use `tool.cursor = None` to go back to using the default cursor with the
       tool.  Tool cursors can be either a QCursor or a QPixmap, but QPixmap should only be used for extra large
       cursors that might not work well with the windowing system.

    To integrate:
    -------------
    1. Prepare an image display component with mouse tracking, make sure it provides a way to convert widget
       coordinates to image coordinates.

    2. Use get_icon, get_label_text, and get_tooltip text to represent the tool in the UI.

    3. When a tool enters active use, do the following:
       - Call tool.on_activate()
       - Display the widget returned by get_control_panel (if not None) somewhere in the UI.
       - Set the image widget cursor to tool cursor, if not None.
       - Connect to the cursor_change signal to handle cursor updates.

    4. When applying cursors, if the cursor is a Pixmap instead of a  QCursor, instead use a minimal cursor and
       manually draw the pixmap over the mouse cursor. If the cursor is None, use the default cursor.

    5. When the image display component receives QEvents, calculate the associated image coordinates if relevant and
       call the associated BaseTool event function. To support, MouseEnter and MouseExit, use the mouse events to flag
       whether the cursor is over the image and keep track of when that flag changes. If the event function returns
       True, the image widget shouldn't do anything else with that event.

    6. When a tool exits active use, call tool.on_deactivate() and disconnect from the cursor_changed signal.
    """

    cursor_change = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._cursor: Optional[QCursor | QPixmap] = None

    @property
    def cursor(self) -> Optional[QCursor | QPixmap]:
        """Returns the active tool cursor or tool pixmap."""
        return self._cursor

    @cursor.setter
    def cursor(self, new_cursor: Optional[QCursor | QPixmap]) -> None:
        """Sets the active tool cursor or tool pixmap."""
        self._cursor = new_cursor
        self.cursor_change.emit()

    def get_hotkey(self) -> Qt.Key:
        """Returns a hotkey that should activate this tool."""
        raise NotImplementedError('BaseTool.get_hotkey needs to be implemented to return a Qt.Key code.')

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        raise NotImplementedError('BaseTool.get_icon needs to be implemented to return a QIcon.')

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        raise NotImplementedError('BaseTool.get_label_text needs to be implemented to return a string.')

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        raise NotImplementedError('BaseTool.get_tooltip_text needs to be implemented to return a string.')

    @property
    def label(self) -> str:
        """Also expose the tool label as the 'label' property."""
        return self.get_label_text()

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return None

    def on_activate(self) -> None:
        """Called when the tool becomes active, implement to handle any setup that needs to be done."""

    def on_deactivate(self) -> None:
        """Called when the tool stops being active, implement to handle any cleanup that needs to be done."""

    # Event handlers:

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse click event, returning whether the tool consumed the event."""
        return False

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse move event, returning whether the tool consumed the event."""
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse release event, returning whether the tool consumed the event."""
        return False

    def mouse_enter(self, event: Optional[QEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse enter event, returning whether the tool consumed the event.

        Mouse enter events are non-standard, the widget managing this tool needs to identify these itself by tracking
        mouse event coordinates and detecting when the cursor moves inside the image bounds.
        """

    def mouse_exit(self, event: Optional[QEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse exit event, returning whether the tool consumed the event.

        Mouse exit events are non-standard, the widget managing this tool needs to identify these itself by tracking
        mouse event coordinates and detecting when the cursor moves outside the image bounds.
        """
        return False

    def tablet_event(self, event: Optional[QTabletEvent], image_coordinates: QPoint) -> bool:
        """Receives a graphics tablet input event, returning whether the tool consumed the event."""
        return False

    def key_event(self, event: Optional[QKeyEvent]) -> bool:
        """Receives a key press/key release event, returning whether the tool consumed the event."""
        return False

    def wheel_event(self, event: Optional[QWheelEvent]) -> bool:
        """Receives a mouse wheel scroll event, returning whether the tool consumed the event."""
        return False