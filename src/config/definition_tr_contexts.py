"""The translation context of each config definition file's labels, descriptions, categories and options.

`Config` translates a definition file's text in its context, and `scripts/build_translations.py` extracts the text to
it. This module imports nothing, so the script can read it without loading Qt.
"""

DEFINITION_TR_CONTEXTS = {
    'a1111_setting_definitions.json': 'config.a1111_config',
    'application_config_definitions.json': 'config.application_config',
    'cache_value_definitions.json': 'config.cache',
    'key_config_definitions.json': 'config.key_config',
}
