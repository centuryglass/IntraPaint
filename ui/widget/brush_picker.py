from PyQt5.QtWidgets import QWidget, QTabWidget, QGridLayout, QScrollArea, QSizePolicy
from PyQt5.QtGui import QPixmap, QImage, QPainter
from PyQt5.QtCore import Qt, QRect
from data_model.canvas.brushlib import Brushlib
from ui.util.get_scaled_placement import getScaledPlacement
import os

class IconButton(QWidget):
    def __init__(self, parent, imagepath, brushpath):
        super().__init__(parent)
        self._brushpath = brushpath
        self._imageRect = None
        self._image = QPixmap(imagepath)
        inverted = QImage(imagepath)
        inverted.invertPixels(QImage.InvertRgba)
        self._image_inverted = QPixmap.fromImage(inverted)
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        sizePolicy.setWidthForHeight(True)
        self.setSizePolicy(sizePolicy)
        self.resizeEvent(None)

    def sizeHint(self):
        return self._image.size()

    def isSelected(self):
        activeBrush = Brushlib.getActiveBrush()
        return activeBrush is not None and activeBrush == self._brushpath

    def resizeEvent(self, event):
        self._imageRect = getScaledPlacement(QRect(0, 0, self.width(), self.height()), self._image.size())


    def paintEvent(self, event):
        painter = QPainter(self)
        if self.isSelected():
            painter.drawPixmap(self._imageRect, self._image_inverted)
        else:
            painter.drawPixmap(self._imageRect, self._image)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.isSelected() and self._imageRect.contains(event.pos()):
            Brushlib.loadBrush(self._brushpath)
            self.parent().update()

class BrushPicker(QTabWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        brushDir = './resources/brushes'
        for category in os.listdir(brushDir):
            categoryDir = os.path.join(brushDir, category)
            if not os.path.isdir(categoryDir):
                continue
            categoryTab = QScrollArea(self)
            categoryTab.setWidgetResizable(True)
            categoryContent = QWidget(categoryTab)
            categoryTab.setWidget(categoryContent)
            categoryLayout = QGridLayout()
            categoryContent.setLayout(categoryLayout)
            x=0
            y=0
            width=5
            for file in os.listdir(categoryDir):
                if not file.endswith(".myb"):
                    continue
                brushname = file[:-4]
                brushpath = os.path.join(categoryDir, file)
                imagepath = os.path.join(categoryDir, brushname + "_prev.png")
                brushIcon = IconButton(categoryContent, imagepath, brushpath)
                categoryLayout.addWidget(brushIcon, y, x)
                x += 1
                if x >= width:
                    y += 1
                    x = 0
            self.addTab(categoryTab, category)

