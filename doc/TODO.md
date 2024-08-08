# Development tasks

# Bugs
- '.png' auto-appended onto '.ora' paths sometimes


# Files
- ORA SVG support
- Move non-standard ORA data to new xml file
- Add layer locks to ORA extended data
- Support saving in formats other than .png (metadata fixes?)
- Warn when saving would merge layers, discard metadata, discard alpha

# General interface
- When scaling, center scale on mouse position
- Warning modal with "don't warn me again checkbox"
- Improve appearance of draggable tabs
- Add right click menu to move tabs to any bar
- Test GLID with tab interface

# Layers
- Transparency locking: adjust for transformation offset (temp disable when resizing/cropping layers, probably)
- support for missing OpenRaster composition modes
- Add selection layer back to layer panel
- Add "merge group" and "merge all" options

# Menus
- open mypaint brush panel
- open mypaint brush file
- Filters: just throw in whatever fun stuff PIL/CV2 have to offer
- Enable/disable menus based on arbitrary context, not just app state

# Config
- Hide startup warnings option
- Automatic metadata update option

# Tools
## Image gen area tool
- generation area to generation size button
- generation size controls
- fix gen area tool aspect ratio constraints
- Fixed aspect ratio should be based on generation size aspect ratio
- Add checkboxes to limit generation size to edit size, force restricted aspect ratio.
- Fix issues with gen area recalculation when loading a smaller image.

## Selection tool
- Add mask draw/erase hotkey

## Lasso tool
- Vector-based selection tool

## Transform tool
- Why do angles look off when rotating scaled layers?
- Unique look for origin point
- Toggle switch for scale/rotate modes

## Pencil tool
- Hard-edged drawing via PixmapCanvas
- Variable opacity/hardness sliders
- Pressure controls
  
## Brush tool sub-tools
Alternate brush tools that filter for certain brush types
- Erase tool
- Smudge tool
- Blur tool

# Text tool
- Font selection
- Size setting

# Shape tool
- Circle, polygons with n sides
- stroke+fill controls

# Generated image selection screen
- Add context menu for selections:
    * Select
    * Send to new layer
    * Save as file
- Non-transitory selection tab?

# ControlNet
- Add vertical layout mode
- Figure out a way to preview module preprocessing
- Get extended controls working in Forge API (PR adding control type endpoint)?
- Add tooltip descriptions for modules and models

# Code cleanup
- Localization support: continue removing hard-coded strings

# sketch canvas/libmypaint
- Cleanup and release libmypaint-pyqt package

# Documentation + Release
- Rewrite README.md for stable-diffusion info
- Create tutorials for common workflows
    * Editing with the sketch layer
    * Filling in details with controlNet + tile
- Create timelapse editing video
- Update Windows libmypaint DLLs
- Add Mac OS, ARM linux libmypaint libraries

# API
- Investigate ComfyUI support
- A1111 script panel support
- A1111 lora/hypernet/etc selection support
- A1111 PR for updating saved styles

# Help window
- Rich text tutorial content, with images and dynamic hotkeys.

# Legacy generators
- DeepDream
- VQGAN+CLIP

# Tutorial topics
- Visual influence on control: sketching details to guide inpainting
- Generation area control: effects of generation area on content
- Stable-diffusion settings: what do all those options do:
- ControlNet model guides