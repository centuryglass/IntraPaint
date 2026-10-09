"""Tests reading and writing saved ControlNet units, and turning them into sd_backend_client request units.

The `legacy_*` fixtures under `UNIT_DIR` were written by `src.api.controlnet.controlnet_unit.ControlNetUnit.serialize`,
so they stay readable after that module is removed.
"""
import json
import os
import tempfile

from PIL import Image
from PySide6.QtGui import QImage, QColor
from sd_backend_client import ControlNetModel, ControlNetPreprocessor, ControlNetUnit, ParameterDef, \
    PreprocessorParams

from src.api.controlnet.controlnet_constants import CONTROLNET_REUSE_IMAGE_CODE
from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.controlnet_adapter import SavedControlNetUnit, to_request_unit, \
    load_request_units
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR

UNIT_DIR = os.path.join(TEST_RESOURCE_DIR, 'controlnet_units')


def _fixture(name: str) -> str:
    with open(os.path.join(UNIT_DIR, f'{name}.json'), encoding='utf-8') as file:
        return file.read()


def _source_image() -> QImage:
    image = QImage(4, 4, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(10, 20, 30))
    return image


def _saved_unit(image_string: str = CONTROLNET_REUSE_IMAGE_CODE, model: bool = True,
                model_free: bool = False) -> SavedControlNetUnit:
    """Returns an enabled saved unit with a preprocessor and, optionally, a model."""
    typedef = ControlNetPreprocessor(name='canny', model_free=model_free,
                                     parameters=[ParameterDef(key='threshold_a', default_value=100)])
    unit = ControlNetUnit(preprocessor=PreprocessorParams(typedef=typedef, parameter_values={}),
                          model=ControlNetModel('control_canny') if model else None)
    return SavedControlNetUnit(True, image_string, unit)


class ControlNetAdapterTest(IntraPaintTestCase):
    """Tests reading and writing saved ControlNet units, and turning them into sd_backend_client request units."""

    def test_reads_legacy_webui_format(self) -> None:
        """A unit saved with WebUI keys keeps its settings, model, preprocessor and parameter values."""
        saved = SavedControlNetUnit.from_json(_fixture('legacy_webui_unit'))
        self.assertTrue(saved.enabled)
        self.assertEqual(saved.image_string, CONTROLNET_REUSE_IMAGE_CODE)
        unit = saved.unit
        assert unit.model is not None and unit.preprocessor is not None
        self.assertEqual(unit.model.full_model_name, 'control_v11p_sd15_canny [d14c016b]')
        self.assertEqual((unit.control_strength, unit.control_start, unit.control_end), (0.75, 0.1, 0.9))
        self.assertEqual(unit.preprocessor.typedef.name, 'canny')
        self.assertEqual(unit.preprocessor.parameter_values,
                         {'control_mode': 'Balanced', 'resize_mode': 'Crop and Resize', 'processor_res': 512,
                          'threshold_a': 50, 'threshold_b': 200})
        control_mode = unit.preprocessor.typedef.parameters[0]
        self.assertEqual(control_mode.description, 'Control mode')
        self.assertEqual(control_mode.option_list,
                         ['Balanced', 'My prompt is more important', 'ControlNet is more important'])

    def test_reads_legacy_comfyui_format(self) -> None:
        """A unit saved with ComfyUI keys keeps its node inputs, their limits and the preprocessor's inputs."""
        saved = SavedControlNetUnit.from_json(_fixture('legacy_comfyui_unit'))
        unit = saved.unit
        assert unit.model is not None and unit.preprocessor is not None
        self.assertEqual(unit.model.full_model_name, 'control_v11p_sd15_canny_fp16.safetensors')
        self.assertEqual((unit.control_strength, unit.control_start, unit.control_end), (0.75, 0.1, 0.9))
        typedef = unit.preprocessor.typedef
        self.assertEqual(typedef.name, 'CannyEdgePreprocessor')
        self.assertEqual(typedef.category_name, 'ControlNet Preprocessors/Line Extractors')
        self.assertFalse(typedef.has_mask_input)
        self.assertEqual(unit.preprocessor.parameter_values,
                         {'low_threshold': 80, 'high_threshold': 200, 'resolution': 512})
        low_threshold = typedef.parameters[0]
        self.assertEqual((low_threshold.default_value, low_threshold.min_val, low_threshold.max_val,
                          low_threshold.step_val), (100, 0, 255, 1))

    def test_reads_legacy_none_values_as_unset(self) -> None:
        """The legacy "None" model and preprocessor become unset fields."""
        saved = SavedControlNetUnit.from_json(_fixture('legacy_default_unit'))
        self.assertFalse(saved.enabled)
        self.assertIsNone(saved.unit.model)
        self.assertIsNone(saved.unit.preprocessor)

    def test_written_format_round_trips(self) -> None:
        """`to_json` output reads back as an equal unit, from either legacy format."""
        for fixture in ('legacy_webui_unit', 'legacy_comfyui_unit', 'legacy_default_unit'):
            saved = SavedControlNetUnit.from_json(_fixture(fixture))
            written = saved.to_json()
            self.assertNotIn('preprocessor_serialized', json.loads(written), fixture)
            self.assertEqual(SavedControlNetUnit.from_json(written), saved, fixture)

    def test_invalid_data_raises_value_error(self) -> None:
        """Malformed JSON, missing keys and values the library rejects all raise ValueError."""
        legacy = json.loads(_fixture('legacy_webui_unit'))
        out_of_range = {**legacy, 'control_start': 0.95}
        missing_key = {key: value for key, value in legacy.items() if key != 'model_name'}
        for data_str in ('{', '[]', json.dumps(missing_key), json.dumps(out_of_range), json.dumps({'unit': {}})):
            with self.assertRaises(ValueError, msg=data_str):
                SavedControlNetUnit.from_json(data_str)

    def test_reuse_image_code(self) -> None:
        """The generation area image is sent only when the request doesn't already send it as the init image."""
        saved = _saved_unit()
        txt2img_unit = to_request_unit(saved, _source_image(), False)
        assert txt2img_unit is not None and txt2img_unit.image is not None
        self.assertEqual(txt2img_unit.image.getpixel((0, 0)), (10, 20, 30, 255))
        img2img_unit = to_request_unit(saved, _source_image(), True)
        assert img2img_unit is not None
        self.assertIsNone(img2img_unit.image)
        self.assertIsNone(saved.unit.image, 'the saved unit must not change')

    def test_image_file(self) -> None:
        """A saved image path loads as RGBA, and a missing file skips the unit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = os.path.join(temp_dir, 'control.png')
            Image.new('RGB', (2, 2), (1, 2, 3)).save(image_path)
            unit = to_request_unit(_saved_unit(image_path), _source_image(), True)
            missing_unit = to_request_unit(_saved_unit(os.path.join(temp_dir, 'missing.png')), _source_image(), True)
        assert unit is not None and unit.image is not None
        self.assertEqual(unit.image.mode, 'RGBA')
        self.assertEqual(unit.image.getpixel((0, 0)), (1, 2, 3, 255))
        self.assertIsNone(missing_unit)

    def test_skips_unusable_units(self) -> None:
        """Disabled units, and units with no model whose preprocessor needs one, are skipped."""
        disabled = _saved_unit()
        disabled.enabled = False
        self.assertIsNone(to_request_unit(disabled, _source_image(), True))
        self.assertIsNone(to_request_unit(_saved_unit(model=False), _source_image(), True))
        self.assertIsNotNone(to_request_unit(_saved_unit(model=False, model_free=True), _source_image(), True))

    def test_load_request_units_skips_invalid_entries(self) -> None:
        """Invalid and disabled cached units are skipped, and the rest load in key order."""
        cache = Cache()
        cache.set(Cache.CONTROLNET_ARGS_0_WEBUI, 'not json')
        cache.set(Cache.CONTROLNET_ARGS_1_WEBUI, _fixture('legacy_default_unit'))
        cache.set(Cache.CONTROLNET_ARGS_2_WEBUI, _fixture('legacy_webui_unit'))
        units = load_request_units([Cache.CONTROLNET_ARGS_0_WEBUI, Cache.CONTROLNET_ARGS_1_WEBUI,
                                    Cache.CONTROLNET_ARGS_2_WEBUI], _source_image(), True)
        self.assertEqual(len(units), 1)
        assert units[0].preprocessor is not None
        self.assertEqual(units[0].preprocessor.typedef.name, 'canny')
