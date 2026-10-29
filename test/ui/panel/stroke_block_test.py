"""Tests StrokeBlock's binding to Cache values, its pen pressure links and its arrangements."""
import itertools
import json
from typing import Optional

from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QCheckBox, QGridLayout, QLabel

from src.config.cache import Cache
from src.tools.filter_tool import FilterTool
from src.ui.panel.tool_control_panels.clone_stamp_preview import CloneStampStrokePreview
from src.ui.panel.tool_control_panels.clone_stamp_tool_panel import CloneStampToolPanel
from src.ui.panel.tool_control_panels.draw_tool_panel import DrawToolPanel
from src.ui.panel.tool_control_panels.eraser_tool_panel import EraserToolPanel
from src.ui.panel.tool_control_panels.fill_tool_panel import FillToolPanel
from src.ui.panel.tool_control_panels.filter_tool_panel import FilterToolPanel
from src.ui.panel.tool_control_panels.smudge_tool_panel import SmudgeToolPanel
from src.tools.draw_tool import DrawTool
from src.ui.layout.panel_fit import FitItem, Orientation
from src.ui.panel.tool_control_panels.stroke_block import (BELOW, BESIDE, BESIDE_FIELD_MIN_WIDTH,
                                                           FIELD_COLUMN_MAX_WIDTH, ONLY_INSIDE_SELECTION_LABEL,
                                                           StrokeToolPanel)
from src.ui.panel.tool_panel import ToolPanel
from src.ui.widget.panel_section import PanelSection
from test.base_test_case import IntraPaintTestCase
from test.tools.tool_test_case import ToolTestCase
from test.ui.panel.tool_panel_test import settle_layouts
from test.ui.panel_capture import tell_orientation


SIDE = Orientation.SIDE
STRIP = Orientation.STRIP


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

    def test_revealing_pressure_links_plans_once(self) -> None:
        """Pen use calls show_pressure_checkboxes on every tablet event, but only the first call replans.

        The reveal changes no measured size, and a forced replan on every event rearranges the panel in a stream,
        flickering it.
        """
        Cache().set(Cache.EXPECT_TABLET_INPUT, False)
        panel = DrawToolPanel()
        panel.set_fit_space(SIDE, QSize(340, 700))
        panel.show()
        settle_layouts(panel)
        planner = panel._planner  # pylint: disable=protected-access
        updates = []
        original_update = planner.update

        def _update(*args, **kwargs):
            updates.append(args)
            return original_update(*args, **kwargs)

        planner.update = _update  # type: ignore[method-assign]
        for _ in range(10):
            panel.show_pressure_checkboxes()
            settle_layouts(panel)
        self.assertEqual(len(updates), 1, 'only the first tablet event replans the panel')
        self.assertTrue(panel.stroke_block.fields()[0].pressure_link_available())

    def test_selection_checkbox_uses_the_shared_label(self) -> None:
        """The selection option reads the same in every tool."""
        texts = [box.text() for box in self.block.findChildren(QCheckBox)]
        self.assertIn(ONLY_INSIDE_SELECTION_LABEL, texts)

    def test_preview_takes_whichever_room_the_panel_has(self) -> None:
        """The preview goes beside the fields where the panel is wide enough, below them where it is tall enough, and
        hides where it is neither."""
        cases = {
            'side_tall_narrow': (SIDE, QSize(260, 900), BELOW),
            'side_wide': (SIDE, QSize(420, 900), BESIDE),
            'side_short': (SIDE, QSize(260, 200), None),
            'strip_wide': (STRIP, QSize(1400, 160), BESIDE),
        }
        for name, (orientation, size, preview) in cases.items():
            with self.subTest(size=name):
                self.panel.set_fit_space(orientation, size)
                arrangement = self.block.arrangement
                self.assertEqual(arrangement.orientation, orientation)
                self.assertEqual(arrangement.preview, preview)
                preview_widget = self.block._preview  # pylint: disable=protected-access
                assert preview_widget is not None
                self.assertEqual(preview_widget.isHidden(), preview is None)

    def test_eraser_panel_has_an_erase_preview(self) -> None:
        """The Eraser panel's preview takes the same arrangements as Draw's."""
        panel = EraserToolPanel()
        preview_widget = panel.stroke_block._preview  # pylint: disable=protected-access
        assert preview_widget is not None
        for size, preview in ((QSize(260, 900), BELOW), (QSize(420, 900), BESIDE), (QSize(260, 200), None)):
            with self.subTest(size=size):
                panel.set_fit_space(SIDE, size)
                self.assertEqual(panel.stroke_block.arrangement.preview, preview)
                self.assertEqual(preview_widget.isHidden(), preview is None)

    def test_smudge_panel_has_a_smudge_preview(self) -> None:
        """The Smudge panel's preview takes the same arrangements as Draw's."""
        panel = SmudgeToolPanel()
        preview_widget = panel.stroke_block._preview  # pylint: disable=protected-access
        assert preview_widget is not None
        for size, preview in ((QSize(260, 900), BELOW), (QSize(420, 900), BESIDE), (QSize(260, 200), None)):
            with self.subTest(size=size):
                panel.set_fit_space(SIDE, size)
                self.assertEqual(panel.stroke_block.arrangement.preview, preview)
                self.assertEqual(preview_widget.isHidden(), preview is None)

    def test_preview_beside_keeps_the_fields_usable(self) -> None:
        """Beside the preview, the fields are at least BESIDE_FIELD_MIN_WIDTH and at most FIELD_COLUMN_MAX_WIDTH
        wide."""
        self.panel.set_fit_space(SIDE, QSize(1000, 900))
        self.assertEqual(self.block.arrangement.preview, BESIDE)
        fields = self.block._fields_widget  # pylint: disable=protected-access
        section = self.block._stroke_section  # pylint: disable=protected-access
        self.assertEqual((fields.minimumWidth(), section.maximumWidth()), (BESIDE_FIELD_MIN_WIDTH,
                                                                           FIELD_COLUMN_MAX_WIDTH))

    def test_controls_stay_grouped_in_the_fields_column(self) -> None:
        """Side panels keep the color pair and checkboxes under the fields at the same width, and no control column
        grows past FIELD_COLUMN_MAX_WIDTH in a wide panel or strip."""
        self.panel.resize(1000, 900)
        self.panel.show()
        for orientation, size in ((SIDE, QSize(1000, 900)), (SIDE, QSize(430, 900)), (STRIP, QSize(1400, 160))):
            with self.subTest(orientation=orientation, size=size):
                self.panel.set_fit_space(orientation, size)
                settle_layouts(self.panel)
                columns = [self.block._fields_widget, self.block._paint_widget,  # pylint: disable=protected-access
                           self.block._checks_widget]  # pylint: disable=protected-access
                for widget in columns:
                    assert widget is not None
                    self.assertLessEqual(widget.width(), FIELD_COLUMN_MAX_WIDTH)
                if orientation == SIDE:
                    fields, paint = columns[:2]
                    assert paint is not None
                    self.assertEqual(paint.mapTo(self.block, paint.rect().topLeft()).x(),
                                     fields.mapTo(self.block, fields.rect().topLeft()).x())
                    self.assertEqual(paint.width(), fields.width())
                else:
                    paint = columns[1]
                    assert paint is not None
                    fields_right = columns[0].mapTo(self.block, columns[0].rect().topRight()).x()
                    paint_left = paint.mapTo(self.block, paint.rect().topLeft()).x()
                    self.assertLess(paint_left - fields_right, 2 * FIELD_COLUMN_MAX_WIDTH - columns[0].width())

    def test_sections_have_headers_except_in_short_strips(self) -> None:
        """Side panels and tall strips title the Stroke and options sections. A strip too short for the headers hides
        them and shows the controls whatever the remembered choice."""
        stroke = self.block._stroke_section  # pylint: disable=protected-access
        options = self.block._options_section  # pylint: disable=protected-access
        self.assertEqual((stroke.title, options.title), ('Stroke', 'Color and options'))
        for orientation, size, headers in ((SIDE, QSize(300, 900), True), (STRIP, QSize(1000, 320), True),
                                           (STRIP, QSize(1000, 90), False)):
            with self.subTest(orientation=orientation, size=size):
                self.panel.set_fit_space(orientation, size)
                self.assertEqual(self.block.arrangement.headers, headers)
                self.assertEqual(stroke.is_header_visible(), headers)
        stroke.set_expanded(False)
        self.assertFalse(stroke.is_collapsed())
        self.panel.set_fit_space(STRIP, QSize(1000, 320))
        self.assertTrue(stroke.is_collapsed())

    def test_collapsed_stroke_section_summarizes_its_fields(self) -> None:
        """The Stroke header shows the fields' values while collapsed."""
        Cache().set(Cache.DRAW_TOOL_BRUSH_SIZE, 48)
        summary = self.block._stroke_section.summary()  # pylint: disable=protected-access
        self.assertIn('Size 48 px', summary)
        self.assertIn('Opacity', summary)

    def test_eraser_options_section_has_no_color_title(self) -> None:
        """A tool with no color row titles the second section "Options"."""
        eraser = EraserToolPanel()
        self.assertEqual(eraser.stroke_block._options_section.title, 'Options')  # pylint: disable=protected-access

    def test_resize_during_a_plan_does_not_plan_again(self) -> None:
        """A resize that trial placements cause while a plan runs is ignored, so planning can't recurse."""
        self.panel.show()
        self.panel.resize(300, 400)
        planner = self.panel._planner  # pylint: disable=protected-access
        calls = []
        original = planner.update

        def _update(*args, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                self.panel.resize(self.panel.width() + 7, self.panel.height())
            return original(*args, **kwargs)

        planner.update = _update  # type: ignore[method-assign]
        self.panel.resize(320, 400)
        self.assertEqual(len(calls), 1)

    def test_rows_stack_when_they_do_not_fit_across(self) -> None:
        """A narrow side panel stacks the checkboxes into a column and a wider one keeps them in a row. A strip keeps
        them in a row, however narrow."""
        self.panel.set_fit_space(SIDE, QSize(170, 900))
        self.assertTrue(self.block.arrangement.checks_stacked)
        self.panel.set_fit_space(SIDE, QSize(500, 900))
        self.assertFalse(self.block.arrangement.checks_stacked)
        self.panel.set_fit_space(STRIP, QSize(170, 300))
        self.assertFalse(self.block.arrangement.checks_stacked)
        self.assertFalse(self.block.arrangement.paint_stacked)

    def test_orientation_reaches_subclass_sections(self) -> None:
        """Planning for a strip calls set_orientation, so subclasses arrange their own sections."""
        orientations = []
        original = self.panel.set_orientation
        self.panel.set_orientation = lambda o: (orientations.append(o), original(o))[1]  # type: ignore[method-assign]
        try:
            self.panel.set_fit_space(STRIP, QSize(1400, 160))
            self.panel.set_fit_space(STRIP, QSize(1300, 160))
        finally:
            # The override holds the panel through `original`:
            del self.panel.set_orientation
        self.assertEqual(len(orientations), 1, orientations)
        self.assertEqual(self.block.arrangement.orientation, STRIP)

    def test_tool_sections_join_the_arrangement(self) -> None:
        """A tool section goes below the block's sections in a side panel and in the next column in a strip, an
        optional one is planned with the block's items, and a hidden one's column takes no spare width."""
        section = PanelSection('Tool', QLabel('Tool controls'))
        forms: list[tuple[Orientation, Optional[int]]] = []

        def _apply(orientation: Orientation, form: Optional[int]) -> None:
            forms.append((orientation, form))
            section.setVisible(form is not None)

        self.panel.add_tool_section(section, FitItem(1), _apply)
        self.panel.set_fit_space(SIDE, QSize(400, 900))
        settle_layouts(self.panel)
        options = self.block._options_section  # pylint: disable=protected-access
        self.assertEqual(forms[-1], (SIDE, 0))
        self.assertGreaterEqual(section.y(), options.geometry().bottom())
        self.assertEqual(section.x(), options.x())
        self.panel.set_fit_space(STRIP, QSize(1400, 200))
        settle_layouts(self.panel)
        self.assertEqual(forms[-1], (STRIP, 0))
        self.assertGreater(section.x(), options.geometry().right())
        self.assertEqual(section.y(), options.y())
        base = self.panel.fit_base_size(STRIP)
        self.panel.set_fit_space(STRIP, QSize(base.width(), 200))
        self.assertEqual(forms[-1], (STRIP, None))
        grid = self.block.layout()
        assert isinstance(grid, QGridLayout)
        self.assertEqual(grid.columnStretch(grid.getItemPosition(grid.indexOf(section))[1]), 0)


class ToolPanelsOnStrokeBlockTest(ToolTestCase):
    """Tests the panels that share the stroke block with Draw, and the tool-specific sections after it."""

    def _filter_panel(self) -> FilterToolPanel:
        panel = FilterTool(self.image_stack, self.image_viewer).get_control_panel()
        assert isinstance(panel, FilterToolPanel)
        return panel

    def test_filter_panel_has_a_filter_preview(self) -> None:
        """The Filter panel's preview takes the same arrangements as Draw's."""
        panel = self._filter_panel()
        preview_widget = panel.stroke_block._preview  # pylint: disable=protected-access
        assert preview_widget is not None
        for size, preview in ((QSize(260, 900), BELOW), (QSize(420, 900), BESIDE), (QSize(260, 200), None)):
            with self.subTest(size=size):
                panel.set_fit_space(SIDE, size)
                self.assertEqual(panel.stroke_block.arrangement.preview, preview)
                self.assertEqual(preview_widget.isHidden(), preview is None)

    def test_clone_stamp_panel_has_a_clone_stamp_preview(self) -> None:
        """The Clone stamp panel's preview takes the same arrangements as Draw's in every source mode."""
        Cache().update_options(Cache.CLONE_STAMP_TOOL_SOURCE_MODE,
                               ['Fixed offset', 'Dynamic offset', 'Fixed position'])
        panel = CloneStampToolPanel()
        preview_widget = panel.stroke_block._preview  # pylint: disable=protected-access
        assert isinstance(preview_widget, CloneStampStrokePreview)
        for mode in ('Fixed offset', 'Dynamic offset', 'Fixed position'):
            Cache().set(Cache.CLONE_STAMP_TOOL_SOURCE_MODE, mode)
            for size, preview in ((QSize(260, 900), BELOW), (QSize(420, 900), BESIDE), (QSize(260, 200), None)):
                with self.subTest(mode=mode, size=size):
                    panel.set_fit_space(SIDE, size)
                    self.assertEqual(panel.stroke_block.arrangement.preview, preview)
                    self.assertEqual(preview_widget.isHidden(), preview is None)

    def _stroke_panels(self) -> dict[str, StrokeToolPanel]:
        """Returns shown panels, because Qt only hides a reparented widget that is visible."""
        panels = {'Draw': DrawToolPanel(), 'Filter': self._filter_panel(), 'Clone stamp': CloneStampToolPanel()}
        for panel in panels.values():
            panel.show()
        return panels

    def test_placements_measure_the_same_whatever_came_before(self) -> None:
        """Measuring a placement gives the same size after every other placement."""
        for name, panel in self._stroke_panels().items():
            for orientation, size in ((SIDE, QSize(420, 900)), (STRIP, QSize(1000, 150))):
                panel.set_fit_space(orientation, size)
                planner = panel._planner  # pylint: disable=protected-access
                items = planner._items  # pylint: disable=protected-access
                placements = list(itertools.product(*((None, *range(item.form_count)) if not item.required
                                                      else tuple(range(item.form_count)) for item in items)))
                for placement in placements:
                    reference = planner.measure_placement(placement)
                    for other in placements:
                        planner.measure_placement(other)
                        with self.subTest(panel=name, orientation=orientation, placement=placement, after=other):
                            self.assertEqual(planner.measure_placement(placement), reference)

    def test_preview_changes_form_at_most_once_while_a_panel_grows(self) -> None:
        """Growing a panel a few pixels at a time never flips the preview between beside and below."""
        for name, panel in self._stroke_panels().items():
            for orientation, height, widths in ((SIDE, 700, range(300, 560, 3)), (STRIP, 150, range(500, 1100, 3))):
                forms = []
                for width in widths:
                    panel.set_fit_space(orientation, QSize(width, height))
                    form = panel.stroke_block.arrangement.preview
                    if len(forms) == 0 or forms[-1] != form:
                        forms.append(form)
                with self.subTest(panel=name, orientation=orientation):
                    self.assertLessEqual(len(forms) - 1, 1, forms)

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

    def test_clone_stamp_source_xy_reaches_the_preview(self) -> None:
        """A new offset in the fields makes the preview's render stale."""
        Cache().set(Cache.CLONE_STAMP_TOOL_SOURCE_MODE, 'Fixed offset')
        panel = CloneStampToolPanel()
        preview = panel.stroke_block._preview  # pylint: disable=protected-access
        assert preview is not None
        preview.setFixedSize(QSize(200, 80))
        preview.render_now()
        self.assertTrue(preview.is_current)
        panel.source_xy = QPoint(-40, 12)
        self.assertFalse(preview.is_current)

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

    def test_tools_panel_gives_the_preview_spare_room(self) -> None:
        """In the Tools panel, a tall, narrow side dock shows the Draw preview below the fields, and a wide strip under
        170 px tall shows it beside them."""
        tool = DrawTool(self.image_stack, self.image_viewer)
        tool_panel = ToolPanel()
        tool_panel.add_tool_button(tool)
        tool_panel.setup_active_tool(tool)
        control_panel = tool.get_control_panel()
        assert isinstance(control_panel, DrawToolPanel)
        for orientation, size, preview in ((SIDE, QSize(260, 1000), BELOW), (STRIP, QSize(1400, 160), BESIDE)):
            with self.subTest(orientation=orientation):
                tell_orientation(tool_panel, orientation, size)
                self.assertEqual(control_panel.stroke_block.arrangement.preview, preview)
