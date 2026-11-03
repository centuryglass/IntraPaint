"""Tests that ThemeManager applies the configured theme options and follows config changes."""
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.controller.theme_manager import ThemeManager
from src.ui.theme import THEME_INK, THEME_SYSTEM, apply_theme
from test.base_test_case import IntraPaintTestCase


class ThemeManagerTest(IntraPaintTestCase):
    """Tests ThemeManager's initial application and live updates."""

    def tearDown(self) -> None:
        apply_theme(THEME_INK)
        super().tearDown()

    def test_applies_configured_font_size_on_creation(self) -> None:
        """Creating the manager applies the configured font size before any widget exists."""
        size = AppConfig().get(AppConfig.FONT_POINT_SIZE)
        manager = ThemeManager()
        self.assertEqual(size, QApplication.font().pointSize())
        AppConfig().disconnect(manager, AppConfig.FONT_POINT_SIZE)

    def test_config_changes_reapply(self) -> None:
        """Changing the theme and font size options updates the application."""
        manager = ThemeManager()
        original_size = AppConfig().get(AppConfig.FONT_POINT_SIZE)
        try:
            AppConfig().set(AppConfig.FONT_POINT_SIZE, original_size + 2)
            self.assertEqual(original_size + 2, QApplication.font().pointSize())
            palette = QApplication.palette()
            AppConfig().set(AppConfig.THEME, THEME_SYSTEM)
            self.assertNotEqual(palette, QApplication.palette())
        finally:
            AppConfig().set(AppConfig.THEME, THEME_INK)
            AppConfig().set(AppConfig.FONT_POINT_SIZE, original_size)
            for key in (AppConfig.OVERLAY_SCROLL_BARS, AppConfig.ROUNDED_POPUPS, AppConfig.STYLE, AppConfig.THEME,
                        AppConfig.FONT_POINT_SIZE):
                AppConfig().disconnect(manager, key)
