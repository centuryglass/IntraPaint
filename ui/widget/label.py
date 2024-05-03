"""
An extended QLabel implementation that supports vertical text.
"""
from PyQt5.QtGui import QPainter, QPixmap, QPainterPath, QTransform, QFontMetrics, QFont, QPalette
from PyQt5.QtCore import Qt, QSize, QPointF
from PyQt5.QtWidgets import QLabel, QSizePolicy

class Label(QLabel):
    def __init__(
            self,
            text,
            config=None,
            parent=None,
            size=None,
            bg_color=Qt.transparent,
            orientation=Qt.Orientation.Vertical):
        super().__init__(parent)
        self._config = config
        self._size = size
        self._font = QFont()
        self._inverted = False
        self._icon = None
        self._image = None
        self._image_inverted = None
        self._orientation = None
        self._text = None
        self.setAutoFillBackground(True)
        self._bg_color = bg_color if bg_color is not None else self.palette().color(self.backgroundRole())
        self._fg_color = self.palette().color(self.foregroundRole())
        bg_color_name = bg_color if not hasattr(bg_color, 'name') else bg_color.name()
        fg_color_name = self._fg_color if not hasattr(self._fg_color, 'name') else self._fg_color.name()
        self._base_style = f"QLabel {{ background-color : {bg_color_name}; color : {fg_color_name}; }}"
        self._inverted_style = f"QLabel {{ background-color : {fg_color_name}; color : {bg_color_name}; }}"
        self.setStyleSheet(self._base_style)
        if size is not None:
            self._font.setPointSize(size)
        elif config is not None:
            font_size = config.get("fontPointSize")
            self._font.setPointSize(font_size)
        self.set_orientation(orientation)
        self.setText(text)
   
    def set_orientation(self, orientation):
        if self._orientation == orientation:
            return
        self._orientation = orientation
        if self._orientation == Qt.Orientation.Vertical:
            self.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        else:
            self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        if self._text is not None and self._image is not None:
            self._image, self._image_inverted = self._draw_text_pixmaps()
            self._merge_text_and_icon()

    def set_inverted(self, invert_colors):
        if invert_colors == self._inverted:
            return
        self.setStyleSheet(self._inverted_style if invert_colors else self._base_style)
        self._inverted = invert_colors
        self.setPixmap(self._image_inverted if invert_colors else self._image)
        self.update()
    
    def sizeHint(self):
        return QSize(self._image.width() + 4, self._image.height() + 4)

    def setText(self, text):
        if text == self._text:
            return
        self._text = text

        self._image, self._image_inverted = self._draw_text_pixmaps()
        self._merge_text_and_icon()

    def setIcon(self, icon):
        if self._icon is not None:
            self._image, self._image_inverted = self._draw_text_pixmaps()
        if isinstance(icon, str):
            icon = QPixmap(icon)
        self._icon = icon
        self._merge_text_and_icon()

    def _draw_text_pixmaps(self):
        drawn_text = "     " if self._text is None else (self._text + "     ")
        text_bounds = QFontMetrics(self._font).boundingRect(drawn_text)
        w = int(text_bounds.height() * 1.3) if self._orientation == Qt.Orientation.Vertical else text_bounds.width()
        h = text_bounds.width() if self._orientation == Qt.Orientation.Vertical else int(text_bounds.height() * 1.3)
        image_size = QSize(w, h)

        path = QPainterPath()
        text_pt = QPointF(0, -(text_bounds.height() * 0.3)) if self._orientation == Qt.Orientation.Vertical \
                else QPointF(0, text_bounds.height())
        path.addText(text_pt, self._font, drawn_text)
        if self._orientation == Qt.Orientation.Vertical:
            rotation = QTransform()
            rotation.rotate(90)
            path = rotation.map(path)

        def draw(bg, fg):
            image = QPixmap(image_size)
            image.fill(bg)
            painter = QPainter(image)
            painter.fillPath(path, fg)
            painter.end()
            return image
        image, inverted = (draw(bg, fg) for (bg, fg) in ((self._bg_color, self._fg_color), (self._fg_color, self._bg_color)))
        return image, inverted

    def _merge_text_and_icon(self):
        if self._icon is not None:
            scaled_icon = self._icon.scaledToWidth(self._image.width()) if self._orientation == Qt.Orientation.Vertical\
                    else self._icon.scaledToHeight(self._image.height())
            icon_padding = (self._image.width() if self._orientation == Qt.Orientation.Vertical \
                    else self._image.height()) // 3
            new_size = QSize(self._image.width(), self._image.height())
            if self._orientation == Qt.Orientation.Vertical:
                new_size.setHeight(new_size.height() + icon_padding + scaled_icon.height())
            else: 
                new_size.setWidth(new_size.width() + icon_padding + scaled_icon.width())

            def draw(text_image):
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

    def image_size(self):
        return self._image.size()
