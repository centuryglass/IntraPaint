# Bundled fonts

The IntraPaint Ink theme (`resources/themes/intrapaint_ink.json`) sets IBM Plex Sans as the interface font, so text
metrics don't depend on the fonts a platform happens to have installed.

| File | Source | Version |
|---|---|---|
| `IBMPlexSans-Regular.ttf`, `IBMPlexSans-Medium.ttf`, `IBMPlexSans-SemiBold.ttf` | [IBM/plex](https://github.com/IBM/plex), `packages/plex-sans/fonts/complete/ttf/` | 3.005 |

- Licensed under the SIL Open Font License 1.1 (`OFL.txt`). "Plex" is a Reserved Font Name, so a modified copy of these
  files can't keep that name.
- Replace these only with IBM's own builds. The Google Fonts build of IBM Plex Sans strips the optional OpenType
  features, including the slashed zero (`zero`) the theme turns on.
