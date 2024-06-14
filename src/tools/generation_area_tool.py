"""An image editing tool that moves the selected editing region."""

from typing import Optional, cast

from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QCursor, QIcon, QKeySequence
from PyQt5.QtWidgets import QWidget, QApplication, QLabel, QSlider, QDoubleSpinBox, \
    QPushButton, QGridLayout

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.tools.base_tool import BaseTool
from src.ui.config_control_setup import get_generation_area_control_boxes
from src.ui.image_viewer import ImageViewer


RESOURCES_GENERATION_AREA_ICON = 'resources/selection.svg'
GENERATION_AREA_LABEL = 'Select Image Generation Area'
GENERATION_AREA_TOOLTIP = 'Select an image region for AI image generation'
SELECT_LAYER_BUTTON_TEXT = "Full image as generation area"
SELECT_LAYER_BUTTON_TOOLTIP = "Send the entire image during image generation.."


class GenerationAreaTool(BaseTool):
    """An image editing tool that moves the selected editing region."""

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer) -> None:
        super().__init__()
        self._layer_stack = layer_stack
        self._image_viewer = image_viewer
        self._icon = QIcon(RESOURCES_GENERATION_AREA_ICON)
        self._resizing = False
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self._control_panel = None
        self._control_layout = None

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return AppConfig.instance().get_keycodes(AppConfig.GENERATION_AREA_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return GENERATION_AREA_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return GENERATION_AREA_TOOLTIP

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns a panel providing controls for customizing tool behavior, or None if no such panel is needed."""
        if self._control_panel is not None:
            return self._control_panel
        self._control_panel = QWidget()
        self._control_layout = QGridLayout(self._control_panel)
        self._control_layout.setSpacing(5)
        self._control_layout.setAlignment(Qt.AlignCenter)
        for i, stretch in enumerate((1, 8, 1)):
            self._control_layout.setColumnStretch(i, stretch)


        # wire x/y coordinate boxes to set image generation area coordinates:
        coordinate_controls = get_generation_area_control_boxes(self._layer_stack, True)
        for control_widget in coordinate_controls:
            row = self._control_layout.rowCount()
            ctrl_label, ctrl_slider, ctrl_box = (cast(QWidget, child) for child in control_widget.children()
                                                 if isinstance(child, QWidget))
            self._control_layout.addWidget(ctrl_label, row, 0)
            self._control_layout.addWidget(ctrl_slider, row, 1)
            self._control_layout.addWidget(ctrl_box, row, 2)



        def select_full_layer():
            """Expand the image generation area to fit the entire active layer."""
            active_layer = self._layer_stack.active_layer
            if active_layer is None:
                return
            self._layer_stack.generation_area = active_layer.geometry
        select_layer_button = QPushButton()
        select_layer_button.setText(SELECT_LAYER_BUTTON_TEXT)
        select_layer_button.setToolTip(SELECT_LAYER_BUTTON_TOOLTIP)
        select_layer_button.clicked.connect(select_full_layer)
        self._control_layout.addWidget(select_layer_button, self._control_layout.rowCount(), 0, 1, 3)

        return self._control_panel

    def _move_generation_area(self, selection_pt: QPoint) -> None:
        """Updates the image generation area's location in the image."""
        self._layer_stack.generation_area = QRect(selection_pt, self._layer_stack.generation_area.size())

    def _resize_generation_area(self, bottom_right: QPoint) -> None:
        """Updates the image generation area's size in the image."""
        generation_area = self._layer_stack.generation_area
        width = min(self._layer_stack.width - generation_area.x(), bottom_right.x() - generation_area.x())
        height = min(self._layer_stack.height - generation_area.y(), bottom_right.y() - generation_area.y())
        if width > 0 and height > 0:
            key_modifiers = QApplication.keyboardModifiers()
            if key_modifiers == Qt.ControlModifier:
                width = max(width, height)
                height = max(width, height)
            self._layer_stack.generation_area = QRect(generation_area.x(), generation_area.y(), width, height)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Move the image generation area on left-click, start resizing on right-click."""
        if event.buttons() == Qt.LeftButton:
            if QApplication.keyboardModifiers() != Qt.KeyboardModifier.NoModifier:
                return False
            self._move_generation_area(image_coordinates)
        elif event.buttons() == Qt.RightButton:
            self._image_viewer.follow_generation_area = False
            self._resizing = True
            self._resize_generation_area(image_coordinates)
        else:
            return False
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If resizing, dynamically adjust the image generation area if the new size would be non-empty."""
        if event.buttons() == Qt.LeftButton:
            return self.mouse_click(event, image_coordinates)
        if event.buttons() == Qt.RightButton and self._resizing:
            self._resize_generation_area(image_coordinates)
            return True
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If resizing, finish on mouse_release."""
        self._resizing = False
        return False

    def key_event(self, event: Optional[QKeyEvent]) -> bool:
        """Move image generation area with arrow keys."""
        translation = QPoint(0, 0)
        multiplier = 10 if QApplication.keyboardModifiers() == Qt.ShiftModifier else 1
        match event.key():
            case Qt.Key.Key_Left:
                translation.setX(-1 * multiplier)
            case Qt.Key.Key_Right:
                translation.setX(1 * multiplier)
            case Qt.Key.Key_Up:
                translation.setY(-1 * multiplier)
            case Qt.Key.Key_Down:
                translation.setY(1 * multiplier)
            case _:
                return False
        self._layer_stack.generation_area = self._layer_stack.generation_area.translated(translation)
        return True

