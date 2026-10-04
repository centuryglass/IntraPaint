# Generation area controls (OQ6)

**Status:** design agreed with the maintainer on 2026-09-30. Implementation is tracked in
[#41](https://github.com/centuryglass/IntraPaint/issues/41).

**Goal (from the former `doc/TODO.md`, now #41):** get maximum flexibility out of the generation area while keeping the user
from having to think about hitting good resolutions and matching aspect ratios. Replace the 1px
selection-brush trick with something better.

---

## 1. How the generation area is used

This section is the basis for every decision below. It comes from the maintainer's own workflow, and it
covers what the workflow docs leave out.

**Three rectangles decide what the model sees:**

| Concept | Where it lives | Role in practice |
|---|---|---|
| Generation area | `ImageStack.generation_area` (image-space `QRect`) | Outer limit, and the aspect-ratio template for everything inside it. |
| Inpaint full-res crop | `SelectionLayer.get_selection_gen_area()` (`selection_layer.py:280`) | What the model actually sees: the selection's bounds plus padding, clamped to the area, then grown to the area's aspect ratio (`:321-345`). |
| Generation resolution | `Cache.GENERATION_SIZE` | The pixel size sent to the model. The crop is scaled to it. |

- **Inpaint Full Resolution is nearly always on.** It's turned off only when a ControlNet unit misbehaves
  with it, or for high-level passes where the scaling doesn't help.
- **Padding is the working zoom control.** Because the crop grows to the area's aspect ratio, padding
  changes never distort the output. Resizing the area directly does, which is why the area is rarely
  resized by dragging. Padding clipped at the area's edge is not a problem; moving the area takes a
  second.
- **The 1px selection-brush trick is used constantly.** Right-clicking with the selection brush paints a
  1px selection outside the real selection (`brush_tool.py:313` switches to a 1px brush on right-click),
  which stretches the crop to include that point. It gives one-sided padding, and one right-click on
  something the model should see is faster than a slider. Its drawback: the pixel really is selected, so
  it gets inpainted.
- **Typical routine (1024×768 images):** select the full image and match the resolution to it for passes
  that need whole-image context. Then set a 768² area, match the resolution again, and keep that for
  detail work, varying context with padding and the 1px trick. Switch back to the full image when targeted
  edits aren't working. On small images the area stays over the whole image. On large ones the size
  changes often, depending on context needs, speed and the model.
- **Resolution normally equals the area size.** It goes higher only when the area is smaller than the model
  handles well (rarely, for integer scaling). Non-square resolutions do get used. The resolution changes
  every few minutes on average. **Changing it is the biggest pain point:** it's a predictable step that
  takes several clicks.
- **The area gets moved mostly from the Navigation tab** (docked in the tool panel, roughly 480×300 on a
  1080p screen). Left-click currently puts the area's top-left corner at the click. That feels like
  dragging, but it overshoots slightly. Resizing from there is rare. The G tool is opened mostly to reach
  its panel. Arrow-key nudging is occasionally useful. `Z` is used only to return to the full-image view.
- **The outlines are enough feedback.** The area and crop outlines on the canvas and in the navigation
  panel already show exactly what the model will get. Numeric readouts wouldn't help.
- txt2img and img2img are rare, and the area matters less there.

---

## 2. Design

Five changes. An interactive mockup of the design was used to settle these; the code in section 3 is the
reference now.

### 2.1 Frames and a resolution rule

Replaces the "Select full image", "Gen. area size to resolution" and "Resolution to gen. area size" buttons
in the generation area tool panel.

**Frames** are one-click area sizes, shown as a row of chips in the generation area tool panel:
- **Full image**: the area covers the whole image.
- **Square**: the largest square that fits (768² on a 1024×768 image).
- **Recent sizes**: the last four area sizes that were used, excluding the two above. A size is recorded
  when a size change is finished (a resize drag ends, W/H editing is finished, or a frame is applied).
  Saved between sessions.
- **Custom**: a "+" chip takes a typed size (`768` or `640x480`) and applies it.

Applying a frame changes only the area's size. The area keeps its center, clamped to the image, then
follow-selection (2.4) places it if that's enabled and there's a selection. **Previous frame** (new
keybinding, default `Shift+G`) switches back to the size used before the current one, so pressing it
repeatedly flips between two frames, such as full image and square.

**Resolution rule** (dropdown under the frames) decides what happens to `GENERATION_SIZE` whenever the area
size changes, by any means:
- **Match area**: resolution = area size.
- **Match area, at least N** (default; N is a setting, default 512): resolution = area size, scaled up by
  the smallest whole-number factor that brings the shorter side to at least N. A whole-number factor keeps
  scaling clean. The factor is reduced if the result would exceed `MAX_GENERATION_SIZE`.
- **Manual**: the resolution only changes when you edit it.

The resolution W/H fields stay visible and editable, in this panel and in the Stable Diffusion panel.
Editing either of them by hand switches the rule to Manual, so a typed value is never overwritten.

Because the rule reacts to area-size changes, undoing an area change also restores the matching
resolution. The resolution itself has no undo entry (it's a `Cache` value), which is only noticeable in
Manual mode, where it's already the user's own value.

### 2.2 Context pins

Replace the 1px trick. With the selection brush:
- **Right-click without dragging** drops a context pin. **Right-clicking an existing pin removes it.**
- **Right-drag** does nothing. The 1px right-button stroke is removed from every brush tool, since pins
  replace its only use.

A pin stretches the full-res crop to include its point, exactly like the 1px dot did, but nothing under it
gets inpainted. Pins are drawn as push-pin markers (`resources/icons/context_pin.svg`) on the canvas and in
the navigation panel. In inpainting mode, the selection tool panels show a "Clear Context Pins" button
beside "Clear" and "Select All"; the three share one row when it fits their full text, and stack
otherwise.

- Pins stay until you remove them. Repeatedly inpainting the same area is common, so they are **not**
  cleared after generating. A setting ("Clear context pins after generating", off by default) turns
  clearing on.
- Clearing the selection doesn't clear pins. **Selection → Clear context pins** removes all of them.
- Pins only matter while something is selected. They count for the crop, for follow-selection and for the
  change highlight in the generated-image selector (which already calls `get_selection_gen_area(True)`).
- Adding and removing pins is undoable. Pins aren't saved in image files.

### 2.3 Padding shortcut

**Shift + scroll wheel** changes Inpaint Full-Res padding from any tool, over the main canvas or the
navigation panel. Each notch changes padding by the same amount as scrolling the padding slider, and the
speed modifier (`Alt`) multiplies it. Scrolling padding above zero turns Inpaint Full Resolution on.

The modifier is a new `KeyConfig` modifier ("Padding scroll modifier", default `Shift`), so it can be moved
if it collides with anything.

### 2.4 Area follows the selection

After each selection change, the area moves to contain the selection's bounds plus pins and padding.
Setting (application settings, "Generation area follows selection"):
- **Minimal move** (default): the area moves only as far as needed, so small follow-up edits don't jump
  it around.
- **Center on selection**: the area centers on the selection.
- **Off**: the area only moves when you move it.

Rules:
- It only runs in Inpaint mode, while the generation area is shown, when there's a selection.
- It only reacts to selection edits. It never runs for undo/redo, and never undoes a manual move.
- It never resizes the area. When the target is bigger than the area along one axis, the area centers
  on the target along that axis.
- Follow moves are ordinary generation-area changes with their own undo step.

### 2.5 Generation area tool: grab, center and handles

**Left-click, on the canvas and in the navigation panel:**
- Pressing inside the area grabs it: dragging moves it without the area jumping to the cursor.
- Pressing outside the area centers the area on that point, and dragging continues from there.

**Handles (main canvas only):** eight handles on the area outline while the G tool is active.
- **Corner handles keep the area's aspect ratio** by default. Holding the fixed-aspect modifier (`Shift`)
  frees the aspect ratio. This inverts the modifier's usual meaning, because keeping the aspect ratio is
  the safe default here; the tool's hint text states it.
- Edge handles move one side.
- The resolution rule applies as the size changes, and the finished size is recorded as a recent frame.

Right-click keeps its current behavior in both places (resize with the top-left corner fixed). Arrow-key
nudging is unchanged. The navigation panel keeps its "Move gen. area" / "Move view" toggle.

---

## 3. Implementation plan

Each step can ship alone, in this order. Put new user-visible strings through the file's `_tr()`, and
define new options in `resources/config/*.json`.

### Step 1: Resolution rule and frames

- **Config:**
  - `cache_value_definitions.json`: `generation_resolution_rule` (string options: Match area / Match area,
    at least N / Manual; default the second, saved) and `recent_generation_area_sizes` (list of `"WxH"`
    strings, saved).
  - `application_config_definitions.json`: `generation_resolution_min_side` (int, default 512).
  - `key_config_definitions.json`: `previous_generation_frame_key` (default `Shift+G`; `Shift+S` and
    `Shift+Z` show the hotkey filter already handles Shift+letter). Don't use `Q` or `E`, which are the
    tool-action hotkey and the eraser.
- **Pure logic** in a new `src/util/generation_area_utils.py`, for unit testing:
  - `resolution_for_area(area_size, rule, min_side, max_size) -> QSize`
  - frame helpers: dynamic frames for an image size, recording a recent size, parsing `768` / `640x480`.
- **Wiring:** one small owner object created by `AppController` (e.g.
  `src/controller/generation_area_controller.py`). It connects to
  `ImageStack.generation_area_bounds_changed`, applies the rule when the size changed, records recent sizes
  on finished changes, and handles the previous-frame hotkey. Guard against feedback loops (the rule sets
  `GENERATION_SIZE`; nothing should set the area back from it).
- **Manual override:** the `GENERATION_SIZE` control changing from user input (not from the rule) sets the
  rule to Manual. Suppress this while the rule itself is writing.
- **UI:** in `generation_area_tool_panel.py`, replace the three buttons and the resolution block
  (`:66-99`) with the frame chips, the rule dropdown and the existing resolution `SizeField`. Keep the
  X/Y/W/H controls. Follow the panel's existing horizontal and vertical layout code (`_build_layout`).
- **Remove** the "Gen. area size to resolution" and "Resolution to gen. area size" buttons and their
  strings. "Select full image" becomes the Full frame chip.

### Step 2: Context pins

- **Model:** `SelectionLayer` owns the pins: a list of image-space points, a `context_pins_changed`
  signal, and add/remove/clear methods recorded on `UndoStack`. `get_selection_gen_area()` unions pins
  into the bounds before padding. Watch the layer offset: the method mixes `_bounding_box` with
  `selection_layer.position` (see `sd_comfyui_generator.py:523`), so convert pins consistently.
- **Tool:** in `SelectionBrushTool`, a right-click released within a few screen pixels of the press
  toggles a pin: it removes the pin whose drawn marker is under the click, otherwise adds one. A longer
  right-drag does nothing. Update the tool's hint text.
- **Drawing:** a push-pin graphics item per pin in `ImageViewer`, so it shows in the main view and
  the navigation panel (`NavigationWindow` is an `ImagePanel`). Refresh `_generation_area_selection_outline`
  on `context_pins_changed`, the same way it refreshes on selection changes (`image_viewer.py:195-210`).
- **Menu and settings:** "Clear context pins" in the Selection menu. `clear_context_pins_after_generating`
  (app config bool, default false), applied when a generation finishes.
- **Backends:**
  - ComfyUI already crops on the client with `get_selection_gen_area()`
    (`sd_comfyui_generator.py:510-547`), so pins work there automatically.
  - **The WebUI (A1111/Forge) backend ignores pins.** It sends `inpaint_full_res` and the padding to the
    server (`diffusion_request_body.py:181-182`), which computes its own crop from the mask. When pins
    change the crop, the WebUI generator has to crop on the client instead: crop the image and mask to
    the pinned crop, send them with `inpaint_full_res` off at `GENERATION_SIZE`, then scale the results
    back and composite them into the area. Move `_inpaint_gen_area_crop_bounds`,
    `_scale_and_crop_gen_qimage` and `_restore_cropped_inpainting_images` from the ComfyUI generator
    into `SDGenerator` so both backends share them. Without pins, keep the current server-side path.

### Step 3: Padding shortcut

- New `KeyConfig` modifier `padding_scroll_modifier` (default `Shift`).
- Handle it in `ToolController.eventFilter`'s wheel case (`tool_controller.py:271`) before the active tool
  sees the event, so it works for every tool and in the navigation panel's own tool controller. Accept
  either wheel axis, because some platforms turn Shift + vertical scroll into horizontal scroll, and brush
  tools use the horizontal axis for brush size (`brush_tool.py:446`).
- Make sure the event is consumed before `ImageGraphicsView`'s zoom filter (`image_graphics_view.py:531`)
  zooms as well. Check the order in which the two filters are installed.

### Step 4: Follow selection

- `app_config`: `generation_area_follow_selection` (string options: Minimal move / Center on selection /
  Off; default Minimal move).
- Placement is a pure function in `generation_area_utils.py`:
  `follow_selection_position(area, target, mode, image_bounds) -> QPoint`, where `target` is the unclamped
  bounds of selection + pins + padding.
- Trigger it from the generation-area owner object from step 1. Debounce on the selection layer's content
  and pin changes, and fire once the edit has settled, not on every stroke segment. Skip while
  `UndoStack().undo_in_progress` is set, and skip when the target bounds didn't change.

### Step 5: Generation area tool gestures and handles

- `GenerationAreaTool` (`generation_area_tool.py`) gets the grab-inside / center-outside left-drag,
  replacing the top-left placement in `_move_generation_area`. `NavigationWindow` uses the same tool
  (`navigation_window.py:115`), so both change together.
- Add a constructor flag for handles, on for the main tool and off for the navigation panel's instance.
- **Handles:** build a small axis-aligned handle item for this tool, reusing `transform_handle.py`'s
  drawing if it fits. Don't build on `TransformOutline`: #11 plans to redesign it, and it carries rotation
  and matrix-decomposition state this tool doesn't need. Handles resize in integer image coordinates,
  clamp to the image and `MIN/MAX_EDIT_SIZE`, and set hover cursors. The corner aspect lock uses the
  area's aspect ratio at the start of the drag.
- Use one `UndoStack().combining_actions(...)` per drag. `ImageStack.generation_area` already merges
  consecutive area changes (`image_stack.py:360-368`); confirm that a whole drag undoes in one step.
- Update the input hint text for both instances.

### Tests

New `unittest` files in `test/`, following the existing `setUp` patterns for config and the undo stack:
- `resolution_for_area` for each rule, including the whole-number factor and the `MAX_GENERATION_SIZE`
  cap.
- Frame helpers: dynamic frames, recent-size ordering and deduplication, size parsing.
- `get_selection_gen_area()` with pins: one-sided pins, pins outside the area (clamped), pins with an
  empty selection (no crop).
- `follow_selection_position` for both modes, for targets smaller and larger than the area, and at the
  image edges.
- Pin add/remove/clear through undo and redo.

Mouse gestures and the WebUI crop path need manual testing with a running backend.

### User docs to update with the implementation

- `doc/tool_guide.md`: generation area tool controls and panel, selection brush right-click. The labeled
  screenshot `doc/labeled_screenshots/tools/gen_area.png` needs replacing.
- `doc/inpainting_guide.md`: "Generation Area control" and "Generation resolution": pins replace the 1px
  trick; describe the resolution rule and Shift+scroll padding.
- `doc/menu_options.md`: navigation window left-click, "Clear context pins", the new settings.

---

## 4. Future work (not part of this refactor)

- **Context bar:** full-res, padding, frames and follow in one bar that's visible for every tool (for
  example above the Navigation tab), so none of them needs a tool switch. Deferred because of the
  complexity of the existing panel layouts.
- **Out-of-bounds indicator:** a visible warning when the selection plus padding extends past the
  generation area. Worth doing; the visual design needs more thought.
- **Move the area to a layer's bounds:** occasionally useful when assembling txt2img results on a larger
  canvas.

## 5. Rejected ideas

Recorded so they aren't proposed again:
- **Automatic area growth** when the selection outgrows the area, whether silent, with undo, or through an
  inline prompt. No rule can tell when growth is wanted, and pins, padding and frames already make the
  manual fix quick.
- **Scale readouts and a "model's-eye" preview** of the exact model input. The outlines already show what
  the model sees, and the numbers don't help in practice.
