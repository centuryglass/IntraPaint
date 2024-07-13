"""Selects image content for image generation or editing."""
from typing import Optional, cast

from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QMouseEvent, QIcon, QPixmap, QPainter, QKeySequence, QColor
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QApplication, QLabel

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.image.canvas.pixmap_layer_canvas import PixmapLayerCanvas
from src.image.layers.image_stack import ImageStack
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.input_fields.dual_toggle import DualToggle
from src.util.shared_constants import PROJECT_DIR

SELECTION_CONTROL_LAYOUT_SPACING = 4

SELECTION_SIZE_SHORT_LABEL = 'Size:'

SELECTION_TOOL_LABEL = 'Selection'
SELECTION_TOOL_TOOLTIP = 'Select areas for editing or inpainting.'
SELECTION_CONTROL_HINT = 'LMB:select - RMB:1px select -'

RESOURCES_PEN_PNG = f'{PROJECT_DIR}/resources/icons/pen_small.svg'
RESOURCES_ERASER_PNG = f'{PROJECT_DIR}/resources/icons/eraser_small.svg'
RESOURCES_CLEAR_PNG = f'{PROJECT_DIR}/resources/icons/clear.png'
RESOURCES_FILL_PNG = f'{PROJECT_DIR}/resources/icons/fill.png'
RESOURCES_SELECTION_CURSOR = f'{PROJECT_DIR}/resources/cursors/selection_cursor.svg'
RESOURCES_SELECTION_ICON = f'{PROJECT_DIR}/resources/icons/selection_icon.svg'
CLEAR_BUTTON_LABEL = 'clear'
FILL_BUTTON_LABEL = 'fill'

TOOL_MODE_DRAW = "Draw"
TOOL_MODE_ERASE = "Erase"


class SelectionTool(CanvasTool):
    """Selects image content for image generation or editing."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        scene = image_viewer.scene()
        assert scene is not None
        super().__init__(image_stack, image_viewer, PixmapLayerCanvas(scene))
        self._last_click = None
        self._control_layout: Optional[QVBoxLayout] = None
        self._active = False
        self._drawing = False
        self._cached_size: Optional[int] = None
        self._icon = QIcon(RESOURCES_SELECTION_ICON)
        self.set_scaling_icon_cursor(QIcon(RESOURCES_SELECTION_CURSOR))

        # Setup brush, load size from config
        self.brush_color = QColor(Qt.GlobalColor.red)
        self.brush_size = AppConfig().get(AppConfig.SELECTION_BRUSH_SIZE)
        self.layer = image_stack.selection_layer
        self.update_brush_cursor()

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.SELECTION_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return SELECTION_TOOL_LABEL

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{SELECTION_CONTROL_HINT} {super().get_input_hint()}'

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return SELECTION_TOOL_TOOLTIP

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the brush control panel."""
        if self._control_layout is not None:
            return self._control_panel
        config = AppConfig()
        # Initialize control panel on first request:
        control_layout = QVBoxLayout(self._control_panel)
        control_layout.setSpacing(SELECTION_CONTROL_LAYOUT_SPACING)
        control_layout.setContentsMargins(0, 0, 0, 0)
        self._control_layout = control_layout

        # Size slider:
        brush_size_slider = cast(IntSliderSpinbox, config.get_control_widget(AppConfig.SELECTION_BRUSH_SIZE))
        brush_size_slider.setText(SELECTION_SIZE_SHORT_LABEL)

        def update_brush_size(size: int) -> None:
            """Updates the active brush size."""
            self._canvas.brush_size = size
            self.update_brush_cursor()

        tool_toggle = DualToggle(self._control_panel, [TOOL_MODE_DRAW, TOOL_MODE_ERASE])
        tool_toggle.set_icons(RESOURCES_PEN_PNG, RESOURCES_ERASER_PNG)
        tool_toggle.setValue(TOOL_MODE_DRAW)

        config.connect(self, AppConfig.SELECTION_BRUSH_SIZE, update_brush_size)
        control_layout.addWidget(brush_size_slider, stretch=1)
        control_layout.addStretch(2)

        def set_drawing_tool(selected_tool_label: str):
            """Switches the mask tool between draw and erase modes."""
            self._canvas.eraser = selected_tool_label == TOOL_MODE_ERASE

        tool_toggle.valueChanged.connect(set_drawing_tool)
        control_layout.addWidget(tool_toggle, stretch=1)
        control_layout.addStretch(1)

        clear_selection_button = QPushButton()
        clear_selection_button.setText(CLEAR_BUTTON_LABEL)
        clear_selection_button.setIcon(QIcon(QPixmap(RESOURCES_CLEAR_PNG)))

        def clear_mask():
            """Switch from eraser back to pen after clearing the mask canvas."""
            if self.layer is not None:
                self.layer.clear()
            tool_toggle.setValue(TOOL_MODE_DRAW)

        clear_selection_button.clicked.connect(clear_mask)

        fill_selection_button = QPushButton()
        fill_selection_button.setText(FILL_BUTTON_LABEL)
        fill_selection_button.setIcon(QIcon(QPixmap(RESOURCES_FILL_PNG)))

        def fill_mask():
            """Fill the mask layer if it exists."""
            if self.layer is None:
                return
            with self.layer.borrow_image() as mask_image:
                painter = QPainter(mask_image)
                painter.fillRect(0, 0, mask_image.width(), mask_image.height(), Qt.GlobalColor.red)

        fill_selection_button.clicked.connect(fill_mask)

        clear_fill_line_layout = QHBoxLayout()
        clear_fill_line_layout.setContentsMargins(0, 0, 0, 0)
        clear_fill_line_layout.setSpacing(0)
        clear_fill_line_layout.addWidget(clear_selection_button)
        clear_fill_line_layout.addSpacing(10)
        clear_fill_line_layout.addWidget(fill_selection_button)
        control_layout.addLayout(clear_fill_line_layout, stretch=1)

        padding_checkbox = config.get_control_widget(AppConfig.INPAINT_FULL_RES)
        control_layout.addWidget(padding_checkbox)
        padding_line_layout = QHBoxLayout()
        padding_line_layout.setContentsMargins(0, 0, 0, 0)
        padding_line_layout.setSpacing(0)
        padding_line_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        padding_label = QLabel(config.get_label(AppConfig.INPAINT_FULL_RES_PADDING))
        padding_line_layout.addWidget(padding_label)
        padding_spinbox = config.get_control_widget(AppConfig.INPAINT_FULL_RES_PADDING)
        padding_line_layout.addWidget(padding_spinbox)

        def _show_hide_padding(should_show: bool) -> None:
            if should_show:
                padding_label.show()
                padding_spinbox.show()
            else:
                padding_label.hide()
                padding_spinbox.hide()
        padding_checkbox.stateChanged.connect(lambda state: _show_hide_padding(bool(state)))
        full_res_padding_tip = config.get_tooltip(AppConfig.INPAINT_FULL_RES_PADDING)
        for padding_widget in (padding_label, padding_spinbox):
            padding_widget.setToolTip(full_res_padding_tip)
        control_layout.addLayout(padding_line_layout)
        _show_hide_padding(padding_checkbox.isChecked())

        control_layout.addStretch(5)

        return self._control_panel

    def adjust_brush_size(self, offset: int) -> None:
        """Change brush size by some offset amount, multiplying offset by 10 if shift is held."""
        if QApplication.keyboardModifiers() == Qt.KeyboardModifier.ShiftModifier:
            offset *= 10
        AppConfig().set(AppConfig.SELECTION_BRUSH_SIZE, max(1, self._canvas.brush_size + offset))

    def _on_activate(self) -> None:
        """Override base canvas tool to keep mask layer visible."""
        super()._on_activate()
        layer = self.layer
        if layer is not None:
            self._image_viewer.resume_rendering_layer(layer)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Hide the mask layer while actively drawing."""
        assert event is not None
        layer = self.layer
        if layer is not None and (event.buttons() == Qt.MouseButton.LeftButton or event.buttons() == Qt.MouseButton.RightButton):
            self._image_viewer.stop_rendering_layer(layer)
            self._canvas.z_value = 1
        return super().mouse_click(event, image_coordinates)

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Stop hiding the mask layer when done drawing."""
        assert event is not None
        layer = self.layer
        if layer is not None:
            self._image_viewer.resume_rendering_layer(layer)
        return super().mouse_release(event, image_coordinates)
