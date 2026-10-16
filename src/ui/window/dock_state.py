"""Edits to the byte layout of `QMainWindow.saveState`, for dock placements Qt has no API for.

- `QMainWindow.addDockWidget` always appends to its area, and `splitDockWidget` only places after. Placing a dock
  first in an area means saving the layout, reordering the area's top-level items, and restoring it.
- The layout follows Qt's `QDockAreaLayout::saveState` and `QDockAreaLayoutInfo::saveState`, written with
  `QDataStream` version Qt_5_0: big-endian 32-bit ints, one-byte markers, and UTF-16 strings with a byte-length prefix.
  Any part that doesn't parse as expected makes the edit return None, so a changed format leaves the layout as it was.
"""
import struct
from typing import Optional

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QMainWindow, QTabBar

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


def _read_item(reader: _Reader) -> Optional[str]:
    """Reads one item of a dock group, returning a widget item's object name, or None for a nested group."""
    marker = reader.byte()
    if marker == _WIDGET_MARKER:
        name = reader.string()
        reader.skip(1 + _WIDGET_FIELDS_SIZE)
        return name if name is not None else ''
    if marker != _SEQUENCE_MARKER:
        raise ValueError(f'unexpected dock item marker {marker:#x}')
    reader.skip(_SEQUENCE_FIELDS_SIZE)
    _read_group(reader)
    return None


def _read_group(reader: _Reader) -> tuple[int, list[tuple[int, int, Optional[str]]]]:
    """Reads a dock group, returning its orientation and each item's start, end and widget name."""
    marker = reader.byte()
    if marker == _TAB_MARKER:
        reader.int32()
    elif marker != _SEQUENCE_MARKER:
        raise ValueError(f'unexpected dock group marker {marker:#x}')
    orientation = reader.byte()
    count = reader.int32()
    items = []
    for _ in range(count):
        start = reader.pos
        name = _read_item(reader)
        items.append((start, reader.pos, name))
    return orientation, items


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


def restore_state_without_stale_tab_bars(window: QMainWindow, state: bytes | QByteArray, version: int = 0) -> bool:
    """Restores a saved layout with `QMainWindow.restoreState`, returning whether it did.

    `restoreState` gives each tab group a new tab bar and leaves the old bars drawn where they were. The old bars are
    hidden first, and Qt shows the new ones. A failed restore changes nothing, so the hidden bars are shown again.
    """
    hidden = [tab_bar for tab_bar in window.findChildren(QTabBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
              if not tab_bar.isHidden()]
    for tab_bar in hidden:
        tab_bar.hide()
    if window.restoreState(QByteArray(state), version):
        return True
    for tab_bar in hidden:
        tab_bar.show()
    return False
