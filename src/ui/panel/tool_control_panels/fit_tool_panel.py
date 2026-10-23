"""A base for tool control panels that plan their own layout by fit, as `src.ui.layout.panel_fit.FitContent`.

The Tools panel measures such a panel at `fit_base_size`, then passes it the space left over with `set_fit_space`.
Outside a `DockPanel`, the panel plans for its own size when resized. Subclasses create `_planner`, a `FitPlanner` over
their items, and arrange their widgets in its `apply` callback.
"""
from typing import Optional

from PySide6.QtCore import QEvent, QSize
from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QWidget

from src.ui.layout.dock_panel import QWIDGETSIZE_MAX, DockPanel
from src.ui.layout.panel_fit import (STRIP_SECTION_MAX_WIDTH, FitPlanner, Orientation, fresh_minimum_size,
                                     orientation_for_size)


class FitToolPanel(QWidget):
    """A tool control panel planned by fit. Optional controls a plan leaves out go in `overflow_content`, which the
    Tools panel shows in its More popover."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._space: Optional[QSize] = None
        self._planning = False
        self._orientation = Orientation.SIDE
        self._planner: Optional[FitPlanner] = None
        self._overflow = QWidget()
        self._overflow_layout = QVBoxLayout(self._overflow)
        self._overflow_layout.setContentsMargins(0, 0, 0, 0)

    def fit_base_size(self, orientation: Orientation) -> QSize:
        """Returns the minimum size with required items in their smallest forms and optional items left out, and keeps
        that arrangement until the next `set_fit_space`."""
        assert self._planner is not None
        return self._planner.base_size(orientation)

    def set_fit_space(self, orientation: Orientation, size: QSize) -> None:
        """Plans for the space the Tools panel gives the panel."""
        assert self._planner is not None
        self._space = QSize(size)
        self._planner.update(orientation, size)

    def overflow_content(self) -> QWidget:
        """Returns the widget holding the controls the latest plan left out."""
        return self._overflow

    def _measure_fit(self) -> QSize:
        return fresh_minimum_size(self)

    def _host(self) -> Optional[DockPanel]:
        """Returns the `DockPanel` the panel is inside, or None."""
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, DockPanel):
                return parent
            parent = parent.parentWidget()
        return None

    def _refit(self) -> None:
        """Plans again after a row appears or disappears: the hosting panel if there is one, or else this panel."""
        host = self._host()
        if host is not None:
            host.refit()
        elif self._planner is not None and self._planner.placement is not None:
            self._plan_own_size(force=True)

    def _plan_own_size(self, force: bool = False) -> None:
        """Plans for the space the host gave the panel, or for its own size without a host. Trial placements can
        resize the panel, and the resize this causes doesn't start another plan."""
        if self._planning or self._planner is None:
            return
        self._planning = True
        try:
            if self._space is not None:
                self._planner.update(self._orientation, self._space, force)
            else:
                self._planner.update(orientation_for_size(self.size(), self._orientation), self.size(), force)
        finally:
            self._planning = False

    @staticmethod
    def _body_grid(body: QWidget) -> QGridLayout:
        layout = QGridLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        return layout

    @staticmethod
    def _clear(layout: QGridLayout, widgets: tuple[QWidget, ...]) -> None:
        """Takes widgets out of a grid and clears its stretch factors, so an arrangement leaves no trace of the last."""
        for widget in widgets:
            layout.removeWidget(widget)
        for index in range(layout.rowCount()):
            layout.setRowStretch(index, 0)
        for index in range(layout.columnCount()):
            layout.setColumnStretch(index, 0)

    @staticmethod
    def _cap_width(widget: QWidget) -> None:
        """Caps a section at `STRIP_SECTION_MAX_WIDTH`, or at its minimum width if that is wider."""
        widget.setMaximumWidth(QWIDGETSIZE_MAX)
        widget.setMaximumWidth(max(STRIP_SECTION_MAX_WIDTH, fresh_minimum_size(widget).width()))

    def event(self, event: QEvent) -> bool:
        """Forgets the host's space when the panel moves to a new parent, and plans for its own size when resized
        without a host.

        A panel inside a `DockPanel` waits for `set_fit_space` instead: the host's trial placements resize it, and
        planning then would replace the base arrangement the host is measuring.
        """
        if event.type() == QEvent.Type.ParentChange:
            self._space = None
        handled = super().event(event)
        if event.type() == QEvent.Type.Resize and self._space is None and self._host() is None:
            self._plan_own_size()
        return handled
