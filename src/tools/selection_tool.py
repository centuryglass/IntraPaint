"""An image editing tool that moves the selected editing region."""

from typing import Optional, cast

from PyQt5.QtCore import Qt, QRect, QPoint
from PyQt5.QtGui import QMouseEvent, QKeyEvent, QCursor, QIcon
from PyQt5.QtWidgets import QWidget, QApplication, QLabel, QSlider, QDoubleSpinBox, \
    QPushButton, QGridLayout

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.tools.base_tool import BaseTool
from src.ui.config_control_setup import get_selection_control_boxes
from src.ui.image_viewer import ImageViewer

SELECT_LAYER_BUTTON_TOOLTIP = "Select the entire active layer."

SELECT_LAYER_BUTTON_TEXT = "Select entire layer"

RESOURCES_SELECTION_ICON = 'resources/selection.svg'
SELECTION_LABEL = 'Select Image Generation Area'
SELECTION_TOOLTIP = 'Select an image region for AI image generation'

SCALE_SLIDER_LABEL = 'Zoom:'
SCALE_RESET_BUTTON_LABEL = 'Reset View'
SCALE_RESET_BUTTON_TOOLTIP = 'Restore default image zoom and offset'
SCALE_ZOOM_BUTTON_LABEL = 'Zoom to selection'
SCALE_ZOOM_BUTTON_TOOLTIP = 'Zoom in on the area selected for image generation'


class SelectionTool(BaseTool):
    """An image editing tool that moves the selected editing region."""

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer, config: AppConfig) -> None:
        super().__init__()
        self._layer_stack = layer_stack
        self._image_viewer = image_viewer
        self._config = config
        self._icon = QIcon(RESOURCES_SELECTION_ICON)
        self._resizing = False
        self.cursor = QCursor(Qt.CursorShape.CrossCursor)
        self._control_panel = None
        self._control_layout = None

    def get_hotkey(self) -> Qt.Key:
        """Returns the hotkey that should activate this tool."""
        key = self._config.get_keycodes(AppConfig.GENERATION_AREA_SELECTION_TOOL_KEY)
        return key[0]

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return SELECTION_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return SELECTION_TOOLTIP

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
        self._control_layout.addWidget(QLabel(SCALE_SLIDER_LABEL), 0, 0)
        image_scale_slider = QSlider(Qt.Orientation.Horizontal)
        self._control_layout.addWidget(image_scale_slider, 0, 1)
        image_scale_slider.setRange(1, 4000)
        image_scale_slider.setSingleStep(10)
        image_scale_slider.setValue(int(self._image_viewer.scene_scale * 100))
        image_scale_box = QDoubleSpinBox()
        self._control_layout.addWidget(image_scale_box, 0, 2)
        image_scale_box.setRange(0.001, 40)
        image_scale_box.setSingleStep(0.1)
        image_scale_box.setValue(self._image_viewer.scene_scale)

        scale_signals = [
            self._image_viewer.scale_changed,
            image_scale_slider.valueChanged,
            image_scale_box.valueChanged
        ]

        def on_scale_change(new_scale: float | int) -> None:
            """Synchronize slider, spin box, panel scale, and zoom button text:"""
            if isinstance(new_scale, int):
                float_scale = new_scale / 100
                int_scale = new_scale
            else:
                float_scale = new_scale
                int_scale = int(float_scale * 100)
            for scale_signal in scale_signals:
                scale_signal.disconnect(on_scale_change)
            if image_scale_box.value() != float_scale:
                image_scale_box.setValue(float_scale)
            if image_scale_slider.value() != int_scale:
                image_scale_slider.setValue(int_scale)
            if self._image_viewer.scene_scale != float_scale:
                self._image_viewer.scene_scale = float_scale
            for scale_signal in scale_signals:
                scale_signal.connect(on_scale_change)
            if self._image_viewer.is_at_default_view and not self._image_viewer.follow_selection:
                scale_reset_button.setText(SCALE_ZOOM_BUTTON_LABEL)
                scale_reset_button.setToolTip(SCALE_ZOOM_BUTTON_TOOLTIP)
            else:
                scale_reset_button.setText(SCALE_RESET_BUTTON_LABEL)
                scale_reset_button.setToolTip(SCALE_RESET_BUTTON_TOOLTIP)

        for signal in scale_signals:
            signal.connect(on_scale_change)

        # wire x/y coordinate boxes to set selection coordinates:
        coordinate_controls = get_selection_control_boxes(self._config, self._layer_stack, True)
        for control_widget in coordinate_controls:
            row = self._control_layout.rowCount()
            ctrl_label, ctrl_slider, ctrl_box = (cast(QWidget, child) for child in control_widget.children()
                                                 if isinstance(child, QWidget))
            self._control_layout.addWidget(ctrl_label, row, 0)
            self._control_layout.addWidget(ctrl_slider, row, 1)
            self._control_layout.addWidget(ctrl_box, row, 2)

        scale_reset_button = QPushButton()

        def toggle_scale():
            """Toggle between default zoom and zooming in on the editing selection."""
            if self._image_viewer.is_at_default_view and not self._image_viewer.follow_selection:
                self._image_viewer.follow_selection = True
                scale_reset_button.setText(SCALE_RESET_BUTTON_LABEL)
                scale_reset_button.setToolTip(SCALE_RESET_BUTTON_TOOLTIP)
            else:
                self._image_viewer.reset_scale()
                scale_reset_button.setText(SCALE_ZOOM_BUTTON_LABEL)
                scale_reset_button.setToolTip(SCALE_ZOOM_BUTTON_TOOLTIP)

        scale_reset_button.setText(SCALE_ZOOM_BUTTON_LABEL)
        scale_reset_button.setToolTip(SCALE_ZOOM_BUTTON_TOOLTIP)
        scale_reset_button.clicked.connect(toggle_scale)
        self._control_layout.addWidget(scale_reset_button, self._control_layout.rowCount(), 0, 1, 3)

        def select_full_layer():
            """Expand the selection to fit the entire active layer."""
            active_layer = self._layer_stack.active_layer
            if active_layer is None:
                return
            self._layer_stack.selection = active_layer.geometry
        select_layer_button = QPushButton()
        select_layer_button.setText(SELECT_LAYER_BUTTON_TEXT)
        select_layer_button.setToolTip(SELECT_LAYER_BUTTON_TOOLTIP)
        select_layer_button.clicked.connect(select_full_layer)
        self._control_layout.addWidget(select_layer_button, self._control_layout.rowCount(), 0, 1, 3)

        return self._control_panel

    def _move_selection(self, selection_pt: QPoint) -> None:
        """Updates the selection's location in the image."""
        self._layer_stack.selection = QRect(selection_pt, self._layer_stack.selection.size())

    def _resize_selection(self, bottom_right: QPoint) -> None:
        """Updates the selection's size in the image."""
        selection = self._layer_stack.selection
        width = min(self._layer_stack.width - selection.x(), bottom_right.x() - selection.x())
        height = min(self._layer_stack.height - selection.y(), bottom_right.y() - selection.y())
        if width > 0 and height > 0:
            key_modifiers = QApplication.keyboardModifiers()
            if key_modifiers == Qt.ControlModifier:
                width = max(width, height)
                height = max(width, height)
            self._layer_stack.selection = QRect(selection.x(), selection.y(), width, height)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Move the selection on left-click, start resizing on right-click."""
        if event.buttons() == Qt.LeftButton:
            if QApplication.keyboardModifiers() != Qt.KeyboardModifier.NoModifier:
                return False
            self._move_selection(image_coordinates)
        elif event.buttons() == Qt.RightButton:
            self._image_viewer.follow_selection = False
            self._resizing = True
            self._resize_selection(image_coordinates)
        else:
            return False
        return True

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If resizing, dynamically adjust the selection if the new size would be non-empty."""
        if event.buttons() == Qt.LeftButton:
            return self.mouse_click(event, image_coordinates)
        if event.buttons() == Qt.RightButton and self._resizing:
            self._resize_selection(image_coordinates)
            return True
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """If resizing, finish on mouse_release."""
        self._resizing = False
        return False

    def key_event(self, event: Optional[QKeyEvent]) -> bool:
        """Move selection with arrow keys."""
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
        self._layer_stack.selection = self._layer_stack.selection.translated(translation)
        return True

