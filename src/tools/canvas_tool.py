"""Base template for tools that use a MyPaint surface within an image layer."""
from typing import Optional

from PyQt5.QtCore import Qt, QPoint, QSize, QRect
from PyQt5.QtGui import QCursor, QTabletEvent, QMouseEvent, QColor, QIcon, QKeyEvent, QWheelEvent
from PyQt5.QtWidgets import QApplication

from src.image.image_layer import ImageLayer
from src.image.canvas.layer_canvas import LayerCanvas
from src.image.layer_stack import LayerStack
from src.tools.base_tool import BaseTool
from src.ui.image_viewer import ImageViewer

RESOURCES_BRUSH_ICON = 'resources/brush.svg'
RESOURCES_CURSOR = './resources/cursor.svg'
RESOURCES_MIN_CURSOR = './resources/minCursor.svg'

MAX_CURSOR_SIZE = 255
MIN_CURSOR_SIZE = 20

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

    def __init__(self, layer_stack: LayerStack, image_viewer: ImageViewer, canvas: LayerCanvas) -> None:
        super().__init__()
        self._layer = None
        self._active = False
        self._drawing = False
        self._cached_size = None
        self._tablet_pressure = None
        self._tablet_x_tilt = None
        self._tablet_y_tilt = None
        self._tablet_input = None

        small_brush_icon = QIcon(RESOURCES_MIN_CURSOR)
        self._small_brush_cursor = QCursor(small_brush_icon.pixmap(MIN_CURSOR_SIZE, MIN_CURSOR_SIZE))
        self._default_scaled_cursor_icon = QIcon(RESOURCES_CURSOR)
        self._scaled_icon_cursor = self._default_scaled_cursor_icon
        self._scaling_cursor = True
        image_viewer.scale_changed.connect(self.update_brush_cursor)

        # Create MyPaintLayerCanvas
        self._layer_stack = layer_stack
        self._image_viewer = image_viewer
        self._canvas = canvas

        def update_size(new_size: QSize) -> None:
            """Sync canvas size with image size."""
            self._canvas.edit_region = QRect(QPoint(0, 0), new_size)
        self._layer_stack.size_changed.connect(update_size)

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
        if layer is None or self._layer_stack.count == 0:
            self._canvas.connect_to_layer(None)
            self._image_viewer.hide_active_layer = False
        else:
            layer_index = self._layer_stack.get_layer_index(self._layer)
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

    @property
    def brush_color(self) -> QColor:
        """Gets the active brush color."""
        return self._canvas.brush_color

    @brush_color.setter
    def brush_color(self, new_color: QColor | Qt.GlobalColor) -> None:
        """Updates the active brush color."""
        self._canvas.brush_color = new_color

    def on_activate(self) -> None:
        """Connect the canvas to the active layer."""
        self._active = True
        if self._layer is not None:
            self.layer = self._layer  # Re-apply the connection
        self.update_brush_cursor()

    def on_deactivate(self) -> None:
        """Disconnect from the image when the tool is inactive."""
        self._active = False
        self._canvas.connect_to_layer(None)
        if self._layer is not None:
            self._image_viewer.resume_rendering_layer(self._layer)

    # Event handlers:
    def _stroke_to(self, image_coordinates: QPoint) -> None:
        """Draws coordinates to the canvas, including tablet data if available."""
        if self._tablet_input == QTabletEvent.PointerType.Eraser:
            self._canvas.eraser = True
        self._canvas.stroke_to(image_coordinates.x(), image_coordinates.y(), self._tablet_pressure,
                               self._tablet_x_tilt, self._tablet_y_tilt)
        if self._tablet_input == QTabletEvent.PointerType.Eraser:
            self._canvas.eraser = False

    def mouse_click(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Starts drawing when the mouse is clicked in the scene."""
        if self._layer is None:
            return False
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
        if self._layer is None:
            return False
        if event.buttons() == Qt.LeftButton or event.buttons() == Qt.RightButton and self._drawing:
            self._stroke_to(image_coordinates)
            return True
        return False

    def mouse_release(self, event: Optional[QMouseEvent], image_coordinates: QPoint) -> bool:
        """Receives a mouse release event, returning whether the tool consumed the event."""
        if self._layer is None:
            return False
        if self._drawing:
            self._drawing = False
            self._stroke_to(image_coordinates)
            self._canvas.end_stroke()
            self._tablet_input = None
            self._tablet_pressure = None
            self._tablet_x_tilt = None
            self._tablet_y_tilt = None
            if self._cached_size:
                self.brush_size = self._cached_size
                self._cached_size = None
            return True
        return False

    def tablet_event(self, event: Optional[QTabletEvent], image_coordinates: QPoint) -> bool:
        """Cache tablet data when received."""
        if event.pointerType() is not None:
            self._tablet_input = event.pointerType()
        self._tablet_pressure = event.pressure()
        self._tablet_x_tilt = event.xTilt()
        self._tablet_y_tilt = event.yTilt()
        return True

    def update_brush_cursor(self) -> None:
        """Recalculates the brush cursor size if using a scaling cursor."""
        if not self._active or self._scaling_cursor is False or self._scaled_icon_cursor is None:
            return
        brush_cursor_size = int(self.brush_size * self._image_viewer.scene_scale)
        if brush_cursor_size < MIN_CURSOR_SIZE:
            self.cursor = self._small_brush_cursor
        else:
            scaled_cursor = self._scaled_icon_cursor.pixmap(brush_cursor_size, brush_cursor_size)
            if brush_cursor_size > MAX_CURSOR_SIZE:
                self.cursor = scaled_cursor
            else:
                self.cursor = QCursor(scaled_cursor)

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
            case Qt.Key.Key_BracketLeft:
                if hasattr(self, 'adjust_brush_size'):
                    self.adjust_brush_size(-1)
                    return True
                return False
            case Qt.Key.Key_BracketRight:
                if hasattr(self, 'adjust_brush_size'):
                    self.adjust_brush_size(1)
                    return True
                return False
            case _:
                return False
        if self._image_viewer.follow_selection:
            self._layer_stack.selection = self._layer_stack.selection.translated(translation)
        else:
            self._image_viewer.offset = self._image_viewer.offset + translation
        return True

    def wheel_event(self, event: Optional[QWheelEvent]) -> bool:
        """Adjust brush size if scrolling with shift held down."""
        if not hasattr(self, 'adjust_brush_size'):
            return False
        offset = 0
        if event.angleDelta().x() > 0:
                offset -= 1
        elif event.angleDelta().x() < 0:
                offset += 1
        if offset != 0:
            self.adjust_brush_size(offset)
            return True
        return False
