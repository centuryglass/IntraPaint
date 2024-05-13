# Future development tasks

# ControlNet
- Make "use selection as control" the default
    - Don't allow it to be unchecked if no image is selected
    - Automatically uncheck it on image selection
- Add tabs for up to 3X control layers
- Figure out a way to preview module preprocessing
- Get extended controls working in Forge API (PR adding control type endpoint)?
- Add tooltip descriptions for modules and models

# sketch canvas/libmypaint
- Update qt bindings to work with an unmodified version of the latest libmypaint
- Pull image data into canvas to allow smudging, blurring, etc.
- Build library binaries for other systems:
    * Windows
    * Mac OS (intel and M1)
    * Raspberry Pi/other ARM-based Linux
    * others?
- Clean up library build process
    * Automate fetching sip dependencies when necessary
    * Integrate sip build into primary makefile (+ qmake?)
- Rewrite C++ layers to allow multiple canvases
- Apply sketch directly to image (with undo!)
- Add fill tool

# Config
- Add categories, tooltips to all config options
- Integrate config with SettingsModal

# Interface
- Unify the mask and image panels
    * Zoom button: Switch between full image view and zoomed-in view
    * When zoomed in, show small amount of greyed-out or blurred image outside of margins
- Add drag tool to move selection window 

# Documentation
- Rewrite README.md for stable-diffusion info
- Create tutorials for common workflows
    * Editing with the sketch layer
    * Filling in details with controlNet + tile
- Create timelapse editing video

# API
- ComfyUI support
- Automatically detect appropriate API/controller/window to use given an endpoint

# Other art tools?
    - Layers
    - Selection manipulation
        * cut/paste masked area
        * Tranform masked area
        * Apply color changes, other misc. filters
    - Text editing
    - Prompt-based mask generation
