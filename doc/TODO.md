# Development tasks

- Create example images for README, finish missing sections and improve writing
- New image modal: bg color picker

# Color picker component:
- Alternate palette options - all custom colors?
- Standalone color picker window
- Selected color preview on palette-only screen, draggable to custom colors
- Condensed layout?
- Save/load custom palettes?

# Misc. bugs and testing:
- Test GLID with tab interface

## Documentation + Release
- Rewrite README.md for stable-diffusion info
- Create tutorials for common workflows
    * Editing with the sketch layer
    * Filling in details with controlNet + tile
- New timelapse editing video with improved UI, scripted to showcase features.
- Update Windows libmypaint DLLs
- Add Mac OS, ARM linux libmypaint libraries

## Generated image selection screen
- Add context menu for selections:
    * Select
    * Send to new layer
    * Save as file
- Non-transitory selection window? 

## Tabs and windows:
- Add shortcut to activate/show/hide each tab
- Hide tab panel resize bars unless the panel is non-empty

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
- Add icons to layers to identify their type (image, group, text, vector (eventually))
- Layer multi-select: Topmost selected layer is active, all others only selected for the sake of bulk copy/grouping/merge/delete
- Add "merge group" and "merge all visible" options
- Add "convert to image" (flatten?) option to text layers

## Menus
- Tools: open mypaint brush panel
- Tools: open mypaint brush file
- Filters: just throw in whatever fun stuff PIL/CV2 have to offer
- Enable/disable menus based on arbitrary context, not just app state

## Tools
### Image gen area tool
- generation area to generation size button
- generation size controls
- fix gen area tool aspect ratio constraints
- Fixed aspect ratio should be based on generation size aspect ratio
- Add checkboxes to limit generation size to edit size, force restricted aspect ratio.
- Fix issues with gen area recalculation when loading a smaller image.

### Text tool
* Connect move/pan keys to text layer placement

### Polygonal lasso tool
- Vector-based selection tool
- Add EditablePath QGraphicsItem:
  * add_point method add a point to the end of the path, present in the scene as a TransformHandle
  * paint method draws lines between appropriate handles
  * close_path method connects first and last points
  * polygon property returns points as a QPolygonF
- Controls:
  * Click to start a new polygon or add a point to an existing one
  * Drag handles to reposition
  * Close path (click first point when there's more than two points? or should it be double-click?)
  * Enter/return: close path if there's more than two points
  * escape: discard path
  * undo/redo: should hold individual point changes
- Panel:
  * snapping controls, maybe?

### Transform tool
- Unique look for origin point (rotate 45 degrees?)
- Toggle switch for scale/rotate modes
- Make sure clear/rotate button is in all panel layouts
- Move panel into src.ui.panel.tool_control_panels

### Draw tool
- Fix erasing, current implementation is erasing to solid black
- For each brush stroke, track changed pixels and remove/control overlap
- Add hardness slider, opacity slider
- Add brush fill patterns
- When tablet input is detected: add size/hardness/opacity pressure toggles
  
### Brush tool
- Pick a few solid defaults for the favorites panel
- Add a way to load in more brushes from the user data directory

### Brush tool variants:
- Implement using MyPaint canvas with a fixed brush: Erase tool, Smudge tool, Blur tool
- Identify which MPBrush parameters are most significant for each of these, provide access through the control panel

### Shape tool
- Circle, polygons with n sides
- stroke+fill controls
- Probably best to just render directly for now, but maybe use with SVGLayer + graphics items in the future

## Possible lurking bugs
Things I never fixed but can no longer reproduce:
- Nested layer selection state shown in the layer panel isn't updating properly (recursive active layer update logic in LayerPanel looks fine)

# Low priority

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


