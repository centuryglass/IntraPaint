"""Guards the rule that stored config option strings are never translated.

An option string in a definition file is both the saved value and the widget text, so translating a constant that is
compared against it silently breaks the comparison (AGENTS.md, "Conventions").
"""
import json
import os
import re
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.input_fields.segmented_control import DisplayMode, Segment, SegmentedControl
from src.ui.input_fields.field_factory import create_control_widget
from src.util.shared_text import PIL_SCALING_MODES, scaling_mode_display
from test.base_test_case import IntraPaintTestCase, PROJECT_ROOT

DEFINITION_FILES = ('a1111_setting', 'application_config', 'cache_value', 'key_config')

# Files that map an option to a display string on purpose; the stored value stays untranslated.
DISPLAY_MAP_FILES = frozenset({
    'src/ui/input_fields/selection_mode_bar.py',
    'src/ui/modal/settings_controls.py',
    'src/ui/panel/generators/testing_panel.py',
    'src/util/visual/magic_wand_area.py',
    'src/ui/widget/color_picker/color_slider_block.py',
})

_TRANSLATE_CALL = re.compile(
    r"""(?:_tr|QApplication\.translate|QCoreApplication\.translate)\((?:\s*'[^']*',)?\s*(['"])(.*?)\1""")


def _load_definitions() -> dict[str, dict]:
    entries = {}
    for name in DEFINITION_FILES:
        path = os.path.join(PROJECT_ROOT, 'resources', 'config', f'{name}_definitions.json')
        with open(path, encoding='utf-8') as definition_file:
            for key, entry in json.load(definition_file).items():
                entries[f'{name}.{key}'] = entry
    return entries


class TranslationSafetyTest(IntraPaintTestCase):
    """Config option strings must stay out of the translation catalog and out of `_tr` calls."""

    def test_option_entries_are_not_translated(self) -> None:
        """Every entry with options carries `"translate": false`."""
        missing = [key for key, entry in _load_definitions().items()
                   if entry.get('options') and entry.get('translate') is not False]
        self.assertEqual([], missing, 'Entries with options need "translate": false')

    def test_option_strings_are_not_translation_sources(self) -> None:
        """No `_tr` call under src/ uses a stored option string as its source text."""
        options = {option for entry in _load_definitions().values() if entry.get('translate') is False
                   for option in entry.get('options', [])}
        # Plain words that are also ordinary UI text rather than stored values:
        options -= {'None', 'default', 'auto'}
        src_root = os.path.join(PROJECT_ROOT, 'src')
        offenders = []
        for directory, _, files in os.walk(src_root):
            for file_name in files:
                path = os.path.join(directory, file_name)
                relative = os.path.relpath(path, PROJECT_ROOT).replace(os.sep, '/')
                if not file_name.endswith('.py') or relative in DISPLAY_MAP_FILES:
                    continue
                with open(path, encoding='utf-8') as source_file:
                    for line_number, line in enumerate(source_file, 1):
                        for match in _TRANSLATE_CALL.finditer(line):
                            if match.group(2) in options:
                                offenders.append(f'{relative}:{line_number}: {match.group(2)!r}')
        self.assertEqual([], offenders)


class OptionDisplayTest(IntraPaintTestCase):
    """Config widgets show translated option text while the stored value stays untranslated."""

    def setUp(self) -> None:
        super().setUp()
        self._translate = QApplication.translate
        edit_modes = Cache().get_options(Cache.EDIT_MODE)  # Constructing the Cache translates, so it comes first.

        def _shout(context: str, text: str, *args, **kwargs) -> str:
            if context == 'config.cache' and text in edit_modes:
                return text.upper()
            return self._translate(context, text, *args, **kwargs)
        patcher = patch.object(QApplication, 'translate', side_effect=_shout)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_combo_box_displays_translation_and_keeps_stored_value(self) -> None:
        """The dropdown text is translated, and its value and the saved config stay the raw option."""
        cache = Cache()
        combo_box = create_control_widget(cache, Cache.EDIT_MODE)
        self.assertEqual(['INPAINT', 'IMAGE TO IMAGE', 'TEXT TO IMAGE'],
                         [combo_box.itemText(i) for i in range(combo_box.count())])
        self.assertEqual('Inpaint', combo_box.value())
        combo_box.setCurrentIndex(2)
        self.assertEqual('Text to Image', cache.get(Cache.EDIT_MODE))
        cache.set(Cache.EDIT_MODE, 'Image to Image')
        self.assertEqual('IMAGE TO IMAGE', combo_box.currentText())

    def test_segmented_control_displays_translation(self) -> None:
        """A segmented control shows the display names but reports the option strings."""
        control = SegmentedControl([Segment('Add', 'AGREGAR'), Segment('Subtract', 'RESTAR')], DisplayMode.LABEL)
        control.setValue('Subtract')
        self.assertEqual('Subtract', control.value())
        self.assertEqual(['AGREGAR', 'RESTAR'], [segment.label for segment in control.segments])


class ScalingModeOptionTest(IntraPaintTestCase):
    """PIL scaling modes are stored by their untranslated names, whatever the interface language."""

    def test_scaling_mode_options_are_untranslated(self) -> None:
        """The upscale and downscale options are the English mode names, so a saved choice survives a language
        change."""
        config = AppConfig()
        for key in (AppConfig.PIL_UPSCALE_MODE, AppConfig.PIL_DOWNSCALE_MODE):
            self.assertEqual(['Bilinear', 'Nearest', 'Hamming', 'Bicubic', 'Lanczos', 'Box'], config.get_options(key))
        self.assertEqual(list(PIL_SCALING_MODES), config.get_options(AppConfig.PIL_UPSCALE_MODE))

    def test_settings_dropdown_displays_translation_and_keeps_stored_value(self) -> None:
        """The settings dropdown shows `scaling_mode_display` text and saves the untranslated name."""
        config = AppConfig()
        config.set(AppConfig.PIL_UPSCALE_MODE, 'Bicubic')
        with patch('src.config.application_config.scaling_mode_display', side_effect=str.upper):
            combo_box = create_control_widget(config, AppConfig.PIL_UPSCALE_MODE)
        self.assertEqual('BICUBIC', combo_box.currentText())
        self.assertEqual('Bicubic', combo_box.value())
        combo_box.setCurrentIndex(combo_box.findData('Box'))
        self.assertEqual('Box', config.get(AppConfig.PIL_UPSCALE_MODE))

    def test_backend_names_display_as_written(self) -> None:
        """A scaling mode name `scaling_mode_display` doesn't know is shown unchanged."""
        self.assertEqual('R-ESRGAN 4x+', scaling_mode_display('R-ESRGAN 4x+'))
