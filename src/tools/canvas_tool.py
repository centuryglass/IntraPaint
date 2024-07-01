"""Base template for tools that use a MyPaint surface within an image layer."""
from typing import Optional

from PyQt5.QtCore import Qt, QPoint, QSize, QRect
from PyQt5.QtGui import QCursor, QTabletEvent, QMouseEvent, QColor, QIcon, QWheelEvent
from PyQt5.QtWidgets import QApplication, QWidget

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.hotkey_filter import HotkeyFilter
from src.image.canvas.layer_canvas import LayerCanvas
from src.image.image_layer import ImageLayer
from src.image.image_stack import ImageStack
from src.tools.base_tool import BaseTool
from src.ui.image_viewer import ImageViewer
from src.util.key_code_utils import get_modifiers

RESOURCES_BRUSH_ICON = 'resources/icons/brush_icon.svg'
RESOURCES_CURSOR = './resources/cursors/brush_cursor.svg'
RESOURCES_MIN_CURSOR = './resources/cursors/min_cursor.svg'

MAX_CURSOR_SIZE = 255
MIN_CURSOR_SIZE = 20
MIN_SMALL_CURSOR_SIZE = 15

BRUSH_LABEL = 'Brush'
BRUSH_TOOLTIP = 'Paint into the image'
COLOR_BUTTON_LABEL = 'Color'
COLOR_BUTTON_TOOLTIP = 'Select sketch brush color'


class CanvasTool(BaseTool):
    """Base template for tools that use a LayerCanvas to edit an image layer using drawing commands.

    CanvasTool handles the connection between a layer and a MyPaint canvas, and the process of applying inputs to
    that canvas. Implementations are responsible for providing their own control panel, configuring brush properties,
    and setting or updating the affected layer.
    """

    def __init__(self, image_stack: ImageStack, image_viewer: ImageViewer, canvas: LayerCanvas) -> None:
        super().__init__()
        self._layer: Optional[ImageLayer] = None
        self._drawing = False
        self._cached_size: Optional[int] = None
        self._tablet_pressure: Optional[float] = None
        self._tablet_x_tilt: Optional[float] = None
        self._tablet_y_tilt: Optional[float] = None
        self._tablet_input: Optional[QTabletEvent.PointerType] = None

        self._small_brush_icon = QIcon(RESOURCES_MIN_CURSOR)
        self._small_brush_cursor = QCursor(self._small_brush_icon.pixmap(MIN_SMALL_CURSOR_SIZE, MIN_SMALL_CURSOR_SIZE))
        self._default_scaled_cursor_icon = QIcon(RESOURCES_CURSOR)
        self._scaled_icon_cursor: Optional[QIcon] = self._default_scaled_cursor_icon
        self._scaling_cursor = True
        image_viewer.scale_changed.connect(self.update_brush_cursor)

        # Create MyPaintLayerCanvas
        self._control_panel = QWidget()
        self._image_stack = image_stack
        self._image_viewer = image_viewer
        self._canvas = canvas

        def update_size(new_size: QSize) -> None:
            """Sync canvas size with image size."""
            self._canvas.edit_region = QRect(QPoint(0, 0), new_size)
        self._image_stack.size_changed.connect(update_size)

        for key, sign in ((KeyConfig.BRUSH_SIZE_DECREASE, -1), (KeyConfig.BRUSH_SIZE_INCREASE, 1)):
            def _size_change(mult, step=sign) -> bool:
                if not self.is_active:
                    return False
                self.adjust_brush_size(step * mult)
                return True

            HotkeyFilter.instance().register_speed_modified_keybinding(_size_change, key)

    def set_scaling_icon_cursor(self, icon: Optional[QIcon]) -> None:
        """Sets whether the tool should use a cursor scaled to the brush size and canvas.

        Parameters
        ----------
        icon: QIcon, optional
            Cursor icon to use. If None, dynamic cursor updates will be disabled. If an icon, CanvasTool will
            dynamically scale it to match the brush size, using an alternate instead if it's below MIN_CURSOR_SIZE.
        """
        self._scaling_cursor = icon is not None
        self._scaled_icon_cursor = icon
        self.update_brush_cursor()

    def reset_scaling_pixmap_cursor(self) -> None:
        """Restores the default scaling brush cursor."""
        if self._scaling_cursor and self._scaled_icon_cursor == self._default_scaled_cursor_icon:
            return
        self._scaling_cursor = True
        self._scaled_icon_cursor = self._default_scaled_cursor_icon
        self.update_brush_cursor()

    @property
    def layer(self) -> Optional[ImageLayer]:
        """Returns the active image layer."""
        return self._layer

    @layer.setter
    def layer(self, layer: Optional[ImageLayer]) -> None:
        """Sets or clears the active image layer."""
        if self._layer is not None and self._layer != layer:
            self._image_viewer.resume_rendering_layer(self._layer)
        self._layer = layer
        if not self._active:
            return
        if layer is None:
            self._canvas.connect_to_layer(None)
            self._image_viewer.hide_active_layer = False
        else:
            layer_index = self._image_stack.get_layer_index(layer)
            if layer_index is not None:
                self._canvas.z_value = -layer_index
            self._canvas.connect_to_layer(layer)
            self._image_viewer.stop_rendering_layer(layer)

    @property
    def brush_size(self) -> int:
        """Gets the active brush size."""
        return self._canvas.brush_size

    @brush_size.setter
    def brush_size(self, new_size: int):
        """Updates the active brush size."""
        self._canvas.brush_size = new_size
        self.update_brush_cursor()

    @property
    def brush_path(self) -> Optional[str]:
        """Gets the active brush file path, if any."""
        if hasattr(self._canvas, 'brush_path'):
            return self._canvas.brush_path
        return None

    @brush_path.setter
    def brush_path(self, new_path: str) -> None:
        """Updates the active brush size."""
        if hasattr(self._canvas, 'brush_path'):
            self._canvas.brush_path = new_path
        else:
            raise RuntimeError(f'Tried to set brush path {new_path} when layer canvas has no brush support.')

    def adjust_brush_size(self, new_size: int) -> None:
        """Update the brush size."""
        raise NotImplementedError()

    @property
    def brush_color(self) -> QColor:
        """Gets the active brush color."""
        return self._canvas.brush_color

    @brush_color.setter
    def brush_color(self, new_color: QColor | Qt.GlobalColor) -> None:
        """Updates the active brush color."""
        self._canvas.brush_color = QColor(new_color)

    def _on_activate(self) -> None:
        """Connect the canvas to the active layer."""
        if self._layer is not None:
            self.layer = self._layer  # Re-apply the connection
        self.update_brush_cursor()

    def _on_deactivate(self) -> None:
        """Disconnect from the image when the tool is inactive."""
        if self._drawing:
            self._drawing = False
            if self._cached_size:
                self.brush_size = self._cached_size
                self._cached_size = None
            self._canvas.end_stroke()
            self._tablet_input = None
            self._tablet_pressure = None
            self._tablet_x_tilt = None
            self._tablet_y_tilt = None
        if self._layer is not None:
            self._image_viewer.resume_rendering_layer(self._layer)
        self._canvas.connect_to_layer(None)

    # Event handlers:
    def _stroke_to(self, image_coordinates: QPoint) -> None:
        """Draws coordinates to the canvas, including tablet data if available."""
        if not self._image_stack.has_image:
            return
        if self._tablet_input == QTabletEvent.PointerType.Eraser:
            self._canvas.eraser = True
        self._canvas.stroke_to(image_coordinates.x(), image_coordinates.y(), self._tablet_pressure,
                               self._tablet_x_tilt, self._tablet_y_tilt)
        if self._tablet_input == QTabletEvent.PointerType.Eraser:
            self._canvas.eraser = False

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Starts drawing when the mouse is clicked in the scene."""
        if self._layer is None or event is None or not self._image_stack.has_image:
            return False
        if QApplication.keyboardModifiers() == Qt.ControlModifier:
            return True
        if event.buttons() == Qt.LeftButton or event.buttons() == Qt.RightButton:
            if self._drawing:
                self._canvas.end_stroke()
            self._drawing = True
            if self._cached_size is not None and event.buttons() == Qt.LeftButton:
                self.brush_size = self._cached_size
                self._cached_size = None
            elif event.buttons() == Qt.RightButton:
                if self._cached_size is None:
                    self._cached_size = self._canvas.brush_size
                self.brush_size = 1
            self._canvas.start_stroke()
            self._stroke_to(image_coordinates)
            return True
        return False

    def mouse_move(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse move event, returning whether the tool consumed the event."""
        if self._layer is None or event is None or not self._image_stack.has_image:
            return False
        if QApplication.keyboardModifiers() == Qt.ControlModifier:
            return False
        if event.buttons() == Qt.LeftButton or event.buttons() == Qt.RightButton and self._drawing:
            self._stroke_to(image_coordinates)
            return True
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse release event, returning whether the tool consumed the event."""
        if self._layer is None or event is None or not self._image_stack.has_image:
            return False
        if QApplication.keyboardModifiers() == Qt.ControlModifier:
            return True
        if self._drawing:
            self._drawing = False
            self._stroke_to(image_coordinates)
            if self._cached_size:
                self.brush_size = self._cached_size
                self._cached_size = None
            self._canvas.end_stroke()
            self._tablet_input = None
            self._tablet_pressure = None
            self._tablet_x_tilt = None
            self._tablet_y_tilt = None
            return True
        return False

    def tablet_event(self, event: Optional[QTabletEvent], image_coordinates: QPoint) -> bool:
        """Cache tablet data when received."""
        assert event is not None
        if event.pointerType() is not None:
            self._tablet_input = event.pointerType()
        self._tablet_pressure = event.pressure()
        self._tablet_x_tilt = event.xTilt()
        self._tablet_y_tilt = event.yTilt()
        return True

    def update_brush_cursor(self) -> None:
        """Recalculates the brush cursor size if using a scaling cursor."""
        if not self.is_active or self._scaling_cursor is False or self._scaled_icon_cursor is None:
            return
        brush_cursor_size = int(self.brush_size * self._image_viewer.scene_scale)
        if brush_cursor_size <= MIN_SMALL_CURSOR_SIZE:
            self.cursor = self._small_brush_cursor
        else:
            icon = self._scaled_icon_cursor if brush_cursor_size > MIN_CURSOR_SIZE else self._small_brush_icon
            scaled_cursor = icon.pixmap(brush_cursor_size, brush_cursor_size)
            if brush_cursor_size > MAX_CURSOR_SIZE:
                self.cursor = scaled_cursor
            else:
                self.cursor = QCursor(scaled_cursor)

    @staticmethod
    def _speed_modifier_held() -> bool:
        speed_modifier = KeyConfig.instance().get(KeyConfig.SPEED_MODIFIER)
        if speed_modifier == '':
            return False
        speed_modifier = get_modifiers(speed_modifier)
        return QApplication.keyboardModifiers() & speed_modifier == speed_modifier

    def wheel_event(self, event: Optional[QWheelEvent]) -> bool:
        """Adjust brush size if scrolling horizontal."""
        assert event is not None
        if not hasattr(self, 'adjust_brush_size'):
            return False
        offset = 0
        if event.angleDelta().x() < 0:
            offset -= 1
        elif event.angleDelta().x() > 0:
            offset += 1
        if offset != 0:
            if self._speed_modifier_held():
                offset *= AppConfig.instance().get(AppConfig.SPEED_MODIFIER_MULTIPLIER)
            self.adjust_brush_size(offset)
            return True
        return False
