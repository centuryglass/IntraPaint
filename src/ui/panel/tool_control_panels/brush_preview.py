"""Base class for the stroke previews in the brush tool panels.

A `BrushPreview` always shows an image rendered with the real brush. While its inputs change, the last render stays on
screen and a new one is made at most once per `RENDER_INTERVAL_MS`, using the inputs as they are at that moment.
Subclasses supply the inputs and the render. Rendered images are cached by inputs and size.
"""
from collections import OrderedDict
from collections.abc import Hashable, Sequence
from typing import Optional

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QImage, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QWidget

from src.config.cache import Cache

RENDER_INTERVAL_MS = 100
MAX_CACHED_IMAGES = 16


class BrushPreview(QWidget):
    """Previews a brush stroke from `Cache` values.

    Subclasses implement `_inputs` and `_render`. Everything runs on the GUI thread. A test can pass a timer and fire
    its `timeout` signal in place of waiting out the interval.
    """

    def __init__(self, cache_keys: Sequence[Optional[str]], parent: Optional[QWidget] = None,
                 render_timer: Optional[QTimer] = None) -> None:
        super().__init__(parent)
        self._images: OrderedDict[Hashable, QImage] = OrderedDict()
        self._shown: Optional[QImage] = None
        self._timer = render_timer if render_timer is not None else QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(RENDER_INTERVAL_MS)
        self._timer.timeout.connect(self.render_now)
        cache = Cache()
        for key in cache_keys:
            if key is not None:
                cache.connect(self, key, lambda *_: self._inputs_changed())

    def _inputs(self) -> Hashable:
        """Returns a hashable value for every setting the rendered image depends on, except the preview's size."""
        raise NotImplementedError()

    def _render(self, size: QSize) -> QImage:
        """Returns a transparent ARGB32_Premultiplied image of `size` holding the stroke drawn by the real brush."""
        raise NotImplementedError()

    @property
    def is_current(self) -> bool:
        """Returns whether the image on screen was rendered from the current inputs and size."""
        return self._shown is not None and self._shown is self._images.get(self._cache_key())

    def render_now(self) -> None:
        """Shows the image for the current inputs and size, rendering it unless it is cached, then repaints."""
        self._timer.stop()
        if self._show_current():
            self.update()

    def _show_current(self) -> bool:
        """Sets the shown image to the current one. Returns False if the widget is too small to render."""
        if self.size().isEmpty():
            return False
        key = self._cache_key()
        if key in self._images:
            self._images.move_to_end(key)
        else:
            self._images[key] = self._render(self.size())
            while len(self._images) > MAX_CACHED_IMAGES:
                self._images.popitem(last=False)
        self._shown = self._images[key]
        return True

    def _cache_key(self) -> Hashable:
        return self._inputs(), self.width(), self.height()

    def _inputs_changed(self) -> None:
        """Shows a cached image at once, otherwise schedules a render if none is pending."""
        if self._cache_key() in self._images:
            self.render_now()
        elif self.isVisible() and not self._timer.isActive():
            self._timer.start()

    def showEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Schedules a render if inputs or size changed while hidden."""
        super().showEvent(event)
        self._inputs_changed()

    def resizeEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Schedules a render for the new size."""
        super().resizeEvent(event)
        self._inputs_changed()

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the shown image, stretched to the widget while a render for its size is pending. The first paint
        renders at once, so the preview is never empty."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Base))
        if self._shown is None:
            self._show_current()
        if self._shown is not None:
            painter.drawImage(self.rect(), self._shown)
        painter.end()
