# Supports panning via spacemouse, if applicable
try:
    import spacenav, atexit, time
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
                    x = 0
                    y = 0
                    w_image = 0
                    h_image = 0
                    w_sel = 0
                    h_sel = 0
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

                    # Offset will be approx. 9000 if the space mouse is held all the way down in one direction for one
                    # second. Calculate offset in pixels so that scrolling across the largest image dimension takes
                    # roughly three seconds.
                    maxScroll = max(w_image - w_sel, h_image - h_sel)
                    # xSum/9000 = xPx/maxScroll
                    xPx = x * maxScroll/27000
                    yPx = -y * maxScroll/27000 
                    if abs(xPx) > 1 or abs(yPx) > 1:
                        with manager._threadData['lock']:
                            manager._threadData['pending'] = True
                            manager._threadData['x'] = 0
                            manager._threadData['y'] = 0
                        print(f"x={xPx}, y={yPx}")
                        self.navEventSignal.emit(int(xPx), int(yPx))

                start = 0
                last = 0
                while manager._threadData['readEvents']:
                    event = spacenav.poll()
                    now = time.monotonic_ns()
                    # Reset accumulated change if last event was more than 0.1 second ago:
                    if ((now - last) / 100000000) > 1:
                        start = now
                        sendNavSignal()
                        with manager._threadData['lock']:
                            manager._threadData['x'] = 0
                            manager._threadData['y'] = 0
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
