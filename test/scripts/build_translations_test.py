"""Tests scripts/build_translations.py against small projects built in a temporary directory."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import textwrap

from PySide6.QtCore import QTranslator

from test.base_test_case import IntraPaintTestCase, PROJECT_ROOT

_SPEC = importlib.util.spec_from_file_location('build_translations',
                                               os.path.join(PROJECT_ROOT, 'scripts', 'build_translations.py'))
assert _SPEC is not None and _SPEC.loader is not None
build_translations = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_translations)

DEFINITIONS = {
    'application_config_definitions.json': """{
        "style": {"label": "Style:", "category": "Interface", "description": "Qt style", "type": "string",
                  "options": ["Fusion"], "translate": false},
        "hidden": {"label": "Hidden:", "category": "Internal", "description": "Never shown", "type": "string",
                   "translate": false}
    }""",
}

TRANSLATED_MODULE = """
    from PySide6.QtWidgets import QApplication

    TR_ID = 'ui.example'


    def _tr(key, disambiguation=None, n=-1):
        return QApplication.translate(TR_ID, key, disambiguation, n)


    FIRST = str(_tr('First'))
    OPEN = _tr('Open')
    OPEN_FILE = _tr('Open', 'File menu')
    GREETING = _tr('Hello, {name}')
    FILES = QApplication.translate('config.application_config', 'Files')
"""


class BuildTranslationsTest(IntraPaintTestCase):
    """Extraction, checking and translation file updates."""

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._temp_dir.cleanup)
        self.project = self._temp_dir.name
        os.makedirs(os.path.join(self.project, 'resources', 'translations'))
        os.makedirs(os.path.join(self.project, 'resources', 'config'))
        for file_name in build_translations.DEFINITION_TR_CONTEXTS:
            self._write(f'resources/config/{file_name}', DEFINITIONS.get(file_name, '{}'))
        self._write('src/ui/example.py', TRANSLATED_MODULE)

    def _path(self, relative_path: str) -> str:
        return os.path.join(self.project, *relative_path.split('/'))

    def _write(self, relative_path: str, text: str) -> None:
        path = self._path(relative_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(textwrap.dedent(text))

    def _read(self, relative_path: str) -> str:
        with open(self._path(relative_path), encoding='utf-8') as file:
            return file.read()

    def _catalog_keys(self) -> set[tuple]:
        catalog, problems = build_translations.build_catalog(self.project)
        self.assertEqual([], problems)
        return {message.key for message in catalog.all_messages()}

    def test_imports_no_qt(self) -> None:
        """The script runs where Qt's system libraries are missing, like CI's lint job, so it doesn't import PySide6."""
        script = os.path.join(PROJECT_ROOT, 'scripts', 'build_translations.py')
        check = (f'import runpy, sys; runpy.run_path({script!r}); '
                 'print(sorted(name for name in sys.modules if name.startswith("PySide6")))')
        result = subprocess.run([sys.executable, '-c', check], capture_output=True, text=True, check=True)
        self.assertEqual('[]', result.stdout.strip())

    def test_extracts_source_and_definition_strings(self) -> None:
        """Literal `_tr` and `translate` calls, and visible definition text, reach the catalog."""
        self.assertEqual({
            ('ui.example', 'First', None),
            ('ui.example', 'Open', None),
            ('ui.example', 'Open', 'File menu'),
            ('ui.example', 'Hello, {name}', None),
            ('config.application_config', 'Files', None),
            ('config.application_config', 'Style:', None),
            ('config.application_config', 'Qt style', None),
            ('config.application_config', 'Fusion', None),
            ('config.application_config', 'Interface', None),
        }, self._catalog_keys())

    def test_keeps_source_order(self) -> None:
        """Messages appear in the order their calls do in the file, however deeply each call is nested."""
        catalog, _ = build_translations.build_catalog(self.project)
        self.assertEqual(['First', 'Open', 'Open', 'Hello, {name}'],
                         [message.source for message in catalog.messages('ui.example')])

    def test_reports_calls_it_cannot_extract(self) -> None:
        """Untranslatable calls are reported with their file and line."""
        self._write('src/ui/no_tr_id.py', """
            LABEL = _tr('Label')
        """)
        self._write('src/ui/bad_calls.py', """
            from PySide6.QtWidgets import QApplication
            TR_ID = 'ui.bad_calls'
            PATH = '/tmp'
            BUILT = _tr('In ' + PATH)
            FORMATTED = _tr(f'In {PATH}')
            PLURAL = _tr('{n} files', None, 2)
            STRAY = QApplication.translate('application_config', 'Developer')
        """)
        _, problems = build_translations.build_catalog(self.project)
        self.assertEqual(['src/ui/bad_calls.py:5:', 'src/ui/bad_calls.py:6:', 'src/ui/bad_calls.py:7:',
                          'src/ui/bad_calls.py:8:', 'src/ui/no_tr_id.py:2:'],
                         sorted(problem.split(' ')[0] for problem in problems))

    def test_check_reports_a_stale_catalog_without_writing_it(self) -> None:
        """A rebuild settles the catalog, and a new string makes `--check` fail until the next rebuild."""
        self.assertEqual(([], ['resources/translations/main.ts']), build_translations.build(self.project))
        self.assertEqual(([], []), build_translations.build(self.project, check=True))
        catalog_text = self._read('resources/translations/main.ts')
        self.assertNotIn('line=', catalog_text)

        self._write('src/ui/added.py', """
            TR_ID = 'ui.added'
            SAVE = _tr('Save')
        """)
        self.assertEqual(([], ['resources/translations/main.ts']), build_translations.build(self.project, check=True))
        self.assertEqual(catalog_text, self._read('resources/translations/main.ts'))

    def test_translation_file_is_merged_and_compiled(self) -> None:
        """Translations are kept, new strings are added unfinished, removed ones vanish, and the .qm file works."""
        self._write('resources/translations/de_DE.ts', """\
            <?xml version="1.0" encoding="utf-8"?>
            <!DOCTYPE TS>
            <TS version="2.1" language="de_DE">
            <context>
                <name>ui.example</name>
                <message>
                    <source>Open</source>
                    <translation>Öffnen</translation>
                </message>
                <message>
                    <source>Removed</source>
                    <translation>Entfernt</translation>
                </message>
            </context>
            </TS>
        """)
        problems, stale = build_translations.build(self.project)
        self.assertEqual([], problems)
        self.assertEqual(['resources/translations/main.ts', 'resources/translations/de_DE.ts',
                          'resources/translations/de_DE.qm'], stale)
        self.assertEqual(([], []), build_translations.build(self.project, check=True))

        _, messages = build_translations.read_ts(self._path('resources/translations/de_DE.ts'))
        by_key = {message.key: message for message in messages}
        self.assertEqual(('Öffnen', None), (by_key[('ui.example', 'Open', None)].translation,
                                            by_key[('ui.example', 'Open', None)].translation_type))
        self.assertEqual('unfinished', by_key[('ui.example', 'Hello, {name}', None)].translation_type)
        self.assertEqual('vanished', by_key[('ui.example', 'Removed', None)].translation_type)

        translator = QTranslator()
        self.assertTrue(translator.load(self._path('resources/translations/de_DE.qm')))
        self.assertEqual('Öffnen', translator.translate('ui.example', 'Open'))
        self.assertEqual('', translator.translate('ui.example', 'Hello, {name}'))

    def test_reports_changed_placeholders_and_orphan_qm_files(self) -> None:
        """A translation must keep its source's placeholders, and every .qm file needs its .ts file."""
        self._write('resources/translations/fr_FR.ts', """\
            <?xml version="1.0" encoding="utf-8"?>
            <!DOCTYPE TS>
            <TS version="2.1" language="fr_FR">
            <context>
                <name>ui.example</name>
                <message>
                    <source>Hello, {name}</source>
                    <translation>Bonjour, {nom}</translation>
                </message>
            </context>
            </TS>
        """)
        self._write('resources/translations/en_US.qm', '')
        problems, _ = build_translations.build(self.project, check=True)
        self.assertEqual(2, len(problems), problems)
        self.assertIn('en_US.qm has no en_US.ts', problems[0])
        self.assertIn("'Hello, {name}'", problems[1])
