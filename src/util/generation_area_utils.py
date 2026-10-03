"""Pure helpers for generation area frames and the generation resolution rule.

Frames are one-click generation area sizes. The resolution rule decides the generation resolution whenever the
generation area size changes. `src/controller/generation_area_controller.py` applies both to the live image and config.
"""
import math
import re
from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

# Values of Cache.GENERATION_RESOLUTION_RULE. They must match the options in cache_value_definitions.json.
RESOLUTION_RULE_MATCH_AREA = QApplication.translate('cache_value', 'Match area')
RESOLUTION_RULE_MATCH_AREA_UPSCALED = QApplication.translate('cache_value', 'Match area, upscale small areas')
RESOLUTION_RULE_MANUAL = QApplication.translate('cache_value', 'Manual')

# Number of entries kept in Cache.RECENT_GENERATION_AREA_SIZES. It's larger than the number of recent frames shown, so
# filtering out the full image and square frames still leaves enough to show.
MAX_RECENT_SIZES = 8

_SIZE_PATTERN = re.compile(r'^\s*(\d+)\s*(?:[x×*,]\s*(\d+))?\s*$', re.IGNORECASE)


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
    """Parses a typed frame size, `768` for a square or `640x480`, returning None if the text isn't a positive size."""
    match = _SIZE_PATTERN.match(text)
    if match is None:
        return None
    width = int(match.group(1))
    height = width if match.group(2) is None else int(match.group(2))
    if width <= 0 or height <= 0:
        return None
    return QSize(width, height)


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
