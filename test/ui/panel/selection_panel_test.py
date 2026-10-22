"""Tests SelectionPanel's clear context pins button."""
import sys
from unittest.mock import MagicMock

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QSpinBox

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.layers.image_stack import ImageStack
from src.ui.layout.panel_fit import Orientation
from src.ui.panel.tool_control_panels.brush_selection_panel import BrushSelectionPanel
from src.ui.panel.tool_control_panels.fill_selection_panel import FillSelectionPanel
from src.ui.panel.tool_control_panels.free_selection_panel import FreeSelectionPanel
from src.ui.panel.tool_control_panels.selection_panel import SelectionPanel
from src.ui.panel.tool_control_panels.shape_selection_panel import ShapeSelectionPanel
from src.ui.widget.panel_section import PanelSection
from src.util.layout import layout_contents
from src.util.visual.selection_fill_area import FillArea
from src.util.visual.selection_mode import SelectionMode
from src.util.shared_constants import EDIT_MODE_INPAINT, EDIT_MODE_IMG2IMG
from test.base_test_case import IntraPaintTestCase, press_key

app = QApplication.instance() or QApplication(sys.argv)


class SelectionPanelTest(IntraPaintTestCase):
    """Tests when the clear context pins button shows and what it does."""

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        cache.restore_default_options(Cache.EDIT_MODE)
        cache.set(Cache.INPAINT_OPTIONS_AVAILABLE, True)
        cache.set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        self.image_stack = ImageStack(QSize(256, 256), QSize(128, 128), QSize(8, 8), QSize(1024, 1024))
        self.selection_layer = self.image_stack.selection_layer
        self.panel = SelectionPanel(self.selection_layer, MagicMock())
        self.button = self.panel._clear_pins_button  # pylint: disable=protected-access

    def test_shown_only_while_inpainting(self) -> None:
        """The button shows in inpainting mode, and hides in other modes or without inpainting support."""
        cache = Cache()
        self.assertFalse(self.button.isHidden())
        cache.set(Cache.EDIT_MODE, EDIT_MODE_IMG2IMG)
        self.assertTrue(self.button.isHidden())
        cache.set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        self.assertFalse(self.button.isHidden())
        cache.set(Cache.INPAINT_OPTIONS_AVAILABLE, False)
        self.assertTrue(self.button.isHidden())

    def test_enabled_only_with_pins(self) -> None:
        """The button is disabled until there's a pin to clear."""
        self.assertFalse(self.button.isEnabled())
        self.selection_layer.add_context_pin(QPoint(10, 10))
        self.assertTrue(self.button.isEnabled())

    def test_click_clears_pins(self) -> None:
        """Clicking the button removes every pin."""
        self.selection_layer.set_context_pins([QPoint(10, 10), QPoint(20, 20)])
        self.button.click()
        self.assertEqual(self.selection_layer.context_pins, [])
        self.assertFalse(self.button.isEnabled())

    def test_fit_plan_moves_hint_and_wraps_buttons(self) -> None:
        """A plan without room moves the hint to the overflow content and stacks the Selection buttons, and a plan
        with room restores both. The base size leaves the hint out, and the same widgets stay throughout."""
        panel = self.panel
        hint = panel._hint_label  # pylint: disable=protected-access
        buttons = panel._actions_layout  # pylint: disable=protected-access
        base = panel.fit_base_size(Orientation.SIDE)
        self.assertEqual(panel.overflow_content(), hint.parentWidget())
        roomy = QSize(600, 600)
        panel.set_fit_space(Orientation.SIDE, roomy)
        self.assertNotEqual(panel.overflow_content(), hint.parentWidget())
        self.assertEqual(buttons.direction(), buttons.Direction.LeftToRight)
        panel.set_fit_space(Orientation.SIDE, QSize(base.width(), roomy.height()))
        self.assertEqual(buttons.direction(), buttons.Direction.TopToBottom)
        self.assertLessEqual(panel.minimumSizeHint().width(), base.width())
        panel.set_fit_space(Orientation.SIDE, roomy)
        self.assertEqual(buttons.direction(), buttons.Direction.LeftToRight)

    def test_no_full_res_controls(self) -> None:
        """The panel holds no checkbox or label for the inpaint full resolution and padding settings."""
        cache = Cache()
        names = {cache.get_label(Cache.INPAINT_FULL_RES), cache.get_label(Cache.INPAINT_FULL_RES_PADDING)}
        texts = {widget.text() for widget in self.panel.findChildren(QCheckBox) + self.panel.findChildren(QLabel)}
        self.assertEqual(texts & names, set())
        self.assertEqual(self.panel.findChildren(QSpinBox), [])


class SelectionPanelsTest(IntraPaintTestCase):
    """Tests what the four selection tools' panels share and where they differ."""

    def setUp(self) -> None:
        super().setUp()
        Cache().restore_default_options(Cache.SELECTION_MODE)
        Cache().restore_default_options(Cache.SELECTION_FILL_AREA)
        self.image_stack = ImageStack(QSize(256, 256), QSize(128, 128), QSize(8, 8), QSize(1024, 1024))
        self.layer = self.image_stack.selection_layer
        self.tools = {name: MagicMock(is_active=False) for name in ('brush', 'fill', 'free', 'shape')}
        self.tools['shape'].get_activation_config_key.return_value = KeyConfig.SHAPE_SELECTION_TOOL_KEY
        self.panels = {
            'brush': BrushSelectionPanel(self.layer, self.tools['brush']),
            'fill': FillSelectionPanel(self.layer, self.tools['fill']),
            'free': FreeSelectionPanel(self.layer, self.tools['free']),
            'shape': ShapeSelectionPanel(self.layer, self.tools['shape'])
        }

    def _press(self, key: Qt.Key) -> None:
        press_key(self.panels['free'], key)

    def test_mode_section_comes_first(self) -> None:
        """Every panel starts with the Mode section, and ends with the Selection section."""
        for name, panel in self.panels.items():
            sections = [section.title for section in layout_contents(panel._layout)  # pylint: disable=protected-access
                        if isinstance(section, PanelSection)]
            self.assertTrue(sections[0].startswith('Mode'), name)
            self.assertEqual(sections[-1], 'Selection', name)

    def test_mode_title_names_active_mode(self) -> None:
        """The Mode section's title shows the stored mode."""
        Cache().set(Cache.SELECTION_MODE, SelectionMode.SUBTRACT.value)
        for panel in self.panels.values():
            self.assertEqual(panel.findChildren(PanelSection)[0].title, 'Mode: Subtract')

    def test_q_cycles_mode_in_every_tool(self) -> None:
        """The tool action key steps through Replace, Add, Subtract and Intersect for each panel's active tool, then
           wraps."""
        order = [SelectionMode.REPLACE, SelectionMode.ADD, SelectionMode.SUBTRACT, SelectionMode.INTERSECT]
        for name, tool in self.tools.items():
            Cache().set(Cache.SELECTION_MODE, SelectionMode.REPLACE.value)
            tool.is_active = True
            for expected in order[1:] + order[:1]:
                self._press(Qt.Key.Key_Q)
                self.assertEqual(Cache().get(Cache.SELECTION_MODE), expected.value, name)
            tool.is_active = False

    def test_sample_merged_has_no_default_key(self) -> None:
        """Toggling Sample merged is an unbound action by default."""
        self.assertEqual(KeyConfig().get(KeyConfig.TOGGLE_SAMPLE_MERGED_HOTKEY), '')

    def test_fill_area_persists_and_gates_fields(self) -> None:
        """The Fill area control stores its choice, and Holes disables the threshold and Sample merged."""
        panel = self.panels['fill']
        assert isinstance(panel, FillSelectionPanel)
        self.assertEqual(panel.area_control.value(), FillArea.CONNECTED.value)
        panel.area_control.set_value(FillArea.HOLES.value)
        self.assertEqual(Cache().get(Cache.SELECTION_FILL_AREA), FillArea.HOLES.value)
        self.assertFalse(panel.threshold_field.isEnabled())
        panel.area_control.set_value(FillArea.BY_COLOR.value)
        self.assertTrue(panel.threshold_field.isEnabled())
        Cache().set(Cache.SELECTION_FILL_AREA, FillArea.HOLES.value)
        self.assertEqual(panel.area_control.value(), FillArea.HOLES.value)

    def test_old_color_select_setting_migrates(self) -> None:
        """A saved `color_select_mode` of true becomes the By color fill area, unless a fill area is saved."""
        data = {'color_select_mode': True}
        Cache()._migrate_saved_values(data)  # pylint: disable=protected-access
        self.assertEqual(data['selection_fill_area'], FillArea.BY_COLOR.value)
        data = {'color_select_mode': True, 'selection_fill_area': 'Holes'}
        Cache()._migrate_saved_values(data)  # pylint: disable=protected-access
        self.assertEqual(data['selection_fill_area'], 'Holes')
        data = {'color_select_mode': False}
        Cache()._migrate_saved_values(data)  # pylint: disable=protected-access
        self.assertNotIn('selection_fill_area', data)
