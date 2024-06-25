# Development tasks

# Bugs
- copy/paste issues in small layers
- disconnect between EDIT_SIZE in config and layer stack gen area

## intermittent, can't reproduce reliably:
- Keep size on brush change not working (possibly a pressure issue?)
- Selection tool reverts to 1px, usually after picking image option


# General interface
- Control Panel cleanup with FormLayout
- Add click+drag resizing to CollapsibleBox
- Add option to pop out CollapsibleBox content as window
- When scaling, center scale on mouse position
- Rework mode settings:
    * Add "No image generation" mode
    * Let web modes start when the server is down
    * Support login/URL changes outside the init process
    * Improve controls for login and setting server URL

# Layers
- Drag and drop reordering
- layer name changes should save on layer change
- Layer locking
- Transparency locking
- Rework selection layer panel item
- Support for extended un-rastered states as GraphicsItems

# Stability
- Unit testing for critical modules
- Crash handling: have a parent process monitor for crashes, cache data, save as .inpt on crash

# Menus
- Open as layers
- Find some way to explicitly list .inpt as a file option
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
- fix ctrl-click panning

## Selection tool
- Add mask draw/erase hotkey
- Add select by color/fill select
- Allow selection outside of image bounds
- Optimize outline detection: pixmap canvas should be able to track outlines,
  only use CV2 for dynamic changes

## Transform tool
- Misc. edge cases causing transforms to be discarded
- Add "apply changes" button
- Better rotation arrows
- Unique look for origin point
- Toggle switch for scale/rotate modes

## Pencil tool
- Hard-edged drawing via PixmapCanvas
- Variable opacity/hardness sliders
- Pressure controls
  
## Fill tool
cv2 or PIL probably have good support for this.
- Color control syncs with brush color
- Adjustable threshold
- Toggle: active layer only/all layers
- Toggle: preserve transparency
  
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
- Rework window/controller interface to avoid circular dependencies
    * Window creates controller
    * Controller has zero interaction with window besides perhaps being able to close it
- Localization support

# sketch canvas/libmypaint
- Cleanup and release libmypaint-pyqt5 package

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
- A1111 saved style support

