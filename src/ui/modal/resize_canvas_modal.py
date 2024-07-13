"""Popup modal window used for cropping or extending the edited image without scaling its contents."""
from typing import Optional
import math
from PyQt6.QtWidgets import QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QSize, QRect, QPoint
from PyQt6.QtGui import QPainter, QPen, QImage, QResizeEvent, QPaintEvent
from src.ui.widget.labeled_spinbox import LabeledSpinbox
from src.util.geometry_utils import get_scaled_placement

WINDOW_TITLE = 'Resize image canvas'
MIN_PX_VALUE = 8
MAX_PX_VALUE = 20000
WIDTH_LABEL = 'Width:'
WIDTH_TOOLTIP = 'New image width in pixels'
HEIGHT_LABEL = 'Height:'
HEIGHT_TOOLTIP = 'New image height in pixels'
X_OFFSET_LABEL = 'X Offset:'
X_OFFSET_TOOLTIP = ('Distance in pixels from the left edge of the resized canvas to the left edge of the current image '
                    'content')
Y_OFFSET_LABEL = 'Y Offset:'
Y_OFFSET_TOOLTIP = ('Distance in pixels from the top edge of the resized canvas to the top edge of the current image '
                    'content')
CENTER_BUTTON_LABEL = 'Center'
CANCEL_BUTTON_LABEL = 'Cancel'
RESIZE_BUTTON_LABEL = 'Resize image canvas'


class ResizeCanvasModal(QDialog):
    """Popup modal window used for cropping or extending the edited image without scaling its contents."""

    def __init__(self, qimage: QImage) -> None:
        super().__init__()

        self._resize = False
        self.setModal(True)
        self.setWindowTitle(WINDOW_TITLE)

        # Main controls:
        self._image = qimage
        current_width = qimage.width()
        current_height = qimage.height()

        self._width_box = LabeledSpinbox(self, WIDTH_LABEL, WIDTH_TOOLTIP, MIN_PX_VALUE, current_width, MAX_PX_VALUE)
        self._height_box = LabeledSpinbox(self, HEIGHT_LABEL, HEIGHT_TOOLTIP, MIN_PX_VALUE, current_height,
                                          MAX_PX_VALUE)
        self._x_offset_box = LabeledSpinbox(self, X_OFFSET_LABEL, X_OFFSET_TOOLTIP
                                            + '', -current_width, 0,
                                            current_width)
        self._y_offset_box = LabeledSpinbox(self, Y_OFFSET_LABEL, Y_OFFSET_TOOLTIP, -current_height, 0,
                                            current_height)

        self._preview = _PreviewWidget(self, qimage, self._width_box, self._height_box, self._x_offset_box,
                                       self._y_offset_box)

        def _on_dim_change(old_value: int | float,
                           new_value: int | float,
                           labeled_offset_box: LabeledSpinbox) -> None:
            """Adjust offset box ranges when width/height change."""
            labeled_offset_box.spinbox.setRange(int(-old_value), int(old_value) + int(new_value))
            self._preview.resizeEvent(None)

        self._width_box.spinbox.valueChanged.connect(lambda w: _on_dim_change(current_width, w, self._x_offset_box))
        self._height_box.spinbox.valueChanged.connect(lambda h: _on_dim_change(current_height, h, self._y_offset_box))
        for offset in [self._x_offset_box, self._y_offset_box]:
            offset.spinbox.valueChanged.connect(lambda v: self._preview.resizeEvent(None))

        center_button = QPushButton(self)
        center_button.setText(CENTER_BUTTON_LABEL)

        def center() -> None:
            """Adjust offsets to center existing image content in the canvas."""
            width = self._width_box.spinbox.value()
            height = self._height_box.spinbox.value()
            x_off = (width // 2) - (current_width // 2)
            y_off = (height // 2) - (current_height // 2)
            self._x_offset_box.spinbox.setValue(x_off)
            self._y_offset_box.spinbox.setValue(y_off)

        center_button.clicked.connect(center)

        self._resize_button = QPushButton(self)
        self._resize_button.setText(RESIZE_BUTTON_LABEL)
        self._resize_button.clicked.connect(self._confirm)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setText(CANCEL_BUTTON_LABEL)
        self._cancel_button.clicked.connect(self._cancel)

        option_bar = QWidget(self)
        layout = QHBoxLayout(option_bar)
        layout.addWidget(self._cancel_button)
        layout.addWidget(self._resize_button)

        self._layout = QVBoxLayout()
        ordered_widgets = [
            self._width_box,
            self._height_box,
            self._x_offset_box,
            self._y_offset_box,
            self._preview,
            center_button,
            option_bar
        ]

        for widget in ordered_widgets:
            self._layout.addWidget(widget)
        self.setLayout(self._layout)
        self.resizeEvent(None)

    def _confirm(self) -> None:
        self._resize = True
        self.hide()

    def _cancel(self) -> None:
        self._resize = False
        self.hide()

    def _center(self) -> None:
        """Adjust offsets to center existing image content in the canvas."""
        current_width = self._image.width()
        current_height = self._image.height()
        width = self._width_box.spinbox.value()
        height = self._height_box.spinbox.value()
        x_off = (width // 2) - (current_width // 2)
        y_off = (height // 2) - (current_height // 2)
        self._x_offset_box.spinbox.setValue(x_off)
        self._y_offset_box.spinbox.setValue(y_off)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Recalculate preview bounds on resize."""
        min_preview = math.ceil(min(self.width(), self.height()) * 0.8)
        self._preview.setMinimumSize(QSize(min_preview, min_preview))

    def show_resize_modal(self) -> tuple[QSize, QPoint] | tuple[None, None]:
        """Show this modal, returning QSize new_size and QPoint offset if changes are confirmed."""
        self.exec()
        if self._resize:
            new_size = QSize(self._width_box.spinbox.value(), self._height_box.spinbox.value())
            offset = QPoint(self._x_offset_box.spinbox.value(), self._y_offset_box.spinbox.value())
            return new_size, offset
        return None, None


class _PreviewWidget(QWidget):
    """Shows a preview of how the image will look after the canvas is resized."""

    def __init__(self,
                 parent: Optional[QWidget],
                 image: QImage,
                 width_box: LabeledSpinbox,
                 height_box: LabeledSpinbox,
                 x_offset_box: LabeledSpinbox,
                 y_offset_box: LabeledSpinbox) -> None:
        super().__init__(parent)
        self._qimage = image
        self._image_bounds: Optional[QRect] = None
        self._canvas_bounds: Optional[QRect] = None
        self._width_box = width_box
        self._height_box = height_box
        self._x_offset_box = x_offset_box
        self._y_offset_box = y_offset_box
        self.resizeEvent(None)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Recalculate bounds on widget size update."""
        width = self._width_box.spinbox.value()
        height = self._height_box.spinbox.value()
        x_off = self._x_offset_box.spinbox.value()
        y_off = self._y_offset_box.spinbox.value()
        current_width = self._qimage.width()
        current_height = self._qimage.height()
        image_rect = QRect(0, 0, current_width, current_height)
        canvas_rect = QRect(-x_off, -y_off, width, height)
        full_rect = image_rect.united(canvas_rect)
        if (full_rect.x() != 0) or (full_rect.y() != 0):
            rect_offset = QPoint(-full_rect.x(), -full_rect.y())
            for r in [full_rect, image_rect, canvas_rect]:
                r.translate(rect_offset)
        draw_area = get_scaled_placement(self.size(), full_rect.size())
        scale = draw_area.width() / full_rect.width()

        def get_draw_rect(src: QRect) -> QRect:
            """Converts full image coordinates to preview drawing coordinates."""
            return QRect(draw_area.x() + int(src.x() * scale),
                         draw_area.y() + int(src.y() * scale),
                         int(src.width() * scale),
                         int(src.height() * scale))

        self._image_bounds = get_draw_rect(image_rect)
        self._canvas_bounds = get_draw_rect(canvas_rect)
        self.update()

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draw image with proposed changes to canvas bounds."""
        if self._canvas_bounds is None:
            return
        painter = QPainter(self)
        line_pen = QPen(Qt.GlobalColor.black, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                        Qt.PenJoinStyle.RoundJoin)
        painter.setPen(line_pen)
        painter.fillRect(self._canvas_bounds, Qt.GlobalColor.darkGray)
        if self._image_bounds is not None:
            painter.drawImage(self._image_bounds, self._qimage)
            painter.drawRect(self._canvas_bounds)
            painter.drawRect(self._image_bounds)
