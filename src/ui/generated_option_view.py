"""Draws a batch of generated image options: the scene item for each option, and the view that shows them.

The view draws the option captions, focus ring, loading states, hover hint and compare tag over the scene in viewport
pixels, so they keep one size at every zoom level. It reads what to draw from an `OverlayState` the selector sets, and
holds no batch state of its own.
"""
from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem, QStyleOptionGraphicsItem, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.generated_image_batch import edit_size_image, full_size_image
from src.ui.ink_style import ink_colors
from src.ui.loading.halftone_press import HalftonePress
from src.ui.loading.loading_design import LoadingDesign
from src.ui.widget.image_graphics_view import ImageGraphicsView
from src.ui.widget.option_filmstrip import MAX_DIGIT_KEY
from src.util.visual.image_utils import get_transparency_tile_pixmap
from src.util.visual.keycap import KEYCAP_DEPTH, draw_keycap, keycap_colors, keycap_font, keycap_size
from src.util.visual.pil_image_utils import pil_image_scaling

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.generated_option_view'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ORIGINAL_CAPTION = _tr('Original')
ORIGINAL_TAG = _tr('Original')
SINGLE_VIEW_CAPTION = _tr('{label} of {count}')
COMPARE_HINT_CAPTION = _tr('Hold {key} to compare')
CLICK_TO_USE_HINT = _tr('Click to use')
GENERATING_TEXT = _tr('Generating')
WAITING_TEXT = _tr('Waiting')

CAPTION_HEIGHT = 24
CAPTION_PADDING = 6
FOCUS_RING_WIDTH = 3
CHIP_PADDING = 6
LOADING_SIZE_FRACTION = 0.4
LOADING_MIN_SIZE = 16
LOADING_MAX_SIZE = 96

VIEW_BACKGROUND = QColor(8, 9, 10)
CAPTION_BACKGROUND = QColor(36, 38, 42)
CAPTION_TEXT = QColor(235, 235, 230)
CAPTION_DIM_TEXT = QColor(160, 162, 166)
CHIP_BACKGROUND = QColor(13, 14, 16, 210)
FALLBACK_ACCENT = QColor(32, 160, 150)
FALLBACK_SIGNAL = QColor(208, 71, 58)


def _accent_color() -> QColor:
    return QApplication.palette().color(QPalette.ColorRole.Highlight) if ink_colors() is not None \
        else QColor(FALLBACK_ACCENT)


def _accent_wash() -> QColor:
    colors = ink_colors()
    if colors is not None:
        return colors.accent_wash
    wash = _accent_color()
    wash.setAlpha(110)
    return wash


def _signal_color() -> QColor:
    colors = ink_colors()
    return QColor(FALLBACK_SIGNAL) if colors is None else colors.signal


@dataclass
class OverlayState:
    """What `GeneratedOptionView` draws over its options. Lists are indexed like the view's options.

    - `ready` is False for a loading placeholder, and `generating` is True for a placeholder whose backend batch is
      running, as opposed to waiting its turn.
    - `single_view` dims every option but `focus_index`, and drops the grid's focus ring.
    - `comparing` tags the focused option as the original, which the selector shows in its place.
    - `margin_fraction` is the grid's margin between options, as a fraction of an option's shorter side.
    """
    focus_index: int = 0
    single_view: bool = False
    hover_index: Optional[int] = None
    comparing: bool = False
    ready: list[bool] = field(default_factory=list)
    generating: list[bool] = field(default_factory=list)
    compare_key: str = ''
    loading_design: LoadingDesign = field(default_factory=HalftonePress)
    loading_phase: float = 0.0
    margin_fraction: float = 0.0


class ImageOption(QGraphicsPixmapItem):
    """Displays a generated image option in the view, at the resolution `AppConfig.SHOW_OPTIONS_FULL_RESOLUTION`
    picks."""

    def __init__(self, image: QImage, label_text: str) -> None:
        super().__init__()
        # None until `full_image` first needs it, when `_scaled_image` is upscaled:
        self._full_image: Optional[QImage] = None
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
        final_size = Cache().get(Cache.EDIT_SIZE)
        self._scaled_image = edit_size_image(new_image)
        self._full_image = None if new_image.size() == final_size else new_image
        self.refresh_pixmap()

    def refresh_pixmap(self) -> None:
        """Shows the full or scaled image, as `AppConfig.SHOW_OPTIONS_FULL_RESOLUTION` picks."""
        self.setPixmap(QPixmap.fromImage(self.full_image if AppConfig().get(AppConfig.SHOW_OPTIONS_FULL_RESOLUTION)
                                         else self._scaled_image))
        self.update()

    @property
    def full_image(self) -> QImage:
        """Return the largest available version of this option's image."""
        if self._full_image is None:
            self._full_image = full_size_image(self._scaled_image)
        return self._full_image

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
        """Draws the image over a transparency pattern. `GeneratedOptionView` draws the caption."""
        assert painter is not None
        if self.opacity() == 1.0:
            painter.drawTiledPixmap(QRect(0, 0, self.width, self.height), self._transparency_pixmap)
        super().paint(painter, option, widget)


class GeneratedOptionView(ImageGraphicsView):
    """Shows the generated options, with the overlays `OverlayState` describes. The selector controls the view."""

    zoom_toggled = Signal()
    content_scrolled = Signal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.content_size = self.size()
        self._options: list[ImageOption] = []
        self._overlay = OverlayState()

    def set_options(self, options: list[ImageOption]) -> None:
        """Sets the option items to draw overlays for. The view reads the list as the owner changes it."""
        self._options = options

    def set_overlay_state(self, state: OverlayState) -> None:
        """Replaces what the overlays show, and redraws them."""
        self._overlay = state
        self.viewport().update()

    def scroll_content(self, dx: int | float, dy: int | float) -> bool:
        """Scroll content by the given offset, returning whether content was able to move."""
        self.content_scrolled.emit(int(dx), int(dy))
        return True

    def toggle_zoom(self) -> None:
        """Switch between the grid and single views. Bound to the 'Toggle Zoom' key."""
        self.zoom_toggled.emit()

    def drawBackground(self, painter: Optional[QPainter], rect: QRectF) -> None:
        """Fill with a near-black backdrop to increase visibility."""
        if painter is not None:
            painter.fillRect(rect, VIEW_BACKGROUND)
        super().drawBackground(painter, rect)

    def drawForeground(self, painter: Optional[QPainter], rect: QRectF) -> None:
        """Draws the cursor pixmap, then the overlays in viewport coordinates."""
        super().drawForeground(painter, rect)
        if painter is None or len(self._options) == 0 or len(self._overlay.ready) != len(self._options):
            return
        painter.save()
        painter.resetTransform()
        self._paint_overlays(painter)
        painter.restore()

    def _paint_overlays(self, painter: QPainter) -> None:
        """Draws the loading states, focus ring, captions and hover hint over the options.

        A caption goes under its image when the margin there fits it, and over the image's bottom edge otherwise.
        """
        state = self._overlay
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        viewport_rect = self.viewport().rect()
        font = QApplication.font()
        metrics = QFontMetrics(font)
        option_count = len(self._options) - 1
        image_size = self._options[0].size
        gap = min(image_size.width(), image_size.height()) * state.margin_fraction * self.scene_scale
        for i, item in enumerate(self._options):
            rect = self.scene_rect_to_widget_rect(QRectF(item.bounds))
            if not rect.intersects(viewport_rect):
                continue
            focused = i == state.focus_index
            if not state.ready[i]:
                self._paint_loading_cell(painter, rect, state.generating[i], font)
            if focused and not state.single_view:
                painter.setPen(QPen(_accent_color(), FOCUS_RING_WIDTH))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                half = FOCUS_RING_WIDTH / 2
                painter.drawRoundedRect(QRectF(rect).adjusted(-half - 1, -half - 1, half + 1, half + 1), 4, 4)
            if state.single_view and not focused:
                continue

            label = ORIGINAL_CAPTION if i == 0 else item.text
            if state.single_view and i != 0:
                label = SINGLE_VIEW_CAPTION.format(label=label, count=option_count)
                if not state.comparing:
                    label = f'{label}  \u00b7  {COMPARE_HINT_CAPTION.format(key=state.compare_key)}'
            visible = rect.intersected(viewport_rect)
            caption = QRect(visible.left(), rect.bottom() + 1, visible.width(), CAPTION_HEIGHT)
            if gap < CAPTION_HEIGHT + FOCUS_RING_WIDTH * 2 or caption.bottom() > viewport_rect.bottom():
                caption.moveBottom(visible.bottom())
            self._paint_caption(painter, caption, i, label, focused and not state.single_view, font)

            if state.comparing and focused:
                self._paint_chip(painter, ORIGINAL_TAG,
                                 QPoint(visible.left() + CHIP_PADDING, visible.top() + CHIP_PADDING),
                                 _signal_color(), font)
            elif i == state.hover_index and state.ready[i]:
                chip_width = metrics.horizontalAdvance(CLICK_TO_USE_HINT) + CHIP_PADDING * 4
                chip_pos = QPoint(rect.center().x() - chip_width // 2,
                                  caption.top() - metrics.height() - CHIP_PADDING * 3)
                self._paint_chip(painter, CLICK_TO_USE_HINT, chip_pos, CHIP_BACKGROUND, font)

    @staticmethod
    def _paint_caption(painter: QPainter, caption: QRect, index: int, label: str, highlighted: bool,
                       font: QFont) -> None:
        """Draws a caption bar with the option's digit key, if it has one, and its label."""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_accent_wash() if highlighted else CAPTION_BACKGROUND)
        painter.drawRect(caption)
        text_left = caption.left() + CAPTION_PADDING
        if index <= MAX_DIGIT_KEY:
            key_font = keycap_font(font)
            key_metrics = QFontMetrics(key_font)
            cap_size = keycap_size(QSize(key_metrics.horizontalAdvance(str(index)), key_metrics.height()))
            cap_rect = QRectF(text_left, caption.center().y() - cap_size.height() / 2 + 1, cap_size.width(),
                              cap_size.height())
            if cap_rect.right() < caption.right():
                fill, outline, text_color = keycap_colors(QApplication.palette())
                draw_keycap(painter, cap_rect, fill, outline)
                painter.setPen(text_color)
                painter.setFont(key_font)
                painter.drawText(cap_rect.adjusted(0, 0, 0, -KEYCAP_DEPTH), Qt.AlignmentFlag.AlignCenter, str(index))
                text_left = int(cap_rect.right()) + CAPTION_PADDING
        painter.setFont(font)
        painter.setPen(CAPTION_DIM_TEXT if index == 0 else CAPTION_TEXT)
        text_rect = QRect(text_left, caption.top(), caption.right() - text_left - CAPTION_PADDING, caption.height())
        elided = QFontMetrics(font).elidedText(label, Qt.TextElideMode.ElideRight, max(text_rect.width(), 0))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

    @staticmethod
    def _paint_chip(painter: QPainter, text: str, top_left: QPoint, background: QColor, font: QFont) -> None:
        metrics = QFontMetrics(font)
        chip = QRect(top_left, QSize(metrics.horizontalAdvance(text) + CHIP_PADDING * 4,
                                     metrics.height() + CHIP_PADDING * 2))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(chip), 4, 4)
        painter.setPen(CAPTION_TEXT)
        painter.setFont(font)
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_loading_cell(self, painter: QPainter, rect: QRect, generating: bool, font: QFont) -> None:
        """Draws the loading indicator over a placeholder, and whether it is generating or waiting."""
        design = self._overlay.loading_design
        side = int(min(rect.width(), rect.height()) * LOADING_SIZE_FRACTION)
        side = max(LOADING_MIN_SIZE, min(side, LOADING_MAX_SIZE))
        indicator = QRectF(rect.center().x() - side / 2, rect.center().y() - side / 2 - side / 4, side, side)
        painter.save()
        design.paint(painter, design.fit(indicator), self._overlay.loading_phase, True)
        painter.restore()
        painter.setFont(font)
        painter.setPen(CAPTION_DIM_TEXT)
        text_rect = QRect(rect.left(), int(indicator.bottom()) + CHIP_PADDING, rect.width(),
                          QFontMetrics(font).height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, GENERATING_TEXT if generating else WAITING_TEXT)
