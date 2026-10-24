"""Tests that the shape and pattern combo boxes save untranslated option names in `Cache`."""
from src.config.cache import Cache
from src.ui.input_fields.fill_style_combo_box import BRUSH_PATTERN_DENSE_4, FillStyleComboBox
from src.ui.input_fields.pen_join_style_combo_box import JOIN_STYLE_BEVEL, PenJoinStyleComboBox
from src.ui.input_fields.pen_style_combo_box import LINE_STYLE_DASH, PenStyleComboBox
from src.ui.input_fields.shape_mode_combo_box import ShapeModeComboBox
from src.util.visual.shape_mode import ShapeMode
from test.base_test_case import IntraPaintTestCase


class OptionComboBoxTest(IntraPaintTestCase):
    """Tests the option names saved by the shape tool's combo boxes."""

    def test_saved_values_ignore_item_text(self) -> None:
        """Choosing an item saves its option name, whatever text the item shows, and loads from the name alone."""
        cases = [(PenStyleComboBox(Cache.SHAPE_TOOL_LINE_STYLE), LINE_STYLE_DASH, Cache.SHAPE_TOOL_LINE_STYLE),
                 (PenJoinStyleComboBox(Cache.SHAPE_TOOL_LINE_JOIN_STYLE), JOIN_STYLE_BEVEL,
                  Cache.SHAPE_TOOL_LINE_JOIN_STYLE),
                 (FillStyleComboBox(Cache.SHAPE_TOOL_FILL_PATTERN), BRUSH_PATTERN_DENSE_4,
                  Cache.SHAPE_TOOL_FILL_PATTERN)]
        for box, option, key in cases:
            for index in range(box.count()):
                box.setItemText(index, f'translated {index}')
            box.set_option(option)
            self.assertEqual(Cache().get(key), option)
            box.setCurrentIndex(0)
            Cache().set(key, option)
            self.assertEqual(box.option(), option)

    def test_shape_mode_saves_name(self) -> None:
        """The shape mode box saves `ShapeMode.name`, and every mode name is valid."""
        box = ShapeModeComboBox(Cache.SHAPE_TOOL_MODE)
        for mode in reversed(list(ShapeMode)):
            self.assertTrue(ShapeMode.is_valid_mode_str(mode.name))
            box.setValue(mode)
            self.assertEqual(Cache().get(Cache.SHAPE_TOOL_MODE), mode.name)
            self.assertIs(ShapeMode.from_text(mode.name), mode)
        self.assertFalse(ShapeMode.is_valid_mode_str(ShapeMode.STAR.display_text()))
