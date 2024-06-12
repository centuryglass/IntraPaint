"""Selects image content for image generation or editing."""
from typing import Optional

from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QMouseEvent, QIcon, QPixmap, QPainter, QKeySequence
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QApplication, QLabel

from src.config.application_config import AppConfig
from src.image.canvas.pixmap_layer_canvas import PixmapLayerCanvas
from src.image.layer_stack import LayerStack
from src.tools.canvas_tool import CanvasTool
from src.ui.config_control_setup import connected_spinbox, connected_checkbox
from src.ui.image_viewer import ImageViewer
from src.ui.widget.dual_toggle import DualToggle
from src.ui.widget.param_slider import ParamSlider

SELECTION_TOOL_LABEL = 'Selection'
SELECTION_TOOL_TOOLTIP = 'Select areas for editing or inpainting.'

RESOURCES_PEN_PNG = './resources/pen.png'
RESOURCES_ERASER_PNG = 'resources/eraser.png'
RESOURCES_CLEAR_PNG = './resources/clear.png'
RESOURCES_FILL_PNG = './resources/fill.png'
RESOURCES_MASK_CURSOR = './resources/mask_cursor.svg'
RESOURCES_MASK_BRUSH = './resources/mask.myb'
RESOURCES_MASK_ICON = './resources/mask_tool.svg'
CLEAR_BUTTON_LABEL = 'clear'
FILL_BUTTON_LABEL = 'fill'

TOOL_MODE_DRAW = "Draw"
TOOL_MODE_ERASE = "Erase"


class SelectionTool(CanvasTool):
    """Selects image content for image generation or editing."""

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer) -> None:
        super().__init__(layer_stack, image_viewer, PixmapLayerCanvas(image_viewer.scene()))
        self._last_click = None
        self._control_layout = None
        self._active = False
        self._drawing = False
        self._cached_size = None
        self._icon = QIcon(RESOURCES_MASK_ICON)
        self.set_scaling_icon_cursor(QIcon(RESOURCES_MASK_CURSOR))

        # Setup brush, load size from config
        self.brush_color = Qt.red
        self.brush_size = AppConfig.instance().get(AppConfig.SELECTION_BRUSH_SIZE)
        self.layer = layer_stack.selection_layer
        self.update_brush_cursor()

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return AppConfig.instance().get_keycodes(AppConfig.SELECTION_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return SELECTION_TOOL_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return SELECTION_TOOL_TOOLTIP

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the brush control panel."""
        if self._control_layout is not None:
            return self._control_panel
        config = AppConfig.instance()
        # Initialize control panel on first request:
        control_layout = QVBoxLayout(self._control_panel)
        self._control_layout = control_layout

        # Size slider:
        brush_size_slider = ParamSlider(self._control_panel, config.get_label(AppConfig.SELECTION_BRUSH_SIZE),
                                        AppConfig.SELECTION_BRUSH_SIZE)
        control_layout.addWidget(brush_size_slider)

        def update_brush_size(size: int) -> None:
            """Updates the active brush size."""
            self._canvas.brush_size = size
            self.update_brush_cursor()

        tool_toggle = DualToggle(self._control_panel, [TOOL_MODE_DRAW, TOOL_MODE_ERASE])
        tool_toggle.set_icons(RESOURCES_PEN_PNG, RESOURCES_ERASER_PNG)
        tool_toggle.set_selected(TOOL_MODE_DRAW)

        config.connect(self, AppConfig.SELECTION_BRUSH_SIZE, update_brush_size)
        control_layout.addWidget(brush_size_slider)

        def set_drawing_tool(selected_tool_label: str):
            """Switches the mask tool between draw and erase modes."""
            self._canvas.eraser = selected_tool_label == TOOL_MODE_ERASE

        tool_toggle.value_changed.connect(set_drawing_tool)
        control_layout.addWidget(tool_toggle)
        control_layout.addStretch(2)

        padding_line = QWidget()
        padding_line_layout = QHBoxLayout(padding_line)
        padding_checkbox_label = QLabel(config.get_label(AppConfig.INPAINT_FULL_RES))
        padding_line_layout.addWidget(padding_checkbox_label)
        padding_checkbox = connected_checkbox(padding_line, AppConfig.INPAINT_FULL_RES)
        padding_line_layout.addWidget(padding_checkbox)
        padding_line_layout.addStretch(100)
        padding_label = QLabel(config.get_label(AppConfig.INPAINT_FULL_RES_PADDING))
        padding_line_layout.addWidget(padding_label, stretch=1)
        padding_spinbox = connected_spinbox(padding_line, AppConfig.INPAINT_FULL_RES_PADDING)
        padding_spinbox.setMinimum(0)
        padding_line_layout.addWidget(padding_spinbox, stretch=2)
        full_res_tip = config.get_tooltip(AppConfig.INPAINT_FULL_RES)
        full_res_padding_tip = config.get_tooltip(AppConfig.INPAINT_FULL_RES_PADDING)
        for full_res_widget in (padding_checkbox_label, padding_checkbox):
            full_res_widget.setToolTip(full_res_tip)
        for padding_widget in (padding_label, padding_spinbox):
            padding_widget.setToolTip(full_res_padding_tip)
        control_layout.addWidget(padding_line)
        control_layout.addStretch(10)

        clear_selection_button = QPushButton()
        clear_selection_button.setText(CLEAR_BUTTON_LABEL)
        clear_selection_button.setIcon(QIcon(QPixmap(RESOURCES_CLEAR_PNG)))

        def clear_mask():
            """Switch from eraser back to pen after clearing the mask canvas."""
            if self.layer is not None:
                self.layer.clear()
            tool_toggle.set_selected(TOOL_MODE_DRAW)

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
                painter.fillRect(0, 0, mask_image.width(), mask_image.height(), Qt.red)

        fill_selection_button.clicked.connect(fill_mask)

        clear_fill_line = QWidget()
        clear_fill_line_layout = QHBoxLayout(clear_fill_line)
        clear_fill_line_layout.addWidget(clear_selection_button)
        clear_fill_line_layout.addSpacing(10)
        clear_fill_line_layout.addWidget(fill_selection_button)
        control_layout.addWidget(clear_fill_line)

        return self._control_panel

    def adjust_brush_size(self, offset: int) -> None:
        """Change brush size by some offset amount, multiplying offset by 10 if shift is held."""
        if QApplication.keyboardModifiers() == Qt.ShiftModifier:
            offset *= 10
        AppConfig.instance().set(AppConfig.SELECTION_BRUSH_SIZE, max(1, self._canvas.brush_size + offset))

    def _on_activate(self) -> None:
        """Override base canvas tool to keep mask layer visible."""
        super()._on_activate()
        self._image_viewer.resume_rendering_layer(self.layer)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Hide the mask layer while actively drawing."""
        if event.buttons() == Qt.LeftButton or event.buttons() == Qt.RightButton:
            self._image_viewer.stop_rendering_layer(self.layer)
            self._canvas.z_value = 1
        return super().mouse_click(event, image_coordinates)

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Stop hiding the mask layer when done drawing."""
        self._image_viewer.resume_rendering_layer(self.layer)
        return super().mouse_release(event, image_coordinates)
