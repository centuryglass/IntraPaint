"""Chooses the UI language and loads its translation at startup.

Each translation is a `.qm` file in `resources/translations/`, named after its language code (`zh_CN.qm`), with an
entry in the `languages.json` manifest beside it. English is the source language and has no file.

The translator is installed before most of `src/` is imported, because config labels and module-level `_tr`
constants are translated once, when they are created. This module therefore imports nothing that constructs a config,
and reads the saved `AppConfig.LANGUAGE` value straight from the config file. Changing the language takes a restart.
"""
import json
import logging
import os
from typing import Any, Optional

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from src.util.shared_constants import PROJECT_DIR, APP_CONFIG_PATH

logger = logging.getLogger(__name__)

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'util.translation'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


TRANSLATION_DIR = f'{PROJECT_DIR}/resources/translations'
# Maps each translation's language code to its metadata. `scripts/build_translations.py` requires an entry for every
# translation file, and none for missing ones.
LANGUAGE_MANIFEST_NAME = 'languages.json'
MANIFEST_MACHINE_TRANSLATED = 'machine_translated'

# `AppConfig.LANGUAGE` values. SYSTEM_LANGUAGE must match the key's default in application_config_definitions.json.
SYSTEM_LANGUAGE = 'System language'
ENGLISH = 'en'
ENGLISH_NAME = 'English'
LANGUAGE_CONFIG_KEY = 'language'


def read_language_manifest(translation_dir: str = TRANSLATION_DIR) -> dict[str, Any]:
    """Returns the language manifest's entries, or an empty dict if it is missing or unreadable."""
    try:
        with open(os.path.join(translation_dir, LANGUAGE_MANIFEST_NAME), encoding='utf-8') as file:
            manifest = json.load(file)
    except (OSError, json.JSONDecodeError) as err:
        logger.warning(f'Reading the language manifest failed: {err}')
        return {}
    return manifest if isinstance(manifest, dict) else {}


def available_languages(translation_dir: str = TRANSLATION_DIR) -> list[str]:
    """Returns English followed by the code of every language with a `.qm` file, sorted."""
    try:
        file_names = os.listdir(translation_dir)
    except OSError:
        file_names = []
    codes = sorted(name[:-len('.qm')] for name in file_names if name.endswith('.qm'))
    return [ENGLISH, *codes]


def is_machine_translated(language: str, translation_dir: str = TRANSLATION_DIR) -> bool:
    """Returns whether a language's manifest entry marks it as machine-translated."""
    entry = read_language_manifest(translation_dir).get(language)
    return isinstance(entry, dict) and entry.get(MANIFEST_MACHINE_TRANSLATED) is True


def language_name(language: str, translation_dir: str = TRANSLATION_DIR) -> str:
    """Returns a language's name written in that language, with a note when it is machine-translated.

    The territory is added only when another available language has the same name, such as two kinds of Portuguese.
    """
    if language == ENGLISH:
        return ENGLISH_NAME
    locale = QLocale(language)
    name = locale.nativeLanguageName() or language
    others = [code for code in available_languages(translation_dir) if code not in (language, ENGLISH)]
    if any(QLocale(code).nativeLanguageName() == name for code in others):
        name = f'{name} ({locale.nativeTerritoryName()})'
    if is_machine_translated(language, translation_dir):
        # Translated here, not at import: this module loads before the translator is installed.
        name = _tr('{language} (machine-translated)').format(language=name)
    return name


def resolve_language(setting: str, ui_languages: Optional[list[str]] = None,
                     translation_dir: str = TRANSLATION_DIR) -> str:
    """Returns the language code to load for an `AppConfig.LANGUAGE` value.

    Parameters
    ----------
    setting: str
        A language code, or SYSTEM_LANGUAGE. A code with no translation file resolves to English.
    ui_languages: list[str], optional
        The system's preferred languages, most preferred first. Defaults to `QLocale.system().uiLanguages()`.
        SYSTEM_LANGUAGE picks the first one IntraPaint has, matching the exact code before the language and script
        alone, and falls back to English.
    """
    available = available_languages(translation_dir)
    if setting != SYSTEM_LANGUAGE:
        return setting if setting in available else ENGLISH
    if ui_languages is None:
        ui_languages = QLocale.system().uiLanguages()
    for ui_language in ui_languages:
        locale = QLocale(ui_language)
        if locale.language() == QLocale.Language.English:
            return ENGLISH
        if locale.name() in available:
            return locale.name()
        for code in available:
            candidate = QLocale(code)
            if candidate.language() == locale.language() and candidate.script() == locale.script():
                return code
    return ENGLISH


def saved_language_setting(config_path: str = APP_CONFIG_PATH) -> str:
    """Returns the `AppConfig.LANGUAGE` value saved in a config file, without constructing `AppConfig`.

    Saved config files only hold values that differ from their default, so a missing file or key means
    SYSTEM_LANGUAGE.
    """
    try:
        with open(config_path, encoding='utf-8') as file:
            saved = json.load(file)
    except (OSError, json.JSONDecodeError):
        return SYSTEM_LANGUAGE
    value = saved.get(LANGUAGE_CONFIG_KEY) if isinstance(saved, dict) else None
    return value if isinstance(value, str) else SYSTEM_LANGUAGE


def install_translation(app: QApplication, language: str,
                        translation_dir: str = TRANSLATION_DIR) -> Optional[QTranslator]:
    """Loads a language's `.qm` file into a new translator and installs it, unless the language is English.

    Returns the translator, which must be kept referenced while it is installed, or None if nothing was installed.
    """
    if language == ENGLISH:
        return None
    translator = QTranslator(app)
    qm_path = os.path.join(translation_dir, f'{language}.qm')
    if not translator.load(qm_path):
        logger.error(f'Failed to load translation {qm_path}, using English.')
        return None
    app.installTranslator(translator)
    return translator
