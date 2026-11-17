"""Reads and edits the byte layout of `QMainWindow.saveState`, for dock facts and placements Qt has no API for.

- `QMainWindow.tabifiedDockWidgets` leaves out closed docks, so tab group membership is read from the saved layout
  (`read_dock_groups`).
- `QMainWindow.addDockWidget` always appends to its area, and `splitDockWidget` only places after. Placing a dock
  first in an area means saving the layout, reordering the area's top-level items, and restoring it.
- `splitDockWidget` tabs a dock into the first dock's group when that dock is tabbed. Splitting beside a tab group
  parses the layout into a tree, moves the dock's item beside the group's, and writes it back (`split_dock_beside`).
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


@dataclass
class _WidgetNode:
    """A dock's item in a layout tree: its name, flags byte, and four ints (see `_WIDGET_FIELDS_SIZE`)."""
    name: Optional[str]
    flags: int
    fields: tuple[int, int, int, int]


@dataclass
class _GroupNode:
    """A tab group or a row or column of items. `current` is only written for a tab group."""
    tabbed: bool
    current: int
    orientation: int
    items: list['_WidgetNode | _NestedNode']


@dataclass
class _NestedNode:
    """A group nested in a row or column, with its four ints (see `_SEQUENCE_FIELDS_SIZE`)."""
    fields: tuple[int, int, int, int]
    group: _GroupNode


@dataclass
class _Area:
    position: int
    size: bytes
    root: _GroupNode


@dataclass
class _LayoutTree:
    """A parsed `saveState` dock layout. Bytes outside the dock areas are kept as they were."""
    header: bytes
    areas: list[_Area]
    tail: bytes


def _parse_group(reader: _Reader) -> _GroupNode:
    marker = reader.byte()
    tabbed = marker == _TAB_MARKER
    if not tabbed and marker != _SEQUENCE_MARKER:
        raise ValueError(f'unexpected dock group marker {marker:#x}')
    current = reader.int32() if tabbed else -1
    orientation = reader.byte()
    items: list[_WidgetNode | _NestedNode] = []
    for _ in range(reader.int32()):
        marker = reader.byte()
        if marker == _WIDGET_MARKER:
            name = reader.string()
            flags = reader.byte()
            items.append(_WidgetNode(name, flags, _read_fields(reader)))
        elif marker == _SEQUENCE_MARKER:
            fields = _read_fields(reader)
            items.append(_NestedNode(fields, _parse_group(reader)))
        else:
            raise ValueError(f'unexpected dock item marker {marker:#x}')
    return _GroupNode(tabbed, current, orientation, items)


def _read_fields(reader: _Reader) -> tuple[int, int, int, int]:
    return reader.int32(), reader.int32(), reader.int32(), reader.int32()


def _parse_tree(state: bytes) -> _LayoutTree:
    """Parses a saved layout, raising ValueError, struct.error or UnicodeDecodeError if it doesn't parse."""
    reader = _Reader(state, _VERSION_HEADER_SIZE)
    if reader.byte() != _DOCK_STATE_MARKER:
        raise ValueError('not a dock layout')
    header = state[:reader.pos]
    areas = []
    for _ in range(reader.int32()):
        position = reader.int32()
        size = reader.data[reader.pos:reader.pos + _AREA_SIZE_SIZE]
        reader.skip(_AREA_SIZE_SIZE)
        areas.append(_Area(position, size, _parse_group(reader)))
    return _LayoutTree(header, areas, state[reader.pos:])


def _write_group(group: _GroupNode, out: list[bytes]) -> None:
    if group.tabbed:
        out.append(struct.pack('>Bi', _TAB_MARKER, group.current))
    else:
        out.append(struct.pack('>B', _SEQUENCE_MARKER))
    out.append(struct.pack('>Bi', group.orientation, len(group.items)))
    for item in group.items:
        if isinstance(item, _WidgetNode):
            out.append(struct.pack('>B', _WIDGET_MARKER))
            if item.name is None:
                out.append(struct.pack('>I', 0xffffffff))
            else:
                encoded = item.name.encode('utf-16-be')
                out.append(struct.pack('>I', len(encoded)) + encoded)
            out.append(struct.pack('>B4i', item.flags, *item.fields))
        else:
            out.append(struct.pack('>B4i', _SEQUENCE_MARKER, *item.fields))
            _write_group(item.group, out)


def _write_tree(tree: _LayoutTree) -> bytes:
    out = [tree.header, struct.pack('>i', len(tree.areas))]
    for area in tree.areas:
        out.append(struct.pack('>i', area.position) + area.size)
        _write_group(area.root, out)
    out.append(tree.tail)
    return b''.join(out)


def _find_path(group: _GroupNode, name: str) -> Optional[list[tuple[_GroupNode, int]]]:
    """Returns each group and item index from `group` down to the named dock's item, or None if it isn't there."""
    for idx, item in enumerate(group.items):
        if isinstance(item, _WidgetNode):
            if item.name == name:
                return [(group, idx)]
        else:
            path = _find_path(item.group, name)
            if path is not None:
                return [(group, idx), *path]
    return None


def _take_dock(tree: _LayoutTree, name: str) -> _WidgetNode:
    """Removes a dock's item, then every group the removal leaves empty. Raises ValueError if the dock isn't there.

    A tab group that loses its front dock puts its first open docked dock in front.
    """
    for area in tree.areas:
        path = _find_path(area.root, name)
        if path is None:
            continue
        group, idx = path[-1]
        node = group.items.pop(idx)
        assert isinstance(node, _WidgetNode)
        if group.tabbed and group.current > idx:
            group.current -= 1
        elif group.tabbed and group.current == idx:
            group.current = next((pos for pos, item in enumerate(group.items) if isinstance(item, _WidgetNode)
                                  and item.flags & _STATE_FLAG_VISIBLE and not item.flags & _STATE_FLAG_FLOATING), -1)
        for parent, parent_idx in reversed(path[:-1]):
            child = parent.items[parent_idx]
            if isinstance(child, _NestedNode) and len(child.group.items) == 0:
                parent.items.pop(parent_idx)
        if len(area.root.items) == 0:
            tree.areas.remove(area)
        return node
    raise ValueError(f'{name} is not in the saved dock layout')


def move_dock_in_tab_group(state: bytes, name: str, before: Optional[str]) -> Optional[bytes]:
    """Returns saved layout bytes with a dock moved within its tab group's order, just before another dock of the
    group, or to the group's end when `before` is None.

    The dock in front stays in front. Returns None if the dock isn't in a tab group, `before` isn't in the same group
    or is the dock itself, or the layout doesn't parse.
    """
    if name == before:
        return None
    try:
        tree = _parse_tree(state)
        path = None
        for area in tree.areas:
            path = _find_path(area.root, name)
            if path is not None:
                break
        if path is None:
            return None
        group, idx = path[-1]
        if not group.tabbed:
            return None
        names = [item.name if isinstance(item, _WidgetNode) else None for item in group.items]
        if before is not None and before not in names:
            return None
        front = group.items[group.current] if 0 <= group.current < len(group.items) else None
        moved = group.items.pop(idx)
        target = len(group.items) if before is None \
            else next(pos for pos, item in enumerate(group.items)
                      if isinstance(item, _WidgetNode) and item.name == before)
        group.items.insert(target, moved)
        if front is not None:
            group.current = next(pos for pos, item in enumerate(group.items) if item is front)
        return _write_tree(tree)
    except (ValueError, struct.error, UnicodeDecodeError):
        return None


def split_dock_beside(state: bytes, name: str, target_name: str, orientation: Qt.Orientation,
                      after: bool) -> Optional[bytes]:
    """Returns saved layout bytes with a dock moved out of its place and docked beside the target dock's tab group.

    The dock goes after the target's group (right or below) when `after` is set, before it otherwise, along
    `orientation`. Where the group's row or column runs the other way, the group and the dock are nested in a new one.
    The dock is open, and the two share the group's old size. Returns None if either dock isn't in the layout, they are
    the same dock, or the layout doesn't parse.
    """
    if name == target_name:
        return None
    try:
        tree = _parse_tree(state)
        moved = _take_dock(tree, name)
        target_path = None
        for area in tree.areas:
            target_path = _find_path(area.root, target_name)
            if target_path is not None:
                break
        if target_path is None:
            return None
        # A tab group is replaced as a whole, through the nested item that holds it:
        parent, idx = target_path[-2] if target_path[-1][0].tabbed and len(target_path) > 1 else target_path[-1]
        if parent.tabbed:
            return None
        target = parent.items[idx]
        size = target.fields[1]
        moved.flags = _STATE_FLAG_VISIBLE
        moved.fields = (target.fields[0], max(size // 2, 0), -1, -1)
        if parent.orientation == orientation.value:
            target.fields = (target.fields[0], size - moved.fields[1], target.fields[2], target.fields[3])
            parent.items.insert(idx + 1 if after else idx, moved)
        else:
            pair: list[_WidgetNode | _NestedNode] = [target, moved] if after else [moved, target]
            parent.items[idx] = _NestedNode(target.fields, _GroupNode(False, -1, orientation.value, pair))
        return _write_tree(tree)
    except (ValueError, struct.error, UnicodeDecodeError):
        return None
