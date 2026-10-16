"""Tests StrokeBlock's binding to Cache values, its pen pressure links and its arrangements."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox

from src.config.cache import Cache
from src.ui.panel.tool_control_panels.draw_tool_panel import DrawToolPanel
from src.ui.panel.tool_control_panels.stroke_block import (ONLY_INSIDE_SELECTION_LABEL, PREVIEW_MIN_WIDTH,
                                                           STACK_CHECKBOXES_WIDTH)
from test.base_test_case import IntraPaintTestCase


class StrokeBlockTest(IntraPaintTestCase):
    """Tests the Draw panel's stroke block."""

    def setUp(self) -> None:
        super().setUp()
        self.panel = DrawToolPanel()
        self.block = self.panel.stroke_block

    def test_fields_follow_cache_both_ways(self) -> None:
        """A field change sets the Cache value, and a Cache change moves the field."""
        size_field = self.block.field(Cache.DRAW_TOOL_BRUSH_SIZE)
        size_field.set_value(77)
        self.assertEqual(Cache().get(Cache.DRAW_TOOL_BRUSH_SIZE), 77)
        Cache().set(Cache.DRAW_TOOL_OPACITY, 0.5)
        self.assertEqual(self.block.field(Cache.DRAW_TOOL_OPACITY).value(), 0.5)

    def test_field_order_is_fixed(self) -> None:
        """Size, Opacity and Hardness appear in that order."""
        self.assertEqual([field.label() for field in self.block.fields()], ['Size', 'Opacity', 'Hardness'])

    def test_pressure_links_follow_cache_and_appear_with_a_tablet(self) -> None:
        """Links are hidden until a tablet is seen, and toggling one sets its Cache value."""
        Cache().set(Cache.EXPECT_TABLET_INPUT, False)
        panel = DrawToolPanel()
        field = panel.stroke_block.field(Cache.DRAW_TOOL_BRUSH_SIZE)
        self.assertFalse(field.pressure_link_available())
        panel.show_pressure_checkboxes()
        self.assertTrue(field.pressure_link_available())
        field.set_pressure_link_enabled(False)
        self.assertFalse(Cache().get(Cache.DRAW_TOOL_PRESSURE_SIZE))

    def test_selection_checkbox_uses_the_shared_label(self) -> None:
        """The selection option reads the same in every tool."""
        texts = [box.text() for box in self.block.findChildren(QCheckBox)]
        self.assertIn(ONLY_INSIDE_SELECTION_LABEL, texts)

    def test_arrangements_follow_width_and_orientation(self) -> None:
        """Narrow side panels stack checkboxes, wide ones show the preview, strips use two columns."""
        self.block.arrange_for_width(STACK_CHECKBOXES_WIDTH - 20)
        self.assertEqual(self.block._arrangement, (Qt.Orientation.Vertical, True, False))
        self.block.arrange_for_width(PREVIEW_MIN_WIDTH + 20)
        self.assertEqual(self.block._arrangement, (Qt.Orientation.Vertical, False, True))
        self.panel.set_orientation(Qt.Orientation.Horizontal)
        self.assertEqual(self.block._arrangement, (Qt.Orientation.Horizontal, False, False))
