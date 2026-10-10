"""Tests ImageScaleModal's Stable Diffusion upscaling controls."""
from sd_backend_client import CONTROLNET_MODEL_NONE, ControlNetModel, ControlNetPreprocessor, ControlNetUnit, \
    PreprocessorParams

from src.controller.image_generation.sd_adapters.controlnet_adapter import SavedControlNetUnit
from src.config.cache import Cache
from src.ui.modal.image_scale_modal import ImageScaleModal
from test.base_test_case import IntraPaintTestCase

TILE_MODEL = 'control_v11f1e_sd15_tile'
TILE_PREPROCESSOR = 'tile_resample'


class ImageScaleModalTest(IntraPaintTestCase):
    """Tests ImageScaleModal's Stable Diffusion upscaling controls."""

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
        strength_input.setValue(0.5)
        start_input.setValue(0.2)
        end_input.setValue(0.8)
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
