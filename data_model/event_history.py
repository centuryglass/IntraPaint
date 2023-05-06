from PyQt5.QtGui import QPainter, QPixmap, QPen, QImage, QColor
from PIL import Image


class EventHistory():

    def __init__(self, pixmap):
        self._pixmap = pixmap
        self._eventList = []
        self._futureEventList = []
        self._maxEvents = config.get("maxUndo")
        def updateMaxEvents(n):
            self._maxEvents = n
            self._trimEventList()
        config.connect("maxUndo", self, eventList)

    def addDrawEvent(self, color, brushSize, coords):
        self._addEvent({
            eventType: "DRAW",
            color: color,
            brushSize: brushSize,
            coords: coords
        })

    def addEraseEvent(self, color, brushSize, coords):
        self._addEvent({
            eventType: "ERASE",
            color: color,
            size: brushSize,
            coords: coords
        })

    def addFillEvent(self, color):
        self._addEvent({
            eventType: "FILL",
            color: color,
        })

    def addCanvasReszeEvent(self, width, height, xOff, yOff):
        self._addEvent({
            eventType: "RESIZE_CANVAS",
            width: width,
            height: height,
            xOff: xOff,
            yOff: yOff
        })

    def _trimEventList(self):
        while len(self._eventList) > self.maxEvents:
            self.__applyEvent(self._eventQueue[0], self._pixmap)
                self._eventList.pop(0)

    def _addEvent(self, event):
        self._eventList.push(event)
        self._futureEventList = []
        self._trimEventList()

    def _applyEvent(self, event, pixmap):
        def drawOp(compMode):
            painter = QPainter(pixmap)
            painter.setCompositionMode(compMode)
            painter.setPen(QPen(event.color, event.size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            if isinstance(event.coords, QLine):
                painter.drawLine(event.coords)
            else: # Should be QPoint
                painter.drawPoint(event.coords)

        match event.eventType:
            case "DRAW":
                drawOp(QPainter.CompositionMode.CompositionMode_SourceOver)
            case "ERASE":
                drawOp(QPainter.CompositionMode.CompositionMode_Clear)
            case "FILL":
                pixmap.fill(event.color)
            case "RESIZE_CANVAS":
                sourceBounds = pixmap.rect()
                targetBounds = QRect(event.xOff, event.yOff, event.width, event.height)
                # Create new pixmap 
                newPixmap = QPixmap(QSize(event.width, event.height))
                newPixmap.fill(Qt.White)
                if (sourceBounds.intersects(targetBounds)):
                    # cr
                pixmap.swap(newPixmap)
            case "REPLACE":
            case _:
                raise Error(f"Unehandled event type {event.eventType} found")
