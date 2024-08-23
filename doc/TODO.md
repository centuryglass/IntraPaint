# Development tasks

# Files
- ORA SVG support

# General interface
- Test GLID with tab interface

# Layers
- support for missing OpenRaster composition modes
- Add selection layer back to layer panel
- Add "merge group" and "merge all" options
- Add "convert to image" option to text layers

# Menus
- open mypaint brush panel
- open mypaint brush file
- Filters: just throw in whatever fun stuff PIL/CV2 have to offer
- Enable/disable menus based on arbitrary context, not just app state


# Tools
## Image gen area tool
- generation area to generation size button
- generation size controls
- fix gen area tool aspect ratio constraints
- Fixed aspect ratio should be based on generation size aspect ratio
- Add checkboxes to limit generation size to edit size, force restricted aspect ratio.
- Fix issues with gen area recalculation when loading a smaller image.


## Lasso tool
- Vector-based selection tool

## Transform tool
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
- fix mouse placement arrows

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
- Figure out a way to preview module preprocessing
- Get extended controls working in Forge API (PR adding control type endpoint)?
- Add tooltip descriptions for modules and models

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