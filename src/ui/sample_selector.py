"""
Provides an interface for choosing between AI-generated changes to selected image content.
"""
import gc
import math
from typing import Callable, Optional, Any, List, cast

from PIL import Image
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, QEvent
from PyQt5.QtGui import QPainter, QPen, QPixmap, QPaintEvent, QResizeEvent, QKeyEvent, QWheelEvent, QMouseEvent
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.ui.util.contrast_color import contrast_color
from src.ui.util.equal_margins import get_equal_margins
from src.ui.util.get_scaled_placement import get_scaled_placement
from src.ui.widget.loading_widget import LoadingWidget
from src.util.image_utils import pil_image_to_qimage


class SampleSelector(QWidget):
    """Shows all inpainting samples as they load, allows the user to select one or discard all of them."""

    def __init__(self,
                 config: AppConfig,
                 layer_stack: LayerStack,
                 mask: Image.Image,
                 close_selector: Callable,
                 make_selection: Callable[[Optional[Image.Image]], None]):
        super().__init__()

        self._left_arrow_bounds = None
        self._right_arrow_bounds = None
        self._config = config
        self._make_selection = make_selection

        source_image = layer_stack.pil_image_selection_content()

        self._source_pixmap = QPixmap.fromImage(pil_image_to_qimage(source_image))
        self._mask_pixmap = QPixmap.fromImage(pil_image_to_qimage(mask))
        self._source_image_bounds = QRect(0, 0, 0, 0)
        self._mask_image_bounds = QRect(0, 0, 0, 0)
        self._include_original = config.get(AppConfig.SHOW_ORIGINAL_IN_OPTIONS)
        self._source_option_bounds = None
        self._zoom_image_bounds = None

        self._expected_count = config.get(AppConfig.BATCH_COUNT) * config.get(AppConfig.BATCH_SIZE)
        self._image_size = QSize(source_image.width, source_image.height)
        self._zoom_mode = False
        self._zoom_index = 0
        self._options: List[dict[str, Any]] = []
        while len(self._options) < self._expected_count:
            self._options.append({'image': None, 'pixmap': None, 'bounds': None})

        self._instructions = QLabel('Click a sample to apply it to the source image, or click "cancel" to discard all'
                                    ' samples.', self)
        self._instructions.show()
        if (self._expected_count > 1) or self._include_original:
            self._zoom_button = QPushButton(self)
            self._zoom_button.setText('Zoom in')
            self._zoom_button.clicked.connect(self.toggle_zoom)
            self._zoom_button.show()
        else:
            self._zoom_button = None
        self._cancel_button = QPushButton(self)
        self._cancel_button.setText('Cancel')
        self._cancel_button.clicked.connect(close_selector)
        self._cancel_button.show()

        self._is_loading = False
        self._loading_widget = LoadingWidget()
        self._loading_widget.setParent(self)
        self._loading_widget.setGeometry(self.frameGeometry())
        self._loading_widget.hide()
        self.resizeEvent(None)

        def free_memory_and_close():
            """Explicitly discard unused image data when the sample selector closes."""
            del self._source_pixmap
            self._source_pixmap = None
            del self._mask_pixmap
            self._mask_pixmap = None
            for option in self._options:
                if option['image'] is not None:
                    del option['image']
                    option['image'] = None
                if option['pixmap'] is not None:
                    del option['pixmap']
                    option['pixmap'] = None
            gc.collect()
            close_selector()

        self._close_selector = free_memory_and_close

    def toggle_zoom(self, index: int = -1):
        """Switch between showing all options and zooming in on a single option."""
        if self._zoom_button is None:
            return
        if self._zoom_mode:
            self._zoom_button.setText('Zoom in')
            self._zoom_mode = False
        else:
            self._zoom_button.setText('Zoom out')
            self._zoom_mode = True
            if isinstance(index, int) and 0 < index < self._option_count():
                self._zoom_index = index
            else:
                self._zoom_index = 0
        self.resizeEvent(None)
        self.update()

    def set_is_loading(self, is_loading: bool, message: Optional[str] = None):
        """Show or hide the loading indicator"""
        if is_loading:
            self._loading_widget.show()
            if message:
                self._loading_widget.set_message(message)
            else:
                self._loading_widget.set_message('Loading images')
        else:
            self._loading_widget.hide()
        self._is_loading = is_loading
        self.update()

    def set_loading_message(self, message: str):
        """Updates loading message text while waiting for generated image options."""
        self._loading_widget.set_message(message)

    def load_sample_image(self, image_sample: Image.Image, idx: int):
        """
        Loads an inpainting sample image into the appropriate SampleWidget.
        Parameters:
        -----------
        image_sample : Image
            Newly generated inpainting image sample.
        idx : int
            Index of the image sample
        """
        pixmap = QPixmap.fromImage(pil_image_to_qimage(image_sample))
        assert pixmap is not None
        if idx >= len(self._options):
            self._options.append({'image': image_sample, 'pixmap': pixmap})
            self.resizeEvent(None)
        else:
            self._options[idx]['pixmap'] = pixmap
            self._options[idx]['image'] = image_sample
        self.update()

    def resizeEvent(self, unused_event: Optional[QResizeEvent]):
        """Recalculate all bounds on resize."""
        status_area = QRect(0, 0, self.width(), self.height() // 8)
        self._source_image_bounds = get_scaled_placement(status_area, self._image_size, 5)
        self._source_image_bounds.moveLeft(status_area.x() + 10)
        self._mask_image_bounds = QRect(self._source_image_bounds.right() + 5,
                                        self._source_image_bounds.y(),
                                        self._source_image_bounds.width(),
                                        self._source_image_bounds.height())

        loading_widget_size = int(status_area.height() * 1.2)
        loading_bounds = QRect(self.width() // 2 - loading_widget_size // 2, 0,
                               loading_widget_size, loading_widget_size)
        self._loading_widget.setGeometry(loading_bounds)

        text_area = QRect(self._mask_image_bounds.right(),
                          status_area.y(),
                          int((status_area.width() - self._mask_image_bounds.right()) * 0.8),
                          status_area.height()).marginsRemoved(get_equal_margins(4))
        self._instructions.setGeometry(text_area)
        zoom_area = QRect(text_area.right(), status_area.y(),
                          (status_area.width() - text_area.right()) // 2,
                          status_area.height()).marginsRemoved(get_equal_margins(10))
        if zoom_area.height() > zoom_area.width():
            zoom_area.setHeight(max(zoom_area.width(), status_area.height() // 3))
            zoom_area.setY(status_area.y() + (status_area.height() // 4) - (zoom_area.height() // 2))
            cancel_area = QRect(zoom_area.left(),
                                status_area.bottom() - (status_area.height() // 4) - (zoom_area.height() // 2),
                                zoom_area.width(),
                                zoom_area.height())
            self._cancel_button.setGeometry(cancel_area)
        else:
            cancel_area = QRect(zoom_area.left() + zoom_area.width(), status_area.y(),
                                (status_area.width() - zoom_area.right()),
                                status_area.height()).marginsRemoved(get_equal_margins(10))
            self._cancel_button.setGeometry(cancel_area)
        if self._zoom_button is not None:
            self._zoom_button.setGeometry(zoom_area)

        option_count = self._option_count()
        option_area = QRect(0, status_area.height(), self.width(), self.height() - status_area.height())
        if self._zoom_mode:
            # Make space on sides for arrows:
            arrow_size = max(self.width() // 70, 8)
            arrow_margin = arrow_size // 2
            option_area.setLeft(option_area.left() + arrow_size + (arrow_margin * 2))
            option_area.setRight(option_area.right() - arrow_size - (arrow_margin * 2))
            self._zoom_image_bounds = get_scaled_placement(option_area, self._image_size, 2)

            arrow_top = option_area.y() + (option_area.height() // 2) - (arrow_size // 2)
            self._left_arrow_bounds = QRect(option_area.left() - (arrow_size + arrow_margin), arrow_top, arrow_size,
                                            arrow_size)
            self._right_arrow_bounds = QRect(option_area.x() + option_area.width() + arrow_margin, arrow_top,
                                             arrow_size, arrow_size)
        else:
            margin = 10

            def get_scale_factor_for_row_count(row_count: int):
                """Returns the largest image scale multiplier possible to fit images within row_count rows."""
                column_count = math.ceil(option_count / row_count)
                img_bounds = QRect(0, 0, option_area.width() // column_count, option_area.height() // row_count)
                img_rect = get_scaled_placement(img_bounds, self._image_size, margin)
                return img_rect.width() / self._image_size.width()

            num_rows = 1
            best_scale = 0
            for i in range(1, option_count + 1):
                scale = get_scale_factor_for_row_count(i)
                last_scale = scale
                if scale > best_scale:
                    best_scale = scale
                    num_rows = i
                elif scale < last_scale:
                    break
            num_columns = math.ceil(option_count / num_rows)
            row_size = option_area.height() // num_rows
            column_size = option_area.width() // num_columns
            for idx in range(option_count):
                row = idx // num_columns
                col = idx % num_columns
                x = column_size * col
                y = option_area.y() + row_size * row
                container_rect = QRect(x, y, column_size, row_size)
                if idx >= len(self._options):
                    self._source_option_bounds = get_scaled_placement(container_rect, self._image_size, 10)
                else:
                    self._options[idx]['bounds'] = get_scaled_placement(container_rect, self._image_size, 10)

    def paintEvent(self, event: Optional[QPaintEvent]):
        """Draw all generated image options within the widget."""
        super().paintEvent(event)
        line_color = contrast_color(self)
        painter = QPainter(self)
        if self._source_pixmap is not None:
            painter.drawPixmap(self._source_image_bounds, self._source_pixmap)
        if self._mask_pixmap is not None:
            painter.drawPixmap(self._mask_image_bounds, self._mask_pixmap)
        painter.setPen(QPen(line_color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

        def draw_image(image_option):
            """Draw one of the image options into the widget, or draw a placeholder section if it's still loading."""
            painter.setPen(QPen(line_color, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawRect(image_option['bounds'].marginsAdded(get_equal_margins(2)))
            if ('pixmap' in image_option) and (image_option['pixmap'] is not None):
                painter.drawPixmap(image_option['bounds'], image_option['pixmap'])
            else:
                painter.fillRect(image_option['bounds'], Qt.black)
                painter.setPen(QPen(line_color, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.drawText(image_option['bounds'], Qt.AlignCenter, 'Waiting for image...')

        if self._zoom_mode:
            if self._zoom_index >= len(self._options):
                pixmap = self._source_pixmap
            else:
                pixmap = self._options[self._zoom_index]['pixmap']
            draw_image({'bounds': self._zoom_image_bounds, 'pixmap': pixmap})

            # draw arrows:
            def draw_arrow(arrow_bounds: QRect, pts: list, text: str):
                """Draw the 'next image'/'previous image' buttons when zoomed in."""
                painter.setPen(QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                text_bounds = QRect(arrow_bounds)
                text_bounds.moveTop(text_bounds.top() - text_bounds.height())
                bg_bounds = QRect(arrow_bounds)
                bg_bounds.setTop(text_bounds.top())
                # Arrow background:
                painter.fillRect(bg_bounds.marginsAdded(get_equal_margins(4)), Qt.white)
                # Arrow:
                painter.drawLine(pts[0], pts[1])
                painter.drawLine(pts[1], pts[2])
                painter.drawLine(pts[0], pts[2])
                # Index labels:
                painter.drawText(text_bounds, Qt.AlignCenter, text)

            max_idx = self._option_count() - 1
            prev_idx = max_idx if (self._zoom_index == 0) else (self._zoom_index - 1)
            next_idx = 0 if (self._zoom_index >= max_idx) else (self._zoom_index + 1)
            left_mid = QPoint(self._left_arrow_bounds.left(), self._left_arrow_bounds.top()
                              + self._left_arrow_bounds.width() // 2)
            right_mid = QPoint(self._right_arrow_bounds.left() + self._right_arrow_bounds.width(),
                               self._right_arrow_bounds.top() + self._right_arrow_bounds.width() // 2)
            draw_arrow(self._left_arrow_bounds,
                       [left_mid, self._left_arrow_bounds.topRight(), self._left_arrow_bounds.bottomRight()],
                       str(prev_idx + 1))
            draw_arrow(self._right_arrow_bounds,
                       [right_mid, self._right_arrow_bounds.topLeft(), self._right_arrow_bounds.bottomLeft()],
                       str(next_idx + 1))

            # write current index centered over the image:
            index_dim = self._right_arrow_bounds.width()
            index_left = int(self._zoom_image_bounds.x() + (self._zoom_image_bounds.width() / 2) + (index_dim / 2))
            index_top = int(self._zoom_image_bounds.y() - index_dim - 8)
            index_bounds = QRect(index_left, index_top, index_dim, index_dim)
            painter.fillRect(index_bounds, Qt.white)
            painter.drawText(index_bounds, Qt.AlignCenter, str(self._zoom_index + 1))

        else:
            for option in self._options:
                draw_image(option)
            if self._source_option_bounds is not None:
                option = {'bounds': self._source_option_bounds, 'pixmap': self._source_pixmap}
                draw_image(option)

    def _option_count(self) -> int:
        return max(len(self._options), self._expected_count) + (1 if self._include_original else 0)

    def _zoom_prev(self):
        if self._zoom_mode:
            self._zoom_index = (self._option_count() - 1) if self._zoom_index <= 0 else (self._zoom_index - 1)
            self.resizeEvent(None)
            self.update()
        else:
            self.toggle_zoom(self._option_count() - 1)

    def _zoom_next(self):
        if self._zoom_mode:
            self._zoom_index = 0 if self._zoom_index >= (self._option_count() - 1) else (self._zoom_index + 1)
            self.resizeEvent(None)
            self.update()
        else:
            self.toggle_zoom(0)

    def _handle_key_event(self, event: Optional[QKeyEvent]):
        if event is None:
            return
        toggle_zoom = False
        zoom_index = None

        def key_index():
            """Get the image index for a numeric key code."""
            return int(event.text()) - 1

        match event.key():
            case Qt.Key_Escape:
                if self._zoom_mode:
                    toggle_zoom = True
                else:
                    self._make_selection(None)
                    self._close_selector()
            case Qt.Key_Return | Qt.Key_Enter if self._zoom_mode:
                if self._zoom_index >= len(self._options):
                    # Original selected, just close selector
                    self._make_selection(None)
                    self._close_selector()
                else:
                    option = self._options[self._zoom_index]
                    if isinstance(option['image'], Image.Image):
                        self._make_selection(option['image'])
                        self._close_selector()
                return True
            case Qt.Key_0 | Qt.Key_1 | Qt.Key_2 | Qt.Key_3 | Qt.Key_4 | Qt.Key_5 | Qt.Key_6 | Qt.Key_7 | Qt.Key_8 \
                    | Qt.Key_9 if key_index() < self._option_count():
                if not self._zoom_mode or key_index() == self._zoom_index:
                    toggle_zoom = True
                zoom_index = key_index()
            # Allow both gaming-style (WASD) and Vim-style (hjkl) navigation:
            case Qt.Key_H | Qt.Key_A if self._zoom_mode:
                self._zoom_prev()
            case Qt.Key_L | Qt.Key_D if self._zoom_mode:
                self._zoom_next()
            case Qt.Key_K | Qt.Key_W if self._zoom_mode:
                toggle_zoom = True
            case Qt.Key_J | Qt.Key_S:
                toggle_zoom = True
            case _:
                return False

        if toggle_zoom:
            self.toggle_zoom(zoom_index)
        elif self._zoom_mode and zoom_index is not None and zoom_index >= 0:
            self._zoom_index = zoom_index
            self.resizeEvent(None)
            self.update()
        return True

    def eventFilter(self, source, event: QEvent):
        """Intercept mouse wheel events, use for scrolling in zoom mode:"""
        if not self.isVisible():
            return super().eventFilter(source, event)
        match event.type():
            case QEvent.Wheel:
                event = cast(QWheelEvent, event)
                if event.angleDelta().y() > 0:
                    self._zoom_next()
                elif event.angleDelta().y() < 0:
                    self._zoom_prev()
                return True
            case QEvent.KeyPress:
                return self._handle_key_event(cast(QKeyEvent, event))
        return super().eventFilter(source, event)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle image selection and arrow button clicks."""
        if event.button() != Qt.LeftButton:
            return
        if self._zoom_mode:
            max_idx = max(len(self._options), self._expected_count) - (0 if self._include_original else 1)
            # Check for arrow clicks:
            if self._left_arrow_bounds.contains(event.pos()):
                self._zoom_prev()
            elif self._right_arrow_bounds.contains(event.pos()):
                self._zoom_next()
            elif self._zoom_image_bounds.contains(event.pos()) and not self._is_loading:
                if self._include_original and self._zoom_index == max_idx:
                    # Original chosen, no need to change anything besides applying sketch:
                    self._make_selection(None)
                    self._close_selector()
                else:
                    option = self._options[self._zoom_index]
                    if isinstance(option['image'], Image.Image):
                        self._make_selection(option['image'])
                        self._close_selector()
        elif not self._is_loading:
            if self._include_original and self._source_option_bounds is not None:
                if self._source_option_bounds.contains(event.pos()):  # Original image chosen
                    self._make_selection(None)
                    self._close_selector()
                    return
            for option in self._options:
                if option['bounds'].contains(event.pos()) and isinstance(option['image'], Image.Image):
                    self._make_selection(option['image'])
                    self._close_selector()
                    return
