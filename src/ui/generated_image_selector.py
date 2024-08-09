"""
Provides an interface for choosing between AI-generated changes to selected image content.
"""
import math
import sys
import time
from typing import Callable, Optional, cast, List

from PIL import Image
from PySide6.QtCore import Qt, QRect, QSize, QSizeF, QRectF, QEvent, Signal, QPointF, QObject, QPoint
from PySide6.QtGui import QImage, QResizeEvent, QPixmap, QPainter, QWheelEvent, QMouseEvent, \
    QPainterPath, QKeyEvent, QPolygonF
from PySide6.QtWidgets import QWidget, QGraphicsPixmapItem, QVBoxLayout, QLabel, \
    QStyleOptionGraphicsItem, QHBoxLayout, QPushButton, QStyle

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.ui.graphics_items.outline import Outline
from src.ui.graphics_items.polygon_outline import PolygonOutline
from src.ui.input_fields.check_box import CheckBox
from src.ui.widget.image_graphics_view import ImageGraphicsView
from src.util.application_state import AppStateTracker, APP_STATE_LOADING, APP_STATE_EDITING
from src.util.display_size import max_font_size
from src.util.geometry_utils import get_scaled_placement
from src.util.image_utils import get_standard_qt_icon, pil_image_scaling, get_transparency_tile_pixmap, \
    pil_image_to_qimage
from src.util.key_code_utils import get_key_display_string
from src.util.shared_constants import TIMELAPSE_MODE_FLAG
from src.util.validation import assert_valid_index

CHANGE_ZOOM_CHECKBOX_LABEL = 'Zoom to changes'

SHOW_SELECTION_OUTLINES_LABEL = 'Show selection'

MODE_INPAINT = 'Inpaint'

CANCEL_BUTTON_TEXT = 'Cancel'
CANCEL_BUTTON_TOOLTIP = 'This will discard all generated images.'
PREVIOUS_BUTTON_TEXT = 'Previous'
ZOOM_BUTTON_TEXT = 'Toggle zoom'
NEXT_BUTTON_TEXT = 'Next'

ORIGINAL_CONTENT_LABEL = 'Original image content'
LOADING_IMG_TEXT = 'Loading...'

SELECTION_TITLE = 'Select from generated image options.'
VIEW_MARGIN = 6
IMAGE_MARGIN_FRACTION = 1 / 6
SCROLL_DEBOUNCE_MS = 100

DEFAULT_CONTROL_HINT = 'Ctrl+LMB or MMB and drag: pan view, mouse wheel: zoom, Esc: discard all options'
ZOOM_CONTROL_HINT = ('Ctrl+LMB or MMB and drag: pan view, mouse wheel: zoom, Enter: select option, Esc: return to full'
                     ' view')

VIEW_BACKGROUND = Qt.GlobalColor.black


class GeneratedImageSelector(QWidget):
    """Shows all images from an image generation operation, allows the user to select one or discard all of them."""

    def __init__(self,
                 image_stack: ImageStack,
                 close_selector: Callable) -> None:
        super().__init__(None)
        self._image_stack = image_stack
        self._close_selector = close_selector
        self._options: List[_ImageOption] = []
        self._outlines: List[Outline] = []
        self._selections: List[PolygonOutline] = []
        self._loading_image = QImage()
        self._zoomed_in = False
        self._zoom_to_changes = AppConfig().get(AppConfig.SELECTION_SCREEN_ZOOMS_TO_CHANGED)
        self._change_bounds: Optional[QRect] = None
        self._zoom_index = 0
        self._last_scroll_time = time.time() * 1000

        self._base_option_offset = QPointF(0.0, 0.0)
        self._base_option_scale = 0.0
        self._option_scale_offset = 0.0
        self._option_pos_offset = QPointF(0.0, 0.0)

        self._layout = QVBoxLayout(self)
        self._page_top_bar = QWidget()
        self._page_top_layout = QHBoxLayout(self._page_top_bar)
        self._page_top_label = QLabel(SELECTION_TITLE)
        self._page_top_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_top_layout.addWidget(self._page_top_label, stretch=255)
        self._layout.addWidget(self._page_top_bar)

        # Setup main option view widget:
        self._view = _SelectionView()
        self._view.scale_changed.connect(self._scale_change_slot)
        self._view.offset_changed.connect(self._offset_change_slot)

        self._view.installEventFilter(self)
        config = AppConfig()

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

        # Add inpainting checkboxes:
        # show/hide selection outlines:
        self._selection_outline_checkbox = config.get_control_widget(
            AppConfig.SHOW_SELECTIONS_IN_GENERATION_OPTIONS)
        assert isinstance(self._selection_outline_checkbox, CheckBox)
        self._selection_outline_checkbox.setText(SHOW_SELECTION_OUTLINES_LABEL)
        self._selection_outline_checkbox.toggled.connect(self.set_selection_outline_visibility)
        self._page_top_layout.addWidget(self._selection_outline_checkbox)

        # zoom to changed area:
        self._change_zoom_checkbox = config.get_control_widget(AppConfig.SELECTION_SCREEN_ZOOMS_TO_CHANGED)
        assert isinstance(self._change_zoom_checkbox, CheckBox)
        self._change_zoom_checkbox.setText(CHANGE_ZOOM_CHECKBOX_LABEL)
        self._change_zoom_checkbox.toggled.connect(self.zoom_to_changes)
        self._page_top_layout.addWidget(self._change_zoom_checkbox)

        self._button_bar = QWidget()
        self._layout.addWidget(self._button_bar)
        self._button_bar_layout = QHBoxLayout(self._button_bar)

        self._cancel_button = QPushButton()
        self._cancel_button.setIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_DialogCancelButton))
        self._cancel_button.setText(CANCEL_BUTTON_TEXT)
        self._cancel_button.setToolTip(CANCEL_BUTTON_TOOLTIP)
        self._cancel_button.clicked.connect(self._close_selector)
        self._button_bar_layout.addWidget(self._cancel_button)

        self._button_bar_layout.addStretch(255)

        self._status_label = QLabel(DEFAULT_CONTROL_HINT)
        self._button_bar_layout.addWidget(self._status_label)
        self._button_bar_layout.addStretch(255)

        key_config = KeyConfig()

        def _add_key_hint(button, config_key):
            keys = key_config.get_keycodes(config_key)
            button.setText(f'{button.text()} [{get_key_display_string(keys)}]')

        self._prev_button = QPushButton()
        self._prev_button.setIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_ArrowLeft))
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
        self._next_button.setIcon(get_standard_qt_icon(QStyle.StandardPixmap.SP_ArrowRight))
        self._next_button.setText(NEXT_BUTTON_TEXT)
        self._next_button.clicked.connect(self._zoom_next)
        _add_key_hint(self._next_button, KeyConfig.MOVE_RIGHT)
        self._button_bar_layout.addWidget(self._next_button)
        self.reset()

    def reset(self) -> None:
        """Remove all old options and prepare for new ones."""
        self._zoom_index = 0
        config = AppConfig()
        scene = self._view.scene()
        assert scene is not None
        # Clear the scene:
        for scene_item_list in (self._selections, self._outlines, self._options):
            assert isinstance(scene_item_list, list)
            while len(scene_item_list) > 0:
                scene_item = scene_item_list.pop()
                if scene_item in scene.items():
                    scene.removeItem(scene_item)

        # Configure checkboxes and change bounds:
        if config.get(AppConfig.EDIT_MODE) == MODE_INPAINT:
            self._selection_outline_checkbox.setVisible(True)
            change_bounds = self._image_stack.selection_layer.get_selection_gen_area(True)
            if change_bounds != self._image_stack.generation_area and change_bounds is not None:
                change_bounds.translate(-self._image_stack.generation_area.x(), -self._image_stack.generation_area.y())
                self._change_bounds = change_bounds
                self._change_zoom_checkbox.setVisible(True)
            else:
                self._change_bounds = None
                self._change_zoom_checkbox.setVisible(False)
        else:
            self._selection_outline_checkbox.setVisible(False)
            self._change_zoom_checkbox.setVisible(False)
            self._change_bounds = None

        # Add initial images, placeholders for expected images:
        original_image = self._image_stack.qimage_generation_area_content()
        original_option = _ImageOption(original_image, ORIGINAL_CONTENT_LABEL)
        scene.addItem(original_option)
        self._options.append(original_option)
        self._outlines.append(Outline(scene, self._view))
        self._outlines[0].outlined_region = self._options[0].bounds
        if config.get(AppConfig.EDIT_MODE) == MODE_INPAINT:
            self._add_option_selection_outline(0)

        self._loading_image = QImage(original_image.size(), QImage.Format.Format_ARGB32_Premultiplied)
        self._loading_image.fill(Qt.GlobalColor.black)
        painter = QPainter(self._loading_image)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(QRect(0, 0, self._loading_image.width(), self._loading_image.height()),
                         Qt.AlignmentFlag.AlignCenter,
                         LOADING_IMG_TEXT)
        painter.end()

        expected_count = config.get(AppConfig.BATCH_SIZE) * config.get(AppConfig.BATCH_COUNT)
        for i in range(expected_count):
            self.add_image_option(self._loading_image, i)

        if self._zoomed_in and TIMELAPSE_MODE_FLAG not in sys.argv:
            self.toggle_zoom()
        elif TIMELAPSE_MODE_FLAG in sys.argv:
            self._zoom_to_option(0)
        self.resizeEvent(None)

    def _add_option_selection_outline(self, idx: int) -> None:
        if len(self._options) <= idx:
            raise IndexError(f'Invalid option index {idx}')
        if len(self._selections) != idx:
            raise RuntimeError(f'Generating selection outline {idx}, unexpected outline count {len(self._selections)}'
                               f' found.')
        selection_crop = QPolygonF(QRectF(self._image_stack.generation_area))
        origin = self._image_stack.generation_area.topLeft()
        selection_polys = (poly.intersected(selection_crop).translated(-origin.x(), -origin.y())
                           for poly in self._image_stack.selection_layer.outline)
        polys = [QPolygonF(poly) for poly in selection_polys]
        outline = PolygonOutline(self._view, polys)
        outline.animated = AppConfig().get(AppConfig.ANIMATE_OUTLINES)
        outline.setScale(self._image_stack.width / self._image_stack.generation_area.width())
        outline.setVisible(AppConfig().get(AppConfig.SHOW_SELECTIONS_IN_GENERATION_OPTIONS))
        self._selections.append(outline)

    def add_image_option(self, image: QImage, idx: int) -> None:
        """Add an image to the list of generated image options."""
        if not 0 <= idx < len(self._options):
            raise IndexError(f'invalid index {idx}, max is {len(self._options)}')
        idx += 1  # Original image gets index zero
        if idx == len(self._options):
            self._options.append(_ImageOption(image, f'Option {idx}'))
            scene = self._view.scene()
            assert scene is not None, 'Scene should have been created automatically and never cleared'
            scene.addItem(self._options[-1])
            self._outlines.append(Outline(scene, self._view))
            # Add selections if inpainting:
            if AppConfig().get(AppConfig.EDIT_MODE) == MODE_INPAINT:
                self._add_option_selection_outline(idx)
        else:
            self._options[idx].image = image
        self._outlines[idx].outlined_region = self._options[idx].bounds

        self.resizeEvent(None)

    def toggle_zoom(self, zoom_index: Optional[int] = None) -> None:
        """Toggle between zooming in on one option and showing all of them."""
        if zoom_index is not None:
            self._zoom_index = zoom_index
        self._zoomed_in = not self._zoomed_in
        if self._zoomed_in:
            self._zoom_to_option(self._zoom_index, True)
        else:
            if not self._scroll_debounce_finished():
                return
            self._view.reset_scale()
            self._option_pos_offset = QPointF(0.0, 0.0)
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
        if self._zoomed_in:
            self._zoom_to_option(self._zoom_index, True)

    def eventFilter(self, source: Optional[QObject], event: Optional[QEvent]):
        """Use horizontal scroll to move through selections, select items when clicked."""
        assert event is not None
        if event.type() == QEvent.Type.Wheel:
            event = cast(QWheelEvent, event)
            if event.angleDelta().x() > 0:
                self._zoom_next()
            elif event.angleDelta().x() < 0:
                self._zoom_prev()
            return event.angleDelta().x() != 0
        if event.type() == QEvent.Type.KeyPress:
            event = cast(QKeyEvent, event)
            if event.key() == Qt.Key.Key_Escape:
                if self._zoomed_in:
                    self.toggle_zoom()
                else:
                    self._close_selector()
            elif (event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return) and self._zoomed_in:
                self._select_option(self._zoom_index)
            else:
                try:
                    num_value = int(event.text())
                    if 0 <= num_value < len(self._options):
                        self._zoom_to_option(num_value, True)
                        return True
                    return False
                except ValueError:
                    return False
            return True
        if event.type() == QEvent.Type.MouseButtonPress:
            if KeyConfig.modifier_held(KeyConfig.PAN_VIEW_MODIFIER):
                return False  # Ctrl+click is for panning, don't select options
            event = cast(QMouseEvent, event)
            if event.button() != Qt.MouseButton.LeftButton or AppStateTracker.app_state() == APP_STATE_LOADING:
                return False
            if source == self._view:
                view_pos = event.pos()
            else:
                view_pos = QPoint(self._view.x() + event.pos().x(), self._view.y() + event.pos().y())
            scene_pos = self._view.mapToScene(view_pos).toPoint()
            for i, option in enumerate(self._options):
                if option.bounds.contains(scene_pos):
                    self._select_option(i)
        return False

    def _offset_change_slot(self, offset: QPointF) -> None:
        if not self._zoomed_in:
            return
        self._option_pos_offset = QPointF(offset) - QPointF(self._base_option_offset)

    def _scale_change_slot(self, scale: float) -> None:
        if not self._zoomed_in:
            return
        self._option_scale_offset = scale - self._base_option_scale

    def _select_option(self, option_index: int) -> None:
        """Apply an AI-generated image change to the edited image."""
        sample_image = None if option_index == 0 else self._options[option_index].image
        if sample_image is not None:
            if isinstance(sample_image, Image.Image):
                image = pil_image_to_qimage(sample_image).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            else:
                image = sample_image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            if AppConfig().get(AppConfig.EDIT_MODE) == 'Inpaint':
                inpaint_mask = self._image_stack.selection_layer.mask_image
                painter = QPainter(image)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                painter.drawImage(QRect(QPoint(0, 0), image.size()), inpaint_mask)
                painter.end()
            layer = self._image_stack.active_layer
            self._image_stack.set_generation_area_content(image, layer)
            AppStateTracker.set_app_state(APP_STATE_EDITING)
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
        if option_index is not None:
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
            scene_x0 += int((new_width - scene_size.width()) / 2)
            scene_size.setWidth(new_width)
        elif scene_ratio > view_ratio:
            new_height = scene_size.width() // view_ratio
            scene_y0 += int((new_height - scene_size.height()) / 2)
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
                scale = self._options[idx].bounds.width() / self._image_stack.generation_area.width()
                selection.setScale(scale)
                selection.move_to(QPointF(x / selection.scale(), y / selection.scale()))


class _ImageOption(QGraphicsPixmapItem):
    """Displays a generated image option in the view, labeled with a title."""

    def __init__(self, image: QImage, label_text: str) -> None:
        super().__init__()
        self._full_image = image
        self._scaled_image = image
        self._label_text = label_text
        self._transparency_pixmap = get_transparency_tile_pixmap(image.size())
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
        config = AppConfig()
        full_size = config.get(AppConfig.GENERATION_SIZE)
        final_size = config.get(AppConfig.EDIT_SIZE)
        if new_image.size() == full_size:
            self._full_image = new_image
            self._scaled_image = pil_image_scaling(new_image, final_size)
        elif new_image.size() == final_size:
            self._full_image = pil_image_scaling(new_image, full_size)
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
            self.setPixmap(QPixmap.fromImage(pil_image_scaling(self.image, new_size)))
            self.update()

    @property
    def width(self) -> int:
        """Returns the image width."""
        return self.size.width()

    @property
    def height(self) -> int:
        """Returns the image height."""
        return self.size.height()

    def paint(self,
              painter: Optional[QPainter],
              option: Optional[QStyleOptionGraphicsItem],
              widget: Optional[QWidget] = None) -> None:
        """Draw the label above the image."""
        super().paint(painter, option, widget)
        assert painter is not None
        painter.save()
        image_margin = int(min(self.width, self.height) * IMAGE_MARGIN_FRACTION)
        text_height = image_margin // 2
        text_bounds = QRect(self.width // 4, - text_height - VIEW_MARGIN, self.width // 2, text_height)
        corner_radius = text_bounds.height() // 5
        text_background = QPainterPath()
        text_background.addRoundedRect(QRectF(text_bounds), corner_radius, corner_radius)
        painter.fillPath(text_background, Qt.GlobalColor.black)
        painter.setPen(Qt.GlobalColor.white)
        font = painter.font()
        font_size = max(1, min(font.pointSize(), max_font_size(self._label_text, font, text_bounds.size())))
        font.setPointSize(font_size)
        painter.setFont(font)
        painter.drawText(text_bounds, Qt.AlignmentFlag.AlignCenter, self._label_text)
        if self.opacity() == 1.0:
            painter.drawTiledPixmap(QRect(0, 0, self.width, self.height), self._transparency_pixmap)
        painter.restore()
        super().paint(painter, option, widget)


class _SelectionView(ImageGraphicsView):
    """Minimal ImageGraphicsView controlled by the GeneratedImageSelector"""

    zoom_toggled = Signal()
    content_scrolled = Signal(int, int)

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

    def drawBackground(self, painter: Optional[QPainter], rect: QRectF) -> None:
        """Fill with solid black to increase visibility."""
        if painter is not None:
            painter.fillRect(rect, VIEW_BACKGROUND)
        super().drawBackground(painter, rect)
