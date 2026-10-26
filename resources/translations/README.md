# Translating IntraPaint

If anyone feels like translating IntraPaint, I'd love to add your translations to the project. AI-generated
translations follow a separate process, drafted in [`doc/machine_translation.md`](../../doc/machine_translation.md).

## Files

- `main.ts` is the catalog: every string IntraPaint can translate, with no translations. It is generated, so don't edit
  it by hand.
- Each other `.ts` file is a translation, named after its language and region code (`es_MX.ts` for Spanish - Mexico).
- Each translation has a compiled `.qm` file of the same name, which IntraPaint loads at startup. The `.qm` files are
  generated and committed with their `.ts` files.

## Adding a translation

1. Install Qt Linguist. Download links and the program manual can be found at
   <https://doc.qt.io/qt-6/linguist-translators.html>.
2. Copy `main.ts`, naming the copy after the language and region you're adding.
3. Open it in Qt Linguist. In the Edit menu, open "Translation File Settings", and set the "Language" and
   "Country/Region" dropdowns under "Target language".
4. Translate the entries, and save the file.
5. Run `python scripts/build_translations.py` to update the file and build its `.qm` file.
6. Open a pull request with the new `.ts` and `.qm` files, or just send me the `.ts` file. I'll test it and merge it
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
