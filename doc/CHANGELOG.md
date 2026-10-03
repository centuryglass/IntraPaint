# Changelog and release notes

## [1.3.0](https://github.com/centuryglass/IntraPaint/compare/v1.2.0...v1.3.0) (2026-10-03)


### Features

* **generation:** add generation area frames and a resolution rule ([a777d4f](https://github.com/centuryglass/IntraPaint/commit/a777d4ffd1ffda664e751f58a1bc47fe213690f4))
* **generation:** add generation area frames and a resolution rule ([cde5d0b](https://github.com/centuryglass/IntraPaint/commit/cde5d0b074980aa9cc77699965c79ed2d46ff5bb))


### Bug Fixes

* **build:** bundle the fill tools, which PyInstaller missed as optional imports ([b350284](https://github.com/centuryglass/IntraPaint/commit/b35028452384b64e89f99f9fa27e901c6c5287ba))
* **build:** include the fill tools in packaged bundles ([7e20d82](https://github.com/centuryglass/IntraPaint/commit/7e20d82e82ef14e52f150b70b58bb3192309dbae))
* **color:** stop File &gt; New clobbering brush color, fix off-canvas color sampling, guard shape tool color sync ([20b3174](https://github.com/centuryglass/IntraPaint/commit/20b3174c23644b7eeb5b65d88dbc21a90bc21aeb))
* **color:** stop File &gt; New overwriting brush color, fix off-canvas color sampling, guard shape tool color sync ([1a07555](https://github.com/centuryglass/IntraPaint/commit/1a0755572119dfd72abd25e0952cbc3bf40f7e08))
* **config:** don't hold the config lock while saving from a worker thread ([f696240](https://github.com/centuryglass/IntraPaint/commit/f6962408caa0d346400d6af94d2c11fdd543e5c6))
* **config:** stop Config.set deadlocking when a worker thread saves ([706add1](https://github.com/centuryglass/IntraPaint/commit/706add1f4f9bac37f81137be02a8bc8c3af2abcd))
* **config:** write config JSON atomically so crashes can't wipe settings ([e054e65](https://github.com/centuryglass/IntraPaint/commit/e054e6506c69ebeba7c109155c326511dcddf6f4))
* **config:** write config JSON atomically via temp file + os.replace ([b88e380](https://github.com/centuryglass/IntraPaint/commit/b88e380f8a250b36986debf2cf26cbbdd52c537f)), closes [#30](https://github.com/centuryglass/IntraPaint/issues/30)
* **generation:** construct KeyConfig before reading its key attribute ([9712252](https://github.com/centuryglass/IntraPaint/commit/97122520b4248899f8e417980e9e93e8503efdcc))
* **generation:** stop frame resizes and huge typed sizes from erroring ([c0e74fc](https://github.com/centuryglass/IntraPaint/commit/c0e74fcf7bab8be48d02f5fcdae30f0f05fec260))
* **ora:** keep awkward layer names from breaking .ora saves ([3ee197c](https://github.com/centuryglass/IntraPaint/commit/3ee197c1ff5a4990b60c25628ad836042f9afabc))
* **ora:** saving no longer fails on layer names with path separators, and src paths use '/' on Windows ([d08816e](https://github.com/centuryglass/IntraPaint/commit/d08816e1dd7656aa002db7dcad67f97b005b4272))
* **ora:** write '/'-separated archive paths on every platform ([c288f0a](https://github.com/centuryglass/IntraPaint/commit/c288f0a18383ddb068b3f87c74e84a2a7a346018))
* replace deprecated QColor.isValidColor calls ([017b805](https://github.com/centuryglass/IntraPaint/commit/017b805944da893a4182cf98041f545eb13e03db))
* replace deprecated QColor.isValidColor calls ([a965ec7](https://github.com/centuryglass/IntraPaint/commit/a965ec72b92d7bab4d13a4631f7eb6a2cf4fcdfe))
* start without the fill tools when the image_fill build is missing ([7b794e7](https://github.com/centuryglass/IntraPaint/commit/7b794e73ca1d43732f79df256bba86d3623cb39b))
* start without the fill tools when the image_fill build is missing ([3e23772](https://github.com/centuryglass/IntraPaint/commit/3e23772cc286b0f936824bf01154dd8b0d0702c4))
* **tools:** deliver each canvas mouse event to the tool once, and add transform tool tests ([9a05cb2](https://github.com/centuryglass/IntraPaint/commit/9a05cb2b08630c833b6b2e69ae41c27d8e45c1e8))
* **tools:** deliver each canvas mouse event to the tool once, in view coordinates ([1a2637b](https://github.com/centuryglass/IntraPaint/commit/1a2637ba75b01d1aa7a7997db2f49e861d7d94fa)), closes [#76](https://github.com/centuryglass/IntraPaint/issues/76)
* **tools:** scale and rotate layers about the transformation origin ([5a8c93a](https://github.com/centuryglass/IntraPaint/commit/5a8c93abe332de4a427af7c1e05a6ce44b906a72))
* **tools:** scale and rotate layers about the transformation origin ([9445a71](https://github.com/centuryglass/IntraPaint/commit/9445a719adfd847599a6c374d958d1d572ea784c))
* **ui:** ask before closing the main window ([7254763](https://github.com/centuryglass/IntraPaint/commit/72547632fcac6434da11bd04cee1e0828731d8b7))
* **ui:** ask before closing the main window ([78aa600](https://github.com/centuryglass/IntraPaint/commit/78aa600c217814b44d4aa841ae87aad38c8060fa))
* **ui:** correct layer_height getter returning width box value ([8b1481e](https://github.com/centuryglass/IntraPaint/commit/8b1481e1de16eb8c615a65cd49450a8f64ae5229))
* **ui:** use _height_box for layer_height getter and fix setter parameter name ([e5eab85](https://github.com/centuryglass/IntraPaint/commit/e5eab854ac17994442eab25ce69f5f84862e3a79)), closes [#12](https://github.com/centuryglass/IntraPaint/issues/12)
* use os.makedirs(exist_ok=True) to fix TOCTOU race in _adjust_defaults ([#97](https://github.com/centuryglass/IntraPaint/issues/97)) ([e573298](https://github.com/centuryglass/IntraPaint/commit/e573298abc208f9d0d03c3241e2b3f4cd0de9bd1))

## 1.2.0

June 18 2026

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
