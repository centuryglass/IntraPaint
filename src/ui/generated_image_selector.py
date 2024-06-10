"""
Provides an interface for choosing between AI-generated changes to selected image content.
"""
import math
import time
from typing import Callable, Optional, cast, List

from PIL import Image
from PyQt5.QtCore import Qt, QRect, QSize, QPoint, QSizeF, QRectF, QEvent, pyqtSignal
from PyQt5.QtGui import QImage, QResizeEvent, QPixmap, QPainter, QWheelEvent, QMouseEvent, \
    QPainterPath, QKeyEvent
from PyQt5.QtWidgets import QWidget, QGraphicsPixmapItem, QVBoxLayout, QLabel, \
    QStyleOptionGraphicsItem, QHBoxLayout, QPushButton, QStyle, QApplication

from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.ui.graphics_items.loading_spinner import LoadingSpinner
from src.ui.graphics_items.outline import Outline
from src.ui.util.geometry_utils import get_scaled_placement
from src.ui.util.text import max_font_size
from src.ui.widget.image_graphics_view import ImageGraphicsView
from src.util.image_utils import get_standard_qt_icon
from src.util.key_code_utils import get_key_display_string
from src.util.validation import assert_valid_index


CANCEL_BUTTON_TEXT = 'Cancel'
CANCEL_BUTTON_TOOLTIP = 'This will discard all generated images.'
PREVIOUS_BUTTON_TEXT = 'Previous'
ZOOM_BUTTON_TEXT = 'Toggle zoom'
NEXT_BUTTON_TEXT = 'Next'


ORIGINAL_CONTENT_LABEL = "Original image content"
LOADING_IMG_TEXT = 'Loading...'

SELECTION_TITLE = 'Select from generated image options.'
VIEW_MARGIN = 6
IMAGE_MARGIN_FRACTION = 1/6
SCROLL_DEBOUNCE_MS = 100

DEFAULT_CONTROL_HINT = 'Ctrl+LMB or MMB and drag: pan view, mouse wheel: zoom, Esc: discard all options'
ZOOM_CONTROL_HINT = ('Ctrl+LMB or MMB and drag: pan view, mouse wheel: zoom, Enter: select option, Esc: return to full'
                     ' view')

VIEW_BACKGROUND = Qt.GlobalColor.black


class GeneratedImageSelector(QWidget):
    """Shows all images from an image generation operation, allows the user to select one or discard all of them."""

    def __init__(self,
                 config: AppConfig,
                 layer_stack: LayerStack,
                 mask: Image.Image,
                 close_selector: Callable,
                 make_selection: Callable[[Optional[Image.Image]], None]) -> None:
        super().__init__(None)
        self._config = config
        self._layer_stack = layer_stack
        self._mask = mask
        self._close_selector = close_selector
        self._make_selection = make_selection
        self._options: List[_ImageOption] = []
        self._outlines: List[Outline] = []
        self._zoomed_in = False
        self._zoom_index = 0
        self._last_scroll_time = time.time() * 1000

        self._base_option_offset = QPoint(0, 0)
        self._base_option_scale = 0.0
        self._option_scale_offset = 0.0
        self._option_pos_offset = QPoint(0, 0)

        self._layout = QVBoxLayout(self)
        self._page_top_label = QLabel(SELECTION_TITLE)
        self._page_top_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self._page_top_label)

        # Setup main option view widget:
        self._view = _SelectionView(config)
        self._view.scale_changed.connect(self._scale_change_slot)
        self._view.offset_changed.connect(self._offset_change_slot)

        self._view.installEventFilter(self)

        def _selection_scroll(dx, dy):
            if dx > 0:
                self._zoom_next()
            elif dx < 0:
                self._zoom_prev()
            if dy != 0 and (dy > 0) == self._zoomed_in:
                self.toggle_zoom()
        self._view.content_scrolled.connect(_selection_scroll)
        self._view.zoom_toggled.connect(self.toggle_zoom)

        self._layout.addWidget(self._view, stretch=255)
        self._loading_spinner = LoadingSpinner()
        self._loading_spinner.setZValue(1)
        self._loading_spinner.visible = False
        self._view.scene().addItem(self._loading_spinner)

        original_image = self._layer_stack.qimage_selection_content()
        original_option = _ImageOption(original_image, ORIGINAL_CONTENT_LABEL)
        self._view.scene().addItem(original_option)
        self._options.append(original_option)
        self._outlines.append(Outline(self._view.scene(), self._view))
        self._outlines[0].outlined_region = self._options[0].bounds

        # Add initial images, placeholders for expected images:
        self._loading_image = QImage(original_image.size(), QImage.Format_ARGB32_Premultiplied)
        self._loading_image.fill(Qt.GlobalColor.black)
        painter = QPainter(self._loading_image)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(QRect(0, 0, self._loading_image.width(), self._loading_image.height()), Qt.AlignCenter,
                         LOADING_IMG_TEXT)

        expected_count = config.get(AppConfig.BATCH_SIZE) * config.get(AppConfig.BATCH_COUNT)
        for i in range(expected_count):
            self.add_image_option(self._loading_image, i)

        self._button_bar = QWidget()
        self._layout.addWidget(self._button_bar)
        self._button_bar_layout = QHBoxLayout(self._button_bar)

        self._cancel_button = QPushButton()
        self._cancel_button.setIcon(get_standard_qt_icon(QStyle.SP_DialogCancelButton))
        self._cancel_button.setText(CANCEL_BUTTON_TEXT)
        self._cancel_button.setToolTip(CANCEL_BUTTON_TOOLTIP)
        self._cancel_button.clicked.connect(self._close_selector)
        self._button_bar_layout.addWidget(self._cancel_button)

        self._button_bar_layout.addStretch(255)

        self._status_label = QLabel(DEFAULT_CONTROL_HINT)
        self._button_bar_layout.addWidget(self._status_label)
        self._button_bar_layout.addStretch(255)

        def _add_key_hint(button, config_key):
            keys = config.get_keycodes(config_key)
            button.setText(f'{button.text()} [{get_key_display_string(keys)}]')

        self._prev_button = QPushButton()
        self._prev_button.setIcon(get_standard_qt_icon(QStyle.SP_ArrowLeft))
        self._prev_button.setText(PREVIOUS_BUTTON_TEXT)
        self._prev_button.clicked.connect(self._zoom_prev)
        _add_key_hint(self._prev_button, AppConfig.MOVE_LEFT)
        self._button_bar_layout.addWidget(self._prev_button)

        self._zoom_button = QPushButton()
        self._zoom_button.setText(ZOOM_BUTTON_TEXT)
        self._zoom_button.clicked.connect(self.toggle_zoom)
        _add_key_hint(self._zoom_button, AppConfig.ZOOM_TOGGLE)
        self._button_bar_layout.addWidget(self._zoom_button)

        self._next_button = QPushButton()
        self._next_button.setIcon(get_standard_qt_icon(QStyle.SP_ArrowRight))
        self._next_button.setText(NEXT_BUTTON_TEXT)
        self._next_button.clicked.connect(self._zoom_next)
        _add_key_hint(self._next_button, AppConfig.MOVE_RIGHT)
        self._button_bar_layout.addWidget(self._next_button)

    def set_is_loading(self, is_loading: bool, message: Optional[str] = None):
        """Show or hide the loading indicator"""
        if message is not None:
            self._loading_spinner.message = message
        self._loading_spinner.visible = is_loading

    def set_loading_message(self, message: str) -> None:
        """Changes the loading spinner message."""
        self._loading_spinner.message = message

    def add_image_option(self, image: QImage, idx: int) -> None:
        """Add an image to the list of generated image options."""
        if not 0 <= idx < len(self._options):
            raise IndexError(f'invalid index {idx}, max is {len(self._options)}')
        idx += 1  # Original image gets index zero
        if idx == len(self._options):
            self._options.append(_ImageOption(image, f'Option {idx}'))
            self._view.scene().addItem(self._options[-1])
            self._outlines.append(Outline(self._view.scene(), self._view))
        else:
            self._options[idx].image = image
        # Image options might come back at a different size if generation size doesn't match edit size, make
        # sure they're all displayed the same:
        size = self._options[idx].size
        original_size = self._options[0].size
        assert size == original_size, f'Expected images to be {original_size}, got {size}'
        self._outlines[idx].outlined_region = self._options[idx].bounds
        self.resizeEvent(None)

    def toggle_zoom(self, zoom_index: Optional[int] = None) -> None:
        """Toggle between zoomin in on one option and showing all of them."""
        if zoom_index is not None:
            self._zoom_index = zoom_index
        self._zoomed_in = not self._zoomed_in
        if self._zoomed_in:
            self._zoom_to_option(self._zoom_index)
        else:
            if not self._scroll_debounce_finished():
                return
            self._view.reset_scale()
            self._option_pos_offset = QPoint(0, 0)
            self._option_scale_offset = 0.0
            for option in self._options:
                option.setOpacity(1.0)
            self._status_label.setText(DEFAULT_CONTROL_HINT)
            self._page_top_label.setText(SELECTION_TITLE)
        self.resizeEvent(None)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]):
        """Recalculate all bounds on resize and update view scale."""
        self._apply_ideal_image_arrangement()

    def eventFilter(self, source, event: QEvent):
        """Use horizontal scroll to move through selections, select items when clicked."""
        if event.type() == QEvent.Wheel:
            event = cast(QWheelEvent, event)
            if event.angleDelta().x() > 0:
                self._zoom_next()
            elif event.angleDelta().x() < 0:
                self._zoom_prev()
            return event.angleDelta().x() != 0
        elif event.type() == QEvent.KeyPress:
            event = cast(QKeyEvent, event)
            if event.key() == Qt.Key_Escape:
                if self._zoomed_in:
                    self.toggle_zoom()
                else:
                    self._close_selector()
            elif event.key() == Qt.Key_Enter and self._zoomed_in:
                self._select_option(self._zoom_index)
            else:
                return False
            return True
        elif event.type() == QEvent.MouseButtonPress:
            if QApplication.keyboardModifiers() == Qt.ControlModifier:
                return False  # Ctrl+click is for panning, don't select options
            event = cast(QMouseEvent, event)
            if event.button() != Qt.LeftButton or self._loading_spinner.visible:
                return False
            if source == self._view:
                view_pos = event.pos()
            else:
                view_pos = QPoint(self._view.x() + event.pos().x(), self._view.y() + event.pos().y())
            scene_pos = self._view.mapToScene(view_pos).toPoint()
            for i in range(len(self._options)):
                if self._options[i].bounds.contains(scene_pos):
                    self._select_option(i)
        return False

    def _offset_change_slot(self, offset: QPoint) -> None:
        if not self._zoomed_in:
            return
        self._option_pos_offset = offset - self._base_option_offset

    def _scale_change_slot(self, scale: float) -> None:
        if not self._zoomed_in:
            return
        self._option_scale_offset = scale - self._base_option_scale

    def _select_option(self, option_index: int) -> None:
        if option_index == 0:  # Original image, no changes needed:
            self._make_selection(None)
        else:
            self._make_selection(self._options[option_index].image)
        self._close_selector()

    def _scroll_debounce_finished(self) -> bool:
        ms_time = time.time() * 1000
        if ms_time > self._last_scroll_time + SCROLL_DEBOUNCE_MS:
            self._last_scroll_time = ms_time
            return True
        return False

    def _zoom_to_option(self, option_index: int) -> None:
        assert_valid_index(option_index, self._options)
        if not self._scroll_debounce_finished():
            return
        if not self._zoomed_in:
            self._zoomed_in = True
        self._zoom_index = option_index
        self._view.scale_changed.disconnect(self._scale_change_slot)
        self._view.offset_changed.disconnect(self._offset_change_slot)
        self._view.zoom_to_bounds(self._options[self._zoom_index].bounds)
        self._base_option_offset = self._view.offset
        self._base_option_scale = self._view.scene_scale
        self._view.offset = self._view.offset + self._option_pos_offset
        self._view.scene_scale = self._view.scene_scale + self._option_scale_offset
        self._view.scale_changed.connect(self._scale_change_slot)
        self._view.offset_changed.connect(self._offset_change_slot)
        for i, option in enumerate(self._options):
            option.setOpacity(1.0 if not self._zoomed_in or i == self._zoom_index else 0.5)
        self._page_top_label.setText(self._options[option_index].text)
        self._status_label.setText(ZOOM_CONTROL_HINT)

    def _zoom_prev(self):
        idx = len(self._options) - 1 if self._zoom_index <= 0 else self._zoom_index - 1
        self._zoom_to_option(idx)

    def _zoom_next(self):
        idx = 0 if self._zoom_index >= len(self._options) - 1 else self._zoom_index + 1
        self._zoom_to_option(idx)

    def _apply_ideal_image_arrangement(self) -> None:
        """Arrange options in a grid within the scene, choosing grid dimensions to maximize use of available space."""
        if len(self._options) == 0:
            return
        view_width = self._view.size().width()
        view_height = self._view.size().height()
        # All options should have matching sizes:
        image_size = self._options[0].size
        option_count = len(self._options)
        image_margin = int(min(image_size.width(), image_size.height()) * IMAGE_MARGIN_FRACTION)

        def get_scale_factor_for_row_count(row_count: int):
            """Returns the largest image scale multiplier possible to fit images within row_count rows."""
            column_count = math.ceil(option_count / row_count)
            img_bounds = QRect(0, 0, view_width // column_count, view_height // row_count)
            img_rect = get_scaled_placement(img_bounds, image_size, image_margin)
            return img_rect.width() / image_size.width()

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
        scene_size = QSizeF(num_columns * (image_size.width() + image_margin) - image_margin + VIEW_MARGIN * 2,
                            num_rows * (image_size.height() + image_margin) - image_margin + VIEW_MARGIN * 2)
        view_ratio = self._view.width() / self._view.height()
        scene_ratio = scene_size.width() / scene_size.height()
        scene_x0 = VIEW_MARGIN
        scene_y0 = VIEW_MARGIN
        if scene_ratio < view_ratio:
            new_width = int(view_ratio * scene_size.height())
            scene_x0 += (new_width - scene_size.width()) / 2
            scene_size.setWidth(new_width)
        elif scene_ratio > view_ratio:
            new_height = scene_size.width() // view_ratio
            scene_y0 += (new_height - scene_size.height()) / 2
            scene_size.setHeight(new_height)

        self._view.content_size = scene_size.toSize()
        for idx in range(option_count):
            row = idx // num_columns
            col = idx % num_columns
            x = scene_x0 + (image_size.width() + image_margin) * col
            y = scene_y0 + (image_size.height() + image_margin) * row
            self._options[idx].setPos(x, y)
            self._outlines[idx].outlined_region = self._options[idx].bounds


class _ImageOption(QGraphicsPixmapItem):
    """Displays a generated image option in the view, labeled with a title."""

    def __init__(self, image: QImage, label_text: str) -> None:
        super().__init__()
        self._image = image
        self._label_text = label_text
        self.setPixmap(QPixmap.fromImage(image))

    @property
    def text(self) -> str:
        """Gets the read-only label text."""
        return self._label_text

    @property
    def image(self) -> QImage:
        """Access the generated image option."""
        return self._image

    @image.setter
    def image(self, new_image: QImage) -> None:
        self._image = new_image
        self.setPixmap(QPixmap.fromImage(new_image))
        self.update()

    @property
    def bounds(self) -> QRect:
        """Return the image bounds within the scene."""
        return QRect(self.pos().toPoint(), self.size)

    @property
    def size(self) -> QSize:
        """Accesses the image size."""
        return self.pixmap().size()

    @size.setter
    def size(self, new_size) -> None:
        if new_size != self.size:
            self.setPixmap(QPixmap.fromImage(self.image.scaled(new_size)))
            self.update()

    @property
    def width(self) -> int:
        """Returns the image width."""
        return self.size.width()

    @property
    def height(self) -> int:
        """Returns the image height."""
        return self.size.height()

    @property
    def x(self) -> float:
        """Returns the item's x-coordinate in the scene."""
        return self.pos().x()

    @property
    def y(self) -> float:
        """Returns the item's y-coordinate in the scene."""
        return self.pos().y()

    def paint(self,
              painter: Optional[QPainter],
              option: Optional[QStyleOptionGraphicsItem],
              widget: Optional[QWidget] = None) -> None:
        """Draw the label above the image."""
        super().paint(painter, option, widget)
        painter.save()
        image_margin = int(min(self.width, self.height) * IMAGE_MARGIN_FRACTION)
        text_height = image_margin // 2
        text_bounds = QRect(self.width // 4, - text_height - VIEW_MARGIN, self.width // 2, text_height)
        corner_radius = text_bounds.height() // 5
        text_background = QPainterPath()
        text_background.addRoundedRect(QRectF(text_bounds), corner_radius, corner_radius)
        painter.fillPath(text_background, Qt.black)
        painter.setPen(Qt.white)
        font = painter.font()
        font_size = min(font.pointSize(), max_font_size(self._label_text, font, text_bounds))
        font.setPointSize(font_size)
        painter.setFont(font)
        painter.drawText(text_bounds, Qt.AlignCenter, self._label_text)
        painter.restore()


class _SelectionView(ImageGraphicsView):
    """Minimal ImageGraphicsView controlled by the GeneratedImageSelector"""

    zoom_toggled = pyqtSignal()
    content_scrolled = pyqtSignal(int, int)

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config)
        self.content_size = self.size()

    def scroll_content(self, dx: int | float, dy: int | float) -> bool:
        """Scroll content by the given offset, returning whether content was able to move."""
        self.content_scrolled.emit(int(dx), int(dy))
        return True

    def toggle_zoom(self) -> None:
        """Zoom in on some area of focus, or back to the full scene. Bound to the 'Toggle Zoom' key."""
        self.zoom_toggled.emit()

    def mousePressEvent(self, event: Optional[QMouseEvent], **kwargs) -> None:
        """Pass mouse events back to the parent widget unless the ImageGraphicsView handles them.

        QGraphicsView likes to intercept mouse events before the parent widget can process them, this gets around that
        behavior.
        """
        if super().mousePressEvent(event, True):
            return
        self.parent().eventFilter(self, event)

    def drawBackground(self, painter: Optional[QPainter], rect: QRectF) -> None:
        """Fill with solid black to increase visibility."""
        if painter is not None:
            painter.fillRect(rect, VIEW_BACKGROUND)
        super().drawBackground(painter, rect)
