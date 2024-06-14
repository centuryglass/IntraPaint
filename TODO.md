# Future development tasks

# Bugs
- system color picker issues on xfce

# intermittent, can't reproduce reliably:
- Keep size on brush change not working (possibly a pressure issue?)

1280x800 display issues:
- Text cut off in some tool panels
- Brush icons stacked in larger lists
- default icon zoom cuts off labels

# ImagePanel
- Restore with minimal toolbar, no orientation
- Move pan/zoom to toolbar

# Layers
- variable layer opacity support

# ToolPanel
- Add mask draw/erase hotkey
- Show hotkeys/inputs in UI
- Navigation tool
    - generation area to generation size button
- Selection tool
    - Add select by color/fill select
    - Select inverted option
- Add "shift to draw lines" in brush/mask tools
- Pencil tool:
  - Hard-edged drawing via PixmapCanvas
- Paint bucket tool
- Text tool

# Menus
- Open as layer
- Crop image to content
- open mypaint brush panel
- open mypaint brush file

# Saving
- Find some way to explicitly list .inpt as a file option
- Support saving in formats other than .png (metadata fixes?)

# LayerPanel
- drag+drop layer reordering
- layer locking

# Layout
- Control Panel cleanup with FormLayout
- Add click+drag resizing to CollapsibleBox
- Add option to pop out CollapsibleBox content as window

# Generated image selection widget
- Add context menu for selections:
    * Select
    * Send to new layer
    * Save as
- Add focused layer label to bars
- Add mouse navigation hints to bars

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

# Config
- Integrate config with SettingsModal
    * Finish redefining A1111 settings via config class
    * Settings modal loading based on config
    * Integrate AppConfig with settings

# Documentation
- Rewrite README.md for stable-diffusion info
- Create tutorials for common workflows
    * Editing with the sketch layer
    * Filling in details with controlNet + tile
- Create timelapse editing video

# Other
- ComfyUI support
- A1111 script panel support
- Rework mode settings:
    * Automatically detect based on server URL
    * Add "No image generation" mode
    * Let web modes start when the server is down
    * Support login/URL changes outside the init process
    * Improve controls for login and setting server URL
- Profiling and performance improvements
