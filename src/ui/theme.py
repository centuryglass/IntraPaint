"""Applies the application's Qt style, theme and font size.

The default theme, IntraPaint Ink, fixes the interface font and every palette color from
`resources/themes/intrapaint_ink.json`, so widget metrics and colors don't depend on the platform. It also draws
controls with `InkStyle`, wrapped around the configured Qt style. The system look and the optional qdarktheme and
qt-material themes stay available as config options, and use the configured Qt style unwrapped.
"""
import json
import logging
import os
from typing import Any, Optional

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

from src.ui.ink_style import InkColors, InkStyle
from src.util.gc_paused import gc_paused
from src.util.optional_import import optional_import
from src.util.shared_constants import PROJECT_DIR

qdarktheme = optional_import('qdarktheme')
qt_material = optional_import('qt_material')

logger = logging.getLogger(__name__)

THEME_INK = 'intrapaint_ink'
THEME_SYSTEM = 'None'
INK_THEME_PATH = f'{PROJECT_DIR}/resources/themes/intrapaint_ink.json'

_PALETTE_GROUPS = {'all': QPalette.ColorGroup.All, 'disabled': QPalette.ColorGroup.Disabled}


class _ThemeState:
    """Values kept between theme changes."""

    def __init__(self) -> None:
        # The application font and palette before any theme changed them, restored by THEME_SYSTEM:
        self.system_font: Optional[QFont] = None
        self.system_palette: Optional[QPalette] = None
        # The loaded IntraPaint Ink font, palette and style colors. Its font files register with Qt once, on first
        # load:
        self.ink_theme: Optional[tuple[Optional[QFont], QPalette, InkColors]] = None
        # The configured Qt style name, the applied theme and the scroll bar option, which together pick the
        # installed QStyle:
        self.style_name: Optional[str] = None
        self.theme: Optional[str] = None
        self.overlay_scroll_bars = True
        # The installed InkStyle. QApplication owns it, and deletes it when another style replaces it:
        self.ink_style: Optional[InkStyle] = None


_state = _ThemeState()


def _app() -> QApplication:
    app = QApplication.instance()
    assert isinstance(app, QApplication), 'Themes need a QApplication'
    return app


def load_theme_font(font_data: dict[str, Any]) -> Optional[QFont]:
    """Registers a theme's font files and returns its font, or None if any file fails to load.

    The font has no size: callers keep the application's current point size. Characters `family` lacks come from
    `fallback_families`, in order. A character none of them has comes from a system font, so its width depends on the
    platform: the fallbacks need to cover every symbol the interface draws, such as the key symbols in
    `src/util/visual/text_drawing_utils.py`.
    """
    for font_file in font_data['files']:
        if QFontDatabase.addApplicationFont(os.path.join(PROJECT_DIR, font_file)) < 0:
            logger.error(f'Failed to load theme font file {font_file}, keeping the system font')
            return None
    font = QFont(font_data['family'])
    font.setFamilies([font_data['family'], *font_data.get('fallback_families', [])])
    # Hinting only vertical positions keeps glyph advances, and so text widths, the same on every platform:
    font.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
    for feature, value in font_data.get('features', {}).items():
        font.setFeature(QFont.Tag(feature), int(value))
    return font


def load_theme_palette(palette_data: dict[str, dict[str, str]]) -> QPalette:
    """Builds a palette from a theme's color groups.

    Colors in `all` apply to every group, and other groups then override them. Roles a theme leaves out keep the
    system's color, so a complete theme sets every role in `all`.

    Raises
    ------
    ValueError
        If a group or role name isn't a QPalette name, or a color doesn't parse.
    """
    palette = QPalette()
    for group_name in sorted(palette_data, key=lambda name: name != 'all'):
        if group_name not in _PALETTE_GROUPS:
            raise ValueError(f'Unknown palette group "{group_name}", expected one of {list(_PALETTE_GROUPS)}')
        group = _PALETTE_GROUPS[group_name]
        for role_name, color_str in palette_data[group_name].items():
            role = getattr(QPalette.ColorRole, role_name, None)
            if not isinstance(role, QPalette.ColorRole) or role in (QPalette.ColorRole.NoRole,
                                                                     QPalette.ColorRole.NColorRoles):
                raise ValueError(f'Unknown palette role "{role_name}"')
            color = QColor(color_str)
            if not color.isValid():
                raise ValueError(f'Invalid color "{color_str}" for palette role {role_name}')
            palette.setColor(group, role, color)
    return palette


def _load_ink_theme() -> tuple[Optional[QFont], QPalette, InkColors]:
    if _state.ink_theme is None:
        with open(INK_THEME_PATH, encoding='utf-8') as theme_file:
            theme_data = json.load(theme_file)
        _state.ink_theme = (load_theme_font(theme_data['font']), load_theme_palette(theme_data['palette']),
                            InkColors.from_theme_data(theme_data['style_colors']))
    return _state.ink_theme


def _install_style() -> None:
    """Installs the configured Qt style, wrapped in InkStyle while THEME_INK is applied.

    Call this inside gc_paused. QApplication.setStyle keeps an application palette that was set explicitly, so the
    theme's palette survives a style change.
    """
    app = _app()
    style_name = _state.style_name if _state.style_name is not None else app.style().name()
    if _state.theme == THEME_INK:
        if style_name.lower() not in (key.lower() for key in QStyleFactory.keys()):
            logger.error(f'Unknown Qt style {style_name}, using Fusion')
            style_name = 'Fusion'
        _, _, colors = _load_ink_theme()
        _state.ink_style = InkStyle(style_name, colors, _state.overlay_scroll_bars)
        app.setStyle(_state.ink_style)
    else:
        _state.ink_style = None
        app.setStyle(style_name)


def _set_font_family(font: QFont) -> None:
    """Sets the application font, keeping its current point size."""
    app = _app()
    sized_font = QFont(font)
    point_size = app.font().pointSizeF()
    if point_size > 0:
        sized_font.setPointSizeF(point_size)
    app.setFont(sized_font)


def apply_theme(theme: str) -> None:
    """Applies a theme option from `AppConfig.THEME` to the application.

    THEME_INK and THEME_SYSTEM also clear any stylesheet a theme package set. Widgets that copied the palette or font
    when they were created keep the old values, so apply the theme before creating the main window.
    """
    app = _app()
    if _state.system_font is None or _state.system_palette is None:
        _state.system_font = QFont(app.font())
        _state.system_palette = QPalette(app.palette())
    # Both theme packages call QApplication.setStyleSheet, which has the hazard gc_paused describes.
    with gc_paused():
        _state.theme = theme
        if (theme == THEME_INK) != (_state.ink_style is not None):
            _install_style()
        if theme in (THEME_INK, THEME_SYSTEM):
            if app.styleSheet() != '':
                app.setStyleSheet('')
            if theme == THEME_INK:
                font, palette, _ = _load_ink_theme()
            else:
                font, palette = _state.system_font, _state.system_palette
            if font is not None:
                _set_font_family(font)
            app.setPalette(palette)
        elif theme.startswith('qdarktheme_') and qdarktheme is not None and hasattr(qdarktheme, 'setup_theme'):
            if theme.endswith('_light'):
                qdarktheme.setup_theme('light')
            elif theme.endswith('_auto'):
                qdarktheme.setup_theme('auto')
            else:
                qdarktheme.setup_theme()
        elif theme.startswith('qt_material_') and qt_material is not None:
            qt_material.apply_stylesheet(app, theme=theme[len('qt_material_'):])
        else:
            logger.error(f'Failed to load theme {theme}')


def apply_style(style: str) -> None:
    """Applies a Qt style name from `AppConfig.STYLE` to the application."""
    _state.style_name = style
    with gc_paused():
        _install_style()


def apply_overlay_scroll_bars(overlay: bool) -> None:
    """Sets whether THEME_INK draws scroll bars over their content, from `AppConfig.OVERLAY_SCROLL_BARS`."""
    if overlay == _state.overlay_scroll_bars:
        return
    _state.overlay_scroll_bars = overlay
    if _state.theme == THEME_INK:
        with gc_paused():
            _install_style()


def apply_font_point_size(font_pt: int) -> None:
    """Sets the application font's point size."""
    app = _app()
    font = app.font()
    font.setPointSize(font_pt)
    app.setFont(font)
