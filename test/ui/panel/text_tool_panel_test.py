"""Tests TextToolPanel: the box-fit choice and the stored text rect, the font filter, the overflow badge, and the
arrangements fit planning picks."""
import json
import sys

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QWidget

from src.config.cache import Cache
from src.image.text_rect import (SCALE_MODE_BOUNDS_TO_TEXT, SCALE_MODE_NONE, SCALE_MODE_TEXT_TO_BOUNDS, TextRect,
                                 TextRectKeys)
from src.ui.input_fields.segmented_control import DisplayMode
from src.ui.layout.panel_fit import Orientation
from src.ui.panel.tool_control_panels.text_tool_panel import TextToolPanel
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class TextToolPanelTest(IntraPaintTestCase):
    """Tests TextToolPanel."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.TEXT_TOOL_PARAMS, '')
        self.panel = TextToolPanel()

    def _stored_scale_mode(self) -> str:
        return json.loads(Cache().get(Cache.TEXT_TOOL_PARAMS))[TextRectKeys.AUTO_SCALE_MODE]

    def _arrange(self, orientation: Orientation, size: QSize) -> None:
        self.panel.set_fit_space(orientation, size)
        self.panel.resize(size)

    def test_box_fit_round_trips(self) -> None:
        """Each box-fit choice sets the text rect's scale mode and stores it, and a text rect loaded with either mode
        shows its choice."""
        control = self.panel.box_fit_control
        for mode, text_to_bounds, bounds_to_text in ((SCALE_MODE_TEXT_TO_BOUNDS, True, False),
                                                     (SCALE_MODE_BOUNDS_TO_TEXT, False, True),
                                                     (SCALE_MODE_NONE, False, False)):
            control.set_value(mode)
            self.assertEqual(self.panel.text_rect.scale_text_to_bounds, text_to_bounds, mode)
            self.assertEqual(self.panel.text_rect.scale_bounds_to_text, bounds_to_text, mode)
            self.assertEqual(self._stored_scale_mode(), mode)
        for mode in (SCALE_MODE_TEXT_TO_BOUNDS, SCALE_MODE_BOUNDS_TO_TEXT, SCALE_MODE_NONE):
            text_rect = TextRect()
            text_rect.scale_text_to_bounds = mode == SCALE_MODE_TEXT_TO_BOUNDS
            text_rect.scale_bounds_to_text = mode == SCALE_MODE_BOUNDS_TO_TEXT
            self.panel.text_rect = text_rect
            self.assertEqual(control.value(), mode)

    def test_stored_box_fit_loads(self) -> None:
        """A new panel shows the box-fit choice stored by the last one."""
        self.panel.box_fit_control.set_value(SCALE_MODE_BOUNDS_TO_TEXT)
        self.assertEqual(TextToolPanel().box_fit_control.value(), SCALE_MODE_BOUNDS_TO_TEXT)

    def test_fit_box_resizes_the_box(self) -> None:
        """With Fit box, typing resizes the W and H fields to the text."""
        self.panel.box_fit_control.set_value(SCALE_MODE_BOUNDS_TO_TEXT)
        self.panel.text_box.setPlainText('A much longer line of text')
        size = self.panel.text_rect.size
        geometry = self.panel.geometry_block
        self.assertEqual((geometry.value('w'), geometry.value('h')), (size.width(), size.height()))

    def test_font_filter_narrows_the_list(self) -> None:
        """Typing in the filter field hides the families that don't contain it, ignoring case, and clearing it shows
        them all again."""
        font_list = self.panel.font_list
        families = [font_list.item(row).text() for row in range(font_list.count())]
        self.assertGreater(len(families), 1)
        target = families[len(families) // 2]
        self.panel.font_filter.setText(target.upper())
        shown = [font_list.item(row).text() for row in range(font_list.count()) if not font_list.item(row).isHidden()]
        self.assertIn(target, shown)
        self.assertLess(len(shown), len(families))
        self.assertTrue(all(target.casefold() in family.casefold() for family in shown))
        self.panel.font_filter.setText('')
        self.assertFalse(any(font_list.item(row).isHidden() for row in range(font_list.count())))

    def test_font_combo_selects_family(self) -> None:
        """Picking a family in the font combo sets the font and selects it in the list."""
        combo = self.panel.font_combo
        row = combo.count() - 1
        combo.setCurrentIndex(row)
        family = self.panel.font_list.item(row).text()
        self.assertEqual(self.panel.text_rect.font.family(), family)
        self.assertEqual(self.panel.font_list.currentItem().text(), family)

    def test_overflow_badge_shows_for_overflowing_text(self) -> None:
        """The Overflows badge shows while the text is larger than a free box, and hides once Fit box resizes it."""
        badge = self.panel.overflow_badge
        text_rect = self.panel.text_rect
        text_rect.size = QSize(10, 10)
        self.panel.text_rect = text_rect
        self.panel.text_box.setPlainText('Too much text for a tiny box')
        self.assertFalse(badge.isHidden())
        self.panel.box_fit_control.set_value(SCALE_MODE_BOUNDS_TO_TEXT)
        self.assertTrue(badge.isHidden())

    def test_wide_side_panel_uses_two_columns(self) -> None:
        """A wide side panel puts Style beside Font, and a narrow one stacks them."""
        # pylint: disable=protected-access
        grid = self.panel._grid

        def _row(widget) -> int:
            return grid.getItemPosition(grid.indexOf(widget))[0]
        self._arrange(Orientation.SIDE, QSize(800, 1200))
        self.assertEqual(_row(self.panel._font_section), _row(self.panel._style_section))
        self._arrange(Orientation.SIDE, QSize(self.panel.fit_base_size(Orientation.SIDE).width(), 1200))
        self.assertLess(_row(self.panel._font_section), _row(self.panel._style_section))

    def test_short_strip_uses_combo_and_overflow(self) -> None:
        """A strip too short for the font list shows the font combo and icon-only box fit, moves Advanced to the
        overflow content and hides the preview. A tall strip shows them all."""
        base = self.panel.fit_base_size(Orientation.STRIP)
        self._arrange(Orientation.STRIP, QSize(1400, base.height()))
        self.assertTrue(self.panel.font_list.isHidden())
        self.assertFalse(self.panel.font_combo.isHidden())
        self.assertEqual(self.panel.box_fit_control.display_mode, DisplayMode.ICON)
        self.assertIs(self.panel.advanced_section.parentWidget(), self.panel.overflow_content())
        self.assertTrue(self.panel.preview_section.isHidden())
        self._arrange(Orientation.STRIP, QSize(1400, 800))
        self.assertFalse(self.panel.font_list.isHidden())
        self.assertIsNot(self.panel.advanced_section.parentWidget(), self.panel.overflow_content())
        self.assertFalse(self.panel.advanced_section.isHidden())
        self.assertFalse(self.panel.preview_section.isHidden())

    def test_preview_respects_its_minimum_size(self) -> None:
        """Wherever the preview shows, it is at least its minimum size."""
        # pylint: disable=protected-access
        preview = self.panel._preview
        for orientation, size in ((Orientation.SIDE, QSize(360, 1400)), (Orientation.STRIP, QSize(1400, 400))):
            self._arrange(orientation, size)
            for widget in (self.panel, *self.panel.findChildren(QWidget)):
                if widget.layout() is not None:
                    widget.layout().activate()
            self.assertFalse(self.panel.preview_section.isHidden(), orientation)
            self.assertGreaterEqual(preview.height(), preview.minimumSizeHint().height(), orientation)
            self.assertGreaterEqual(preview.width(), preview.minimumSizeHint().width(), orientation)
