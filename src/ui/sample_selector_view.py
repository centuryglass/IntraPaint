import math
from typing import Callable, Optional, cast

from PIL import Image
from PyQt5.QtCore import Qt, QRect, QSize, QPoint, QSizeF, QPointF, QRectF, QEvent
from PyQt5.QtGui import QImage, QResizeEvent, QPixmap, QTransform, QPainter, QWheelEvent, QKeyEvent, QMouseEvent, \
    QPainterPath
from PyQt5.QtWidgets import QWidget, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QVBoxLayout, QLabel, \
    QStyleOptionGraphicsItem
from src.config.application_config import AppConfig
from src.image.layer_stack import LayerStack
from src.ui.graphics_items.loading_spinner import LoadingSpinner
from src.ui.util.geometry_utils import get_scaled_placement

SCALE_OFFSET_STEP = 0.05

MAX_SCALE_OFFSET = 20.0

ORIGINAL_CONTENT_LABEL = "Original image content"

LOADING_IMG_TEXT = 'Loading...'

SELECTION_TITLE = 'Select from generated image options.'
ZOOM_IN_BUTTON_LABEL = 'Zoom in [z]'
ZOOM_OUT_BUTTON_LABEL = 'Zoom out [z]'
CANCEL_BUTTON_LABEL = 'Cancel'
VIEW_MARGIN = 6
IMAGE_MARGIN_FRACTION = 1/6


class SampleSelector(QWidget):

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
        self._options = []
        self._zoomed_in = False
        self._zoom_index = 0
        self._scale = 1.0
        self._scale_offset = 0.0
        self._scene_bounds = QRect()
        self._layout = QVBoxLayout(self)

        self._layout.addWidget(QLabel(SELECTION_TITLE))
        self._view = QGraphicsView()
        self._layout.addWidget(self._view, stretch=255)
        self._loading_spinner = LoadingSpinner()
        self._loading_spinner.setZValue(1)
        self._loading_spinner.visible = False
        self.installEventFilter(self)

        self._loading_image = QImage(self._config.get(AppConfig.GENERATION_SIZE), QImage.Format_ARGB32_Premultiplied)
        self._loading_image.fill(Qt.GlobalColor.black)
        painter = QPainter(self._loading_image)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(QRect(0, 0, self._loading_image.width(), self._loading_image.height()), Qt.AlignCenter,
                         LOADING_IMG_TEXT)

        # Scene/view setup:
        self._scene = QGraphicsScene()
        self._scene.setSceneRect(QRectF(0, 0, float(self.width()), float(self.height())))
        self._view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setCacheMode(QGraphicsView.CacheBackground)
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self._view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self._view.setScene(self._scene)
        self._scene.addItem(self._loading_spinner)

        original_image = self._layer_stack.qimage_selection_content().scaled(self._loading_image.size())
        original_option = _ImageOption(original_image, ORIGINAL_CONTENT_LABEL)
        self._scene.addItem(original_option)
        self._options.append(original_option)

        expected_count = config.get(AppConfig.BATCH_SIZE) * config.get(AppConfig.BATCH_COUNT)
        for i in range(expected_count):
            self.add_image_option(self._loading_image, i)

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
            self._options.append(_ImageOption(image, f'Option {idx + 1}'))
            self._scene.addItem(self._options[-1])
        else:
            self._options[idx].image = image
        self.resizeEvent(None)

    def toggle_zoom(self, zoom_index: Optional[int] = None) -> None:
        if zoom_index is not None:
            self._zoom_index = zoom_index
        self._zoomed_in = not self._zoomed_in
        print(f'zoom toggle: {self._zoom_index}, zoom = {self._zoomed_in}')
        self.resizeEvent(None)

    def _zoom_prev(self):
        if not self._zoomed_in:
            self._zoomed_in = True
        self._zoom_index -= 1
        if self._zoom_index < 0:
            self._zoom_index = len(self._options) - 1
        print('zoom next: ', self._zoom_index)
        self.resizeEvent(None)

    def _zoom_next(self):
        if not self._zoomed_in:
            self._zoomed_in = True
        self._zoom_index += 1
        if self._zoom_index >= len(self._options):
            self._zoom_index = 0
        print('zoom prev: ', self._zoom_index)
        self.resizeEvent(None)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]):
        """Recalculate all bounds on resize and update view scale."""
        self._scene.setSceneRect(QRectF(0, 0, float(self._view.width()), float(self._view.height())))
        self._apply_ideal_image_arrangement()
        for i, option in enumerate(self._options):
            option.setOpacity(1.0 if not self._zoomed_in or i == self._zoom_index else 0.5)
        if len(self._options) > 0:
            if self._zoomed_in:
                if self._zoom_index is None or not 0 <= self._zoom_index < len(self._options):
                    self._zoom_index = 0
                option = self._options[self._zoom_index]
                self._scale = min(self._view.width() / (option.width + VIEW_MARGIN * 2),
                                  self._view.height() / (option.height + VIEW_MARGIN * 2))
            else:
                content_width = self._scene_bounds.width()
                view_width = self._view.width()
                self._scale = view_width / content_width
            transformation = QTransform()
            final_scale = max(self._scale + self._scale_offset, 0.01)
            transformation.scale(final_scale, final_scale)
            self._view.setTransform(transformation)
            if self._zoomed_in:
                option_bounds = self._options[self._zoom_index].bounds
                self._scene.setSceneRect(QRectF(option_bounds))
                self._view.centerOn(option_bounds.center())
            else:
                self._scene.setSceneRect(QRectF(self._scene_bounds))
                self._view.centerOn(self._scene_bounds.center())

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
            scene_x0 += (new_width - scene_size.width()) // 2
            scene_size.setWidth(new_width)
        elif scene_ratio > view_ratio:
            new_height = scene_size.width() // view_ratio
            scene_y0 += (new_height - scene_size.height()) // 2
            scene_size.setHeight(new_height)

        self._scene_bounds = QRect(QPoint(0, 0), scene_size.toSize())
        for idx in range(option_count):
            row = idx // num_columns
            col = idx % num_columns
            x = scene_x0 + (image_size.width() + image_margin) * col
            y = scene_y0 + (image_size.height() + image_margin) * row
            self._options[idx].setPos(x, y)

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
                if self._zoomed_in:
                    toggle_zoom = True
                else:
                    self._make_selection(None)
                    self._close_selector()
            case Qt.Key_Return | Qt.Key_Enter if self._zoomed_in:
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
            case Qt.Key_Left | Qt.Key_A | Qt.Key_H:
                if self._zoomed_in:
                    self._zoom_prev()
            case Qt.Key_Right | Qt.Key_D | Qt.Key_L:
                if self._zoomed_in:
                    self._zoom_next()
            case Qt.Key_Up | Qt.Key_W | Qt.Key_K:
                if self._zoomed_in:
                    toggle_zoom = True
            case Qt.Key_Down | Qt.Key_S | Qt.Key_J:
                if not self._zoomed_in:
                    toggle_zoom = True
            case _:
                return False
        if toggle_zoom:
            self.toggle_zoom(zoom_index)
        elif self._zoomed_in and zoom_index is not None and zoom_index >= 0:
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
                print('wheelevent')
                event = cast(QWheelEvent, event)
                if event.angleDelta().y() > 0:
                    self._zoom_next()
                elif event.angleDelta().y() < 0:
                    self._zoom_prev()
                elif event.angleDelta().x() > 0:
                    self._scale_offset = min(self._scale_offset + SCALE_OFFSET_STEP, MAX_SCALE_OFFSET)
                    self.resizeEvent(None)
                elif event.angleDelta().x() < 0:
                    self._scale_offset = max(self._scale_offset - SCALE_OFFSET_STEP, -self._scale)
                    self.resizeEvent(None)
                return True
            case QEvent.KeyPress:
                return self._handle_key_event(cast(QKeyEvent, event))
        return super().eventFilter(source, event)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle image selection and arrow button clicks."""
        if event.button() != Qt.LeftButton or self._loading_spinner.visible:
            return
        if self._zoomed_in:
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


class _ImageOption(QGraphicsPixmapItem):

    def __init__(self, image: QImage, label_text: str) -> None:
        super().__init__()
        self._image = image
        self._label_text = label_text
        self.setPixmap(QPixmap.fromImage(image))

    @property
    def image(self) -> QImage:
        return self._image

    @image.setter
    def image(self, new_image: QImage) -> None:
        self._image = new_image
        self.setPixmap(QPixmap.fromImage(new_image))
        self.update()

    @property
    def bounds(self) -> QRect:
        return QRect(self.pos().toPoint(), self.size)

    @property
    def size(self) -> QSize:
        return self._image.size()

    @property
    def width(self) -> int:
        return self.size.width()

    @property
    def height(self) -> int:
        return self.size.height()

    @property
    def x(self) -> int:
        return int(self.pos().x())

    @property
    def y(self) -> int:
        return int(self.pos().y())

    def paint(self,
              painter: Optional[QPainter],
              option: Optional[QStyleOptionGraphicsItem],
              widget: Optional[QWidget] = None) -> None:
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
        painter.drawText(text_bounds, Qt.AlignCenter, self._label_text)
        painter.restore()

