"""Tests ImageScaleModal's Stable Diffusion upscaling controls."""
from src.api.controlnet.controlnet_constants import CONTROLNET_MODEL_NONE
from src.api.controlnet.controlnet_model import ControlNetModel
from src.api.controlnet.controlnet_preprocessor import ControlNetPreprocessor
from src.api.controlnet.controlnet_unit import ControlNetUnit, ControlKeyType
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
        preprocessor = ControlNetPreprocessor(TILE_PREPROCESSOR, TILE_PREPROCESSOR, [])
        tile_unit = ControlNetUnit(ControlKeyType.WEBUI)
        tile_unit.model = ControlNetModel(TILE_MODEL)
        tile_unit.preprocessor = preprocessor
        tile_unit.control_strength.value = 0.75
        tile_unit.control_start.value = 0.1
        tile_unit.control_end.value = 0.9
        cache.set(Cache.SD_UPSCALING_AVAILABLE, True)
        cache.set(Cache.USE_STABLE_DIFFUSION_UPSCALING, True)
        cache.set(Cache.ULTIMATE_UPSCALE_SCRIPT_AVAILABLE, False)
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_MODELS, [TILE_MODEL, CONTROLNET_MODEL_NONE])
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_PREPROCESSORS, [preprocessor.serialize()])
        cache.set(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS, tile_unit.serialize())

    @staticmethod
    def _saved_tile_unit() -> ControlNetUnit:
        return ControlNetUnit.deserialize(Cache().get(Cache.SD_UPSCALING_CONTROLNET_TILE_SETTINGS))

    def test_tile_unit_inputs_show_saved_values(self) -> None:
        """The tile model's strength, start and end inputs open with the saved values."""
        modal = ImageScaleModal(512, 512)
        values = [widget.value() for widget in modal._tile_unit_param_controls]
        self.assertEqual(values, [0.75, 0.1, 0.9])

    def test_scaling_saves_changed_tile_unit_values(self) -> None:
        """Values changed in the tile inputs are saved when the modal closes, without waiting for the save timer."""
        modal = ImageScaleModal(512, 512)
        strength_input, start_input, end_input = modal._tile_unit_param_controls
        strength_input.setValue(0.5)
        start_input.setValue(0.2)
        end_input.setValue(0.8)
        modal._create_button.click()
        saved_unit = self._saved_tile_unit()
        self.assertEqual(float(saved_unit.control_strength.value), 0.5)
        self.assertEqual(float(saved_unit.control_start.value), 0.2)
        self.assertEqual(float(saved_unit.control_end.value), 0.8)
        self.assertEqual(saved_unit.model.full_model_name, TILE_MODEL)

    def test_no_tile_model_removes_tile_unit_inputs(self) -> None:
        """Selecting no tile model removes the tile inputs, and selecting a model again restores them."""
        modal = ImageScaleModal(512, 512)
        assert modal._tile_model_dropdown is not None
        modal._tile_model_dropdown.setCurrentText(CONTROLNET_MODEL_NONE)
        self.assertEqual(modal._tile_unit_param_controls, [])
        self.assertIsNone(modal._tile_preprocessor_dropdown)
        modal._tile_model_dropdown.setCurrentText(TILE_MODEL)
        values = [widget.value() for widget in modal._tile_unit_param_controls]
        self.assertEqual(values, [0.75, 0.1, 0.9])
