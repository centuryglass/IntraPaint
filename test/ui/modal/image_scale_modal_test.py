"""Tests ImageScaleModal's size fields, scaling modes and Stable Diffusion upscaling controls."""
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QComboBox
from sd_backend_client import CONTROLNET_MODEL_NONE, ControlNetModel, ControlNetPreprocessor, ControlNetUnit, \
    PreprocessorParams

from src.controller.image_generation.sd_adapters.controlnet_adapter import SavedControlNetUnit
from src.config.cache import Cache
from src.ui.input_fields import geometry_block
from src.ui.input_fields.number_field import NumberField
from src.ui.modal.image_scale_modal import ImageScaleModal
from src.ui.modal.image_scale_modal import MODE_AI, MODE_BASIC, MODE_GENERATOR, UNIT_PCT
from test.base_test_case import IntraPaintTestCase

TILE_MODEL = 'control_v11f1e_sd15_tile'
TILE_PREPROCESSOR = 'tile_resample'


class ImageScaleModalTest(IntraPaintTestCase):
    """Tests ImageScaleModal."""

    def setUp(self) -> None:
        super().setUp()
        cache = Cache()
        preprocessor = ControlNetPreprocessor(name=TILE_PREPROCESSOR)
        tile_unit = ControlNetUnit(model=ControlNetModel(TILE_MODEL),
                                   preprocessor=PreprocessorParams(typedef=preprocessor, parameter_values={}),
                                   control_strength=0.75, control_start=0.1, control_end=0.9)
        cache.set(Cache.SD_UPSCALING_AVAILABLE, True)
        cache.set(Cache.USE_STABLE_DIFFUSION_UPSCALING, True)
        cache.set(Cache.ULTIMATE_UPSCALE_SCRIPT_AVAILABLE, False)
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_MODELS, [TILE_MODEL, CONTROLNET_MODEL_NONE])
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_PREPROCESSORS, [preprocessor.model_dump_json()])
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS, SavedControlNetUnit(True, '', tile_unit).to_json())

    @staticmethod
    def _saved_tile_unit() -> ControlNetUnit:
        return SavedControlNetUnit.from_json(Cache().get(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS)).unit

    def test_tile_unit_inputs_show_saved_values(self) -> None:
        """The tile model's strength, start and end inputs open with the saved values."""
        modal = ImageScaleModal(512, 512)
        values = [widget.value() for widget in modal._tile_unit_param_controls.values()]
        self.assertEqual(values, [0.75, 0.1, 0.9])

    def test_scaling_saves_changed_tile_unit_values(self) -> None:
        """Values changed in the tile inputs are saved when the modal closes, without waiting for the save timer."""
        modal = ImageScaleModal(512, 512)
        strength_input, start_input, end_input = modal._tile_unit_param_controls.values()
        strength_input.set_value(0.5)
        start_input.set_value(0.2)
        end_input.set_value(0.8)
        modal._create_button.click()
        saved_unit = self._saved_tile_unit()
        self.assertEqual(saved_unit.control_strength, 0.5)
        self.assertEqual(saved_unit.control_start, 0.2)
        self.assertEqual(saved_unit.control_end, 0.8)
        self.assertEqual(saved_unit.model.full_model_name if saved_unit.model else None, TILE_MODEL)

    def test_no_tile_model_removes_tile_unit_inputs(self) -> None:
        """Selecting no tile model removes the tile inputs, and selecting a model again restores them."""
        modal = ImageScaleModal(512, 512)
        assert modal._tile_model_dropdown is not None
        modal._tile_model_dropdown.setCurrentText(CONTROLNET_MODEL_NONE)
        self.assertEqual(modal._tile_unit_param_controls, {})
        self.assertIsNone(modal._tile_preprocessor_dropdown)
        modal._tile_model_dropdown.setCurrentText(TILE_MODEL)
        values = [widget.value() for widget in modal._tile_unit_param_controls.values()]
        self.assertEqual(values, [0.75, 0.1, 0.9])

    def test_size_fields_mirror_each_other(self) -> None:
        """Pixel edits update the percent fields and the reverse."""
        modal = ImageScaleModal(400, 200)
        modal._geometry.field(geometry_block.WIDTH).set_value(800)
        self.assertEqual(modal._geometry.value(geometry_block.SCALE_X), 2.0)
        modal._unit_control.set_value(UNIT_PCT)
        self.assertTrue(modal._geometry.percent_mode())
        modal._geometry.field(geometry_block.SCALE_Y).set_value(0.5)
        self.assertEqual(modal._geometry.value(geometry_block.HEIGHT), 100)
        self.assertEqual(modal._geometry.field(geometry_block.SCALE_Y).value_text(), '50%')

    def test_aspect_lock_applies_in_both_units(self) -> None:
        """With the lock on, editing one side scales the other, in pixels and in percent."""
        modal = ImageScaleModal(400, 200)
        modal._geometry.set_ratio_locked(True)
        modal._geometry.field(geometry_block.WIDTH).set_value(800)
        self.assertEqual(modal._geometry.value(geometry_block.HEIGHT), 400)
        modal._unit_control.set_value(UNIT_PCT)
        modal._geometry.field(geometry_block.SCALE_X).set_value(0.5)
        self.assertEqual(modal._geometry.value(geometry_block.WIDTH), 200)
        self.assertEqual(modal._geometry.value(geometry_block.HEIGHT), 100)

    def test_confirm_returns_size_and_cancel_returns_none(self) -> None:
        """Confirming returns the chosen size; cancelling returns none."""
        modal = ImageScaleModal(400, 200)
        modal.exec = lambda: 0  # type: ignore[method-assign]
        modal._geometry.field(geometry_block.WIDTH).set_value(300)
        modal._create_button.click()
        self.assertEqual(modal.show_image_modal(), QSize(300, 200))
        modal.reject()
        self.assertIsNone(modal.show_image_modal())

    def test_controls_are_not_clipped_when_the_window_widens(self) -> None:
        """The controls column spans the dialog, and the dialog is never narrower than the controls need."""
        modal = ImageScaleModal(512, 512)
        modal.show()
        modal.resize(modal.width() + 300, modal.height())
        self.assertGreaterEqual(modal.minimumWidth(), modal._controls.minimumSizeHint().width())
        self.assertGreater(modal._scroll.width(), 380)
        self.assertGreaterEqual(modal._scroll.viewport().width(), modal._controls.minimumSizeHint().width())
        self.assertEqual(modal._controls.width(), modal._scroll.viewport().width())
        modal.resize(10, modal.height())
        self.assertGreaterEqual(modal._scroll.viewport().width(), modal._controls.minimumSizeHint().width())
        modal.hide()

    def test_long_option_names_do_not_widen_the_dialog(self) -> None:
        """Dropdowns in every mode stay at their clamped width however long their options are."""
        long_name = 'control_lora_' + 'very_long_model_name_' * 8 + '.safetensors'
        cache = Cache()
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_MODELS, [long_name, CONTROLNET_MODEL_NONE])
        cache.set(Cache.GENERATOR_SCALING_MODES, [long_name, 'short'])
        reference = ImageScaleModal(512, 512)
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_MODELS, [TILE_MODEL, CONTROLNET_MODEL_NONE])
        cache.set(Cache.GENERATOR_SCALING_MODES, ['short'])
        modal = ImageScaleModal(512, 512)
        for dialog in (reference, modal):
            dialog.show()
        assert modal._mode_control is not None and reference._mode_control is not None
        for mode in (MODE_AI, MODE_GENERATOR, MODE_BASIC, MODE_AI):
            modal._mode_control.set_value(mode)
            reference._mode_control.set_value(mode)
            self.assertEqual(reference.minimumWidth(), modal.minimumWidth(), mode)
            self.assertLessEqual(modal.minimumWidth(), 380, mode)
        # The long names don't move any AI dropdown's right edge off the number fields':
        for dialog in (reference, modal):
            dialog.resize(dialog.width() + 150, dialog.height())
            dialog._mode_control.set_value(MODE_AI)
            body = dialog._ai_body
            edges = {widget.mapTo(body, widget.rect().topRight()).x()
                     for kind in (QComboBox, NumberField) for widget in body.findChildren(kind)
                     if widget.isVisibleTo(body)}
            self.assertEqual(len(edges), 1, edges)
        modal.hide()
        reference.hide()

    def test_ai_section_follows_mode(self) -> None:
        """The AI settings show only in AI upscaling mode, and the mode is saved to the cache."""
        cache = Cache()
        cache.set(Cache.USE_STABLE_DIFFUSION_UPSCALING, False)
        modal = ImageScaleModal(512, 512)
        modal.show()
        assert modal._mode_control is not None
        self.assertEqual(modal._mode, MODE_BASIC)
        self.assertTrue(modal._ai_section.isHidden())
        modal._mode_control.set_value(MODE_AI)
        self.assertTrue(cache.get(Cache.USE_STABLE_DIFFUSION_UPSCALING))
        self.assertFalse(modal._ai_section.isHidden())
        modal._mode_control.set_value(MODE_BASIC)
        self.assertFalse(cache.get(Cache.USE_STABLE_DIFFUSION_UPSCALING))
        self.assertTrue(modal._ai_section.isHidden())

    def test_ultimate_upscale_limits_scale(self) -> None:
        """The Ultimate SD Upscale script limits the size to four times the current size in AI mode only."""
        cache = Cache()
        cache.set(Cache.ULTIMATE_UPSCALE_SCRIPT_AVAILABLE, True)
        cache.set(Cache.USE_ULTIMATE_UPSCALE_SCRIPT, True)
        modal = ImageScaleModal(256, 128)
        self.assertEqual(modal._geometry.field(geometry_block.WIDTH).maximum(), 1024)
        self.assertEqual(modal._geometry.field(geometry_block.HEIGHT).maximum(), 512)
        assert modal._ult_upscale_checkbox is not None
        modal._ult_upscale_checkbox.setChecked(False)
        self.assertGreater(modal._geometry.field(geometry_block.WIDTH).maximum(), 1024)
