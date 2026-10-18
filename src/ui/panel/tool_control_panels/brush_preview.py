"""Base class for the stroke previews in the brush tool panels.

A `BrushPreview` shows a cheap approximation while its inputs are changing, and swaps in an image rendered with the
real brush once they have been unchanged for `DEBOUNCE_MS`. Subclasses supply the inputs, the approximation and the
accurate render. Rendered images are cached by inputs and size.
"""
from collections import OrderedDict
from collections.abc import Hashable, Sequence
from typing import Optional

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QImage, QPainter, QPaintEvent, QPalette, QResizeEvent
from PySide6.QtWidgets import QWidget

from src.config.cache import Cache

DEBOUNCE_MS = 150
MAX_CACHED_IMAGES = 16


class BrushPreview(QWidget):
    """Previews a brush stroke from `Cache` values.

    Subclasses implement `_inputs`, `_paint_approximation` and `_render_accurate`. Everything runs on the GUI thread.
    A test can pass a timer and fire its `timeout` signal in place of waiting out the debounce.
    """

    def __init__(self, cache_keys: Sequence[Optional[str]], parent: Optional[QWidget] = None,
                 debounce_timer: Optional[QTimer] = None) -> None:
        super().__init__(parent)
        self._images: OrderedDict[Hashable, QImage] = OrderedDict()
        self._timer = debounce_timer if debounce_timer is not None else QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._timer.timeout.connect(self.render_accurate_now)
        cache = Cache()
        for key in cache_keys:
            if key is not None:
                cache.connect(self, key, lambda *_: self._inputs_changed())

    def _inputs(self) -> Hashable:
        """Returns a hashable value for every setting the rendered image depends on, except the preview's size."""
        raise NotImplementedError()

    def _paint_approximation(self, painter: QPainter) -> None:
        """Draws a fast stand-in for the stroke over the widget's whole rect."""
        raise NotImplementedError()

    def _render_accurate(self, size: QSize) -> QImage:
        """Returns a transparent ARGB32_Premultiplied image of `size` holding the stroke drawn by the real brush."""
        raise NotImplementedError()

    @property
    def is_accurate(self) -> bool:
        """Returns whether the accurate render for the current inputs and size is what paintEvent shows."""
        return self._cache_key() in self._images

    def render_accurate_now(self) -> None:
        """Renders and caches the accurate image for the current inputs and size, then repaints."""
        self._timer.stop()
        key = self._cache_key()
        size = self.size()
        if size.isEmpty():
            return
        if key not in self._images:
            self._images[key] = self._render_accurate(size)
            while len(self._images) > MAX_CACHED_IMAGES:
                self._images.popitem(last=False)
        else:
            self._images.move_to_end(key)
        self.update()

    def _cache_key(self) -> Hashable:
        return self._inputs(), self.width(), self.height()

    def _inputs_changed(self) -> None:
        self.update()
        if self.isVisible() and not self.is_accurate:
            self._timer.start()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Restarts the debounce, since the cached image has the old size."""
        super().resizeEvent(event)
        self._inputs_changed()

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the accurate image if it is cached, otherwise the approximation, and schedules the accurate render."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Base))
        image = self._images.get(self._cache_key())
        if image is not None:
            painter.drawImage(0, 0, image)
        else:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._paint_approximation(painter)
            if not self._timer.isActive():
                self._timer.start()
        painter.end()
