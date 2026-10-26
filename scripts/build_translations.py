"""Builds IntraPaint's translation catalog and translation files, and checks them in CI.

`resources/translations/main.ts` is the catalog: every translatable string, with no translations. It is extracted from
the `_tr` and `QApplication.translate` calls under `src/` and from the config definition files, by reading them with
`ast` and `json`. No source file is modified, and no Qt tool runs during extraction.

Every other `.ts` file in `resources/translations/` is a translation into the language its `language` attribute names.
Each is merged with the catalog: translations of strings still in the catalog are kept, new strings are added
unfinished, and translations of removed strings are kept as vanished. Each is compiled with PySide6's `lrelease` into
the `.qm` file of the same name beside it, which IntraPaint loads at startup.

Output is deterministic, so a rebuild with no source changes leaves the files untouched:
- Contexts are sorted by name. Messages keep the order they are first found in, reading files in sorted path order.
- Locations name the file only, so moving a string within a file changes nothing.

Extraction fails, naming the file and line, on calls it can't extract:
- `_tr`, or `translate(TR_ID, ...)`, in a file with no module-level `TR_ID`.
- A `_tr` call whose source text or disambiguation isn't a string literal. Text built at runtime has no catalog entry.
  Pass the variable parts as `str.format` placeholders.
- A `_tr` call with a plural count, which the catalog doesn't support.
- A `translate` call whose literal context is neither the file's `TR_ID` nor a config definition context.

A translation file fails when it doesn't match a fresh merge, when a translation drops or adds a `{name}` or `%1`
placeholder of its source, or when its `.qm` file is missing or stale. A `.qm` file with no `.ts` file also fails.

Usage: python scripts/build_translations.py [--check]
  Without options, rewrites main.ts, merges every translation file and rebuilds its .qm file.
  --check changes nothing, and exits with status 1 if a rebuild would change any file or any problem is found.
"""
import argparse
import ast
import json
import os
import re
import string
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional
from xml.sax.saxutils import escape, quoteattr

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_DIR)

# pylint: disable=wrong-import-position
from src.config.definition_tr_contexts import DEFINITION_TR_CONTEXTS  # noqa: E402

TRANSLATION_DIR = 'resources/translations'
CATALOG_NAME = 'main.ts'
SOURCE_DIR = 'src'
DEFINITION_DIR = 'resources/config'
SOURCE_LANGUAGE = 'en_US'
UPDATE_COMMAND = 'python scripts/build_translations.py'

TRANSLATE_HELPER = '_tr'
TRANSLATE_CLASSES = ('QApplication', 'QCoreApplication')
TR_ID_NAME = 'TR_ID'

UNFINISHED = 'unfinished'
VANISHED = 'vanished'
OBSOLETE = 'obsolete'

_PERCENT_PLACEHOLDER = re.compile(r'%(?:\d+|n)')


@dataclass
class Message:
    """One translatable string, and its translation when read from a translation file."""
    context: str
    source: str
    comment: Optional[str] = None
    locations: list[str] = field(default_factory=list)
    translation: str = ''
    translation_type: Optional[str] = UNFINISHED
    translator_comment: Optional[str] = None

    @property
    def key(self) -> tuple[str, str, Optional[str]]:
        """Identifies the message the way Qt's translator does."""
        return self.context, self.source, self.comment


class Catalog:
    """Messages grouped by context, each group in the order its messages were added."""

    def __init__(self) -> None:
        self._contexts: dict[str, dict[tuple[str, Optional[str]], Message]] = {}

    def add(self, context: str, source: str, comment: Optional[str], location: str) -> None:
        """Adds a message, or adds a location to the message already added with the same context, source and comment."""
        messages = self._contexts.setdefault(context, {})
        message = messages.get((source, comment))
        if message is None:
            message = Message(context, source, comment)
            messages[(source, comment)] = message
        if location not in message.locations:
            message.locations.append(location)

    def add_message(self, message: Message) -> None:
        """Adds a message as-is, replacing any message with the same key."""
        self._contexts.setdefault(message.context, {})[(message.source, message.comment)] = message

    def contexts(self) -> list[str]:
        """Returns every context name, sorted."""
        return sorted(self._contexts)

    def messages(self, context: str) -> list[Message]:
        """Returns a context's messages in the order they were added."""
        return list(self._contexts.get(context, {}).values())

    def all_messages(self) -> list[Message]:
        """Returns every message, in output order."""
        return [message for context in self.contexts() for message in self.messages(context)]


def _string_literal(node: Optional[ast.expr]) -> Optional[str]:
    """Returns the value of a string literal, or None for anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _module_tr_id(tree: ast.Module) -> Optional[str]:
    """Returns the string a module assigns to `TR_ID` at its top level, if any."""
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 \
                and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id == TR_ID_NAME:
            return _string_literal(statement.value)
    return None


def _call_argument(call: ast.Call, index: int, name: str) -> Optional[ast.expr]:
    """Returns a call's argument by position or keyword, or None if it wasn't passed."""
    if len(call.args) > index:
        return call.args[index]
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _is_translate_call(call: ast.Call) -> bool:
    return isinstance(call.func, ast.Attribute) and call.func.attr == 'translate' \
        and isinstance(call.func.value, ast.Name) and call.func.value.id in TRANSLATE_CLASSES


def extract_python(path: str, display_path: str, location: str, catalog: Catalog, problems: list[str]) -> None:
    """Adds the strings one Python file translates, and reports the calls it can't extract.

    Parameters
    ----------
    path: str
        The file to read.
    display_path: str
        The file name to use in problem reports.
    location: str
        The file name to record in the catalog, relative to the translation directory.
    catalog: Catalog
        Receives the extracted messages.
    problems: list[str]
        Receives a description of each call that can't be extracted.
    """
    with open(path, encoding='utf-8') as source_file:
        tree = ast.parse(source_file.read(), path)
    tr_id = _module_tr_id(tree)
    allowed_contexts = set(DEFINITION_TR_CONTEXTS.values())
    if tr_id is not None:
        allowed_contexts.add(tr_id)

    def _problem(node: ast.AST, text: str) -> None:
        line = getattr(node, 'lineno', 0)
        problems.append(f'{display_path}:{line}: {text}')

    calls = sorted((node for node in ast.walk(tree) if isinstance(node, ast.Call)),
                   key=lambda call: (call.lineno, call.col_offset))
    for node in calls:
        if isinstance(node.func, ast.Name) and node.func.id == TRANSLATE_HELPER:
            context = tr_id
            source_arg = _call_argument(node, 0, 'key')
            comment_arg = _call_argument(node, 1, 'disambiguation')
            count_arg = _call_argument(node, 2, 'n')
            if context is None:
                _problem(node, f'{TRANSLATE_HELPER}() is called, but the file has no module-level {TR_ID_NAME}.')
                continue
            source = _string_literal(source_arg)
            if source is None:
                _problem(node, f'{TRANSLATE_HELPER}() source text is not a string literal. Pass runtime values as '
                               'str.format placeholders.')
                continue
        elif _is_translate_call(node):
            context_arg = _call_argument(node, 0, 'context')
            source_arg = _call_argument(node, 1, 'key')
            comment_arg = _call_argument(node, 2, 'disambiguation')
            count_arg = _call_argument(node, 3, 'n')
            source = _string_literal(source_arg)
            if source is None:
                # Translates text known only at runtime, like config labels or the `_tr` helper's own argument.
                continue
            if isinstance(context_arg, ast.Name) and context_arg.id == TR_ID_NAME:
                context = tr_id
                if context is None:
                    _problem(node, f'translate() uses {TR_ID_NAME}, but the file has no module-level {TR_ID_NAME}.')
                    continue
            else:
                context = _string_literal(context_arg)
                if context is None:
                    _problem(node, 'translate() has literal source text but a context that is not a string literal.')
                    continue
                if context not in allowed_contexts:
                    _problem(node, f'translate() context {context!r} is neither the file\'s {TR_ID_NAME} nor a config '
                                   'definition context.')
                    continue
        else:
            continue
        comment = None
        if comment_arg is not None and not (isinstance(comment_arg, ast.Constant) and comment_arg.value is None):
            comment = _string_literal(comment_arg)
            if comment is None:
                _problem(node, 'The disambiguation is not a string literal.')
                continue
        if count_arg is not None and not (isinstance(count_arg, ast.Constant) and count_arg.value == -1):
            _problem(node, 'Plural forms are not supported. Format the count into the text instead.')
            continue
        catalog.add(context, source, comment, location)


def extract_definitions(path: str, display_path: str, location: str, context: str, catalog: Catalog,
                        problems: list[str]) -> None:
    """Adds the labels, descriptions, categories and options of one config definition file.

    An entry marked `"translate": false` with no options is internal state that is never shown, so it is skipped. An
    entry with options is always extracted: its options are stored untranslated, and widgets show their translation
    (`Config.get_option_display`).
    """
    with open(path, encoding='utf-8') as json_file:
        definitions = json.load(json_file)
    for key, entry in definitions.items():
        if entry.get('translate') is False and not entry.get('options'):
            continue
        if 'category' not in entry:
            problems.append(f'{display_path}: "{key}" has no category.')
            continue
        texts = [entry['label'], entry['description'], *entry.get('options', []), entry['category']]
        if 'subcategory' in entry:
            texts.append(entry['subcategory'])
        for text in texts:
            if isinstance(text, str) and text != '':
                catalog.add(context, text, None, location)


def build_catalog(project_dir: str = PROJECT_DIR) -> tuple[Catalog, list[str]]:
    """Extracts every translatable string in a project, and returns the catalog and any extraction problems."""
    catalog = Catalog()
    problems: list[str] = []
    translation_dir = os.path.join(project_dir, TRANSLATION_DIR)

    def _location(path: str) -> str:
        return os.path.relpath(path, translation_dir).replace(os.sep, '/')

    def _display_path(path: str) -> str:
        return os.path.relpath(path, project_dir).replace(os.sep, '/')

    python_files = []
    for directory, _, files in os.walk(os.path.join(project_dir, SOURCE_DIR)):
        python_files.extend(os.path.join(directory, name) for name in files if name.endswith('.py'))
    for path in sorted(python_files, key=_display_path):
        extract_python(path, _display_path(path), _location(path), catalog, problems)
    for file_name, context in sorted(DEFINITION_TR_CONTEXTS.items()):
        path = os.path.join(project_dir, DEFINITION_DIR, file_name)
        extract_definitions(path, _display_path(path), _location(path), context, catalog, problems)
    return catalog, problems


def write_ts(catalog: Catalog, language: Optional[str] = None) -> str:
    """Returns a catalog as the text of a Qt Linguist `.ts` file."""
    language_attribute = '' if language is None else f' language={quoteattr(language)}'
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<!DOCTYPE TS>',
             f'<TS version="2.1"{language_attribute} sourcelanguage="{SOURCE_LANGUAGE}">']
    for context in catalog.contexts():
        lines += ['<context>', f'    <name>{escape(context)}</name>']
        for message in catalog.messages(context):
            lines.append('    <message>')
            for location in sorted(message.locations):
                lines.append(f'        <location filename={quoteattr(location)}/>')
            lines.append(f'        <source>{escape(message.source)}</source>')
            if message.comment is not None:
                lines.append(f'        <comment>{escape(message.comment)}</comment>')
            if message.translator_comment:
                lines.append(f'        <translatorcomment>{escape(message.translator_comment)}</translatorcomment>')
            type_attribute = '' if message.translation_type is None else f' type="{message.translation_type}"'
            lines.append(f'        <translation{type_attribute}>{escape(message.translation)}</translation>')
            lines.append('    </message>')
        lines.append('</context>')
    lines.append('</TS>')
    return '\n'.join(lines) + '\n'


def read_ts(path: str) -> tuple[Optional[str], list[Message]]:
    """Reads a `.ts` file, returning its language and its messages."""
    root = ET.parse(path).getroot()
    messages = []
    for context_element in root.iter('context'):
        context = context_element.findtext('name', '')
        for message_element in context_element.iter('message'):
            translation_element = message_element.find('translation')
            messages.append(Message(
                context=context,
                source=message_element.findtext('source', ''),
                comment=message_element.findtext('comment'),
                translation='' if translation_element is None else ''.join(translation_element.itertext()),
                translation_type=None if translation_element is None else translation_element.get('type'),
                translator_comment=message_element.findtext('translatorcomment')))
    return root.get('language'), messages


def merge_translations(catalog: Catalog, existing: list[Message]) -> Catalog:
    """Returns a copy of the catalog carrying the translations of an existing translation file.

    A translation of a string that is no longer in the catalog is kept as vanished, so rewording a string doesn't
    discard work a translator may reuse. A vanished translation whose string returns comes back unfinished.
    """
    previous = {message.key: message for message in existing}
    merged = Catalog()
    for message in catalog.all_messages():
        old = previous.pop(message.key, None)
        new_message = Message(message.context, message.source, message.comment, list(message.locations))
        if old is not None:
            new_message.translation = old.translation
            new_message.translator_comment = old.translator_comment
            if old.translation == '' or old.translation_type in (UNFINISHED, VANISHED, OBSOLETE):
                new_message.translation_type = UNFINISHED
            else:
                new_message.translation_type = None
        merged.add_message(new_message)
    for old in previous.values():
        if old.translation != '':
            merged.add_message(Message(old.context, old.source, old.comment, [], old.translation, VANISHED,
                                       old.translator_comment))
    return merged


def _placeholders(text: str) -> Optional[list[str]]:
    """Returns the sorted `{name}` fields and `%1` markers in text, or None if its braces don't parse."""
    found = _PERCENT_PLACEHOLDER.findall(text)
    try:
        for _, field_name, format_spec, conversion in string.Formatter().parse(text):
            if field_name is not None:
                found.append('{' + field_name + ('!' + conversion if conversion else '')
                             + (':' + format_spec if format_spec else '') + '}')
    except ValueError:
        return None
    return sorted(found)


def placeholder_problems(file_name: str, catalog: Catalog) -> list[str]:
    """Reports each translation whose placeholders differ from its source's."""
    problems = []
    for message in catalog.all_messages():
        if message.translation == '' or message.translation_type == VANISHED:
            continue
        expected = _placeholders(message.source)
        actual = _placeholders(message.translation)
        if expected is not None and actual != expected:
            found = 'braces that do not parse' if actual is None else f'placeholders {actual}'
            problems.append(f'{file_name}: [{message.context}] {message.source!r}: the translation has {found}, '
                            f'expected {expected}.')
    return problems


def compile_qm(ts_path: str, qm_path: str) -> None:
    """Compiles a `.ts` file into a `.qm` file with the lrelease that ships in the PySide6 package."""
    import PySide6  # pylint: disable=import-outside-toplevel
    lrelease = os.path.join(os.path.dirname(PySide6.__file__), 'lrelease' + ('.exe' if os.name == 'nt' else ''))
    subprocess.run([lrelease, '-silent', ts_path, '-qm', qm_path], check=True)


def _read_bytes(path: str) -> Optional[bytes]:
    if not os.path.isfile(path):
        return None
    with open(path, 'rb') as file:
        return file.read()


def build(project_dir: str = PROJECT_DIR, check: bool = False) -> tuple[list[str], list[str]]:
    """Rebuilds the catalog and translation files, or only checks them.

    Returns
    -------
    problems: list[str]
        Errors that need a source or translation fix.
    stale: list[str]
        Project-relative paths of files a rebuild changes. When `check` is False they have been rewritten.
    """
    catalog, problems = build_catalog(project_dir)
    stale: list[str] = []
    translation_dir = os.path.join(project_dir, TRANSLATION_DIR)

    def _update(relative_path: str, content: bytes) -> None:
        path = os.path.join(translation_dir, relative_path)
        current = _read_bytes(path)
        if current is not None and relative_path.endswith('.ts'):
            # A Windows checkout may have converted line endings.
            current = current.replace(b'\r\n', b'\n')
        if current == content:
            return
        stale.append(f'{TRANSLATION_DIR}/{relative_path}')
        if not check:
            with open(path, 'wb') as file:
                file.write(content)

    _update(CATALOG_NAME, write_ts(catalog).encode('utf-8'))

    file_names = sorted(os.listdir(translation_dir))
    for file_name in file_names:
        stem, extension = os.path.splitext(file_name)
        if extension == '.qm' and f'{stem}.ts' not in file_names:
            problems.append(f'{TRANSLATION_DIR}/{file_name} has no {stem}.ts to build it from. Remove it.')
        if extension != '.ts' or file_name == CATALOG_NAME:
            continue
        language, existing = read_ts(os.path.join(translation_dir, file_name))
        if not language:
            problems.append(f'{TRANSLATION_DIR}/{file_name} has no language attribute.')
            continue
        merged = merge_translations(catalog, existing)
        problems.extend(placeholder_problems(f'{TRANSLATION_DIR}/{file_name}', merged))
        ts_text = write_ts(merged, language)
        _update(file_name, ts_text.encode('utf-8'))
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_ts = os.path.join(temp_dir, file_name)
            temp_qm = os.path.join(temp_dir, f'{stem}.qm')
            with open(temp_ts, 'w', encoding='utf-8') as ts_file:
                ts_file.write(ts_text)
            compile_qm(temp_ts, temp_qm)
            qm_content = _read_bytes(temp_qm)
            assert qm_content is not None
        _update(f'{stem}.qm', qm_content)
    return problems, stale


def main() -> int:
    """Runs the build or check, prints what it found, and returns the exit status."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true', help='change nothing, and fail if anything is stale')
    args = parser.parse_args()
    problems, stale = build(check=args.check)
    for problem in problems:
        print(problem)
    if args.check and stale:
        print('Out of date: ' + ', '.join(stale))
        print(f'Run `{UPDATE_COMMAND}` and commit the result.')
    elif stale:
        print('Updated: ' + ', '.join(stale))
    if problems:
        print(f'{len(problems)} translation problem(s).')
    return 1 if problems or (args.check and stale) else 0


if __name__ == '__main__':
    sys.exit(main())
