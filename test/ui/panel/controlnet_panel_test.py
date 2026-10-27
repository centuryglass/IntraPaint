"""Tests the ControlNet panel's use of the library's ControlNet types and the saved unit format."""
from typing import Any

from PySide6.QtCore import QPoint, QSize
from PySide6.QtGui import QImage
from sd_backend_client import CONTROLNET_MODEL_NONE, PREPROCESSOR_NONE, PREPROCESSOR_RES_PARAM_KEY, \
    ControlNetPreprocessor, ParameterDef, PreprocessorParams

from src.config.cache import Cache
from src.controller.image_generation.sd_adapters.controlnet_adapter import CONTROLNET_REUSE_IMAGE_CODE, \
    SavedControlNetUnit, to_request_unit
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.panel_fit import Orientation
from src.ui.panel.controlnet_panel import ControlNetPanel, SOURCE_GENERATION_AREA_VALUE, SOURCE_IMAGE_FILE_VALUE
from src.ui.widget.parameter_def_widget import create_parameter_field, create_parameter_widget, parameter_label, \
    parameter_tooltip
from test.base_test_case import IntraPaintTestCase, TEST_RESOURCE_DIR
from test.ui.panel_capture import PanelHost

CANNY = 'canny'
CANNY_MODEL = 'control_canny'
DEPTH = 'depth'
DEPTH_MODEL = 'control_depth'
# A strip with room for the preview's column, the size the strip layout issue showed:
STRIP_SIZE = QSize(1021, 314)
CACHE_KEYS = [Cache.CONTROLNET_ARGS_0_COMFYUI, Cache.CONTROLNET_ARGS_1_COMFYUI, Cache.CONTROLNET_ARGS_2_COMFYUI]
CACHE_KEY = CACHE_KEYS[0]


def _preprocessors() -> list[ControlNetPreprocessor]:
    return [ControlNetPreprocessor(name=PREPROCESSOR_NONE),
            ControlNetPreprocessor(name=CANNY, parameters=[
                ParameterDef(key=PREPROCESSOR_RES_PARAM_KEY, default_value=512, display_name='Resolution',
                             min_val=64, max_val=2048, step_val=8),
                ParameterDef(key='low_threshold', default_value=100, description='Lower bound',
                             min_val=0, max_val=255, step_val=1)]),
            ControlNetPreprocessor(name=DEPTH)]


def _control_types() -> dict[str, Any]:
    return {'All': {'module_list': [PREPROCESSOR_NONE, CANNY, DEPTH],
                    'model_list': [CONTROLNET_MODEL_NONE, CANNY_MODEL, DEPTH_MODEL],
                    'default_option': CANNY, 'default_model': CANNY_MODEL},
            'Canny': {'module_list': [PREPROCESSOR_NONE, CANNY], 'model_list': [CONTROLNET_MODEL_NONE, CANNY_MODEL],
                      'default_option': CANNY, 'default_model': CANNY_MODEL},
            'Depth': {'module_list': [PREPROCESSOR_NONE, DEPTH], 'model_list': [CONTROLNET_MODEL_NONE, DEPTH_MODEL],
                      'default_option': DEPTH, 'default_model': DEPTH_MODEL}}


class ControlNetPanelTest(IntraPaintTestCase):
    """Tests ControlNetPanel loading, editing and saving units."""

    def setUp(self) -> None:
        super().setUp()
        for key in CACHE_KEYS:
            Cache().set(key, '')

    @staticmethod
    def _panel(webui: bool = False) -> ControlNetPanel:
        return ControlNetPanel(_preprocessors(), [CONTROLNET_MODEL_NONE, CANNY_MODEL, DEPTH_MODEL], _control_types(),
                               CACHE_KEYS, webui)

    @staticmethod
    def _saved(index: int = 0) -> SavedControlNetUnit:
        return SavedControlNetUnit.from_json(Cache().get(CACHE_KEYS[index]))

    @staticmethod
    def _parameter_field(panel: ControlNetPanel, key: str) -> SliderField:
        field = next(control for control in panel._dynamic_controls
                     if isinstance(control, SliderField) and control.accessibleName() in (key, 'Resolution'))
        return field

    def _save_off_depth_unit(self, index: int) -> None:
        """Saves a unit that is off and uses Depth with a weight of 0.6 and an image file."""
        panel = self._panel()
        panel.tab_bar.setCurrentIndex(index)
        panel._preprocessor_combobox.setCurrentIndex(panel._preprocessor_combobox.findText(DEPTH))
        panel._model_combobox.setCurrentIndex(panel._model_combobox.findData(DEPTH_MODEL))
        panel._control_strength_slider.set_value(0.6)
        panel._image_source.set_value(SOURCE_IMAGE_FILE_VALUE)
        panel._image_path_edit.setText('refs/pose.png')
        panel._save_data_to_cache()
        panel.deleteLater()

    def test_empty_cache_starts_with_default_unit(self) -> None:
        """A unit that was never saved is disabled and uses the generation area as its control image."""
        panel = self._panel()
        panel._save_data_to_cache()
        saved = self._saved()
        self.assertFalse(saved.enabled)
        self.assertEqual(saved.image_string, CONTROLNET_REUSE_IMAGE_CODE)

    def test_changes_are_saved_in_the_library_format(self) -> None:
        """Strength, step range, preprocessor values and the enabled flag are saved when edited."""
        panel = self._panel()
        panel._enabled_checkbox.setChecked(True)
        panel._control_strength_slider.set_value(0.5)
        panel._control_start_slider.set_value(0.2)
        panel._control_end_slider.set_value(0.8)
        self._parameter_field(panel, 'low_threshold').set_value(80)
        panel._save_data_to_cache()
        saved = self._saved()
        unit = saved.unit
        self.assertTrue(saved.enabled)
        self.assertEqual((unit.control_strength, unit.control_start, unit.control_end), (0.5, 0.2, 0.8))
        assert unit.preprocessor is not None and unit.model is not None
        self.assertEqual(unit.preprocessor.typedef.name, CANNY)
        self.assertEqual(unit.preprocessor.parameter_values, {PREPROCESSOR_RES_PARAM_KEY: 512, 'low_threshold': 80})
        self.assertEqual(unit.model.full_model_name, CANNY_MODEL)

    def test_strength_runs_weight_start_end(self) -> None:
        """Weight comes first in the Strength section, then the start and end pair."""
        panel = self._panel()
        self.assertEqual([field.accessibleName() for field in panel.strength_fields], ['Weight', 'Start', 'End'])
        self.assertEqual(panel._strength_section.widget.summary(), 'weight 1.00, steps 0.00-1.00')

    def test_start_above_end_moves_end(self) -> None:
        """Raising the starting step above the ending step moves the ending step with it."""
        panel = self._panel()
        panel._control_end_slider.set_value(0.4)
        panel._control_start_slider.set_value(0.6)
        self.assertEqual(panel._control_end_slider.value(), 0.6)
        self.assertEqual(panel._control_unit.control_end, 0.6)

    def test_numeric_parameters_are_slider_fields_with_resolution_last(self) -> None:
        """Numeric preprocessor parameters get slider fields, and resolution comes after the others."""
        panel = self._panel()
        self.assertTrue(all(isinstance(control, SliderField) for control in panel._dynamic_controls))
        self.assertEqual([control.accessibleName() for control in panel._dynamic_controls],
                         ['low_threshold', 'Resolution'])

    def test_pixel_perfect_hides_resolution(self) -> None:
        """In the WebUI, Pixel perfect hides the resolution parameter, and turning it off shows it and is saved."""
        panel = self._panel(webui=True)
        resolution = self._parameter_field(panel, 'Resolution')
        assert panel._px_perfect_checkbox is not None
        self.assertTrue(panel._px_perfect_checkbox.isChecked())
        self.assertTrue(resolution.isHidden())
        panel._px_perfect_checkbox.setChecked(False)
        self.assertFalse(resolution.isHidden())
        panel._save_data_to_cache()
        self.assertFalse(self._saved().unit.pixel_perfect)

    def test_comfyui_has_no_webui_options(self) -> None:
        """ComfyUI shows no Pixel perfect or Low VRAM option."""
        panel = self._panel(webui=False)
        self.assertIsNone(panel._px_perfect_checkbox)
        self.assertIsNone(panel._vram_checkbox)

    def test_control_image_choice_maps_to_stored_values(self) -> None:
        """Generation area saves the reuse code, and Image file saves the path, which returns when chosen again."""
        panel = self._panel()
        self.assertEqual(panel._image_source.value(), SOURCE_GENERATION_AREA_VALUE)
        self.assertTrue(panel._image_path_row.isHidden())
        panel._image_source.set_value(SOURCE_IMAGE_FILE_VALUE)
        self.assertFalse(panel._image_path_row.isHidden())
        panel._image_path_edit.setText('control.png')
        panel._save_data_to_cache()
        self.assertEqual(self._saved().image_string, 'control.png')
        panel._image_source.set_value(SOURCE_GENERATION_AREA_VALUE)
        panel._save_data_to_cache()
        self.assertEqual(self._saved().image_string, CONTROLNET_REUSE_IMAGE_CODE)
        self.assertTrue(panel._image_path_row.isHidden())
        panel._image_source.set_value(SOURCE_IMAGE_FILE_VALUE)
        panel._save_data_to_cache()
        self.assertEqual(self._saved().image_string, 'control.png')

    def test_saved_image_file_loads_as_image_file(self) -> None:
        """A unit saved with an image path opens with Image file chosen and the path shown."""
        self._save_off_depth_unit(0)
        panel = self._panel()
        self.assertEqual(panel._image_source.value(), SOURCE_IMAGE_FILE_VALUE)
        self.assertEqual(panel._image_path_edit.text(), 'refs/pose.png')

    def test_loads_legacy_saved_unit(self) -> None:
        """A unit saved by an older version opens with its values."""
        with open(f'{TEST_RESOURCE_DIR}/controlnet_units/legacy_comfyui_unit.json', encoding='utf-8') as file:
            Cache().set(CACHE_KEY, file.read())
        saved = SavedControlNetUnit.from_json(Cache().get(CACHE_KEY))
        panel = self._panel()
        self.assertEqual(panel._saved.enabled, saved.enabled)
        self.assertEqual(panel._control_unit.control_strength, saved.unit.control_strength)

    def test_preview_request_carries_preprocessor_values(self) -> None:
        """The preview button requests the selected preprocessor with its current parameter values."""
        panel = self._panel()
        panel._enabled_checkbox.setChecked(True)
        self._parameter_field(panel, 'low_threshold').set_value(60)
        requests: list[tuple[PreprocessorParams, str]] = []
        panel.request_preview.connect(lambda params, image: requests.append((params, image)))
        panel._preview_button.click()
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0][0].typedef.name, CANNY)
        self.assertEqual(requests[0][0].parameter_values['low_threshold'], 60)
        self.assertEqual(requests[0][1], CONTROLNET_REUSE_IMAGE_CODE)

    def test_no_preprocessor_disables_preview(self) -> None:
        """Choosing the "None" preprocessor leaves the unit without a preprocessor."""
        panel = self._panel()
        panel._enabled_checkbox.setChecked(True)
        index = panel._preprocessor_combobox.findText(PREPROCESSOR_NONE)
        panel._preprocessor_combobox.setCurrentIndex(index)
        self.assertIsNone(panel._control_unit.preprocessor)
        self.assertFalse(panel._preview_button.isEnabled())

    @staticmethod
    def _preview_image() -> QImage:
        preview = QImage(64, 64, QImage.Format.Format_ARGB32_Premultiplied)
        preview.fill(0xff336699)
        return preview

    def test_preview_image_shows_for_its_unit(self) -> None:
        """A preview shows for the unit it belongs to, and returns with its tab."""
        panel = self._panel()
        panel.set_preview(self._preview_image(), 1)
        preview = panel.preview_image_widget
        self.assertFalse(preview.isVisibleTo(panel))
        panel.tab_bar.setCurrentIndex(1)
        self.assertTrue(preview.isVisibleTo(panel))
        panel.tab_bar.setCurrentIndex(0)
        self.assertFalse(preview.isVisibleTo(panel))

    def test_strip_lists_units_in_place_of_tabs(self) -> None:
        """A strip shows a unit list with the tabs' titles in place of the tabs, and choosing a row loads its unit."""
        self._save_off_depth_unit(1)
        panel = self._panel()
        panel._enabled_checkbox.setChecked(True)
        host = PanelHost(panel)
        host.capture(STRIP_SIZE, Orientation.STRIP)
        unit_list = panel.unit_list
        self.assertTrue(unit_list.isVisible())
        self.assertFalse(panel.tab_bar.isVisible())
        self.assertEqual([unit_list.item(i).text() for i in range(3)], ['1 Canny', '2 Depth', '3'])
        self.assertEqual([unit_list.item(i).toolTip() for i in range(3)], ['Unit 1: on', 'Unit 2: off', 'Unit 3: off'])
        # Every title fits without eliding:
        for row in range(unit_list.count()):
            title_width = unit_list.fontMetrics().horizontalAdvance(unit_list.item(row).text())
            self.assertGreaterEqual(unit_list.visualItemRect(unit_list.item(row)).width(), title_width)
        unit_list.setCurrentRow(1)
        self.assertEqual(panel.unit_index, 1)
        self.assertEqual(panel.tab_bar.currentIndex(), 1)
        self.assertEqual(panel._preprocessor_combobox.currentText(), DEPTH)
        panel.tab_bar.setCurrentIndex(0)
        self.assertEqual(unit_list.currentRow(), 0)
        host.capture(QSize(STRIP_SIZE.height(), STRIP_SIZE.width()), Orientation.SIDE)
        self.assertTrue(panel.tab_bar.isVisible())
        self.assertFalse(unit_list.isVisible())
        host.release()

    def test_strip_preview_has_its_own_column(self) -> None:
        """A strip shows the preview right of the preprocessor controls, and a side panel puts it back under them."""
        panel = self._panel()
        panel._enabled_checkbox.setChecked(True)
        panel.set_preview(self._preview_image())
        host = PanelHost(panel)
        host.capture(STRIP_SIZE, Orientation.STRIP)
        preview = panel.preview_image_widget
        preprocessor = panel._preprocessor_section.widget
        self.assertTrue(preview.isVisible())
        self.assertFalse(preprocessor.isAncestorOf(preview))
        self.assertGreaterEqual(preview.mapTo(panel, QPoint()).x(),
                                preprocessor.mapTo(panel, QPoint(preprocessor.width(), 0)).x())
        self.assertLessEqual(preview.mapTo(panel, QPoint(0, preview.height())).y(), STRIP_SIZE.height())

        preprocessor.set_expanded(False)
        self.assertFalse(preview.isVisible())
        preprocessor.set_expanded(True)
        self.assertTrue(preview.isVisible())

        host.capture(QSize(STRIP_SIZE.height(), STRIP_SIZE.width()), Orientation.SIDE)
        self.assertTrue(preview.isVisible())
        self.assertTrue(preprocessor.isAncestorOf(preview))
        host.release()

    def test_tabs_show_unit_state(self) -> None:
        """A tab shows its unit's number, its control type once set up or on, and whether it is on."""
        self._save_off_depth_unit(1)
        panel = self._panel()
        self.assertEqual([panel.tab_bar.tabText(i) for i in range(3)], ['1', '2 Depth', '3'])
        panel._enabled_checkbox.setChecked(True)
        self.assertEqual(panel.tab_bar.tabText(0), '1 Canny')
        self.assertEqual(panel.tab_bar.tabToolTip(0), 'Unit 1: on')
        self.assertEqual(panel.tab_bar.tabToolTip(1), 'Unit 2: off')

    def test_switching_tabs_saves_and_loads_units(self) -> None:
        """Choosing another tab saves the first unit's pending edits and loads the other unit's settings."""
        self._save_off_depth_unit(1)
        panel = self._panel()
        panel._control_strength_slider.set_value(1.5)
        panel.tab_bar.setCurrentIndex(1)
        self.assertEqual(self._saved(0).unit.control_strength, 1.5)
        self.assertEqual(panel.unit_index, 1)
        self.assertEqual(panel._control_strength_slider.value(), 0.6)
        self.assertEqual(panel._preprocessor_combobox.currentText(), DEPTH)
        panel.tab_bar.setCurrentIndex(0)
        self.assertEqual(panel._control_strength_slider.value(), 1.5)

    def test_off_unit_shows_summary_until_edited(self) -> None:
        """An off unit with settings shows a summary in place of its sections, and Edit settings opens them."""
        self._save_off_depth_unit(0)
        panel = self._panel()
        sections = [panel._control_image_section.widget, panel._preprocessor_section.widget,
                    panel._strength_section.widget]
        self.assertFalse(panel._off_summary.isHidden())
        self.assertTrue(all(section.isHidden() for section in sections))
        self.assertEqual([line.full_text for line in panel._off_summary_lines],
                         ['Depth · depth', 'depth', 'Weight 0.60, steps 0.00-1.00', 'Image file: pose.png'])
        panel._edit_settings_button.click()
        self.assertTrue(panel._off_summary.isHidden())
        self.assertFalse(any(section.isHidden() for section in sections))
        panel._edit_settings_button.click()
        self.assertTrue(all(section.isHidden() for section in sections))

    def test_unit_never_set_up_shows_its_sections(self) -> None:
        """A unit still at its default settings shows its sections with the switch off, and no Edit settings."""
        panel = self._panel()
        self.assertTrue(panel._off_summary.isHidden())
        self.assertTrue(panel._edit_settings_row.isHidden())
        self.assertFalse(panel._preprocessor_section.widget.isHidden())

    def test_disabled_unit_edits_persist_and_are_not_sent(self) -> None:
        """Settings edited while a unit is off are saved, and the unit still adds nothing to requests."""
        self._save_off_depth_unit(0)
        panel = self._panel()
        panel._edit_settings_button.click()
        panel._control_strength_slider.set_value(0.25)
        panel._save_data_to_cache()
        saved = self._saved()
        self.assertFalse(saved.enabled)
        self.assertEqual(saved.unit.control_strength, 0.25)
        self.assertIsNone(to_request_unit(saved, QImage(), False))

    def test_turning_unit_off_shows_summary(self) -> None:
        """Turning a set-up unit off replaces its sections with the summary."""
        panel = self._panel()
        panel._enabled_checkbox.setChecked(True)
        panel._control_strength_slider.set_value(0.5)
        self.assertTrue(panel._off_summary.isHidden())
        panel._enabled_checkbox.setChecked(False)
        self.assertFalse(panel._off_summary.isHidden())
        self.assertTrue(panel._strength_section.widget.isHidden())

    def test_reset_unit_keeps_enabled_state(self) -> None:
        """Reset returns the selected unit to its default settings and leaves it on."""
        self._save_off_depth_unit(0)
        panel = self._panel()
        panel._enabled_checkbox.setChecked(True)
        panel.header.reset_button.click()
        panel._save_data_to_cache()
        saved = self._saved()
        self.assertTrue(saved.enabled)
        self.assertEqual(saved.image_string, CONTROLNET_REUSE_IMAGE_CODE)
        self.assertEqual(saved.unit.control_strength, 1.0)
        assert saved.unit.preprocessor is not None
        self.assertEqual(saved.unit.preprocessor.typedef.name, CANNY)


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

    def test_field_reports_changes(self) -> None:
        """A numeric parameter makes a slider field over its range, and edits are passed to the callback."""
        param = ParameterDef(key='threshold', default_value=0.5, min_val=0.0, max_val=1.0, step_val=0.1)
        values: list[Any] = []
        field = create_parameter_field(param, 0.2, values.append)
        self.assertIsInstance(field, SliderField)
        self.assertEqual((field.minimum(), field.maximum(), field.value()), (0.0, 1.0, 0.2))
        field.set_value(0.7)
        self.assertEqual(values[-1], 0.7)
        self.assertEqual(create_parameter_field(param, 5.0, values.append).value(), 0.5)

    def test_label_comes_from_display_name(self) -> None:
        """Parameters are labeled with their display name when they have one and with their key otherwise."""
        webui_param = ParameterDef(key='threshold_a', default_value=1.0, display_name='Low threshold')
        comfy_param = ParameterDef(key='low_threshold', default_value=1, description='Lower bound')
        self.assertEqual((parameter_label(webui_param), parameter_tooltip(webui_param)), ('Low threshold', ''))
        self.assertEqual((parameter_label(comfy_param), parameter_tooltip(comfy_param)),
                         ('low_threshold', 'Lower bound'))
