# Development tasks

# v.1.1.0 Plans: ComfyUI support and API expansions
## Goals:
- Provide support for the ComfyUI API as an alternate image generator choice, keeping feature-parity with WebUI implementations across all features:
  * text-to-image, image-to-image, and inpainting through the Image Generation panel.
  * LoRA model loading from prompts
  * ControlNet support through the ControlNetPanel.
  * Basic AI upscaling, latent upscaling, through the ImageScaleModal.
  * CLIP interrogate support (if possible)
- Clean up WebUI API code, making it easier to handle required compatibility conversions, and to make it easier to support more API features in the future, especially custom scripts.
- Add "extras" tab to the Image Generation panel, with at least a few API-specific options present
- Reorganize stable-diffusion settings, dividing by generator when necessary, and condensing all of them into a single page. 

## Remaining tasks:
ComfyUI support:
- ControlNet type constants are incomplete: regular expressions need updates to properly sort the whole list of ComfyUI options.
- Implement a basic upscaling workflow, add in generator and webservice classes, test with ImageScaleModal.
- As above, but a full latent upscaling workflow, using the ComfyUI version of the ultimate upscaler script.
- CLIP skip still needs to be implemented.
- Add the image generation Extras tab, with (at least) the following controls:
  * Model config file selection
  * a "Free memory" button

WebUI parity:
- Nore testing: make sure all API features still work as expected, especially upscaling.
- Come up with a standardized system for widgets that send config changes like the model selection dropdown does
- Add the image generation Extras tab, with the following controls:
  * CLIP-skip
  * "Variation seed" and similar
  * Tiling checkbox
  * Face restore checkbox

Documentation:
- Document the ComfyUI installation process within the generator selection window.
- Make sure documentation has a proper local setup section, (include python3.11 requirement)
- Add expanded stable-diffusion installation section, fully covering all options, including ComfyUI
- Document the differences between Automatic1111, Forge, and ComfyUI, as they apply to IntraPaint.
- Update labeled screenshots for the generator panel, controlnet panel, and stable-diffusion settings
- Create CHANGELOG.md in docs folder

Misc. cleanup:
- Add a warning message to console output at the start when running under Python<3.11

Low priority, possibly post-release:
- Expand WebUI latent upscaling support, and add support for the various "highres. fix" options.
- Using a custom node, implement the ComfyUI "interrogate" workflow.
- Add queue support for the WebUI generator/API to keep it in parity with ComfyUI
- ComfyUI inpainting model support: This requires some significant (but not unmanageable) workflow changes.
- ComfyUI tiled VAE support:  The ComfyNode classes are implemented, I just need to add UI controls to activate them and set the tile size, probably in image generation extras.
- Figure out IpAdapter in ComfyUI:  I suspect that also requires a new workflow.

## What's already done:
ComfyUI support:
- Created the api.comfyui.nodes package, diffusion_workflow_builder.py for dynamically constructing the ComfyUI workflow.
- Created comfyui_webservice.py to handle API access including applying cached parameters, fully implemented and mostly tested.
- Created sd_comfyui_generator.py to use the API for image generation tasks.
- Added the websockets-client library to handle ComfyUI progress monitoring.
- Text-to-image, image-to-image, inpainting, and ControlNet all tested and confirmed working, with only minor bugs left to resolve.
- "inpaint full res" implemented by pre-cropping and scaling image content in SDComfyUIGenerator.

UI Changes (Image Generation tab):
- Minor adjustments made to allow this to work with both WebUI and ComfyUI generators:
  * "interrogate" button removed in ComfyUI for now
- Added model selection dropdown
- Tab now supports an inner "Extras" tab that can be used for generator-specific options

ControlNet:
- Added ControlNetPreprocessor class for tracking a preprocessor option's name and valid parameters in a standardized way
- Added ControlNetCategoryBuilder class for tracking valid preprocessor/model pairings in a standardized way.
- Added hard-coded preprocessor parameters to use with the Forge WebUI, which doesn't send preprocessor parameters.
- Added hard-coded preprocessor/model category pairings with regex support to allow ControlNetCategoryBuilder to work in Forge and ComfyUI instead of just A1111.
- Removed most of the Cache entries for ControlNet data, since a lot of that is API specific, and can all be managed by the ImageGenerator anyway.
- Adjusted ControlNetPanel to use new standardized data types, simplifying a lot of code and enabling ComfyUI support.

WebUI compatibility and cleanup:
- Added and applied TypedDict classes defining all API request and response formats, so that code accessing API dicts will be properly validated.
- Added diffusion_request_body.py to automatically assemble cached parameters into a valid request body, with support for parameters IntraPaint currently ignores.
- A1111Webservice methods added to provide ControlNet preprocessors, types using new standardized formats.
- ControlNet preprocessor resolution, balance mode, and resize mode are now shown properly in the ControlNet panel

Misc. cleanup:
- Updated minimum required Python version to 3.11, removed some workarounds that were previously present to allow use with earlier versions.
- Removed Set, Dict, List, Tuple imports from typing that are no longer required.
- Adjust various dropdown list sizing properties so that the UI doesn't get distorted if the API sends an extremely long option.


---

## Possible lurking bugs
Things I never fixed but can no longer reproduce, or that come from external issues:
- Nested layer selection state shown in the layer panel isn't updating properly (recursive active layer update logic in LayerPanel looks fine)
- changing gen. area size still doesn't always sync fully - width changes but not height. Possibly fixed, keep an eye out for it.
- Weird bug where every new image loads with a seemingly-arbitrary transformation pre-applied.  Maybe a bug with layer group transforms? Haven't been able to reproduce.


## General concerns and ideas
* Solid color selection layer is less than ideal, even with a configurable color.  Maybe some sort of animated fill?
* Fill and color fill algorithms are not ideal, look into measuring color differences with a perceptual algorithm instead of plain distance
  - Adaptive thresholding and texture fill are possibilities. scikit provides useful tools for this.
* Do more profiling, performance is adequate but there's still some noticeable lag in a few places
* TabBar should have some mechanism for scrolling so the UI doesn't break when you turn up the tab bar shortcut count
* There should be a mechanism for sending UI tabs to new windows
* Color picker could use other options: RGB cube, color wheel, OKLab perceptual color
* Switch color picker to horizontal icon tabs
* Transform tool: clicking a layer should activate it, or there should be an option to do that at least.
* ImageViewer: add sidebar rulers
* add 'sample merged' option to smudge, stamp, and filter tools
* A lot of unnecessary complexity could probably be removed from undo history management if I just used QUndoStack instead of my own implementation.  It'd take a fair bit of refactoring though, so it probably isn't a priority 

## Minor bugs:
- Some of the MyPaint brushes are clearly not working. Cross-test on Windows and with actual MyPaint, refer to images in examples folder.
- LayerPanel layout still shows some odd glitches on occasion
- "crop layer to selection": overlap handling on layer groups may still have some issues with groups overlapping the selection boundary

---

## ComfyUI support:
This isn't really useful to me personally, but it definitely expands my potential audience. 

Looks like the ComfyUI API is websocket-based instead of REST, and the client needs to be aware of ComfyUI's node graph structure.

### Resources:
Basic example: (https://github.com/comfyanonymous/ComfyUI/blob/master/script_examples/basic_api_example.py)
Krita extension's implementation: (https://github.com/Acly/krita-ai-diffusion/blob/main/ai_diffusion/comfy_client.py)

### Questions to answer
- How do I get the list of available nodes?
- How do I change the active workflow, or read the current workflow?
- Can I install new nodes through the API?
- Can I switch models through the API?
- How can I access the lists of LoRAs/ControlNet models/etc.?
- Is CLIP interrogate supported?

### Steps to implement (bare minimum):
1. ~~Update my ComfyUI installation and the Krita ComfyUI plugin, make sure all of it still works on my system.~~
2. ~~Install websockets_client, add to requirements.txt~~ No longer needed, there's a perfectly good REST api now.
3. ~~Create src/api/comfyui_webservice.py, implement basic connection and authentication.~~ Not really much to do regarding auth.
4. ~~Implement bare minimum set of necessary workflows: txt2img, img2img, inpainting, with progress checking~~
5. ~~Create src/ui/panel/generators/sd_comfyui_panel.py, or refactor sd_webui_panel.py to ensure it works with both SD providers.~~
6. ~~Create src/controller/image_generation/sd_comfyui_generator.py, implement the usual methods for connection, setup, inpainting, etc.~~
7. Implement local handling for "inpaint full res" in ComfyUI generator
8. Test to confirm all the basic tasks work.
9. Update documentation to describe configuration, including rich text fields used in GeneratorSetupWindow

### Follow-up: ControlNet
1. Add methods to ComfyUiWebservice to load preprocessors and models,
2. have SdComfyUiGenerator use those methods to load data into Cache.CONTROLNET_MODELS and Cache.CONTROLNET_MODULES on activation.
3. Convert loaded data to the same format A1111 uses, to avoid needing to change ControlNetPanel
   - Updating ControlNetPanel to support both formats or creating ComfyControlNetPanel are also options, but probably best avoided unless the structure is radically different.
4. Update SdComfyUiGenerator to load the ControlNet panel the same way that SdWebUiGenerator does
5. Update ComfyUIWebservice txt2img/img2img/inpaint methods to properly add data from Cache.CONTROLNET_ARGS_0/CONTROLNET_ARGS_1/CONTROLNET_ARGS_2 to the requests

### Follow-up: Upscaling
1. Investigate options for non-latent upscalers via ComfyUI, or perhaps through alternate providers.
2. ComfyUiWebservice: Implement ControlNet tiled upscaling with optional support for the ComfyUI version of the SD Ultimate Upscale script.
3. Update SdComfyUiGenerator to load options and set them as Cache.UPSCALE_METHOD options on activation. 
4. Implement SdComfyUiGenerator.upscale

### Follow-up: interrogate
1. Assuming this feature is available through the ComfyUI API, implement it in ComfyUiWebservice
2. Implement SdComfyUiGenerator interrogate, connect it to the prompt state the same way SdWebUiGenerator does.

### Follow-up: settings
1. See which existing AppConfig settings in the Stable-Diffusion category can be used, and apply them in ComfyUIWebservice wherever possible.
2. Review available options to see if there's any new settings I should add to that category.
3. Implement init_settings/refresh_settings/update_settings/unload/settings
4. If a settings API is available, implement an equivalent to src/config/a1111_config.py to handle saving and loading ComfyUI settings.

---

## Help window
- Rich text tutorial content, with images and dynamic hotkeys.

## ORA format: Preserve information from other programs
- SVG layers:
  * Create SVGLayer class that functions as image layer, but preserves the original SVG file
  * Disable painting+destructive changes, use "convert to ImageLayer" logic the same way TextLayer does
- Check for and preserve non-standard image and layer tags from the original .ora file (also, the "isolate" tag).
- Check for and preserve non-standard files
- Text layers, svg approach:
  * Write TextRect serialization, deserialization functions that write to svg xml
  * On save: serialize to .svg, but also write a backup .png
  * On load: attempt to parse as text.  If the text doesn't parse or match the .png copy, fallback to image loading.
- Text layers, .ora extension approach:
  * As above, but serialize and write to the xml data extension file instead
  * Possibly better than the .svg approach, this route won't break the image in other editors if loaded on a system that's missing fonts. Decide based on ease of .svg serialization.

## Layer interface
- Add selection layer back to layer panel
- Layer multi-select: Topmost selected layer is active, all others only selected for the sake of bulk copy/grouping/merge/delete
- Add "merge group" and "merge all visible" options

## Menus
- Filters: just throw in whatever fun stuff PIL/CV2 have to offer

### Draw tool
- Add custom brush fill patterns, alternate brush shapes
  
### Smudge tool
- Find some way to mitigate delays when smudging linearly over long distances:
- When the drawing buffer has huge numbers of pending operations, see if we can defer some of them to give the window time to update

## libmypaint
- Update Windows libmypaint DLLs
- Add macOS (intel and M1), ARM linux libmypaint libraries
- Import latest code/changes
- Get the demo app working again
- Port to qtpy for maximum compatibility
- Figure out Pip release process, libmypaint bundling

## Generated image selection screen
- Non-transitory selection window? Would be nice to see past options, at least the ones from the last batch.

# Gradient support
- Select between gradient types, define gradient transition points
- Option to save gradients
- Support in draw, fill, shape, text tools


## A1111/Forge api extensions
- More support for custom scripts, script UI panels
- A1111 lora/hypernet/etc selection support

## ControlNet
- Figure out a way to preview module preprocessing
- Add tooltip descriptions for modules and models
- Saved preset support, with defaults saved.

## Legacy AI generators:
It would be cool to add support for these, if only for the nostalgia.  Probably best done with standalone server programs with minimal REST interfaces.
- DeepDream
- VQGAN+CLIP


