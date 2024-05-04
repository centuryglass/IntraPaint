"""
Selects between the default mypaint brushes found in resources/brushes. This widget can only be used if a compatible
brushlib/libmypaint QT library is available, currently only true for x86_64 Linux.
"""
from PyQt5.QtWidgets import QWidget, QTabWidget, QGridLayout, QScrollArea, QSizePolicy
from PyQt5.QtGui import QPixmap, QImage, QPainter
from PyQt5.QtCore import Qt, QRect
from brushlib import MPBrushLib as brushlib
from ui.util.get_scaled_placement import get_scaled_placement
import os

class IconButton(QWidget):
    def __init__(self, parent, imagepath, brushpath):
        super().__init__(parent)
        self._brushpath = brushpath
        self._image_rect = None
        self._image = QPixmap(imagepath)
        inverted = QImage(imagepath)
        inverted.invertPixels(QImage.InvertRgba)
        self._image_inverted = QPixmap.fromImage(inverted)
        size_policy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        size_policy.setWidthForHeight(True)
        self.setSizePolicy(size_policy)
        self.resizeEvent(None)

    def sizeHint(self):
        return self._image.size()

    def is_selected(self):
        activeBrush = brushlib.get_active_brush()
        return activeBrush is not None and activeBrush == self._brushpath

    def resizeEvent(self, event):
        self._image_rect = get_scaled_placement(QRect(0, 0, self.width(), self.height()), self._image.size())


    def paintEvent(self, event):
        painter = QPainter(self)
        if self.is_selected():
            painter.drawPixmap(self._image_rect, self._image_inverted)
        else:
            painter.drawPixmap(self._image_rect, self._image)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self.is_selected() and self._image_rect.contains(event.pos()):
            brushlib.load_brush(self._brushpath)
            self.parent().update()

class BrushPicker(QTabWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        brushDir = './resources/brushes'
        for category in os.listdir(brushDir):
            category_dir = os.path.join(brushDir, category)
            if not os.path.isdir(category_dir):
                continue
            category_tab = QScrollArea(self)
            category_tab.setWidgetResizable(True)
            category_content = QWidget(category_tab)
            category_tab.setWidget(category_content)
            category_layout = QGridLayout()
            category_content.setLayout(category_layout)
            x=0
            y=0
            width=5
            for file in os.listdir(category_dir):
                if not file.endswith(".myb"):
                    continue
                brush_name = file[:-4]
                brush_path = os.path.join(category_dir, file)
                image_path = os.path.join(category_dir, brush_name + "_prev.png")
                brush_icon = IconButton(category_content, image_path, brush_path)
                category_layout.addWidget(brush_icon, y, x)
                x += 1
                if x >= width:
                    y += 1
                    x = 0
            self.addTab(category_tab, category)

