# Development tasks

## Definite bugs
- The transform tool's center of rotation point isn't working, and dragging and rotating causes glitchy behavior on occasion. This might require significant redesign, I remember there's serious challenges involved in syncronizing that state with the transformation panel's input fields.
- Responsive UI on smaller displays continues to be a thorn in my side. Display size tracking is glitchy, as it can't tell when there's a OS toolbar blocking screen real estate in many circumstances. There's too many conditions where a UI tweak still pushes minimum window size beyond the available space. Not a problem on 1080p or larger, thankfully, but I'd like it to work with fewer issues on my old laptop.
- Some of the MyPaint brushes are clearly not working. Cross-test on Windows and with actual MyPaint, refer to images in examples folder.
- LayerPanel layout still shows some odd glitches on occasion


## Possible lurking bugs
Things I never fixed but can no longer reproduce, or that come from external issues:
- "crop layer to selection": overlap handling on layer groups may still have some issues with groups overlapping the selection boundary
- Nested layer selection state shown in the layer panel isn't updating properly (recursive active layer update logic in LayerPanel looks fine)
- changing gen. area size still doesn't always sync fully - width changes but not height. Possibly fixed, keep an eye out for it.
- Weird bug where every new image loads with a seemingly-arbitrary transformation pre-applied.  Maybe a bug with layer group transforms? Haven't been able to reproduce.
- .ora save fails when layer name is "" (couldn't reproduce, but I don't remember fixing this)
- text layer offset is buggy: transform tool offsets aren't in sync with text tool coordinates, copy/paste puts layers in weird places. (can't reproduce - probably conditional. Requires specific transform type?)
- Weird resize glitch sometimes when moving the window between monitors, possibly related to panel orientation/layout (Probably requires specific panel positions/sizes, display sizes)
- selection_layer.py line 340, height_to_add < 0:  Should be non-breaking now, keep an eye on logs
- selection outline issues: sometimes the vectorization doesn't properly join the sections, but it's hard to reproduce. Selection layer could use a revamp anyway to get rid of the need for large bitmaps.
- - Partial alpha compositing glitches (brush tool on alpha-locked layer, partial alpha?) - Seems like a GraphicsView rendering issue, so this one might be tricky.

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
* `QColor.isValidColor(str)` is deprecated in the current PySide6 and is called in several places (config.py, color_button.py, qt_paint_brush_tool.py, selection_outline.py, and more). It generates ~250 warnings per test run and will eventually break. Low effort to fix, worth doing before it becomes a hard error on a PySide6 upgrade.


## Extremely low-priority edge-cases:
- All my QImage data indexing assumes a little-endian data structure. Odds of ever running on a big-endian system are extremely slim, but a lot of things are going to fail if it ever does. Consider checking endianness and using it to set channel indexes on launch.

---
## Testing:
- Test coverage is pretty sparse, lots of features are completely uncovered.
- DONE: `pytest` now runs the whole suite headlessly from the CLI (`pytest.ini` + `conftest.py` force
  the Qt offscreen platform), so IntelliJ is no longer required. A GitHub Actions workflow
  (`.github/workflows/test.yml`) runs it on PRs to master and can be triggered manually.
- Remaining: broaden coverage (still only ~11 test files for the whole app). The transform tool, layer
  panel, and responsive-layout code — the areas with the most lurking bugs — have little or none.
- `geometry_utils_test.py` alone takes ~4 min (brute-force transform grid) and dominates suite runtime.
  Consider trimming its parameter space or enabling pytest-xdist if CI time becomes annoying.

## Color Picker:
- The default QT color picker is not very good, and my modular port of it is only the tiniest bit better. Consider a full replacement.
- Implement the sort of background/foreground dual-color setup that literally every image editor uses.


## Generation area management.
Generation area management is key. Current tools for managing it are clunky and should be improved. Find a better pattern than messing with gen area padding and that ugly 1px selection brush hack. Goal is maximum flexibility while minimizing the amount the user has to think about hitting ideal resolutions and making sure aspect ratios match.

## API setup:
- The current process is way too technical for your average user. You should be able to click a button and have the whole thing set up automatically. Have a popup button offer to do it on launch if you start it up without one running already. Krita AI does it, there's no reason I can't too. I'll never use it, but I still want to keep the possibility open.


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
Final notes: Text layer handling is pretty important, and shouldn't be too hard. SVG layers are a lower priority.

## Layer interface
- Possibly add selection layer back to layer panel
- Layer multi-select: Topmost selected layer is active, all others only selected for the sake of bulk copy/grouping/merge/delete
- Add "merge group" and "merge all visible" options
Final notes: Multi-select might be a bit of a pain, merge options should be trivial. Displaying the selection in the layer interface is a UX question to answer later.

### Draw tool
- Add custom brush fill patterns, alternate brush shapes
Final notes: Would be a cool feature, but there's enough going on in qt_paint_brush that this might be a pain.
  
### Smudge tool
- Find some way to mitigate delays when smudging linearly over long distances:
- When the drawing buffer has huge numbers of pending operations, see if we can defer some of them to give the window time to update
Final notes: I've already done a lot of optimizing here, further improvements may be challenging. Make sure to test significantly.

## libmypaint
- Update Windows libmypaint DLLs
- Add macOS (intel and M1), ARM linux libmypaint libraries
Final notes: Very low priority. I don't have a mac for testing, and the current DLLs for Windows seem fine.

## Generated image selection screen
- Non-transitory selection window? Would be nice to see past options, at least the ones from the last batch. Having to fully switch to a different window for inpainting option selection provides both benefits and drawbacks. Minimizing the friction of generating, comparing, and applying repeated inpainting operations is key.

# Gradient support
- Select between gradient types, define gradient transition points
- Option to save gradients
- Support in draw, fill, shape, text tools
Final notes: low priority. Seems mildly useful, but it might be best to move away from trying to replace a full image editor.

## A1111/Forge api extensions
- More support for custom scripts, script UI panels
- A1111 lora/hypernet/etc selection support
Final notes: mid to low priority. I think most people have already moved to ComfyUI, I should probably start treating that as the default.

## ControlNet
- Add tooltip descriptions for modules and models
- Saved preset support, with defaults saved.
Final notes: Will have to be careful to not make an already cluttered interface even worse.

## Legacy AI generators:
It would be cool to add support for these, if only for the nostalgia.  Probably best done with standalone server programs with minimal REST interfaces. Save this one for a random weekend project.
- DeepDream
- VQGAN+CLIP

## Help window
- Rich text tutorial content, with images and dynamic hotkeys.
- Any sort of tutorial is desperately needed if anyone else is ever gonna use this. That's low priority though, new user adoption is a marketing problem I don't care to deal with right now.
