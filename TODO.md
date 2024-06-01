# Future development tasks


raise mask/brush cursor opacity/add white
fixed selection panel option?
width/height boxes should have step 1
remove debug sample image saving

# Input
- Global hotkey management
- Expand hotkeys for all tools
- Configurable hotkeys
- escape unfocuses text input
- non-numeric unfocuses numeric input
- tab navigation keys

# ToolPanel
- Show hotkeys in UI
- Navigation tool
    - add "select all" button
    - rename to mask selection?
    - selection to generation size
    - selection to full image
- Add another tool to handle view zoom+pan
- Add "shift to draw lines" in MyPaint tool
- Paint bucket tool
- Text tool
- More conventional selection controls?

# Bugfix
- "masked only" selection not cleared when mask is cleared
- Cursor gets lost sometimes on transition to image cursor

# Undo system
- Add undo support to sample selection

# LayerPanel
- Add a 'new layer' button
- Implement active layer switching
- Layer copying
- Layer deletion
- Layer re-order
- cut+paste via mask tool

# Layout
- Add --window_size arg for testing reactive layouts
- Fix various widget scrolling issues
- Add tabs for image generation
- Find better placement for "Interrogate/Generate" buttons
- Add Layer panel to window (again)
- Panel cleanup with FormLayout
- Add click+drag resizing to CollapsibleBox
- Add option to pop out CollapsibleBox content as window
- Add option to move CollapsibleBox content into tab
- Fix BrushPanel list layout issues

# Sample selection widget
- Add context menu for selections:
    * Select
    * Send to new layer
- Nicer selection page design:
    * Use an actual layout
    * Right-click for zoom

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
- Better fix for brush setting init

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
