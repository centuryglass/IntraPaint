"""
An extended QLabel implementation that supports vertical text.
"""
from typing import Optional

from PySide6.QtCore import Qt, QSize, QMargins, QRect, QPoint
from PySide6.QtGui import QPainter, QPixmap, QFont, QColor, QPalette, QIcon, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from src.util.visual.text_drawing_utils import find_text_size, max_font_size, create_text_path, draw_text_path

TEXT_IMG_MARGIN = 4


class Label(QLabel):
    """Label is an extended QLabel implementation that supports vertical text."""

    def __init__(
            self,
            text: str,
            parent: Optional[QWidget] = None,
            size: Optional[int] = None,
            bg_color: QColor | Qt.GlobalColor = Qt.GlobalColor.transparent,
            orientation: Qt.Orientation = Qt.Orientation.Vertical):
        """__init__.

        Parameters
        ----------
        text : str
            Initial label text.
        parent : QWidget, optional, default=None
            Optional parent widget
        size : int
            Font point size.
        bg_color : QColor, default=Qt.transparent
            Label background color
        orientation : Qt.Orientation, default=Vertical
            Initial orientation.
        """
        super().__init__(parent)
        self._size = size
        self._font = QFont()
        self._scale_text_to_bounds = False
        self._inverted: Optional[bool] = False
        self._icon: Optional[QPixmap] = None
        self._image: Optional[QPixmap] = None
        self._image_inverted: Optional[QPixmap] = None
        self._orientation: Optional[Qt.Orientation] = None
        self._text: Optional[str] = None
        self.setAutoFillBackground(True)
        self._bg_color = bg_color if bg_color is not None else self.palette().color(self.backgroundRole())
        self._fg_color = self.palette().color(self.foregroundRole())
        self._base_palette = QPalette(self.palette())
        self._base_palette.setColor(self.backgroundRole(), self._bg_color)
        self._base_palette.setColor(self.foregroundRole(), self._fg_color)
        self._inverted_palette = QPalette(self.palette())
        self._inverted_palette.setColor(self.backgroundRole(), self._fg_color)
        self._inverted_palette.setColor(self.foregroundRole(), self._bg_color)
        self.setPalette(self._base_palette)
        if size is not None:
            self._font.setPointSize(size)
        self.set_orientation(orientation)
        self.setText(text)

    def set_scale_to_bounds(self, should_scale: bool) -> None:
        """Sets whether text to be scaled to fit available bounds."""
        if should_scale != self._scale_text_to_bounds:
            self._scale_text_to_bounds = should_scale
            text = self._text
            self.setText('')
            self.setText(text)

    @property
    def orientation(self) -> Qt.Orientation:
        """Returns the label's orientation."""
        return self._orientation

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        """Sets the label's text orientation."""
        if self._orientation == orientation:
            return
        self._orientation = orientation
        if self._orientation == Qt.Orientation.Vertical:
            self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        else:
            self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if self._text is not None and self._image is not None:
            self._image, self._image_inverted = self._draw_text_pixmaps()
            self._merge_text_and_icon()

    def set_inverted(self, invert_colors: bool) -> None:
        """Sets whether the label should be drawn using inverted colors."""
        if invert_colors == self._inverted:
            return
        assert self._image is not None and self._image_inverted is not None
        self.setPalette(self._inverted_palette if invert_colors else self._base_palette)
        self._inverted = invert_colors
        self.setPixmap(self._image_inverted if invert_colors else self._image)
        self.update()

    def sizeHint(self) -> QSize:
        """Calculate ideal widget size based on text size."""
        assert self._image is not None
        if self._scale_text_to_bounds:
            text_size = find_text_size(self._text or '', self._font)
            if self._icon is not None:
                text_size.setWidth(text_size.width() + text_size.height())
            if self._orientation == Qt.Orientation.Vertical:
                text_size.transpose()
            return text_size
        return QSize(self._image.width(), self._image.height())

    def text(self) -> str:
        """Return the current displayed string"""
        return '' if self._text is None else self._text

    def setText(self, text: Optional[str]) -> None:
        """Changes the displayed text string"""
        if text == self._text and not self._scale_text_to_bounds:
            return
        self._text = text

        self._image, self._image_inverted = self._draw_text_pixmaps()
        self._merge_text_and_icon()

    # noinspection PyPep8Naming
    def setIcon(self, icon: QPixmap | QIcon | str) -> None:
        """Adds an icon to the label before its text.

        Parameters
        ----------
        icon : QPixmap or QIcon or str
            If icon is a string, it should be a path to a valid image file.
        """
        if self._icon is not None:
            self._image, self._image_inverted = self._draw_text_pixmaps()
        if isinstance(icon, str):
            icon = QPixmap(icon)
        elif isinstance(icon, QIcon):
            icon = icon.pixmap(QSize(256, 256))
        if not isinstance(icon, QPixmap):
            raise TypeError(f'Icon should be image path or QPixmap, icon={icon}')
        self._icon = icon
        self._merge_text_and_icon()

    def _draw_text_pixmaps(self) -> tuple[QPixmap, QPixmap]:
        """Re-renders the label text."""
        drawn_text = '     ' if self._text is None else (self._text)
        font = QFont(self._font)
        if self._scale_text_to_bounds:
            text_size = self.size().transposed() if self._orientation == Qt.Orientation.Vertical else self.size()
            text_size.setWidth(text_size.width() - 2 * TEXT_IMG_MARGIN)
            text_size.setHeight(text_size.height() - 2 * TEXT_IMG_MARGIN)
            font_size = max_font_size(drawn_text, font, text_size)
            font.setPointSize(font_size)
        else:
            text_size = find_text_size(drawn_text, font, True, orientation=self._orientation)
        image_size = QSize(text_size)
        if image_size.isEmpty() or text_size.isEmpty():
            return QPixmap(), QPixmap()
        image_size.setWidth(image_size.width() + 2 * TEXT_IMG_MARGIN)
        image_size.setHeight(image_size.height() + 2 * TEXT_IMG_MARGIN)
        margins = QMargins(TEXT_IMG_MARGIN, TEXT_IMG_MARGIN, TEXT_IMG_MARGIN, TEXT_IMG_MARGIN)
        text_path = create_text_path(drawn_text, font, QRect(QPoint(), image_size), self.alignment(), margins,
                                     self._orientation)

        def draw(bg: QColor | Qt.GlobalColor, fg: QColor | Qt.GlobalColor) -> QPixmap:
            """Perform drawing operations on one of the internal label images."""
            label_image = QPixmap(image_size)
            label_image.fill(bg)
            painter = QPainter(label_image)
            draw_text_path(text_path, painter, fg)
            painter.end()
            return label_image

        image, inverted = (draw(bg, fg) for (bg, fg) in ((self._bg_color, self._fg_color),
                                                         (self._fg_color, self._bg_color)))
        return image, inverted

    def _merge_text_and_icon(self) -> None:
        """Combines the text and icon into a single internal image."""
        assert self._image is not None and self._image_inverted is not None
        if self._icon is not None:
            text_padding = self._image.width() // 3 if self._orientation == Qt.Orientation.Vertical  \
                else self._image.height() // 3
            icon_padding = 2
            if self._orientation == Qt.Orientation.Vertical:
                scaled_icon = self._icon.scaledToWidth(self._image.width() - (2 * icon_padding),
                                                       Qt.TransformationMode.SmoothTransformation)
            else:
                scaled_icon = self._icon.scaledToHeight(self._image.height() - (2 * icon_padding),
                                                        Qt.TransformationMode.SmoothTransformation)
            new_size = QSize(self._image.width(), self._image.height())
            if self._orientation == Qt.Orientation.Vertical:
                new_size.setHeight(new_size.height() + 2 * icon_padding + text_padding + scaled_icon.height())
            else:
                new_size.setWidth(new_size.width() + 2 * icon_padding + text_padding + scaled_icon.width())

            def draw(text_image: QPixmap) -> QPixmap:
                """Perform drawing operations on one of the internal label images."""
                merged_image = QPixmap(new_size)
                merged_image.fill(self._bg_color if text_image == self._image else self._fg_color)
                painter = QPainter(merged_image)
                painter.setRenderHint(QPainter.RenderHint.LosslessImageRendering, True)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.drawPixmap(icon_padding, icon_padding, scaled_icon)
                if self._orientation == Qt.Orientation.Vertical:
                    painter.drawPixmap(0, scaled_icon.height() + icon_padding * 2 + text_padding, text_image)
                else:
                    painter.drawPixmap(scaled_icon.width() + icon_padding * 2 + text_padding, 0, text_image)
                painter.end()
                return merged_image

            self._image, self._image_inverted = (draw(img) for img in (self._image, self._image_inverted))
        if self._orientation == Qt.Orientation.Vertical:
            self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding))
        else:
            self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed))
        self.setPixmap(self._image_inverted if self._inverted else self._image)
        self.update()

    def image_size(self) -> QSize:
        """Returns the size of the label's internal image representation."""
        assert self._image is not None
        return self._image.size()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """If scaling text to bounds, redraw text when bounds change."""
        if self._scale_text_to_bounds:
            self.setText(self._text)
