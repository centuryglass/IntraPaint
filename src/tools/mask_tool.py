"""Marks areas within the image generation selection for inpainting."""
from typing import Optional
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QKeyEvent, QMouseEvent, QWheelEvent, QIcon, QPixmap, QPainter
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QPushButton
from src.image.layer_stack import LayerStack
from src.image.canvas.mypaint.mp_brush import MPBrush
from src.config.application_config import AppConfig
from src.tools.canvas_tool import CanvasTool
from src.image.canvas.pixmap_layer_canvas import PixmapLayerCanvas
from src.ui.image_viewer import ImageViewer
from src.ui.widget.param_slider import ParamSlider
from src.ui.widget.dual_toggle import DualToggle

MASK_LABEL = 'Mask'
MASK_TOOLTIP = 'Mark areas for inpainting'
COLOR_BUTTON_LABEL = 'Color'
COLOR_BUTTON_TOOLTIP = 'Select sketch brush color'

MASK_LAYER_NAME = "Inpainting Mask"

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


class MaskTool(CanvasTool):
    """Implements brush controls using a MyPaint surface."""

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer, config: AppConfig) -> None:
        super().__init__(layer_stack, image_viewer, PixmapLayerCanvas(image_viewer.scene()))
        self._config = config
        self._last_click = None
        self._control_panel = None
        self._active = False
        self._drawing = False
        self._cached_size = None
        self._icon = QIcon(RESOURCES_MASK_ICON)
        self.set_scaling_icon_cursor(QIcon(RESOURCES_MASK_CURSOR))

        # Setub brush, load size from config
        self.brush_color = Qt.red
        self.brush_size = config.get(AppConfig.MASK_BRUSH_SIZE)
        self.layer = layer_stack.mask_layer

    def get_hotkey(self) -> Qt.Key:
        """Returns the hotkey that should activate this tool."""
        return Qt.Key.Key_M

    def get_icon(self) -> QIcon:
        """Returns an icon used to represent this tool."""
        return self._icon

    def get_label_text(self) -> str:
        """Returns label text used to represent this tool."""
        return MASK_LABEL

    def get_tooltip_text(self) -> str:
        """Returns tooltip text used to describe this tool."""
        return MASK_TOOLTIP

    def get_control_panel(self) -> Optional[QWidget]:
        """Returns the brush control panel."""
        if self._control_panel is not None:
            return self._control_panel
        # Initialize control panel on first request:
        self._control_panel = QWidget()
        control_layout = QVBoxLayout(self._control_panel)
        control_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        # Size slider:
        brush_size_slider = ParamSlider(self._control_panel, self._config.get_label(AppConfig.MASK_BRUSH_SIZE),
                                        self._config, AppConfig.MASK_BRUSH_SIZE)
        control_layout.addWidget(brush_size_slider)

        def update_brush_size(size: int) -> None:
            """Updates the active brush size."""
            self._canvas.brush_size = size
            self.update_brush_cursor()

        self._config.connect(self, AppConfig.MASK_BRUSH_SIZE, update_brush_size)
        control_layout.addWidget(brush_size_slider)

        tool_toggle = DualToggle(self._control_panel, [TOOL_MODE_DRAW, TOOL_MODE_ERASE], self._config)
        tool_toggle.set_icons(RESOURCES_PEN_PNG, RESOURCES_ERASER_PNG)
        tool_toggle.set_selected(TOOL_MODE_DRAW)

        def set_drawing_tool(selection: str):
            """Switches the mask tool between draw and erase modes."""
            # TODO: would be better to do this without direct canvas access.
            self._canvas.brush.set_value(MPBrush.ERASER, 1.0 if selection == TOOL_MODE_ERASE else 0.0)

        tool_toggle.value_changed.connect(set_drawing_tool)
        control_layout.addWidget(tool_toggle)

        clear_mask_button = QPushButton()
        clear_mask_button.setText(CLEAR_BUTTON_LABEL)
        clear_mask_button.setIcon(QIcon(QPixmap(RESOURCES_CLEAR_PNG)))

        def clear_mask():
            """Switch from eraser back to pen after clearing the mask canvas."""
            if self.layer is not None:
                self.layer.clear()
            tool_toggle.set_selected(TOOL_MODE_DRAW)

        clear_mask_button.clicked.connect(clear_mask)

        fill_mask_button = QPushButton()
        fill_mask_button.setText(FILL_BUTTON_LABEL)
        fill_mask_button.setIcon(QIcon(QPixmap(RESOURCES_FILL_PNG)))

        def fill_mask():
            """Fill the mask layer if it exists."""
            if self.layer is None:
                return
            with self.layer.borrow_image() as mask_image:
                painter = QPainter(mask_image)
                painter.fillRect(0, 0, mask_image.width(), mask_image.height(), Qt.red)

        fill_mask_button.clicked.connect(fill_mask)

        clear_fill_line = QWidget()
        clear_fill_line_layout = QHBoxLayout(clear_fill_line)
        clear_fill_line_layout.addWidget(clear_mask_button)
        clear_fill_line_layout.addWidget(fill_mask_button)
        control_layout.addWidget(clear_fill_line)
        return self._control_panel

    def key_event(self, event: Optional[QKeyEvent]) -> bool:
        """Adjust brush size with square bracket keys."""
        if event.type() != QKeyEvent.Type.KeyPress:
            return False
        match event.key():
            case Qt.Key.Key_BracketLeft:
                self._config.set(AppConfig.MASK_BRUSH_SIZE, max(1, self._canvas.brush_size - 1))
            case Qt.Key.Key_BracketRight:
                self._config.set(AppConfig.MASK_BRUSH_SIZE, max(1, self._canvas.brush_size + 1))
            case _:
                return False
        return True

    def wheel_event(self, event: Optional[QWheelEvent]) -> bool:
        """Adjust brush size if scrolling with shift held down."""
        if event.angleDelta().x() > 0:
            self._config.set(AppConfig.MASK_BRUSH_SIZE, max(1, self._canvas.brush_size - 1))
        elif event.angleDelta().x() < 0:
            self._config.set(AppConfig.MASK_BRUSH_SIZE, max(1, self._canvas.brush_size + 1))
        else:
            return False
        return True

    def on_activate(self) -> None:
        """Override MyPaint tool to keep mask layer visible."""
        super().on_activate()
        self._image_viewer.resume_rendering_layer(self.layer)

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Hide the mask layer while actively drawing."""
        if event.buttons() == Qt.LeftButton or event.buttons() == Qt.RightButton:
            self._image_viewer.stop_rendering_layer(self.layer)
        return super().mouse_click(event, image_coordinates)

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Stop hiding the mask layer when done drawing."""
        self._image_viewer.resume_rendering_layer(self.layer)
        return super().mouse_release(event, image_coordinates)
