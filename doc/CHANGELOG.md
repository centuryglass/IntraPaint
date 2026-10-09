# Changelog and release notes

## [1.3.0](https://github.com/centuryglass/IntraPaint/compare/v1.2.0...v1.3.0) (2026-10-09)


### Features

* **color:** add a background color, swap/reset shortcuts and a color pair widget ([#123](https://github.com/centuryglass/IntraPaint/issues/123)) ([27f0456](https://github.com/centuryglass/IntraPaint/commit/27f0456cb4e4ced73123d34852fe8f8882b0daa3))
* **color:** add an OKHSV ring + square Wheel tab to the color picker ([#157](https://github.com/centuryglass/IntraPaint/issues/157)) ([137ab54](https://github.com/centuryglass/IntraPaint/commit/137ab540d72f74213781a80f5e2870ea9f0360ba))
* **color:** add RGB, HSV and OKLCH gradient sliders to the color picker ([#167](https://github.com/centuryglass/IntraPaint/issues/167)) ([36461c2](https://github.com/centuryglass/IntraPaint/commit/36461c209abcc17fb1681bfb02f15813d8e7c485))
* **color:** add saved colors and a recent colors row to the color picker ([#195](https://github.com/centuryglass/IntraPaint/issues/195)) ([457433c](https://github.com/centuryglass/IntraPaint/commit/457433c3c8e37408bf7de54874a71d1ac014efdc))
* **color:** finish the color picker with a header and size-based layouts ([#197](https://github.com/centuryglass/IntraPaint/issues/197)) ([a123c8e](https://github.com/centuryglass/IntraPaint/commit/a123c8e2ea408eb1cc6df87d76d298e9f213e8e4))
* copy and paste images through the system clipboard ([#241](https://github.com/centuryglass/IntraPaint/issues/241)) ([b0f4de5](https://github.com/centuryglass/IntraPaint/commit/b0f4de5a3b113f56a0e05ada686d946464a3c41d))
* **generation:** add context pins to stretch the inpaint crop ([#106](https://github.com/centuryglass/IntraPaint/issues/106)) ([c4b0f31](https://github.com/centuryglass/IntraPaint/commit/c4b0f31caa66928feea59cf0cc729bc6c905c822))
* **generation:** add generation area frames and a resolution rule ([a777d4f](https://github.com/centuryglass/IntraPaint/commit/a777d4ffd1ffda664e751f58a1bc47fe213690f4))
* **generation:** add generation area frames and a resolution rule ([cde5d0b](https://github.com/centuryglass/IntraPaint/commit/cde5d0b074980aa9cc77699965c79ed2d46ff5bb))
* **generation:** change inpaint padding with Shift + scroll wheel ([#108](https://github.com/centuryglass/IntraPaint/issues/108)) ([fbb3a68](https://github.com/centuryglass/IntraPaint/commit/fbb3a68e54c3a7a92fdc7a7070f48ac021bb55d5))
* **generation:** drag the generation area by grab point and resize it with handles ([#156](https://github.com/centuryglass/IntraPaint/issues/156)) ([7578c96](https://github.com/centuryglass/IntraPaint/commit/7578c96df072218820f0c119f9965692d1ba9827))
* **generation:** move the generation area to follow selection edits ([#118](https://github.com/centuryglass/IntraPaint/issues/118)) ([6c0a481](https://github.com/centuryglass/IntraPaint/commit/6c0a481c9b84a82adad10dd2c363e514fe8be0bc))
* **layers:** keep text layers editable when saving to .ora ([#130](https://github.com/centuryglass/IntraPaint/issues/130)) ([a972206](https://github.com/centuryglass/IntraPaint/commit/a972206345f9a72b0d481571d0634e31869edbdb))
* **ui:** add rulers beside the image viewer ([#131](https://github.com/centuryglass/IntraPaint/issues/131)) ([90c84c5](https://github.com/centuryglass/IntraPaint/commit/90c84c5d7de8086290726c33efb67bf1ac190a65))
* **ui:** add the IntraPaint Ink theme with a bundled font as the default ([#207](https://github.com/centuryglass/IntraPaint/issues/207)) ([9de015a](https://github.com/centuryglass/IntraPaint/commit/9de015aedf7e1d41c59b3e4f26fb9c6ada30c0e5))
* **ui:** draw controls with an IntraPaint Ink QProxyStyle ([#230](https://github.com/centuryglass/IntraPaint/issues/230)) ([f520935](https://github.com/centuryglass/IntraPaint/commit/f520935872fcaa389b07f2e93e34ccaa14a7f818))
* **ui:** draw tool tiles, key hints, side tabs and frames in the Ink look ([#235](https://github.com/centuryglass/IntraPaint/issues/235)) ([4f5de9f](https://github.com/centuryglass/IntraPaint/commit/4f5de9f385bc576a72341344a4f5aba6dd9937a3))
* **ui:** recolor black line icons from the dark palette ([#232](https://github.com/centuryglass/IntraPaint/issues/232)) ([3ae073c](https://github.com/centuryglass/IntraPaint/commit/3ae073ccfb15eafcc450ae4cdc059e3ccc8d995e))
* **ui:** use the Ink signal color for discarding actions and lock alerts ([#246](https://github.com/centuryglass/IntraPaint/issues/246)) ([3776ba3](https://github.com/centuryglass/IntraPaint/commit/3776ba332e4afa7f7fcb4bb6a9eabf802339a70c))


### Bug Fixes

* **brushes:** load the bundled libmypaint first and bundle only the platform's build ([#129](https://github.com/centuryglass/IntraPaint/issues/129)) ([4c2d1c4](https://github.com/centuryglass/IntraPaint/commit/4c2d1c4768bfc85fdd9e37a851c8b587868d9736))
* **build:** bundle the fill tools, which PyInstaller missed as optional imports ([b350284](https://github.com/centuryglass/IntraPaint/commit/b35028452384b64e89f99f9fa27e901c6c5287ba))
* **build:** include the fill tools in packaged bundles ([7e20d82](https://github.com/centuryglass/IntraPaint/commit/7e20d82e82ef14e52f150b70b58bb3192309dbae))
* **color:** stop File &gt; New clobbering brush color, fix off-canvas color sampling, guard shape tool color sync ([20b3174](https://github.com/centuryglass/IntraPaint/commit/20b3174c23644b7eeb5b65d88dbc21a90bc21aeb))
* **color:** stop File &gt; New overwriting brush color, fix off-canvas color sampling, guard shape tool color sync ([1a07555](https://github.com/centuryglass/IntraPaint/commit/1a0755572119dfd72abd25e0952cbc3bf40f7e08))
* **comfyui:** avoid crashing on unexpected fields in ComfyUI image references ([#257](https://github.com/centuryglass/IntraPaint/issues/257)) ([77b4990](https://github.com/centuryglass/IntraPaint/commit/77b49903f30666d1f8d4c9ce2c8e03041d565c9f))
* **config:** don't hold the config lock while saving from a worker thread ([f696240](https://github.com/centuryglass/IntraPaint/commit/f6962408caa0d346400d6af94d2c11fdd543e5c6))
* **config:** stop Config.set deadlocking when a worker thread saves ([706add1](https://github.com/centuryglass/IntraPaint/commit/706add1f4f9bac37f81137be02a8bc8c3af2abcd))
* **config:** write config JSON atomically so crashes can't wipe settings ([e054e65](https://github.com/centuryglass/IntraPaint/commit/e054e6506c69ebeba7c109155c326511dcddf6f4))
* **config:** write config JSON atomically via temp file + os.replace ([b88e380](https://github.com/centuryglass/IntraPaint/commit/b88e380f8a250b36986debf2cf26cbbdd52c537f)), closes [#30](https://github.com/centuryglass/IntraPaint/issues/30)
* **filters:** keep RGBA color balance output validly premultiplied ([#202](https://github.com/centuryglass/IntraPaint/issues/202)) ([2f16df4](https://github.com/centuryglass/IntraPaint/commit/2f16df4bcbd722089993a28c8a41ff5bb461516e)), closes [#160](https://github.com/centuryglass/IntraPaint/issues/160)
* **formats:** stop offering formats that can never load or save, and fix JPEG 2000 saves ([#198](https://github.com/centuryglass/IntraPaint/issues/198)) ([aaf8068](https://github.com/centuryglass/IntraPaint/commit/aaf806865e451765359398017f408c8873efb355))
* **generation:** construct KeyConfig before reading its key attribute ([9712252](https://github.com/centuryglass/IntraPaint/commit/97122520b4248899f8e417980e9e93e8503efdcc))
* **generation:** keep the selection inside the generation area when applying a frame ([#243](https://github.com/centuryglass/IntraPaint/issues/243)) ([2edf40a](https://github.com/centuryglass/IntraPaint/commit/2edf40ace71062eb03d81afed1aaba0c7e44c079))
* **generation:** stop frame resizes and huge typed sizes from erroring ([c0e74fc](https://github.com/centuryglass/IntraPaint/commit/c0e74fcf7bab8be48d02f5fcdae30f0f05fec260))
* **layers:** fix layer panel layout glitches with nested groups ([#201](https://github.com/centuryglass/IntraPaint/issues/201)) ([0fcb99f](https://github.com/centuryglass/IntraPaint/commit/0fcb99f12ec337f2e53139ab8e35e15f42f78369))
* **layers:** keep the composite when flattening over translucent content ([#244](https://github.com/centuryglass/IntraPaint/issues/244)) ([fa6e8b5](https://github.com/centuryglass/IntraPaint/commit/fa6e8b5fa2a4103251d1370a7121a62955b04895))
* **layers:** refresh a group's cached image when its own opacity or mode changes ([#179](https://github.com/centuryglass/IntraPaint/issues/179)) ([a013307](https://github.com/centuryglass/IntraPaint/commit/a013307bcc826e9aaee5c4ac865f3431f6a62a56)), closes [#166](https://github.com/centuryglass/IntraPaint/issues/166)
* **layers:** report the old area when a layer moves, shrinks or is smoothly sampled ([#220](https://github.com/centuryglass/IntraPaint/issues/220)) ([c708024](https://github.com/centuryglass/IntraPaint/commit/c7080240ca1b52c0d0760da492d34ad36b3e4f8d))
* **layers:** show a hidden layer group's content in its layer panel preview ([#222](https://github.com/centuryglass/IntraPaint/issues/222)) ([8599c01](https://github.com/centuryglass/IntraPaint/commit/8599c0116fbd277e66ecf3a09cf8e9f4ae8d91a9)), closes [#208](https://github.com/centuryglass/IntraPaint/issues/208)
* **layers:** stop non-isolated groups compositing the content beneath them over itself ([#228](https://github.com/centuryglass/IntraPaint/issues/228)) ([6424f97](https://github.com/centuryglass/IntraPaint/commit/6424f97e8f2462a8ca1d7676a4e2fc5193fd7fab))
* **layout:** fix tab drop order, tab box stretch drift and divider height limits, and test the layout code ([#219](https://github.com/centuryglass/IntraPaint/issues/219)) ([1d6ea03](https://github.com/centuryglass/IntraPaint/commit/1d6ea03d23119e1cd42bd4896b22ff066558b39e))
* **ora:** keep awkward layer names from breaking .ora saves ([3ee197c](https://github.com/centuryglass/IntraPaint/commit/3ee197c1ff5a4990b60c25628ad836042f9afabc))
* **ora:** saving no longer fails on layer names with path separators, and src paths use '/' on Windows ([d08816e](https://github.com/centuryglass/IntraPaint/commit/d08816e1dd7656aa002db7dcad67f97b005b4272))
* **ora:** write '/'-separated archive paths on every platform ([c288f0a](https://github.com/centuryglass/IntraPaint/commit/c288f0a18383ddb068b3f87c74e84a2a7a346018))
* pause garbage collection while applying Qt styles and themes ([#196](https://github.com/centuryglass/IntraPaint/issues/196)) ([ef23f6d](https://github.com/centuryglass/IntraPaint/commit/ef23f6d4dfc1f08361879cb9027ae038b3639e47)), closes [#153](https://github.com/centuryglass/IntraPaint/issues/153)
* replace deprecated QColor.isValidColor calls ([017b805](https://github.com/centuryglass/IntraPaint/commit/017b805944da893a4182cf98041f545eb13e03db))
* replace deprecated QColor.isValidColor calls ([a965ec7](https://github.com/centuryglass/IntraPaint/commit/a965ec72b92d7bab4d13a4631f7eb6a2cf4fcdfe))
* **selection:** filters apply to every region of a multi-region selection ([#122](https://github.com/centuryglass/IntraPaint/issues/122)) ([d716c82](https://github.com/centuryglass/IntraPaint/commit/d716c825c25d947cbcb544882b0b83491af6cb8e)), closes [#117](https://github.com/centuryglass/IntraPaint/issues/117)
* **selection:** join outline sections after nearby edits and grow/shrink by the exact radius ([#224](https://github.com/centuryglass/IntraPaint/issues/224)) ([f5bb4d8](https://github.com/centuryglass/IntraPaint/commit/f5bb4d88c1bb37203027dc85e61ad5f737d5def2)), closes [#23](https://github.com/centuryglass/IntraPaint/issues/23) [#209](https://github.com/centuryglass/IntraPaint/issues/209)
* **selection:** keep selection brush strokes one-bit, and pin them with golden tests ([#159](https://github.com/centuryglass/IntraPaint/issues/159)) ([51fe090](https://github.com/centuryglass/IntraPaint/commit/51fe0904db4f60d3ba8671c1a8b63130106d0e35))
* **smudge:** composite strokes in 16 bits per channel to keep color ([#204](https://github.com/centuryglass/IntraPaint/issues/204)) ([216f7bc](https://github.com/centuryglass/IntraPaint/commit/216f7bc11fc1805eccc95751fd51bc2392573fee)), closes [#110](https://github.com/centuryglass/IntraPaint/issues/110)
* start without the fill tools when the image_fill build is missing ([7b794e7](https://github.com/centuryglass/IntraPaint/commit/7b794e73ca1d43732f79df256bba86d3623cb39b))
* start without the fill tools when the image_fill build is missing ([3e23772](https://github.com/centuryglass/IntraPaint/commit/3e23772cc286b0f936824bf01154dd8b0d0702c4))
* **testing:** keep test runs out of the real user data and log dirs ([#200](https://github.com/centuryglass/IntraPaint/issues/200)) ([29588b9](https://github.com/centuryglass/IntraPaint/commit/29588b960b429920b44ed603d8f31e4ad1959d15))
* **tools:** deliver each canvas mouse event to the tool once, and add transform tool tests ([9a05cb2](https://github.com/centuryglass/IntraPaint/commit/9a05cb2b08630c833b6b2e69ae41c27d8e45c1e8))
* **tools:** deliver each canvas mouse event to the tool once, in view coordinates ([1a2637b](https://github.com/centuryglass/IntraPaint/commit/1a2637ba75b01d1aa7a7997db2f49e861d7d94fa)), closes [#76](https://github.com/centuryglass/IntraPaint/issues/76)
* **tools:** make rotate drags follow the cursor and keep the origin on resize ([#120](https://github.com/centuryglass/IntraPaint/issues/120)) ([05103f5](https://github.com/centuryglass/IntraPaint/commit/05103f52757d06be395c7defa51383af7d4d2c0f))
* **tools:** scale and rotate layers about the transformation origin ([5a8c93a](https://github.com/centuryglass/IntraPaint/commit/5a8c93abe332de4a427af7c1e05a6ce44b906a72))
* **tools:** scale and rotate layers about the transformation origin ([9445a71](https://github.com/centuryglass/IntraPaint/commit/9445a719adfd847599a6c374d958d1d572ea784c))
* **tools:** show the same X/Y in the text and transform tools ([#223](https://github.com/centuryglass/IntraPaint/issues/223)) ([cc23163](https://github.com/centuryglass/IntraPaint/commit/cc231633ff7b81b6c042664161c79991057cac84))
* **ui:** ask before closing the main window ([7254763](https://github.com/centuryglass/IntraPaint/commit/72547632fcac6434da11bd04cee1e0828731d8b7))
* **ui:** ask before closing the main window ([78aa600](https://github.com/centuryglass/IntraPaint/commit/78aa600c217814b44d4aa841ae87aad38c8060fa))
* **ui:** correct layer_height getter returning width box value ([8b1481e](https://github.com/centuryglass/IntraPaint/commit/8b1481e1de16eb8c615a65cd49450a8f64ae5229))
* **ui:** show MyPaint brushes in scrolling icon lists sized to the panel ([#240](https://github.com/centuryglass/IntraPaint/issues/240)) ([f64f1bc](https://github.com/centuryglass/IntraPaint/commit/f64f1bc33ea9e71765b1db4c8edb6426e5b1e889))
* **ui:** size the layer, layer transform, color and toggle controls to fit their contents ([#239](https://github.com/centuryglass/IntraPaint/issues/239)) ([cea6701](https://github.com/centuryglass/IntraPaint/commit/cea67016943f2436382dd9ecfb1ac529594ee0ac))
* **ui:** stop clipping dock tab bars, key hints, selection buttons and the text preview ([#242](https://github.com/centuryglass/IntraPaint/issues/242)) ([49830fc](https://github.com/centuryglass/IntraPaint/commit/49830fc952a8db8db45b63b9c91d58e805de8011))
* **ui:** use _height_box for layer_height getter and fix setter parameter name ([e5eab85](https://github.com/centuryglass/IntraPaint/commit/e5eab854ac17994442eab25ce69f5f84862e3a79)), closes [#12](https://github.com/centuryglass/IntraPaint/issues/12)
* use os.makedirs(exist_ok=True) to fix TOCTOU race in _adjust_defaults ([#97](https://github.com/centuryglass/IntraPaint/issues/97)) ([e573298](https://github.com/centuryglass/IntraPaint/commit/e573298abc208f9d0d03c3241e2b3f4cd0de9bd1))
* **util:** fix text sizing, alignment and parameter bugs found by new helper tests ([#181](https://github.com/centuryglass/IntraPaint/issues/181)) ([3042002](https://github.com/centuryglass/IntraPaint/commit/3042002f171fab68f5c08a1f32f7e54a4b9c7ddf))
* **view:** show the root layer group's opacity and mode once ([#205](https://github.com/centuryglass/IntraPaint/issues/205)) ([ac2174c](https://github.com/centuryglass/IntraPaint/commit/ac2174c38a25e3cd50176f50ab2fc1f8f40f7f8d)), closes [#150](https://github.com/centuryglass/IntraPaint/issues/150)
* **view:** stop using the deprecated QMouseEvent.pos() when panning ([#225](https://github.com/centuryglass/IntraPaint/issues/225)) ([c6c3e1b](https://github.com/centuryglass/IntraPaint/commit/c6c3e1b505468696364ee7f87202c20e81acf482))


### Performance Improvements

* **brush:** pin draw tool output with golden tests and make strokes about twice as fast ([#121](https://github.com/centuryglass/IntraPaint/issues/121)) ([656ad8e](https://github.com/centuryglass/IntraPaint/commit/656ad8e221fe5556961f8afaab97f5ab1e05018b))
* **brush:** pin MyPaint brush output with golden tests, fix alpha lock and mid-stroke rounding, cut tile callback overhead ([#143](https://github.com/centuryglass/IntraPaint/issues/143)) ([379def6](https://github.com/centuryglass/IntraPaint/commit/379def610d0acaa513f0193056f04d6f54336562))
* **smudge:** make long smudge strokes up to 30x faster and keep the window responsive ([#109](https://github.com/centuryglass/IntraPaint/issues/109)) ([32324a2](https://github.com/centuryglass/IntraPaint/commit/32324a2b97e9df85b54b404861c36b8c707b512f))

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
