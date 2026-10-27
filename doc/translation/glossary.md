# English glossary for translators

The terms in IntraPaint's UI where a wrong or inconsistent translation would confuse users, defined as IntraPaint uses
them. Every per-language glossary in this directory decides one rendering for each term here. The process that uses
this file is in [`doc/machine_translation.md`](../machine_translation.md).

- **Meaning** is IntraPaint's sense of the word, which can be narrower than its everyday or Stable Diffusion sense.
- **Where** names the panel, menu, tool or setting that shows the term. Settings are under **Settings**, by tab.
- **UI strings** quotes the English source strings that use the term. When a term appears in several spellings, all of
  them are listed, and every one of them takes the term's single rendering.
- Common UI words that models already translate well (Open, Save, Undo, Copy) are left out.

New terms are added here before their strings are translated into any language.

## Image-editing terms

General vocabulary shared with Photoshop, GIMP and Krita. Per-language glossaries follow those programs' localized UIs.

| Term | Meaning | Where | UI strings |
| --- | --- | --- | --- |
| Layer | One image in the stack that makes up the picture. Text layers hold editable text. | Layers panel, Layers menu | "Add layer", "Merge down", "Convert text layer to image?" |
| Layer group | A layer that holds other layers and composites them together. | Layers panel | "Add layer group", "Merge group" |
| Active layer | The layer that tools and layer commands act on. | Layers panel, tool hints | "Delete the active layer.", "Change active layer only" |
| Isolation (layer group) | Whether a group composites its children by themselves before blending the result onto the layers below. | Layers panel button | "Toggle layer group isolation" |
| Lock, transparency lock | Lock blocks all changes to a layer. Transparency lock lets painting change color but not opacity. | Layers panel buttons | "Toggle layer lock", "Toggle layer transparency lock", "Changes were blocked because the layer is locked." |
| Merge, flatten | Merge combines layers into one. Flatten turns a layer into a plain image layer, applying its transform and opacity to its pixels. | Layers menu | "Merge down", "Merge all visible", "Flatten layer", "Only visible layers can be flattened." |
| Canvas | The image's bounds. Resizing the canvas changes the image size without scaling its content. | Image menu, generation panel | "Resize image canvas", "Text to image: ignores the canvas" |
| Scale (verb) | Resize content by resampling it. Contrast with resizing the canvas. | Image menu, transform tool | "Scale image", "Scale X", "Image scaling mode:" |
| Crop | Cut an image or layer down to a region. | Image and Layers menus | "Crop layer to selection", "Crop layer to content" |
| Selection | The image region chosen for editing. It is also the inpainting mask (see "Mask"). | Selection menu, selection tools | "Select all", "Invert selection", "Nothing is selected, select an area in the image first." |
| Add, Subtract, Replace, Intersect | How a new selection shape combines with the current selection. | Selection tools' mode control | "Add new areas to the selection", "Keep only the part of the selection inside new areas" |
| Opacity | How opaque a stroke or layer is, from transparent to fully opaque. | Brush tools, Layers panel | "Opacity:", "Decrease brush opacity:" |
| Hardness | How sharp a brush's edge is. | Brush tools | "Hardness:", "Increase brush hardness:" |
| Pen pressure | Force reported by a drawing tablet pen, mapped onto size, opacity or hardness. | Brush tools, Settings > Drawing tablet settings | "Pen pressure=size:", "Pen pressure changes this value", "Pressure curve..." |
| Antialiasing | Smoothing of stroke and shape edges. | Brush and shape tools | "Antialiasing" |
| Blend mode | How a layer combines with the layers below it. The values are the standard Photoshop/GIMP names and Qt's Porter-Duff composition names. | Layers panel | "Layer mode:", "Multiply", "Screen", "Color Dodge", "Source Atop", "Destination Out" |
| Foreground / background color | The two current colors. Brushes paint with the foreground color. | Color panel | "Foreground color: click to change, or drag a color here", "Swap foreground and background colors" |
| Color picker | The tool that samples a color from the image or screen. Also called the eyedropper in config keys only. | Tools panel | "Color Picker", "Switch to the color picker tool:", "Pick a color from anywhere on the screen" |
| Fill | Paint a contiguous area with a color or pattern. Also a noun: the fill of a shape. | Fill tool, shape tool | "Color fill", "Fill areas with solid colors", "Fill Color" |
| Threshold | How closely colors must match the clicked color to be filled or selected. | Fill and Magic wand tools | "Color threshold:" |
| Sample merged | Fill or select based on all visible layers combined, not just the active layer. | Fill and Magic wand tools | "Sample Merged", "Toggle sample merged" |
| Smudge | Drag existing image color along a stroke. | Smudge tool | "Smudge", "How far the smudge carries color" |
| Clone stamp, source | Paint a copy of one image area (the source) into another. | Clone stamp tool | "Clone Stamp", "Source mode:", "{right_mouse_icon}: set source - {left_mouse_icon}: draw" |
| Filter | An image effect such as blur or sharpen, applied to a layer or painted with the filter brush. | Filters menu, filter brush | "Apply image filter", "Filter Brush", "Draw to apply an image filter" |
| Posterize | Reduce the number of colors by lowering the bits per channel. | Filters menu | "Posterize", "Reduce color range by reducing image color bit count." |
| Scaling algorithms | Resampling methods named after their algorithms. | Scale image window, Settings > Editing | "Nearest", "Bilinear", "Bicubic", "Lanczos", "Hamming", "Box" |
| Line join | How the corners of a shape outline are drawn. | Shape tool | "Join", "Miter", "Bevel", "Round" |
| Vertex | A corner point of a polygon or star. | Shape tool | "Vertices", "Vertex count:", "{shape}, {count} vertices" |
| Kerning | Adjustment of the spacing between pairs of letters. | Text tool | "Kerning" |

## Stable Diffusion terms

Vocabulary from the Stable Diffusion community and the A1111 WebUI and ComfyUI interfaces. Many of these are usually
kept in English or transliterated; per-language glossaries check community localizations before translating any.

| Term | Meaning | Where | UI strings |
| --- | --- | --- | --- |
| Image generation, generate | Creating or changing image content with the active image generator. "Generate" is the main action button. | Image Generation panel, panel rail | "Generate", "Start AI image generation or modification", "Image generation failed" |
| Inpainting, inpaint | Regenerating only the masked part of the generation area, keeping the rest. The default edit mode. | Image Generation panel | "Inpaint", "Start inpainting", "Inpainting and size" |
| Image to image, text to image | The other edit modes. Image to image alters the whole generation area. Text to image replaces it with new content from the prompt alone. | Image Generation panel | "Image to Image", "Text to Image", "Image to image: ignores the mask" |
| Mask | The area inpainting regenerates. In IntraPaint the mask is the selection. | Image Generation panel's Mask section | "Mask", "Mask blur:", "Masked content:" |
| Masked content | What fills the mask before inpainting: fill, original, latent noise or latent nothing. | Image Generation panel | "Masked content:", "fill", "original", "latent noise", "latent nothing" |
| Prompt | The text describing what to generate. | Image Generation panel | "Prompt", "Add to prompt", "Replace prompt" |
| Negative prompt | Text describing what to avoid. | Image Generation panel | "Negative prompt", "Negative:" |
| Prompt style | A saved prompt fragment, loaded from the WebUI, that can be added to the prompt. | Image Generation panel, Stable Diffusion menu | "Styles", "Saved Prompt Styles", "Add saved prompt styles to the prompt" |
| Guidance scale (CFG) | How strongly the prompt and negative prompt steer generation. | Image Generation panel | "Guidance", "Guidance scale:", "{sampler}, {steps} steps, CFG {guidance}" |
| Steps | The number of denoising steps per image. | Image Generation panel | "Steps", "Sampling steps:", "Step count:", "{steps} steps" |
| Sampler, sampling method | The algorithm that runs the steps. Sampler names such as "Euler a" come from the backend and are not translated. | Image Generation panel | "Sampling", "Sampling method:" |
| Scheduler | How the noise level is spread across the steps. | Image Generation panel | "Scheduler:" |
| Seed | The number that fixes generation's randomness, so a seed and settings reproduce an image. | Image Generation panel | "Use a random seed", "Last seed", "Reuse last seed value" |
| Variation seed, variation strength | A second seed mixed into the first, for small variations of one image (WebUI only). | Image Generation panel | "Variation seed:", "Seed variation", "variation {strength}" |
| Denoising strength | How much image to image and inpainting change the existing content, from 0 (no change) to 1 (all new). | Image Generation panel | "Denoising strength:", "Strength" |
| Batch size, batch count | Batch size is images generated at once. Batch count is how many batches run one after another. | Image Generation panel | "Size and batch", "Batch size:", "Batch count:", "Batch {batch_num} of {num_batches}:" |
| Model, checkpoint | The Stable Diffusion model file that generates images. | Image Generation panel, Stable Diffusion settings | "Model", "Stable Diffusion Model:", "Max checkpoints loaded:", "Model loading" |
| VAE, tiled VAE | The model that converts between images and latent data. Tiled VAE processes it in blocks to save GPU memory. | Image Generation panel, Stable Diffusion settings | "Tiled VAE encoding", "VAE tile size:", "tiled VAE {size}" |
| LoRA | A small add-on model that adjusts a base model, added to the prompt by name. | Image Generation panel, Stable Diffusion menu | "LoRA", "LoRA Models", "Choose LoRA models to add to the prompt" |
| LCM mode | A menu action that sets up fast generation with an LCM LoRA: it adds the LoRA and sets sampler, steps and guidance. | Image Generation panel's More menu | "LCM mode" |
| ControlNet | An add-on that guides generation with a control image, such as edges or a pose. | ControlNet panel | "ControlNet", "Control Model:", "Control Type:", "Control Image:" |
| ControlNet unit | One ControlNet slot, with its own model, image and settings. Up to three run at once. | ControlNet panel | "ControlNet Unit {unit_number}", "Enable ControlNet Unit", "ControlNet: {count} units on" |
| Preprocessor | The step that turns a control image into ControlNet's input, such as an edge map. | ControlNet panel | "Preprocessor:", "Preview Preprocessor", "ControlNet preview failed" |
| Control weight, control step | How strongly a ControlNet unit applies, and the fraction of the steps it applies during. | ControlNet panel | "Control Weight:", "Starting Control Step:", "Ending Control Step:" |
| Describe | Ask the backend to write a prompt describing the generation area's content. Uses the WebUI's interrogate endpoint, where available. | Image Generation panel's More menu | "Describe", "Describing image", "Describe failed", "Describe model (WebUI only):" |
| CLIP skip | How many of the text encoder's final layers to skip. | Stable Diffusion settings | "CLIP skip:" |
| Upscale | Enlarge an image. Stable Diffusion upscaling regenerates detail while enlarging, optionally with a tile ControlNet. | Scale image window | "Advanced AI upscaling", "Upscale method:", "Tile ControlNet model:", "Upscale failure" |
| Inpaint full resolution, padding | Inpaint the masked area at full resolution, with this many pixels of surrounding context. | Image Generation panel | "Inpaint Full Resolution", "Padding:" |
| GPU memory, VRAM | Graphics card memory that models occupy. | Image Generation panel's More menu, ControlNet panel | "Clear GPU memory", "Remove cached models from GPU memory in ComfyUI.", "Low VRAM" |
| Restore faces, tiling | WebUI generation options. Restore faces runs a face-repair model afterwards. Tiling makes the image repeat seamlessly. | Image Generation panel's Advanced section (WebUI only) | "Restore faces", "Tiling", and "restore faces", "tiling" in the section summary |

## IntraPaint terms

Words IntraPaint gives its own meaning. No other program's localization covers them, so each language glossary
chooses a rendering and records its reasoning.

| Term | Meaning | Where | UI strings |
| --- | --- | --- | --- |
| Generation area | The rectangle of the image sent to the image generator. Generated content replaces it. It is separate from the selection. | Generation area tool, Image Generation panel, rulers | "Image generation area:", "Set Image Generation Area", "Move gen. area", "Editing size:", "Zoom in on the area selected for image generation" |
| Generation resolution | The size in pixels the generator works at, which can differ from the generation area's size. | Image Generation panel | "Image generation resolution:", "Generation size:", "Minimum generation resolution:" |
| Resolution rule | How the generation resolution follows changes to the generation area's size. | Image Generation panel | "Resolution rule:", "Match area", "Match area, upscale small areas", "Manual" |
| Context pin | A marker that stretches the inpainting crop to include a point without inpainting it. Placed with the right mouse button. | Selection tools, Selection menu | "Clear context pins", "{left_mouse_icon}: select - {right_mouse_icon}: add, move or remove context pin" |
| Generated image options | The window that shows each image a generation produced, for choosing one to apply. | Opens after generating | "Select from generated image options.", "Option {index}", "Reopen last generated options" |
| Image generator | The backend connection that generates images: Stable Diffusion via WebUI or ComfyUI, GLID-3-XL, or none. | Stable Diffusion menu, generator selection window | "Select image generator...", "Image Generator Selection", "This image generator is not available: {error_reason}" |
| Panel, rail, dock, float | Panels are the dockable windows (Tools, Layers, Image Generation). The rail is the strip of panel tabs at the window's edge. A panel docks into the main window or floats as its own window. | View menu, panel menus | "Panels", "Dock", "Float", "Drag to move panel", "Tab font size:" |
| Tool control hints | The line under the image that lists the active tool's mouse and key controls. | View menu, Settings > Interface | "Show tool control hints", "Hide tool control hints", "{left_mouse_icon}: draw" |
| Speed modifier | A held key that makes keyboard and mouse wheel changes, such as moving, panning and zooming, go faster. | Settings > Keybindings | "Key Speed Modifier:", "{key_binding_name} (with speed modifier)" |
| Selection brush | Tool that paints a selection. | Tools panel | "Selection Brush" |
| Magic wand | Tool that selects connected or similar-colored areas. Photoshop and Paint.NET use this name; GIMP calls it Fuzzy Select. | Tools panel | "Magic wand", "Select areas of similar color", "Switch to the magic wand tool:" |
| Fit box, fit font | Text tool sizing: the box resizes to fit the text, or the font size changes to fit the box. | Text tool | "Fit box", "Fit font", "Fit box: the box resizes to fit the text" |
| Saved colors | The user's stored color swatches. | Color panel | "Saved colors ({count}/{max_count}):", "Add the current color to the saved colors" |

## Names kept as they are

These are product, format, model or color-model names. Each per-language glossary records whether its language keeps
them in Latin script, and the default is to keep them.

- Products and backends: IntraPaint, Stable Diffusion, ComfyUI, WebUI, Automatic1111 (A1111), Forge, GLID-3-XL,
  MyPaint, libmypaint, Qt.
- Model and technique names: CLIP, BERT, VAE, LoRA, LCM, CFG, ControlNet, Ultimate SD Upscale.
- Formats and color models: OpenRaster (`.ora`), PNG, RGB, RGBA, HSV, OKLCH, sRGB.
- Interface theme names, such as "IntraPaint Ink".

## Strings that need context

Short strings whose part of speech or meaning depends on where they are used. The translator checks the code that
uses each one before translating it.

- **Noun or verb:** "Fill", "Clear", "Select", "Filter", "Transform", "Outline", "Stroke", "Invert", "Float", "Dock",
  "Paint", "Draw", "Erase", "Merged".
- **Stored values:** some option strings, such as the edit modes, "Masked content" values and resolution rules, are
  also the values saved in config files. Translating them breaks those settings until #297 is fixed, so they stay
  out of translation files until then.
- **Unit and short labels:** "px", "pt", "deg", "x", and the axis and channel letters "W:", "H:", "X:", "R", "G", "B",
  "H", "S", "V", "L", "C".
