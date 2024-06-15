# Development tasks

# Bugs
- Transparent layers show up in generated images
- system color picker issues on xfce

## intermittent, can't reproduce reliably:
- Keep size on brush change not working (possibly a pressure issue?)
- Selection tool reverts to 1px

## 1280x800 display issues:
- Text cut off in some tool panels
- Brush icons stacked in larger lists
- default icon zoom cuts off labels

# General interface
- Implement QGraphicsItem item handle control with support for translate, scale, rotate
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
- New layer panel button icons
- Double click/right click+"rename" to change layer names
- variable layer opacity support
- Alternate layer composition modes
- Layer locking
- Transparency locking
- Drag and drop reordering
- Rework selection layer panel item
- Support for extended un-rastered states as GraphicsItems

# Stability
- Unit testing for critical modules
- Crash handling: have a parent process monitor for crashes, cache data, save as .inpt on crash

# Menus
- Separate "Save" and "Save as"
- Open as layers
- Find some way to explicitly list .inpt as a file option
- Support saving in formats other than .png (metadata fixes?)
- Crop image to content
- open mypaint brush panel
- open mypaint brush file
- Filters: just throw in whatever fun stuff CV2 has to offer

# Config
- Hide startup warnings
- Preview at final resolution
- Show selection in previews
- Automatic metadata updates

# Tools
## Image gen area tool
- generation area to generation size button
- generation size controls

## Selection tool
- Redo icon
- Change default hotkey
- Add mask draw/erase hotkey
- Add select by color/fill select
- Allow selection outside of image bounds

## Transform tool
- List transformations as pixel widths and positions, not as offsets
- Fix rotation center point issues

## Pencil tool
- Hard-edged drawing via PixmapCanvas
  
## Fill tool
cv2 probably has good support for this.
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

