# Machine translation process (draft)

**Status: work in progress.** This is a first outline, written before any translation has been attempted. Expect it
to change once a pilot language has been through it.

How IntraPaint gets AI-generated translations of its UI when the maintainer speaks only English and no native-speaking
reviewer is available. The process aims for translations that are useful to people who don't read English well,
without needing a professional localization budget. It builds on the catalog workflow in
[`resources/translations/README.md`](../resources/translations/README.md).

## When a language is worth shipping

A machine translation ships only when all of these hold. Without them, the language is left out and users get English.

- **English is one click away.** The language picker labels the language as machine-translated, and a user can switch
  back to English at any time. The picker is the Interface > Language setting
  ([`resources/translations/README.md`](../resources/translations/README.md#choosing-a-language)). A translation is
  labeled when its `languages.json` entry has `"machine_translated": true`.
- **Stale translations fall back to English.** When an English string changes, its old translation is dropped until
  it is redone. A translation that no longer matches its source is worse than none. Untranslated strings show in
  English, so a partly translated UI is acceptable.
- **The key terms have been checked against real usage.** If "inpaint", "mask" or "denoising strength" come out wrong,
  the AI features become hard to find, and those are why people use IntraPaint.
- **Models are strong in the language.** If two models from different families disagree on much of the glossary, the
  language waits.

Start with the languages that have the largest Stable Diffusion communities and the most existing terminology to
check against: Simplified Chinese, Japanese and Korean. Spanish, German, French and Brazilian Portuguese come next.

## Process

### 1. English glossary (once, for all languages)

Before any per-language work, extract the terms the UI depends on into one English glossary,
[`doc/translation/glossary.md`](translation/glossary.md). For each term, record:

- a short definition, in IntraPaint's sense of the word;
- where it appears (panel, menu, setting) and one example string;
- whether it is general image-editing vocabulary (layer, selection, opacity), Stable Diffusion vocabulary (inpainting,
  denoising strength, CFG scale, sampler, seed, LoRA, ControlNet) or specific to IntraPaint.

Common UI words that models already translate well (Open, Save, Undo) don't need entries. The glossary is for the few
dozen terms where a wrong or inconsistent choice confuses users.

Writing the glossary also surfaces English strings that can't be translated well, such as sentences assembled from
fragments or plurals made by adding "s". Those get fixed in the English source, or filed as issues.

### 2. Per-language glossary

For each language, decide how every glossary term is rendered, from real usage rather than a model's best guess:

- **Image-editing terms** follow the localized UIs of Photoshop, GIMP and Krita, since users coming from those tools
  expect the same words.
- **Stable Diffusion terms** follow community localizations: the A1111 WebUI and ComfyUI localization packs,
  krita-ai-diffusion's translations, and tutorials written in the language. Often the right answer is to keep the
  English term or transliterate it.
- **Standard dialog and platform wording** follows Qt's own translations and the operating system's conventions.

Each term gets one decision: translate, transliterate or keep in English.

The per-language glossary is a table with these columns, explained in English for the maintainer:

| English term | Chosen rendering | Decision | Source | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |

- **Source** links to where the rendering was found. Links are the one part of the glossary a monolingual maintainer
  can verify: the page must exist and use the term. A claim without a source is marked low confidence.
- **Confidence** is high, medium or low, so the riskiest choices are easy to find.

A short style section follows the table: formality (for example, polite or plain forms), how buttons are phrased,
capitalization and punctuation conventions. An "open questions" list closes the file, as the first thing a future
native-speaking reviewer should check.

All descriptive text in a per-language glossary - the Notes column, the style section and the open questions list -
appears twice: first in the target language, then an English translation of it. A monolingual maintainer reads the
English text; native-speaking reviewers read the target-language text.

Per-language glossaries live beside the English glossary as `doc/translation/<language code>.md`.

### 3. Glossary review

A model from a different family than the one that wrote the glossary reviews it, following "Reviewing as a model"
with each glossary row as the unit under review. The reviewer also re-reads every Source link and reports a link that
is dead or doesn't use the term. Disagreements go to the open questions list, and low-confidence terms are
re-researched.

A native speaker with Stable Diffusion experience is the better reviewer whenever one is available.

### 4. Translation

Translate in batches, one PR per batch. Each batch is translated, reviewed (step 5) and checked (step 6) before the
next one starts, so a problem with the process shows up once instead of in every batch.

- **A batch is one UI area,** such as a panel, a menu or a group of related contexts, sized at about 100-200 strings
  or 1,500 words, so the glossary, the strings and the code that uses them fit in one session.
- **The first batch is a pilot** of about 100 strings drawn from across the catalog, reviewed closely. What it
  teaches goes into the per-language glossary's style section before the next batch.
- **Order batches by what users need first:** short labels shared across the UI, then the image generation UI, then
  the tools, layers, menus and dialogs. The config definition contexts go last, once conventions are settled.
- **The legacy GLID-3-XL contexts stay in English.**
- **Each batch is tracked as a GitHub issue,** and its PR closes it.

For each string:

- **Read the code that uses it.** A `.ts` location names the file only, so search that file for the source text.
  This is required for every string of two words or fewer, every option value and every string with placeholders:
  "Fill" or "Clear" can be a noun or a verb, and models get them wrong without seeing where they are used.
- **Use the glossary's rendering for every glossary term.** A term that needs a decision and isn't in the glossary
  goes into the English glossary and the per-language glossary in the same PR, before the strings that use it.
- **Keep the source's mechanics:** every `{name}` and `%1` placeholder, HTML tags, line breaks, and the `&`
  accelerator in the form the style section gives.
- **Flag a string instead of forcing it.** A string that can't be translated correctly as written (assembled from
  fragments, one English string with two meanings in one context, an English-only plural) stays untranslated. The fix
  goes to the English source in a separate PR, such as a `_tr` disambiguation or a rewording, or into an issue. The
  batch PR lists the flagged strings.

The first batch of a language adds its `languages.json` entry, with `"machine_translated": true`. Edit the `.ts` file
directly, then run `python scripts/build_translations.py` to normalize it and build its `.qm`
file. An entry is either translated and marked finished, or left empty. `lrelease` compiles unfinished translations
too, so a draft left in an unfinished entry ships.

The batch PR names the translating model and the reviewing model, lists the flagged strings, summarizes the review's
findings and how each was resolved, and names the UI sheets checked (step 6).

### 5. Batch review

A model from a different family than the translator reviews each batch, following "Reviewing as a model". It gets
the English and per-language glossaries, the batch's source strings with their translations, and the code that uses
them. It does not get the translator's notes or reasoning, so it judges the translation rather than the argument for
it.

The translator, or the agent running the batch, answers every finding:

- **Accepted** findings are fixed in the batch.
- **Rejected** findings get a one-line reason. A rejected meaning finding is settled by reading the code again with
  the reviewer's reason in hand. If it is still unclear, the string is flagged (step 4).
- **Glossary disagreements** go to the per-language glossary's open questions, and the glossary rendering stands
  until the question is decided.

The review table and the answers go in the batch PR, in a collapsed `<details>` section.

### Reviewing as a model

A review model reports specific problems rather than an overall verdict, since models asked whether something is good
tend to say yes. For every unit under review (a translated string, or a glossary row), it:

1. **Back-translates the translation into English without looking at the source,** then compares the two. A
   difference in meaning is a finding. Back-translations are the part of a review a monolingual maintainer can read.
2. **Checks it against each category below,** and reports every problem as a finding in one category.
3. **Writes one table row,** with the back-translation filled in for every unit, including those with no findings,
   so a missing check is visible.

| Category | A finding when |
| --- | --- |
| Meaning | The translation says something the source doesn't, or reads a noun as a verb, in the context of the code. |
| Glossary | A glossary term isn't rendered as the glossary says, or a term is rendered differently from earlier batches. |
| Mechanics | A placeholder, tag, line break or accelerator differs from the source, or punctuation, spacing or the accelerator form breaks the style section. |
| Register | The wording is unnatural, too literal, or in a different register than the style section asks for. |
| Length | A compact control (button, label, combo box item, column header) gets a translation much longer than the source. |

The table has these columns, with one row per unit and one finding per row (repeat the unit for a second finding):

| Context | Source | Translation | Back-translation | Category | Problem | Suggested fix | Confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |

Category, Problem and Suggested fix stay empty for a unit with no findings. Confidence is high, medium or low, and a
low-confidence finding says what would settle it.

### 6. Checks

Automated checks run on every translation file after every batch:

- placeholders, markup and keyboard accelerators match the source;
- glossary terms are used wherever the English term appears;
- no accelerator collisions within a menu;
- punctuation and spacing follow the language's style section, where a rule can be checked mechanically.

Then run `python scripts/capture_ui.py --sheet` in the language for the batch's panels and windows, and look for
clipped or overflowing text, which needs no knowledge of the language to spot. The batch PR names the sheets checked.

Once every batch is merged, a model from a different family than the translator makes a consistency pass over the
whole file, following "Reviewing as a model" for the Glossary category only, and lists every English string that has
more than one translation across contexts. Each one either has a context that explains the difference, or is unified.

## Maintenance

- **Translations are updated in batches before releases,** never as a requirement on ordinary PRs. A PR that adds or
  changes strings is not blocked by missing translations.
- **New terms go into the English glossary first,** then each language's glossary, before their strings are
  translated.
- **User reports are the main source of native-speaker review.** The README and the language picker say the language
  is machine-translated and how to report bad wording.

## Open questions

- Which models to use for translation and for review. Each batch PR records the models it used.
- Whether to use a hosted platform such as Weblate if volunteer translators appear.
