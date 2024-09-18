# Development tasks


## Misc. bugs, minor features, and testing:
- Add tool keys to raise/lower opacity, hardness
- Fill tool should support patterns
- Free selection tool: Escape should clear input, left-clicking first point should close.
- Add tool icons to tools toolbar when closed.

## Documentation + Release
- Create example images for README, finish missing sections and improve writing
- Create tutorials for common workflows
    * Editing with the sketch layer
    * Filling in details with controlNet + tile
- New timelapse editing video with improved UI, scripted to showcase features.
- Update Windows libmypaint DLLs
- Add Mac OS, ARM linux libmypaint libraries

## Generated image selection screen
- Non-transitory selection window? 

## Tabs and windows:
- Add shortcut to activate/show/hide each tab

## Help window
- Rich text tutorial content, with images and dynamic hotkeys.

## Tutorial topics
- Visual influence on control: sketching details to guide inpainting
- Generation area control: effects of generation area on content
- Stable-diffusion settings: what do all those options do:
- ControlNet model guides

## Generators:
- Update SD webui instructions with simpler Stability Matrix setup process
  
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
- Tools: open mypaint brush panel
- Tools: open mypaint brush file
- Filters: just throw in whatever fun stuff PIL/CV2 have to offer

### Text tool
* Connect move/pan keys to text layer placement

### Transform tool
- Unique look for origin point (rotate 45 degrees?)
- Toggle switch for scale/rotate modes
- Make sure clear/rotate button is in all panel layouts

### Draw tool
- Add custom brush fill patterns
  
### Smudge tool
- Find some way to mitigate delays when smudging linearly over long distances

### Brush tool
- Pick a few solid defaults for the favorites panel

### Blur tool
Implement using filter instead of libmypaint

### Shape tool
- Circle, polygons with n sides
- stroke+fill controls
- Probably best to just render directly for now, but maybe use with SVGLayer + graphics items in the future

### Stamp tool
- Clone stamp brush, using the same color sampling approach as smudge tool, complete with usual modifiers
- Right-click/ctrl-click to set sample point, visible as graphics item
- Left click to draw, sample point moves with brush strokes
- Sample point content as cursor?

## Possible lurking bugs
Things I never fixed but can no longer reproduce, or that come from external issues:
- Nested layer selection state shown in the layer panel isn't updating properly (recursive active layer update logic in LayerPanel looks fine)
- Txt2Img + ControlNet doesn't seem to work with the image as source. Looks like a webui error, `'StableDiffusionProcessingTxt2Img' object has no attribute 'resize_mode'`, shows up in logs. After trying other settings I can no longer reproduce this, but I don't think it's fixed (input size needs to be a multiple of 32?).
- changing gen. area size still doesn't always sync fully - width changes but not height. Possibly fixed, keep an eye out for it.

# Low priority

# Gradient support
- Select between gradient types, define gradient transition points
- Option to save gradients
- Support in draw, fill, shape, text tools


## sketch canvas/libmypaint
- Cleanup and release libmypaint-qt package
- Get it working with one of those compatibility packages that lets you use the same code with Qt 4-6 and both PyQt and PySide
- Update demo app

## API
- Investigate ComfyUI support
- A1111 script panel support
- A1111 lora/hypernet/etc selection support

## ControlNet
- Figure out a way to preview module preprocessing
- Add tooltip descriptions for modules and models
- Saved preset support, with defaults saved.

## Add legacy AI generators:
- DeepDream
- VQGAN+CLIP


