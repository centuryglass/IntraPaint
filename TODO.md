# Development tasks

- ORA SVG support

# General interface
- When scaling, center scale on mouse position
- Rework mode settings:
    * Support login/URL changes outside the init process
    * Improve controls for login and setting server URL

# Layers
- Layer locking
- Transparency locking

# Menus
- Support saving in formats other than .png (metadata fixes?)
- Crop image to content
- open mypaint brush panel
- open mypaint brush file
- Filters: just throw in whatever fun stuff PIL/CV2 has to offer

# Config
- Hide startup warnings option
- Automatic metadata updates

# Tools
## Image gen area tool
- generation area to generation size button
- generation size controls

## Selection fill
- fill based on selection layer only
- floodfill with alpha support

## Selection tool
- Add mask draw/erase hotkey

## Transform tool
- Better rotation arrows
- Unique look for origin point
- Toggle switch for scale/rotate modes

## Pencil tool
- Hard-edged drawing via PixmapCanvas
- Variable opacity/hardness sliders
- Pressure controls
  
## Fill tool
cv2 or PIL probably have good support for this.
- floodfill with alpha support
  
## Brush tool sub-tools
Alternate brush tools that filter for certain brush types
- Erase tool
- Smudge tool
- Blur tool

## Canvas tools
- Draw lines on shift

# Text tool
- Font selection
- Size setting

# Shape tool
- Circle, polygons with n sides
- stroke+fill controls

# Generated image selection widget
- Add context menu for selections:
    * Select
    * Send to new layer
    * Save as file
- Non-transitory selection tab?

# ControlNet
- Make "use generation area as control" the default
    - Don't allow it to be unchecked if no image is selected
    - Automatically uncheck it on image selection
- Add tabs for up to 3X control layers
- Figure out a way to preview module preprocessing
- Get extended controls working in Forge API (PR adding control type endpoint)?
- Add tooltip descriptions for modules and models

# Code cleanup
- Localization support

# sketch canvas/libmypaint
- Cleanup and release libmypaint-pyqt package

# Documentation + Release
- Rewrite README.md for stable-diffusion info
- Create tutorials for common workflows
    * Editing with the sketch layer
    * Filling in details with controlNet + tile
- Create timelapse editing video
- Wizard for automatic stable-diffusion setup
- Write scripts for generating release builds on all platforms
- Update Windows libmypaint DLLs
- Add Mac OS, ARM linux libmypaint libraries

# API
- Investigate ComfyUI support
- A1111 script panel support
- A1111 lora/hypernet/etc selection support
- A1111 PR for updating saved styles

# Legacy generators
- DeepDream
- VQGAN+CLIP
