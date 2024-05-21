"""
Combines various data_model/canvas modules to represent and control an edited image section.
"""
from typing import Optional
from PyQt5.QtGui import QColor, QPixmap, QImage, QTabletEvent, QMouseEvent
from PyQt5.QtCore import Qt, QPoint, QLine, QSize, QEvent, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget
from ui.widget.fixed_aspect_graphics_view import FixedAspectGraphicsView
from data_model.image.canvas import Canvas
from data_model.image.layer_stack import LayerStack
from data_model.config.application_config import AppConfig


class MaskCreator(FixedAspectGraphicsView):
    """
    QWidget that shows the selected portion of the edited image, and lets the user draw a mask for inpainting.
    """

    class DrawMode:
        """Panel drawing mode options."""

        MASK = 'Mask'
        SKETCH = 'Sketch'

        @staticmethod
        def is_valid(option):
            """Returns whether a value is a valid drawing mode."""
            return option == MaskCreator.DrawMode.MASK or option == MaskCreator.DrawMode.SKETCH or option is None

    class ToolMode:
        """Drawing tool options."""

        PEN = 'Pen'
        ERASER = 'Eraser'

        @staticmethod
        def is_valid(option):
            """Returns whether a value is a valid drawing tool mode."""
            return option == MaskCreator.ToolMode.PEN or option == MaskCreator.ToolMode.ERASER or option is None

    color_selected = pyqtSignal(QColor)

    def __init__(self,
                 parent: Optional[QWidget],
                 mask_canvas: Canvas,
                 sketch_canvas: Canvas,
                 layer_stack: LayerStack,
                 config: AppConfig):
        super().__init__(parent)
        self._config = config
        self._mask_canvas = mask_canvas
        self._sketch_canvas = sketch_canvas
        self._layer_stack = layer_stack
        self._drawing = False
        self._last_point = QPoint()
        self._tool_mode = MaskCreator.ToolMode.PEN
        self._draw_mode = MaskCreator.DrawMode.MASK if mask_canvas.enabled() else MaskCreator.DrawMode.SKETCH
        self._line_mode = False
        self._sketch_color = QColor(0, 0, 0)
        self._pen_pressure = None
        self._pressure_size = False
        self._pressure_opacity = False
        self._tablet_eraser = False
        self._image_section = None
        self._image_pixmap = None
        self._mode_swap_timestamps = []
        self.content_size = self._mask_canvas.size()
        sketch_canvas.add_to_scene(self.scene(), 0)
        mask_canvas.add_to_scene(self.scene(), 1)
        self.resizeEvent(None)

        def update_image() -> None:
            """Apply the changes when image layer content is altered."""
            self.content_size = layer_stack.selection.size()
            self.background = layer_stack.qimage_selection_content()

        layer_stack.size_changed.connect(update_image)
        layer_stack.selection_bounds_changed.connect(update_image)
        layer_stack.visible_content_changed.connect(update_image)
        update_image()

    def set_pressure_size_mode(self, use_pressure_size: bool) -> None:
        """Set whether tablet pen pressure affects line width."""
        self._pressure_size = use_pressure_size

    def set_pressure_opacity_mode(self, use_pressure_opacity: bool) -> None:
        """Set whether tablet pen pressure affects line opacity."""
        self._pressure_opacity = use_pressure_opacity

    def _get_sketch_opacity(self) -> float:
        return 1.0 if (not self._pressure_opacity or self._pen_pressure is None) else min(1, self._pen_pressure * 1.25)

    def set_draw_mode(self, mode: str) -> None:
        """Sets whether the panel is sketching into the image or masking off an area for inpainting.

        Parameters
        ----------
        mode : str from MaskCreator.DrawMode
            Selected drawing mode.
        """
        if mode == self._draw_mode:
            return
        if not MaskCreator.DrawMode.is_valid(mode):
            raise ValueError(f'tried to set invalid drawing mode {mode}')
        if mode == MaskCreator.DrawMode.MASK and not self._mask_canvas.enabled():
            raise ValueError('called setDrawMode(MASK) when mask mode is disabled')
        if mode == MaskCreator.DrawMode.SKETCH and not self._sketch_canvas.enabled():
            raise ValueError('called setDrawMode(SKETCH) when sketch mode is disabled')
        self._draw_mode = mode
        if self._draw_mode != mode:
            self._draw_mode = mode
            self._mask_canvas.setOpacity(0.4 if mode == MaskCreator.DrawMode.SKETCH else 0.6)

    def get_draw_mode(self) -> Optional[str]:
        """Returns the current MaskCreator.DrawMode drawing mode."""
        return self._draw_mode

    def set_line_mode(self, line_mode: bool) -> None:
        """Sets whether clicking on the canvas should draw a line from the last clicked point."""
        self._line_mode = line_mode
        if line_mode:
            self._drawing = False

    def get_sketch_color(self) -> QColor:
        """Returns the current sketch canvas brush color."""
        return self._sketch_color

    def set_sketch_color(self, sketch_color: QColor):
        """Sets the current sketch canvas brush color."""
        self._sketch_color = sketch_color

    def set_tool_mode(self, mode: ToolMode):
        """Selects between draw ane erase modes."""
        if mode == self._tool_mode:
            return
        if not MaskCreator.ToolMode.is_valid(mode):
            raise ValueError(f'tried to set invalid drawing tool mode {mode}')
        self._tool_mode = mode

    def get_tool_mode(self) -> str:
        """Returns the current MaskCreator.ToolMode drawing tool mode."""
        return self._tool_mode

    def clear(self):
        """Clears image content in the active canvas."""
        if self._draw_mode == MaskCreator.DrawMode.SKETCH:
            if self._sketch_canvas.enabled():
                self._sketch_canvas.clear()
        else:
            if self._mask_canvas.enabled():
                self._mask_canvas.clear()
        self.update()

    def undo(self):
        """Reverses the last drawing operation done in the active canvas."""
        canvas = self._sketch_canvas if self._draw_mode == MaskCreator.DrawMode.SKETCH else self._mask_canvas
        if canvas.enabled():
            canvas.undo()
        self.update()

    def redo(self):
        """Restores the last drawing operation in the active canvas removed by undo."""
        canvas = self._sketch_canvas if self._draw_mode == MaskCreator.DrawMode.SKETCH else self._mask_canvas
        if canvas.enabled():
            canvas.redo()
        self.update()

    def fill(self):
        """Fills the active canvas."""
        if self._draw_mode == MaskCreator.DrawMode.SKETCH:
            if self._sketch_canvas.enabled():
                self._sketch_canvas.fill(self._sketch_color)
        else:
            if self._mask_canvas.enabled():
                self._mask_canvas.fill()
        self.update()

    def load_image(self, image: Optional[QPixmap | QImage]):
        """Loads a new image section behind the canvas."""
        self.background = image

    def get_color_at_point(self, point: QPoint) -> QColor:
        """Returns the color of the image and sketch canvas at a given point.

        If the point is outside of the widget bounds, QColor(0, 0, 0) is returned instead.
        """
        sketch_color = QColor(0, 0, 0, 0)
        image_color = QColor(0, 0, 0, 0)
        if self._sketch_canvas.has_sketch():
            sketch_color = self._sketch_canvas.get_color_at_point(point)
        if self.background is not None:
            image_color = self.background.toImage().pixelColor(point)

        def get_component(sketch_component: float, image_component: float) -> float:
            """Get combined values for a RGBA image color component"""
            return int((sketch_component * sketch_color.alphaF()) + (image_component * image_color.alphaF()
                                                                     * (1.0 - sketch_color.alphaF())))

        red = get_component(sketch_color.red(), image_color.red())
        green = get_component(sketch_color.green(), image_color.green())
        blue = get_component(sketch_color.blue(), image_color.blue())
        combined = QColor(red, green, blue)
        return combined

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Start drawing, erasing, or color sampling when clicking if an image is loaded."""
        if not self._layer_stack.has_image:
            return
        key_modifiers = QApplication.keyboardModifiers()
        if event.button() == Qt.LeftButton or event.button() == Qt.RightButton:
            size_override = 1 if event.button() == Qt.RightButton else None
            if key_modifiers == Qt.ControlModifier and self._draw_mode == MaskCreator.DrawMode.SKETCH:
                point = self.widget_to_scene_coords(event.pos()).toPoint()
                color = self.get_color_at_point(point)
                if color is not None:
                    self.color_selected.emit(color)
            else:
                canvas = self._sketch_canvas if self._draw_mode == MaskCreator.DrawMode.SKETCH else self._mask_canvas
                color = QColor(self._sketch_color if self._draw_mode == MaskCreator.DrawMode.SKETCH else Qt.red)
                if self._draw_mode == MaskCreator.DrawMode.SKETCH and self._pressure_opacity:
                    color.setAlphaF(self._get_sketch_opacity())
                size_multiplier = self._pen_pressure if (self._pressure_size and self._pen_pressure is not None) \
                    else None
                if self._line_mode:
                    new_point = self.widget_to_scene_coords(event.pos()).toPoint()
                    line = QLine(self._last_point, new_point)
                    self._last_point = new_point
                    # Prevent issues with lines not drawing by setting a minimum multiplier for lineMode only:
                    if size_multiplier is not None:
                        size_multiplier = max(size_multiplier, 0.5)
                    if self._tool_mode == MaskCreator.ToolMode.ERASER:
                        canvas.erase_line(line, size_multiplier, size_override)
                    else:
                        canvas.draw_line(line, color, size_multiplier, size_override)
                    canvas.end_stroke()
                else:
                    canvas.start_stroke()
                    self._drawing = True
                    self._mask_canvas.setOpacity(0.8 if canvas == self._mask_canvas else 0.2)

                    self._last_point = self.widget_to_scene_coords(event.pos()).toPoint()
                    if self._tool_mode == MaskCreator.ToolMode.ERASER or self._tablet_eraser:
                        canvas.erase_point(self._last_point, size_multiplier, size_override)
                    else:
                        canvas.draw_point(self._last_point, color, size_multiplier, size_override)
                self.update()

    def mouseMoveEvent(self, event: Optional[QMouseEvent]) -> None:
        """Continue any active drawing when the mouse is moved with a button held down."""
        if not self._layer_stack.has_image:
            return
        if (Qt.LeftButton == event.buttons() or Qt.RightButton == event.buttons()) and self._drawing:
            size_override = 1 if Qt.RightButton == event.buttons() else None
            canvas = self._sketch_canvas if self._draw_mode == MaskCreator.DrawMode.SKETCH else self._mask_canvas
            color = QColor(self._sketch_color if self._draw_mode == MaskCreator.DrawMode.SKETCH else Qt.red)
            if self._draw_mode == MaskCreator.DrawMode.SKETCH and self._pressure_opacity:
                color.setAlphaF(self._get_sketch_opacity())
            size_multiplier = self._pen_pressure if (self._pressure_size and self._pen_pressure is not None) else 1.0
            new_last_point = self.widget_to_scene_coords(event.pos()).toPoint()
            line = QLine(self._last_point, new_last_point)
            self._last_point = new_last_point
            if self._tool_mode == MaskCreator.ToolMode.ERASER or self._tablet_eraser:
                canvas.erase_line(line, size_multiplier, size_override)
            else:
                canvas.draw_line(line, color, size_multiplier, size_override)
            self.update()

    def tabletEvent(self, tablet_event: Optional[QTabletEvent]) -> None:
        """Update pen pressure and eraser status when a drawing tablet event is triggered."""
        if tablet_event.type() == QEvent.TabletRelease:
            self._pen_pressure = None
            self._tablet_eraser = False
        elif tablet_event.type() == QEvent.TabletPress:
            self._tablet_eraser = tablet_event.pointerType() == QTabletEvent.PointerType.Eraser
            self._pen_pressure = tablet_event.pressure()
        else:
            self._pen_pressure = tablet_event.pressure()

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Finishes any drawing operations when the mouse button is released."""
        if not self._layer_stack.has_image:
            return
        if (event.button() == Qt.LeftButton or event.button() == Qt.RightButton) and self._drawing:
            self._drawing = False
            self._pen_pressure = None
            self._tablet_eraser = False
            canvas = self._sketch_canvas if self._draw_mode == MaskCreator.DrawMode.SKETCH else self._mask_canvas
            canvas.end_stroke()
            self._mask_canvas.setOpacity(0.6 if canvas == self._mask_canvas else 0.4)
        self.update()

    def get_image_display_size(self) -> QSize:
        """Get the QSize in pixels of the area where the edited image section is drawn."""
        return QSize(self.displayed_content_size.width(), self.displayed_content_size.height())
