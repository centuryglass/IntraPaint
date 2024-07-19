"""
Enables moving the edited image section using a spacemouse.

To function correctly, the spacenav package must be installed, the associated daemon must be running, and a spacemouse
must be attached. If any of those conditions are not met, spacemouse functionality will be disabled.
"""
import atexit
import time
import math
from threading import Lock
import logging
from typing import Optional

import spacenav
from PyQt6.QtCore import QObject, QThread, QSize, QRect, pyqtSignal
from src.image.layers.image_stack import ImageStack
from src.ui.window.main_window import MainWindow
from src.util.application_state import AppStateTracker, APP_STATE_EDITING

logger = logging.getLogger(__name__)

# Once the xy offset of sequential spacenav events adds up to this value, the image generation area will
# reach max scrolling speed:
MAX_SPEED_AT_OFFSET = 20000
# Controls how quickly the image generation area will move across the entire image at max speed:
# Values must >= 0.  The higher the value, the slower the max speed will be.
MAX_SPEED_CONTROL = 1


class SpacenavManager:
    """Tracks spacemouse input and applies it to the edited image generation area."""

    def __init__(self, window: MainWindow, image_stack: ImageStack) -> None:
        """Connects the manager to the edited image and the main application window.""

        Parameters
        ----------
        window : MainWindow
            The main application window.
        image_stack : ImageStack
            Image layers being edited.
        """
        if spacenav is None:
            return
        self._window = window
        self._image_stack = image_stack
        self._thread: Optional[QThread] = None
        self._worker: Optional['SpacenavThreadWorker'] = None

        class ThreadData:
            """Shares data between main thread and spacemouse thread."""

            def __init__(self):
                self.read_events = True
                self.pending = False
                self.x = 0
                self.y = 0
                self.w_image = 0
                self.h_image = 0
                self.w_sel = 0
                self.h_sel = 0
                self.speed = 1
                self.lock = Lock()

            @property
            def dimensions_all_nonzero(self) -> bool:
                """Return whether all image and image generation area dimensions are not zero."""
                return any(dim == 0 for dim in (self.w_image, self.h_image, self.w_sel, self.h_sel))

        self._thread_data = ThreadData()
        self._thread = None

        def update_image_size(size: QSize):
            """Keep image size in sync with edited image data."""
            with self._thread_data.lock:
                if size.width() != self._thread_data.w_image:
                    self._thread_data.w_image = size.width()
                if size.height() != self._thread_data.h_image:
                    self._thread_data.h_image = size.height()

        self._image_stack.size_changed.connect(update_image_size)

        def update_generation_area_size(bounds: QRect):
            """Keep tracked image generation area size in sync with the current image generation area."""
            with self._thread_data.lock:
                if bounds.width() != self._thread_data.w_sel:
                    self._thread_data.w_sel = bounds.width()
                if bounds.height() != self._thread_data.h_sel:
                    self._thread_data.h_sel = bounds.height()

        self._image_stack.generation_area_bounds_changed.connect(update_generation_area_size)

        def stop_loop():
            """Stop the event thread when the application finishes."""
            with self._thread_data.lock:
                self._thread_data.read_events = False
            logger.info('Spacenav connection terminating at exit.')

        atexit.register(stop_loop)

        class SpacenavThreadWorker(QObject):
            """SpacenavThreadWorker tracks spacenav events in its own thread."""

            nav_event_signal = pyqtSignal(int, int)

            def __init__(self, thread_data: ThreadData) -> None:
                super().__init__()
                self._thread_data = thread_data

            def run(self) -> None:
                """Main thread loop."""
                logger.info('Loading optional space mouse support for panning:')
                try:
                    spacenav.open()
                    atexit.register(spacenav.close)
                except spacenav.ConnectionError:
                    logger.warning('spacenav connection failed, space mouse will not be used.')
                    return
                logger.info('spacenav connection started.')

                def send_nav_signal() -> None:
                    """Convert spacemouse events to appropriate image generation area changes, emit results to main
                       thread."""
                    with self._thread_data.lock:
                        if self._thread_data.pending:
                            return
                        if not self._thread_data.dimensions_all_nonzero:
                            return
                        x = self._thread_data.x
                        y = self._thread_data.y
                        w_image = self._thread_data.w_image
                        h_image = self._thread_data.h_image
                        w_sel = self._thread_data.w_sel
                        h_sel = self._thread_data.h_sel
                        offset = math.sqrt(x * x + y * y)
                        speed = min(self._thread_data.speed + offset, MAX_SPEED_AT_OFFSET)
                        self._thread_data.speed = speed

                    max_scroll = max(w_image - w_sel, h_image - h_sel)
                    scalar = max_scroll / math.pow(((MAX_SPEED_AT_OFFSET + 1) * (MAX_SPEED_CONTROL + .1)) - speed, 2)
                    x_px = x * x * scalar * (-1 if x < 0 else 1)
                    y_px = y * y * scalar * (1 if y < 0 else -1)
                    if abs(x_px) > 1 or abs(y_px) > 1:
                        with self._thread_data.lock:
                            self._thread_data.pending = True
                            self._thread_data.x = 0
                            self._thread_data.y = 0
                        self.nav_event_signal.emit(int(x_px), int(y_px))

                # start = 0
                last = 0
                while self._thread_data.read_events:
                    event = spacenav.poll()
                    now = time.monotonic_ns()
                    # Reset accumulated change if last event was more than 0.2 second ago:
                    if ((now - last) / 50000000) > 1:
                        # start = now
                        send_nav_signal()
                        with self._thread_data.lock:
                            self._thread_data.x = 0
                            self._thread_data.y = 0
                            self._thread_data.speed = 1
                    if event is None or not hasattr(event, 'x') or not hasattr(event, 'z'):
                        thread = QThread.currentThread()
                        assert thread is not None, 'No active Qt thread'
                        thread.usleep(100)
                        continue
                    last = now

                    with self._thread_data.lock:
                        self._thread_data.x += event.x
                        self._thread_data.y += event.z
                    # change = (time.monotonic_ns() - start) / 1000000
                    # print(f"{change} ms: scroll x={manager._thread_data.x} y={manager._thread_data.y}")

                    send_nav_signal()
                    thread = QThread.currentThread()
                    assert thread is not None, 'No active Qt thread'
                    thread.usleep(100)
                    thread.yieldCurrentThread()

        self._worker = SpacenavThreadWorker(self._thread_data)

        def handle_nav_event(x_offset: int, y_offset: int) -> None:
            """Move the image generation area when the thread worker requests."""
            with self._thread_data.lock:
                self._thread_data.pending = False
            if self._window is None or AppStateTracker.app_state() != APP_STATE_EDITING:
                return
            generation_area = self._image_stack.generation_area
            generation_area.moveTo(generation_area.x() + x_offset, generation_area.y() + y_offset)
            self._image_stack.generation_area = generation_area
            self._window.repaint()

        self._worker.nav_event_signal.connect(handle_nav_event)

    def start_thread(self) -> None:
        """Starts the spacemouse worker thread to track inputs."""
        if spacenav is None or self._thread is not None:
            return
        assert self._worker is not None
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._thread.start()
