"""
Popup modal window used for cropping or extending the edited image without scaling its contents.
"""
from PyQt5.QtWidgets import QWidget, QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QSize, QRect, QPoint
from PyQt5.QtGui import QImage, QPainter, QPen
from ui.widget.labeled_spinbox import LabeledSpinbox
from ui.util.get_scaled_placement import get_scaled_placement
import math

class ResizeCanvasModal(QDialog):
    """ResizeCanvasModal.
    """

    def __init__(self, qImage):
        """__init__.

        Parameters
        ----------
        qImage :
            qImage
        """
        super().__init__()

        self._resize = False
        self.setModal(True)

        title = QLabel(self)
        title.setText("Resize image canvas")

        # Main controls:
        min_val = 8
        max_val = 20000
        current_width = qImage.width()
        current_height = qImage.height()

        self._widthbox = LabeledSpinbox(self, "Width:", "New image width in pixels", min_val, current_width, max_val)
        self._heightbox = LabeledSpinbox(self, "Height:", "New image height in pixels", min_val, current_height, max_val)
        self._x_offsetbox = LabeledSpinbox(self, "X Offset:", "Distance in pixels from the left edge of the resized "
                + "canvas to the left edge of the current image content", -current_width, 0, current_width)
        self._y_offsetbox = LabeledSpinbox(self, "Y Offset:", "Distance in pixels from the top edge of the resized "
                + "canvas to the top edge of the current image content", -current_height, 0, current_height)


        # Preview widget:
        class PreviewWidget(QWidget):
            """PreviewWidget.
            """

            def __init__(prev, parent):
                """__init__.

                Parameters
                ----------
                prev :
                    prev
                parent :
                    parent
                """
                super().__init__(parent)
                prev.resizeEvent(None)

            def resizeEvent(prev, event):
                """resizeEvent.

                Parameters
                ----------
                prev :
                    prev
                event :
                    event
                """
                width = self._widthbox.spinbox.value()
                height = self._heightbox.spinbox.value()
                x_off = self._x_offsetbox.spinbox.value()
                y_off = self._y_offsetbox.spinbox.value()
                image_rect = QRect(0, 0, current_width, current_height)
                canvas_rect = QRect(-x_off, -y_off, width, height)
                full_rect = image_rect.united(canvas_rect)
                if (full_rect.x() != 0) or (full_rect.y() != 0):
                    offset = QPoint(-full_rect.x(), -full_rect.y())
                    for r in [full_rect, image_rect, canvas_rect]:
                        r.translate(offset)
                draw_area = get_scaled_placement(QRect(0, 0, prev.width(), prev.height()), full_rect.size())
                scale = draw_area.width() / full_rect.width()
                def get_draw_rect(src):
                    """get_draw_rect.

                    Parameters
                    ----------
                    src :
                        src
                    """
                    return QRect(draw_area.x() + int(src.x() * scale),
                            draw_area.y() + int (src.y() * scale),
                            int(src.width() * scale),
                            int(src.height() * scale))
                prev._image_bounds = get_draw_rect(image_rect)
                prev._canvas_bounds = get_draw_rect(canvas_rect)
                prev.update()

            def paintEvent(prev, event):
                """paintEvent.

                Parameters
                ----------
                prev :
                    prev
                event :
                    event
                """
                painter = QPainter(prev)
                linePen = QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(linePen)
                painter.fillRect(prev._canvas_bounds, Qt.darkGray)
                painter.drawImage(prev._image_bounds, qImage)
                painter.drawRect(prev._canvas_bounds)
                painter.drawRect(prev._image_bounds)
        self._preview = PreviewWidget(self)

        def on_dim_change(old_value, new_value, labeled_offsetbox):
            """on_dim_change.

            Parameters
            ----------
            old_value :
                old_value
            new_value :
                new_value
            labeled_offsetbox :
                labeled_offsetbox
            """
            labeled_offsetbox.spinbox.setRange(int(-old_value), int(old_value) + int(new_value))
            self._preview.resizeEvent(None)

        self._widthbox.spinbox.valueChanged.connect(lambda w: on_dim_change(current_width, w, self._x_offsetbox))
        self._heightbox.spinbox.valueChanged.connect(lambda h: on_dim_change(current_height, h, self._y_offsetbox))
        for offset in [self._x_offsetbox, self._y_offsetbox]:
            offset.spinbox.valueChanged.connect(lambda v: self._preview.resizeEvent(None))

        center_button = QPushButton(self)
        center_button.setText("Center")
        def center():
            """center.
            """
            width = self._widthbox.spinbox.value()
            height = self._heightbox.spinbox.value()
            x_off = (width // 2) - (current_width // 2)
            y_off = (height // 2) - (current_height // 2)
            self._x_offsetbox.spinbox.setValue(x_off)
            self._y_offsetbox.spinbox.setValue(y_off)
        center_button.clicked.connect(center)


        # Confirm / Cancel buttons:
        self._resize_button = QPushButton(self)
        self._resize_button.setText("Resize image canvas")
        def on_resize():
            """on_resize.
            """
            self._resize = True
            self.hide()
        self._resize_button.clicked.connect(on_resize)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText("Cancel")
        def on_cancel():
            """on_cancel.
            """
            self._resize = False
            self.hide()
        self._cancel_button.clicked.connect(on_cancel)

        option_bar = QWidget(self)
        option_bar.setLayout(QHBoxLayout())
        option_bar.layout().addWidget(self._cancel_button)
        option_bar.layout().addWidget(self._resize_button)
        
        self._layout = QVBoxLayout()
        ordered_widgets = [
            title,
            self._widthbox,
            self._heightbox,
            self._x_offsetbox,
            self._y_offsetbox,
            self._preview,
            center_button,
            option_bar
        ]

        for widget in ordered_widgets:
            self._layout.addWidget(widget)
        self.setLayout(self._layout)
        self.resizeEvent(None)

    def resizeEvent(self, event):
        """resizeEvent.

        Parameters
        ----------
        event :
            event
        """
        min_preview = math.ceil(min(self.width(), self.height()) * 0.8)
        self._preview.setMinimumSize(QSize(min_preview, min_preview))

    def showResizeModal(self):
        """showResizeModal.
        """
        self.exec_()
        if self._resize:
            new_size = QSize(self._widthbox.spinbox.value(), self._heightbox.spinbox.value())
            offset =  QPoint(self._x_offsetbox.spinbox.value(), self._y_offsetbox.spinbox.value())
            return new_size, offset
        return None, None
