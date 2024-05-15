"""
A PyQt5 widget wrapper for data_model/edited_image.
"""

from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import Qt, QPoint, QRect, QSize

from ui.util.get_scaled_placement import get_scaled_placement
from ui.util.equal_margins import get_equal_margins

class ImageViewer(QWidget):
    """
    Shows the image being edited, and allows the user to select sections.
    """

    def __init__(self, edited_image):
        super().__init__()
        self._edited_image = edited_image
        self._border_size = 4
        edited_image.size_changed.connect(lambda: self.resizeEvent(None))
        edited_image.selection_changed.connect(self.update)
        edited_image.content_changed.connect(self.update)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

    def resizeEvent(self, unused_event):
        """Recalculate drawn image bounds on resize."""
        if self._edited_image.has_image():
            self._image_rect = get_scaled_placement(QRect(QPoint(0, 0), self.size()), self._edited_image.size(),
                    self._border_size)
        else:
            self._image_rect = get_scaled_placement(QRect(QPoint(0, 0), self.size()), self.size(), self._border_size)

    def _image_to_widget_coords(self, point):
        assert isinstance(point, QPoint)
        scale = self._image_rect.width() / self._edited_image.width()
        return QPoint(int(point.x() * scale) + self._image_rect.x(),
                int(point.y() * scale) + self._image_rect.y())

    def _widget_to_image_coords(self, point):
        assert isinstance(point, QPoint)
        scale = self._image_rect.width() / self._edited_image.width()
        return QPoint(int((point.x() - self._image_rect.x()) / scale),
                int((point.y() - self._image_rect.y()) / scale))

    def paintEvent(self, unused_event):
        """Draw the image, selection area, and border."""
        painter = QPainter(self)
        line_pen = QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(line_pen)
        if self._edited_image.has_image():
            painter.drawImage(self._image_rect, self._edited_image.get_qimage())
            # outline selection:
            selection = self._edited_image.get_selection_bounds()
            selection_top_left = self._image_to_widget_coords(selection.topLeft())
            selection_bottom_right = self._image_to_widget_coords(selection.topLeft() +
                    + QPoint(selection.width(), selection.height()))
            selected_rect = QRect(selection_top_left, selection.size())
            selected_rect.setBottomRight(selection_bottom_right)
            painter.drawRect(selected_rect)
        # draw margin:
        line_pen.setWidth(self._border_size)
        painter.drawRect(QRect(QPoint(0, 0), self.size()).marginsRemoved(get_equal_margins(2)))

    def sizeHint(self):
        """Returns image size as ideal widget size."""
        if self._edited_image.has_image():
            return self._edited_image.size()
        return QSize(512, 512)

    def mousePressEvent(self, event):
        """Select the area in in the image to be edited."""
        if event.button() == Qt.LeftButton and self._edited_image.has_image():
            image_coords = self._widget_to_image_coords(event.pos())
            selection = self._edited_image.get_selection_bounds()
            selection.moveTopLeft(image_coords)
            self._edited_image.set_selection_bounds(selection)
