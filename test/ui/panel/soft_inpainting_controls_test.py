"""Tests for the soft inpainting controls under themes that provide no Ink colors."""
from PySide6.QtGui import QPalette

from src.ui.ink_style import caution_color
from src.ui.panel.generators.soft_inpainting_controls import SoftInpaintingControls
from src.ui.theme import THEME_INK, THEME_SYSTEM, apply_theme
from test.base_test_case import IntraPaintTestCase


class SoftInpaintingControlsTest(IntraPaintTestCase):
    """The test session applies THEME_INK in conftest.py, so each test starts and ends with it applied."""

    def tearDown(self) -> None:
        apply_theme(THEME_INK)
        super().tearDown()

    def test_hint_uses_caution_color_under_ink_style(self) -> None:
        """The hint draws in the caution color while InkStyle provides one."""
        controls = SoftInpaintingControls()
        color = caution_color()
        assert color is not None
        self.assertEqual(color, controls.hint.palette().color(QPalette.ColorRole.WindowText))

    def test_builds_without_ink_style(self) -> None:
        """Without InkStyle there is no caution color, and the hint keeps its inherited color."""
        apply_theme(THEME_SYSTEM)
        self.assertIsNone(caution_color())
        controls = SoftInpaintingControls()
        self.assertEqual(controls.palette().color(QPalette.ColorRole.WindowText),
                         controls.hint.palette().color(QPalette.ColorRole.WindowText))
