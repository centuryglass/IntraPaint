"""Model for the guide lines dragged out of the rulers.

Guides are view state, like zoom: session-only, not saved with the image and not undoable. A horizontal guide has a
fixed y coordinate and a vertical guide a fixed x coordinate, both in whole image pixels.
"""
from PySide6.QtCore import QObject, QSize, Qt, Signal


class RulerGuides(QObject):
    """Holds guide positions and the lock flag, and emits `guides_changed` when either changes."""

    guides_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._guides: dict[Qt.Orientation, list[int]] = {Qt.Orientation.Horizontal: [], Qt.Orientation.Vertical: []}
        self._locked = False

    def positions(self, orientation: Qt.Orientation) -> list[int]:
        """Returns the coordinates of the guides with a given orientation, in the order they were added.

        A horizontal guide runs horizontally, so its coordinate is a y value; a vertical guide's is an x value."""
        return list(self._guides[orientation])

    @property
    def count(self) -> int:
        """Returns the total number of guides."""
        return sum(len(positions) for positions in self._guides.values())

    @property
    def locked(self) -> bool:
        """Returns whether guide handles ignore presses."""
        return self._locked

    @locked.setter
    def locked(self, locked: bool) -> None:
        if locked != self._locked:
            self._locked = locked
            self.guides_changed.emit()

    def add(self, orientation: Qt.Orientation, position: int) -> None:
        """Adds a guide."""
        self._guides[orientation].append(position)
        self.guides_changed.emit()

    def move(self, orientation: Qt.Orientation, old_position: int, new_position: int) -> None:
        """Moves the guide at `old_position` to `new_position`. Does nothing if there is no such guide."""
        positions = self._guides[orientation]
        if old_position not in positions or old_position == new_position:
            return
        positions[positions.index(old_position)] = new_position
        self.guides_changed.emit()

    def remove(self, orientation: Qt.Orientation, position: int) -> None:
        """Removes the guide at `position`. Does nothing if there is no such guide."""
        positions = self._guides[orientation]
        if position in positions:
            positions.remove(position)
            self.guides_changed.emit()

    def clear(self) -> None:
        """Removes every guide."""
        if self.count > 0:
            for positions in self._guides.values():
                positions.clear()
            self.guides_changed.emit()

    def prune(self, size: QSize) -> None:
        """Removes every guide outside [0, size] on its axis."""
        limits = {Qt.Orientation.Horizontal: size.height(), Qt.Orientation.Vertical: size.width()}
        changed = False
        for orientation, positions in self._guides.items():
            kept = [position for position in positions if 0 <= position <= limits[orientation]]
            if len(kept) != len(positions):
                self._guides[orientation] = kept
                changed = True
        if changed:
            self.guides_changed.emit()
