# Development tasks

## Before next release:
- Basic workflow tutorials (< 1 day)
- Final timelapse video (< 5 days)
- Upscale: make new layer, scale up existing layers

## Priority issues:
- add 'sample merged' option to smudge, stamp, and filter tools
- when selecting generated imagery tries to insert into a locked layer, an error is shown but the selection is lost
- RGBA filter: alpha not working with filter tool, or when constrained to selection
- Filter previews really slow on large images, are they not being scaled?
- Make sure non-ai scaling is always possible via PIL scaling modes

## Timelapse video

### Prompt component ideas: 
- Fauvism, Cubo-Futurism, Glitch Art, Post-Impressionism, outsider art, mosaic, papercraft


### Step-by-step process:
- Script this to make use of every tool.
- Text tool: insert process description notes directly into timelapse footage.
- Text-to-Image: generate reference images
- Transform tool: arrange reference images outside of image border
- Brush tool (pencil): initial image sketch and planning.
- Filter tool (blur): hide sketch details before adding line art.
- Draw tool: rough line-art
- Shape tool, brush tool, smudge tool: rough background painting
- Image-to-Image: refine backgrounds
- Inpainting, ControlNet scribble module: refine line-art
- Brush tool (acrylics): 

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

## Possible lurking bugs
Things I never fixed but can no longer reproduce, or that come from external issues:
- Nested layer selection state shown in the layer panel isn't updating properly (recursive active layer update logic in LayerPanel looks fine)
- changing gen. area size still doesn't always sync fully - width changes but not height. Possibly fixed, keep an eye out for it.
- smudge tool: short brush strokes being lost (only on old laptop, perhaps?)


# Lower priority/post-release:

## General concerns and ideas
* Solid color selection layer is less than ideal, even with a configurable color.  Maybe some sort of animated fill?
* Fill and color fill algorithms are not ideal, look into measuring color differences with a perceptual algorithm instead of plain distance
  - Adaptive thresholding and texture fill are possibilities. scikit provides useful tools for this.
* Do more profiling, performance is adequate but there's still some noticeable lag in a few places
* TabBar should have some mechanism for scrolling so the UI doesn't break when you turn up the tab bar shortcut count
* There should be a mechanism for sending UI tabs to new windows
* Color picker could use other options: RGB cube, color wheel, OKLab perceptual color
* Switch color picker to horizontal tabs

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

## libmypaint
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


