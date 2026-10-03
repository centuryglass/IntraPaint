# Color subsystem (A8)

**Question (open_questions.txt):** The color picker is a lightly-modified Qt dialog and there's no
foreground/background dual-color model that every other editor has. Design a color subsystem: a proper picker (RGB
cube / wheel / OKLab), the FG/BG dual-color model shared across tools, and how it plugs into the existing config/cache
color storage.

**Related issues:** #57 (better color picker), #58 (foreground and background colors), #59 (gradients, low priority,
consumes the FG/BG pair), #29 (per-entry config signals), #32 (widget creation out of Config), #33 (generated key
constants), #51 (sample merged for other tools), #24 (partial-alpha rendering).

**Substrate:** `_codebase_map.md`, `_decisions_ledger.md`, `config_system.md` (A4: keep config-as-data, per-entry Qt
signals, UI-free `Config`), `concurrency_model.md` (all config writes on the GUI thread), `responsive_layout.md` (the
picker must fit the space budget). Feeds OQ2 (`editor_norms.md`) through section 3, whose headings are stable for
citation.

**Scope:** the brush/tool color state, the picker widgets, the eyedropper, color alpha, and color-space handling on
import/export. The selection overlay color (`AppConfig.SELECTION_COLOR`) is UI chrome and stays outside the model.

**Verification:** written against `integration` at `41add94`. "Verified (ran)" marks behavior reproduced with headless
scripts in `.venv` (`QT_QPA_PLATFORM=offscreen`); "verified (read)" marks code read line by line; "inferred" marks
reasoning not checked against running code. Section 7 lists each.

---

## 1. Current state

### 1.1 Where colors are stored

All colors are `"type": "string"` config entries holding `#AARRGGBB` text. There is no color type in the config
schema; `Config.get_color(key, default)` (`src/config/config.py`) parses the string and falls back to the default.
Writers use `QColor.name(QColor.NameFormat.HexArgb)`, which emits lowercase. The JSON defaults for the shape colors are
uppercase (`#FF000000`), so the first `ColorButton` built on them rewrites the value in lowercase.

| Key | Owner | Default | Used for |
|---|---|---|---|
| `last_brush_color` | `Cache` | `#ff000000` | The one shared paint color: MyPaint brush, draw tool, fill tool, text color, eyedropper output |
| `shape_tool_line_color` | `Cache` | `#FF000000` | Shape tool outline |
| `shape_tool_fill_color` | `Cache` | `#FFFFFFFF` | Shape tool fill |
| `text_background_color` | `Cache` | `#ffffffff` | Text layer box fill |
| `new_image_background_color` | `Cache` | `#ffffffff` | Fill for File > New, and for the image created at launch (`AppController`) |
| `saved_colors` | `AppConfig` | `[]` | Custom palette swatches in the picker |
| `selection_color` | `AppConfig` | `#55ff0000` | Selection overlay (not paint) |

Color keybindings (`key_config_definitions.json`): `eyedropper_tool_key` (`C`) and `eyedropper_override_modifier`
(`Ctrl`, shared with `pan_view_modifier`). There is no swap, reset, or color-history key, and no recent-colors store.
The defaults `X` and `D` are taken by `text_tool_key` and `draw_tool_key`.

### 1.2 How each tool gets its color (verified, read)

| Tool | Source | Mechanism |
|---|---|---|
| MyPaint brush (`MyPaintBrushTool`) | `last_brush_color` | `cache.connect` -> `brush_color`; `MyPaintBrush.color` setter passes H, S, V only |
| Draw (`DrawTool` via `QtPaintBrushTool`) | `last_brush_color` | `color_key` argument; `QtPaintBrush.paint_segment` uses the full ARGB `QPen` |
| Eraser (`EraserTool`) | none | Disconnects `last_brush_color` in `__init__` |
| Fill (`FillTool`) | `last_brush_color` | `_update_color`; writes premultiplied ARGB straight into masked pixels |
| Text (`TextTool`, `TextToolPanel`, `TextRect`) | `last_brush_color` for glyphs, `text_background_color` for the box | Panel `ColorButton(parent=self)` defaults to `last_brush_color` |
| Shape (`ShapeTool`) | `shape_tool_line_color`, `shape_tool_fill_color` | Plus a hidden coupling: every `last_brush_color` change is copied into whichever of the two was edited last (see B3) |
| Smudge, clone stamp, filter | none | Color comes from the image |
| Selection brush/fill/shape | `selection_color` | Overlay only |

The `ColorButton` (`src/ui/widget/color_button.py`) on each tool panel edits one config key through `ColorDialog`.
Its `config_key` argument defaults to `'last_brush_color'`, so a call site that omits it silently edits the brush
color (see B1).

### 1.3 The picker widgets (verified, read)

`src/ui/widget/color_picker/` (about 1,700 lines) is a Python port of Qt5's internal `QColorDialog` pieces:
`HSBox` (a static `resources/hsv_square.png` with hue on x and saturation on y), `HsvValuePicker` (value bar),
`ComponentSpinboxPicker` (HSV and RGBA spinboxes plus an HTML field whose validator accepts only `#RRGGBB`/`#RGB`),
`StandardColorPaletteWidget` (Qt's 48 basic colors), `CustomColorPaletteWidget` (backed by `AppConfig.SAVED_COLORS`,
mirrored into `QColorDialog.setCustomColor`), and `ScreenColorWidget` (pick from anywhere on screen).
`TabbedColorPicker` arranges these four panels in one of five layouts. It is used in three places:

- `ColorDialog` (`src/ui/modal/color_dialog.py`), the modal opened by every `ColorButton`.
- `ColorControlPanel` (`src/ui/panel/color_panel.py`), bound to `last_brush_color`, docked as the tool panel's "Color"
  utility tab (`AppController`, four-tab mode).
- The eyedropper tool's control panel (`EyedropperTool.get_control_panel`), a second `ColorControlPanel`.

Every drag tick in the picker emits `color_selected`, and `ColorControlPanel._update_config_color` writes it to the
cache, so all listeners run per mouse move. There is no "committed" event that separates browsing from choosing.

### 1.4 Eyedropper (verified, ran)

`EyedropperTool.mouse_click` handles left press only. It calls `image_stack_color_at_point`
(`src/image/layers/image_stack_utils.py`), which reads one pixel of the merged composite, and writes the result to
`last_brush_color` with its alpha. Ctrl held in the brush, draw, fill, shape or text tool delegates to it
(`ToolController.__init__`, `register_tool_delegate`). Observed:

- A fully transparent pixel yields `#00000000`, so the brush color becomes invisible.
- A point outside all content yields opaque black.
- A point outside the canvas but inside layer content to the right of or below the canvas yields opaque black (B2).
- No drag sampling, no sample size, no current-layer mode, no way to set a second color.

### 1.5 Alpha (verified, ran and read)

Colors carry alpha end to end, and the picker exposes an alpha spinbox, but tools treat it inconsistently:

- Draw tool: color alpha multiplies with the tool's own opacity setting (`QtPaintBrush`).
- MyPaint brush: alpha is dropped. `MyPaintBrush.color` sets only `COLOR_H/S/V`; `OPAQUE` stays 1.0 for a color with
  alpha 64 (ran).
- Fill tool: writes the color, alpha included, over the masked pixels with no compositing, so a translucent fill
  replaces opaque content with translucent pixels.
- Shape tool: `QPen`/`QBrush` honor alpha and composite normally.

### 1.6 Color space and profiles (verified, ran)

- **Working space:** 8-bit `Format_ARGB32_Premultiplied` everywhere, interpreted as sRGB without saying so.
- **Blending is in gamma-encoded sRGB.** `QPainter` composites 50% white over black to 128 (ran). The bundled
  `lib/libmypaint.so` exports `mypaint_brush_stroke_to` as a wrapper that hard-codes `viewzoom=1`, `viewrotation=0`,
  `barrel_rotation=0` and `linear=0` before calling `mypaint_brush_stroke_to_internal` (read from the disassembly).
  So MyPaint strokes also blend non-linearly, and the four trailing arguments IntraPaint passes
  (`mypaint_layer_surface.py`, `mypaint_scene_surface.py`, including the `c_int(1)` the argtypes comment in
  `libmypaint.py` labels `is_linear`) are ignored. The two engines agree, which is what keeps brush and draw tool
  output consistent.
- **ICC profiles are ignored.** `load_image` (`src/util/visual/image_format_utils.py`) returns the embedded
  `icc_profile` in the metadata dict but `pil_image_to_qimage` copies raw pixel values, and neither `save_image` nor
  `save_image_with_metadata` writes a profile back (ran with a PNG tagged with an sRGB profile: the profile is gone
  after a round trip). A Display P3 or Adobe RGB image is edited as if its numbers were sRGB, and saved untagged.
- **Existing color math:** `src/util/visual/image_fill.py` already implements sRGB -> linear -> XYZ -> CIELAB in Cython
  for the fill threshold. There is no OKLab code.

---

## 2. Bugs found

Filed as #81 (B1-B3), #82 (B4 and the argtypes note) and #83 (B5).

- **B1 - Opening File > New overwrites the brush color (verified, ran).** `NewImageModal.__init__` builds
  `ColorButton(parent=self)`, which binds to `last_brush_color`, then assigns `self._color_button.color =
  self._color`; the setter writes that color to the cache. Opening the dialog and cancelling turns the brush color
  into the last new-image background color. Picking a custom background color also changes the brush color. Fix:
  `ColorButton(config_key=None, ...)`, and make `ColorButton.select_color` call `_update_color(selection)` in the
  unbound branch so the icon refreshes.
- **B2 - Off-canvas sampling returns black right of and below the canvas (verified, ran).**
  `image_stack_color_at_point` tests `content_bounds.contains(adjusted_point)`, mixing image coordinates with
  composite-local ones. With content at (-100, -100, 300x300) over a 100x100 canvas, (-50, -50) samples correctly and
  (150, 150) returns `#ff000000`. Fix: test `content_bounds.contains(image_point)`.
- **B3 - The shape tool's colors follow the brush color while the shape tool is inactive (verified, ran).**
  `ShapeTool.__init__` connects `_update_last_color` to `last_brush_color` unconditionally, though the comment above
  it says "When the tool is active". Picking a color for the brush changes the next shape's fill. Section 4.2 removes
  the coupling; a same-pass fix is an `is_active` guard.
- **B4 - The MyPaint brush ignores color alpha (verified, ran).** See 1.5. The draw tool and the brush give different
  results for the same color. Needs a design call (section 6, M4), so it belongs in an issue.
- **B5 - Embedded ICC profiles are ignored on load and dropped on save (verified, ran).** See 1.6. Low priority; the
  fix in 4.6 uses Pillow's bundled `ImageCms` and adds no dependency.
- **Doc fix - `libmypaint.py` `stroke_to` argtypes.** The declaration lists 12 arguments and labels the last one
  `is_linear`; the bundled Linux library's `mypaint_brush_stroke_to` takes 8 and ignores the rest. Harmless under the
  x86-64 and Win64 calling conventions (the caller cleans up). The Windows DLL (`libmypaint-1-4-0.dll`) was not
  checked.

---

## 3. How IntraPaint differs from GIMP, Krita and Photoshop

Each heading is a stable anchor for `editor_norms.md`.

### D1 - No foreground/background color pair
GIMP, Krita and Photoshop keep two colors shared by every tool, shown as overlapping swatches in the toolbox. IntraPaint
has one shared color (`last_brush_color`) plus four tool-private colors (shape line, shape fill, text background, new
image background), each edited through its own button and dialog.

### D2 - No swap or reset shortcut, and the conventional keys are taken
The common bindings are X (swap) and D (reset to black/white). IntraPaint has neither action; X is the text tool and D
the draw tool.

### D3 - The picker is a port of Qt's generic dialog
GIMP (wheel, LCh and scales), Krita (advanced selector, wheel, HSY'), and Photoshop (HSB square with Lab fields) all
offer a hue wheel or ring and at least one perceptual mode. IntraPaint offers the `QColorDialog` HSV square, a value
bar, spinboxes and Qt's basic palette. There is no hue ring, no perceptual mode, and no recent-colors history. The hex
field rejects 8-digit `#AARRGGBB` input although colors carry alpha.

### D4 - Colors carry alpha, applied inconsistently
In GIMP and Photoshop the FG/BG colors are opaque, and transparency comes from tool opacity or the layer. IntraPaint
colors carry alpha that the draw tool multiplies with its own opacity, the MyPaint brush ignores, and the fill tool
writes without compositing.

### D5 - The eyedropper samples one merged pixel and sets one color
The others offer a sample size (point, 3x3, 5x5 average), a current-layer versus merged choice, a modifier or second
button to set the background color, and live sampling while dragging. IntraPaint samples one pixel of the merged image
on press, copies its alpha (a transparent pixel makes the brush invisible), and can only set the brush color.

### D6 - Bucket fill replaces pixels without compositing
GIMP and Photoshop composite the fill in the tool's blend mode and opacity. `FillTool.mouse_click` assigns the color to
the masked pixels, so a translucent fill punches translucency into opaque content.

### D7 - Shape colors are tool-private with a hidden link to the brush color
Krita strokes shapes with the foreground color and fills them with a chosen source (foreground, background, pattern).
IntraPaint keeps separate line and fill colors and copies brush color changes into whichever was edited last (B3).

### D8 - No color management
GIMP and Krita convert embedded profiles on import (Krita can also work in other spaces), and Photoshop at least
preserves them. IntraPaint ignores embedded profiles and saves untagged. Gamma-space blending matches Photoshop's
default and GIMP's "perceptual" legacy mode, so it is not a departure in itself.

---

## 4. Recommended design

### 4.1 The FG/BG model

**Storage stays in `Cache` as `#aarrggbb` strings.** This fits A4's config-as-data direction and needs no schema type.

- **Foreground = the existing `last_brush_color` key.** Keep the key name so saved caches, the 16 `LAST_BRUSH_COLOR`
  call sites and `test/resources/cache_test.json` keep working; change its label to "Foreground color" and its
  description to say it is the foreground color. The key name becomes a permanent alias, which earns a one-line
  comment where the key is defined. Renaming it would need a cache migration hook that `Config` does not have, and
  #33's generated constants make a later rename cheap if wanted.
- **Background = a new `Cache` key `background_color`**, default `#ffffffff`, `saved: true`. No migration: absent
  from old cache files, it loads its default.
- **Recent colors = a new `Cache` key `recent_colors`**, a list capped at 16, most recent first, deduplicated.
- **Canonical form.** Add `Config.set_color(key, color)` beside `get_color`, writing
  `color.name(QColor.NameFormat.HexArgb)`. Every color write goes through it. `Config.set` stops notifying the
  remaining callbacks when one of them changes the value (the `self.get(key, inner_key) != value` check), so a mixed
  `#FF...`/`#ff...` write currently causes a second notification round; one canonical form avoids it.
- **Operations live in a small `src/controller/color_controller.py`** (functions, not a new singleton):
  `foreground()`, `background()`, `set_foreground(color, commit=True)`, `set_background(...)`, `swap()`, `reset()`
  (black/white), and `commit(color)`, which pushes to `recent_colors`. They write through `Cache`, so listeners keep
  using `Cache().connect(...)` today and the per-entry signals once #29 lands. Nothing in the design waits on #29.
  This also keeps color logic out of `AppController` (#38).
- **Commit versus browse.** Picker drags update the foreground live, as now, but only a commit (mouse release in the
  picker, a swatch click, an eyedropper pick, Enter in the hex field) pushes to recent colors. `TabbedColorPicker`
  needs a `color_committed` signal for this.
- **Swap emits two writes.** Listeners briefly see FG equal to BG. No current listener acts on that state; a swap that
  must be atomic waits for #29's signals and a batched emit.
- **Threading.** All writes come from GUI events, so they already meet the main-thread-only rule (A5, #28).

**`ColorPairWidget`** (`src/ui/widget/color_pair_widget.py`): two overlapping swatches with swap and reset icons and
tooltips naming the bound keys. Clicking a swatch opens the picker on that color. It heads the Color utility tab and
replaces the brush-color `ColorButton` on the brush, draw, fill and MyPaint panels. User-visible strings go through
`_tr` with single-quoted literals.

### 4.2 Tool integration

| Tool | Foreground | Background | Change |
|---|---|---|---|
| MyPaint brush, draw, fill | Paint color | - | None; already on `last_brush_color` |
| Text | Glyph color | - | None; the box fill stays `text_background_color`, a per-layer property, with a "use background color" button |
| Shape | Line color when the line source is foreground | Fill color when the fill source is background | New `Cache` keys `shape_tool_line_source` (`foreground`/`custom`) and `shape_tool_fill_source` (`background`/`foreground`/`custom`); the existing color keys become the custom values; delete the `_update_last_color` coupling |
| New image | - | New "background color" dropdown option | Fix B1 first |
| Eraser, smudge, stamp, filter, selection tools | - | - | None |
| Gradient (#59, future) | Start | End | Default endpoints |

Shape defaults (line from foreground, fill from background) reproduce today's black-outline, white-fill defaults with
fresh settings. Existing users with custom shape colors land on the source defaults and lose them unless the first
load sets the sources to `custom` when the stored colors differ from the old defaults; section 6 lists this as M3.

### 4.3 The picker

**Recommendation: an OKHSV hue ring with an OKHSV saturation/value square inside it**, as the default panel of a
rewritten `TabbedColorPicker` with horizontal icon tabs (#57):

1. **Ring + square** (default): hue ring around an OKHSV square, plus an alpha slider.
2. **Sliders:** RGB, HSV and OKLCH channel sliders with gradient tracks, and a hex field that accepts `#RRGGBB` and
   `#AARRGGBB`.
3. **Palettes:** the saved palette (`saved_colors`), the recent-colors strip, and the screen color picker.

Reasons:

- **OKHSV over a raw OKLab/OKLCH plane.** OKHSV (Ottosson, 2021) is built on OKLab, so hue steps and lightness look
  even, but it maps the sRGB gamut onto a full square. A raw OKLCH plane at hue 30 degrees is only 33% inside sRGB
  (ran), so most of the square would need clipping or masking. Every OKHSV pixel is a real color.
- **Ring + square over an RGB cube.** A 3D cube needs a projection or slicing UI and is uncommon in painting tools.
  The ring + square is what Krita, GIMP and MyPaint users expect. The cube gets no tab.
- **Fits the layout budget.** One square widget that scales with width (`heightForWidth`) replaces the five layout
  modes and the window-size checks in `ColorControlPanel.set_orientation`, which helps `responsive_layout.md` P2.
- **No new dependency.** The conversions are short closed-form numpy code. A vectorized OKLab -> sRGB render of a
  256x256 plane takes about 6 ms in `.venv` (ran); OKHSV adds a cusp lookup per hue, so a square re-render on hue
  change stays well under a frame (inferred). Put the math in `src/util/visual/color_math.py`: pure functions for
  sRGB <-> linear <-> OKLab <-> OKLCH <-> OKHSV, scalar and array forms. The OKHSV reference implementation
  (`ok_color.h`) is MIT-licensed; a port keeps its copyright notice (M5).
- **Reuse the screen picker.** `ScreenColorWidget` and its Windows workaround are the part of the port worth keeping.

The old `HSBox`, `HsvValuePicker`, `ComponentSpinboxPicker` and `StandardColorPaletteWidget` are deleted once the new
tabs ship, with `resources/hsv_square.png`.

### 4.4 Eyedropper

- Left click or drag sets the foreground; right click or drag sets the background. Right-click is IntraPaint's
  secondary action elsewhere (brush 1px, shape tool), and the Ctrl delegate passes either button through.
- Live sampling while dragging, with the sampled color previewed in the color panel; commit on release.
- Options in the eyedropper panel (new `Cache` keys): sample size (`1`, `3x3`, `5x5`, averaged in premultiplied space
  then unpremultiplied), and sample merged versus current layer, reusing `Cache.SAMPLE_MERGED` per #51.
- Alpha: sampling returns the unpremultiplied RGB with alpha 255 by default; a fully transparent sample leaves the
  color unchanged. A "sample alpha" checkbox keeps today's behavior (M2).
- The eyedropper's control panel becomes the `ColorPairWidget` plus these options, not a second full picker.
- Fix B2 first.

### 4.5 Alpha policy

Keep alpha in stored colors: the shape, text background, new-image and selection colors need it, and dropping it would
need a migration. Make tools agree:

- The MyPaint brush applies color alpha by scaling its opacity for the stroke (B4, M4). Which brush setting to scale
  must be checked against brushes with pressure-driven opacity; this part is inferred.
- The fill tool composites with `CompositionMode_SourceOver` through the mask (fixes D6). With an opaque color the
  result matches today's, so existing fill tests keep passing (inferred).
- The picker keeps the alpha slider. The `ColorPairWidget` draws swatches over a checkerboard so a translucent FG is
  visible.

### 4.6 Color management

Keep 8-bit sRGB as the working space and gamma-space blending. Stable Diffusion models consume sRGB-encoded pixels,
all goldens assume it, and linear blending would change every brush result. Fix only D8's import side:

- On load, when the embedded profile is not sRGB, convert to sRGB with `PIL.ImageCms` (bundled with the pinned
  Pillow; imported and used in `.venv` while verifying this report) and log the conversion. On failure, keep raw
  pixels and log a warning.
- On save, write untagged sRGB, as now. Untagged images are read as sRGB by convention.
- No display-profile handling, no other working spaces.

### 4.7 Keybindings

New `KeyConfig` entries under "Edit Menu": `swap_colors_shortcut` default `Shift+X`, `reset_colors_shortcut` default
`Shift+D` (both unbound today). Register them with `@menu_action` in a small Edit-menu block that calls
`color_controller.swap`/`reset`. Moving the text and draw tools off X and D to free the conventional keys is M1.

---

## 5. Phased plan

Each phase is one PR, tested headlessly, with no modal dialogs opened in tests (conftest fails them; mock
`ColorDialog.show_color_dialog`).

**P0 - Bug fixes (small, independent).** B1, B2, B3 guard, the `libmypaint.py` comment.
Tests: `NewImageModal` construct + cancel leaves `last_brush_color` unchanged; `image_stack_color_at_point` at points
left/above and right/below the canvas inside content (the second currently returns black); toggling
`last_brush_color` with an inactive `ShapeTool` leaves `shape_tool_fill_color` unchanged.

**P1 - Color math.** `src/util/visual/color_math.py`, no UI.
Tests: round trips sRGB -> OKLab -> sRGB within 1/255 over a grid; published OKLab reference values (white, black,
primaries); every OKHSV square pixel in gamut for a sweep of hues; array and scalar paths agree.

**P2 - FG/BG model.** `background_color`, `recent_colors`, `Config.set_color`, `color_controller`, swap/reset menu
actions and keys, `ColorPairWidget` on the color tab and brush/draw/fill/MyPaint panels.
Tests: swap and reset write the expected canonical strings; recent colors dedupe and cap at 16; old cache files without
the new keys load defaults; `ColorPairWidget` click calls the mocked dialog with the right color and writes the right
key; a `ToolTestCase` draw stroke after `swap()` paints the old background color (pixel assertion, no golden).

**P3 - Eyedropper.** Right-button background, drag sampling, sample size, current layer versus merged, alpha policy,
slim panel.
Tests (`ToolTestCase`): left and right clicks set FG and BG; a 3x3 average on a known checker; current-layer sampling
ignores a covering layer; a transparent sample leaves the color unchanged; Ctrl-delegate right click from the draw tool
sets BG.

**P4 - Picker rewrite.** Ring + square, sliders, palettes, icon tabs, `color_committed`; delete the ported Qt
widgets.
Tests: setting a color then reading `selected_color()` round-trips; simulated presses on the ring and square land on
the expected OKHSV values; drags do not push recent colors and release does; the hex field accepts `#AARRGGBB`; the
panel's `minimumSizeHint` fits the responsive-layout budget once that test exists.

**P5 - Tool consistency.** Shape line/fill sources, new-image "background color" option, text "use background color",
fill-tool compositing, MyPaint alpha.
Tests: shape goldens with each source; fill with a translucent color over opaque content composites (pixel
assertion); MyPaint stroke with alpha 128 is lighter than with 255 over white (pixel comparison, not exact values).

**P6 - Import color management (independent).** Convert non-sRGB profiles on load.
Tests: a fixture PNG tagged with a non-sRGB profile built by `ImageCms` loads with converted pixels; an sRGB-tagged and
an untagged image load unchanged.

Order: P0 any time; P1 before P4; P2 before P3 and P5. P2 and P3 deliver issue #58; P4 delivers #57. P6 stands alone.

---

## 6. Decisions for the maintainer

- **M1 - Swap/reset keys.** Ship `Shift+X`/`Shift+D` (no conflicts), or move the text tool off X and the draw tool off
  D to use the conventional keys. The second changes muscle memory for the maintainer's own workflow, so this report
  recommends the first.
- **M2 - Eyedropper alpha.** Default to opaque sampling (convention, avoids the invisible-brush trap) with a "sample
  alpha" option, or keep today's behavior as the default.
- **M3 - Shape color migration.** Whether first load after P5 sets the shape sources to `custom` for users whose saved
  shape colors differ from the old defaults.
- **M4 - MyPaint alpha.** Apply color alpha to the MyPaint brush (consistent with the draw tool), or hide alpha for
  paint colors and keep it only for shape, text and background colors.
- **M5 - Porting MIT-licensed OKHSV code.** No package is added, but ported code carries Ottosson's MIT notice. Confirm
  that is acceptable under the dependency policy.
- **Audience tension (per AGENTS.md "Who it serves"):** P2-P4 change the color panel the maintainer uses every
  session. The ring + square and FG/BG pair are the convention other users and reviewers expect; the maintainer
  should try P4 before the old widgets are deleted.

---

## 7. What was verified

- **Ran:** B1 through B5; transparent and out-of-content eyedropper results; `QPainter` gamma-space blending; ICC
  profile dropped on PNG round trip and present in JPEG load metadata; OKLab plane render time and gamut coverage;
  free default key combinations.
- **Read:** every file in `src/ui/widget/color_picker/`, `ColorButton`, `ColorDialog`, `ColorControlPanel`,
  `NewImageModal`, the eyedropper, fill, shape, text, eraser, MyPaint and draw tool color paths, `Config.get_color` and
  `Config.set`, the config definition files, `image_format_utils` load/save; disassembly of
  `mypaint_brush_stroke_to` in `lib/libmypaint.so`.
- **Inferred:** OKHSV square render cost, fill-tool compositing preserving opaque-fill results, which MyPaint setting
  to scale for alpha, the Windows libmypaint DLL's argument handling, and the GIMP/Krita/Photoshop behavior in
  section 3 (from product knowledge, not checked against current releases).

## 8. Cross-references

- `config_system.md`: the model uses existing `Cache` string keys and gains from #29 (signals) and #33 (constants)
  without waiting for them. `Config.set_color` is a data helper and stays UI-free per #32.
- `responsive_layout.md`: the picker rewrite drops `ColorControlPanel`'s window-size layout switching.
- `rendering_pipeline.md` R2 / #24: fill-tool compositing (4.5) touches the same partial-alpha paths; test with #24's
  repro once it exists.
- `testing_strategy.md`: all tests above use `IntraPaintTestCase` or `ToolTestCase`.
