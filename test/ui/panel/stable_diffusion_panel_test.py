"""Tests the Stable Diffusion generation panel: its sections, the action block, edit mode handling, bindings to config
values, prompt tools, More menu, Advanced section and where each control sits in both orientations."""
from PySide6.QtCore import QEvent, QPoint, QPointF, QSize, Qt
from PySide6.QtGui import QKeyEvent, QPalette, QWheelEvent
from PySide6.QtWidgets import QApplication, QBoxLayout, QPushButton, QScrollArea, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.ink_style import PRIMARY_BUTTON_PROPERTY, caution_color
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.panel_fit import Orientation
from src.ui.panel.generators.comfyui_advanced_controls import ComfyUIAdvancedControls
from src.ui.panel.generators.stable_diffusion_panel import (NOTE_IMG2IMG, NOTE_TXT2IMG, PADDING_OFF,
                                                            SECTION_TITLE_ADVANCED, SECTION_TITLE_MASK,
                                                            SECTION_TITLE_PROMPT, SECTION_TITLE_SAMPLING,
                                                            SECTION_TITLE_SIZE, FieldPair, StableDiffusionPanel)
from src.ui.panel.generators.webui_advanced_controls import VARIATION_OFF, WebUIAdvancedControls
from src.ui.widget.panel_section import PanelSection
from src.util.application_state import APP_STATE_EDITING, AppStateTracker
from src.util.shared_constants import EDIT_MODE_IMG2IMG, EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG
from test.base_test_case import IntraPaintTestCase
from test.ui.panel.tool_panel_test import settle_layouts
from test.ui.panel_capture import PanelHost, tell_orientation

SIDE = Orientation.SIDE
STRIP = Orientation.STRIP


def _host(panel: StableDiffusionPanel, orientation: Orientation, size: QSize) -> None:
    panel.resize(size)
    tell_orientation(panel, orientation, size)
    settle_layouts(panel)


def _rect_in(widget: QWidget, panel: QWidget):
    return widget.rect().translated(widget.mapTo(panel, QPoint(0, 0)))


class StableDiffusionPanelTest(IntraPaintTestCase):
    """Tests the WebUI form of the panel, and the ComfyUI form where it differs."""

    def setUp(self) -> None:
        super().setUp()
        # The base test case trims option lists to the default, and edit mode needs all three:
        Cache().restore_default_options(Cache.EDIT_MODE)
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_INPAINT)
        AppStateTracker().set_app_state(APP_STATE_EDITING)
        self.panel = StableDiffusionPanel(True)
        self.panel.set_advanced_content(WebUIAdvancedControls())

    def _visible(self, widget) -> bool:
        return not widget.isHidden()

    def _section(self, title: str) -> PanelSection:
        return next(section.widget for section in self.panel.sections if section.title == title)

    def test_sections_follow_how_often_they_are_used(self) -> None:
        """The sections run from Prompt to Advanced, the most used first."""
        self.assertEqual([section.title for section in self.panel.sections],
                         [SECTION_TITLE_PROMPT, SECTION_TITLE_MASK, SECTION_TITLE_SAMPLING, SECTION_TITLE_SIZE,
                          SECTION_TITLE_ADVANCED])

    def test_rarely_used_sections_start_collapsed(self) -> None:
        """Prompt, Mask and Sampling start open, and Size and batch and Advanced start collapsed."""
        expanded = {section.title: section.widget.is_expanded() for section in self.panel.sections}
        self.assertEqual(expanded, {SECTION_TITLE_PROMPT: True, SECTION_TITLE_MASK: True, SECTION_TITLE_SAMPLING: True,
                                    SECTION_TITLE_SIZE: False, SECTION_TITLE_ADVANCED: False})

    def test_edit_mode_control_follows_cache_both_ways(self) -> None:
        """Picking a mode in the header sets the edit mode, and a Cache change moves the selection."""
        cache = Cache()
        control = self.panel.edit_mode_control
        self.assertTrue(self.panel.header.isAncestorOf(control))
        control.setCurrentIndex(control.findData(EDIT_MODE_TXT2IMG))
        self.assertEqual(cache.get(Cache.EDIT_MODE), EDIT_MODE_TXT2IMG)
        cache.set(Cache.EDIT_MODE, EDIT_MODE_IMG2IMG)
        self.assertEqual(control.currentData(), EDIT_MODE_IMG2IMG)

    def test_action_block_and_mask_section_follow_the_edit_mode(self) -> None:
        """Denoising shows in Inpaint and Image to image, padding and the Mask section in Inpaint only, and a note
        above Generate names any other mode."""
        cache = Cache()
        denoising, batch_size, padding = self.panel.action_fields
        mask = self._section(SECTION_TITLE_MASK)
        expected = {
            EDIT_MODE_INPAINT: (True, True, None),
            EDIT_MODE_IMG2IMG: (True, False, NOTE_IMG2IMG),
            EDIT_MODE_TXT2IMG: (False, False, NOTE_TXT2IMG),
        }
        for mode, (denoise_shown, inpaint_only_shown, note) in expected.items():
            with self.subTest(mode=mode):
                cache.set(Cache.EDIT_MODE, mode)
                _host(self.panel, SIDE, QSize(340, 900))
                self.assertEqual(self._visible(denoising), denoise_shown)
                self.assertTrue(self._visible(batch_size))
                self.assertEqual(self._visible(padding), inpaint_only_shown)
                self.assertEqual(self._visible(mask), inpaint_only_shown)
                self.assertEqual(self._visible(self.panel.mode_note), note is not None)
                if note is not None:
                    self.assertEqual(self.panel.mode_note.text(), note)

    def test_edit_mode_selector_takes_the_caution_color_outside_inpaint(self) -> None:
        """The header's mode selector draws its text in the caution color in any mode but Inpaint."""
        color = caution_color()
        if color is None:
            self.skipTest('The test theme has no caution color')
        cache = Cache()
        control = self.panel.edit_mode_control
        for mode, cautioned in ((EDIT_MODE_TXT2IMG, True), (EDIT_MODE_IMG2IMG, True), (EDIT_MODE_INPAINT, False)):
            with self.subTest(mode=mode):
                cache.set(Cache.EDIT_MODE, mode)
                text = control.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText)
                self.assertEqual(text == color, cautioned)

    def test_numeric_fields_follow_config(self) -> None:
        """Slider fields write their config values, and follow changes to them."""
        cache = Cache()
        cache.set(Cache.INPAINT_FULL_RES, True)
        denoising, batch_size, padding = self.panel.action_fields
        fields = [(self.panel._steps_field, cache, Cache.SAMPLING_STEPS, 12),
                  (denoising, cache, Cache.DENOISING_STRENGTH, 0.4),
                  (batch_size, cache, Cache.BATCH_SIZE, 2),
                  (padding, cache, Cache.INPAINT_FULL_RES_PADDING, 48),
                  (self.panel._batch_count_field, cache, Cache.BATCH_COUNT, 3),
                  (self.panel._mask_blur_field, AppConfig(), AppConfig.MASK_BLUR, 9)]
        for field, config, key, value in fields:
            with self.subTest(key=key):
                field.set_value(value)
                self.assertEqual(config.get(key), value)
                config.set(key, value + field.step())
                self.assertAlmostEqual(field.value(), value + field.step())

    def test_padding_toggle_turns_full_resolution_on_and_off(self) -> None:
        """The toggle in the padding field sets full resolution. While it is off, the field reads off and ignores the
        wheel, so the wheel scrolls the panel."""
        cache = Cache()
        padding = self.panel.padding_field
        cache.set(Cache.INPAINT_FULL_RES, True)
        self.assertFalse(padding.is_off())
        padding.set_pressure_link_enabled(False)
        self.assertFalse(cache.get(Cache.INPAINT_FULL_RES))
        self.assertTrue(padding.is_off())
        self.assertEqual(padding.value_text(), PADDING_OFF)
        value = padding.value()
        wheel = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton,
                            Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(padding, wheel)
        self.assertFalse(wheel.isAccepted())
        self.assertEqual(padding.value(), value)
        cache.set(Cache.INPAINT_FULL_RES, True)
        self.assertFalse(padding.is_off())
        self.assertNotEqual(padding.value_text(), PADDING_OFF)

    def test_tiling_locks_full_resolution_off_and_keeps_the_setting(self) -> None:
        """While tiling is on, the padding field reads off and its toggle ignores clicks and Space. Full resolution
        stays set, so it comes back when tiling ends."""
        cache = Cache()
        padding = self.panel.padding_field
        cache.set(Cache.INPAINT_FULL_RES, True)
        cache.set(Cache.WEBUI_TILING_AVAILABLE, True)
        cache.set(Cache.WEBUI_TILING, True)
        self.assertTrue(padding.is_off())
        self.assertTrue(padding.toggle_locked())
        self.assertTrue(cache.get(Cache.INPAINT_FULL_RES))
        space = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, ' ')
        QApplication.sendEvent(padding, space)
        self.assertTrue(padding.is_off())
        self.assertTrue(cache.get(Cache.INPAINT_FULL_RES))
        cache.set(Cache.WEBUI_TILING, False)
        self.assertFalse(padding.is_off())
        self.assertFalse(padding.toggle_locked())

    def test_tiling_button_shows_while_tiling_and_turns_it_off(self) -> None:
        """The action block's tiling button shows in the caution color while tiling is on, and clicking it turns
        tiling off."""
        cache = Cache()
        button = self.panel.tiling_button
        self.assertTrue(self.panel.action_block.isAncestorOf(button))
        self.assertFalse(self._visible(button))
        cache.set(Cache.WEBUI_TILING, True)
        self.assertFalse(self._visible(button), 'Tiling only applies while the WebUI is connected')
        cache.set(Cache.WEBUI_TILING_AVAILABLE, True)
        self.assertTrue(self._visible(button))
        color = caution_color()
        if color is not None:
            self.assertEqual(button.palette().color(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText), color)
        button.click()
        self.assertFalse(cache.get(Cache.WEBUI_TILING))
        self.assertFalse(self._visible(button))

    def test_comfyui_panel_never_shows_the_tiling_button(self) -> None:
        """ComfyUI has no tiling option, so its panel hides the button whatever the WebUI's setting is."""
        cache = Cache()
        cache.set(Cache.WEBUI_TILING_AVAILABLE, True)
        cache.set(Cache.WEBUI_TILING, True)
        panel = StableDiffusionPanel(False)
        self.assertFalse(self._visible(panel.tiling_button))

    def test_moved_controls_are_reachable_in_their_new_places(self) -> None:
        """Model is in the Prompt section, Interrogate in the More menu, and full resolution in the padding field."""
        self.assertTrue(self._section(SECTION_TITLE_PROMPT).isAncestorOf(self.panel.model_combobox))
        interrogate = self.panel.more_menu_buttons[0]
        self.assertTrue(self.panel.more_content().isAncestorOf(interrogate))
        self.assertTrue(self._visible(interrogate))
        self.assertTrue(self.panel.padding_field.pressure_link_available())
        self.assertTrue(self.panel.action_block.isAncestorOf(self.panel.padding_field))

    def test_negative_prompt_folds_to_a_line_showing_its_text(self) -> None:
        """The negative prompt starts folded, with its text as the fold's summary on one line."""
        fold = self.panel._negative_fold
        self.assertFalse(fold.is_expanded())
        self.panel._negative_textbox.setPlainText('blurry,\n  lowres')
        self.assertEqual(fold.summary(), 'blurry, lowres')
        fold.header_button.click()
        self.assertTrue(fold.is_expanded())
        self.assertTrue(self._visible(self.panel._negative_textbox))

    def test_sampling_summary_shows_a_fixed_seed(self) -> None:
        """The collapsed Sampling section names the seed while one is fixed, and the sampler otherwise."""
        cache = Cache()
        sampling = self._section(SECTION_TITLE_SAMPLING)
        cache.set(Cache.SEED, 1234)
        self.assertTrue(sampling.summary().startswith('seed 1234'))
        cache.set(Cache.SEED, -1)
        self.assertTrue(sampling.summary().startswith(cache.get(Cache.SAMPLING_METHOD)))

    def test_prompt_tools_hide_when_they_have_nothing_to_show(self) -> None:
        """LoRA and Styles are hidden until their lists have entries."""
        cache = Cache()
        lora, styles = self.panel.prompt_tool_buttons
        cache.set(Cache.LORA_MODELS, [])
        cache.set(Cache.STYLES, [])
        self.assertFalse(self._visible(lora))
        self.assertFalse(self._visible(styles))
        cache.set(Cache.LORA_MODELS, [{'name': 'a', 'alias': 'a', 'path': 'a'}])
        cache.set(Cache.STYLES, ['{"name": "a", "prompt": "", "negative_prompt": ""}'])
        self.assertTrue(self._visible(lora))
        self.assertTrue(self._visible(styles))

    def test_comfyui_panel_has_only_the_lora_tool(self) -> None:
        """ComfyUI has no styles or interrogate, and offers Clear GPU memory in the More menu."""
        panel = StableDiffusionPanel(False)
        self.assertEqual(len(panel.prompt_tool_buttons), 1)
        interrogate, _, _, _, clear = panel.more_menu_buttons
        self.assertTrue(interrogate.isHidden())
        self.assertFalse(clear.isHidden())
        self.assertTrue(self.panel.more_menu_buttons[4].isHidden())

    def test_commands_emit_their_signals(self) -> None:
        """Each prompt tool, More menu entry and Generate emits the signal the generator connects to."""
        panel = self.panel
        received: list[str] = []
        signals = {'lora': panel.lora_requested, 'styles': panel.styles_requested,
                   'interrogate': panel.interrogate_signal, 'setup': panel.setup_requested,
                   'settings': panel.settings_requested, 'lcm': panel.lcm_mode_requested,
                   'clear': panel.clear_memory_requested, 'generate': panel.generate_signal}
        for name, signal in signals.items():
            signal.connect(lambda name=name: received.append(name))
        lora, styles = panel.prompt_tool_buttons
        interrogate, setup, settings, lcm, clear = panel.more_menu_buttons
        for button in (lora, styles, interrogate, setup, settings, lcm, clear, panel.generate_button):
            button.click()
        self.assertEqual(received, ['lora', 'styles', 'interrogate', 'setup', 'settings', 'lcm', 'clear', 'generate'])

    def test_lcm_mode_shows_in_more_only_when_available(self) -> None:
        """The LCM entry follows the generator's availability check each time More opens."""
        available = [False]
        self.panel.lcm_available_check = lambda: available[0]
        self.panel.header.more_requested.emit()
        self.assertTrue(self.panel.more_menu_buttons[3].isHidden())
        available[0] = True
        self.panel.header.more_requested.emit()
        self.assertFalse(self.panel.more_menu_buttons[3].isHidden())

    def test_banner_shows_its_message_and_asks_for_setup(self) -> None:
        """The banner is hidden while connected, and its button asks for the generator setup window."""
        requests: list[bool] = []
        self.panel.setup_requested.connect(lambda: requests.append(True))
        self.assertTrue(self.panel.banner.isHidden())
        self.panel.set_disconnected('Not connected')
        self.assertFalse(self.panel.banner.isHidden())
        self.assertEqual(self.panel.banner.message(), 'Not connected')
        self.panel.banner.fix_button.click()
        self.assertEqual(requests, [True])
        self.panel.set_disconnected(None)
        self.assertTrue(self.panel.banner.isHidden())

    def test_advanced_section_summarizes_unusual_settings(self) -> None:
        """Advanced's summary names anything unusual that is on."""
        cache = Cache()
        section = self._section(SECTION_TITLE_ADVANCED)
        cache.set(Cache.WEBUI_TILING, False)
        cache.set(Cache.WEBUI_SUBSEED_STRENGTH, 0.0)
        cache.set(Cache.WEBUI_RESTORE_FACES, False)
        cache.set(Cache.WEBUI_SEED_RESIZE_ENABLED, False)
        defaults = section.summary()
        self.assertNotIn('tiling', defaults)
        cache.set(Cache.WEBUI_SUBSEED_STRENGTH, 0.25)
        cache.set(Cache.WEBUI_TILING, True)
        self.assertEqual(section.summary(), 'variation 0.25, tiling')

    def test_advanced_section_holds_the_rarely_changed_settings(self) -> None:
        """Masked content, the resolution rule and CLIP skip sit in Advanced, and masked content shows in Inpaint
        only."""
        advanced = self._section(SECTION_TITLE_ADVANCED)
        for widget in (self.panel._masked_content_combobox, self.panel._resolution_rule_combobox,
                       self.panel._clip_skip_field):
            self.assertTrue(advanced.isAncestorOf(widget))
        rows = self.panel._masked_content_rows
        assert rows is not None
        self.assertTrue(self._visible(rows))
        Cache().set(Cache.EDIT_MODE, EDIT_MODE_TXT2IMG)
        self.assertFalse(self._visible(rows))

    def test_variation_strength_reads_off_at_zero(self) -> None:
        """Zero variation strength shows "Off"."""
        controls = self.panel.advanced_controls
        assert isinstance(controls, WebUIAdvancedControls)
        controls._strength_field.set_value(0)
        self.assertEqual(controls._strength_field.value_text(), VARIATION_OFF)

    def test_seed_resize_input_is_dimmed_until_checked(self) -> None:
        """The seed resize size input is enabled only while its check box is on."""
        controls = self.panel.advanced_controls
        assert isinstance(controls, WebUIAdvancedControls)
        Cache().set(Cache.WEBUI_SEED_RESIZE_ENABLED, False)
        self.assertFalse(controls._seed_resize_input.isEnabledTo(self.panel))
        Cache().set(Cache.WEBUI_SEED_RESIZE_ENABLED, True)
        self.assertTrue(controls._seed_resize_input.isEnabledTo(self.panel))

    def test_comfyui_tile_size_is_dimmed_until_tiled_vae_is_on(self) -> None:
        """Tile size is enabled only while tiled VAE encoding is on, and the summary names it."""
        panel = StableDiffusionPanel(False)
        panel.set_advanced_content(ComfyUIAdvancedControls())
        controls = panel.advanced_controls
        assert isinstance(controls, ComfyUIAdvancedControls)
        cache = Cache()
        cache.set(Cache.COMFYUI_TILED_VAE, False)
        self.assertFalse(controls._tile_size_field.isEnabledTo(panel))
        cache.set(Cache.COMFYUI_TILED_VAE, True)
        cache.set(Cache.COMFYUI_TILED_VAE_TILE_SIZE, 512)
        self.assertTrue(controls._tile_size_field.isEnabledTo(panel))
        self.assertIn('tiled VAE 512', controls.summary())

    def test_advanced_content_can_be_set_once(self) -> None:
        """A second call to `set_advanced_content` is an error."""
        with self.assertRaises(RuntimeError):
            self.panel.set_advanced_content(WebUIAdvancedControls())

    def test_generate_stays_in_the_bottom_right_corner(self) -> None:
        """Generate ends at the panel's bottom right, in both orientations, even when the sections need scrolling."""
        host = PanelHost(self.panel)
        try:
            for orientation, size in ((SIDE, QSize(300, 360)), (SIDE, QSize(340, 1400)), (STRIP, QSize(1000, 240)),
                                      (STRIP, QSize(1400, 400))):
                with self.subTest(orientation=orientation, size=size):
                    host.capture(size, orientation)
                    self._assert_generate_in_corner(orientation)
        finally:
            host.release()

    def _assert_generate_in_corner(self, orientation: Orientation) -> None:
        self.assertEqual(self.panel.orientation, orientation)
        button = self.panel.generate_button
        self.assertTrue(button.isVisible())
        rect = _rect_in(button, self.panel)
        self.assertLessEqual(rect.bottom(), self.panel.height())
        self.assertGreater(rect.bottom(), self.panel.height() - 2 * button.height())
        self.assertLessEqual(rect.right(), self.panel.width())
        self.assertGreater(rect.right(), self.panel.width() - 2 * self.panel.inset - button.height())

    def test_strip_pins_prompt_left_and_the_action_block_right(self) -> None:
        """A strip keeps Prompt in a column at the left and the action block in one at the right, neither of which
        scrolls sideways, and a side panel puts the action block back in the footer."""
        self.panel.show()
        prompt = self._section(SECTION_TITLE_PROMPT)
        mask = self._section(SECTION_TITLE_MASK)
        _host(self.panel, STRIP, QSize(1000, 300))
        self.assertEqual(self.panel.orientation, STRIP)
        scroll_area = next(area for area in self.panel.findChildren(QScrollArea) if area.isAncestorOf(mask))
        for widget in (prompt, self.panel.action_block):
            self.assertFalse(scroll_area.isAncestorOf(widget))
            self.assertTrue(widget.isVisible())
        self.assertLess(_rect_in(prompt, self.panel).right(), _rect_in(mask, self.panel).left())
        self.assertGreater(_rect_in(self.panel.action_block, self.panel).left(), _rect_in(mask, self.panel).right())
        _host(self.panel, SIDE, QSize(340, 1400))
        self.assertTrue(scroll_area.isAncestorOf(prompt))
        self.assertFalse(scroll_area.isAncestorOf(self.panel.action_block))
        self.assertGreater(_rect_in(self.panel.action_block, self.panel).top(), _rect_in(mask, self.panel).bottom())
        tops = [_rect_in(section.widget, self.panel).top() for section in self.panel.sections]
        self.assertEqual(tops, sorted(tops))

    def test_strip_packs_short_sections_into_one_column(self) -> None:
        """In a strip tall enough for both, Mask and Sampling share a column, and the collapsed sections stack in the
        columns' spare height."""
        self.panel.show()
        _host(self.panel, STRIP, QSize(1200, 400))
        left = {section.title: _rect_in(section.widget, self.panel).left() for section in self.panel.sections[1:]}
        self.assertEqual(left[SECTION_TITLE_MASK], left[SECTION_TITLE_SAMPLING])
        self.assertLessEqual(len(set(left.values())), 2)

    def test_strip_sections_stay_visible_as_the_columns_repack(self) -> None:
        """Every section stays visible when a resize moves sections between packed columns."""
        host = PanelHost(self.panel)
        try:
            for size in (QSize(1200, 160), QSize(1000, 260), QSize(1200, 400), QSize(1000, 260)):
                with self.subTest(size=size):
                    host.capture(size, STRIP)
                    hidden = [section.title for section in self.panel.sections
                              if not section.widget.isVisibleTo(self.panel)]
                    self.assertEqual(hidden, [])
        finally:
            host.release()

    def test_strip_columns_stay_top_aligned(self) -> None:
        """Spare height in a tall strip stays under each column's controls instead of spreading them apart."""
        self.panel.show()
        _host(self.panel, STRIP, QSize(1400, 800))
        mask = self._section(SECTION_TITLE_MASK)
        self.assertLess(mask.height(), self.panel.height() // 2)
        self.assertLess(_rect_in(mask, self.panel).top(), self.panel.height() // 4)

    def test_minimum_size_does_not_depend_on_the_last_layout(self) -> None:
        """A strip size gives the same minimum size hint whatever size the panel showed before."""
        self.panel.show()
        size = QSize(1200, 300)
        _host(self.panel, STRIP, size)
        first = self.panel.minimumSizeHint()
        for other in (QSize(1200, 800), QSize(160, 100)):
            _host(self.panel, STRIP, other)
        _host(self.panel, STRIP, size)
        self.assertEqual(self.panel.minimumSizeHint(), first)

    def test_field_pair_forms_follow_the_column_width(self) -> None:
        """A pair's forms are side by side and stacked, except that a strip column too narrow for both fields' text
        keeps it stacked."""
        pair = FieldPair(SliderField('A long first label', 1, 0, 10), SliderField('A long second label', 1, 0, 10))
        stacked, side_by_side = QBoxLayout.Direction.TopToBottom, QBoxLayout.Direction.LeftToRight
        for column_width, expected in ((None, (side_by_side, stacked)), (1000, (side_by_side, stacked)),
                                       (100, (stacked, stacked))):
            with self.subTest(column_width=column_width):
                for form, direction in zip(pair.forms(lambda width=column_width: width), expected):
                    form()
                    self.assertEqual(pair.layout().direction(), direction)

    def test_generate_is_the_only_primary_button(self) -> None:
        """Every other button in the panel is flat or standard."""
        primary = [button for button in self.panel.findChildren(QPushButton)
                   if button.property(PRIMARY_BUTTON_PROPERTY) is True]
        self.assertEqual(primary, [self.panel.generate_button])
