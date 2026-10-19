"""Tests the Stable Diffusion generation panel: its sections, edit mode handling, bindings to config values, prompt
tools, More menu, Advanced section and pinned Generate button."""
import json

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QPushButton

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.controlnet_adapter import SavedControlNetUnit
from src.ui.ink_style import PRIMARY_BUTTON_PROPERTY
from src.ui.layout.panel_fit import Orientation
from src.ui.panel.generators.comfyui_advanced_controls import ComfyUIAdvancedControls
from src.ui.panel.generators.stable_diffusion_panel import (CONTROLNET_ALL_OFF, SECTION_TITLE_ADVANCED,
                                                            SECTION_TITLE_CONTROLNET, SECTION_TITLE_INPAINT,
                                                            SECTION_TITLE_MODE, SECTION_TITLE_OUTPUT,
                                                            SECTION_TITLE_PROMPT, SECTION_TITLE_SAMPLING,
                                                            StableDiffusionPanel, controlnet_summary)
from src.ui.panel.generators.webui_advanced_controls import VARIATION_OFF, WebUIAdvancedControls
from src.util.shared_constants import EDIT_MODE_IMG2IMG, EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG
from test.base_test_case import IntraPaintTestCase
from test.ui.panel.tool_panel_test import settle_layouts

SIDE = Orientation.SIDE
STRIP = Orientation.STRIP


def _host(panel: StableDiffusionPanel, orientation: Orientation, size: QSize) -> None:
    panel.resize(size)
    panel.set_host_facts(orientation, size)
    settle_layouts(panel)


class StableDiffusionPanelTest(IntraPaintTestCase):
    """Tests the WebUI form of the panel, and the ComfyUI form where it differs."""

    def setUp(self) -> None:
        super().setUp()
        self.panel = StableDiffusionPanel(True)
        self.panel.set_advanced_content(WebUIAdvancedControls())

    def _visible(self, widget) -> bool:
        return not widget.isHidden()

    def test_sections_follow_the_loop_order(self) -> None:
        """The sections run from edit mode to ControlNet, in the order the loop uses them."""
        self.assertEqual([section.title for section in self.panel.sections],
                         [SECTION_TITLE_MODE, SECTION_TITLE_PROMPT, SECTION_TITLE_INPAINT, SECTION_TITLE_OUTPUT,
                          SECTION_TITLE_SAMPLING, SECTION_TITLE_ADVANCED, SECTION_TITLE_CONTROLNET])

    def test_edit_mode_control_follows_cache_both_ways(self) -> None:
        """Picking a segment sets the edit mode, and a Cache change moves the selection."""
        cache = Cache()
        self.panel.edit_mode_control.set_value(EDIT_MODE_TXT2IMG)
        self.assertEqual(cache.get(Cache.EDIT_MODE), EDIT_MODE_TXT2IMG)
        cache.set(Cache.EDIT_MODE, EDIT_MODE_IMG2IMG)
        self.assertEqual(self.panel.edit_mode_control.value(), EDIT_MODE_IMG2IMG)

    def test_inpaint_section_keeps_its_place_in_every_mode(self) -> None:
        """Only the controls inside the Inpaint section change with the edit mode. The section stays shown, and the
        sections after it stay in the same order."""
        cache = Cache()
        section = self.panel.sections[2]
        expected = {
            EDIT_MODE_INPAINT: (False, True, True),
            EDIT_MODE_IMG2IMG: (False, True, False),
            EDIT_MODE_TXT2IMG: (True, False, False),
        }
        for mode, (note_shown, denoise_shown, mask_shown) in expected.items():
            with self.subTest(mode=mode):
                cache.set(Cache.EDIT_MODE, mode)
                self.assertTrue(self._visible(section.widget))
                self.assertEqual(self._visible(self.panel._inpaint_note), note_shown)
                self.assertEqual(self._visible(self.panel._denoising_field), denoise_shown)
                self.assertEqual(self._visible(self.panel._mask_blur_field), mask_shown)
                self.assertEqual(self._visible(self.panel._full_res_pair), mask_shown)

    def test_numeric_fields_follow_config(self) -> None:
        """Slider fields write their config values, and follow changes to them."""
        cache = Cache()
        fields = [(self.panel._steps_field, cache, Cache.SAMPLING_STEPS, 12),
                  (self.panel._denoising_field, cache, Cache.DENOISING_STRENGTH, 0.4),
                  (self.panel._padding_field, cache, Cache.INPAINT_FULL_RES_PADDING, 48),
                  (self.panel._batch_count_field, cache, Cache.BATCH_COUNT, 3),
                  (self.panel._mask_blur_field, AppConfig(), AppConfig.MASK_BLUR, 9)]
        for field, config, key, value in fields:
            with self.subTest(key=key):
                field.set_value(value)
                self.assertEqual(config.get(key), value)
                config.set(key, value + field.step)
                self.assertEqual(field.value(), value + field.step)

    def test_padding_dims_until_full_resolution_is_on(self) -> None:
        """Padding is dimmed while full resolution is off, so the row doesn't change size."""
        cache = Cache()
        cache.set(Cache.INPAINT_FULL_RES, False)
        self.assertFalse(self.panel._padding_field.isEnabled())
        cache.set(Cache.INPAINT_FULL_RES, True)
        self.assertTrue(self.panel._padding_field.isEnabled())
        self.assertTrue(self.panel._full_res_checkbox.isChecked())

    def test_prompt_tools_hide_when_they_have_nothing_to_show(self) -> None:
        """LoRA and Styles are hidden until their lists have entries. Interrogate is always there in the WebUI."""
        cache = Cache()
        lora, styles, interrogate = self.panel.prompt_tool_buttons
        cache.set(Cache.LORA_MODELS, [])
        cache.set(Cache.STYLES, [])
        self.assertFalse(self._visible(lora))
        self.assertFalse(self._visible(styles))
        self.assertTrue(self._visible(interrogate))
        cache.set(Cache.LORA_MODELS, [{'name': 'a', 'alias': 'a', 'path': 'a'}])
        cache.set(Cache.STYLES, ['{"name": "a", "prompt": "", "negative_prompt": ""}'])
        self.assertTrue(self._visible(lora))
        self.assertTrue(self._visible(styles))

    def test_comfyui_panel_has_only_the_lora_tool(self) -> None:
        """ComfyUI has no styles or interrogate, and offers Clear GPU memory in the More menu."""
        panel = StableDiffusionPanel(False)
        self.assertEqual(len(panel.prompt_tool_buttons), 1)
        self.assertFalse(panel.more_menu_buttons[3].isHidden())
        self.assertTrue(self.panel.more_menu_buttons[3].isHidden())

    def test_commands_emit_their_signals(self) -> None:
        """Each prompt tool, More menu entry and Generate emits the signal the generator connects to."""
        panel = self.panel
        received: list[str] = []
        signals = {'lora': panel.lora_requested, 'styles': panel.styles_requested,
                   'interrogate': panel.interrogate_signal, 'setup': panel.setup_requested,
                   'settings': panel.settings_requested, 'lcm': panel.lcm_mode_requested,
                   'clear': panel.clear_memory_requested, 'generate': panel.generate_signal,
                   'controlnet': panel.controlnet_requested}
        for name, signal in signals.items():
            signal.connect(lambda name=name: received.append(name))
        lora, styles, interrogate = panel.prompt_tool_buttons
        setup, settings, lcm, clear = panel.more_menu_buttons
        for button in (lora, styles, interrogate, setup, settings, lcm, clear, panel.generate_button,
                       panel._controlnet_button):
            button.click()
        self.assertEqual(received, ['lora', 'styles', 'interrogate', 'setup', 'settings', 'lcm', 'clear', 'generate',
                                    'controlnet'])

    def test_lcm_mode_shows_in_more_only_when_available(self) -> None:
        """The LCM entry follows the generator's availability check each time More opens."""
        available = [False]
        self.panel.lcm_available_check = lambda: available[0]
        self.panel.header.more_requested.emit()
        self.assertTrue(self.panel.more_menu_buttons[2].isHidden())
        available[0] = True
        self.panel.header.more_requested.emit()
        self.assertFalse(self.panel.more_menu_buttons[2].isHidden())

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

    def test_advanced_section_starts_collapsed_with_a_summary(self) -> None:
        """Advanced is collapsed, and its summary names anything unusual that is on."""
        cache = Cache()
        section = self.panel.sections[5].widget
        self.assertFalse(section.is_expanded())
        cache.set(Cache.WEBUI_TILING, False)
        cache.set(Cache.WEBUI_SUBSEED_STRENGTH, 0.0)
        cache.set(Cache.WEBUI_RESTORE_FACES, False)
        cache.set(Cache.WEBUI_SEED_RESIZE_ENABLED, False)
        defaults = section.summary()
        self.assertNotIn('tiling', defaults)
        cache.set(Cache.WEBUI_SUBSEED_STRENGTH, 0.25)
        cache.set(Cache.WEBUI_TILING, True)
        self.assertEqual(section.summary(), 'variation 0.25, tiling')

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
        self.assertFalse(controls._seed_resize_input.isEnabled())
        Cache().set(Cache.WEBUI_SEED_RESIZE_ENABLED, True)
        self.assertTrue(controls._seed_resize_input.isEnabled())

    def test_comfyui_tile_size_is_dimmed_until_tiled_vae_is_on(self) -> None:
        """Tile size is enabled only while tiled VAE encoding is on, and the summary names it."""
        panel = StableDiffusionPanel(False)
        panel.set_advanced_content(ComfyUIAdvancedControls())
        controls = panel.advanced_controls
        assert isinstance(controls, ComfyUIAdvancedControls)
        cache = Cache()
        cache.set(Cache.COMFYUI_TILED_VAE, False)
        self.assertFalse(controls._tile_size_field.isEnabled())
        cache.set(Cache.COMFYUI_TILED_VAE, True)
        cache.set(Cache.COMFYUI_TILED_VAE_TILE_SIZE, 512)
        self.assertTrue(controls._tile_size_field.isEnabled())
        self.assertIn('tiled VAE 512', controls.summary())

    def test_advanced_content_can_be_set_once(self) -> None:
        """A second call to `set_advanced_content` is an error."""
        with self.assertRaises(RuntimeError):
            self.panel.set_advanced_content(WebUIAdvancedControls())

    def test_controlnet_section_shows_only_with_units(self) -> None:
        """The ControlNet summary appears once a backend gives the panel its unit keys."""
        _host(self.panel, SIDE, QSize(340, 900))
        self.assertTrue(self.panel.sections[6].widget.isHidden())
        self.panel.set_controlnet_cache_keys([Cache.CONTROLNET_ARGS_0_WEBUI])
        _host(self.panel, SIDE, QSize(340, 900))
        self.assertFalse(self.panel.sections[6].widget.isHidden())

    def test_controlnet_summary(self) -> None:
        """The summary names the enabled unit, counts several, and reports none."""
        default_units = [Cache().get(key) for key in (Cache.CONTROLNET_ARGS_0_WEBUI, Cache.CONTROLNET_ARGS_1_WEBUI,
                                                      Cache.CONTROLNET_ARGS_2_WEBUI)]
        enabled_unit = SavedControlNetUnit.from_json(default_units[0])
        enabled_unit.enabled = True
        enabled = enabled_unit.to_json()
        self.assertEqual(controlnet_summary(default_units), CONTROLNET_ALL_OFF)
        self.assertTrue(controlnet_summary([default_units[0], enabled]).startswith('unit 2 on'))
        self.assertTrue(controlnet_summary([enabled, enabled]).startswith('2 units'))
        self.assertEqual(controlnet_summary(['not json', json.dumps({})]), CONTROLNET_ALL_OFF)

    def test_generate_stays_below_the_content_while_it_scrolls(self) -> None:
        """Generate sits at the bottom of the panel, in both orientations, even when the sections need scrolling."""
        for orientation, size in ((SIDE, QSize(340, 300)), (SIDE, QSize(340, 1400)), (STRIP, QSize(1000, 240))):
            with self.subTest(orientation=orientation, size=size):
                self.panel.show()
                _host(self.panel, orientation, size)
                button = self.panel.generate_button
                self.assertTrue(button.isVisible())
                bottom = button.mapTo(self.panel, button.rect().bottomLeft()).y()
                self.assertLessEqual(bottom, self.panel.height())
                self.assertGreater(bottom, self.panel.height() - 2 * button.height())

    def test_generate_is_the_only_primary_button(self) -> None:
        """Every other button in the panel is flat or standard."""
        primary = [button for button in self.panel.findChildren(QPushButton)
                   if button.property(PRIMARY_BUTTON_PROPERTY) is True]
        self.assertEqual(primary, [self.panel.generate_button])
