# How IntraPaint is used

What to know before advising on feature design or user workflows: the product's scope, and where IntraPaint departs
from a conventional image editor. The user guides in `doc/` hold the details.

## Scope

- **IntraPaint is for sequential, partly manual editing.** The core loop is inpainting small regions one at a time:
  select, generate a batch, compare, accept, repeat. Batch generation and exploration belong to the Stable Diffusion
  WebUI and ComfyUI interfaces, so a feature that moves IntraPaint toward them needs a reason.
- **Manual painting and editing are first-class.** They must keep working with no backend, and a change must not trade
  them away for inpainting convenience.
- **Support many working styles.** Defaults favor the common case, but the other path stays usable. The generation
  area follows the selection by default, and manual placement still matters for work such as a systematic sweep
  across a large image.

## Where IntraPaint departs from convention

- **A selection is an inpainting mask and a clipboard region, not a clip mask.** Painting tools ignore it unless
  "Paint selection only" is checked, which is off by default. The filter window's "Change selected areas only" starts
  checked whenever something is selected. [Selection tools](../tool_guide.md#selection-tools).
- **Generated candidates are compared off-canvas,** in the generated image selection view, which has its own zoom and
  "Show selection" controls. [Generated Image Selection View](../controls.md#generated-image-selection-view).
- **The generation area is a persistent on-canvas object.** In inpainting mode it moves to contain the selection, its
  context and context pins. It is hidden when no generator is active.
  [Generation area tool](../tool_guide.md#-generation-area-tool-c),
  [Generation Area control](../inpainting_guide.md#generation-area-control).
- **Generation reads the composite and writes one layer.** The generator sees every visible layer in the generation
  area. The accepted result goes into the active layer, or onto a new top layer when the active layer's blending or a
  layer above it would change how the result looks (`src/controller/image_generation/apply_option.py`).

## Guides

- [Controls](../controls.md), [Tool guide](../tool_guide.md), [Menu options](../menu_options.md)
- [Stable Diffusion controls](../stable-diffusion.md), [Inpainting guide](../inpainting_guide.md)
