"""Implements brush controls using a MyPaint surface."""
from typing import Optional, cast

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QColor, QIcon, QKeySequence
from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QColorDialog, QWidget, QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.canvas.mypaint_layer_canvas import MyPaintLayerCanvas
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.panel.brush_panel import BrushPanel

RESOURCES_BRUSH_ICON = 'resources/icons/brush_icon.svg'
BRUSH_LABEL = 'Brush'
BRUSH_TOOLTIP = 'Paint into the image'
COLOR_BUTTON_LABEL = 'Color'
COLOR_BUTTON_TOOLTIP = 'Select sketch brush color'
BRUSH_CONTROL_HINT = 'LMB:draw - RMB:1px draw - Ctrl:pick color -'


class BrushTool(CanvasTool):
    """Implements brush controls using a MyPaint surface."""

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer) -> None:
        scene = image_viewer.scene()
        assert scene is not None
        super().__init__(image_stack, image_viewer, MyPaintLayerCanvas(scene))
        self._last_click = None
        self._control_layout: Optional[QVBoxLayout] = None
        self._active = False
        self._drawing = False
        self._cached_size = None
        self._icon = QIcon(RESOURCES_BRUSH_ICON)

        # Load brush and size from config
        config = AppConfig()
        self.brush_path = config.get(AppConfig.MYPAINT_BRUSH)
        self.brush_size = config.get(AppConfig.SKETCH_BRUSH_SIZE)

        image_stack.active_layer_changed.connect(self._active_layer_change_slot)
        self.layer = image_stack.active_layer

        self.update_brush_cursor()

    def get_hotkey(self) -> QKeySequence:
        """Returns the hotkey(s) that should activate this tool."""
        return KeyConfig().get_keycodes(KeyConfig.BRUSH_TOOL_KEY)

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
        config = AppConfig()
        # Initialize control panel on first request:
        control_layout = QVBoxLayout(self._control_panel)
        self._control_layout = control_layout

        # Size slider:

        brush_size_slider = cast(IntSliderSpinbox, config.get_control_widget(AppConfig.SKETCH_BRUSH_SIZE))
        brush_size_slider.setText(config.get_label(AppConfig.SKETCH_BRUSH_SIZE))
        control_layout.addWidget(brush_size_slider)

        def update_brush_size(size: int) -> None:
            """Updates the active brush size."""
            self._canvas.brush_size = size
            self.update_brush_cursor()

        AppConfig().connect(self, AppConfig.SKETCH_BRUSH_SIZE, update_brush_size)
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
            Cache().set(Cache.LAST_BRUSH_COLOR, color.name(QColor.HexArgb))

        color_dialog = QColorDialog()
        color_dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        color_dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        color_picker_button.clicked.connect(lambda: set_brush_color(color_dialog.getColor(self.brush_color)))
        Cache().connect(color_picker_button, Cache.LAST_BRUSH_COLOR,
                                     lambda color_str: set_brush_color(QColor(color_str)))
        set_brush_color(self.brush_color)
        control_layout.addWidget(color_picker_button, stretch=2)

        # Brush selection:
        canvas = cast(MyPaintLayerCanvas, self._canvas)
        brush_panel = BrushPanel(canvas.brush)
        control_layout.addWidget(brush_panel, stretch=8)
        control_layout.addStretch(255)
        return self._control_panel

    def adjust_brush_size(self, offset: int) -> None:
        """Change brush size by some offset amount, multiplying offset by 10 if shift is held."""
        if QApplication.keyboardModifiers() == Qt.ShiftModifier:
            offset *= 10
        canvas = cast(MyPaintLayerCanvas, self._canvas)
        AppConfig().set(AppConfig.SKETCH_BRUSH_SIZE, max(1, canvas.brush_size + offset))

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        self.layer = active_layer
