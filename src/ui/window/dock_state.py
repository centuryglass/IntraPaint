"""Reads and edits the byte layout of `QMainWindow.saveState`, for dock facts and placements Qt has no API for.

- `QMainWindow.tabifiedDockWidgets` leaves out closed docks, so tab group membership is read from the saved layout
  (`read_dock_groups`).
- `QMainWindow.addDockWidget` always appends to its area, and `splitDockWidget` only places after. Placing a dock
  first in an area means saving the layout, reordering the area's top-level items, and restoring it.
- The layout follows Qt's `QDockAreaLayout::saveState` and `QDockAreaLayoutInfo::saveState`, written with
  `QDataStream` version Qt_5_0: big-endian 32-bit ints, one-byte markers, and UTF-16 strings with a byte-length prefix.
  Any part that doesn't parse as expected makes a read or edit return None, so a changed format leaves the layout as it
  was.
"""
import struct
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt

_VERSION_HEADER_SIZE = 8  # An int marker, then the caller's version int.
_DOCK_STATE_MARKER = 0xfd
_SEQUENCE_MARKER = 0xfc
_TAB_MARKER = 0xfa
_WIDGET_MARKER = 0xfb
# A widget item's flags byte is followed by four ints: position, size, minimum and maximum, or a floating geometry.
_WIDGET_FIELDS_SIZE = 16
# A nested sequence's marker is followed by the same four ints, then the nested group's own state:
_SEQUENCE_FIELDS_SIZE = 16
_AREA_SIZE_SIZE = 8
# Bits of a widget item's flags byte:
_STATE_FLAG_VISIBLE = 1
_STATE_FLAG_FLOATING = 2

# Qt's internal `QInternal::DockPosition` numbering, used for each area in the saved layout.
_DOCK_POSITIONS = {
    Qt.DockWidgetArea.LeftDockWidgetArea: 0,
    Qt.DockWidgetArea.RightDockWidgetArea: 1,
    Qt.DockWidgetArea.TopDockWidgetArea: 2,
    Qt.DockWidgetArea.BottomDockWidgetArea: 3,
}


class _Reader:
    """Reads `QDataStream` values from saved layout bytes, raising ValueError past the end."""

    def __init__(self, data: bytes, pos: int = 0) -> None:
        self.data = data
        self.pos = pos

    def _take(self, size: int) -> bytes:
        if self.pos + size > len(self.data):
            raise ValueError('saved dock layout ended early')
        chunk = self.data[self.pos:self.pos + size]
        self.pos += size
        return chunk

    def byte(self) -> int:
        """Reads one unsigned byte."""
        return self._take(1)[0]

    def int32(self) -> int:
        """Reads one big-endian signed 32-bit int."""
        return struct.unpack('>i', self._take(4))[0]

    def skip(self, size: int) -> None:
        """Skips bytes."""
        self._take(size)

    def string(self) -> Optional[str]:
        """Reads a QString, or None for a null one."""
        size = struct.unpack('>I', self._take(4))[0]
        if size == 0xffffffff:
            return None
        return self._take(size).decode('utf-16-be')


@dataclass(frozen=True)
class SavedDock:
    """One dock's entry in a saved layout. A floating dock keeps an entry where it was docked."""
    name: str
    visible: bool
    floating: bool


@dataclass(frozen=True)
class SavedGroup:
    """A tab group in a saved layout, or a dock alone in its place.

    `current` is the index in `docks` of the dock in front, or -1 if no dock in the group is open.
    """
    docks: list[SavedDock]
    current: int


def _read_item(reader: _Reader, groups: Optional[list[SavedGroup]]) -> Optional[SavedDock]:
    """Reads one item of a dock group, returning a widget item's dock, or None for a nested group."""
    marker = reader.byte()
    if marker == _WIDGET_MARKER:
        name = reader.string()
        flags = reader.byte()
        reader.skip(_WIDGET_FIELDS_SIZE)
        return SavedDock(name if name is not None else '', bool(flags & _STATE_FLAG_VISIBLE),
                         bool(flags & _STATE_FLAG_FLOATING))
    if marker != _SEQUENCE_MARKER:
        raise ValueError(f'unexpected dock item marker {marker:#x}')
    reader.skip(_SEQUENCE_FIELDS_SIZE)
    _read_group(reader, groups)
    return None


def _read_group(reader: _Reader, groups: Optional[list[SavedGroup]] = None) \
        -> tuple[int, list[tuple[int, int, Optional[str]]]]:
    """Reads a dock group, returning its orientation and each item's start, end and widget name.

    With `groups`, also appends each tab group and lone dock found, in layout order.
    """
    marker = reader.byte()
    tabbed = marker == _TAB_MARKER
    current = -1
    if tabbed:
        current = reader.int32()
    elif marker != _SEQUENCE_MARKER:
        raise ValueError(f'unexpected dock group marker {marker:#x}')
    orientation = reader.byte()
    count = reader.int32()
    items = []
    tab_docks: list[SavedDock] = []
    for _ in range(count):
        start = reader.pos
        dock = _read_item(reader, groups)
        items.append((start, reader.pos, None if dock is None else dock.name))
        if dock is None:
            continue
        if tabbed:
            tab_docks.append(dock)
        elif groups is not None:
            groups.append(SavedGroup([dock], 0 if dock.visible else -1))
    if tabbed and groups is not None:
        groups.append(SavedGroup(tab_docks, current if 0 <= current < len(tab_docks) else -1))
    return orientation, items


def read_dock_groups(state: bytes) -> Optional[list[SavedGroup]]:
    """Returns every tab group and lone dock in a saved layout's dock areas, in layout order, or None if the layout
    doesn't parse."""
    groups: list[SavedGroup] = []
    try:
        reader = _Reader(state, _VERSION_HEADER_SIZE)
        if reader.byte() != _DOCK_STATE_MARKER:
            return None
        area_count = reader.int32()
        for _ in range(area_count):
            reader.int32()
            reader.skip(_AREA_SIZE_SIZE)
            _read_group(reader, groups)
    except (ValueError, struct.error, UnicodeDecodeError):
        return None
    return groups


def move_dock_to_area_start(state: bytes, area: Qt.DockWidgetArea, orientation: Qt.Orientation,
                            object_name: str) -> Optional[bytes]:
    """Returns saved layout bytes with a dock moved from the end of its area's top-level row or column to the start.

    The dock must be the last top-level item of the area, which is laid out along `orientation`, as
    `addDockWidget(area, dock, orientation)` leaves it. Returns None if the layout doesn't have that shape or doesn't
    parse.
    """
    try:
        reader = _Reader(state, _VERSION_HEADER_SIZE)
        if reader.byte() != _DOCK_STATE_MARKER:
            return None
        area_count = reader.int32()
        for _ in range(area_count):
            position = reader.int32()
            reader.skip(_AREA_SIZE_SIZE)
            group_orientation, items = _read_group(reader)
            if position != _DOCK_POSITIONS[area]:
                continue
            if group_orientation != orientation.value or items[-1][2] != object_name:
                return None
            first_start = items[0][0]
            last_start, end, _name = items[-1]
            return state[:first_start] + state[last_start:end] + state[first_start:last_start] + state[end:]
    except (ValueError, struct.error, UnicodeDecodeError):
        return None
    return None
