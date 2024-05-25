"""
Provides a Canvas implementation using the libmypaint/brushlib library, used for directly drawing within edited image
sections. Allows painting in full color with drawing tablet support, using .myb brush files.

To function correctly, this Canvas requires the pre-packaged brushlib.so library, which is currently only built for
x86_64 Linux machines. Other systems will need to use the older sketch_canvas module instead.
"""
from typing import Optional
import math
from PyQt5.QtGui import QPainter, QImage, QPixmap, QColor
from PyQt5.QtCore import Qt, QLine, QSize, QPoint, QRect
from PyQt5.QtWidgets import QGraphicsScene
from PIL import Image
from src.image.canvas.canvas import Canvas
from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.util.image_utils import pil_image_to_qimage
from src.image.mypaint.mp_surface import MPSurface
from src.image.mypaint.mp_brush import MPBrush
from src.image.mypaint.mp_tile import MPTile
from src.image.mypaint.libmypaint import TILE_DIM


class MyPaintCanvas(Canvas):
    """MyPaintCanvas provides an image editing layer that uses the MyPaint brush engine."""

    def __init__(self,
                 config: AppConfig,
                 image: Optional[QImage | Image.Image | QPixmap | QSize | str]):
        """Initialize with config values and optional arbitrary initial image data.

        Parameters
        ----------
        config: AppConfig
            Used for setting initial size if no initial image data is provided.
        image: QImage or PIL Image or QPixmap or QSize or str, optional
        """
        super().__init__(config, image)
        self._visible = True
        self._size = config.get(AppConfig.EDIT_SIZE)
        self._mp_surface = MPSurface(self._size)
        self._mp_surface.size = config.get(AppConfig.EDIT_SIZE)

        def set_brush_size(size: int) -> None:
            """Synchronize brush size with application config."""
            self.brush_size = size
        config.connect(self, AppConfig.SKETCH_BRUSH_SIZE, set_brush_size)
        self.brush_size = config.get(AppConfig.SKETCH_BRUSH_SIZE)
        self.set_image(image)
        self._drawing = False
        self._scene = None
        self._scale = 1.0
        self._has_sketch = False
        self._saved_brush_size = None
        self._saved_image = None
        self._layer_stack = None
        self._undo_coordinates = []
        self._redo_coordinates = []
        self._last_stroke_bounds = QRect(0, 0, 0, 0)

        self._mp_surface.brush.load_file(config.get(AppConfig.MYPAINT_BRUSH), True)

    @property
    def mp_surface(self) -> MPSurface:
        """Returns the underlying libmypaint surface."""
        return self._mp_surface

    def connect_layer_stack(self, layer_stack: LayerStack):
        """Connects an edited image to the canvas. Changes made to the canvas will be synchronized with the image."""
        self._layer_stack = layer_stack
        self.size = layer_stack.selection.size()
        self._layer_stack.visible_content_changed.connect(self._handle_layer_stack_update)
        self._layer_stack.selection_bounds_changed.connect(self._handle_layer_stack_update)

    def undo(self):
        """Apply undo operations to the connected image."""
        if self._layer_stack is not None and len(self._undo_coordinates) > 0:
            selection = self._layer_stack.selection
            undo_coordinates = self._undo_coordinates.pop()
            # if coordinates don't match current, move selection
            if selection != undo_coordinates:
                self._layer_stack.selection = undo_coordinates
            self._redo_coordinates.append(undo_coordinates)
        super().undo()
        self._copy_changes_to_layer()

    def redo(self):
        """Apply redo operations to the connected image."""
        if self._layer_stack is not None and len(self._redo_coordinates) > 0:
            selection = self._layer_stack.selection
            redo_coordinates = self._redo_coordinates.pop()
            if redo_coordinates != selection:
                self._layer_stack.selection = redo_coordinates
        super().redo()
        self._copy_changes_to_layer()

    def clear_undo_history(self):
        """Clears all cached undo and redo states."""
        self._undo_coordinates.clear()
        self._redo_coordinates.clear()
        super().clear_undo_history()

    def _handle_layer_stack_update(self, bounds: Optional[QRect] = None):
        if self._layer_stack is not None:
            self.set_image(self._layer_stack.qimage_selection_content())
            if bounds is None:  # Content change, not selection change, add to undo state:
                self._save_undo_state()

    def _copy_changes_to_layer(self):
        if self._layer_stack is not None:
            self._layer_stack.visible_content_changed.disconnect(self._handle_layer_stack_update)
            self._layer_stack.selection_bounds_changed.disconnect(self._handle_layer_stack_update)
            self._layer_stack.set_selection_content(self.q_image)
            self._layer_stack.visible_content_changed.connect(self._handle_layer_stack_update)
            self._layer_stack.selection_bounds_changed.connect(self._handle_layer_stack_update)

    def _save_undo_state(self, clear_redo_stack: bool = True):
        if self._layer_stack is not None:
            self._undo_coordinates.append(self._layer_stack.selection)
            max_undo_count = self._config.get(AppConfig.MAX_UNDO)
            if len(self._undo_coordinates) > max_undo_count:
                self._undo_coordinates = self._undo_coordinates[-max_undo_count:]
            if clear_redo_stack:
                self._redo_coordinates.clear()
        super()._save_undo_state(clear_redo_stack)

    @property
    def has_sketch(self) -> bool:
        """Returns whether the canvas contains non-empty image data."""
        return self._has_sketch

    def set_brush(self, brush_path: str):
        """Loads a MyPaint brush file.

        Parameters
        ----------
        brush_path : str
            Path to a valid MyPaint brush file. These files contain JSON data in the format specified by MyPaint and
            usually have the .myb extension.
        """
        self._mp_surface.brush.load_file(brush_path, True)
        self.brush_size = self.brush_size

    @property
    def brush_size(self):
        return super()._brush_size_get()

    @brush_size.setter
    def brush_size(self, size: int):
        """Sets the base brush size.

        Parameters
        ----------
        size : int
            Base brush blot diameter in pixels.
        """
        super()._brush_size_set(size)
        Canvas.brush_size.__set__(self, size)
        size_log_radius = math.log(size / 2)
        self._mp_surface.brush.set_value(MPBrush.RADIUS_LOGARITHMIC, size_log_radius)

    @property
    def _bounds_x(self):
        return self._last_stroke_bounds.x()

    @property
    def _bounds_y(self):
        return self._last_stroke_bounds.y()

    @property
    def _bounds_w(self):
        return self._last_stroke_bounds.width()

    @property
    def _bounds_h(self):
        return self._last_stroke_bounds.height()

    def add_to_scene(self, scene: QGraphicsScene, z_value: Optional[int] = None):
        """Adds the canvas to a QGraphicsScene.

        Parameters
        ----------
        scene : QGraphicsScene
            Scene that will display the canvas content.
        z_value : int
            Level within the scene where canvas content is drawn, higher levels appear above lower ones.
        """
        self._scene = scene

        def add_or_update_tile(tile: MPTile) -> None:
            """When tiles update, make sure they're in the scene and trigger a redraw."""
            if tile.scene() is None:
                tile.setZValue(z_value)
                scene.addItem(tile)
            if self._drawing:
                tile_x = int(tile.x())
                tile_y = int(tile.y())
                if self._last_stroke_bounds.isEmpty():
                    x1 = tile_x
                    y1 = tile_y
                    x2 = x1 + TILE_DIM
                    y2 = y1 + TILE_DIM
                else: 
                    x1 = min(tile_x, self._bounds_x)
                    y1 = min(tile_y, self._bounds_x)
                    x2 = min(max(tile_x + TILE_DIM, self._bounds_x + self._bounds_w), self.width)
                    y2 = min(max(tile_y + TILE_DIM, self._bounds_y + self._bounds_h), self.height)
                self._last_stroke_bounds.setCoords(x1, y1, x2, y2)
            tile.update()
        self._mp_surface.tile_created.connect(add_or_update_tile)
        self._mp_surface.tile_updated.connect(add_or_update_tile)

    def set_image(self, image_data: QImage | QSize | Image.Image | str):
        """Loads an image into the canvas, overwriting existing canvas content.

        Parameters
        ----------
        image_data : QImage or QSize or PIL Image or str
            An image, image size, or image path. If necessary, the canvas will be resized to match the image size.
            If image_data is a QSize, the canvas will be cleared.
        """
        if not hasattr(self, '_mp_surface'):
            return
        image = None
        if isinstance(image_data, QSize):
            if self.size != image_data:
                self._mp_surface.size = image_data
        elif isinstance(image_data, str):
            image = QImage(image_data)
        elif isinstance(image_data, Image.Image):
            image = pil_image_to_qimage(image_data)
        elif isinstance(image_data, QImage):
            image = image_data
        else:
            raise TypeError(f'Invalid image param {image_data}')
        if image is not None:
            if self._size != image.size():
                self._mp_surface.size = image.size()
            if image.format() != QImage.Format_ARGB32_Premultiplied:
                image.convertTo(QImage.Format_ARGB32_Premultiplied)
            self._mp_surface.load_image(image)

    @property
    def size(self) -> QSize:
        """Returns the canvas size in pixels as a QSize."""
        return self._mp_surface.size

    @size.setter
    def size(self, size: QSize):
        """Updates the canvas size, scaling any image content to match.

        Parameters
        ----------
        size : QSize
            New canvas size in pixels.
        """
        self._size = size
        size = QSize(int(size.width() * self._scale), int(size.height() * self._scale))
        if size != self._mp_surface.size:
            image = self.q_image.scaled(size)
            self._mp_surface.size = size
            self.set_image(image)

    @property
    def q_image(self) -> QImage:
        """Returns all canvas image content as a QImage."""
        image = self._mp_surface.render_image()
        if image.size() != self.size:
            image = image.scaled(self.size)
        return image

    def start_stroke(self):
        """Signals the start of a brush stroke, to be called once whenever user input starts or resumes."""
        if not self._visible:
            return
        self._last_stroke_bounds.setWidth(0)
        super().start_stroke()
        self._mp_surface.start_stroke()
        self._drawing = True

    def end_stroke(self):
        """Signals the end of a brush stroke, to be called once whenever user input stops or pauses."""
        if not self._visible:
            return
        self._drawing = False
        print(f'last stroke bounds: {self._last_stroke_bounds}')
        if self._saved_brush_size is not None:
            self.brush_size = self._saved_brush_size
            self._saved_brush_size = None
        self._copy_changes_to_layer()

    def draw_point(self,
                   point: QPoint,
                   color: QColor,
                   size_multiplier: Optional[float],
                   size_override: Optional[int] = None):
        """Draws a single point on the canvas.

        Parameters
        ----------
        point : QPoint
            Position where the point should be drawn.
        color : QColor
            Current color selected for drawing.
        size_multiplier : float, optional
            Tablet pen pressure value. This may or may not actually affect size, it depends on the brush.
        size_override : int, optional
            Value that should override brush_size for this operation only.
        """
        if not self._visible:
            return
        self._mp_surface.brush.set_value(MPBrush.ERASER, 0.0)
        self._draw(point, color, size_multiplier, size_override)

    def draw_line(self,
                  line: QLine,
                  color: QColor,
                  size_multiplier: Optional[float],
                  size_override: Optional[int] = None):
        """Draws a line on the canvas.

        Parameters
        ----------
        line : QLine
            Position where the line should be drawn.
        color : QColor
            Current color selected for drawing.
        size_multiplier : float, optional
            Tablet pen pressure value. This may or may not actually affect size, it depends on the brush.
        size_override : int, optional
            Value that should override brush_size for this operation only.
        """
        if not self._visible:
            return
        self._mp_surface.brush.set_value(MPBrush.ERASER, 0.0)
        self._draw(line, color, size_multiplier, size_override)

    def erase_point(self,
                    point: QPoint,
                    size_multiplier: Optional[float],
                    size_override: Optional[int] = None):
        """Erases a single point on the canvas.

        Parameters
        ----------
        point : QPoint
            Position where the point should be erased.
        size_multiplier : float, optional
            Tablet pen pressure value. This may or may not actually affect size, it depends on the brush.
        size_override : int, optional
            Value that should override brush_size for this operation only.
        """
        if not self._visible:
            return
        self._mp_surface.brush.set_value(MPBrush.ERASER, 1.0)
        self._draw(point, Qt.black, size_multiplier, size_override)

    def erase_line(self,
                   line: QLine,
                   size_multiplier: Optional[float],
                   size_override: Optional[int] = None):
        """Erases a line on the canvas.

        Parameters
        ----------
        line : QLine
            Position where the line should be erased.
        size_multiplier : float, optional
            Tablet pen pressure value. This may or may not actually affect size, it depends on the brush.
        size_override : int, optional
            Value that should override brush_size for this operation only.
        """
        if not self._visible:
            return
        self._mp_surface.brush.set_value(MPBrush.ERASER, 1.0)
        self._draw(line, Qt.black, size_multiplier, size_override)

    def fill(self, color: QColor):
        """Fills the canvas with a single QColor."""
        if not self._visible:
            return
        super().fill(color)
        self._has_sketch = True
        size = self.size
        image = QImage(size, QImage.Format_ARGB32)
        painter = QPainter(image)
        painter.fillRect(0, 0, size.width(), size.height(), color)
        painter.end()
        self.set_image(image)
        self._copy_changes_to_layer()

    def clear(self):
        """Replaces all canvas image contents with transparency.  Does nothing if connected to an image layer."""
        if self._layer_stack is not None:
            return
        super().clear()
        self._has_sketch = False
        self._mp_surface.clear()
        if self._layer_stack is not None:
            self.set_image(self._layer_stack.get_qimage_selection_content())

    def setVisible(self, visible: bool):
        """Shows or hides the canvas."""
        if visible == self._visible:
            return
        self._visible = visible
        if self._visible:
            if self._saved_image is not None:
                self.set_image(self._saved_image)
                self._saved_image = None
        else:
            self._saved_image = self.q_image
            self.clear()

    def _draw(self,
              pos: QPoint | QLine,
              color: QColor,
              size_multiplier: Optional[float],
              size_override: Optional[int] = None):
        if not self._visible:
            return
        if size_override is not None:
            if self._saved_brush_size is None:
                self._saved_brush_size = self.brush_size
            self.brush_size = size_override
        self._has_sketch = True
        self._mp_surface.brush.color = color
        if not self._drawing:
            self.start_stroke()
            if isinstance(pos, QLine):
                if size_multiplier is None:
                    self._mp_surface.basic_stroke_to(float(pos.x1()), float(pos.y1()))
                else:
                    self._mp_surface.stroke_to(float(pos.x1()), float(pos.y1()), size_multiplier, 0.0, 0.0)
        if isinstance(pos, QLine):
            if size_multiplier is None:
                self._mp_surface.basic_stroke_to(float(pos.x2()), float(pos.y2()))
            else:
                self._mp_surface.stroke_to(float(pos.x2()), float(pos.y2()), size_multiplier, 0.0, 0.0)
        else:  # QPoint
            if size_multiplier is None:
                self._mp_surface.basic_stroke_to(float(pos.x()), float(pos.y()))
            else:
                self._mp_surface.stroke_to(float(pos.x()), float(pos.y()), size_multiplier, 0.0, 0.0)
