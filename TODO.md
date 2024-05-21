# Future development tasks

# Layer system
- Add layer list widget
- Implement layer create/delete/copy/merge in widget/menus
- Implement show/hide layers in widget
- Sketch interaction with layers:
  * Drawing tools should copy content into the active layer
  * Erasers shoule erase layer content to transparency
- Selection/Layer interaction:
  * Add right-click "Send to new layer" option in 
- Selected image generations should be applied to active layer

# Unify the mask and image panels
- Add zoom controls, panning to image panel

# Tool changes:
- rework mask/sketch/pen/eraser buttons into an expandable toolbox section
- Tool modules define tool behavior: MaskCreator doesn't track active tool, just provides interfaces for tools to use
- MaskPanel doesn't handle cursors, just provides an interface for setting the tool cursor/updating it for scale changes.

    * Zoom controls: Switch between full image view and zoomed-in view
    * When zoomed in, show small amount of greyed-out or blurred image outside of margins
- Toolbox:
- Better panel system:
    - Add option to pop out CollapsibleBox content as widget
    - Add option to move CollapsibleBox content into tab

# Other art tools?
    - Add drag tool to move selection window 
    - Selection manipulation
        * cut/paste masked area
        * Tranform masked area
        * Apply color changes, other misc. filters
    - Text editing
    - Prompt-based mask generation

# ControlNet
- Make "use selection as control" the default
    - Don't allow it to be unchecked if no image is selected
    - Automatically uncheck it on image selection
- Add tabs for up to 3X control layers
- Figure out a way to preview module preprocessing
- Get extended controls working in Forge API (PR adding control type endpoint)?
- Add tooltip descriptions for modules and models

# Code cleanup
- Finish type check updates
- Rework window/controller interface to avoid circular dependencies
    * Window creates controller
    * Controller has zero interaction with window besides perhaps being able to close it
- Reorganize everything GLID-3-XL related into new subdirectory
- Finish finding and moving inline constants

# sketch canvas/libmypaint
- Build library binaries for other systems:
    * Windows
    * Mac OS (intel and M1)
    * Raspberry Pi/other ARM-based Linux
    * others?
- Clean up library build process
    * Automate fetching sip dependencies when necessary
    * Integrate sip build into primary makefile (+ qmake?)
- Directly use prebuilt libmypaint?
    - Qt layers over libmypaint aren't that complicated, could be ported without much hassle
    - Biggest pain would be writing new libmypaint bindings that don't need to be built into new libraries
    - Still need to obtain and package library files, test on other systems.

# Config
- Integrate config with SettingsModal
- Finish removing hard-coded labels from UI

# Documentation
- Rewrite README.md for stable-diffusion info
- Create tutorials for common workflows
    * Editing with the sketch layer
    * Filling in details with controlNet + tile
- Create timelapse editing video

# API
- ComfyUI support
- Automatically detect appropriate API/controller/window to use given an endpoint

