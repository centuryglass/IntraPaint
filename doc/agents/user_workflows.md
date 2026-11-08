# How IntraPaint is used

Read this before answering a question about user experience, feature design or user workflows, or before proposing
how a feature should behave. It covers how IntraPaint is used and where it departs from a conventional image editor.
The user guides in `doc/` hold the details; this file says which one to read.

## The inpainting loop

Most AI work in IntraPaint repeats one loop many times on small regions of a larger image:

1. **Place the generation area.** It is the region the generator sees and changes, sized near the model's native
   resolution. In inpainting mode it follows the selection by default.
   [Generation area tool](../tool_guide.md#-generation-area-tool-c),
   [Generation Area](../inpainting_guide.md#generation-area).
2. **Select what to change.** The selection is the inpainting mask. "Limit context to the selection" crops what the
   generator sees to the selection plus a context margin, and context pins stretch that crop.
   [Selection tools](../tool_guide.md#selection-tools),
   [Limit context](../inpainting_guide.md#limit-context-to-the-selection-checkbox).
3. **Optionally paint a rough guide** into the region, for the generator to clean up.
   [Visually guiding image generation](../inpainting_guide.md#visually-guiding-image-generation).
4. **Generate a batch.** The generator reads the merged visible image inside the generation area, not only the
   active layer. [Image Generation Panel](../stable-diffusion.md#image-generation-panel).
5. **Compare the candidates** in the generated image selection view, which replaces the canvas until one is chosen or
   all are rejected. The original is always the first option. The view has its own zoom controls and its own
   "Show selection" toggle. [Generated Image Selection View](../controls.md#generated-image-selection-view).
6. **Accept one.** It is drawn into the active layer at the generation area. A candidate can also be sent to a new
   layer, to keep parts of several.
7. **Repeat** with adjusted denoising strength, context or prompt.
   [Inpainting strategies](../inpainting_guide.md#inpainting-strategies).

## Where IntraPaint differs from a conventional editor

- **A selection is an inpainting mask first.** Painting tools ignore it unless "Paint selection only" is checked,
  which is off by default. Don't assume a selection clips edits. The exceptions act on selected content by design:
  cut, copy and clear, and the filter window, whose "Change selected areas only" starts checked whenever something is
  selected.
- **Candidates are compared off-canvas.** A feature about judging generated results belongs in the generated image
  selection view. The main canvas is for editing between generations.
- **The generation area is a persistent object.** It stays on the canvas while every tool is active, and it moves on
  its own when the selection changes in inpainting mode.
- **Generation input and output differ in scope.** Input is every visible layer in the generation area. Output goes
  into the active layer only.
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
