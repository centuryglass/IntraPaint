# Development tasks

# Latest bugs, next priorities:

- Partial alpha compositing glitches (brush tool on alpha-locked layer, partial alpha?)
- Shift key conflict messes up transforms on switch from transform tool -> shape tool
- Remove ControlNet preprocessor images from results
- Clone tool docs need update
- invalid bounds errors (empty) in mypaint_layer_tile when cropping to bounds with the brush tool open
- fix slowness when layer size = 6k:
  - Refactor to remove unnecessary layer copying in ImageLayer._handle_content_change
  - QtPaintBrush._draw_input_event:  Make sure the numpy copying really is faster
  - QtPaintBrush.start_stroke: Refactor to avoid copying the whole layer into prev_image_buffer
  - layer_widget:  Also copies the whole image, see if we can get a scaled copy instead
- Selection issues: Try reproducing with selection_debug.ora
- Clone tool sample brush seems off by a couple pixels
- line previews are also off by <1 scene pixel
- assertion error: image_stack.py L1466, after reload then undo on multi-layer .ora file
---

## Possible lurking bugs
Things I never fixed but can no longer reproduce, or that come from external issues:
- Nested layer selection state shown in the layer panel isn't updating properly (recursive active layer update logic in LayerPanel looks fine)
- changing gen. area size still doesn't always sync fully - width changes but not height. Possibly fixed, keep an eye out for it.
- Weird bug where every new image loads with a seemingly-arbitrary transformation pre-applied.  Maybe a bug with layer group transforms? Haven't been able to reproduce.
- .ora save fails when layer name is "" (couldn't reproduce, but I don't remember fixing this)
- text layer offset is buggy: transform tool offsets aren't in sync with text tool coordinates, copy/paste puts layers in weird places. (can't reproduce - probably conditional. Requires specific transform type?)
- Weird resize glitch sometimes when moving the window between monitors, possibly related to panel orientation/layout (Probably requires specific panel positions/sizes, display sizes)
- selection_layer.py line 340, height_to_add < 0:  Should be non-breaking now, keep an eye on logs
- Crash on alpha unlock:  Requires some sort of complex multi-layer sequence


## General concerns and ideas
* Do more profiling, performance is adequate but there's still some noticeable lag in a few places
* TabBar should have some mechanism for scrolling so the UI doesn't break when you turn up the tab bar shortcut count
* There should be a mechanism for sending UI tabs to new windows
* Color picker could use other options: RGB cube, color wheel, OKLab perceptual color
* Switch color picker to horizontal icon tabs
* Transform tool: clicking a layer should activate it, or there should be an option to do that at least.
* ImageViewer: add sidebar rulers
* add 'sample merged' option to smudge, stamp, and filter tools
* A lot of unnecessary complexity could probably be removed from undo history management if I just used QUndoStack instead of my own implementation.  It'd take a fair bit of refactoring though, so it probably isn't a priority 

## Minor bugs:
- Some of the MyPaint brushes are clearly not working. Cross-test on Windows and with actual MyPaint, refer to images in examples folder.
- LayerPanel layout still shows some odd glitches on occasion
- "crop layer to selection": overlap handling on layer groups may still have some issues with groups overlapping the selection boundary

---

## Help window
- Rich text tutorial content, with images and dynamic hotkeys.

## ORA format: Preserve information from other programs
- SVG layers:
  * Create SVGLayer class that functions as image layer, but preserves the original SVG file
  * Disable painting+destructive changes, use "convert to ImageLayer" logic the same way TextLayer does
- Check for and preserve non-standard image and layer tags from the original .ora file (also, the "isolate" tag).
- Check for and preserve non-standard files
- Text layers, svg approach:
  * Write TextRect serialization, deserialization functions that write to svg xml
  * On save: serialize to .svg, but also write a backup .png
  * On load: attempt to parse as text.  If the text doesn't parse or match the .png copy, fallback to image loading.
- Text layers, .ora extension approach:
  * As above, but serialize and write to the xml data extension file instead
  * Possibly better than the .svg approach, this route won't break the image in other editors if loaded on a system that's missing fonts. Decide based on ease of .svg serialization.

## Layer interface
- Add selection layer back to layer panel
- Layer multi-select: Topmost selected layer is active, all others only selected for the sake of bulk copy/grouping/merge/delete
- Add "merge group" and "merge all visible" options

## Menus
- Filters: just throw in whatever fun stuff PIL/CV2 have to offer

### Draw tool
- Add custom brush fill patterns, alternate brush shapes
  
### Smudge tool
- Find some way to mitigate delays when smudging linearly over long distances:
- When the drawing buffer has huge numbers of pending operations, see if we can defer some of them to give the window time to update

## libmypaint
- Update Windows libmypaint DLLs
- Add macOS (intel and M1), ARM linux libmypaint libraries
- Import latest code/changes
- Get the demo app working again
- Port to qtpy for maximum compatibility
- Figure out Pip release process, libmypaint bundling

## Generated image selection screen
- Non-transitory selection window? Would be nice to see past options, at least the ones from the last batch.

# Gradient support
- Select between gradient types, define gradient transition points
- Option to save gradients
- Support in draw, fill, shape, text tools


## A1111/Forge api extensions
- More support for custom scripts, script UI panels
- A1111 lora/hypernet/etc selection support

## ControlNet
- Figure out a way to preview module preprocessing
- Add tooltip descriptions for modules and models
- Saved preset support, with defaults saved.

## Legacy AI generators:
It would be cool to add support for these, if only for the nostalgia.  Probably best done with standalone server programs with minimal REST interfaces.
- DeepDream
- VQGAN+CLIP


