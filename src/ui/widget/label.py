"""
An extended QLabel implementation that supports vertical text.
"""
from typing import Optional

from PyQt5.QtCore import Qt, QSize, QPointF
from PyQt5.QtGui import QPainter, QPixmap, QPainterPath, QTransform, QFont, QColor
from PyQt5.QtWidgets import QLabel, QSizePolicy, QWidget

from src.config.application_config import AppConfig
from src.util.font_size import find_text_size


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
        config = AppConfig.instance()
        self._size = size
        self._font = QFont()
        self._inverted: Optional[bool] = False
        self._icon: Optional[QPixmap] = None
        self._image: Optional[QPixmap] = None
        self._image_inverted: Optional[QPixmap] = None
        self._orientation: Optional[Qt.Orientation] = None
        self._text: Optional[str] = None
        self.setAutoFillBackground(True)
        self._bg_color = bg_color if bg_color is not None else self.palette().color(self.backgroundRole())
        self._fg_color = self.palette().color(self.foregroundRole())
        bg_color_name = bg_color if not hasattr(bg_color, 'name') else bg_color.name()
        fg_color_name = self._fg_color if not hasattr(self._fg_color, 'name') else self._fg_color.name()
        self._base_style = f'QLabel {{ background-color : {bg_color_name}; color : {fg_color_name}; }}'
        self._inverted_style = f'QLabel {{ background-color : {fg_color_name}; color : {bg_color_name}; }}'
        self.setStyleSheet(self._base_style)
        if size is not None:
            self._font.setPointSize(size)
        else:
            font_size = config.get(AppConfig.FONT_POINT_SIZE)
            self._font.setPointSize(font_size)
        self.set_orientation(orientation)
        self.setText(text)

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
        self.setStyleSheet(self._inverted_style if invert_colors else self._base_style)
        self._inverted = invert_colors
        self.setPixmap(self._image_inverted if invert_colors else self._image)
        self.update()

    def sizeHint(self) -> QSize:
        """Calculate ideal widget size based on text size."""
        assert self._image is not None
        return QSize(self._image.width() + 4, self._image.height() + 4)

    def setText(self, text: Optional[str]) -> None:
        """Changes the displayed text string"""
        if text == self._text:
            return
        self._text = text

        self._image, self._image_inverted = self._draw_text_pixmaps()
        self._merge_text_and_icon()

    # noinspection PyPep8Naming
    def setIcon(self, icon: QPixmap | str) -> None:
        """Adds an icon to the label before its text.

        Parameters
        ----------
        icon : QPixmap or str
            If icon is a string, it should be a path to a valid image file.
        """
        if self._icon is not None:
            self._image, self._image_inverted = self._draw_text_pixmaps()
        if isinstance(icon, str):
            icon = QPixmap(icon)
        if not isinstance(icon, QPixmap):
            raise TypeError(f'Icon should be image path or QPixmap, icon={icon}')
        self._icon = icon
        self._merge_text_and_icon()

    def _draw_text_pixmaps(self) -> tuple[QPixmap, QPixmap]:
        """Re-renders the label text."""
        drawn_text = '     ' if self._text is None else (self._text + '     ')
        text_size = find_text_size(drawn_text, self._font)
        w = int(text_size.height() * 1.3) if self._orientation == Qt.Orientation.Vertical else text_size.width()
        h = text_size.width() if self._orientation == Qt.Orientation.Vertical else int(text_size.height() * 1.3)
        image_size = QSize(w, h)

        path = QPainterPath()
        text_pt = QPointF(0, -(text_size.height() * 0.3)) if self._orientation == Qt.Orientation.Vertical \
            else QPointF(0, text_size.height())
        path.addText(text_pt, self._font, drawn_text)
        if self._orientation == Qt.Orientation.Vertical:
            rotation = QTransform()
            rotation.rotate(90)
            path = rotation.map(path)

        def draw(bg: QColor | Qt.GlobalColor, fg: QColor | Qt.GlobalColor) -> QPixmap:
            """Perform drawing operations on one of the internal label images."""
            label_image = QPixmap(image_size)
            label_image.fill(bg)
            painter = QPainter(label_image)
            painter.setRenderHint(QPainter.RenderHint.LosslessImageRendering, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.fillPath(path, fg)
            painter.end()
            return label_image

        image, inverted = (draw(bg, fg) for (bg, fg) in ((self._bg_color, self._fg_color),
                                                         (self._fg_color, self._bg_color)))
        return image, inverted

    def _merge_text_and_icon(self) -> None:
        """Combines the text and icon into a single internal image."""
        assert self._image is not None and self._image_inverted is not None
        if self._icon is not None:
            if self._orientation == Qt.Orientation.Vertical:
                scaled_icon = self._icon.scaledToWidth(self._image.width())
            else:
                scaled_icon = self._icon.scaledToHeight(self._image.height())
            icon_padding = (self._image.width() if self._orientation == Qt.Orientation.Vertical
                            else self._image.height()) // 3
            new_size = QSize(self._image.width(), self._image.height())
            if self._orientation == Qt.Orientation.Vertical:
                new_size.setHeight(new_size.height() + icon_padding + scaled_icon.height())
            else:
                new_size.setWidth(new_size.width() + icon_padding + scaled_icon.width())

            def draw(text_image: QPixmap) -> QPixmap:
                """Perform drawing operations on one of the internal label images."""
                assert self._icon is not None
                merged_image = QPixmap(new_size)
                merged_image.fill(self._bg_color if text_image == self._image else self._fg_color)
                painter = QPainter(merged_image)
                painter.drawPixmap(0, 0, self._icon)
                if self._orientation == Qt.Orientation.Vertical:
                    painter.drawPixmap(0, self._icon.height() + icon_padding, text_image)
                else:
                    painter.drawPixmap(self._icon.width() + icon_padding, 0, text_image)
                painter.end()
                return merged_image

            self._image, self._image_inverted = (draw(img) for img in (self._image, self._image_inverted))
        if self._orientation == Qt.Orientation.Vertical:
            self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding))
        else:
            self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.setPixmap(self._image_inverted if self._inverted else self._image)
        self.update()

    def image_size(self) -> QSize:
        """Returns the size of the label's internal image representation."""
        assert self._image is not None
        return self._image.size()
