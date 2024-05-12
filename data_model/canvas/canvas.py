"""
Interface for classes that display image data through a QGraphicsView and support various drawing and editing
operations.
"""

from PyQt5.QtGui import QColor
from PyQt5.QtCore import QObject, pyqtSignal
from ui.image_utils import qimage_to_pil_image

class Canvas():
    """
    Interface for classes that display image data through a QGraphicsView and support various drawing and editing
    operations.

    Signals
    -------
    enabled_state_changed: bool
        Emitted whenever a Canvas is enabled or disabled.
    """


    def __init__(self, config, image):
        """ Initialize with config values and optional arbitrary initial image data.

        Parameters
        ----------

        config: data_model.Config
            Used for setting initial size if no initial image data is provided.
        image: QImage or PIL Image or QPixmap or QSize or str, optional
        """
        super().__init__()
        self._config = config
        self._brush_size = 1
        self._image = None

        # Directly inheriting from QObject can cause problems with multiple inheritance, so Canvas will use a wrapped
        # inner QObject to handle PyQt5 signals.
        class _SignalWrapper(QObject):
            enabled_state_changed = pyqtSignal(bool)

        self._signal_wrapper = _SignalWrapper()
        self.enabled_state_changed = self._signal_wrapper.enabled_state_changed
        self._undo_stack = []
        self._redo_stack = []
        if image is not None:
            self.set_image(image)
        else:
            self.set_image(config.get('editSize'))
        self._enabled = True


    def undo(self):
        """
        Reverses the last change applied to canvas image content.

        Canvas tracks a number of state changes defined by the "maxUndo" config parameter, and can reverse those
        changes using the undo function. The following are considered discrete changes by the undo and redo functions:
        - All changes from draw_point(), draw_line(), erase_point(), and erase_line() made between calling
          start_stroke() and calling end_stroke().
        - Any individual call to fill(), clear(), or set_image().
        """
        if len(self._undo_stack) == 0:
            return
        image = self.get_qimage().copy()
        self._redo_stack.append(image)
        new_image = self._undo_stack.pop()
        if new_image.size() != self.size():
            new_image = new_image.scaled(self.size())
        self.set_image(new_image)


    def redo(self):
        """Restores a change previously removed through canvas.undo()"""
        if len(self._redo_stack) == 0:
            return
        self._save_undo_state(False)
        image = self._redo_stack.pop()
        if image.size() != self.size():
            image = image.scaled(self.size())
        self.set_image(image)


    def undo_count(self):
        """Returns the number of image states currently cached that can be restored through undo()."""
        return len(self._undo_stack)

    def redo_count(self):
        """Returns the number of image states currently cached that can be restored through redo()."""
        return len(self._undo_stack)


    def set_enabled(self, enabled):
        """
        Sets whether the canvas is currently enabled. When not enabled, all drawing operations should be ignored, and
        canvas content should not be drawn.
        """
        if enabled != self._enabled:
            self._enabled = enabled
            if hasattr(self, 'setVisible'):
                self.setVisible(enabled)
            self.enabled_state_changed.emit(enabled)


    def enabled(self):
        """Returns whether the canvas is currently enabled."""
        return self._enabled


    def set_brush_size(self, size):
        """Sets the base size in pixels used when drawing or erasing lines within the canvas."""
        self._brush_size = size


    def brush_size(self):
        """Returns the base size in pixels used when drawing or erasing lines within the canvas."""
        return self._brush_size


    def get_pil_image(self):
        """
        Returns canvas image contents as a PIL Image. This relies on self.get_qimage(), so make sure to override this
        if adding a Canvas class that works directly with PIL Image data.
        """
        return qimage_to_pil_image(self.get_qimage())


    def get_color_at_point(self, point):
        """
        Returns canvas color at a particular QPoint, or a completely transparent QColor if the point is not within
        the canvas bounds.
        """
        if self.get_qimage().rect().contains(point):
            return self.get_qimage().pixelColor(point)
        return QColor(0, 0, 0, 0)


    def start_stroke(self):
        """
        Unimplemented, intended for handling necessary steps before a series of connected drawing operations.
        Additional requirements are implementation-specific. Implementations should call super().start_stroke() to
        ensure undo/redo state is managed properly.
        """
        self._save_undo_state()


    def fill(self, color):
        """
        Partially unimplemented. Implementations should call super().fill(), then fill the image with the given
        QColor. Calling the super() method will ensure undo/redo state is managed properly.
        """
        self._save_undo_state()


    def clear(self):
        """
        Partially unimplemented. Implementations should call super().clear(), then erase all image data. Calling
        the super() method will ensure undo/redo state is managed properly.
        """
        self._save_undo_state()


    def add_to_scene(self, scene):
        """Unimplemented. Implementations should add the canvas to a QGraphicsScene"""
        raise NotImplementedError("Canvas.add_to_scene not implemented")


    def set_image(self, image_data):
        """
        Unimplemented. Implementations should initialize canvas content from a QImage, QPixmap, PIL Image, or QSize.
        """
        raise NotImplementedError("Canvas.set_image() not implemented")


    def size(self):
        """Unimplemented. Implementations should return the canvas size in pixels as QSize."""
        raise NotImplementedError("Canvas.size() not implemented")


    def width(self):
        """Unimplemented. Implementations should return the canvas width in pixels as int."""
        raise NotImplementedError("Canvas.width() not implemented")


    def height(self):
        """Unimplemented. Implementations should return the canvas height in pixels as int."""
        raise NotImplementedError("Canvas.height() not implemented")


    def get_qimage(self):
        """Unimplemented. Implementations should return the canvas contents as a QImage."""
        raise NotImplementedError("Canvas.get_qimage() not implemented")


    def resize(self, size):
        """Unimplemented. Implementations should resize the canvas to match the QSize parameter."""
        raise NotImplementedError("Canvas.resize() not implemented")


    def end_stroke(self):
        """
        Unimplemented, intended for handling necessary steps after a series of connected drawing operations.
        Additional requirements are implementation-specific. Implementations should *not* call super().end_stroke()
        """
        raise NotImplementedError("Canvas.end_stroke() not implemented")


    def draw_point(self, point, color, size_multiplier, size_override = None):
        """
        Unimplemented. Implementations should draw a circle to the canvas based on expected parameters and the current
        brush size.

        Parameters
        ----------

        point: QPoint
            Image pixel coordinates. Implementations need to draw a circle centered at this point.
        color: QColor
        size_multiplier: float
            Multiplier to apply to self.brush_size() to determine the diameter of the circle drawn.
        size_override: float, optional
            If defined, both self.brush_size() and size_multiplier should be ignored, and this value should be used
            as the circle diameter instead.
        """
        raise NotImplementedError("Canvas.draw_point() not implemented")


    def draw_line(self, line, color, size_multiplier, size_override = None):
        """
        Unimplemented. Implementations should draw a line on the canvas based on expected parameters and the current
        brush size.

        Parameters
        ----------

        line: QLine
            Image pixel coordinates. Implementations need to draw a line between these two points.
        color: QColor
        size_multiplier: float
            Multiplier to apply to self.brush_size() to determine the thickness of the line drawn.
        size_override: float, optional
            If defined, both self.brush_size() and size_multiplier should be ignored, and this value should be used
            as the line thickness instead.
        """
        raise NotImplementedError("Canvas.draw_line() not implemented")


    def erase_point(self, point, size_multiplier, size_override = None):
        """
        Unimplemented. Implementations should erase a circle in the canvas based on expected parameters and the current
        brush size.

        Parameters
        ----------

        point: QPoint
            Image pixel coordinates. Implementations need to erase a circle centered at this point.
        size_multiplier: float
            Multiplier to apply to self.brush_size() to determine the diameter of the circle erased.
        size_override: float, optional
            If defined, both self.brush_size() and size_multiplier should be ignored, and this value should be used
            as the circle diameter instead.
        """
        raise NotImplementedError("Canvas.erase_point() not implemented")


    def erase_line(self, line, size_multiplier, size_override = None):
        """
        Unimplemented. Implementations should erase a line on the canvas based on expected parameters and the current
        brush size.

        Parameters
        ----------

        line: QLine
            Image pixel coordinates. Implementations need to erase a line between these two points.
        size_multiplier: float
            Multiplier to apply to self.brush_size() to determine the thickness of the line erased.
        size_override: float, optional
            If defined, both self.brush_size() and size_multiplier should be ignored, and this value should be used
            as the line thickness instead.
        """
        raise NotImplementedError("Canvas.erase_line() not implemented")


    def _save_undo_state(self, clear_redo_stack=True):
        image = self.get_qimage().copy()
        self._undo_stack.append(image)
        max_undo_count = self._config.get('maxUndo')
        if len(self._undo_stack) > max_undo_count:
            self._undo_stack = self._undo_stack[-max_undo_count:]
        if clear_redo_stack:
            self._redo_stack.clear()
