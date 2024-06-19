"""
Provides an interface for choosing between AI-generated changes to selected image content.
"""
import math
import time
from typing import Callable, Optional, cast, List

from PIL import Image
from PyQt5.QtCore import Qt, QRect, QSize, QPoint, QSizeF, QRectF, QEvent, pyqtSignal, QPointF
from PyQt5.QtGui import QImage, QResizeEvent, QPixmap, QPainter, QWheelEvent, QMouseEvent, \
    QPainterPath, QKeyEvent, QPolygonF, QTransform
from PyQt5.QtWidgets import QWidget, QGraphicsPixmapItem, QVBoxLayout, QLabel, \
    QStyleOptionGraphicsItem, QHBoxLayout, QPushButton, QStyle, QApplication, QCheckBox

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.image.layer_stack import LayerStack
from src.ui.config_control_setup import connected_checkbox
from src.ui.graphics_items.loading_spinner import LoadingSpinner
from src.ui.graphics_items.outline import Outline
from src.ui.graphics_items.polygon_outline import PolygonOutline
from src.util.geometry_utils import get_scaled_placement
from src.util.font_size import max_font_size
from src.ui.widget.image_graphics_view import ImageGraphicsView
from src.util.image_utils import get_standard_qt_icon
from src.util.key_code_utils import get_key_display_string
from src.util.validation import assert_valid_index

CHANGE_ZOOM_CHECKBOX_LABEL = 'Zoom to changes'

SHOW_SELECTION_OUTLINES_LABEL = "Show selection"

MODE_INPAINT = 'Inpaint'

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
                 layer_stack: LayerStack,
                 close_selector: Callable,
                 make_selection: Callable[[Optional[Image.Image]], None]) -> None:
        super().__init__(None)
        self._layer_stack = layer_stack
        self._close_selector = close_selector
        self._make_selection = make_selection
        self._options: List[_ImageOption] = []
        self._outlines: List[Outline] = []
        self._selections: List[PolygonOutline] = []
        self._zoomed_in = False
        self._zoom_to_changes = AppConfig.instance().get(AppConfig.SELECTION_SCREEN_ZOOMS_TO_CHANGED)
        self._change_bounds = None
        self._zoom_index = 0
        self._last_scroll_time = time.time() * 1000

        self._base_option_offset = QPoint(0, 0)
        self._base_option_scale = 0.0
        self._option_scale_offset = 0.0
        self._option_pos_offset = QPoint(0, 0)

        self._layout = QVBoxLayout(self)
        self._page_top_bar = QWidget()
        self._page_top_layout = QHBoxLayout(self._page_top_bar)
        self._page_top_label = QLabel(SELECTION_TITLE)
        self._page_top_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_top_layout.addWidget(self._page_top_label, stretch = 255)
        self._layout.addWidget(self._page_top_bar)

        # Setup main option view widget:
        self._view = _SelectionView()
        self._view.scale_changed.connect(self._scale_change_slot)
        self._view.offset_changed.connect(self._offset_change_slot)

        self._view.installEventFilter(self)
        config = AppConfig.instance()

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

        original_image = self._layer_stack.qimage_generation_area_content()
        original_option = _ImageOption(original_image, ORIGINAL_CONTENT_LABEL)
        self._view.scene().addItem(original_option)
        self._options.append(original_option)
        self._outlines.append(Outline(self._view.scene(), self._view))
        self._outlines[0].outlined_region = self._options[0].bounds
        if config.get(AppConfig.EDIT_MODE) == MODE_INPAINT:
            self._add_option_selection_outline(0)

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

        # Add extra checkboxes when inpainting:
        if config.get(AppConfig.EDIT_MODE) == MODE_INPAINT:
            # show/hide selection outlines:
            self._selection_outline_checkbox = connected_checkbox(None,
                                                                  AppConfig.SHOW_SELECTIONS_IN_GENERATION_OPTIONS,
                                                                  SHOW_SELECTION_OUTLINES_LABEL)
            self._selection_outline_checkbox.toggled.connect(self.set_selection_outline_visibility)
            self._page_top_layout.addWidget(self._selection_outline_checkbox)
            # zoom to changed area:
            change_bounds = layer_stack.selection_layer.get_selection_gen_area(True)
            if change_bounds != layer_stack.generation_area and change_bounds is not None:
                change_bounds.translate(-layer_stack.generation_area.x(), -layer_stack.generation_area.y())
                self._change_bounds = change_bounds
                self._change_zoom_checkbox = connected_checkbox(None, AppConfig.SELECTION_SCREEN_ZOOMS_TO_CHANGED,
                                                                CHANGE_ZOOM_CHECKBOX_LABEL)
                self._change_zoom_checkbox.toggled.connect(self.zoom_to_changes)
                self._page_top_layout.addWidget(self._change_zoom_checkbox)

        # Add selections if inpainting:

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

        key_config = KeyConfig.instance()

        def _add_key_hint(button, config_key):
            keys = key_config.get_keycodes(config_key)
            button.setText(f'{button.text()} [{get_key_display_string(keys)}]')

        self._prev_button = QPushButton()
        self._prev_button.setIcon(get_standard_qt_icon(QStyle.SP_ArrowLeft))
        self._prev_button.setText(PREVIOUS_BUTTON_TEXT)
        self._prev_button.clicked.connect(self._zoom_prev)
        _add_key_hint(self._prev_button, KeyConfig.MOVE_LEFT)
        self._button_bar_layout.addWidget(self._prev_button)

        self._zoom_button = QPushButton()
        self._zoom_button.setText(ZOOM_BUTTON_TEXT)
        self._zoom_button.clicked.connect(self.toggle_zoom)
        _add_key_hint(self._zoom_button, KeyConfig.ZOOM_TOGGLE)
        self._button_bar_layout.addWidget(self._zoom_button)

        self._next_button = QPushButton()
        self._next_button.setIcon(get_standard_qt_icon(QStyle.SP_ArrowRight))
        self._next_button.setText(NEXT_BUTTON_TEXT)
        self._next_button.clicked.connect(self._zoom_next)
        _add_key_hint(self._next_button, KeyConfig.MOVE_RIGHT)
        self._button_bar_layout.addWidget(self._next_button)

    def set_is_loading(self, is_loading: bool, message: Optional[str] = None):
        """Show or hide the loading indicator"""
        if message is not None:
            self._loading_spinner.message = message
        self._loading_spinner.visible = is_loading

    def set_loading_message(self, message: str) -> None:
        """Changes the loading spinner message."""
        self._loading_spinner.message = message

    def _add_option_selection_outline(self, idx: int) -> None:
        if len(self._options) <= idx:
            raise IndexError(f'Invalid option index {idx}')
        if len(self._selections) != idx:
            raise RuntimeError(f'Generating selection outline {idx}, unexpected outline count {len(self._selections)}'
                               f' found.')
        selection_crop = QPolygonF(QRectF(self._layer_stack.generation_area))
        origin = self._layer_stack.generation_area.topLeft()
        selection_polys = (poly.intersected(selection_crop).translated(-origin.x(), -origin.y())
                           for poly in self._layer_stack.selection_layer.outline)
        polys = [QPolygonF(poly) for poly in selection_polys]
        outline = PolygonOutline(self._view, polys)
        outline.animated = AppConfig.instance().get(AppConfig.ANIMATE_OUTLINES)
        outline.setScale(self._layer_stack.width / self._layer_stack.generation_area.width())
        outline.setVisible(AppConfig.instance().get(AppConfig.SHOW_SELECTIONS_IN_GENERATION_OPTIONS))
        self._selections.append(outline)

    def add_image_option(self, image: QImage, idx: int) -> None:
        """Add an image to the list of generated image options."""
        if not 0 <= idx < len(self._options):
            raise IndexError(f'invalid index {idx}, max is {len(self._options)}')
        idx += 1  # Original image gets index zero
        if idx == len(self._options):
            self._options.append(_ImageOption(image, f'Option {idx}'))
            self._view.scene().addItem(self._options[-1])
            self._outlines.append(Outline(self._view.scene(), self._view))
            # Add selections if inpainting:
            if AppConfig.instance().get(AppConfig.EDIT_MODE) == MODE_INPAINT:
                self._add_option_selection_outline(idx)
        else:
            self._options[idx].image = image
        self._outlines[idx].outlined_region = self._options[idx].bounds

        self.resizeEvent(None)

    def toggle_zoom(self, zoom_index: Optional[int] = None) -> None:
        """Toggle between zoomin in on one option and showing all of them."""
        if zoom_index is not None:
            self._zoom_index = zoom_index
        self._zoomed_in = not self._zoomed_in
        if self._zoomed_in:
            self._zoom_to_option(self._zoom_index, True)
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

    def zoom_to_changes(self, should_zoom: bool) -> None:
        """Zoom in to the updated area when inpainting small sections."""
        self._zoom_to_changes = should_zoom
        if self._zoom_to_changes:
            if not self._zoomed_in:
                self.toggle_zoom()
            self._zoom_to_option(self._zoom_index, True)
        elif self._zoomed_in:
            self._zoom_to_option(self._zoom_index, True)

    def set_selection_outline_visibility(self, show_selections: bool) -> None:
        """Set whether selection outlines are drawn."""
        for selection_outline in self._selections:
            selection_outline.setVisible(show_selections)

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

    def _zoom_to_option(self, option_index: Optional[int] = None, ignore_debounce: bool = False) -> None:
        assert_valid_index(option_index, self._options)
        if not ignore_debounce and not self._scroll_debounce_finished():
            return
        if not self._zoomed_in:
            self._zoomed_in = True
        if option_index is not None:
            self._zoom_index = option_index
        self._view.scale_changed.disconnect(self._scale_change_slot)
        self._view.offset_changed.disconnect(self._offset_change_slot)
        if self._zoom_to_changes and self._change_bounds is not None:
            bounds = QRect(self._change_bounds)
            offset = self._options[self._zoom_index].bounds.topLeft()
            bounds.translate(offset.x(), offset.y())
        else:
            bounds = self._options[self._zoom_index].bounds
        self._view.zoom_to_bounds(bounds)
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
            if len(self._selections) > idx:
                selection = self._selections[idx]
                selection.setZValue(self._options[idx].zValue() + 1)
                scale = self._options[idx].bounds.width() / self._layer_stack.generation_area.width()
                selection.setScale(scale)
                selection.move_to(QPointF(x / selection.scale(), y / selection.scale()))


class _ImageOption(QGraphicsPixmapItem):
    """Displays a generated image option in the view, labeled with a title."""

    def __init__(self, image: QImage, label_text: str) -> None:
        super().__init__()
        self._full_image = image
        self._scaled_image = image
        self._label_text = label_text
        self.image = image

    @property
    def text(self) -> str:
        """Gets the read-only label text."""
        return self._label_text

    @property
    def image(self) -> QImage:
        """Access the generated image option."""
        return self._scaled_image

    @image.setter
    def image(self, new_image: QImage) -> None:
        config = AppConfig.instance()
        full_size = config.get(AppConfig.GENERATION_SIZE)
        final_size = config.get(AppConfig.EDIT_SIZE)
        if new_image.size() == full_size:
            self._full_image = new_image
            self._scaled_image = new_image.scaled(final_size.width(), final_size.height(),
                                              transformMode=Qt.TransformationMode.SmoothTransformation)
        elif new_image.size() == final_size:
            self._full_image = new_image.scaled(full_size.width(), full_size.height(),
                                            transformMode=Qt.TransformationMode.SmoothTransformation)
            self._scaled_image = new_image
        self.setPixmap(QPixmap.fromImage(self._full_image if config.get(AppConfig.SHOW_OPTIONS_FULL_RESOLUTION)
                                         else self._scaled_image))
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
        font_size = max(1, min(font.pointSize(), max_font_size(self._label_text, font, text_bounds)))
        font.setPointSize(font_size)
        painter.setFont(font)
        painter.drawText(text_bounds, Qt.AlignCenter, self._label_text)
        painter.restore()


class _SelectionView(ImageGraphicsView):
    """Minimal ImageGraphicsView controlled by the GeneratedImageSelector"""

    zoom_toggled = pyqtSignal()
    content_scrolled = pyqtSignal(int, int)

    def __init__(self) -> None:
        super().__init__()
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
