"""
Combines various data_model/canvas modules to represent and control an edited image section.
"""
from PyQt5.QtGui import QPainter, QPen, QImage, QPixmap, QColor, QTabletEvent, QTransform
from PyQt5.QtCore import Qt, QPoint, QLine, QSize, QRect, QRectF, QBuffer, QEvent, QMargins
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem
import PyQt5.QtGui as QtGui
from PIL import Image

from ui.util.get_scaled_placement import get_scaled_placement
from ui.util.equal_margins import get_equal_margins
from ui.util.contrast_color import contrast_color
from ui.image_utils import pil_image_to_qimage, qimage_to_pil_image

class MaskCreator(QGraphicsView):
    """
    QWidget that shows the selected portion of the edited image, and lets the user draw a mask for inpainting.
    """

    def __init__(self, parent, mask_canvas, sketch_canvas, edited_image, config, eyedropper_callback=None):
        super().__init__(parent)
        self._config = config
        self._mask_canvas = mask_canvas
        self._sketch_canvas = sketch_canvas
        self._edited_image = edited_image
        self._drawing = False
        self._last_point = QPoint()
        self._use_eraser=False
        self._sketch_mode=False
        self._eyedropper_mode=False
        self._line_mode=False
        self._eyedropper_callback=eyedropper_callback
        self._sketch_color = QColor(0, 0, 0)
        self._pen_pressure = None
        self._pressure_size = False
        self._pressure_opacity = False
        self._tablet_eraser = False
        selection_size = self._mask_canvas.size()
        self._image_rect = get_scaled_placement(QRect(QPoint(0, 0), self.size()), selection_size,
                self._border_size())

        # Setup scene with layers:
        self.setAlignment(Qt.AlignCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCacheMode(QGraphicsView.CacheBackground)
        self.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self._scene = QGraphicsScene()
        self.setScene(self._scene)

        selection_size = self._mask_canvas.size()
        selection_rect_f = QRectF(0.0, 0.0, float(selection_size.width()), float(selection_size.height()))
        self._scene.setSceneRect(selection_rect_f)

        self._image_pixmap = None
        sketch_canvas.add_to_scene(self._scene, 0)
        mask_canvas.add_to_scene(self._scene, 1)
        self.resizeEvent(None)

        def update_image():
            if edited_image.has_image():
                image = edited_image.get_selection_content()
                self.load_image(image)
            else:
                self._image_pixmap = None
                self.resizeEvent(None)
                self.update()
        edited_image.selection_changed.connect(update_image)
        update_image()

    def set_pressure_size_mode(self, use_pressure_size):
        self._pressure_size = use_pressure_size

    def set_pressure_opacity_mode(self, use_pressure_opacity):
        self._pressure_opacity = use_pressure_opacity

    def _get_sketch_opacity(self):
        return 1.0 if (not self._pressure_opacity or self._pen_pressure is None) else min(1, self._pen_pressure * 1.25)

    def set_sketch_mode(self, sketch_mode):
        self._sketch_mode = sketch_mode
        self._mask_canvas.setOpacity(0.4 if sketch_mode else 0.6)

    def set_eyedropper_mode(self, eyedropper_mode):
        self._eyedropper_mode = eyedropper_mode

    def set_line_mode(self, line_mode):
        self._line_mode = line_mode
        if line_mode:
            self._drawing = False

    def get_sketch_color(self):
        return self._sketch_color

    def set_sketch_color(self, sketch_color):
        self._sketch_color = sketch_color

    def set_use_eraser(self, use_eraser):
        self._use_eraser = use_eraser

    def clear(self):
        if self._sketch_mode:
            if self._sketch_canvas.enabled():
                self._sketch_canvas.clear()
        else:
            if self._mask_canvas.enabled():
                self._mask_canvas.clear()
        self.update()

    def undo(self):
        canvas = self._sketch_canvas if self._sketch_mode else self._mask_canvas
        if canvas.enabled():
            canvas.undo()
        self.update()

    def redo(self):
        canvas = self._sketch_canvas if self._sketch_mode else self._mask_canvas
        if canvas.enabled():
            canvas.redo()
        self.update()

    def fill(self):
        canvas = self._sketch_canvas if self._sketch_mode else self._mask_canvas
        color = self._sketch_color if self._sketch_mode else Qt.red
        if canvas.enabled():
            canvas.fill(color)
        self.update()

    def load_image(self, pil_image):
        selectionSize = self._mask_canvas.size()
        selectionRectF = QRectF(0.0, 0.0, float(selectionSize.width()), float(selectionSize.height()))
        self._scene.setSceneRect(selectionRectF)
        self._imageSection = pil_image_to_qimage(pil_image)
        self._image_pixmap = QPixmap.fromImage(self._imageSection)
        self.resizeEvent(None)
        self.resetCachedContent()
        self.update()

    def _widget_to_image_coords(self, point):
        assert isinstance(point, QPoint)
        point_f = self.mapToScene(point)
        return QPoint(int(point_f.x()), int(point_f.y()))


    def get_color_at_point(self, point):
        sketch_color = QColor(0, 0, 0, 0)
        image_color = QColor(0, 0, 0, 0)
        if self._sketch_canvas._has_sketch:
            sketch_color = self._sketch_canvas.get_color_at_point(point)
        image_color = self._imageSection.pixelColor(point)
        def getComponent(sketchComp, imageComp):
            return int((sketchComp * sketch_color.alphaF()) + (imageComp * image_color.alphaF() * (1.0 - sketch_color.alphaF())))
        red = getComponent(sketch_color.red(), image_color.red())
        green = getComponent(sketch_color.green(), image_color.green())
        blue = getComponent(sketch_color.blue(), image_color.blue())
        combined = QColor(red, green, blue)
        return combined

    def mousePressEvent(self, event):
        if not self._edited_image.has_image():
            return
        if event.button() == Qt.LeftButton or event.button() == Qt.RightButton:
            size_override = 1 if event.button() == Qt.RightButton else None
            if self._eyedropper_mode:
                point = self._widget_to_image_coords(event.pos())
                color = self.get_color_at_point(point)
                if color is not None:
                    self._eyedropper_callback(color)
            else:
                canvas = self._sketch_canvas if self._sketch_mode else self._mask_canvas
                color = QColor(self._sketch_color if self._sketch_mode else Qt.red)
                if self._sketch_mode and self._pressure_opacity:
                    color.setAlphaF(self._get_sketch_opacity())
                size_multiplier = self._pen_pressure if (self._pressure_size and self._pen_pressure is not None) else None
                if self._line_mode:
                    #canvas.start_stroke()
                    new_point = self._widget_to_image_coords(event.pos())
                    line = QLine(self._last_point, new_point)
                    self._last_point = new_point
                    # Prevent issues with lines not drawing by setting a minimum multiplier for lineMode only:
                    if size_multiplier is not None:
                        size_multiplier = max(size_multiplier, 0.5)
                    if self._use_eraser:
                        canvas.erase_line(line, color, size_multiplier, size_override)
                    else:
                        canvas.draw_line(line, color, size_multiplier, size_override)
                    canvas.end_stroke()
                else:
                    canvas.start_stroke()
                    self._drawing = True
                    self._mask_canvas.setOpacity(0.8 if canvas == self._mask_canvas else 0.2)

                    self._last_point = self._widget_to_image_coords(event.pos())
                    if self._use_eraser or self._tablet_eraser:
                        canvas.erase_point(self._last_point, color, size_multiplier, size_override)
                    else:
                        canvas.draw_point(self._last_point, color, size_multiplier, size_override)
                self.update()

    def mouseMoveEvent(self, event):
        if (Qt.LeftButton == event.buttons() or Qt.RightButton == event.buttons()) and self._drawing and not self._eyedropper_mode:
            size_override = 1 if Qt.RightButton == event.buttons() else None
            canvas = self._sketch_canvas if self._sketch_mode else self._mask_canvas
            color = QColor(self._sketch_color if self._sketch_mode else Qt.red)
            if self._sketch_mode and self._pressure_opacity:
                color.setAlphaF(self._get_sketch_opacity())
            size_multiplier = self._pen_pressure if (self._pressure_size and self._pen_pressure is not None) else 1.0
            new_last_point = self._widget_to_image_coords(event.pos())
            line = QLine(self._last_point, new_last_point)
            self._last_point = new_last_point
            if self._use_eraser or self._tablet_eraser:
                canvas.erase_line(line, color, size_multiplier, size_override)
            else:
                canvas.draw_line(line, color, size_multiplier, size_override)
            self.update()

    def tabletEvent(self, tabletEvent):
        if tabletEvent.type() == QEvent.TabletRelease:
            self._pen_pressure = None
            self._tablet_eraser = False
        elif tabletEvent.type() == QEvent.TabletPress:
            self._tablet_eraser = (tabletEvent.pointerType() == QTabletEvent.PointerType.Eraser)
            self._pen_pressure = tabletEvent.pressure()
        else:
            self._pen_pressure = tabletEvent.pressure()

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.LeftButton or event.button() == Qt.RightButton) and self._drawing:
            self._drawing = False
            self._pen_pressure = None
            self._tablet_eraser = False
            canvas = self._sketch_canvas if self._sketch_mode else self._mask_canvas
            self._last_point = self._widget_to_image_coords(event.pos())
            color = QColor(self._sketch_color if self._sketch_mode else Qt.red)
            size_multiplier = self._pen_pressure if (self._pressure_size and self._pen_pressure is not None) else None
            size_override = 1 if event.button() == Qt.RightButton else None
            if self._use_eraser or self._tablet_eraser:
                canvas.erase_point(self._last_point, color, size_multiplier, size_override)
            else:
                canvas.draw_point(self._last_point, color, size_multiplier, size_override)
            canvas.end_stroke()
            self._mask_canvas.setOpacity(0.6 if canvas == self._mask_canvas else 0.4)
        self.update()


    def drawBackground(self, painter, rect):
        x_scale = self._image_rect.width() / self.size().width()
        y_scale = self._image_rect.height() / self.size().height()
        image_rect = QRectF(0, 0, rect.width() * x_scale, rect.height() * y_scale).toAlignedRect()
        if self._image_pixmap is not None:
            painter.drawPixmap(image_rect, self._image_pixmap)
        margins = QMargins(5, 5, 5, 5)
        border_rect = image_rect.marginsAdded(margins)
        painter.setPen(QPen(contrast_color(self), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(border_rect)

    def drawForeground(self, painter, rect):
        x_scale = self._image_rect.width() / self.size().width()
        y_scale = self._image_rect.height() / self.size().height()
        image_rect = QRectF(0, 0, rect.width() * x_scale, rect.height() * y_scale).toAlignedRect()
        margins = QMargins(5, 5, 5, 5)
        border_rect = image_rect.marginsAdded(margins)

        # QGraphicsView fails to clip content sometimes, so fill everything outside of the scene with the
        # background color, then draw the border:
        fill_color = self.palette().color(self.backgroundRole())
        border_left = int(border_rect.x())
        border_right = border_left + int(border_rect.width())
        border_top = int(border_rect.y())
        border_bottom = border_top + int(border_rect.height())

        max_size = 200000000 # Larger than the viewport can ever possibly be, small enough to avoid overflow issues
        painter.fillRect(border_left, -(max_size // 2), -max_size, max_size, fill_color)
        painter.fillRect(border_right, -(max_size // 2), max_size, max_size, fill_color)
        painter.fillRect(-(max_size // 2), border_top, max_size, -max_size, fill_color)
        painter.fillRect(-(max_size // 2), border_bottom, max_size, max_size, fill_color)

        painter.setPen(QPen(contrast_color(self), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(border_rect)
        super().drawForeground(painter, rect)


    def resizeEvent(self, event):
        selection_size = self._mask_canvas.size()
        selection_rect_f = QRectF(0.0, 0.0, float(selection_size.width()), float(selection_size.height()))
        if selection_rect_f != self._scene.sceneRect():
            self._scene.setSceneRect(selection_rect_f)

        border_size = self._border_size()
        self._image_rect = get_scaled_placement(QRect(QPoint(0, 0), self.size()), self._mask_canvas.size(),
                border_size)
        x_scale = self._image_rect.width() / self._mask_canvas.width()
        y_scale = self._image_rect.height() / self._mask_canvas.height()
        transformation = QTransform()
        transformation.scale(x_scale, y_scale)
        transformation.translate(float(self._image_rect.x()), float(self._image_rect.y()))
        self.setTransform(transformation)
        # TODO: find a good way to do this within MaskPanel directly:
        if self.parent() and hasattr(self.parent(), '_updateBrushCursor'):
            self.parent()._updateBrushCursor()
        self.update()

    def get_image_display_size(self):
        return QSize(self._image_rect.width(), self._image_rect.height())

    def _border_size(self):
        return (min(self.width(), self.height()) // 40) + 1
