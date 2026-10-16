"""Tests StrokeBlock's binding to Cache values, its pen pressure links and its arrangements."""
import json

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QCheckBox

from src.config.cache import Cache
from src.tools.filter_tool import FilterTool
from src.ui.panel.tool_control_panels.clone_stamp_tool_panel import CloneStampToolPanel
from src.ui.panel.tool_control_panels.draw_tool_panel import DrawToolPanel
from src.ui.panel.tool_control_panels.eraser_tool_panel import EraserToolPanel
from src.ui.panel.tool_control_panels.fill_tool_panel import FillToolPanel
from src.ui.panel.tool_control_panels.filter_tool_panel import FilterToolPanel
from src.ui.panel.tool_control_panels.smudge_tool_panel import SmudgeToolPanel
from src.ui.panel.tool_control_panels.stroke_block import (ONLY_INSIDE_SELECTION_LABEL, PREVIEW_MIN_WIDTH,
                                                           STACK_CHECKBOXES_WIDTH)
from test.base_test_case import IntraPaintTestCase
from test.tools.tool_test_case import ToolTestCase
from test.ui.panel.tool_panel_test import settle_layouts


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


class ToolPanelsOnStrokeBlockTest(ToolTestCase):
    """Tests the panels that share the stroke block with Draw, and the tool-specific sections after it."""

    def _filter_panel(self) -> FilterToolPanel:
        panel = FilterTool(self.image_stack, self.image_viewer).get_control_panel()
        assert isinstance(panel, FilterToolPanel)
        return panel

    def test_size_field_keeps_its_position_between_tools(self) -> None:
        """Draw, Eraser, Smudge, Clone stamp and Filter put Size first with the same label and geometry."""
        panels = [DrawToolPanel(), EraserToolPanel(), SmudgeToolPanel(), CloneStampToolPanel(),
                  self._filter_panel()]
        positions = []
        for panel in panels:
            panel.resize(340, 600)
            panel.show()
            settle_layouts(panel)
            size_field = panel.stroke_block.fields()[0]
            self.assertEqual(size_field.label(), 'Size')
            positions.append(size_field.mapTo(panel, size_field.rect().topLeft()))
        self.assertEqual(len(set((point.x(), point.y()) for point in positions)), 1)

    def test_smudge_and_filter_read_opacity_as_strength(self) -> None:
        """The second field is Strength, bound to the opacity value."""
        for panel, key in ((SmudgeToolPanel(), Cache.SMUDGE_TOOL_OPACITY),
                           (self._filter_panel(), Cache.FILTER_TOOL_OPACITY)):
            field = panel.stroke_block.field(key)
            self.assertEqual(field.label(), 'Strength')
            field.set_value(0.75)
            self.assertEqual(Cache().get(key), 0.75)

    def test_clone_stamp_mode_binds_raw_values(self) -> None:
        """The source mode control stores the raw option, and the X/Y labels follow it."""
        Cache().update_options(Cache.CLONE_STAMP_TOOL_SOURCE_MODE,
                               ['Fixed offset', 'Dynamic offset', 'Fixed position'])
        panel = CloneStampToolPanel()
        control = panel._source_mode_control
        control.set_value('Fixed position')
        self.assertEqual(Cache().get(Cache.CLONE_STAMP_TOOL_SOURCE_MODE), 'Fixed position')
        self.assertEqual(panel._x_field.label(), 'Source X')
        Cache().set(Cache.CLONE_STAMP_TOOL_SOURCE_MODE, 'Dynamic offset')
        self.assertEqual(control.value(), 'Dynamic offset')
        self.assertEqual(panel._y_field.label(), 'Offset Y')

    def test_clone_stamp_source_xy_signal(self) -> None:
        """Editing a field emits the combined point, and the setter fills both fields."""
        panel = CloneStampToolPanel()
        points = []
        panel.source_xy_change.connect(points.append)
        panel._x_field.set_value(5)
        self.assertEqual(points[-1], QPoint(5, 0))
        panel.source_xy = QPoint(7, 9)
        self.assertEqual(panel.source_xy, QPoint(7, 9))

    def test_fill_threshold_is_an_integer_field_bound_to_cache(self) -> None:
        """The Color threshold field uses the Cache range as whole numbers and stores a float."""
        panel = FillToolPanel()
        field = panel.threshold_field
        minimum, maximum, step = Cache().get_range(Cache.FILL_THRESHOLD)
        self.assertEqual((field.minimum(), field.maximum(), field.step()), (minimum, maximum, step))
        field.set_value(maximum)
        self.assertEqual(Cache().get(Cache.FILL_THRESHOLD), float(maximum))
        Cache().set(Cache.FILL_THRESHOLD, float(minimum))
        self.assertEqual(field.value(), minimum)

    def test_filter_parameters_follow_the_cached_json(self) -> None:
        """Changing a parameter field rewrites the cached parameters, and a cache change moves the field."""
        panel = self._filter_panel()
        assert panel._current_filter is not None
        filter_name = panel._current_filter.get_name()
        field = panel._parameter_widgets[0]
        field.set_value(3.0)
        self.assertEqual(json.loads(Cache().get(Cache.FILTER_TOOL_CACHED_PARAMETERS))[filter_name][0],
                         3.0)
        params = json.loads(Cache().get(Cache.FILTER_TOOL_CACHED_PARAMETERS))
        params[filter_name][0] = 2.0
        Cache().set(Cache.FILTER_TOOL_CACHED_PARAMETERS, json.dumps(params))
        self.assertEqual(field.value(), 2.0)
