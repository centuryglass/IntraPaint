"""Shows the edited image in its own window."""
from typing import Optional

from PySide6.QtCore import QPoint
from PySide6.QtGui import QIcon, Qt, QCursor, QMouseEvent
from PySide6.QtWidgets import QWidget, QApplication, QHBoxLayout, QPushButton

from src.config.cache import Cache
from src.controller.tool_controller import ToolController
from src.image.layers.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.tools.generation_area_tool import GenerationAreaTool, GEN_AREA_CONTROL_HINT
from src.ui.graphics_items.border import Border
from src.ui.graphics_items.click_and_drag_selection import ClickAndDragSelection
from src.ui.graphics_items.outline import Outline
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.dual_toggle import DualToggle
from src.ui.panel.image_panel import ImagePanel
from src.util.shared_constants import APP_ICON_PATH, PROJECT_DIR, ICON_SIZE

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.window.image_window'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ZOOM_LABEL = _tr('Move view')
IMAGE_GEN_LABEL_SHORT = _tr('Move gen. area')
BUTTON_TEXT_RESET_VIEW = _tr('Reset view')
BORDER_OPACITY = 0.4

RESOURCES_ZOOM_ICON = f'{PROJECT_DIR}/resources/icons/tools/zoom_icon.svg'
MIN_AREA = 4


class ZoomTool(BaseTool):
    """Tool used to control the zoom level of the primary image view from within the image window."""

    def __init__(self, main_view: ImageViewer, controller_view: ImageViewer) -> None:
        super().__init__()
        self._main_view = main_view
        self._control_view = controller_view
        scene = controller_view.scene()
        self._selection_handler = ClickAndDragSelection(scene)
        self._dragging = False
        self._icon = QIcon(RESOURCES_ZOOM_ICON)
        self.cursor = QCursor(Qt.CursorShape.OpenHandCursor)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns the tool's localized label text."""
        return ZOOM_LABEL

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{GEN_AREA_CONTROL_HINT}{BaseTool.fixed_aspect_hint()}{super().get_input_hint()}'

    def _move_view(self, image_coordinates: QPoint) -> None:
        initial_scene_pos = self._main_view.mapToScene(QPoint())
        offset_change = image_coordinates - initial_scene_pos.toPoint()
        initial_offset = self._main_view.offset
        final_offset = initial_offset + offset_change
        self._main_view.offset = final_offset

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Move the view on left-click, start resizing the view on right-click."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._move_view(image_coordinates)
            return True
        if event.buttons() == Qt.MouseButton.RightButton:
            if self._selection_handler.selecting:
                self._selection_handler.end_selection(image_coordinates)
            aspect_ratio = self._main_view.width() / self._main_view.height()
            self._selection_handler.set_aspect_ratio(aspect_ratio)
            self._selection_handler.start_selection(image_coordinates)
            self._dragging = True
            return True
        return False

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Continue moving or resizing the view if mouse buttons are down."""
        assert event is not None
        if event.buttons() == Qt.MouseButton.LeftButton:
            self._move_view(image_coordinates)
            return True
        if event.buttons() == Qt.MouseButton.RightButton:
            if not self._dragging:
                return False
            self._selection_handler.drag_to(image_coordinates)
            return True
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If resizing, finish on mouse_release."""
        if not self._dragging:
            return False
        self._dragging = False
        final_bounds = self._selection_handler.end_selection(image_coordinates).boundingRect().toAlignedRect()
        if MIN_AREA <= final_bounds.width() * final_bounds.height():
            self._main_view.zoom_to_bounds(final_bounds)
        return True


class ImageWindow(ImagePanel):
    """Shows the edited image in its own window."""

    def __init__(self, image_stack: ImageStack, main_image_view: ImageViewer, include_zoom_controls=True,
                 use_keybindings=True) -> None:
        super().__init__(image_stack, include_zoom_controls=include_zoom_controls, use_keybindings=use_keybindings)
        self._main_image_viewer = main_image_view
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self._image_stack = image_stack
        self._tool_controller = ToolController(image_stack, self.image_viewer, False, False)
        self._tool_controller.tool_changed.connect(self._update_tool_slot)
        self._generation_area_tool = GenerationAreaTool(image_stack, self.image_viewer)
        self._zoom_tool = ZoomTool(main_image_view, self.image_viewer)
        self._tool_controller.active_tool = self._generation_area_tool
        self._tool_controller.active_tool = self._zoom_tool

        scene = self.image_viewer.scene()
        assert scene is not None
        main_scene = main_image_view.scene()
        assert main_scene is not None
        self._main_scene = main_scene
        self._main_view_outline = Outline(scene, self.image_viewer)
        self._main_view_outline.animated = False
        self._main_view_outline.dash_pattern = [2, 0]
        self._main_view_outline.outlined_region = main_image_view.view_scene_bounds
        self._main_view_outline.setVisible(True)

        self._nav_control_bar = QWidget()
        self.vertical_layout.addWidget(self._nav_control_bar)
        self._nav_control_bar_layout = QHBoxLayout(self._nav_control_bar)
        self._nav_control_bar_layout.setSpacing(1)
        self._nav_control_bar_layout.setContentsMargins(2, 2, 2, 2)
        self._nav_control_bar_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        if not include_zoom_controls:
            self._reset_zoom_button: Optional[QPushButton] = QPushButton()
            self._reset_zoom_button.setText(BUTTON_TEXT_RESET_VIEW)
            self._reset_zoom_button.clicked.connect(self.image_viewer.reset_scale)
            self._nav_control_bar_layout.addWidget(self._reset_zoom_button)
        else:
            self._reset_zoom_button = None

        self.image_viewer.offset_changed.connect(self._local_offset_change_slot)
        self.image_viewer.scale_changed.connect(self._local_scale_change_slot)
        main_image_view.offset_changed.connect(self._main_offset_change_slot)
        main_image_view.scale_changed.connect(self._main_scale_change_slot)

        self._tool_toggle = DualToggle(None, [IMAGE_GEN_LABEL_SHORT, self._zoom_tool.label])
        self._tool_toggle.setValue(self._zoom_tool.label)
        self._tool_toggle.set_icons(self._generation_area_tool.get_icon().pixmap(ICON_SIZE),
                                    self._zoom_tool.get_icon().pixmap(ICON_SIZE))
        self._tool_toggle.valueChanged.connect(self._set_active_tool)
        self._nav_control_bar_layout.addWidget(self._tool_toggle)
        initial_tool = Cache().get(Cache.LAST_NAV_PANEL_TOOL)
        if initial_tool in self._tool_toggle.options:
            self._tool_toggle.setValue(initial_tool)

    def _set_active_tool(self, tool_name: str) -> None:
        if tool_name == IMAGE_GEN_LABEL_SHORT:
            self._tool_controller.active_tool = self._generation_area_tool
        elif tool_name == self._zoom_tool.label:
            self._tool_controller.active_tool = self._zoom_tool
        Cache().set(Cache.LAST_NAV_PANEL_TOOL, tool_name)

    def _update_tool_slot(self, active_tool: Optional[BaseTool]) -> None:
        if active_tool is None:
            return
        self.image_viewer.set_cursor(active_tool.cursor)

    # noinspection PyUnusedLocal
    def _local_offset_change_slot(self, offset: QPoint) -> None:
        if self._reset_zoom_button is not None:
            self._reset_zoom_button.setVisible(not self.image_viewer.is_at_default_view)

    # noinspection PyUnusedLocal
    def _local_scale_change_slot(self, scale: float) -> None:
        if self._reset_zoom_button is not None:
            self._reset_zoom_button.setVisible(not self.image_viewer.is_at_default_view)

    # noinspection PyUnusedLocal
    def _main_offset_change_slot(self, offset: QPoint) -> None:
        self._main_view_outline.outlined_region = self._main_image_viewer.view_scene_bounds

    # noinspection PyUnusedLocal
    def _main_scale_change_slot(self, scale: float) -> None:
        self._main_view_outline.outlined_region = self._main_image_viewer.view_scene_bounds
