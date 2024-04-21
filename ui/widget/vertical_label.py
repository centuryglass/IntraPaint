from PyQt5.QtGui import QPainter, QPixmap, QPainterPath, QTransform, QFontMetrics, QFont
from PyQt5.QtCore import Qt, QSize, QPointF
from PyQt5.QtWidgets import QLabel

class VerticalLabel(QLabel):
    def __init__(self, text, config=None, parent=None, size=None, bgColor=Qt.transparent):
        super().__init__(parent)
        self._config = config
        self._size = size
        self._font = QFont()
        self._image = None
        self._bgColor = bgColor
        if size is not None:
            self._font.setPointSize(size)
        elif config is not None:
            fontSize = config.get("fontPointSize")
            self._font.setPointSize(fontSize)
        self._text = None
        self.setText(text)

    def setText(self, text):
        if text == self._text:
            return
        self._text = text
        textBounds = QFontMetrics(self._font).boundingRect(text)
        imageSize = QSize(int(textBounds.height() * 1.5), textBounds.width())
        if self._image is None or imageSize != self._image.size():
            self._image = QPixmap(imageSize)
        self._image.fill(self._bgColor)
        path = QPainterPath()
        path.addText(QPointF(0, -(textBounds.height() * 0.3)), self._font, text)
        rotation = QTransform()
        rotation.rotate(90)
        path = rotation.map(path)

        color = self.palette().color(self.foregroundRole())
        painter = QPainter(self._image)
        painter.fillPath(path, color)
        painter.end()

        self.setPixmap(self._image)

    def imageSize(self):
        return self._image.size()
