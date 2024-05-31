"""Implements brush controls using a MyPaint surface."""
from typing import Optional

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QCursor, QPixmap, QKeyEvent, QWheelEvent, QColor, QIcon
from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QColorDialog, QWidget

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.tools.mypaint_tool import MyPaintTool
from src.ui.image_viewer import ImageViewer
from src.ui.panel.brush_panel import BrushPanel
from src.ui.widget.param_slider import ParamSlider

TOOL_MODE_DRAW = 'DRAW'
TOOL_MODE_EYEDROPPER = 'EYEDROPPER'
TOOL_MODE_1PX = '1PX'
TOOL_MODE_LINE = 'LINE'

RESOURCES_BRUSH_ICON = 'resources/brush.svg'
RESOURCES_CURSOR_PNG = './resources/cursor.png'
RESOURCES_MIN_CURSOR_PNG = './resources/minCursor.png'
RESOURCES_EYEDROPPER_PNG = './resources/eyedropper.png'

BRUSH_LABEL = 'Brush'
BRUSH_TOOLTIP = 'Paint into the image'
COLOR_BUTTON_LABEL = 'Color'
COLOR_BUTTON_TOOLTIP = 'Select sketch brush color'


class BrushTool(MyPaintTool):
    """Implements brush controls using a MyPaint surface."""

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer, config: AppConfig) -> None:
        super().__init__(layer_stack, image_viewer)
        self._config = config
        self._last_click = None
        self._control_panel = None
        self._active = False
        self._drawing = False
        self._cached_size = None
        self._icon = QIcon(RESOURCES_BRUSH_ICON)

        if layer_stack.count > 0:
            active_layer = layer_stack.get_layer(layer_stack.active_layer)
            self.layer = active_layer

        # Load brush and size from config
        self.brush_path = config.get(AppConfig.MYPAINT_BRUSH)
        self.brush_size = config.get(AppConfig.SKETCH_BRUSH_SIZE)

        def active_layer_update(layer_idx: int) -> None:
            """Synchronize with active layer changes."""
            layer = layer_stack.get_layer(layer_idx)
            self.layer = layer

        layer_stack.active_layer_changed.connect(active_layer_update)

        self._eyedropper_cursor = QCursor(QPixmap(RESOURCES_EYEDROPPER_PNG))
        self._line_brush_cursor = QCursor(Qt.CursorShape.ArrowCursor)

    def get_hotkey(self) -> Qt.Key:
        """Returns the hotkey that should activate this tool."""
        return Qt.Key.Key_B

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return BRUSH_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return BRUSH_TOOLTIP

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the brush control panel."""
        if self._control_panel is not None:
            return self._control_panel
        # Initialize control panel on first request:
        self._control_panel = QWidget()
        control_layout = QVBoxLayout(self._control_panel)

        # Size slider:
        brush_size_slider = ParamSlider(self._control_panel, self._config.get_label(AppConfig.SKETCH_BRUSH_SIZE),
                                        self._config, AppConfig.SKETCH_BRUSH_SIZE)
        control_layout.addWidget(brush_size_slider)

        def update_brush_size(size: int) -> None:
            """Updates the active brush size."""
            self._canvas.brush_size = size
            self.update_brush_cursor()

        self._config.connect(self, AppConfig.SKETCH_BRUSH_SIZE, update_brush_size)
        control_layout.addWidget(brush_size_slider, stretch=2)
        color_picker_button = QPushButton()
        color_picker_button.setText(COLOR_BUTTON_LABEL)
        color_picker_button.setToolTip(COLOR_BUTTON_TOOLTIP)

        # Color picker:
        def set_brush_color(color: QColor) -> None:
            """Update the brush color within the canvas."""
            if color == self._canvas.brush.color:
                return
            self._canvas.brush.color = color
            icon = QPixmap(QSize(64, 64))
            icon.fill(color)
            color_picker_button.setIcon(QIcon(icon))
            self._config.set(AppConfig.LAST_BRUSH_COLOR, color.name(QColor.HexArgb))

        color_dialog = QColorDialog()
        color_dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        color_picker_button.clicked.connect(lambda: set_brush_color(color_dialog.getColor()))
        self._config.connect(color_picker_button, AppConfig.LAST_BRUSH_COLOR,
                             lambda color_str: set_brush_color(QColor(color_str)))
        set_brush_color(self._canvas.brush.color)
        control_layout.addWidget(color_picker_button, stretch=2)

        # Brush selection:
        brush_panel = BrushPanel(self._config, self._canvas.brush)
        control_layout.addWidget(brush_panel, stretch=8)
        return self._control_panel

    def key_event(self, event: Optional[QKeyEvent]) -> bool:
        """Adjust brush size with square bracket keys."""
        if event.type() != QKeyEvent.Type.KeyPress:
            return False
        match event.key():
            case Qt.Key.Key_BracketLeft:
                self._config.set(AppConfig.SKETCH_BRUSH_SIZE, max(1, self._canvas.brush_size - 1))
            case Qt.Key.Key_BracketRight:
                self._config.set(AppConfig.SKETCH_BRUSH_SIZE, max(1, self._canvas.brush_size + 1))
            case _:
                return False
        return True

    def wheel_event(self, event: Optional[QWheelEvent]) -> bool:
        """Adjust brush size if scrolling with shift held down."""
        if event.angleDelta().x() > 0:
            self._config.set(AppConfig.SKETCH_BRUSH_SIZE, max(1, self._canvas.brush_size - 1))
        elif event.angleDelta().x() < 0:
            self._config.set(AppConfig.SKETCH_BRUSH_SIZE, max(1, self._canvas.brush_size + 1))
        else:
            return False
        return True