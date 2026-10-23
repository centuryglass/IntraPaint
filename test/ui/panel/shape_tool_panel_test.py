"""Tests ShapeToolPanel: its Cache bindings, the rows each shape type and line style shows, the dash pattern field,
and the arrangements fit planning picks."""
import sys

from PySide6.QtCore import QSize
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import QApplication, QCheckBox

from src.config.cache import Cache
from src.ui.input_fields.pen_join_style_combo_box import JOIN_STYLE_BEVEL, JOIN_STYLE_MITER
from src.ui.input_fields.pen_style_combo_box import LINE_STYLE_CUSTOM, LINE_STYLE_SOLID
from src.ui.input_fields.segmented_control import DisplayMode
from src.ui.layout.panel_fit import Orientation
from src.ui.panel.tool_control_panels.shape_tool_panel import ShapeToolPanel, build_dash_pattern_validator
from src.util.visual.shape_mode import ShapeMode
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class ShapeToolPanelTest(IntraPaintTestCase):
    """Tests ShapeToolPanel."""

    def setUp(self) -> None:
        super().setUp()
        Cache().set(Cache.SHAPE_TOOL_MODE, ShapeMode.ELLIPSE.display_text())
        Cache().set(Cache.SHAPE_TOOL_LINE_STYLE, LINE_STYLE_SOLID)
        self.panel = ShapeToolPanel()

    def _arrange(self, orientation: Orientation, size: QSize) -> None:
        self.panel.set_fit_space(orientation, size)
        self.panel.resize(size)

    def test_dash_validator_accepts_pairs_only(self) -> None:
        """Dash patterns are pairs of numbers, with or without a trailing space. An odd count is never acceptable."""
        validator = build_dash_pattern_validator()
        for text in ('6 3', '6 3 2 3', '6 3 ', '12  4'):
            self.assertEqual(validator.validate(text, len(text))[0], QValidator.State.Acceptable, text)
        for text in ('6', '6 3 2', 'a b'):
            self.assertNotEqual(validator.validate(text, len(text))[0], QValidator.State.Acceptable, text)

    def test_shape_type_shows_only_its_rows(self) -> None:
        """Vertices shows for polygons and stars, and Inner radius for stars only. The stored value is the label the
        shape tool reads."""
        expected = {ShapeMode.ELLIPSE: (False, False), ShapeMode.RECTANGLE: (False, False),
                    ShapeMode.POLYGON: (True, False), ShapeMode.STAR: (True, True)}
        for mode, (vertices, inner_radius) in expected.items():
            self.panel.shape_control.set_value(mode.name)
            self.assertEqual(Cache().get(Cache.SHAPE_TOOL_MODE), mode.display_text())
            self.assertEqual(not self.panel.vertex_field.isHidden(), vertices, mode)
            self.assertEqual(not self.panel.inner_radius_field.isHidden(), inner_radius, mode)

    def test_cache_changes_update_controls(self) -> None:
        """Values set elsewhere, such as by reset, show in the shape type and join controls."""
        Cache().set(Cache.SHAPE_TOOL_MODE, ShapeMode.STAR.display_text())
        self.assertEqual(self.panel.shape_control.value(), ShapeMode.STAR.name)
        Cache().set(Cache.SHAPE_TOOL_LINE_JOIN_STYLE, JOIN_STYLE_MITER)
        self.assertEqual(self.panel.join_control.value(), 'MITER')

    def test_join_stores_its_label(self) -> None:
        """The join control stores the label the shape tool reads."""
        self.panel.join_control.set_value('BEVEL')
        self.assertEqual(Cache().get(Cache.SHAPE_TOOL_LINE_JOIN_STYLE), JOIN_STYLE_BEVEL)

    def test_dash_row_shows_for_custom_style_with_hint(self) -> None:
        """The dash pattern field and its hint show while the line style is custom, and the hint marks unusable
        input."""
        textbox = self.panel.dash_textbox
        self.assertTrue(textbox.isHidden())
        Cache().set(Cache.SHAPE_TOOL_LINE_STYLE, LINE_STYLE_CUSTOM)
        self.assertFalse(textbox.isHidden())
        self.assertFalse(self.panel.dash_hint.isHidden())
        textbox.setText('6')
        self.assertTrue(self.panel.dash_pattern_invalid())
        textbox.setText('6 3')
        self.assertFalse(self.panel.dash_pattern_invalid())
        self.assertEqual(Cache().get(Cache.SHAPE_TOOL_DASH_PATTERN), '6 3')

    def test_width_zero_reads_none(self) -> None:
        """An outline width of 0 reads "none"."""
        Cache().set(Cache.SHAPE_TOOL_LINE_WIDTH, 0)
        self.assertEqual(self.panel.width_field.value_text(), 'none')

    def test_antialias_uses_its_own_label(self) -> None:
        """The antialiasing checkbox takes its label from the shape tool's own key."""
        checkboxes = self.panel.findChildren(QCheckBox)
        self.assertEqual([box.text() for box in checkboxes], ['Antialiasing'])
        Cache().set(Cache.SHAPE_TOOL_ANTIALIAS, False)
        self.assertFalse(checkboxes[0].isChecked())

    def test_narrow_side_panel_shows_shape_icons(self) -> None:
        """A side panel too narrow for the shape type labels shows icons, and a wide one shows labels."""
        self._arrange(Orientation.SIDE, QSize(600, 800))
        self.assertEqual(self.panel.shape_control.display_mode, DisplayMode.LABEL)
        base = self.panel.fit_base_size(Orientation.SIDE)
        self._arrange(Orientation.SIDE, QSize(base.width(), 800))
        self.assertEqual(self.panel.shape_control.display_mode, DisplayMode.ICON)
        self.assertLessEqual(self.panel.minimumSizeHint().width(), base.width())

    def test_wide_side_panel_puts_outline_beside_fill(self) -> None:
        """Outline and Fill sit side by side in a wide side panel, and stack in a narrow one."""
        # pylint: disable=protected-access
        grid = self.panel._grid
        outline, fill = self.panel._outline_section, self.panel._fill_section

        def _row(widget) -> int:
            return grid.getItemPosition(grid.indexOf(widget))[0]
        self._arrange(Orientation.SIDE, QSize(700, 800))
        self.assertEqual(_row(outline), _row(fill))
        self._arrange(Orientation.SIDE, QSize(self.panel.fit_base_size(Orientation.SIDE).width(), 800))
        self.assertLess(_row(outline), _row(fill))

    def test_short_strip_moves_join_to_overflow(self) -> None:
        """A strip too short for Join beside the dash pattern moves it to the overflow content, and a tall strip
        brings it back."""
        Cache().set(Cache.SHAPE_TOOL_LINE_STYLE, LINE_STYLE_CUSTOM)
        join = self.panel.join_control
        base = self.panel.fit_base_size(Orientation.STRIP)
        self._arrange(Orientation.STRIP, QSize(1200, base.height()))
        self.assertIs(join.parentWidget(), self.panel.overflow_content())
        self._arrange(Orientation.STRIP, QSize(1200, 600))
        self.assertIsNot(join.parentWidget(), self.panel.overflow_content())
        self.assertFalse(join.isHidden())
