# Handoff: inpainting vs. layer compositing modes and partial alpha

This summarizes a separate session so it can be merged with the mask-blur discussion. Nothing has been changed,
committed or filed yet. The other session only answered a question.

## The maintainer's question

IntraPaint has a full layer stack: composition modes, opacity, groups and partial alpha. Inpainting handles all of
these badly, so in practice the maintainer never inpaints over custom composition modes or partial alpha without
flattening that region first. They asked whether IntraPaint could or should be smarter about it, given that Stable
Diffusion doesn't understand alpha.

## How the pipeline works today (verified in code)

- **Input:** `ImageGenerator.get_generation_inputs()` (`src/controller/image_generation/image_generator.py`) calls
  `ImageStack.qimage_generation_area_content()`. That renders the full composite of all visible layers, crops it to
  the generation area and scales it to `Cache.GENERATION_SIZE`.
  - The composite goes to the backend as RGBA. The sd_backend_client adapters (`sd_adapters/image_adapter.py`) keep
    the alpha, but the ComfyUI and Forge/A1111 backends drop it.
  - So transparent pixels reach SD as whatever RGB is stored under them, which is usually black.
- **Paste mask:** `SDGenerator.get_paste_mask()` (`src/controller/image_generation/sd_generator.py`) grows the
  selection mask by the blur band's reach (`mask_blur.py`, `blur_extent_in_image` / `grow_mask`). The grown mask
  stays hard-edged.
  - Backends return results that are already blended back into the source composite through the blurred mask. A
    soft paste clip would therefore apply the blur twice.
- **Previews:** `GenerationSession.generate()` (`generation_session.py`) draws the source outside the paste mask
  (`composite_base`) over each result, so previews match what applying would produce.
- **Apply:** `apply_generated_image()` (`src/controller/image_generation/apply_option.py`) works in three steps:
  1. Clips the option with the paste mask (`DestinationIn`).
  2. Calls `ImageStack.set_generation_area_content()`, which maps the option through the active layer's transform.
  3. Draws it with SourceOver through `ImageLayer.insert_image_content()`, which writes via `borrow_image`. That may
     make alpha lock apply, but this hasn't been verified.
- A blocked target (locked, hidden or not an image layer) falls back to a new layer from `create_layer`. That layer
  goes above the active layer, not at the top of the stack. "Send to new layer" uses the same placement.

## The core problem

The generated image is a target **composite** (what the whole stack should look like in the area), but it gets
written into the active layer as if it were that layer's own **pixels**. That's only correct when all of these hold:

1. The active layer is Normal mode at 100% opacity.
2. Every ancestor group is Normal, fully opaque and isolated.
3. Nothing above the active layer draws over the area.
4. The composite under the area is fully opaque.

When any condition fails, the result gets applied twice or diluted:

- **Multiply layer:** too dark, because the result is multiplied over the content below again.
- **50% opacity layer:** faded halfway back toward the old content.
- **Line art layer above:** the line art gets copied into the paint layer, so it shows twice. Hiding the line art
  later leaves the copy behind.

**Where this meets the mask blur:** the blur band outside the selection holds the backend's blend of the result with
the original composite. The hard paste mask covers that band, so the composite gets copied into the active layer
there too.

- On a non-Normal or translucent layer, the band shows the double-application problem even where the user didn't
  select anything. It looks like a halo or seam around the edit.
- This also means a soft paste mask and the backend's blur interact with layer compositing. Any fix to one has to
  account for the other.

## Options discussed, in recommended order

1. **Apply the result on a new Normal layer at the top of the stack** (top-level, outside any group), clipped by the
   paste mask.
   - Exact by construction: the view shows the same composite that went into generation, including the blur band.
     It's basically flattening without destroying anything.
   - Could be an apply option, or the automatic fallback when conditions 1-3 fail. Cheap and never wrong.
   - Today's "send to new layer" doesn't do this. Its layer sits above the active layer, so it's still under the
     layers above and inside the group's composition mode.
2. **Inverse-composite into the active layer.** Given the target C′ and the content below B, solve for the layer
   pixels L′:
   - Normal at opacity o: L′ = (C′ − (1−o)·B) / o. Clips when C′ is far from B; unstable at low opacity.
   - Multiply: L′ = C′ / B. Can't brighten; fails where B is near black.
   - Screen: L′ = 1 − (1−C′)/(1−B). Can't darken.
   - Add: L′ = C′ − B. Can't darken.
   - Darken, Lighten, Difference and the rest: often no solution.

   After solving, recomposite and measure the error. If it's past a threshold, fall back to option 1 and tell the
   user. Limit scope to the active layer, with nothing above it, inside a Normal group. Beyond that it becomes a
   general solver. The blur band needs solving too, since it also holds composite pixels. Multiply and opacity are
   the cases most likely to matter (shading layers, toned-down layers).
3. **Fix alpha on the input side.** The first part is a plain bug fix:
   - Flatten transparent regions over a known background (the background color, or neutral gray) before sending,
     so SD doesn't get accidental black.
   - Optional: add fully transparent pixels to the generation mask, so SD fills them.
   - Optional on apply: restore the original alpha in the area ("inpaint the color, keep the shape"). Check first
     whether alpha-locked layers already get this through `borrow_image`.
4. **Let the user choose what SD sees** ("exclude layers above the active layer", "active layer only"). Ranked last:
   - Excluding line art means the result ignores it.
   - A Multiply shading layer sent alone reads to SD as a pale, washed-out image, which it treats as a normal one.

## Audience tension (flag to the maintainer, per AGENTS.md "Who it serves")

Options 1 and 3 fit the maintainer's generate/compare/inpaint loop, since they make "just inpaint" safe on layered
documents. Option 2 is where the cleverness is, but it gives approximate results in some regions. Silent clipping
would be worse than today's predictable failure, so keep option 2 opt-in, or have it warn when it clips.

## Status

- No open issue covers this. Searched the issue cache for composite, alpha, transparency and opacity. Related but
  separate issues: #132 (non-isolated groups composite the content beneath them), #211, #24.
- The maintainer was offered one issue per option, or a start on option 1. They haven't answered yet.
- Assigned branch for this work: `claude/inpaint-compositing-modes-yiqfn9`. Per AGENTS.md, a self-named branch from
  `integration` is preferred.
