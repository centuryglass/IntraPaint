# Supports panning via spacemouse, if applicable
try:
    import spacenav, atexit, time, math
except ImportError:
    print('spaceMouse support not installed.')
    spacenav = None
from PyQt5.QtCore import QObject, QThread, QRect, QSize, pyqtSignal
from threading import Lock


class SpacenavManager():
    def __init__(self, window, editedImage):
        if spacenav is None:
            return
        self._window = window
        self._editedImage = editedImage
        self._threadData = {
            'readEvents': True,
            'pending': False,
            'x': 0,
            'y': 0,
            'w_image': 0,
            'h_image': 0,
            'w_sel': 0,
            'h_sel': 0,
            'speed': 1,
            'lock': Lock()
        }
        self._thread = None

        def updateImageSize(size):
            with self._threadData['lock']:
                if size.width() != self._threadData['w_image']:
                    self._threadData['w_image'] = size.width()
                if size.height() != self._threadData['h_image']:
                    self._threadData['h_image'] = size.height()
        self._editedImage.sizeChanged.connect(updateImageSize)

        def updateSelectionSize(bounds):
            with self._threadData['lock']:
                if bounds.width() != self._threadData['w_sel']:
                    self._threadData['w_sel'] = bounds.width()
                if bounds.height() != self._threadData['h_sel']:
                    self._threadData['h_sel'] = bounds.height()
        self._editedImage.selectionChanged.connect(updateSelectionSize)

        def stopLoop():
            with self._threadData['lock']:
                self._threadData['readEvents'] = False
        atexit.register(stopLoop)


        manager = self
        class SpacenavThreadWorker(QObject):
            navEventSignal = pyqtSignal(int, int)
            def __init__(self):
                super().__init__()

            def run(self):
                print("Loading optional space mouse support for panning:")
                try:
                    spacenav.open()
                    atexit.register(spacenav.close)
                except spacenav.ConnectionError:
                    print("spacenav connection failed, space mouse will not be used.")
                    return
                print("spacenav connection started.")

                def sendNavSignal():
                    # Once the xy offset of sequential spacenav events adds up to this value, the selection window will
                    # reach max scrolling speed:
                    MAX_SPEED_AT_OFFSET = 9000
                    # Controls how quickly the selection will move across the entire image at max speed:
                    # Values must >= 0.  The higher the value, the slower the max speed will be.
                    MAX_SPEED_CONTROL = 1
                    x = 0
                    y = 0
                    w_image = 0
                    h_image = 0
                    w_sel = 0
                    h_sel = 0
                    speed = 0
                    with manager._threadData['lock']:
                        if manager._threadData['pending']:
                            return
                        if any(manager._threadData[dim] == 0 for dim in ['w_sel', 'h_sel', 'w_image', 'h_image']):
                            return
                        x = manager._threadData['x']
                        y = manager._threadData['y']
                        w_image = manager._threadData['w_image']
                        h_image = manager._threadData['h_image']
                        w_sel = manager._threadData['w_sel']
                        h_sel = manager._threadData['h_sel']
                        offset = math.sqrt(x * x + y * y)
                        speed = min(manager._threadData['speed'] + offset, MAX_SPEED_AT_OFFSET)
                        manager._threadData['speed'] = speed

                    maxScroll = max(w_image - w_sel, h_image - h_sel)
                    scalar = maxScroll / math.pow(((MAX_SPEED_AT_OFFSET + 1) * (MAX_SPEED_CONTROL + .1)) - speed, 2)
                    xPx = x * x * scalar * (-1 if x < 0 else 1)
                    yPx = y * y * scalar * (1 if y < 0 else -1)
                    if abs(xPx) > 1 or abs(yPx) > 1:
                        with manager._threadData['lock']:
                            manager._threadData['pending'] = True
                            manager._threadData['x'] = 0
                            manager._threadData['y'] = 0
                        self.navEventSignal.emit(int(xPx), int(yPx))

                start = 0
                last = 0
                while manager._threadData['readEvents']:
                    event = spacenav.poll()
                    now = time.monotonic_ns()
                    # Reset accumulated change if last event was more than 0.2 second ago:
                    if ((now - last) / 50000000) > 1:
                        start = now
                        sendNavSignal()
                        with manager._threadData['lock']:
                            manager._threadData['x'] = 0
                            manager._threadData['y'] = 0
                            manager._threadData['speed'] = 1
                    if event is None or not hasattr(event, 'x') or not hasattr(event, 'z'):
                        QThread.currentThread().usleep(100)
                        continue
                    last = now
                        
                    with manager._threadData['lock']:
                        manager._threadData['x'] += event.x
                        manager._threadData['y'] += event.z
                    #change = (time.monotonic_ns() - start) / 1000000
                    #print(f"{change} ms: scroll x={manager._threadData['x']} y={manager._threadData['y']}")

                    sendNavSignal()
                    QThread.currentThread().usleep(100)
                    QThread.currentThread().yieldCurrentThread()
        self._worker = SpacenavThreadWorker()

        def handleNavEvent(xOffset, yOffset):
            with manager._threadData['lock']:
                manager._threadData['pending'] = False
            if manager._window is None or not manager._editedImage.hasImage() or manager._window.isSampleSelectorVisible():
               return
            selection = manager._editedImage.getSelectionBounds();
            #print(f"moveTo: {selection.x() + xOffset},{selection.y() + yOffset}")
            selection.moveTo(selection.x() + xOffset, selection.y() + yOffset)
            manager._editedImage.setSelectionBounds(selection)
            manager._window.repaint()
        self._worker.navEventSignal.connect(handleNavEvent)

    def startThread(self):
        if spacenav is None or self._thread is not None:
            return
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._thread.start()
