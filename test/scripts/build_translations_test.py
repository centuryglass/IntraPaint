"""Tests scripts/build_translations.py against small projects built in a temporary directory."""
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from xml.sax.saxutils import escape

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


MINIMAL_ENGLISH_GLOSSARY = """
    | Term | Meaning |
    | --- | --- |
    | Zebra | An animal. |
"""

MINIMAL_LANGUAGE_GLOSSARY = """
    | English term | Chosen rendering |
    | --- | --- |
    | Zebra | Zebra |
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
        self._write('resources/translations/languages.json', '{}')
        self._write('doc/translation/glossary.md', MINIMAL_ENGLISH_GLOSSARY)
        for language in ('de_DE', 'fr_FR', 'zh_CN'):
            self._write(f'doc/translation/{language}.md', MINIMAL_LANGUAGE_GLOSSARY)

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
        self._write('resources/translations/languages.json', '{"de_DE": {"machine_translated": false}}')
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
        self._write('resources/translations/languages.json', '{"fr_FR": {"machine_translated": true}}')
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

    def test_every_translation_needs_a_manifest_entry(self) -> None:
        """languages.json flags each translation as machine-translated or not, and lists nothing else."""
        self._write('resources/translations/fr_FR.ts', """\
            <?xml version="1.0" encoding="utf-8"?>
            <!DOCTYPE TS>
            <TS version="2.1" language="fr_FR">
            </TS>
        """)
        self._write('resources/translations/languages.json', '{"ja_JP": {"machine_translated": true}}')
        problems, _ = build_translations.build(self.project, check=True)
        self.assertEqual(2, len(problems), problems)
        self.assertIn('needs an entry for fr_FR.ts', problems[0])
        self.assertIn('entry for ja_JP, which has no ja_JP.ts', problems[1])

        self._write('resources/translations/languages.json', '{"fr_FR": {"machine_translated": "yes"}}')
        problems, _ = build_translations.build(self.project, check=True)
        self.assertEqual(1, len(problems), problems)
        self.assertIn('needs an entry for fr_FR.ts', problems[0])

        self._write('resources/translations/languages.json', '{"fr_FR": {"machine_translated": true}}')
        problems, _ = build_translations.build(self.project)
        self.assertEqual([], problems)

    def _write_translation(self, language: str, messages: list[tuple[str, str, str]], translation_type: str = '') -> None:
        """Writes a translation file with (context, source, translation) messages."""
        self._write('resources/translations/languages.json', f'{{"{language}": {{"machine_translated": true}}}}')
        entries = ''.join(
            f'<context><name>{context}</name><message><source>{escape(source)}</source>'
            f'<translation{translation_type}>{escape(translation)}</translation></message></context>'
            for context, source, translation in messages)
        self._write(f'resources/translations/{language}.ts',
                    f'<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n'
                    f'<TS version="2.1" language="{language}">{entries}</TS>\n')

    def _check_problems(self, language: str, messages: list[tuple[str, str, str]]) -> list[str]:
        directory = self._path('resources/translations')
        for name in os.listdir(directory):
            if name.endswith(('.ts', '.qm')) and name != build_translations.CATALOG_NAME:
                os.remove(os.path.join(directory, name))
        self._write_translation(language, messages)
        build_translations.build(self.project)
        problems, _ = build_translations.build(self.project, check=True)
        return problems

    def test_reports_changed_markup(self) -> None:
        """Tags, entities and line breaks must match the source, in any order."""
        source = 'a<br>b<b>c</b>&nbsp;'
        self._write('src/ui/markup.py', f"""
            from PySide6.QtWidgets import QApplication
            TR_ID = 'ui.markup'
            def _tr(key):
                return QApplication.translate(TR_ID, key)
            TEXT = _tr('{source}')
            LINES = _tr('one\\ntwo')
        """)
        self.assertEqual([], self._check_problems('de_DE', [
            ('ui.markup', source, 'x<b>y</b>z<br>&nbsp;'), ('ui.markup', 'one\ntwo', 'eins\nzwei')]))
        problems = self._check_problems('de_DE', [
            ('ui.markup', source, 'a b<b>c'), ('ui.markup', 'one\ntwo', 'eins zwei')])
        self.assertEqual(2, len(problems), problems)
        self.assertIn('markup', problems[0])
        self.assertIn("'one\\ntwo'", problems[1])

    def test_reports_accelerator_problems(self) -> None:
        """A translation keeps its accelerator, in its language's form, and no two share one in a context."""
        self._write('src/ui/menu.py', """
            from PySide6.QtWidgets import QApplication
            TR_ID = 'ui.menu'
            def _tr(key):
                return QApplication.translate(TR_ID, key)
            SAVE = _tr('&Save')
            SLIDERS = _tr('Sl&iders')
            PLAIN = _tr('Plain')
            AMP = _tr('A && B')
        """)
        german = [('ui.menu', '&Save', '&Speichern'), ('ui.menu', 'Sl&iders', 'Schieberegler'),
                  ('ui.menu', 'Plain', 'Einfach'), ('ui.menu', 'A && B', 'A && B')]
        problems = self._check_problems('de_DE', german)
        self.assertEqual(1, len(problems), problems)
        self.assertIn("'Sl&iders': the translation has 0 accelerator(s), expected 1", problems[0])

        problems = self._check_problems('de_DE', [('ui.menu', '&Save', '&Speichern'),
                                                  ('ui.menu', 'Sl&iders', '&Schieber')])
        self.assertEqual(1, len(problems), problems)
        self.assertIn('also used by', problems[0])

        problems = self._check_problems('zh_CN', [('ui.menu', '&Save', '保存(&S)'),
                                                 ('ui.menu', 'Sl&iders', '&滑块')])
        self.assertEqual(1, len(problems), problems)
        self.assertIn('not in the form', problems[0])

    def test_reports_style_problems(self) -> None:
        """A Chinese translation uses full-width punctuation, spaces Latin text, and keeps a label's colon."""
        self._write('src/ui/labels.py', """
            from PySide6.QtWidgets import QApplication
            TR_ID = 'ui.labels'
            def _tr(key):
                return QApplication.translate(TR_ID, key)
            OPACITY = _tr('&Opacity:')
            STEPS = _tr('Steps: {steps}')
            SENTENCE = _tr('Saved. Use VAE 2, then retry.')
            OPEN = _tr('Open...')
            WIDTH = _tr('Width')
        """)
        good = [('ui.labels', '&Opacity:', '不透明度(&O)：'), ('ui.labels', 'Steps: {steps}', '步数：{steps}'),
                ('ui.labels', 'Saved. Use VAE 2, then retry.', '已保存。使用 VAE 2，然后重试。'),
                ('ui.labels', 'Open...', '打开...'), ('ui.labels', 'Width', '宽度')]
        self.assertEqual([], self._check_problems('zh_CN', good))

        problems = self._check_problems('zh_CN', [('ui.labels', '&Opacity:', '不透明度(&O):'),
                                                 ('ui.labels', 'Saved. Use VAE 2, then retry.',
                                                  '已保存.使用VAE 2,然后重试。')])
        self.assertEqual(3, len(problems), problems)
        self.assertIn("'&Opacity:': the translation does not end with '：'", problems[0])
        self.assertIn("half-width punctuation after Chinese text at '存.'", problems[1])
        self.assertIn("no space between Chinese text and Latin letters or digits at '用V'", problems[2])

        german = [('ui.labels', '&Opacity:', '&Deckkraft:'), ('ui.labels', 'Width', 'Breite')]
        self.assertEqual([], self._check_problems('de_DE', german))

    def test_unfinished_drafts_are_not_compiled(self) -> None:
        """An unfinished entry that holds draft text falls back to English in the .qm file."""
        self._write_translation('de_DE', [('ui.example', 'Open', 'Entwurf')], ' type="unfinished"')
        problems, _ = build_translations.build(self.project)
        self.assertEqual([], problems)
        translator = QTranslator()
        self.assertTrue(translator.load(self._path('resources/translations/de_DE.qm')))
        self.assertEqual('', translator.translate('ui.example', 'Open'))


ENGLISH_GLOSSARY = """
    # English glossary

    | Term | Meaning | Where | UI strings |
    | --- | --- | --- | --- |
    | Layer | A layer. | Panel | "Add layer" |
    | Vertex / vertices | A corner. | Shape | "Vertices" |
    | Lock, transparency lock | Two locks. | Panel | "Toggle layer lock" |
    | Model, checkpoint | The model. | Panel | "Model" |
    | "Miter", "Round", "Match area, upscale" (line joins) | Join values. | Shape | "Miter" |
    | Negative prompt / "Negative" | What to avoid. | Panel | "Negative:" |

    ## Names kept as they are

    - Products: IntraPaint, Qt.
    - Formats: PNG,
      .ora.

    Theme names are also kept.
"""

LANGUAGE_GLOSSARY = """
    # Glossary

    | English term | Chosen rendering | Notes |
    | --- | --- | --- |
    | Layer | Ebene | - |
    | Vertex / vertices | Knoten / Ecke | - |
    | Lock, transparency lock | Sperre, Transparenzsperre | - |
    | Model, checkpoint | Modell | - |
    | "Miter", "Round", "Match area, upscale" (line joins) | "Gehrung", "Rund", "Bereich, skalieren" | - |
    | Negative prompt / "Negative" | Negativ | - |

    ## Names kept as they are

    - Products: IntraPaint.
"""


class GlossaryParserTest(IntraPaintTestCase):
    """Reading and joining the glossary tables."""

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._temp_dir.cleanup)

    def _write(self, name: str, text: str) -> str:
        path = os.path.join(self._temp_dir.name, name)
        with open(path, 'w', encoding='utf-8') as file:
            file.write(textwrap.dedent(text))
        return path

    def _join(self, english: str = ENGLISH_GLOSSARY, language: str = LANGUAGE_GLOSSARY):
        rows, names, english_problems = build_translations.parse_english_glossary(self._write('en.md', english))
        glossary, problems = build_translations.parse_language_glossary(self._write('de.md', language), rows)
        return rows, names, glossary, english_problems + problems

    def test_cell_syntax(self) -> None:
        """Commas split items, slashes split spellings, quotes make a spelling whole, a trailing label is dropped."""
        parse = build_translations.parse_glossary_cell
        spelling = build_translations.Spelling
        self.assertEqual([[spelling('Lock')], [spelling('transparency lock')]], parse('Lock, transparency lock', True))
        self.assertEqual([[spelling('Vertex'), spelling('vertices')]], parse('Vertex / vertices', True))
        self.assertEqual([[spelling('Negative prompt'), spelling('Negative', True)]],
                         parse('Negative prompt / "Negative"', True))
        self.assertEqual([[spelling('Match area, upscale / x', True)], [spelling('Box', True)]],
                         parse('"Match area, upscale / x", "Box" (scaling)', True))
        self.assertEqual([[spelling('Isolation')]], parse('Isolation (layer group)', True))
        self.assertEqual([[spelling('滑块(&I)')]], parse('滑块(&I)', False))

    def test_malformed_cells_fail(self) -> None:
        """Empty cells, dashes, unbalanced quotes, text beside quotes and empty items are errors."""
        for cell in ('', '—', '"Box', 'a "Box"', '"Box" b', 'a,, b', 'a / ', '"A""B"'):
            with self.subTest(cell=cell), self.assertRaises(ValueError):
                build_translations.parse_glossary_cell(cell, True)

    def test_rows_join(self) -> None:
        """Renderings pair with terms by position, or one rendering covers every term."""
        rows, names, glossary, problems = self._join()
        self.assertEqual([], problems)
        self.assertEqual(['IntraPaint', 'Qt', 'PNG', '.ora'], names)
        self.assertEqual(len(rows), len(glossary.rows))
        by_cell = {row.cell: row for row in glossary.rows}
        self.assertEqual([['Sperre'], ['Transparenzsperre']],
                         [term.renderings for term in by_cell['Lock, transparency lock'].terms])
        self.assertEqual([['Modell'], ['Modell']], [term.renderings for term in by_cell['Model, checkpoint'].terms])
        self.assertEqual([['Knoten', 'Ecke']], [term.renderings for term in by_cell['Vertex / vertices'].terms])
        self.assertEqual([['Gehrung'], ['Rund'], ['Bereich, skalieren']],
                         [term.renderings for term in glossary.rows[4].terms])

    def test_row_mismatches_fail_with_line(self) -> None:
        """A missing, unknown, repeated or miscounted row fails and names the file and line."""
        language = LANGUAGE_GLOSSARY.replace('    | Layer | Ebene | - |\n', '')
        language = language.replace('| Model, checkpoint | Modell |', '| Models | Modell |')
        language = language.replace('Sperre, Transparenzsperre', 'Sperre, Transparenzsperre, Extra')
        problems = self._join(language=language)[3]
        self.assertEqual(5, len(problems), problems)
        self.assertTrue(any("no row for the English term 'Layer'" in problem for problem in problems), problems)
        self.assertTrue(any("'Models' is not a Term" in problem and 'de.md:' in problem for problem in problems))
        self.assertTrue(any('3 renderings for 2 terms' in problem for problem in problems), problems)
        self.assertTrue(any("no row for the English term 'Model, checkpoint'" in problem for problem in problems))

        layer_row = '    | Layer | Ebene | - |\n'
        repeated = LANGUAGE_GLOSSARY.replace(layer_row, layer_row * 2)
        problems = self._join(language=repeated)[3]
        self.assertEqual(1, len(problems), problems)
        self.assertIn("'Layer' is already on line", problems[0])

    def test_bad_cells_name_file_and_row(self) -> None:
        """A cell that does not parse fails in either file."""
        problems = self._join(english=ENGLISH_GLOSSARY.replace('| Layer |', '| "Layer |'))[3]
        self.assertTrue(any(problem.startswith(self._temp_dir.name) and 'unbalanced quote' in problem
                            for problem in problems), problems)
        problems = self._join(language=LANGUAGE_GLOSSARY.replace('| Ebene |', '| — |'))[3]
        self.assertTrue(any('Chosen rendering cell' in problem and 'em dash' in problem for problem in problems))

    def test_kept_names_form(self) -> None:
        """A kept-names bullet without a label or with an empty name fails."""
        english = ENGLISH_GLOSSARY.replace('- Products: IntraPaint, Qt.', '- No label here')
        self.assertTrue(any('Label: name, name' in problem for problem in self._join(english=english)[3]))
        english = ENGLISH_GLOSSARY.replace('- Products: IntraPaint, Qt.', '- Products: IntraPaint,, Qt.')
        self.assertTrue(any('empty name' in problem for problem in self._join(english=english)[3]))

    def test_committed_glossaries_parse_and_join(self) -> None:
        """Every committed glossary parses, and each has a row for every English row."""
        directory = os.path.join(PROJECT_ROOT, 'doc', 'translation')
        rows, _, problems = build_translations.parse_english_glossary(os.path.join(directory, 'glossary.md'))
        self.assertEqual([], problems)
        self.assertGreater(len(rows), 0)
        for name in sorted(os.listdir(directory)):
            if name == 'glossary.md' or not name.endswith('.md'):
                continue
            with self.subTest(glossary=name):
                glossary, problems = build_translations.parse_language_glossary(os.path.join(directory, name), rows)
                self.assertEqual([], problems)
                self.assertEqual(len(rows), len(glossary.rows))


class GlossaryCheckTest(IntraPaintTestCase):
    """Matching glossary terms in source strings, and checking translations against the chosen renderings."""

    ENGLISH = """
        | Term | Meaning | Where | UI strings |
        | --- | --- | --- | --- |
        | Layer | A layer. | Panel | "Add layer" |
        | Layer group | A group. | Panel | "Add layer group" |
        | Scale (verb) | Resample. | Menu | "Scale image" |
        | Negative prompt | Avoid. | Panel | "Negative prompt:" |
        | Prompt | Describe. | Panel | "Prompt" |
        | "Box", "Screen" (scaling) | Values. | Menu | "Box" |
        | Create, merge | Verbs. | Menu | "Merge down" |
        | "Match area, upscale" | Option. | Panel | "Match area, upscale" |
        | Round | A word. | Panel | "Round" |
    """

    LANGUAGE = """
        | English term | Chosen rendering |
        | --- | --- |
        | Layer | Ebene |
        | Layer group | Ebenengruppe |
        | Scale (verb) | skalieren / vergrößern |
        | Negative prompt | Negativ-Prompt |
        | Prompt | Prompt |
        | "Box", "Screen" (scaling) | "Kasten", "Bildschirm" |
        | Create, merge | erstellen, zusammenführen |
        | "Match area, upscale" | Bereich |
        | Round | Runde |
    """

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._temp_dir.cleanup)
        english_path = os.path.join(self._temp_dir.name, 'en.md')
        language_path = os.path.join(self._temp_dir.name, 'de.md')
        for path, text in ((english_path, self.ENGLISH), (language_path, self.LANGUAGE)):
            with open(path, 'w', encoding='utf-8') as file:
                file.write(textwrap.dedent(text))
        self.rows, _, problems = build_translations.parse_english_glossary(english_path)
        self.assertEqual([], problems)
        self.glossary, problems = build_translations.parse_language_glossary(language_path, self.rows)
        self.assertEqual([], problems)

    def _matches(self, source: str) -> list[str]:
        return [spelling.text for _, _, spelling in build_translations.match_glossary_terms(source, self.rows)]

    def _problems(self, source: str, translation: str, comment: str | None = None) -> list[str]:
        catalog = build_translations.Catalog()
        catalog.add_message(build_translations.Message('ui.test', source, translation=translation, translation_type=None,
                                                       translator_comment=comment))
        return build_translations.glossary_problems('de.ts', self.glossary, catalog)

    def test_matching_ignores_case_and_accepts_regular_endings(self) -> None:
        """Unquoted spellings match words in any case, with -s, -es, -ed and -ing, and not parts of other words."""
        self.assertEqual(['Layer'], self._matches('Delete the LAYER'))
        self.assertEqual(['Layer'], self._matches('Layers'))
        self.assertEqual(['Create'], self._matches('Creating'))
        self.assertEqual(['merge'], self._matches('Merged'))
        self.assertEqual(['Scale'], self._matches('Scaling'))
        self.assertEqual([], self._matches('Layerless effects'))
        self.assertEqual([], self._matches('Background'))
        self.assertEqual([], self._matches('Grayscale'))

    def test_longest_term_consumes_its_span(self) -> None:
        """A longer term hides the shorter terms inside it."""
        self.assertEqual(['Layer group'], self._matches('Add layer group'))
        self.assertEqual(['Negative prompt'], self._matches('Negative prompt:'))
        self.assertEqual(['Layer', 'Prompt'], self._matches('Layer prompt'))
        self.assertEqual(['Negative prompt', 'Prompt'], self._matches('Negative prompt and prompt'))

    def test_quoted_terms_match_whole_strings_only(self) -> None:
        """Quoted spellings match the whole string, ignoring accelerator, colon and ellipsis, with case significant."""
        self.assertEqual(['Box'], self._matches('Box'))
        self.assertEqual(['Box'], self._matches('&Box...'))
        self.assertEqual(['Screen'], self._matches('Screen:'))
        self.assertEqual([], self._matches('Fit box'))
        self.assertEqual([], self._matches('box'))
        self.assertEqual([], self._matches('on the Screen'))
        self.assertEqual(['Match area, upscale'], self._matches('Match area, upscale'))

    def test_markup_and_placeholders_do_not_match(self) -> None:
        """Tags, entities, placeholder names and accelerators are removed before matching."""
        self.assertEqual([], self._matches('<b>x</b> {layer} %1 &nbsp;'))
        self.assertEqual(['Layer'], self._matches('<b>La&yer</b> {layer}'))

    def test_missing_rendering_is_reported(self) -> None:
        """A translation must hold a chosen rendering of each term, ignoring case, spacing and accelerators."""
        self.assertEqual([], self._problems('Add layer', 'Ebene hinzufügen'))
        self.assertEqual([], self._problems('Add layer', 'Neue EBENE'))
        self.assertEqual([], self._problems('Add layer group', 'Ebenengruppe'))
        self.assertEqual([], self._problems('Scale image', 'Bild vergrößern'))
        self.assertEqual([], self._problems('Create', 'er&stellen'))
        self.assertEqual([], self._problems('Create', 'er stellen'))
        problems = self._problems('Add layer', 'Schicht hinzufügen')
        self.assertEqual(1, len(problems), problems)
        self.assertIn("'Layer'", problems[0])
        self.assertIn('Ebene', problems[0])
        self.assertEqual(1, len(self._problems('Add layer group', 'Ebene')))
        self.assertEqual(1, len(self._problems('Box', 'Schachtel')))

    def test_unfinished_and_vanished_translations_are_not_checked(self) -> None:
        """Entries with no translation and vanished ones are not held to the glossary."""
        catalog = build_translations.Catalog()
        catalog.add_message(build_translations.Message('c', 'Layer'))
        catalog.add_message(build_translations.Message('c', 'Layers', translation='x', translation_type='vanished'))
        self.assertEqual([], build_translations.glossary_problems('de.ts', self.glossary, catalog))

    def test_exemptions(self) -> None:
        """A valid exemption suppresses the problem, and one the source no longer needs fails."""
        exemption = 'glossary: not "Layer" - the verb sense'
        self.assertEqual([], self._problems('Add layer', 'Schicht hinzufügen', exemption))
        self.assertEqual([], self._problems('Add layer', 'Ebene hinzufügen', exemption))
        problems = self._problems('Add group', 'Gruppe hinzufügen', exemption)
        self.assertEqual(1, len(problems), problems)

    def test_language_glossary_lookup(self) -> None:
        """The language's own file is used, then its prefix's."""
        for name in ('de_DE.md', 'zh.md'):
            with open(os.path.join(self._temp_dir.name, name), 'w', encoding='utf-8'):
                pass
        find = build_translations.find_language_glossary
        directory = self._temp_dir.name
        self.assertEqual(os.path.join(directory, 'de_DE.md'), find(directory, 'de_DE'))
        self.assertEqual(os.path.join(directory, 'zh.md'), find(directory, 'zh_CN'))
        self.assertIsNone(find(directory, 'fr_FR'))

    def test_committed_glossary_strings_match_their_own_rows(self) -> None:
        """Each quoted entry of the English glossary's UI strings column is in the catalog and matches its row."""
        directory = os.path.join(PROJECT_ROOT, 'doc', 'translation')
        rows, _, problems = build_translations.parse_english_glossary(os.path.join(directory, 'glossary.md'))
        self.assertEqual([], problems)
        catalog, problems = build_translations.build_catalog(PROJECT_ROOT)
        self.assertEqual([], problems)
        sources = {build_translations._glossary_source_text(message.source)  # pylint: disable=protected-access
                   for message in catalog.all_messages()}
        with open(os.path.join(directory, 'glossary.md'), encoding='utf-8') as file:
            table_rows = build_translations._table_rows(file.read().splitlines())  # pylint: disable=protected-access
        by_line = {row.line: row for row in rows}
        problems = []
        for number, header, cells in table_rows:
            if 'UI strings' not in header or number not in by_line:
                continue
            for string in re.findall(r'"([^"]*)"', cells[header.index('UI strings')]):
                if build_translations._glossary_source_text(string) not in sources:  # pylint: disable=protected-access
                    problems.append(f'line {number}: {string!r} is not a UI string.')
                elif not build_translations.match_glossary_terms(string, [by_line[number]]):
                    problems.append(f'line {number}: {string!r} matches no term of its row.')
        self.assertEqual([], problems)
