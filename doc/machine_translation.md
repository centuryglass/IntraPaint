# Machine translation process (draft)

**Status: work in progress.** This is a first outline, written before any translation has been attempted. Expect it
to change once a pilot language has been through it.

How IntraPaint gets AI-generated translations of its UI when the maintainer speaks only English and no native-speaking
reviewer is available. The process aims for translations that are useful to people who don't read English well,
without needing a professional localization budget. It assumes the catalog workflow in #332 is in place.

## When a language is worth shipping

A machine translation ships only when all of these hold. Without them, the language is left out and users get English.

- **English is one click away.** The language picker labels the language as machine-translated, and a user can switch
  back to English at any time.
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

A model from a different family than the one that wrote the glossary reviews it. Ask for specific problems
(wrong term, unnatural term, term the community doesn't use, inconsistency) rather than an overall verdict, since
models asked whether something is good tend to say yes. Disagreements go to the open questions list, and low-confidence
terms are re-researched.

A native speaker with Stable Diffusion experience is the better reviewer whenever one is available.

### 4. Translation

Translate file by file, with the per-language glossary and the code that uses each string in context. Short strings
need context most: "Fill" or "Clear" can be a noun or a verb, and models get them wrong without seeing where they are
used. Strings that can't be translated correctly as written are flagged back to the English source, not forced.

### 5. Checks

Automated checks run on every translation file:

- placeholders, `%n`, markup and keyboard accelerators match the source;
- plural forms are complete for the language;
- glossary terms are used wherever the English term appears;
- no accelerator collisions within a menu.

Then a consistency pass against the glossary, by a different model family than the translator. Finally, run
`python scripts/capture_ui.py --sheet` in the language and look for clipped or overflowing text, which needs no
knowledge of the language to spot.

## Maintenance

- **Translations are updated in batches before releases,** never as a requirement on ordinary PRs. A PR that adds or
  changes strings is not blocked by missing translations.
- **New terms go into the English glossary first,** then each language's glossary, before their strings are
  translated.
- **User reports are the main source of native-speaker review.** The README and the language picker say the language
  is machine-translated and how to report bad wording.

## Open questions

- Where the language picker lives, and how it labels machine-translated languages. IntraPaint currently loads every
  `.qm` file it finds and has no way to choose a language.
- Which models to use for translation and for review, and whether to record the model in the glossary.
- Whether to use a hosted platform such as Weblate if volunteer translators appear.
