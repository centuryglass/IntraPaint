"""Tests choosing and loading the UI language in src/util/translation.py."""
import importlib.util
import json
import os
import tempfile
import textwrap

from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.util.translation import ENGLISH, ENGLISH_NAME, SYSTEM_LANGUAGE, available_languages, install_translation, \
    language_name, resolve_language, saved_language_setting
from test.base_test_case import IntraPaintTestCase, PROJECT_ROOT

_SPEC = importlib.util.spec_from_file_location('build_translations',
                                               os.path.join(PROJECT_ROOT, 'scripts', 'build_translations.py'))
assert _SPEC is not None and _SPEC.loader is not None
build_translations = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_translations)

TEST_CONTEXT = 'test.translation'
GERMAN_TS = """\
    <?xml version="1.0" encoding="utf-8"?>
    <!DOCTYPE TS>
    <TS version="2.1" language="de_DE">
    <context>
        <name>test.translation</name>
        <message>
            <source>Open</source>
            <translation>Öffnen</translation>
        </message>
    </context>
    </TS>
"""


class TranslationTest(IntraPaintTestCase):
    """Language discovery, naming, selection and loading, against a temporary translation directory."""

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._temp_dir.cleanup)
        self.dir = self._temp_dir.name

    def _add_language(self, code: str, machine_translated: bool) -> None:
        with open(os.path.join(self.dir, f'{code}.qm'), 'wb'):
            pass
        manifest_path = os.path.join(self.dir, 'languages.json')
        manifest = {}
        if os.path.isfile(manifest_path):
            with open(manifest_path, encoding='utf-8') as file:
                manifest = json.load(file)
        manifest[code] = {'machine_translated': machine_translated}
        with open(manifest_path, 'w', encoding='utf-8') as file:
            json.dump(manifest, file)

    def test_english_is_always_available(self) -> None:
        """English has no file, and leads the list ahead of the sorted translations."""
        self.assertEqual([ENGLISH], available_languages(self.dir))
        self._add_language('zh_CN', True)
        self._add_language('de_DE', False)
        self.assertEqual([ENGLISH, 'de_DE', 'zh_CN'], available_languages(self.dir))

    def test_names_are_native_and_mark_machine_translation(self) -> None:
        """Each language is named in itself, and a machine-translated one says so."""
        self._add_language('zh_CN', True)
        self._add_language('de_DE', False)
        self.assertEqual(ENGLISH_NAME, language_name(ENGLISH, self.dir))
        self.assertEqual('Deutsch', language_name('de_DE', self.dir))
        self.assertEqual('简体中文 (machine-translated)', language_name('zh_CN', self.dir))

    def test_names_add_the_territory_only_when_ambiguous(self) -> None:
        """Two variants of one language are told apart by territory."""
        self._add_language('pt_BR', False)
        self.assertEqual('português', language_name('pt_BR', self.dir))
        self._add_language('pt_PT', False)
        self.assertNotEqual(language_name('pt_BR', self.dir), language_name('pt_PT', self.dir))

    def test_system_language_uses_the_first_available_preference(self) -> None:
        """The system's first language with a translation wins, English stops the search, and the fallback is English."""
        self._add_language('zh_CN', True)
        self.assertEqual('zh_CN', resolve_language(SYSTEM_LANGUAGE, ['ja-JP', 'zh-CN', 'en-US'], self.dir))
        self.assertEqual('zh_CN', resolve_language(SYSTEM_LANGUAGE, ['zh-Hans-SG'], self.dir))
        self.assertEqual(ENGLISH, resolve_language(SYSTEM_LANGUAGE, ['zh-TW'], self.dir))
        self.assertEqual(ENGLISH, resolve_language(SYSTEM_LANGUAGE, ['en-GB', 'zh-CN'], self.dir))
        self.assertEqual(ENGLISH, resolve_language(SYSTEM_LANGUAGE, ['ja-JP'], self.dir))

    def test_chosen_language_falls_back_to_english_without_its_file(self) -> None:
        """An explicit choice is used as is, unless its translation is gone."""
        self._add_language('zh_CN', True)
        self.assertEqual('zh_CN', resolve_language('zh_CN', ['en-US'], self.dir))
        self.assertEqual(ENGLISH, resolve_language(ENGLISH, ['zh-CN'], self.dir))
        self.assertEqual(ENGLISH, resolve_language('de_DE', ['zh-CN'], self.dir))

    def test_saved_setting_is_read_from_the_sparse_config_file(self) -> None:
        """A missing file or key is the default, and a saved code is returned."""
        config_path = os.path.join(self.dir, 'config.json')
        self.assertEqual(SYSTEM_LANGUAGE, saved_language_setting(config_path))
        with open(config_path, 'w', encoding='utf-8') as file:
            json.dump({'config_version': 1}, file)
        self.assertEqual(SYSTEM_LANGUAGE, saved_language_setting(config_path))
        with open(config_path, 'w', encoding='utf-8') as file:
            json.dump({'config_version': 1, 'language': 'en'}, file)
        self.assertEqual(ENGLISH, saved_language_setting(config_path))

    def test_default_matches_the_config_definition(self) -> None:
        """saved_language_setting's default for a missing key is the definition's default."""
        self.assertEqual(SYSTEM_LANGUAGE, AppConfig().get_default(AppConfig.LANGUAGE))
        self.assertEqual(SYSTEM_LANGUAGE, AppConfig().get_options(AppConfig.LANGUAGE)[0])
        self.assertIn(ENGLISH, AppConfig().get_options(AppConfig.LANGUAGE))
        self.assertEqual(ENGLISH_NAME, AppConfig().get_option_display(ENGLISH))

    def test_installs_only_the_chosen_translation(self) -> None:
        """English installs nothing, and another language translates through its own file."""
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        self.assertIsNone(install_translation(app, ENGLISH, self.dir))
        self.assertIsNone(install_translation(app, 'de_DE', self.dir))

        ts_path = os.path.join(self.dir, 'de_DE.ts')
        with open(ts_path, 'w', encoding='utf-8') as file:
            file.write(textwrap.dedent(GERMAN_TS))
        build_translations.compile_qm(ts_path, os.path.join(self.dir, 'de_DE.qm'))
        translator = install_translation(app, 'de_DE', self.dir)
        self.assertIsNotNone(translator)
        try:
            self.assertEqual('Öffnen', QApplication.translate(TEST_CONTEXT, 'Open'))
        finally:
            app.removeTranslator(translator)
            translator.setParent(None)
        self.assertEqual('Open', QApplication.translate(TEST_CONTEXT, 'Open'))
