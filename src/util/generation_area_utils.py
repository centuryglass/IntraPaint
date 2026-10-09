"""Pure helpers for generation area frames, the generation resolution rule, follow-selection placement and handle
   resizing.

Frames are one-click generation area sizes. The resolution rule decides the generation resolution whenever the
generation area size changes. Follow-selection placement moves the area to contain the selection after selection edits.
`src/controller/generation_area_controller.py` applies those three to the live image and config. Handle resizing is
the geometry behind `GenerationAreaTool`'s resize handles.
"""
import math
import re
from typing import Optional

from PySide6.QtCore import QSize, QRect, QPoint, QPointF
from PySide6.QtWidgets import QApplication

# Values of Cache.GENERATION_RESOLUTION_RULE. They must match the options in cache_value_definitions.json.
RESOLUTION_RULE_MATCH_AREA = QApplication.translate('cache_value', 'Match area')
RESOLUTION_RULE_MATCH_AREA_UPSCALED = QApplication.translate('cache_value', 'Match area, upscale small areas')
RESOLUTION_RULE_MANUAL = QApplication.translate('cache_value', 'Manual')

# Values of AppConfig.GENERATION_AREA_FOLLOW_SELECTION. They must match the options in
# application_config_definitions.json.
FOLLOW_SELECTION_MINIMAL = QApplication.translate('application_config', 'Minimal move')
FOLLOW_SELECTION_CENTER = QApplication.translate('application_config', 'Center on selection')
FOLLOW_SELECTION_OFF = QApplication.translate('application_config', 'Off')

# Number of entries kept in Cache.RECENT_GENERATION_AREA_SIZES. It's larger than the number of recent frames shown, so
# filtering out the full image and square frames still leaves enough to show.
MAX_RECENT_SIZES = 8

_SIZE_PATTERN = re.compile(r'^\s*(\d+)\s*(?:[x×*,]\s*(\d+))?\s*$', re.IGNORECASE)

# Largest side parse_size returns. Larger typed values are clamped to it, so QSize and QRect arithmetic on the result
# can't overflow a C int. ImageStack then clamps the area to the image and the area size limits.
MAX_PARSED_SIDE = 1 << 20


def resolution_for_area(area_size: QSize, rule: str, min_side: int, max_size: QSize) -> Optional[QSize]:
    """Returns the generation resolution a resolution rule picks for an area size, or None under the manual rule.

    The upscaled rule multiplies the area size by the smallest whole number that brings its shorter side to at least
    `min_side`, then lowers the factor until the result fits in `max_size`. The factor never drops below one, so an
    area larger than `max_size` keeps its own size.
    """
    if rule == RESOLUTION_RULE_MANUAL:
        return None
    if rule == RESOLUTION_RULE_MATCH_AREA or area_size.isEmpty():
        return QSize(area_size)
    if rule != RESOLUTION_RULE_MATCH_AREA_UPSCALED:
        raise ValueError(f'Unknown resolution rule "{rule}"')
    short_side = min(area_size.width(), area_size.height())
    factor = max(1, math.ceil(min_side / short_side))
    while factor > 1 and (area_size.width() * factor > max_size.width()
                          or area_size.height() * factor > max_size.height()):
        factor -= 1
    return QSize(area_size.width() * factor, area_size.height() * factor)


def full_image_frame(image_size: QSize, max_area_size: QSize) -> QSize:
    """Returns the largest generation area size that covers the image, limited to the maximum area size."""
    return image_size.boundedTo(max_area_size)


def square_frame(image_size: QSize, max_area_size: QSize) -> QSize:
    """Returns the largest square generation area size that fits in the image and the maximum area size."""
    side = min(image_size.width(), image_size.height(), max_area_size.width(), max_area_size.height())
    return QSize(side, side)


def parse_size(text: str) -> Optional[QSize]:
    """Parses a typed frame size, `768` for a square or `640x480`, returning None if the text isn't a positive size.

    Sides larger than MAX_PARSED_SIDE are clamped to it.
    """
    match = _SIZE_PATTERN.match(text)
    if match is None:
        return None
    width = int(match.group(1))
    height = width if match.group(2) is None else int(match.group(2))
    if width <= 0 or height <= 0:
        return None
    return QSize(min(width, MAX_PARSED_SIDE), min(height, MAX_PARSED_SIDE))


def size_to_str(size: QSize) -> str:
    """Formats a size the way Cache.RECENT_GENERATION_AREA_SIZES stores it."""
    return f'{size.width()}x{size.height()}'


def parse_recent_sizes(recent: list[str]) -> list[QSize]:
    """Returns the valid sizes in a stored recent size list, in order, skipping any that don't parse."""
    sizes = []
    for entry in recent:
        size = parse_size(entry) if isinstance(entry, str) else None
        if size is not None:
            sizes.append(size)
    return sizes


def updated_recent_sizes(recent: list[str], size: QSize) -> list[str]:
    """Returns a stored recent size list with `size` moved or added to the front, trimmed to MAX_RECENT_SIZES."""
    size_str = size_to_str(size)
    kept = [size_to_str(entry) for entry in parse_recent_sizes(recent) if entry != size]
    return [size_str, *kept][:MAX_RECENT_SIZES]


def recent_frames(recent: list[str], image_size: QSize, max_area_size: QSize, count: int) -> list[QSize]:
    """Returns up to `count` recent sizes to offer as frames.

    The full image and square frames are excluded, since they're always offered, and so are sizes that don't fit in the
    image or the maximum area size.
    """
    excluded = (full_image_frame(image_size, max_area_size), square_frame(image_size, max_area_size))
    limit = image_size.boundedTo(max_area_size)
    frames = []
    for size in parse_recent_sizes(recent):
        if size in excluded or size.width() > limit.width() or size.height() > limit.height():
            continue
        frames.append(size)
        if len(frames) == count:
            break
    return frames


def previous_frame(recent: list[str], current_size: QSize) -> Optional[QSize]:
    """Returns the most recent stored size that differs from the current area size, or None if there isn't one."""
    for size in parse_recent_sizes(recent):
        if size != current_size:
            return size
    return None


def follow_selection_target(selection_bounds: Optional[QRect], context_pins: list[QPoint],
                            padding: int) -> Optional[QRect]:
    """Returns the bounds the generation area follows: the selection and its context pins, grown by `padding`.

    Returns None when nothing is selected, since pins only count alongside a selection. The result isn't clamped to
    the image.
    """
    if selection_bounds is None or selection_bounds.isEmpty():
        return None
    target = QRect(selection_bounds)
    for pin in context_pins:
        target = target.united(QRect(pin, QSize(1, 1)))
    return target.adjusted(-padding, -padding, padding, padding)


def _follow_axis(area_start: int, area_length: int, target_start: int, target_length: int, center: bool,
                 image_start: int, image_length: int) -> int:
    """Returns the new area start along one axis for follow_selection_position."""
    if center or target_length >= area_length:
        start = target_start + (target_length - area_length) // 2
    else:
        start = min(area_start, target_start)
        start = max(start, target_start + target_length - area_length)
    return max(image_start, min(start, image_start + image_length - area_length))


def follow_selection_position(area: QRect, target: QRect, mode: str, image_bounds: QRect) -> QPoint:
    """Returns where the generation area's top left corner goes to follow a target from follow_selection_target.

    The minimal mode moves the area only as far as it takes to contain the target, and the center mode centers the
    area on it. Along an axis where the target is at least as long as the area, both modes center the area on the
    target. The area keeps its size, and the result keeps it inside `image_bounds` when it fits there.
    """
    if mode == FOLLOW_SELECTION_OFF:
        return area.topLeft()
    if mode not in (FOLLOW_SELECTION_MINIMAL, FOLLOW_SELECTION_CENTER):
        raise ValueError(f'Unknown follow selection mode "{mode}"')
    center = mode == FOLLOW_SELECTION_CENTER
    x = _follow_axis(area.x(), area.width(), target.x(), target.width(), center, image_bounds.x(),
                     image_bounds.width())
    y = _follow_axis(area.y(), area.height(), target.y(), target.height(), center, image_bounds.y(),
                     image_bounds.height())
    return QPoint(x, y)


# Resize handle ids, for area_handle_positions and resize_area_from_handle:
HANDLE_TOP_LEFT = 'top_left'
HANDLE_TOP = 'top'
HANDLE_TOP_RIGHT = 'top_right'
HANDLE_RIGHT = 'right'
HANDLE_BOTTOM_RIGHT = 'bottom_right'
HANDLE_BOTTOM = 'bottom'
HANDLE_BOTTOM_LEFT = 'bottom_left'
HANDLE_LEFT = 'left'
CORNER_HANDLES = (HANDLE_TOP_LEFT, HANDLE_TOP_RIGHT, HANDLE_BOTTOM_RIGHT, HANDLE_BOTTOM_LEFT)
EDGE_HANDLES = (HANDLE_TOP, HANDLE_RIGHT, HANDLE_BOTTOM, HANDLE_LEFT)
_LEFT_SIDE_HANDLES = (HANDLE_TOP_LEFT, HANDLE_LEFT, HANDLE_BOTTOM_LEFT)
_RIGHT_SIDE_HANDLES = (HANDLE_TOP_RIGHT, HANDLE_RIGHT, HANDLE_BOTTOM_RIGHT)
_TOP_SIDE_HANDLES = (HANDLE_TOP_LEFT, HANDLE_TOP, HANDLE_TOP_RIGHT)
_BOTTOM_SIDE_HANDLES = (HANDLE_BOTTOM_LEFT, HANDLE_BOTTOM, HANDLE_BOTTOM_RIGHT)


def area_handle_positions(area: QRect) -> dict[str, QPointF]:
    """Returns each resize handle's position on the area's outline, in image coordinates."""
    left = float(area.x())
    top = float(area.y())
    right = float(area.x() + area.width())
    bottom = float(area.y() + area.height())
    center_x = left + area.width() / 2
    center_y = top + area.height() / 2
    return {
        HANDLE_TOP_LEFT: QPointF(left, top),
        HANDLE_TOP: QPointF(center_x, top),
        HANDLE_TOP_RIGHT: QPointF(right, top),
        HANDLE_RIGHT: QPointF(right, center_y),
        HANDLE_BOTTOM_RIGHT: QPointF(right, bottom),
        HANDLE_BOTTOM: QPointF(center_x, bottom),
        HANDLE_BOTTOM_LEFT: QPointF(left, bottom),
        HANDLE_LEFT: QPointF(left, center_y)
    }


def _clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamps a value, with max_value winning when the range is empty."""
    return min(max(value, min_value), max_value)


def resize_area_from_handle(start_area: QRect, handle: str, point: QPoint, keep_aspect: bool, image_bounds: QRect,
                            min_size: QSize, max_size: QSize) -> QRect:
    """Returns the generation area after dragging one of its resize handles to `point`.

    The sides the handle doesn't touch stay fixed. Each moved side follows `point`, keeping the area within
    `image_bounds` and between `min_size` and `max_size`. With `keep_aspect`, a corner handle keeps `start_area`'s
    aspect ratio, sizing the area to the projection of `point` onto the diagonal through the fixed corner. Edge handles
    ignore `keep_aspect`.
    """
    if handle not in CORNER_HANDLES and handle not in EDGE_HANDLES:
        raise ValueError(f'Unknown handle "{handle}"')
    left = start_area.x()
    top = start_area.y()
    right = start_area.x() + start_area.width()
    bottom = start_area.y() + start_area.height()
    image_right = image_bounds.x() + image_bounds.width()
    image_bottom = image_bounds.y() + image_bounds.height()
    moves_x = handle in _LEFT_SIDE_HANDLES or handle in _RIGHT_SIDE_HANDLES
    moves_y = handle in _TOP_SIDE_HANDLES or handle in _BOTTOM_SIDE_HANDLES

    if handle in _LEFT_SIDE_HANDLES:
        desired_width = right - point.x()
        max_width = min(max_size.width(), right - image_bounds.x())
    else:
        desired_width = point.x() - left
        max_width = min(max_size.width(), image_right - left)
    if handle in _TOP_SIDE_HANDLES:
        desired_height = bottom - point.y()
        max_height = min(max_size.height(), bottom - image_bounds.y())
    else:
        desired_height = point.y() - top
        max_height = min(max_size.height(), image_bottom - top)
    if not moves_x:
        desired_width = start_area.width()
        max_width = start_area.width()
    if not moves_y:
        desired_height = start_area.height()
        max_height = start_area.height()
    min_width = min_size.width() if moves_x else start_area.width()
    min_height = min_size.height() if moves_y else start_area.height()

    if keep_aspect and handle in CORNER_HANDLES and not start_area.isEmpty():
        base_width = start_area.width()
        base_height = start_area.height()
        scale = (desired_width * base_width + desired_height * base_height) / (base_width ** 2 + base_height ** 2)
        scale = _clamp(scale, max(min_width / base_width, min_height / base_height),
                       min(max_width / base_width, max_height / base_height))
        desired_width = round(base_width * scale)
        desired_height = round(base_height * scale)
    width = round(_clamp(desired_width, min_width, max_width))
    height = round(_clamp(desired_height, min_height, max_height))

    x = right - width if handle in _LEFT_SIDE_HANDLES else left
    y = bottom - height if handle in _TOP_SIDE_HANDLES else top
    return QRect(x, y, width, height)
