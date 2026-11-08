# How IntraPaint is used

Read this before answering a question about user experience, feature design or user workflows, or before proposing
how a feature should behave. It covers how IntraPaint is used and where it departs from a conventional image editor.
The user guides in `doc/` hold the details; this file says which one to read.

## The inpainting loop

Most AI work in IntraPaint repeats one loop many times on small regions of a larger image:

1. **Select what to change.** The selection is the inpainting mask, and choosing it carefully does most of the work.
   [Selection tools](../tool_guide.md#selection-tools).
2. **Set what the generator sees.** In inpainting mode the generation area follows the selection, so it is rarely
   placed by hand. What the generator sees is tuned with "Limit context to the selection", the context slider
   (Shift+scroll from any tool) and context pins.
   [Generation area tool](../tool_guide.md#-generation-area-tool-c),
   [Limit context](../inpainting_guide.md#limit-context-to-the-selection-checkbox),
   [Generation Area control](../inpainting_guide.md#generation-area-control).
3. **Adjust generator parameters,** mainly denoising strength. Painting a rough guide or rewriting the prompt is an
   occasional fallback when parameters aren't enough.
   [Visually guiding image generation](../inpainting_guide.md#visually-guiding-image-generation).
4. **Generate a batch.** The generator reads the merged visible image inside the generation area, not only the
   active layer. [Image Generation Panel](../stable-diffusion.md#image-generation-panel).
5. **Compare the candidates** in the generated image selection view, which replaces the canvas until one is chosen or
   all are rejected. The original is always the first option. The view has its own zoom controls and its own
   "Show selection" toggle. [Generated Image Selection View](../controls.md#generated-image-selection-view).
6. **Accept one.** It is drawn into the active layer at the generation area. A candidate can also be sent to a new
   layer, to keep parts of several.
7. **Repeat** on the next small region, or on the same one with adjusted parameters.
   [Inpainting strategies](../inpainting_guide.md#inpainting-strategies).

Projects start either from a blank canvas or, more often, from a flawed but interesting image picked out of a large
random batch. Text to Image and Image to Image are rarely used inside IntraPaint; inpainting is the core mode.

Manual painting and drawing are a full workflow in their own right, not support for inpainting. They are used less at
times but stay first-class: a change must not trade them away for inpainting convenience.

## Where IntraPaint differs from a conventional editor

- **A selection is an inpainting mask and a clipboard region, not a clip mask.** Painting tools ignore it unless
  "Paint selection only" is checked, which is off by default, because painting past the selection is common. Cut,
  copy, paste and clear are used heavily and act on it. The filter window's "Change selected areas only" starts
  checked whenever something is selected, because filtering a whole layer is rare; filters are occasional steps, not
  part of the core loop.
- **Candidates are compared off-canvas.** A feature about judging generated results belongs in the generated image
  selection view. The main canvas is for editing between generations.
- **The generation area is a persistent object.** It stays on the canvas while every tool is active, and it moves on
  its own when the selection changes in inpainting mode.
- **Generation input and output differ in scope.** Input is every visible layer in the generation area. Output goes
  into the active layer only, drawn normally, so inpainting a layer with a non-normal composition mode gives wrong
  results. Layers are mostly ephemeral in AI work for this reason; most images stay on one layer, with more only in
  large projects.
- **Without a backend, IntraPaint is a plain image editor.** The Image Generation panel and the generation area are
  absent, and every manual tool must still work (AGENTS.md, "Who it serves").

## The maintainer's workflow

The maintainer uses IntraPaint for hobby inpainting. A change that slows the loop above needs a strong reason
(AGENTS.md, "Who it serves").

- **Selection overlay:** on while masking for inpainting, so the masked pixels are unambiguous. Off while editing
  inside a selection, so the edited pixels are fully visible while the outline still shows the bounds.

## Other guides

- [Controls](../controls.md): the main window and the generated image selection view, labeled.
- [Tool guide](../tool_guide.md): every tool's controls and options.
- [Menu options](../menu_options.md): every menu item and the preferences window.
- [Stable Diffusion controls](../stable-diffusion.md): generation settings, denoising strength and upscaling.
- [Inpainting guide](../inpainting_guide.md): the maintainer's own inpainting technique.
