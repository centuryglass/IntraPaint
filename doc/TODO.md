# Development tasks

## Before next release:
- Add tool icons, generate button, to toolbar when panel isn't showing. (1 day)
- Add "resize image to contents" option (key already exists, I think) (< 15 minutes)
- Layer right-click menus: add "select content" option (< 15 minutes)
- Add shortcut to activate/show/hide each tab  (< 1 hour)
- Improve empty tab bar appearances (< 1 hour)
- Update SD webui instructions with simpler Stability Matrix setup process (copy from release page) (< 15 minutes)
- Pick a few solid defaults for the mypaint brush favorites panel  (< 15 minutes)
- implement shape tool (< 2 days)
- Connect move/pan keys to text layer placement  (< 1 hour)
- transform tool: make sure clear/rotate button is in all panel layouts  (< 30 minutes)
- Finish README cleanup and examples (< 1 day)
- Basic workflow tutorials (< 1 day)
- Final timelapse video (< 5 days)

## Timelapse video: using latest interface
Scripted to make use of every tool, in-video text explaining what I'm doing

## Documentation + Release
- Create example images for README, finish missing sections and improve writing
- Prioritize examples showing the actual interface over standalone outputs
- Create tutorials for common workflows
    * Editing with the sketch layer
    * Filling in details with controlNet + tile
- New timelapse editing video with improved UI, scripted to showcase features.
- Update Windows libmypaint DLLs
- Add Mac OS, ARM linux libmypaint libraries


## Tutorial topics
- Visual influence on control: sketching details to guide inpainting
- Generation area control: effects of generation area on content
- Stable-diffusion settings: what do all those options do:
- ControlNet model guides

### Shape tool
- Circle, polygons with n sides
- stroke+fill controls
- Probably best to just render directly for now, but maybe use with SVGLayer + graphics items in the future

## Possible lurking bugs
Things I never fixed but can no longer reproduce, or that come from external issues:
- Nested layer selection state shown in the layer panel isn't updating properly (recursive active layer update logic in LayerPanel looks fine)
- Txt2Img + ControlNet doesn't seem to work with the image as source. Looks like a webui error, `'StableDiffusionProcessingTxt2Img' object has no attribute 'resize_mode'`, shows up in logs. After trying other settings I can no longer reproduce this, but I don't think it's fixed (input size needs to be a multiple of 32?).
- changing gen. area size still doesn't always sync fully - width changes but not height. Possibly fixed, keep an eye out for it.


# Lower priority/post-release:

## General concerns:
* Solid color selection layer is less than ideal, even with a configurable color.  Maybe some sort of animated fill?
* Fill and color fill algorithms are not ideal, look into measuring color differences with a perceptual algorithm instead of plain distance
* Do more profiling, performance is adequate but there's still some noticeable lag in a few places

## Help window
- Rich text tutorial content, with images and dynamic hotkeys.

### "Isolate" layer group attribute:
- With isolate:
  * Render all group layers to a transparent group image
  * Render the group image to the backdrop using group settings.
- Without isolate:
  * Render all group layers to a group image that's a copy of the backdrop
  * (?) also render all layers to a transparent mask image
  * (?) draw the mask over the group using DestinationIn to crop out backdrop content that doesn't overlap with the group content
  * Render the group image to the backdrop using group settings.


## ORA format: Preserve information from other programs
- SVG layers:
  * Create SVGLayer class that functions as imagelayer, but preserves the original SVG file
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
- Add custom brush fill patterns
  
### Smudge tool
- Find some way to mitigate delays when smudging linearly over long distances:
- Try numpy compositing again now that the algorithm's worked out (see ImagePanel alpha-lock implementation)
- When the drawing buffer has huge numbers of pending operations, see if we can defer some of them to give the window time to update

### Stamp tool
- Clone stamp brush, using the same color sampling approach as smudge tool, complete with usual modifiers
- Right-click/ctrl-click to set sample point, visible as graphics item
- Left click to draw, sample point moves with brush strokes
- Sample point content as cursor?

## sketch canvas/libmypaint
- Import latest code/changes
- Get the demo app working again
- Port to qtpy for maximum compatibility
- Figure out Pip release process, libmypaint bundling

## Generated image selection screen
- Non-transitory selection window?

# Gradient support
- Select between gradient types, define gradient transition points
- Option to save gradients
- Support in draw, fill, shape, text tools

## ComfyUI support:
Looks like the ComfyUI API is websocket-based instead of REST, and the client needs to be aware of ComfyUI's node graph structure. This is manageable, but requires a totally different approach and a lot of work. Defer unless a lot of people show interest. 

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


