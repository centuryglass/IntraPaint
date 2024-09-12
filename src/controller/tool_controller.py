"""Manages available tools and handles tool input events."""
import logging
from typing import Optional, cast, Dict, List

from PySide6.QtCore import Qt, QObject, QEvent, QRect, QPoint, Signal
from PySide6.QtGui import QMouseEvent, QTabletEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.tools.draw_tool import DrawTool
from src.tools.eyedropper_tool import EyedropperTool
from src.tools.fill_tool import FillTool
from src.tools.free_selection_tool import FreeSelectionTool
from src.tools.generation_area_tool import GenerationAreaTool
from src.tools.layer_transform_tool import LayerTransformTool
from src.tools.selection_fill_tool import SelectionFillTool
from src.tools.selection_tool import SelectionTool
from src.tools.shape_selection_tool import ShapeSelectionTool
from src.tools.text_tool import TextTool
from src.ui.image_viewer import ImageViewer
from src.ui.modal.modal_utils import show_warning_dialog
from src.util.optional_import import optional_import

BrushTool = optional_import('src.tools.brush_tool', attr_name='BrushTool')

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'controller.tool_controller'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


BRUSH_LOAD_ERROR_TITLE = _tr('Failed to load libmypaint brush library files')
BRUSH_LOAD_ERROR_MESSAGE = _tr('The brush tool will not be available unless this is fixed.')


class ToolController(QObject):
    """Manages available tools and handles tool input events."""

    tool_changed = Signal(QObject)

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer, load_all_tools: bool = True,
                 use_hotkeys: bool = True):
        """Installs itself as an event handler within an image viewer."""
        super().__init__()
        self._use_hotkeys = use_hotkeys
        self._image_viewer = image_viewer
        self._active_tool: Optional[BaseTool] = None
        self._active_delegate: Optional[BaseTool] = None
        self._tool_modifier_delegates: Dict[BaseTool, Dict[Qt.KeyboardModifier, BaseTool]] = {}
        self._mouse_in_bounds = False
        self._all_tools: List[BaseTool] = []
        image_viewer.setMouseTracking(True)
        image_viewer.installEventFilter(self)
        HotkeyFilter.instance().modifiers_changed.connect(self._handle_modifier_delegation)

        if not load_all_tools:
            return

        # Set up tools:
        last_active_tool_name = Cache().get(Cache.LAST_ACTIVE_TOOL)
        self._add_tool(GenerationAreaTool(image_stack, image_viewer))
        self._add_tool(LayerTransformTool(image_stack, image_viewer))
        if BrushTool is not None:
            brush_tool = BrushTool(image_stack, image_viewer)
            self._add_tool(brush_tool)
        else:
            show_warning_dialog(None, BRUSH_LOAD_ERROR_TITLE, BRUSH_LOAD_ERROR_MESSAGE,
                                AppConfig.WARN_ON_LIBMYPAINT_ERROR)
            brush_tool = None
        draw_tool = DrawTool(image_stack, image_viewer)
        self._add_tool(draw_tool)
        fill_tool = FillTool(image_stack)
        self._add_tool(fill_tool)
        eyedropper_tool = EyedropperTool(image_stack)
        self._add_tool(eyedropper_tool)
        text_tool = TextTool(image_stack, image_viewer)
        self._add_tool(text_tool)
        self._add_tool(SelectionTool(image_stack, image_viewer))
        self._add_tool(FreeSelectionTool(image_stack, image_viewer))
        self._add_tool(ShapeSelectionTool(image_stack, image_viewer))
        self._add_tool(SelectionFillTool(image_stack))

        eyedropper_modifier = KeyConfig().get_modifier(KeyConfig.EYEDROPPER_OVERRIDE_MODIFIER)
        if eyedropper_modifier != Qt.KeyboardModifier.NoModifier:
            for tool in (brush_tool, fill_tool, draw_tool):
                if tool is not None:
                    if isinstance(eyedropper_modifier, list):
                        for mod in eyedropper_modifier:
                            self.register_tool_delegate(tool, eyedropper_tool, mod)
                    else:
                        assert isinstance(eyedropper_modifier, Qt.KeyboardModifier)
                        self.register_tool_delegate(tool, eyedropper_tool, eyedropper_modifier)
        last_active_tool = self.find_tool_by_label(last_active_tool_name)
        if last_active_tool is not None:
            self.active_tool = last_active_tool
        else:
            self.active_tool = self.find_tool_by_class(GenerationAreaTool)

    @property
    def tools(self) -> List[BaseTool]:
        """Return a list of available tools."""
        return [*self._all_tools]

    def find_tool_by_class(self, tool_class: type[BaseTool]) -> Optional[BaseTool]:
        """Finds a tool using its tool class."""
        for tool in self._all_tools:
            if isinstance(tool, tool_class):

                return tool
        return None

    def find_tool_by_label(self, tool_label: str) -> Optional[BaseTool]:
        """Finds a tool using its label string"""
        for tool in self._all_tools:
            if tool.label == tool_label:
                return tool
        return None

    def register_hotkeys(self, tool: BaseTool) -> None:
        """Register key(s) that should load a specific tool."""
        if not self._use_hotkeys:
            return
        keys = tool.get_hotkey()

        def set_active():
            """On hotkey press, set the active tool and consume the event if another tool was previously active."""
            if self._active_tool == tool or not self._image_viewer.isVisible():
                return False
            self.active_tool = tool
            self._image_viewer.focusWidget()
            return True
        HotkeyFilter.instance().register_keybinding(set_active, keys, Qt.KeyboardModifier.NoModifier)

    def register_tool_delegate(self, source_tool: BaseTool, delegate_tool: BaseTool,
                               modifiers: Qt.KeyboardModifier) -> None:
        """Registers a delegate relationship between tools. Delegates take over when certain hotkeys are held, and the
           original tool reactivates when tho set of held keys changes.

        Parameters
        ----------
            source_tool: BaseTool
                The active tool that will register the selected modifiers.
            delegate_tool: BaseTool
                The tool that will become active when the modifier is held.
            modifiers: Qt.KeyModifier
                The modifier or set of modifiers that will trigger the delegation.
        """
        if source_tool not in self._tool_modifier_delegates:
            self._tool_modifier_delegates[source_tool] = {}
        self._tool_modifier_delegates[source_tool][modifiers] = delegate_tool

    def _handle_modifier_delegation(self, modifiers: Qt.KeyboardModifier) -> None:
        """Check for changes in held key modifiers, and handle tool delegation."""
        if self._active_tool is None:
            return
        if self._active_delegate is not None and self._tool_modifier_delegates[self._active_tool] != modifiers:
            self._active_delegate.is_active = False
            self._active_delegate = None
            self._active_tool.reactivate_after_delegation()
            self.tool_changed.emit(self._active_tool)
        if modifiers in self._tool_modifier_delegates[self._active_tool]:
            self._active_tool.is_active = False
            self._active_delegate = self._tool_modifier_delegates[self._active_tool][modifiers]
            self._active_delegate.is_active = True
            self.tool_changed.emit(self._active_delegate)

    @property
    def active_tool(self) -> Optional[BaseTool]:
        """Returns the active tool, if any."""
        if self._active_delegate is not None:
            return self._active_delegate
        return self._active_tool

    @active_tool.setter
    def active_tool(self, new_tool: BaseTool) -> None:
        """Sets a new active tool."""
        logger.info(f'active tool set: {new_tool}')
        if new_tool not in self._all_tools:
            self._add_tool(new_tool)
        if self._active_delegate is not None:
            self._active_delegate.is_active = False
            self._active_delegate = None
        elif self._active_tool is not None:
            self._active_tool.is_active = False
        self._active_tool = new_tool
        if new_tool not in self._tool_modifier_delegates:
            self._tool_modifier_delegates[new_tool] = {}
        if len(self._all_tools) > 1:
            Cache().set(Cache.LAST_ACTIVE_TOOL, new_tool.label)
        if new_tool is not None:
            new_tool.is_active = True
        self._mouse_in_bounds = False
        if new_tool is not None:
            self.tool_changed.emit(new_tool)

    def eventFilter(self, source: Optional[QObject], event: Optional[QEvent]):
        """Allow the active tool to intercept and handle events."""
        assert event is not None
        if self._active_tool is None:
            return super().eventFilter(source, event)
        active_tool = self._active_delegate if self._active_delegate is not None else self._active_tool

        def find_image_coordinates(typed_event: QMouseEvent | QTabletEvent) -> QPoint:
            """Find event image coordinates and detect mouse enter/exit."""
            pos = typed_event.position().toPoint()
            self._image_viewer.set_cursor_pos(pos)
            image_size = self._image_viewer.content_size
            assert image_size is not None
            image_coordinates = self._image_viewer.mapToScene(pos).toPoint()
            point_in_image = QRect(QPoint(0, 0), image_size).contains(image_coordinates)
            if point_in_image and not self._mouse_in_bounds:
                self._mouse_in_bounds = True
                active_tool.mouse_enter(typed_event, image_coordinates)
            elif not point_in_image and self._mouse_in_bounds:
                self._mouse_in_bounds = False
                active_tool.mouse_exit(typed_event, image_coordinates)
            return image_coordinates

        # Handle expected event types:
        event_handled = False
        pan_modifier_held = KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER, True)
        match event.type():
            case QEvent.Type.MouseButtonDblClick:
                event = cast(QMouseEvent, event)
                event_handled = active_tool.mouse_double_click(event, find_image_coordinates(event))
            case QEvent.Type.MouseButtonPress:
                event = cast(QMouseEvent, event)
                event_handled = active_tool.mouse_click(event, find_image_coordinates(event))
            case QEvent.Type.MouseMove if not pan_modifier_held:
                event = cast(QMouseEvent, event)
                event_handled = active_tool.mouse_move(event, find_image_coordinates(event))
            case QEvent.Type.MouseButtonRelease:
                event = cast(QMouseEvent, event)
                event_handled = active_tool.mouse_release(event, find_image_coordinates(event))
            case QEvent.Type.TabletMove | QEvent.Type.TabletEnterProximity | QEvent.Type.TabletLeaveProximity | \
                    QEvent.Type.TabletPress | QEvent.Type.TabletRelease:
                event = cast(QTabletEvent, event)
                event_handled = active_tool.tablet_event(event, find_image_coordinates(event))
            case QEvent.Type.Wheel:
                event_handled = active_tool.wheel_event(cast(QWheelEvent, event))
        return True if event_handled else super().eventFilter(source, event)

    def _add_tool(self, new_tool: BaseTool) -> None:
        """Adds a new tool to the list of available tools."""
        self._all_tools.append(new_tool)
        self.register_hotkeys(new_tool)
