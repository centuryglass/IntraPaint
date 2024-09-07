"""
Basic interface for tools that interact with image data.

Supports the following:
- Consumes key and mouse events with scene coordinates, use them to make arbitrary changes.
- Provide a tool panel widget with UI controls.
- Override the cursor when over the image viewer.
"""
from typing import Optional

from PySide6.QtCore import QObject, Signal, QPoint, QEvent, Qt
from PySide6.QtGui import QCursor, QPixmap, QMouseEvent, QTabletEvent, QWheelEvent, QIcon, QKeySequence
from PySide6.QtWidgets import QWidget, QApplication

from src.config.key_config import KeyConfig


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.base_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


PAN_HINT = _tr('{modifier_or_modifiers}+LMB/MMB and drag:pan view - ')
ZOOM_HINT = _tr('Scroll wheel:zoom')
FIXED_ASPECT_HINT = _tr('{modifier_or_modifiers}: Fixed aspect ratio')


# noinspection PyMethodMayBeStatic
class BaseTool(QObject):
    """
    Basic interface for tools that interact with image data.

    To extend:
    ----------
    1. Implement get_icon, get_label_text, and get_tooltip_text to provide descriptive information.

    2. If needed, implement on_activate to handle setup tasks and on_deactivate to handle cleanup tasks.

    3.  Implement all needed event handling functions, probably by acting on the ImageStack. All event handling
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
       - Set tool.is_active = True
       - Display the widget returned by get_control_panel (if not None) somewhere in the UI.
       - Set the image widget cursor to tool cursor, if not None.
       - Connect to the cursor_change signal to handle cursor updates.

    4. When applying cursors, if the cursor is a Pixmap instead of a  QCursor, instead use a minimal cursor and
       manually draw the pixmap over the mouse cursor. If the cursor is None, use the default cursor.

    5. When the image display component receives QEvents, calculate the associated image coordinates if relevant and
       call the associated BaseTool event function. To support, MouseEnter and MouseExit, use the mouse events to flag
       whether the cursor is over the image and keep track of when that flag changes. If the event function returns
       True, the image widget shouldn't do anything else with that event.

    6. When a tool exits active use, set tool.is_active=False and disconnect from the cursor_changed signal.
    """

    cursor_change = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._cursor: Optional[QCursor | QPixmap] = None
        self._active = False

    @staticmethod
    def modifier_hint(modifier_key: str, modifier_hint_str: str) -> str:
        """Returns a hint string with a config-defined modifier inserted, or the empty string if the modifier is not
           defined."""
        assert '{modifier_or_modifiers}' in modifier_hint_str
        if KeyConfig().get_modifier(modifier_key) == Qt.KeyboardModifier.NoModifier:
            return ''
        return modifier_hint_str.format(modifier_or_modifiers=KeyConfig().get(modifier_key))

    @staticmethod
    def fixed_aspect_hint() -> str:
        """Returns the hint for the fixed aspect ratio key, if set"""
        return BaseTool.modifier_hint(KeyConfig.FIXED_ASPECT_MODIFIER, FIXED_ASPECT_HINT)

    @property
    def cursor(self) -> Optional[QCursor | QPixmap]:
        """Returns the active tool cursor or tool pixmap."""
        return self._cursor

    @cursor.setter
    def cursor(self, new_cursor: Optional[QCursor | QPixmap]) -> None:
        """Sets the active tool cursor or tool pixmap."""
        self._cursor = new_cursor
        self.cursor_change.emit()

    @property
    def is_active(self) -> bool:
        """Returns whether this tool is currently marked as active."""
        return self._active

    @is_active.setter
    def is_active(self, active: bool) -> None:
        if active == self._active:
            return
        self._active = active
        if active:
            self._on_activate()
        else:
            self._on_deactivate()

    def reactivate_after_delegation(self) -> None:
        """Sets the tool as active again after temporarily disabling it to delegate inputs to another tool."""
        assert not self._active
        self._active = True
        self._on_activate(True)

    def get_hotkey(self) -> QKeySequence:
        """Returns a hotkey or list of keys that should activate this tool."""
        raise NotImplementedError('BaseTool.get_hotkey needs to be implemented to return a QKeySequence.')

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        raise NotImplementedError('BaseTool.get_icon needs to be implemented to return a QIcon.')

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        raise NotImplementedError('BaseTool.get_label_text needs to be implemented to return a string.')

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        raise NotImplementedError('BaseTool.get_tooltip_text needs to be implemented to return a string.')

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{BaseTool.modifier_hint(KeyConfig.PAN_VIEW_MODIFIER, PAN_HINT)}{ZOOM_HINT}'

    @property
    def label(self) -> str:
        """Also expose the tool label as the 'label' property."""
        return self.get_label_text()

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        return None

    def _on_activate(self, restoring_after_delegation=False) -> None:
        """Called when the tool becomes active, implement to handle any setup that needs to be done."""

    def _on_deactivate(self) -> None:
        """Called when the tool stops being active, implement to handle any cleanup that needs to be done."""

    # Event handlers:

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse click event, returning whether the tool consumed the event."""
        return False

    def mouse_double_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse double click event, returning whether the tool consumed the event."""
        return False

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse move event, returning whether the tool consumed the event."""
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse release event, returning whether the tool consumed the event."""
        return False

    # noinspection PyUnusedLocal
    def mouse_enter(self, event: Optional[QEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse enter event, returning whether the tool consumed the event.

        Mouse enter events are non-standard, the widget managing this tool needs to identify these itself by tracking
        mouse event coordinates and detecting when the cursor moves inside the image bounds.
        """
        return False

    # noinspection PyUnusedLocal
    def mouse_exit(self, event: Optional[QEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse exit event, returning whether the tool consumed the event.

        Mouse exit events are non-standard, the widget managing this tool needs to identify these itself by tracking
        mouse event coordinates and detecting when the cursor moves outside the image bounds.
        """
        return False

    def tablet_event(self, event: Optional[QTabletEvent], image_coordinates: QPoint) -> bool:
        """Receives a graphics tablet input event, returning whether the tool consumed the event."""
        return False

    def wheel_event(self, event: Optional[QWheelEvent]) -> bool:
        """Receives a mouse wheel scroll event, returning whether the tool consumed the event."""
        return False
