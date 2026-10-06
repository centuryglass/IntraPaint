"""Foreground/background color pair operations, and the recent and saved color lists.

The foreground color is `Cache.LAST_BRUSH_COLOR` and the background color is `Cache.BACKGROUND_COLOR`. Every write goes
through `Config.set_color`, so listeners keep using `Cache().connect` on those keys.

Browsing and choosing are separate: `set_foreground` and `set_background` with `commit=False` only change the color,
while a commit also pushes the color onto `Cache.RECENT_COLORS`. Picker drags write without committing; a finished
choice (dialog OK, eyedropper pick, swatch click) commits.

Saved colors are `AppConfig.SAVED_COLORS`, a user-curated list kept in the order colors were saved.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from src.config.application_config import AppConfig
from src.config.cache import Cache

MAX_RECENT_COLORS = 16
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
    """Returns the saved colors, in the order they were saved, skipping any value that isn't a valid color."""
    return [QColor(color_str) for color_str in AppConfig().get(AppConfig.SAVED_COLORS) if QColor(color_str).isValid()]


def _set_saved_colors(colors: list[QColor]) -> None:
    AppConfig().set(AppConfig.SAVED_COLORS, [color.name(QColor.NameFormat.HexArgb) for color in colors])


def save_color(color: QColor) -> None:
    """Adds a color to the end of the saved colors, unless it is already saved."""
    colors = saved_colors()
    color_str = color.name(QColor.NameFormat.HexArgb)
    if any(saved.name(QColor.NameFormat.HexArgb) == color_str for saved in colors):
        return
    _set_saved_colors([*colors, color])


def insert_saved_color(color: QColor, index: int) -> None:
    """Puts a color into the saved colors before an index into `saved_colors()`, moving it there if it is already
    saved."""
    colors = saved_colors()
    color_str = color.name(QColor.NameFormat.HexArgb)
    for saved_index, saved in enumerate(colors):
        if saved.name(QColor.NameFormat.HexArgb) == color_str:
            del colors[saved_index]
            if saved_index < index:
                index -= 1
            break
    colors.insert(max(0, min(index, len(colors))), QColor(color))
    _set_saved_colors(colors)


def remove_saved_color(index: int) -> None:
    """Removes the saved color at an index into `saved_colors()`."""
    colors = saved_colors()
    if 0 <= index < len(colors):
        del colors[index]
        _set_saved_colors(colors)
