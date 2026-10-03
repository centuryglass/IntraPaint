# Editor convention departures (OQ2)

**Question (`open_questions.txt`):** IntraPaint has idiosyncrasies that put off people who use established image
editors. Identify them, say whether and how IntraPaint should adapt to the norms, and sketch an implementation plan
for each.

**Inputs:** `responsive_layout.md` (OQ1), `generation_area_ux.md` (OQ6), `color_subsystem.md` (A8),
`architecture_review.md` §4 (OQ7). This report cites them and does not repeat their designs.

**Scope:** user-facing behavior: shortcuts, mouse gestures, selection, files, clipboard, color, layout. The code-level
deviations in `architecture_review.md` §4 (singletons, dynamic config attributes, home-grown signal plumbing) are
invisible to users and stay there.

**Method:**
- The reference editors are Photoshop, GIMP and Krita. A behavior counts as a norm when all three agree on it, or
  when two agree and the third offers it as an option. Where they disagree there is no norm, and IntraPaint's choice
  stands unless it collides with something else.
- IntraPaint behavior is verified from source and from the defaults in `resources/config/*.json`, and cited by path
  and symbol. Nothing here was checked by running the GUI; claims marked `[inferred]` come from reading code.
- Claims about the reference editors are from general knowledge of their default keymaps, not checked in this
  session. Verify a specific shortcut before relying on it in an implementation.

**Constraint:** "Who it serves" in `AGENTS.md` puts the maintainer's inpainting workflow first. A norm that would slow
generate-compare-inpaint is added as an option or an extra binding, not swapped in as the default. Each such case is
marked **Tension** below for the maintainer to decide.

---

## 1. Summary

| # | Departure | Verdict | Cost | Section |
|---|---|---|---|---|
| N1 | Closing the window discards unsaved work with no prompt; Quit always prompts | **Fix** (bug) | S | 2.1 |
| N2 | No dirty tracking: no title marker, no "Save changes?" choice | **Adopt** | S-M | 2.1 |
| N3 | Ctrl+S onto PNG/JPEG flattens layers, warns after writing | **Adopt** (warn before) | S | 2.2 |
| N4 | No recent files, no drag-and-drop open | **Adopt** | S | 2.3 |
| N5 | Copy and paste never touch the system clipboard | **Adopt** | M | 2.4 |
| N6 | Zoom on PgUp/PgDn, no 100% or fit-to-window shortcut | **Adopt** (add bindings) | S | 2.5 |
| N7 | Pan is Ctrl+drag, which also triggers the eyedropper; Space does nothing | **Adopt** Space-pan; **Tension** on Ctrl | S | 2.6 |
| N8 | Save As is Ctrl+Alt+S | **Adopt** Ctrl+Shift+S | XS | 2.7 |
| N9 | Tool letters differ from every reference editor | **Keep**, add a preset later | - / M | 2.8 |
| N10 | Selection tools only add; subtract is per-tool (right-click or `Q`) | **Adopt** Shift/Alt modifiers; **Tension** on replace | M | 2.9 |
| N11 | Painting ignores the selection unless a per-tool box is checked | **Keep** | - | 2.10 |
| N12 | Per-tool colors, no FG/BG pair, no swap/reset keys | **Adopt** per A8 | per A8 | 2.11 |
| N13 | Keybindings are entered by typing key names | **Adopt** a key-capture field | S | 2.12 |
| N14 | No undo history panel; undo merges by time | **Defer** | - | 2.13 |
| N15 | Window fills the screen, no saved geometry, fixed 10pt font | per OQ1 | per OQ1 | 2.14 |
| N16 | Generation-area gizmo: no handles, left-click teleports | per OQ6 (#41) | per OQ6 | 2.15 |
| N17 | Panels are custom tab boxes, not dockable/floatable windows | per #55 | L | 2.16 |

Recommended order: N1 → N3 → N8 → N6/N7 → N4 → N13 → N5 → N10 → N12. The first five are small, independent, and
remove the failures an editor user hits in their first session. N12 is the largest and has its own report.

---

## 2. Departures

### 2.1 Unsaved changes (N1, N2)

**What IntraPaint does.**
- `MainWindow.closeEvent` (`src/ui/window/main_window.py`) calls `QApplication.exit()` with no check. Closing the
  window from the title bar, the taskbar or the OS discards all work silently.
- `AppController.quit` (`src/controller/app_controller.py`) asks for confirmation every time, then calls
  `self._window.close()`. Only Ctrl+Q and the menu reach it.
- Nothing tracks whether the image changed since the last save. `CONFIRM_QUIT_MESSAGE`,
  `NEW_IMAGE_CONFIRMATION_MESSAGE` and `RELOAD_CONFIRMATION_MESSAGE` say "unsaved changes will be lost" whether or not
  there are any. The main window never sets a title, so neither the file name nor a modified marker is shown.

**Norm.** All three editors track a modified state, mark it in the title (`*` or similar), prompt only when it is
set, and offer Save / Discard / Cancel. Closing the window and choosing Quit run the same check.

**Recommendation.** Fix N1 now (#80): it loses work. Then add a dirty flag.

**Sketch.**
1. Route `closeEvent` through `AppController.quit`: emit a signal or call a controller hook, and `event.ignore()`
   when the user cancels. Keep the `skip_confirmation` path for programmatic exits. Tracked in
   #80.
2. Dirty state: record the `UndoStack` position (count of actions, or the identity of the top action) at load and
   after each save. The image is modified when the current position differs. This needs one accessor on
   `UndoStack` and no per-edit bookkeeping. Undoing back to the saved point clears the flag, as in the reference
   editors.
3. Title: `"<file name>[*] - IntraPaint"` via `setWindowFilePath` + `setWindowModified`, which also gives the macOS
   proxy icon for free.
4. Replace the three unconditional confirmations with one helper: skip the prompt when clean, and offer Save /
   Discard / Cancel when dirty. Save failing or being cancelled aborts the close.
5. Tests: dirty flag after edit, undo to saved point, save; `closeEvent` ignored on cancel (mock the dialog, per
   `conftest.py`'s modal rule).

### 2.2 Saving to a flat format (N3)

**What IntraPaint does.** Save (Ctrl+S) writes back to the loaded path in its own format. When that is PNG or JPEG
and the image has several layers, the file is written flattened, then `LAYERS_NOT_SAVED_TITLE` /
`LAYERS_NOT_SAVED_MESSAGE` tell the user after the fact. The same after-the-fact pattern covers alpha, metadata and
write-only formats.

**Norm.** GIMP separates Save (native format) from Export. Photoshop and Krita warn before a save loses layers and
let the user cancel or pick the native format.

**Recommendation.** Warn before writing, not after, with "Save as .ora" / "Flatten and save" / "Cancel" and a
"don't ask again" box tied to the existing alert settings. Do not add a GIMP-style Save/Export split: the maintainer
saves generated work to PNG for its embedded generation metadata, and a split would add a step to that loop.
**Tension:** only the maintainer knows how often they Ctrl+S a layered image onto a PNG; if the answer is "on
purpose, constantly", default the new prompt's "don't ask again" to checked.

**Sketch.** Move the existing format checks in the save path ahead of the write, collect every loss (layers, alpha,
metadata, size, color) into one dialog instead of up to five sequential ones, and keep the existing alert keys.

### 2.3 Recent files and drag-and-drop (N4)

**What IntraPaint does.** No recent-files list. The main window accepts no file drops (`setAcceptDrops` appears only
in `src/ui/layout/draggable_tabs/tab_bar.py`).

**Norm.** All three have File → Open Recent and open a dropped file; dropping onto an open image adds it as a layer
in Photoshop and Krita.

**Sketch.**
- A `Cache` list `recent_files` (definition in `cache_value_definitions.json`), updated on load and save, shown as a
  File submenu built in `AppController`'s menu setup.
- `dragEnterEvent`/`dropEvent` on the image panel: no image open → `load_image`; image open → the existing
  "Open as layers" path. Both are already undoable.

### 2.4 Clipboard (N5)

**What IntraPaint does.** `ImageStack.copy_selected` and `cut_selected` store into `ImageStack._copy_buffer`, and
`ImageStack.paste` reads only that buffer. Images copied in IntraPaint cannot be pasted into another program, and a
screenshot or a browser image cannot be pasted into IntraPaint. Text fields use the system clipboard
(`src/util/active_text_field_tracker.py`).

**Norm.** All three exchange images with the system clipboard in both directions.

**Recommendation.** Use the system clipboard, keeping the internal buffer for the layer transform.

**Sketch.**
1. On copy/cut, also `QApplication.clipboard().setImage(...)` with the cropped image. Keep `_copy_buffer` and
   `_copy_buffer_transform` so an internal paste still lands in place.
2. On paste, compare the clipboard image with the last one IntraPaint wrote (keep its `cacheKey()` or a hash). If it
   is IntraPaint's own, paste from the internal buffer with its transform. Otherwise paste the clipboard image as a
   new layer centered in the view, or at the generation area if one is shown.
3. Large images: `setImage` copies the pixels; that is acceptable for selections, and whole-layer copies are the
   same cost as a save. No dependency needed.
4. Tests use `QApplication.clipboard()` under the offscreen platform `[inferred: offscreen supports an in-process
   clipboard; confirm before relying on it in CI]`.

### 2.5 Zoom shortcuts (N6)

**What IntraPaint does.** `zoom_in`/`zoom_out` default to PgUp/PgDn; `zoom_toggle` (Shift+Z) switches between the
full image and the generation area. No binding sets 100% or fit-to-window. Ctrl+= and Ctrl+- are taken by
grow/shrink selection, and Ctrl+1 through Ctrl+7 by the filters.

**Norm.** Ctrl+= / Ctrl+- zoom in all three (GIMP and Krita also take bare `+`/`-`). Each has a 100% key and a
fit key, though the keys differ (Photoshop Ctrl+1 / Ctrl+0; GIMP `1` / Shift+Ctrl+J).

**Recommendation.** Keep PgUp/PgDn and add norm bindings next to them. `KeyConfig` already accepts several keys per
action (comma-separated).

**Sketch.**
- `zoom_in`: `PgUp,Ctrl+=,+`; `zoom_out`: `PgDown,Ctrl+-,-`. Move grow/shrink selection to `Ctrl+Alt+=` /
  `Ctrl+Alt+-` (no reference editor binds them by default). **Tension:** the maintainer may use Ctrl+=/Ctrl+- for
  selection growth.
- New actions `zoom_actual_size` (default `Ctrl+Alt+0`, avoiding Ctrl+1's filter) and `zoom_fit` (`Ctrl+0`), backed
  by `ImageGraphicsView.scene_scale = 1.0` and the existing reset path used by `zoom_toggle`.

### 2.6 Panning and the Ctrl key (N7)

**What IntraPaint does.**
- Pan is middle-drag or `pan_view_modifier` (Ctrl) + left-drag (`ImageGraphicsView.mouseMoveEvent`). Space is not
  bound on the canvas.
- `eyedropper_override_modifier` is also Ctrl. `ToolController` registers the eyedropper as a delegate for the brush,
  fill, draw, shape and text tools while Ctrl is held. `[inferred]` So with those tools, Ctrl+click picks a color
  and Ctrl+drag pans as well, since the view's pan check does not know the delegate took the click.
- Ctrl+arrows pan in most tools but resize the layer in the text and transform tools.

**Norm.** Hold Space and drag to pan, in all three. The color-pick modifier is Ctrl in GIMP and Krita, Alt in
Photoshop.

**Recommendation.** Add Space-hold pan as a new default. Keep Ctrl as the eyedropper modifier, which matches two of
three references. **Tension:** Ctrl+drag panning is the maintainer's current habit. Options: keep both (Ctrl-drag
pans only when the active tool has no eyedropper delegate), or move pan to Space only. Recommend keeping both for one
release with the delegate rule, so neither habit breaks.

**Sketch.** A `pan_view_key` in `key_config_definitions.json` (default `Space`), tracked in `ImageGraphicsView`'s key
handling as "held". While held, left-drag pans and the cursor shows an open/closed hand. Space must be ignored while
a text field or the text tool has focus; `ActiveTextFieldTracker` already knows this.

### 2.7 Save As (N8)

`save_as_shortcut` is Ctrl+Alt+S. All three references use Ctrl+Shift+S, which IntraPaint leaves unbound
(`shape_tool_key` is bare Shift+S, a different chord). Change the default to `Ctrl+Shift+S,Ctrl+Alt+S` so the old
binding keeps working.

### 2.8 Tool letters (N9)

**What IntraPaint does.** B brush, D draw, E eraser, F fill, I filter brush, M smudge, N clone, C eyedropper, X text,
T transform, S selection brush, A selection fill, R rectangle/ellipse selection, L free selection, Shift+S shape, G
generation area.

**Norm.** None. The references disagree on most letters (Photoshop: I eyedropper, M marquee, W wand, T type,
S clone, Ctrl+T transform; GIMP: O color picker, R rectangle select, U fuzzy select, T text, C clone; Krita: Ctrl+R
rectangle select, F fill, T move). The only letters all three share are B for brush and L for lasso, which IntraPaint
already uses. Two single letters do have a shared meaning that collides here: **D** (reset colors) and **X** (swap
colors), see 2.11.

**Recommendation.** Keep the defaults. A changed letter costs the maintainer every time and gains a user of one
reference editor only. Ship keymap presets later if users ask: a settings dropdown that writes a known set of
`KeyConfig` values ("IntraPaint", "Photoshop-like", "Krita-like"). This is self-contained and waits for demand.

### 2.9 Selection modes (N10)

**What IntraPaint does.** Every selection gesture adds to the existing selection. Removing selection differs by tool:
right-drag in the rectangle/ellipse and selection-fill tools, a `Q` toggle in the free-selection and selection-brush
tools (where right-click means a 1px brush). `Q` in the rectangle tool switches rectangle/ellipse instead. There is
no replace mode and no Shift/Alt modifier for add/subtract.

**Norm.** A new selection replaces the old one; Shift adds and Alt (Photoshop, Krita) or Ctrl (GIMP) subtracts.
Selection tools also offer an explicit mode toggle (replace / add / subtract / intersect).

**Recommendation.** Add a consistent mode model to all four selection tools: a shared mode control in the tool
panels with Add as the default, plus Shift = add and Alt = subtract while dragging. Keep right-click subtract where it
exists. **Tension:** replace-by-default is the strongest norm here, but inpainting builds selections up across many
strokes, and replace would break that. Keep Add as the shipped default and offer Replace in the mode control.

Modifier collisions: in the selection brush, Shift is `line_modifier` and Alt is `fixed_angle_modifier`, and Ctrl is
`pan_view_modifier` everywhere. Bind Shift = add and Alt = subtract only in the rectangle/ellipse, free-selection and
selection-fill tools, where those modifiers have no stroke meaning, and give the selection brush the mode control and
its existing `Q` toggle only. Rectangle/ellipse already uses Shift for a 1:1 shape (`fixed_aspect_modifier`), so
there Shift held before the press means add and Shift held during the drag means 1:1, as in Photoshop.

**Sketch.** A `selection_mode` Cache value (`add`/`subtract`/`replace`/`intersect`) and a shared panel widget; each
tool's commit step composes its shape with the existing mask using the matching `QPainter` composition mode
(SourceOver, DestinationOut, Source after clear, DestinationIn). Modifiers override the stored mode for one gesture.
Undo is unchanged, since each tool already commits one selection-layer action per gesture. Tests: one per mode, using
`ToolTestCase`.

### 2.10 Painting outside the selection (N11)

**What IntraPaint does.** `paint_selection_only` and the per-tool equivalents default to false: brushes, fill,
filters and smudge ignore the selection unless their box is checked.

**Norm.** Painting is clipped to an active selection in all three.

**Recommendation.** Keep. IntraPaint's selection is first an inpainting mask that stays active through whole
sessions; clipping every stroke to it would make touch-ups around a pending inpaint area impossible without
deselecting. The norm exists to make selections useful for painting, and the per-tool box already gives that. Make
it discoverable: show a small "Clipped to selection" badge near the cursor hint while the box is on.

### 2.11 Colors (N12)

_Pending `color_subsystem.md` (A8)._

### 2.12 Keybinding entry (N13)

**What IntraPaint does.** The settings window takes keybindings as typed text: the user types `PgDown`, not presses
the key (`doc/menu_options.md`, "Settings window").

**Norm.** Press-to-record fields, with a conflict warning.

**Sketch.** Qt's `QKeySequenceEdit` records chords. Wrap it in an input field that also allows several keys (the
existing comma-separated format) and modifier-only bindings, which `QKeySequenceEdit` does not capture alone, by
falling back to a combo box for the `*_modifier` keys. Flag conflicts by scanning `KeyConfig` for the same sequence
in an overlapping context; "Who it serves" item 3 makes this worth more than its size, since a conflict currently
fails silently.

### 2.13 Undo history (N14)

No history panel, and undo merges actions that land within `undo_merge_interval` (0.2s). The reference editors merge
by gesture, not by time, and Photoshop and Krita show a history list. Time-based merging is already filed as a bug
(#6), and the QUndoStack migration that would give a history view cheaply (`QUndoView`) is on hold (#36). Defer both
here; revisit the panel if #36 resumes.

### 2.14 Window and layout (N15)

`responsive_layout.md` covers these: the window fills the available screen on every launch instead of restoring its
last geometry (§1(d), R5), the 10pt font ignores DPI (§1(e), R6), and overflow clips instead of scrolling (C6, R2).
All three are norm departures as well as layout bugs; follow that report's phases. Saving and restoring geometry
(`QWidget.saveGeometry` into `Cache`) is the cheapest piece and can land ahead of the rest.

### 2.15 Generation area controls (N16)

The generation area has no reference-editor equivalent, but its gizmo breaks the conventions every on-canvas
rectangle follows elsewhere: no handles, left-click places the corner instead of grabbing, right-click resizes from
the top-left. `generation_area_ux.md` §2.5 replaces these with grab/center dragging and eight handles, and inverts
the Shift aspect rule there; implementation is tracked in #41. Nothing to add.

### 2.16 Panels (N17)

Panels live in four custom tab boxes (`responsive_layout.md` §1(a)); they cannot float or dock freely, as Qt's
`QDockWidget` panels do in Krita and in Photoshop's workspace model. #55 tracks moving tabs into separate windows.
A move to `QDockWidget` would also replace the hand-tuned tab-box heuristics in OQ1, so decide #55 together with OQ1's
P4 rather than separately.

---

## 3. Not departures

Checked and found conventional, or IntraPaint-specific with no norm to follow:
- Undo/redo (Ctrl+Z / Ctrl+Shift+Z), copy/cut/paste keys, Ctrl+A select all, Ctrl+D deselect (Photoshop), Ctrl+I
  invert selection (GIMP), Ctrl+Shift+N new layer, `[`/`]` brush size, wheel zoom (Krita's default; a preference in
  the others).
- Paste creating a new layer (Photoshop, Krita).
- Red-tinted selection overlay: matches Quick Mask in Photoshop and GIMP, and suits an inpainting mask.
- Arrow keys moving the generation area, `F4` to generate, the generated-image selector: IntraPaint-specific.

## Issues filed

- #80: closing the main window discards unsaved changes without a prompt (N1).
