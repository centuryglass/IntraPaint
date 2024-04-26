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
            bgColor=Qt.transparent,
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
        self._bgColor = bgColor if bgColor is not None else self.palette().color(self.backgroundRole())
        self._fgColor = self.palette().color(self.foregroundRole())
        bgColorName = bgColor if not hasattr(bgColor, 'name') else bgColor.name()
        fgColorName = self._fgColor if not hasattr(self._fgColor, 'name') else self._fgColor.name()
        self._baseStyle = f"QLabel {{ background-color : {bgColorName}; color : {fgColorName}; }}"
        self._invertedStyle = f"QLabel {{ background-color : {fgColorName}; color : {bgColorName}; }}"
        self.setStyleSheet(self._baseStyle)
        if size is not None:
            self._font.setPointSize(size)
        elif config is not None:
            fontSize = config.get("fontPointSize")
            self._font.setPointSize(fontSize)
        self.setOrientation(orientation)
        self.setText(text)
   
    def setOrientation(self, orientation):
        if self._orientation == orientation:
            return
        self._orientation = orientation
        if self._orientation == Qt.Orientation.Vertical:
            self.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        else:
            self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        if self._text is not None and self._image is not None:
            self._image, self._image_inverted = self._drawTextPixmaps()
            self._mergeTextAndIcon()

    def setInverted(self, invertColors):
        if invertColors == self._inverted:
            return
        self.setStyleSheet(self._invertedStyle if invertColors else self._baseStyle)
        self._inverted = invertColors
        self.setPixmap(self._image_inverted if invertColors else self._image)
        self.update()
    
    def sizeHint(self):
        return QSize(self._image.width() + 4, self._image.height() + 4)

    def setText(self, text):
        if text == self._text:
            return
        self._text = text

        self._image, self._image_inverted = self._drawTextPixmaps()
        self._mergeTextAndIcon()

    def setIcon(self, icon):
        if self._icon is not None:
            self._image, self._image_inverted = self._drawTextPixmaps()
        if isinstance(icon, str):
            icon = QPixmap(icon)
        self._icon = icon
        self._mergeTextAndIcon()

    def _drawTextPixmaps(self):
        drawnText = "   " if self._text is None else (self._text + "   ")
        textBounds = QFontMetrics(self._font).boundingRect(drawnText)
        w = int(textBounds.height() * 1.3) if self._orientation == Qt.Orientation.Vertical else textBounds.width()
        h = textBounds.width() if self._orientation == Qt.Orientation.Vertical else int(textBounds.height() * 1.3)
        imageSize = QSize(w, h)

        path = QPainterPath()
        textPt = QPointF(0, -(textBounds.height() * 0.3)) if self._orientation == Qt.Orientation.Vertical \
                else QPointF(0, textBounds.height())
        path.addText(textPt, self._font, drawnText)
        if self._orientation == Qt.Orientation.Vertical:
            rotation = QTransform()
            rotation.rotate(90)
            path = rotation.map(path)

        def draw(bg, fg):
            image = QPixmap(imageSize)
            image.fill(bg)
            painter = QPainter(image)
            painter.fillPath(path, fg)
            painter.end()
            return image
        image, inverted = (draw(bg, fg) for (bg, fg) in ((self._bgColor, self._fgColor), (self._fgColor, self._bgColor)))
        return image, inverted

    def _mergeTextAndIcon(self):
        if self._icon is not None:
            
            scaledIcon = self._icon.scaledToWidth(self._image.width()) if self._orientation == Qt.Orientation.Vertical\
                    else self._icon.scaledToHeight(self._image.height())
            iconPadding = (self._image.width() if self._orientation == Qt.Orientation.Vertical \
                    else self._image.height()) // 3
            newSize = QSize(self._image.width(), self._image.height())
            if self._orientation == Qt.Orientation.Vertical:
                newSize.setHeight(newSize.height() + iconPadding + scaledIcon.height())
            else: 
                newSize.setWidth(newSize.width() + iconPadding + scaledIcon.width())

            def draw(textImage):
                mergedImage = QPixmap(newSize)
                mergedImage.fill(self._bgColor if textImage == self._image else self._fgColor)
                painter = QPainter(mergedImage)
                painter.drawPixmap(0, 0, self._icon)
                if self._orientation == Qt.Orientation.Vertical:
                    painter.drawPixmap(0, self._icon.height() + iconPadding, textImage)
                else: 
                    painter.drawPixmap(self._icon.width() + iconPadding, 0, textImage)
                painter.end()
                return mergedImage
            self._image, self._image_inverted = (draw(img) for img in (self._image, self._image_inverted))
        if self._orientation == Qt.Orientation.Vertical:
            self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.MinimumExpanding))
        else:
            self.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.setPixmap(self._image_inverted if self._inverted else self._image)
        self.update()

    def imageSize(self):
        return self._image.size()
