"""
Enables moving the edited image section using a spacemouse.

To function correctly, the spacenav package must be installed, the associated daemon must be running, and a spacemouse
must be attached. If any of those conditions are not met, spacemouse functionality will be disabled.
"""
import atexit
import time
import math
from threading import Lock
try:
    import spacenav
except ImportError:
    print('spaceMouse support not installed.')
    spacenav = None
from PyQt5.QtCore import QObject, QThread, pyqtSignal

# Once the xy offset of sequential spacenav events adds up to this value, the selection window will
# reach max scrolling speed:
MAX_SPEED_AT_OFFSET = 9000
# Controls how quickly the selection will move across the entire image at max speed:
# Values must >= 0.  The higher the value, the slower the max speed will be.
MAX_SPEED_CONTROL = 1

class SpacenavManager():
    """Tracks spacemouse input and applies it to the edited image selection window."""

    def __init__(self, window, edited_image):
        """Connects the manager to the editen image and the main application window.""

        Parameters
        ----------
        window : MainWindow
            The main application window.
        edited_image : EditedImage
            The image being edited.
        """
        if spacenav is None:
            return
        self._window = window
        self._edited_image = edited_image
        self._thread_data = {
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

        def update_image_size(size):
            with self._thread_data['lock']:
                if size.width() != self._thread_data['w_image']:
                    self._thread_data['w_image'] = size.width()
                if size.height() != self._thread_data['h_image']:
                    self._thread_data['h_image'] = size.height()
        self._edited_image.size_changed.connect(update_image_size)

        def update_selection_size(bounds):
            with self._thread_data['lock']:
                if bounds.width() != self._thread_data['w_sel']:
                    self._thread_data['w_sel'] = bounds.width()
                if bounds.height() != self._thread_data['h_sel']:
                    self._thread_data['h_sel'] = bounds.height()
        self._edited_image.selection_changed.connect(update_selection_size)

        def stop_loop():
            with self._thread_data['lock']:
                self._thread_data['readEvents'] = False
        atexit.register(stop_loop)


        class SpacenavThreadWorker(QObject):
            """SpacenavThreadWorker tracks spacenav events in its own thread."""

            nav_event_signal = pyqtSignal(int, int)

            def __init__(self, thread_data):
                super().__init__()
                self._thread_data = thread_data

            def run(self):
                """Main thread loop."""
                print('Loading optional space mouse support for panning:')
                try:
                    spacenav.open()
                    atexit.register(spacenav.close)
                except spacenav.ConnectionError:
                    print('spacenav connection failed, space mouse will not be used.')
                    return
                print('spacenav connection started.')

                def send_nav_signal():
                    x = 0
                    y = 0
                    w_image = 0
                    h_image = 0
                    w_sel = 0
                    h_sel = 0
                    speed = 0
                    with self._thread_data['lock']:
                        if self._thread_data['pending']:
                            return
                        if any(self._thread_data[dim] == 0 for dim in ['w_sel', 'h_sel', 'w_image', 'h_image']):
                            return
                        x = self._thread_data['x']
                        y = self._thread_data['y']
                        w_image = self._thread_data['w_image']
                        h_image = self._thread_data['h_image']
                        w_sel = self._thread_data['w_sel']
                        h_sel = self._thread_data['h_sel']
                        offset = math.sqrt(x * x + y * y)
                        speed = min(self._thread_data['speed'] + offset, MAX_SPEED_AT_OFFSET)
                        self._thread_data['speed'] = speed

                    max_scroll = max(w_image - w_sel, h_image - h_sel)
                    scalar = max_scroll / math.pow(((MAX_SPEED_AT_OFFSET + 1) * (MAX_SPEED_CONTROL + .1)) - speed, 2)
                    x_px = x * x * scalar * (-1 if x < 0 else 1)
                    y_px = y * y * scalar * (1 if y < 0 else -1)
                    if abs(x_px) > 1 or abs(y_px) > 1:
                        with self._thread_data['lock']:
                            self._thread_data['pending'] = True
                            self._thread_data['x'] = 0
                            self._thread_data['y'] = 0
                        self.nav_event_signal.emit(int(x_px), int(y_px))

                #start = 0
                last = 0
                while self._thread_data['readEvents']:
                    event = spacenav.poll()
                    now = time.monotonic_ns()
                    # Reset accumulated change if last event was more than 0.2 second ago:
                    if ((now - last) / 50000000) > 1:
                        #start = now
                        send_nav_signal()
                        with self._thread_data['lock']:
                            self._thread_data['x'] = 0
                            self._thread_data['y'] = 0
                            self._thread_data['speed'] = 1
                    if event is None or not hasattr(event, 'x') or not hasattr(event, 'z'):
                        QThread.currentThread().usleep(100)
                        continue
                    last = now

                    with self._thread_data['lock']:
                        self._thread_data['x'] += event.x
                        self._thread_data['y'] += event.z
                    #change = (time.monotonic_ns() - start) / 1000000
                    #print(f"{change} ms: scroll x={manager._thread_data['x']} y={manager._thread_data['y']}")

                    send_nav_signal()
                    QThread.currentThread().usleep(100)
                    QThread.currentThread().yieldCurrentThread()
        self._worker = SpacenavThreadWorker(self._thread_data)

        def handle_nav_event(x_offset, y_offset):
            with self._thread_data['lock']:
                self._thread_data['pending'] = False
            if self._window is None or not self._edited_image.has_image() \
                    or self._window.is_sample_selector_visible():
                return
            selection = self._edited_image.get_selection_bounds()
            #print(f"moveTo: {selection.x() + x_offset},{selection.y() + y_offset}")
            selection.moveTo(selection.x() + x_offset, selection.y() + y_offset)
            self._edited_image.set_selection_bounds(selection)
            self._window.repaint()
        self._worker.nav_event_signal.connect(handle_nav_event)

    def start_thread(self):
        """Starts the spacemouse worker thread to track inputs."""
        if spacenav is None or self._thread is not None:
            return
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._thread.start()
