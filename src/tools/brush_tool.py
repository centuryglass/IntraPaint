"""Implements brush controls using a MyPaint surface."""
from typing import Optional

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QColor, QIcon, QKeySequence
from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QColorDialog, QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.canvas.mypaint_layer_canvas import MyPaintLayerCanvas
from src.image.layer_stack import LayerStack
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.brush_panel import BrushPanel
from src.ui.widget.param_slider import ParamSlider


RESOURCES_BRUSH_ICON = 'resources/icons/brush_icon.svg'
BRUSH_LABEL = 'Brush'
BRUSH_TOOLTIP = 'Paint into the image'
COLOR_BUTTON_LABEL = 'Color'
COLOR_BUTTON_TOOLTIP = 'Select sketch brush color'
BRUSH_CONTROL_HINT = 'LMB:draw - RMB:1px draw - Ctrl:pick color -'


class BrushTool(CanvasTool):
    """Implements brush controls using a MyPaint surface."""

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer) -> None:
        super().__init__(layer_stack, image_viewer, MyPaintLayerCanvas(image_viewer.scene()))
        self._last_click = None
        self._control_layout = None
        self._active = False
        self._drawing = False
        self._cached_size = None
        self._icon = QIcon(RESOURCES_BRUSH_ICON)

        # Load brush and size from config
        config = AppConfig.instance()
        self.brush_path = config.get(AppConfig.MYPAINT_BRUSH)
        self.brush_size = config.get(AppConfig.SKETCH_BRUSH_SIZE)

        def _active_layer_update(layer_id: Optional[int], layer_idx: Optional[int]) -> None:
            self.layer = layer_stack.active_layer
            self._canvas.z_value = -layer_idx

        layer_stack.active_layer_changed.connect(_active_layer_update)
        if layer_stack.active_layer is not None:
            _active_layer_update(layer_stack.active_layer.id, layer_stack.active_layer_index)

        self.update_brush_cursor()

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig.instance().get_keycodes(KeyConfig.BRUSH_TOOL_KEY)

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return BRUSH_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return BRUSH_TOOLTIP

    def get_input_hint(self) -> str:
        """Return text describing different input functionality."""
        return f'{BRUSH_CONTROL_HINT} {super().get_input_hint()}'

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the brush control panel."""
        if self._control_layout is not None:
            return self._control_panel
        # Initialize control panel on first request:
        control_layout = QVBoxLayout(self._control_panel)
        self._control_layout = control_layout

        # Size slider:
        brush_size_slider = ParamSlider(self._control_panel,
                                        AppConfig.instance().get_label(AppConfig.SKETCH_BRUSH_SIZE),
                                        AppConfig.SKETCH_BRUSH_SIZE)
        control_layout.addWidget(brush_size_slider)

        def update_brush_size(size: int) -> None:
            """Updates the active brush size."""
            self._canvas.brush_size = size
            self.update_brush_cursor()

        AppConfig.instance().connect(self, AppConfig.SKETCH_BRUSH_SIZE, update_brush_size)
        control_layout.addWidget(brush_size_slider, stretch=2)
        color_picker_button = QPushButton()
        color_picker_button.setText(COLOR_BUTTON_LABEL)
        color_picker_button.setToolTip(COLOR_BUTTON_TOOLTIP)

        # Color picker:
        def set_brush_color(color: QColor) -> None:
            """Update the brush color within the canvas."""
            if color == self.brush_color:
                return
            self.brush_color = color
            icon = QPixmap(QSize(64, 64))
            icon.fill(color)
            color_picker_button.setIcon(QIcon(icon))
            Cache.instance().set(Cache.LAST_BRUSH_COLOR, color.name(QColor.HexArgb))

        color_dialog = QColorDialog()
        color_dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        color_dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        color_picker_button.clicked.connect(lambda: set_brush_color(color_dialog.getColor()))
        Cache.instance().connect(color_picker_button, Cache.LAST_BRUSH_COLOR,
                                     lambda color_str: set_brush_color(QColor(color_str)))
        set_brush_color(self.brush_color)
        control_layout.addWidget(color_picker_button, stretch=2)

        # Brush selection:
        brush_panel = BrushPanel(self._canvas.brush)
        control_layout.addWidget(brush_panel, stretch=8)
        return self._control_panel

    def adjust_brush_size(self, offset: int) -> None:
        """Change brush size by some offset amount, multiplying offset by 10 if shift is held."""
        if QApplication.keyboardModifiers() == Qt.ShiftModifier:
            offset *= 10
        AppConfig.instance().set(AppConfig.SKETCH_BRUSH_SIZE, max(1, self._canvas.brush_size + offset))
