"""Implements brush controls using a MyPaint surface."""
from typing import Optional, cast

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap, QColor, QIcon, QKeySequence
from PyQt6.QtWidgets import QVBoxLayout, QPushButton, QColorDialog, QWidget, QApplication, QHBoxLayout

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.config.config_entry import RangeKey
from src.config.key_config import KeyConfig
from src.image.canvas.mypaint_layer_canvas import MyPaintLayerCanvas
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.tools.base_tool import BaseTool
from src.tools.canvas_tool import CanvasTool
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.slider_spinbox import IntSliderSpinbox
from src.ui.panel.mypaint_brush_panel import MypaintBrushPanel
from src.util.shared_constants import PROJECT_DIR


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'tools.brush_tool'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


RESOURCES_BRUSH_ICON = f'{PROJECT_DIR}/resources/icons/tools/brush_icon.svg'
BRUSH_LABEL = _tr('Brush')
BRUSH_TOOLTIP = _tr('Paint into the image')
COLOR_BUTTON_LABEL = _tr('Color')
COLOR_BUTTON_TOOLTIP = _tr('Select sketch brush color')
BRUSH_CONTROL_HINT = _tr('LMB:draw - RMB:1px draw - ')
COLOR_PICK_HINT = _tr('{modifier_or_modifiers}:pick color - ')
SELECTION_ONLY_LABEL = _tr('Paint selection only')


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
        return (f'{BRUSH_CONTROL_HINT}{BaseTool.modifier_hint(KeyConfig.EYEDROPPER_TOOL_KEY, COLOR_PICK_HINT)}'
                f'{CanvasTool.canvas_control_hints()}{super().get_input_hint()}')

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
        second_row = QHBoxLayout()
        control_layout.addLayout(second_row, stretch=2)
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
            Cache().set(Cache.LAST_BRUSH_COLOR, color.name(QColor.NameFormat.HexArgb))

        color_dialog = QColorDialog()
        color_dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        color_dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        color_picker_button.clicked.connect(lambda: set_brush_color(color_dialog.getColor(self.brush_color)))
        Cache().connect(color_picker_button, Cache.LAST_BRUSH_COLOR,
                                     lambda color_str: set_brush_color(QColor(color_str)))
        set_brush_color(self.brush_color)
        second_row.addWidget(color_picker_button, stretch=2)

        selection_only_checkbox = Cache().get_control_widget(Cache.PAINT_SELECTION_ONLY)
        selection_only_checkbox.setText(SELECTION_ONLY_LABEL)
        second_row.addWidget(selection_only_checkbox)

        # Brush selection:
        canvas = cast(MyPaintLayerCanvas, self._canvas)
        brush_panel = MypaintBrushPanel(canvas.brush)
        control_layout.addWidget(brush_panel, stretch=8)
        control_layout.addStretch(255)
        return self._control_panel

    def set_brush_size(self, new_size: int) -> None:
        """Update the brush size."""
        new_size = min(new_size, AppConfig().get(AppConfig.SKETCH_BRUSH_SIZE, RangeKey.MAX))
        super().set_brush_size(new_size)
        AppConfig().set(AppConfig.SKETCH_BRUSH_SIZE, max(1, new_size))

    def _active_layer_change_slot(self, active_layer: Layer) -> None:
        if isinstance(active_layer, ImageLayer):
            self.layer = active_layer
        else:
            self.layer = None
