from PyQt5.QtWidgets import QWidget, QDialog, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QSize, QRect, QPoint
from PyQt5.QtGui import QImage, QPainter, QPen
from inpainting.ui.widget.labeled_spinbox import LabeledSpinbox
from inpainting.ui.util.get_scaled_placement import getScaledPlacement
import math

class ResizeCanvasModal(QDialog):
    def __init__(self, qImage):
        super().__init__()

        self._resize = False
        self.setModal(True)

        title = QLabel(self)
        title.setText("Resize image canvas")

        # Main controls:
        minVal = 8
        maxVal = 20000
        currentWidth = qImage.width()
        currentHeight = qImage.height()

        self._widthBox = LabeledSpinbox(self, "Width:", "New image width in pixels", minVal, currentWidth, maxVal)
        self._heightBox = LabeledSpinbox(self, "Height:", "New image height in pixels", minVal, currentHeight, maxVal)
        self._xOffsetBox = LabeledSpinbox(self, "X Offset:", "Distance in pixels from the left edge of the resized "
                + "canvas to the left edge of the current image content", -currentWidth, 0, currentWidth)
        self._yOffsetBox = LabeledSpinbox(self, "Y Offset:", "Distance in pixels from the top edge of the resized "
                + "canvas to the top edge of the current image content", -currentHeight, 0, currentHeight)


        # Preview widget:
        class PreviewWidget(QWidget):
            def __init__(prev, parent):
                super().__init__(parent)
                prev.resizeEvent(None)

            def resizeEvent(prev, event):
                width = self._widthBox.spinbox.value()
                height = self._heightBox.spinbox.value()
                xOff = self._xOffsetBox.spinbox.value()
                yOff = self._yOffsetBox.spinbox.value()
                imageRect = QRect(0, 0, currentWidth, currentHeight)
                canvasRect = QRect(-xOff, -yOff, width, height)
                fullRect = imageRect.united(canvasRect)
                if (fullRect.x() != 0) or (fullRect.y() != 0):
                    offset = QPoint(-fullRect.x(), -fullRect.y())
                    for r in [fullRect, imageRect, canvasRect]:
                        r.translate(offset)
                drawArea = getScaledPlacement(QRect(0, 0, prev.width(), prev.height()), fullRect.size())
                scale = drawArea.width() / fullRect.width()
                def getDrawRect(src):
                    return QRect(drawArea.x() + int(src.x() * scale),
                            drawArea.y() + int (src.y() * scale),
                            int(src.width() * scale),
                            int(src.height() * scale))
                prev._imageBounds = getDrawRect(imageRect)
                prev._canvasBounds = getDrawRect(canvasRect)
                prev.update()

            def paintEvent(prev, event):
                painter = QPainter(prev)
                linePen = QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(linePen)
                painter.fillRect(prev._canvasBounds, Qt.darkGray)
                painter.drawImage(prev._imageBounds, qImage)
                painter.drawRect(prev._canvasBounds)
                painter.drawRect(prev._imageBounds)
        self._preview = PreviewWidget(self)

        def onDimChange(oldValue, newValue, labeledOffsetBox):
            labeledOffsetBox.spinbox.setRange(-oldValue, oldValue + newValue)
            self._preview.resizeEvent(None)

        self._widthBox.spinbox.valueChanged.connect(lambda w: onDimChange(currentWidth, w, self._xOffsetBox))
        self._heightBox.spinbox.valueChanged.connect(lambda h: onDimChange(currentHeight, h, self._yOffsetBox))
        for offset in [self._xOffsetBox, self._yOffsetBox]:
            offset.spinbox.valueChanged.connect(lambda v: self._preview.resizeEvent(None))

        centerButton = QPushButton(self)
        centerButton.setText("Center")
        def center():
            width = self._widthBox.spinbox.value()
            height = self._heightBox.spinbox.value()
            xOff = (width // 2) - (currentWidth // 2)
            yOff = (height // 2) - (currentHeight // 2)
            self._xOffsetBox.spinbox.setValue(xOff)
            self._yOffsetBox.spinbox.setValue(yOff)
        centerButton.clicked.connect(center)


        # Confirm / Cancel buttons:
        self._resizeButton = QPushButton(self)
        self._resizeButton.setText("Resize image canvas")
        def onResize():
            self._resize = True
            self.hide()
        self._resizeButton.clicked.connect(onResize)

        self._cancelButton = QPushButton(self)
        self._cancelButton.setText("Cancel")
        def onCancel():
            self._resize = False
            self.hide()
        self._cancelButton.clicked.connect(onCancel)

        optionBar = QWidget(self)
        optionBar.setLayout(QHBoxLayout())
        optionBar.layout().addWidget(self._cancelButton)
        optionBar.layout().addWidget(self._resizeButton)
        
        self._layout = QVBoxLayout()
        orderedWidgets = [
            title,
            self._widthBox,
            self._heightBox,
            self._xOffsetBox,
            self._yOffsetBox,
            self._preview,
            centerButton,
            optionBar
        ]

        for widget in orderedWidgets:
            self._layout.addWidget(widget)
        self.setLayout(self._layout)
        self.resizeEvent(None)

    def resizeEvent(self, event):
        minPreview = math.ceil(min(self.width(), self.height()) * 0.8)
        self._preview.setMinimumSize(QSize(minPreview, minPreview))

    def showResizeModal(self):
        self.exec_()
        if self._resize:
            newSize = QSize(self._widthBox.spinbox.value(), self._heightBox.spinbox.value())
            offset =  QPoint(self._xOffsetBox.spinbox.value(), self._yOffsetBox.spinbox.value())
            return newSize, offset
        return None, None
