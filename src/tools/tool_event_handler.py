"""Passes ImageViewer input events to an active editing tool."""
from typing import Optional, cast, Dict
from PyQt5.QtCore import Qt, QObject, QEvent, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QKeyEvent, QMouseEvent, QTabletEvent, QWheelEvent
from PyQt5.QtWidgets import QApplication

from src.ui.image_viewer import ImageViewer
from src.tools.base_tool import BaseTool


class ToolEventHandler(QObject):
    """Passes ImageViewer input events to an active editing tool."""

    tool_changed = pyqtSignal(str)

    def __init__(self, image_viewer: ImageViewer):
        """Installs itself as an event handler within an image viewer."""
        super().__init__()
        self._image_viewer = image_viewer
        self._active_tool: Optional[BaseTool] = None
        self._active_delegate: Optional[BaseTool] = None
        self._tool_hotkeys = {}
        self._tool_modifier_delegates: Dict[BaseTool, Dict[Qt.KeyModifiers, BaseTool]] = {}
        self._last_modifier_state = QApplication.keyboardModifiers()
        self._mouse_in_bounds = False
        image_viewer.setMouseTracking(True)
        image_viewer.installEventFilter(self)

    def register_hotkey(self, key: Qt.Key, tool: BaseTool) -> None:
        """Register a keystroke that should load a specific tool."""
        if key in self._tool_hotkeys:
            raise ValueError(f'Key {key} already registered for tool {tool.label}.')
        self._tool_hotkeys[key] = tool

    def register_tool_delegate(self, source_tool: BaseTool, delegate_tool: BaseTool,
                               modifiers: Qt.KeyboardModifiers | Qt.KeyboardModifier) -> None:
        """Registers a delegate relationship between tools. Delegates take over when certain hotkeys are held, and the
           original tool reactivates when tho set of held keys changes.

        Parameters
        ----------
            source_tool: BaseTool
                The active tool that will register the selected modifiers.
            delegate_tool: BaseTool
                The tool that will become active when the modifier is held.
            modifiers: Qt.KeyModifiers
                The modifier or set of modifiers that will trigger the delegation.
        """
        if source_tool not in self._tool_modifier_delegates:
            self._tool_modifier_delegates[source_tool] = {}
        self._tool_modifier_delegates[source_tool][modifiers] = delegate_tool

    def _check_modifiers(self):
        """Check for changes in held key modifiers, and handle tool delegation."""
        modifiers = QApplication.keyboardModifiers()
        if modifiers == self._last_modifier_state:
            return
        self._last_modifier_state = modifiers
        if self._active_delegate and self._tool_modifier_delegates[self._active_tool] != modifiers:
            self._active_delegate.on_deactivate()
            self._active_delegate = None
            self._active_tool.on_activate()
            self.tool_changed.emit(self._active_tool.label)
        if modifiers in self._tool_modifier_delegates[self._active_tool]:
            self._active_tool.on_deactivate()
            self._active_delegate = self._tool_modifier_delegates[self._active_tool][modifiers]
            self._active_delegate.on_activate()
            self.tool_changed.emit(self._active_delegate.label)

    @property
    def active_tool(self) -> BaseTool:
        """Returns the active tool, if any."""
        return self._active_tool

    @active_tool.setter
    def active_tool(self, new_tool: BaseTool) -> None:
        """Sets a new active tool."""
        if self._active_delegate is not None:
            self._active_delegate.on_deactivate()
            self._active_delegate = None
        elif self._active_tool is not None:
            self._active_tool.on_deactivate()
        self._active_tool = new_tool
        if new_tool not in self._tool_modifier_delegates:
            self._tool_modifier_delegates[new_tool] = {}
        if new_tool is not None:
            new_tool.on_activate()
        self._mouse_in_bounds = False
        self.tool_changed.emit(new_tool.label)

    def eventFilter(self, source: QObject, event: QEvent):
        """Allow the active tool to intercept and handle events."""
        if self._active_tool is None:
            return super().eventFilter(source, event)
        self._check_modifiers()
        active_tool = self._active_delegate if self._active_delegate is not None else self._active_tool

        def find_image_coordinates(typed_event: QMouseEvent | QTabletEvent) -> Optional[QPoint]:
            """Find event image coordinates and detect mouse enter/exit."""
            image_coordinates = self._image_viewer.widget_to_scene_coordinates(typed_event.pos()).toPoint()
            point_in_image = QRect(QPoint(0, 0), self._image_viewer.content_size).contains(image_coordinates)
            if point_in_image and not self._mouse_in_bounds:
                self._mouse_in_bounds = True
                active_tool.mouse_enter(typed_event, point_in_image)
            elif not point_in_image and self._mouse_in_bounds:
                self._mouse_in_bounds = False
                active_tool.mouse_exit(typed_event, point_in_image)
            return image_coordinates

        # Handle expected event types:
        event_handled = False
        match event.type():
            case QEvent.Type.MouseButtonPress:
                event = cast(QMouseEvent, event)
                event_handled = active_tool.mouse_click(event, find_image_coordinates(event))
            case QEvent.Type.MouseMove:
                event = cast(QMouseEvent, event)
                event_handled = active_tool.mouse_move(event, find_image_coordinates(event))
            case QEvent.Type.MouseButtonRelease:
                event = cast(QMouseEvent, event)
                event_handled = active_tool.mouse_release(event, find_image_coordinates(event))
            case QEvent.Type.KeyPress:
                event = cast(QKeyEvent, event)
                if event.modifiers() == Qt.KeyboardModifier.NoModifier and event.key() in self._tool_hotkeys:
                    self.active_tool = self._tool_hotkeys[event.key()]
                    event_handled = True
                else:
                    event_handled = self._active_tool.key_event(event)
            case QEvent.Type.KeyRelease:
                event = cast(QKeyEvent, event)
                event_handled = active_tool.key_event(event)
            case QEvent.Type.TabletMove | QEvent.Type.TabletEnterProximity | QEvent.Type.TabletLeaveProximity | \
                 QEvent.Type.TabletPress | QEvent.Type.TabletRelease:
                event = cast(QTabletEvent, event)
                event_handled = active_tool.tablet_event(event, find_image_coordinates(event))
            case QEvent.Type.Wheel:
                event_handled = active_tool.wheel_event(cast(QWheelEvent, event))
        return True if event_handled else super().eventFilter(source, event)