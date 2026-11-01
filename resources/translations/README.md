# Translating IntraPaint

If anyone feels like translating IntraPaint, I'd love to add your translations to the project. AI-generated
translations follow a separate process, drafted in [`doc/machine_translation.md`](../../doc/machine_translation.md).

## Files

- `main.ts` is the catalog: every string IntraPaint can translate, with no translations. It is generated, so don't edit
  it by hand.
- Each other `.ts` file is a translation, named after its language and region code (`es_MX.ts` for Spanish - Mexico).
- Each translation has a compiled `.qm` file of the same name. The `.qm` files are generated and committed with their
  `.ts` files.
- `languages.json` has an entry for each translation, saying whether it was machine-translated:
  `"es_MX": {"machine_translated": false}`. The build fails when a translation has no entry.

## Choosing a language

The "Language" setting, under Interface in the settings window, lists English and every language with a `.qm` file,
each by its own name. Languages flagged in `languages.json` are labeled as machine-translated. The default, "System
language", picks the system's language when a translation for it exists, and English otherwise. IntraPaint loads only
the chosen `.qm` file, at startup, so a change takes effect after a restart.

Wrong or confusing wording in a machine-translated language can be reported as a
[GitHub issue](https://github.com/centuryglass/IntraPaint/issues).

## Adding a translation

1. Install Qt Linguist. Download links and the program manual can be found at
   <https://doc.qt.io/qt-6/linguist-translators.html>.
2. Copy `main.ts`, naming the copy after the language and region you're adding.
3. Open it in Qt Linguist. In the Edit menu, open "Translation File Settings", and set the "Language" and
   "Country/Region" dropdowns under "Target language".
4. Translate the entries, and save the file.
5. Add an entry for it to `languages.json`, with `"machine_translated": false` for a translation written by a person.
6. Run `python scripts/build_translations.py` to update the file and build its `.qm` file.
7. Select it under Interface > Language in the settings window, restart IntraPaint and check how it looks.
8. Open a pull request with the new `.ts` and `.qm` files, or just send me the `.ts` file. I'll test it and merge it
   into the main codebase.

Keep every `{name}` and `%1` placeholder of the English text in your translation. IntraPaint fills them in, and the
build fails on a translation that drops or adds one.

Option names in the settings and tool panels (for example the edit modes) are shown translated, but IntraPaint always
saves the original English option, so translating them is safe.

## Keeping the catalog current

`python scripts/build_translations.py` regenerates `main.ts` from the source, updates every translation to match it and
rebuilds the `.qm` files. CI runs it with `--check`, and fails when a committed file is out of date, so a pull request
that adds or changes a user-facing string commits the regenerated `main.ts` with it. The script's docstring covers what
it extracts and the calls it rejects.

Updating a translation keeps the translations of strings that are still present. New strings are added unfinished,
and the translations of removed strings are kept and marked vanished, so a translator can reuse them.

Only display text is translated. A string that is also stored or compared, like a config option value, stays in
English in the code and is translated only where it is shown (`Config.get_option_display`).
