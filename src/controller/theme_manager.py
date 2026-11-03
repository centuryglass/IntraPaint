"""ThemeManager keeps the application's Qt style, theme and font size in step with `AppConfig`.

Construct it before creating any widget: widgets copy the palette and font when they are created, so the initial values
have to be applied first. The apply functions themselves live in `src/ui/theme.py`.
"""
from src.config.application_config import AppConfig
from src.ui.theme import (apply_font_point_size, apply_overlay_scroll_bars, apply_rounded_popups, apply_style,
                          apply_theme)


class ThemeManager:
    """Applies the configured style, theme and font size, and reapplies them when the config changes."""

    def __init__(self) -> None:
        config = AppConfig()
        # Order matters: the scroll bar and popup options and the style pick the installed QStyle that the theme and
        # font are applied on top of.
        for key, apply_fn in ((AppConfig.OVERLAY_SCROLL_BARS, apply_overlay_scroll_bars),
                              (AppConfig.ROUNDED_POPUPS, apply_rounded_popups),
                              (AppConfig.STYLE, apply_style),
                              (AppConfig.THEME, apply_theme),
                              (AppConfig.FONT_POINT_SIZE, apply_font_point_size)):
            config.connect(self, key, apply_fn)
            apply_fn(config.get(key))
