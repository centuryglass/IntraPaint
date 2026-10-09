# Bundled fonts

The IntraPaint Ink theme (`resources/themes/intrapaint_ink.json`) sets IBM Plex Sans as the interface font, so text
metrics don't depend on the fonts a platform happens to have installed. IBM Plex Math, then Noto Sans Math, supply the
key and arrow symbols IBM Plex Sans lacks, such as the ⇧ and ⌃ in key hints. A symbol none of them has falls back to a
system font, whose width differs between platforms.

| File | Source | Version |
|---|---|---|
| `IBMPlexSans-Regular.ttf`, `IBMPlexSans-Medium.ttf`, `IBMPlexSans-SemiBold.ttf` | [IBM/plex](https://github.com/IBM/plex), `packages/plex-sans/fonts/complete/ttf/` | 3.005 |
| `IBMPlexMath-Regular.ttf` | [IBM/plex](https://github.com/IBM/plex), `packages/plex-math/fonts/complete/ttf/` | 1.000 |
| `NotoSansMath-Regular.ttf` | [notofonts](https://github.com/notofonts/notofonts.github.io), `fonts/NotoSansMath/unhinted/ttf/` | 3.000 |

- All are licensed under the SIL Open Font License 1.1: the IBM Plex files under `OFL.txt`, and Noto Sans Math under
  `OFL-Noto.txt`. "Plex" is a Reserved Font Name, so a modified copy of the IBM Plex files can't keep that name.
- Replace the IBM Plex files only with IBM's own builds. The Google Fonts build of IBM Plex Sans strips the optional
  OpenType features, including the slashed zero (`zero`) the theme turns on.
