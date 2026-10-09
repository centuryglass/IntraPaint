"""Foreground/background color pair operations, and the recent and saved color lists.

The foreground color is `Cache.LAST_BRUSH_COLOR` and the background color is `Cache.BACKGROUND_COLOR`. Every write goes
through `Config.set_color`, so listeners keep using `Cache().connect` on those keys.

Browsing and choosing are separate: `set_foreground` and `set_background` with `commit=False` only change the color,
while a commit also pushes the color onto `Cache.RECENT_COLORS`. Picker drags write without committing; a finished
choice (dialog OK, eyedropper pick, swatch click) commits.

Saved colors are `AppConfig.SAVED_COLORS`, a user-curated list kept in the order colors were saved, holding at most
MAX_SAVED_COLORS. Entries past the cap in a hand-edited config are ignored, and the next change to the list drops them.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from src.config.application_config import AppConfig
from src.config.cache import Cache

MAX_RECENT_COLORS = 16
MAX_SAVED_COLORS = 64
DEFAULT_FOREGROUND = QColor(Qt.GlobalColor.black)
DEFAULT_BACKGROUND = QColor(Qt.GlobalColor.white)


def foreground() -> QColor:
    """Returns the foreground color."""
    return Cache().get_color(Cache.LAST_BRUSH_COLOR, DEFAULT_FOREGROUND)


def background() -> QColor:
    """Returns the background color."""
    return Cache().get_color(Cache.BACKGROUND_COLOR, DEFAULT_BACKGROUND)


def set_foreground(color: QColor, commit: bool = True) -> None:
    """Sets the foreground color, adding it to the recent colors if `commit` is true."""
    Cache().set_color(Cache.LAST_BRUSH_COLOR, color)
    if commit:
        commit_color(color)


def set_background(color: QColor, commit: bool = True) -> None:
    """Sets the background color, adding it to the recent colors if `commit` is true."""
    Cache().set_color(Cache.BACKGROUND_COLOR, color)
    if commit:
        commit_color(color)


def swap() -> None:
    """Exchanges the foreground and background colors.

    This is two cache writes, so foreground listeners briefly see the foreground equal to the background.
    """
    old_foreground = foreground()
    set_foreground(background(), commit=False)
    set_background(old_foreground, commit=False)


def reset() -> None:
    """Sets the foreground color to black and the background color to white."""
    set_foreground(DEFAULT_FOREGROUND, commit=False)
    set_background(DEFAULT_BACKGROUND, commit=False)


def recent_colors() -> list[QColor]:
    """Returns the recent colors, newest first, skipping any saved value that isn't a valid color."""
    return [QColor(color_str) for color_str in Cache().get(Cache.RECENT_COLORS) if QColor(color_str).isValid()]


def updated_recent_colors(recent: list[str], color: QColor) -> list[str]:
    """Returns a recent colors list with `color` moved or added to the front, without duplicates, capped at
    MAX_RECENT_COLORS."""
    color_str = color.name(QColor.NameFormat.HexArgb)
    others = [entry for entry in recent if QColor(entry).isValid()
              and QColor(entry).name(QColor.NameFormat.HexArgb) != color_str]
    return [color_str, *others][:MAX_RECENT_COLORS]


def commit_color(color: QColor) -> None:
    """Records a chosen color at the front of the recent colors list."""
    cache = Cache()
    recent = cache.get(Cache.RECENT_COLORS)
    updated = updated_recent_colors(recent, color)
    if updated != recent:
        cache.set(Cache.RECENT_COLORS, updated)


def saved_colors() -> list[QColor]:
    """Returns the first MAX_SAVED_COLORS saved colors in the order they were saved, skipping invalid values."""
    colors = [QColor(color_str) for color_str in AppConfig().get(AppConfig.SAVED_COLORS) if QColor(color_str).isValid()]
    return colors[:MAX_SAVED_COLORS]


def _set_saved_colors(colors: list[QColor]) -> None:
    AppConfig().set(AppConfig.SAVED_COLORS, [color.name(QColor.NameFormat.HexArgb) for color in colors])


def saved_color_index(color: QColor) -> int:
    """Returns a color's index in `saved_colors()`, or -1 if it isn't saved."""
    color_str = color.name(QColor.NameFormat.HexArgb)
    for index, saved in enumerate(saved_colors()):
        if saved.name(QColor.NameFormat.HexArgb) == color_str:
            return index
    return -1


def saved_colors_full() -> bool:
    """Returns whether the saved colors hold MAX_SAVED_COLORS, so no new color can be saved."""
    return len(saved_colors()) >= MAX_SAVED_COLORS


def save_color(color: QColor) -> bool:
    """Adds a color to the end of the saved colors. Returns false if it was already saved or the list is full."""
    if saved_color_index(color) >= 0 or saved_colors_full():
        return False
    _set_saved_colors([*saved_colors(), color])
    return True


def insert_saved_color(color: QColor, index: int) -> bool:
    """Puts a color into the saved colors before an index into `saved_colors()`, moving it there if it is already
    saved. Returns false, changing nothing, if it is a new color and the list is full."""
    colors = saved_colors()
    saved_index = saved_color_index(color)
    if saved_index >= 0:
        del colors[saved_index]
        if saved_index < index:
            index -= 1
    elif len(colors) >= MAX_SAVED_COLORS:
        return False
    colors.insert(max(0, min(index, len(colors))), QColor(color))
    _set_saved_colors(colors)
    return True


def remove_saved_color(index: int) -> None:
    """Removes the saved color at an index into `saved_colors()`."""
    colors = saved_colors()
    if 0 <= index < len(colors):
        del colors[index]
        _set_saved_colors(colors)
