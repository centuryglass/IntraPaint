"""Guards the rule that stored config option strings are never translated.

An option string in a definition file is both the saved value and the widget text, so translating a constant that is
compared against it silently breaks the comparison (AGENTS.md, "Conventions").
"""
import json
import os
import re

from test.base_test_case import IntraPaintTestCase, PROJECT_ROOT

DEFINITION_FILES = ('a1111_setting', 'application_config', 'cache_value', 'key_config')

# Files that map an option to a display string on purpose; the stored value stays untranslated.
DISPLAY_MAP_FILES = frozenset({
    'src/ui/input_fields/selection_mode_toggle.py',
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
