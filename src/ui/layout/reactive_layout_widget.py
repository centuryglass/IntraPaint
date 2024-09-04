"""A QWidget with extra support for rearranging contents based on bounds."""
from typing import Optional, Dict, Callable, List
import logging

from PySide6.QtCore import QSize
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import QWidget, QSizePolicy

from src.util.shared_constants import INT_MAX

logger = logging.getLogger(__name__)


class ReactiveLayoutWidget(QWidget):
    """A QWidget with extra support for rearranging contents based on bounds."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._visibility_limits: Dict[QWidget, QSize] = {}
        self._layout_modes: List[_LayoutMode] = []
        self._default_mode: Optional[_LayoutMode] = None
        self._active_mode: Optional[str] = None

    def sizeHint(self) -> Optional[QSize]:
        """Returns a null size to ensure Qt layout management doesn't block transitions into other modes."""
        return QSize()

    def add_visibility_limit(self, widget: QWidget, min_size: QSize) -> None:
        """Set a threshold, below which a given child widget shouldn't be shown."""
        self._visibility_limits[widget] = min_size

    def add_layout_mode(self, name: str, setup: Callable[[], None],
                        min_size: Optional[QSize] = None,
                        max_size: Optional[QSize] = None) -> None:
        """Add a new layout mode to reconfigure the widget when it enters a given size range."""
        for old_mode in self._layout_modes:
            if old_mode.in_range(min_size) or old_mode.in_range(max_size):
                raise RuntimeError(f'Mode {name} bounds {min_size}-{max_size} overlap with mode {old_mode.name} bounds '
                                   f'{old_mode.min_size}-{old_mode.max_size}')
        mode = _LayoutMode(name, self, setup, min_size, max_size)
        self._layout_modes.append(mode)
        self.resizeEvent(None)

    def add_default_layout_mode(self, setup: Callable[[], None]) -> None:
        """Add a layout mode to use as a fallback if none of the size-specific modes apply."""
        self._default_mode = _LayoutMode('default', self, setup, None, None)

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Apply visibility rules and switch layout modes if necessary."""
        new_mode = None
        for mode in self._layout_modes:
            if mode.in_range():
                new_mode = mode
        if new_mode is None and self._default_mode is not None:
            new_mode = self._default_mode
        if new_mode is not None:
            if new_mode.name != self._active_mode:
                self._active_mode = new_mode.name
                new_mode.activate()
        elif len(self._layout_modes) > 0:
            logger.error(f'no layout mode in range at {self.size()}')

        for widget, size in self._visibility_limits.items():
            if not self._is_descendant(widget):
                continue
            should_show = self.width() >= size.width() and self.height() >= size.height()
            if should_show:
                widget.show()
            else:
                widget.hide()

    def showEvent(self, unused_event: Optional[QShowEvent]) -> None:
        """Re-check size constraints when the widget is shown."""
        self.resizeEvent(None)

    def _is_descendant(self, widget: Optional[QWidget]) -> bool:
        widget_iter = widget
        while widget_iter is not None:
            if widget_iter == self:
                return True
            widget_iter = widget_iter.parent()
        return False


class _LayoutMode:
    def __init__(self, name: str, widget: ReactiveLayoutWidget, setup: Callable[[], None],
                 min_size: Optional[QSize] = None,
                 max_size: Optional[QSize] = None) -> None:
        self.name = name
        self._widget = widget
        if min_size is None:
            min_size = QSize(0, 0)
        self.min_size = min_size
        if max_size is None:
            max_size = QSize(INT_MAX, INT_MAX)
        self.max_size = max_size
        assert min_size.width() < max_size.width() and min_size.height() < max_size.height(), (f'{name}: '
                                                                                               f'max_size > min_size')
        self.setup = setup

    def in_range(self, size: Optional[QSize] = None) -> bool:
        """Returns whether the given size (or the widget size) is in-range for this mode."""
        if size is None:
            size = self._widget.size()
        if size.width() < self.min_size.width() or size.height() < self.min_size.height():
            return False
        if size.width() > self.max_size.width() or size.height() > self.max_size.height():
            return False
        return True

    def activate(self) -> None:
        """Apply the mode setup function after confirming bounds are in range."""
        if not self.in_range():
            raise RuntimeError(f'Mode {self.name} not supported at {self._widget.size()}')
        self.setup()
