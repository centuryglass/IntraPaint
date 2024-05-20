"""Popup modal window used for cropping or extending the edited image without scaling its contents."""
from typing import Optional
import math
from PyQt5.QtWidgets import QWidget, QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QSize, QRect, QPoint
from PyQt5.QtGui import QPainter, QPen, QImage, QResizeEvent, QPaintEvent
from ui.widget.labeled_spinbox import LabeledSpinbox
from ui.util.get_scaled_placement import get_scaled_placement

class ResizeCanvasModal(QDialog):
    """Popup modal window used for cropping or extending the edited image without scaling its contents."""

    def __init__(self, qimage: QImage) -> None:
        super().__init__()

        self._resize = False
        self.setModal(True)

        title = QLabel(self)
        title.setText('Resize image canvas')

        # Main controls:
        min_val = 8
        max_val = 20000
        current_width = qimage.width()
        current_height = qimage.height()

        self._widthbox = LabeledSpinbox(self, 'Width:', 'New image width in pixels', min_val, current_width, max_val)
        self._heightbox = LabeledSpinbox(self, 'Height:', 'New image height in pixels', min_val, current_height,
                max_val)
        self._x_offsetbox = LabeledSpinbox(self, 'X Offset:', 'Distance in pixels from the left edge of the resized '
                + 'canvas to the left edge of the current image content', -current_width, 0, current_width)
        self._y_offsetbox = LabeledSpinbox(self, 'Y Offset:', 'Distance in pixels from the top edge of the resized '
                + 'canvas to the top edge of the current image content', -current_height, 0, current_height)


        class _PreviewWidget(QWidget):
            """Shows a preview of how the image will look after the canvas is resized."""

            def __init__(self,
                    parent: Optional[QWidget],
                    widthbox: LabeledSpinbox,
                    heightbox: LabeledSpinbox,
                    x_offsetbox: LabeledSpinbox,
                    y_offsetbox: LabeledSpinbox) -> None:
                super().__init__(parent)
                self._widthbox = widthbox
                self._heightbox = heightbox
                self._x_offsetbox = x_offsetbox
                self._y_offsetbox = y_offsetbox
                self.resizeEvent(None)

            def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
                """Recalculate bounds on widget size update."""
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
                draw_area = get_scaled_placement(QRect(0, 0, self.width(), self.height()), full_rect.size())
                scale = draw_area.width() / full_rect.width()
                def get_draw_rect(src: QRect) -> QRect:
                    return QRect(draw_area.x() + int(src.x() * scale),
                            draw_area.y() + int (src.y() * scale),
                            int(src.width() * scale),
                            int(src.height() * scale))
                self._image_bounds = get_draw_rect(image_rect)
                self._canvas_bounds = get_draw_rect(canvas_rect)
                self.update()

            def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
                """Draw image with proposed changes to canvas bounds."""
                painter = QPainter(self)
                line_pen = QPen(Qt.GlobalColor.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(line_pen)
                painter.fillRect(self._canvas_bounds, Qt.darkGray)
                painter.drawImage(self._image_bounds, qimage)
                painter.drawRect(self._canvas_bounds)
                painter.drawRect(self._image_bounds)
        self._preview = _PreviewWidget(self, self._widthbox, self._heightbox, self._x_offsetbox, self._y_offsetbox)

        def _on_dim_change(old_value: int | float,
                new_value: int | float,
                labeled_offsetbox: LabeledSpinbox) -> None:
            labeled_offsetbox.spinbox.setRange(int(-old_value), int(old_value) + int(new_value))
            self._preview.resizeEvent(None)

        self._widthbox.spinbox.valueChanged.connect(lambda w: _on_dim_change(current_width, w, self._x_offsetbox))
        self._heightbox.spinbox.valueChanged.connect(lambda h: _on_dim_change(current_height, h, self._y_offsetbox))
        for offset in [self._x_offsetbox, self._y_offsetbox]:
            offset.spinbox.valueChanged.connect(lambda v: self._preview.resizeEvent(None))

        center_button = QPushButton(self)
        center_button.setText('Center')
        def center() -> None:
            width = self._widthbox.spinbox.value()
            height = self._heightbox.spinbox.value()
            x_off = (width // 2) - (current_width // 2)
            y_off = (height // 2) - (current_height // 2)
            self._x_offsetbox.spinbox.setValue(x_off)
            self._y_offsetbox.spinbox.setValue(y_off)
        center_button.clicked.connect(center)


        # Confirm / Cancel buttons:
        self._resize_button = QPushButton(self)
        self._resize_button.setText('Resize image canvas')
        def on_resize() -> None:
            self._resize = True
            self.hide()
        self._resize_button.clicked.connect(on_resize)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText('Cancel')
        def on_cancel() -> None:
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


    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Recalculate preview bounds on resize."""
        min_preview = math.ceil(min(self.width(), self.height()) * 0.8)
        self._preview.setMinimumSize(QSize(min_preview, min_preview))


    def show_resize_modal(self) -> tuple[QSize, QPoint] | tuple[None, None]:
        """Show this modal, returning QSize new_size and QPoint offset if changes are confirmed."""
        self.exec_()
        if self._resize:
            new_size = QSize(self._widthbox.spinbox.value(), self._heightbox.spinbox.value())
            offset =  QPoint(self._x_offsetbox.spinbox.value(), self._y_offsetbox.spinbox.value())
            return new_size, offset
        return None, None
