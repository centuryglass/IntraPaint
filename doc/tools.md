# Tools:
All hotkeys can be changed in settings (F9) under the keybindings tab.

## Image Generation Area tool (G)
Controls the area of the image in use for AI image generation. AI generators are restricted to certain resolutions, but this tool lets you use them with images of any size.  When you click "Generate", the AI generator will only act on the area selected by this tool, and only content within this area will influence generated imagery.
- Set the image generation area position and size directly in the tool control panel.  For best results, make sure that the selected area is no larger than the image generation resolution, and that the aspect ratio of the generation area matches the aspect ratio of the generation resolution.
- Left-click the image to move the generation area without changing its size.
- Right-click the image to resize the generation area without changing its position.
- Hold control to force aspect ratio when resizing.

## Transform layer tool (T)
Move, scale, or rotate image layers or layer groups. Transformations are lossless when editing, or when saving in the .ora file format.
- Click and drag the layer to move it within the image, double-click the layer to switch between scaling or rotation modes.
- Click and drag the handle in the middle of the layer to control the center of rotation/scaling.
- Click and drag corners to scale or rotate the layer, depending on mode.
- Directly set layer transformation parameters in the tool panel.
- Use the "Clear" button in the tool panel to remove all transformations.
- Use the "Reset" button in the tool panel to reset layer transformations to their previous state.

# Painting tools:
Draw image content directly.

## Brush tool (B)
Draw, paint, blur, smudge, or erase within the image using the MyPaint brush engine.
- Edit brush size in the brush control panel, or using `[` and `]` keys.  Depending on the brush used, drawing tablet pen pressure may also affect brush size.
- Tabs in the brush control panel let you switch between pre-made MyPaint brush sets.  Right click on any brush, and you can add it to the "favorites" tab. 
- If you right-click and draw, the brush will use a fixed size of 1 pixel.
- Shift-click draws a straight line between the place you click and the previous place you clicked.
- Holding Alt while drawing forces the brush to follow a straight line.
- Hold Control to temporarily switch to the color picker tool.

## Fill tool (F)
Fill connected image areas with solid colors.
- Color threshold slider on the tool control panel controls how precisely the tool acts. At 0, only connected areas with exactly the same color as the clicked point will be filled. The higher the value, the more color variation allowed.
- If "sample merged" is unchecked, the tool will only act based on the active image layer's contents.  When checked, all visible layers will affect what area is filled.
- Hold Control to temporarily switch to the color picker tool.

## Color Picker tool (C)
Selects the color used by the brush and fill tools.
- Click any point in the image to select a color from the image.
- The tool control panel contains two tabs, "Color Component" and "Palette".
- The Color Component tab provides options to select color precisely based on red/green/blue/alpha components, or by hue/saturation/value components.
- The Palette tab lets you select from a predefined list of basic colors, or save the current color to the selected palette.
- "Select screen color" button under the palette tab will let you pick a color from anywhere on screen, including within other applications.

# Selection tools:
Selected content is marked with an animated outline and a transparent red overlay.  Outline animation and selection color can be changed in the Settings (F9) under the interface tab.
- In the edit menu, cut/copy/paste act on selected content.
- Selection menu provides tools for editing the selection bounds (invert, select all, select none, grow/shrink).
- All image filters can be restricted to only act on selected content.
- Brush and Fill tools can be restricted to only change selected content, but don't do so by default.
- When the generation mode is set to "Inpaint" (the default), image generation will only affect selected areas.

## Selection brush tool (S)
Select content by drawing over it in the image, similar to the brush tool.
- Edit brush size in the brush control panel, or using `[` and `]` keys . When using a drawing tablet, pen pressure also affects brush size.
- Switch between draw/erase in the tool panel to either add to the selection or remove from it.
- If you right-click and draw, the brush will use a fixed brush size of 1 pixel, useful for selecting very small details or controlling the full resolution inpainting bounds. See generation area guide for more details.
- Shift-click selects or clears a straight line between the place you click and the previous place you clicked.
- Holding Alt while drawing forces the selection to follow a straight line.

## Selection fill tool (E)
Select content based on similar color regions, like the fill tool.
- Left click selects, right click clears selection/
- Color threshold slider on the tool control panel controls how precisely selection works. At 0, only connected areas with exactly the same color as the clicked point will be selected/de-selected. The higher the value, the more color variation allowed.
- If "sample merged" is unchecked, the tool will only act based on the active image layer's contents.  When checked, all visible layers will affect the selection.
- If "Fill selection holes" is checked, the tool will ignore image content entirely, and only act based on what's already selected. Useful for filling gaps in the selection or clearing connected selection areas.

## Rectangle/ellipse selection (R)
Select rectangle or ellipse regions in the image.
- Left click and drag to select, right click and drag to clear.
- Hold control to force selections to stick to a fixed aspect ratio.