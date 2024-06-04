# Future development tasks

# Bugs
- Keep size on brush change isn't working
- "Time is running backwards" errors
- rare: brush input stuck going to selection 
- 1px draw mode not reverting until next stroke finishes
- Weird issue with canvas/layer image corruption (copy to layer/navigation conflict?)

# Input
- Configurable hotkeys

# ImagePanel
- Restore with minimal toolbar, no orientation
- Move pan/zoom to toolbar

# Layers
- Combine layer movement in undo stack.
- automatic layer resizing when copying into areas outside of bounds
- variable layer opacity support

# ToolPanel
- Show hotkeys/inputs in UI
- Navigation tool
    - add "select all" button
    - selection to generation size
    - selection to full image
- Mask tool
    - Move 'inpaint masked only' widgets here
    - Add select by color/fill select
- Add "shift to draw lines" in brush/mask tools
- Pencil tool:
  - Hard-edged drawing via PixmapCanvas
- Paint bucket tool
- Text tool
- 
- 

# Menus
- Add layer menu duplicating layer panel options
- edit menu: cut/copy/paste using mask and active layer
- Open as layer
- Save with layers,mask,metadata
- open mypaint brush panel
- open mypaint brush file

# LayerPanel
- drag+drop layer reordering
- layer locking

# Layout
- Fix brushPanel layout woes
- Panel cleanup with FormLayout
- Add click+drag resizing to CollapsibleBox
- Add option to pop out CollapsibleBox content as window
- Add option to move CollapsibleBox content into tab
- Fix BrushPanel list layout issues

# Sample selection widget
- Add context menu for selections:
    * Select
    * Send to new layer
    * Save as
- Nicer selection page design:
    * Use an actual layout
    * Right-click for zoom
    * arbitrary zoom via graphicsView?

# ControlNet
- Make "use selection as control" the default
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
- Use a proper logging system
- Localization support

# sketch canvas/libmypaint
- Cleanup and release libmypaint-pyqt5 package

# Config
- Integrate config with SettingsModal
    * Finish redefining A1111 settings via config class
    * Settings modal loading based on config
    * Integrate AppConfig with settings
- Configurable hotkeys

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
