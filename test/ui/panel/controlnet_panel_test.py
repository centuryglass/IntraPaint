"""Tests the ControlNet panel's use of the library's ControlNet types and the saved unit format."""
from typing import Any

from sd_backend_client import CONTROLNET_MODEL_NONE, PREPROCESSOR_NONE, ControlNetPreprocessor, ParameterDef, \
    PreprocessorParams

from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.controlnet_adapter import CONTROLNET_REUSE_IMAGE_CODE, \
    SavedControlNetUnit
from src.ui.panel.controlnet_panel import ControlNetPanel
from src.ui.widget.parameter_def_widget import create_parameter_widget, parameter_label, parameter_tooltip
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR

CANNY = 'canny'
CANNY_MODEL = 'control_canny'
CACHE_KEY = Cache.CONTROLNET_ARGS_0_COMFYUI


def _preprocessors() -> list[ControlNetPreprocessor]:
    return [ControlNetPreprocessor(name=PREPROCESSOR_NONE),
            ControlNetPreprocessor(name=CANNY, parameters=[
                ParameterDef(key='low_threshold', default_value=100, description='Lower bound',
                             min_val=0, max_val=255, step_val=1)])]


def _control_types() -> dict[str, Any]:
    return {'All': {'module_list': [PREPROCESSOR_NONE, CANNY], 'model_list': [CONTROLNET_MODEL_NONE, CANNY_MODEL],
                    'default_option': CANNY, 'default_model': CANNY_MODEL}}


class ControlNetPanelTest(IntraPaintTestCase):
    """Tests ControlNetPanel loading, editing and saving a unit."""

    def _panel(self) -> ControlNetPanel:
        panel = ControlNetPanel(CACHE_KEY, _preprocessors(), [CONTROLNET_MODEL_NONE, CANNY_MODEL], _control_types(),
                                False)
        return panel

    @staticmethod
    def _saved() -> SavedControlNetUnit:
        panel_json = Cache().get(CACHE_KEY)
        return SavedControlNetUnit.from_json(panel_json)

    def test_empty_cache_starts_with_default_unit(self) -> None:
        """A unit that was never saved is disabled and uses the generation area as its control image."""
        Cache().set(CACHE_KEY, '')
        panel = self._panel()
        panel._save_data_to_cache()
        saved = self._saved()
        self.assertFalse(saved.enabled)
        self.assertEqual(saved.image_string, CONTROLNET_REUSE_IMAGE_CODE)

    def test_changes_are_saved_in_the_library_format(self) -> None:
        """Strength, step range, preprocessor values and the enabled flag are saved when edited."""
        Cache().set(CACHE_KEY, '')
        panel = self._panel()
        panel._enabled_checkbox.setChecked(True)
        panel._control_strength_slider.setValue(0.5)  # type: ignore[union-attr]
        panel._control_start_slider.setValue(0.2)  # type: ignore[union-attr]
        panel._control_end_slider.setValue(0.8)  # type: ignore[union-attr]
        panel._dynamic_controls[0].setValue(80)  # type: ignore[union-attr]
        panel._save_data_to_cache()
        saved = self._saved()
        unit = saved.unit
        self.assertTrue(saved.enabled)
        self.assertEqual((unit.control_strength, unit.control_start, unit.control_end), (0.5, 0.2, 0.8))
        assert unit.preprocessor is not None and unit.model is not None
        self.assertEqual(unit.preprocessor.typedef.name, CANNY)
        self.assertEqual(unit.preprocessor.parameter_values, {'low_threshold': 80})
        self.assertEqual(unit.model.full_model_name, CANNY_MODEL)

    def test_start_above_end_moves_end(self) -> None:
        """Raising the starting step above the ending step moves the ending step with it."""
        Cache().set(CACHE_KEY, '')
        panel = self._panel()
        panel._control_end_slider.setValue(0.4)  # type: ignore[union-attr]
        panel._control_start_slider.setValue(0.6)  # type: ignore[union-attr]
        self.assertEqual(panel._control_end_slider.value(), 0.6)  # type: ignore[union-attr]
        self.assertEqual(panel._control_unit.control_end, 0.6)

    def test_loads_legacy_saved_unit(self) -> None:
        """A unit saved by an older version opens with its values."""
        with open(f'{TEST_RESOURCE_DIR}/controlnet_units/legacy_comfyui_unit.json', encoding='utf-8') as file:
            Cache().set(CACHE_KEY, file.read())
        panel = self._panel()
        saved = SavedControlNetUnit.from_json(Cache().get(CACHE_KEY))
        self.assertEqual(panel._saved.enabled, saved.enabled)
        self.assertEqual(panel._control_unit.control_strength, saved.unit.control_strength)

    def test_preview_request_carries_preprocessor_values(self) -> None:
        """The preview button requests the selected preprocessor with its current parameter values."""
        Cache().set(CACHE_KEY, '')
        panel = self._panel()
        panel._enabled_checkbox.setChecked(True)
        panel._dynamic_controls[0].setValue(60)  # type: ignore[union-attr]
        requests: list[tuple[PreprocessorParams, str]] = []
        panel.request_preview.connect(lambda params, image: requests.append((params, image)))
        panel._preview_button.click()
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][0].typedef.name, CANNY)
        self.assertEqual(requests[0][0].parameter_values, {'low_threshold': 60})

    def test_no_preprocessor_disables_preview(self) -> None:
        """Choosing the "None" preprocessor leaves the unit without a preprocessor."""
        Cache().set(CACHE_KEY, '')
        panel = self._panel()
        panel._enabled_checkbox.setChecked(True)
        index = panel._preprocessor_combobox.findText(PREPROCESSOR_NONE)
        panel._preprocessor_combobox.setCurrentIndex(index)
        self.assertIsNone(panel._control_unit.preprocessor)
        self.assertFalse(panel._preview_button.isEnabled())


class ParameterDefWidgetTest(IntraPaintTestCase):
    """Tests widgets built from ParameterDef values."""

    def test_widget_reports_changes(self) -> None:
        """An int parameter makes a widget limited to its range, and edits are passed to the callback."""
        param = ParameterDef(key='low_threshold', default_value=100, min_val=0, max_val=255, step_val=1)
        values: list[Any] = []
        widget = create_parameter_widget(param, 40, values.append)
        self.assertEqual(widget.value(), 40)  # type: ignore[union-attr]
        widget.setValue(50)  # type: ignore[union-attr]
        self.assertEqual(values[-1], 50)

    def test_invalid_initial_value_uses_default(self) -> None:
        """A value outside the parameter's range is replaced by the default."""
        param = ParameterDef(key='low_threshold', default_value=100, min_val=0, max_val=255, step_val=1)
        widget = create_parameter_widget(param, 999, lambda _: None)
        self.assertEqual(widget.value(), 100)  # type: ignore[union-attr]

    def test_webui_label_comes_from_description(self) -> None:
        """WebUI parameters are labeled with their description, and ComfyUI parameters with their key."""
        webui_param = ParameterDef(key='threshold_a', default_value=1.0, description='Low threshold')
        comfy_param = ParameterDef(key='low_threshold', default_value=1, description='Lower bound')
        self.assertEqual((parameter_label(webui_param), parameter_tooltip(webui_param)), ('Low threshold', ''))
        self.assertEqual((parameter_label(comfy_param), parameter_tooltip(comfy_param)),
                         ('low_threshold', 'Lower bound'))
