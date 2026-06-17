# Changelog and release notes

## 1.2.0

June 17 2026

### New features:
- The Fill tool has been significantly improved, using LAB color space thresholding to better match perceived colors and cython compilation to increase speed.
- Added "source mode" options to the clone stamp tool to better control how it samples image content and follows the cursor.
- Added color invert and saturation filters
- Improve pixel-level precision when editing at high zoom levels, highlighting targeted pixels and fixing sub-pixel offset issues.
- Increased max zoom level, automatically snappint zoom steps to integer scales
- Improved rendering of rotated image layers, scaled layers: use antialiasing for rotation and non-integer scaling only.

### Interface and appearance improvements
- Shape tool preview overlays no longer block image content as much, display in alternate colors and fill styles when appropriate
- Exclude ControlNet previews from A1111 inpainting image results
- Correct tiny offset errors in cursors, make minor improvements to cursor designs
- Fix flickering issues with extra-large cursors
- Improve appearance of selected content overlays using subtle optional animations
- Disable panning/zooming the navigation panel
- Draw line previews from pixel center, not corner
- Improved appearance of checkerboard transparent image background
- Image zoom is now multiplicative instead of additive, improving the experience of working at high zoom levels
- Zooming with the mouse wheel does a better job of keeping the point under the cursor fixed

### Performance improvements
- Optimized the draw tool to decrease lag on very large layers.
- Layer stack engine and rendering improvements to decrease lag in complex layer stacks
- Layer preview renders scaled and batched to prevent slowdowns

### Misc. Bugfixes:
- Fixed modifier bindings breaking text tool shortcuts like copy/paste
- Missing MyPaint brushes no longer cause crashes
- Fixed smudge brush not working correctly when cursor moves down or left
- Undo now works reliably to undo loading a new image when previous image had multiple layers
- Block zero-scale layer transformations more comprehensively
- Fix issues with invisible control image widget blocking ControlNet panel interface
- "Erase in selection only" no longer affects the selection brush itself
- Corrected numerous color picker bugs: issues with custom colors, syncing changes between popup and panel, HSV selection alpha values
- Fixed a bug where image cropping could cause crashes
- Fixed a rare bug where certain actions caused crashes after locking layer alpha
- Fixed issues with loading .ora files with layer alpha locks
- Custom MyPaint brushes now load fully, show selected brush correctly

### Dev:
- Improved debug tools for cursor rendering and performance analysis
- Add TIMELAPSE_MODE flag that applies settings convenient for recording timelapse footage, such as disabling animation

## 1.1.0

Nov. 17 2024

### New features:

#### ComfyUI image generator support
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) can now be used in place of the Stable Diffusion WebUI for image generation, present as a new entry in the list of image generators.  All major features are supported, with the "Interrogate" button being the only major exception.
- Dynamic ComfyUI workflow generator created to handle ComfyUI's unique API, and provide some flexibility for things like ControlNet use.
- "Extras" tab added to the image generation panel, holding controls for generator-specific features. Config selection, tiled VAE options, inpainting model loading, and clear memory button added to the ComfyUI extras tab.

#### Improved image scaling controls
- New dropdown added to explicitly select between basic scaling, image generator powered scaling, and advanced latent upscaling.
- Add extended support for selecting a ControlNet tile model and preprocessor, and setting tile preprocessor parameters.
- Use of the "Ultimate SD Upscale" script can now be directly enabled and disabled.
- When using latent upscaling, denoising strength and step count can now be set in the image scaling window.

#### Improved ControlNet support
- Improved management of ControlNet data and added useful defaults, so the "Control Type" dropdown will always be available.
- Add hard-coded preprocessor parameters for WebUI APIs that don't provide those, so parameters from standard preprocessors should always be available.
- Add a "preprocessor preview" button, showing ControlNet preprocessor output directly in the ControlNet panel.
- WebUI ControlNet resolution, image scaling mode, and control mode options can now be set in the ControlNet panel.

#### Other
- Added a Help menu, linking to GitHub documentation
- Stable Diffusion model selection and CLIP skip are now available directly in the Image Generation panel
- Added "randomize", "reuse last value" buttons to the seed input field.
- When using the WebUI generator, rovide access to batch variation seed settings, seed resizing, and tile/face restore toggles within the new "extras" tab within the Image Generation panel.

### Bugfixes
- Changing the URL of an image generator within the image generator selection window should be possible again.
- Fixed some errors where ControlNet widgets weren't properly disabled when the ControlNet unit is disabled.
- Image generator activation failures should be a lot clearer now.
- Fixed some issues caused by changing lists of various options when switching between image generators.
- Fixed an error blocking access to settings if the Stable Diffusion WebUI stops responding.

### Development changes, documentation and cleanup
- Increased minimum Python version from 3.9 to 3.11 to take advantage of typing system improvements.
- In the settings, the "Stable Diffusion" and "Connected generator" options have been merged, and some items have been moved to the Image Generation panel and Scale Image window.
- Added expanded [Stable Diffusion installation guide](./stable_diffusion_setup.md), 
- Improved documentation layout, setup instructions in the image generator selection window.
- When upscaling adds a new image layer, that layer now becomes the active layer.
- Placeholder preview image in the LoRA panel is no longer excessively tall.
