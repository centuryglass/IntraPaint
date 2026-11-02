# Changelog and release notes

## [1.5.0](https://github.com/centuryglass/IntraPaint/compare/v1.4.0...v1.5.0) (2026-11-02)


### Features

* **config:** save only non-default values and version saved config files ([#636](https://github.com/centuryglass/IntraPaint/issues/636)) ([9b16b3f](https://github.com/centuryglass/IntraPaint/commit/9b16b3ff286f47cf5e4bbd7dee5fa9508c321988)), closes [#624](https://github.com/centuryglass/IntraPaint/issues/624)
* **controlnet:** rebuild the ControlNet tab with unit state on its tabs and a summary for units that are off ([#537](https://github.com/centuryglass/IntraPaint/issues/537)) ([1646623](https://github.com/centuryglass/IntraPaint/commit/1646623b7dcb7b970bec6b2d95e7323e4130e338))
* **eraser:** preview erasing in the Eraser panel ([#431](https://github.com/centuryglass/IntraPaint/issues/431)) ([b2c0d1b](https://github.com/centuryglass/IntraPaint/commit/b2c0d1b6949ddd62397a9165f6846e8e7b047bbf))
* **file formats:** save top-level layers as an animated GIF, WebP, APNG or AVIF ([#650](https://github.com/centuryglass/IntraPaint/issues/650)) ([552899e](https://github.com/centuryglass/IntraPaint/commit/552899ed36decb849da8d2ad8cf519ed776a8068))
* **generation:** add soft inpainting option for Stable Diffusion inpainting ([#700](https://github.com/centuryglass/IntraPaint/issues/700)) ([bab490e](https://github.com/centuryglass/IntraPaint/commit/bab490e83e0c1fe19746bd5a76954a79f0600f63))
* **generation:** arrange the generation panel by how often each control is used ([#477](https://github.com/centuryglass/IntraPaint/issues/477)) ([e401127](https://github.com/centuryglass/IntraPaint/commit/e40112730af5e75c7201478163258ff69fc335e7)), closes [#450](https://github.com/centuryglass/IntraPaint/issues/450) [#321](https://github.com/centuryglass/IntraPaint/issues/321)
* **generation:** redesign the generated image selector ([#608](https://github.com/centuryglass/IntraPaint/issues/608)) ([f90c901](https://github.com/centuryglass/IntraPaint/commit/f90c901e643efaeb67735d6dd253776bf6a33c4e)), closes [#326](https://github.com/centuryglass/IntraPaint/issues/326)
* **generation:** show when tiling is on, and ignore inpaint full resolution while it is ([#534](https://github.com/centuryglass/IntraPaint/issues/534)) ([52ed341](https://github.com/centuryglass/IntraPaint/commit/52ed341c410e8bba2cab671330825ae0fc116e52))
* **inpaint:** mask blur control, and inpainting results without a hard edge ([#339](https://github.com/centuryglass/IntraPaint/issues/339)) ([9c34ef9](https://github.com/centuryglass/IntraPaint/commit/9c34ef9e6cc1204274c8ca71734f448ab961efe4))
* **layers:** add a selected-layer header, uniform rows and an image strip to the layer panel ([#596](https://github.com/centuryglass/IntraPaint/issues/596)) ([a3c5acd](https://github.com/centuryglass/IntraPaint/commit/a3c5acdf5a2c7a8b36a516fbaf23d3505bd17ace)), closes [#319](https://github.com/centuryglass/IntraPaint/issues/319)
* **layers:** add NonDestructiveLayer base and .ora extension hooks ([#702](https://github.com/centuryglass/IntraPaint/issues/702)) ([5a4db17](https://github.com/centuryglass/IntraPaint/commit/5a4db1726e3f4c46fecc841bf900fe8dfb9578ed))
* **layers:** grouped context menu, Duplicate, F2 rename, drop hints and thumbnail size ([#640](https://github.com/centuryglass/IntraPaint/issues/640)) ([d282a9b](https://github.com/centuryglass/IntraPaint/commit/d282a9bb0e192cc2686c0f7b4b5a574d4f75e1c5)), closes [#320](https://github.com/centuryglass/IntraPaint/issues/320)
* **navigation:** segmented mode toggle, dimmed outside view and an aspect-fit viewer ([#539](https://github.com/centuryglass/IntraPaint/issues/539)) ([ddac1f6](https://github.com/centuryglass/IntraPaint/commit/ddac1f60bb98ac1d9426dd979fccb41947e4e715))
* open animated GIF, WebP, APNG and AVIF files as one layer per frame ([#331](https://github.com/centuryglass/IntraPaint/issues/331)) ([43c571c](https://github.com/centuryglass/IntraPaint/commit/43c571c8a6cbbc2b9a1ce65511d87fdf64beef66)), closes [#329](https://github.com/centuryglass/IntraPaint/issues/329)
* Reopen the last batch of generated image options ([#300](https://github.com/centuryglass/IntraPaint/issues/300)) ([2da6bd5](https://github.com/centuryglass/IntraPaint/commit/2da6bd5a2575f7207d57bcfab5e2b867614c8148))
* **scripts:** add --edit-mode flag to capture_ui.py ([#428](https://github.com/centuryglass/IntraPaint/issues/428)) ([f1a683c](https://github.com/centuryglass/IntraPaint/commit/f1a683cfaef47c8a6ba33648045de1836ad7b1c4))
* **scripts:** export the loading preview as a looping GIF ([#442](https://github.com/centuryglass/IntraPaint/issues/442)) ([1da9b54](https://github.com/centuryglass/IntraPaint/commit/1da9b540808aabfa62ec4b794c0656dca4e673c6))
* **selection:** add replace/intersect modes and Shift/Alt modifiers to selection tools ([#287](https://github.com/centuryglass/IntraPaint/issues/287)) ([9c59120](https://github.com/centuryglass/IntraPaint/commit/9c591202087188d24c872f70cf0b6c2441f2aed2))
* **tools:** edit context pins with the right button in every selection tool ([#328](https://github.com/centuryglass/IntraPaint/issues/328)) ([ae0b9be](https://github.com/centuryglass/IntraPaint/commit/ae0b9beb23411c1212d818bc2a4513fa1743742c))
* **tools:** eyedropper right-click picks the background color ([#707](https://github.com/centuryglass/IntraPaint/issues/707)) ([0af5f7c](https://github.com/centuryglass/IntraPaint/commit/0af5f7ce74cc6c841330246327511bdf5a50654a))
* **ui:** add a dock context menu to tab panels together or move them to a window edge ([#369](https://github.com/centuryglass/IntraPaint/issues/369)) ([a02e21b](https://github.com/centuryglass/IntraPaint/commit/a02e21b5fc7aa8edf7f6f212808eac9d0d331f0e))
* **ui:** add a drag notch to docked panels' upper-left corners ([#391](https://github.com/centuryglass/IntraPaint/issues/391)) ([9f62efb](https://github.com/centuryglass/IntraPaint/commit/9f62efb4c17bc197451622fa54ca2ac1576435da))
* **ui:** add a Layouts menu for saving, applying and managing panel layouts ([#654](https://github.com/centuryglass/IntraPaint/issues/654)) ([c9cef0b](https://github.com/centuryglass/IntraPaint/commit/c9cef0bdacf5a4c53289df29d6384d24e8dfb1ae))
* **ui:** add a setting for a static loading indicator ([#473](https://github.com/centuryglass/IntraPaint/issues/473)) ([abeb772](https://github.com/centuryglass/IntraPaint/commit/abeb7726300ad022f39454570e659555f2b2214b))
* **ui:** add a trailing pinned column and opt-in column packing to strip docks ([#453](https://github.com/centuryglass/IntraPaint/issues/453)) ([c718301](https://github.com/centuryglass/IntraPaint/commit/c718301bbceb622919c8246e34f620bc01a0af8b))
* **ui:** add a UI language setting that labels machine-translated languages ([#724](https://github.com/centuryglass/IntraPaint/issues/724)) ([485c07e](https://github.com/centuryglass/IntraPaint/commit/485c07e4ef9ffcc2369625d28a736ae4836f274b)), closes [#673](https://github.com/centuryglass/IntraPaint/issues/673)
* **ui:** add a View menu for view-only actions ([#367](https://github.com/centuryglass/IntraPaint/issues/367)) ([d6f592a](https://github.com/centuryglass/IntraPaint/commit/d6f592aece55c2348e5bbb16af1753c4c759adc6))
* **ui:** Add five variations to the loading indicators ([#454](https://github.com/centuryglass/IntraPaint/issues/454)) ([394e4e4](https://github.com/centuryglass/IntraPaint/commit/394e4e42a422c7f373f7a28b5328587d4b4b3e67))
* **ui:** add GeometryBlock for position, size, scale and angle fields ([#308](https://github.com/centuryglass/IntraPaint/issues/308)) ([#361](https://github.com/centuryglass/IntraPaint/issues/361)) ([820a24d](https://github.com/centuryglass/IntraPaint/commit/820a24d4b5428cd55bc62e56ceeecb2d9ac3b064))
* **ui:** add orientation and size class model with DockPanel ([#356](https://github.com/centuryglass/IntraPaint/issues/356)) ([3aa0dbf](https://github.com/centuryglass/IntraPaint/commit/3aa0dbf472287e4fc6fbde9bdbec635c8ee80c3f))
* **ui:** add panel sections, header, disabled banner and button weights ([#306](https://github.com/centuryglass/IntraPaint/issues/306)) ([#355](https://github.com/centuryglass/IntraPaint/issues/355)) ([faca47f](https://github.com/centuryglass/IntraPaint/commit/faca47f5593a01b4bd9b4de6e67f26902a389876))
* **ui:** add section headers to the stroke block and a More popover to the Tools panel ([#399](https://github.com/centuryglass/IntraPaint/issues/399)) ([55ce24a](https://github.com/centuryglass/IntraPaint/commit/55ce24a3aa23e40ead530061cebee2bae040fc7f))
* **ui:** add SegmentedControl for short choices ([#354](https://github.com/centuryglass/IntraPaint/issues/354)) ([3bcbb91](https://github.com/centuryglass/IntraPaint/commit/3bcbb9147595eccb0672d7af3603fce4de7b53d5))
* **ui:** add SliderField and NumberField input fields ([#304](https://github.com/centuryglass/IntraPaint/issues/304)) ([#350](https://github.com/centuryglass/IntraPaint/issues/350)) ([7169b77](https://github.com/centuryglass/IntraPaint/commit/7169b77dcaaa9993c0413dc025f255870952ed8d))
* **ui:** cycle the Diffusion Ring through all its images ([#466](https://github.com/centuryglass/IntraPaint/issues/466)) ([66b09d1](https://github.com/centuryglass/IntraPaint/commit/66b09d1655b8e135cefc45869162596d8d66f510))
* **ui:** divide the generation panel's pinned sections, fix prompt spacing ([#542](https://github.com/centuryglass/IntraPaint/issues/542)) ([5e29f3f](https://github.com/centuryglass/IntraPaint/commit/5e29f3f307dcc1e0b42f407001f347d00b0944b7))
* **ui:** dock panels with QDockWidget instead of custom tab boxes ([#358](https://github.com/centuryglass/IntraPaint/issues/358)) ([30fd230](https://github.com/centuryglass/IntraPaint/commit/30fd230a5f72e5f94d00f590570be9632aab7dca))
* **ui:** drag panels by their rail buttons, and hide docked panels' title bars ([#385](https://github.com/centuryglass/IntraPaint/issues/385)) ([db6d001](https://github.com/centuryglass/IntraPaint/commit/db6d0016682a5c90053ad3708e78b4fb6f875615))
* **ui:** fit panels to their measured space, and show the brush preview wherever it fits ([#393](https://github.com/centuryglass/IntraPaint/issues/393)) ([641e19f](https://github.com/centuryglass/IntraPaint/commit/641e19fda851d8b9758f3cf235bacb01f1b3719d))
* **ui:** icon rails for panel docks, recent tools and Generate ([#363](https://github.com/centuryglass/IntraPaint/issues/363)) ([b5d403e](https://github.com/centuryglass/IntraPaint/commit/b5d403eaa6f64aae4b46cafa69ff71be3619c4ad))
* **ui:** improve selection icons, default selection color ([#573](https://github.com/centuryglass/IntraPaint/issues/573)) ([5685b53](https://github.com/centuryglass/IntraPaint/commit/5685b539c4a5741935fb67324e6ef5007f38bad1))
* **ui:** keep tab groups open and ordered by what they show ([#588](https://github.com/centuryglass/IntraPaint/issues/588)) ([0fc2bf4](https://github.com/centuryglass/IntraPaint/commit/0fc2bf4d3b7e22f653230c1bdd4e209e381b9dce)), closes [#579](https://github.com/centuryglass/IntraPaint/issues/579)
* **ui:** let a DockPanel section collapse to its summary by fit ([#468](https://github.com/centuryglass/IntraPaint/issues/468)) ([1b702b8](https://github.com/centuryglass/IntraPaint/commit/1b702b8b72f84217a2823aa1725813208ddd500c))
* **ui:** line up each group's rail buttons with its panels ([#383](https://github.com/centuryglass/IntraPaint/issues/383)) ([93000c3](https://github.com/centuryglass/IntraPaint/commit/93000c32c33485055c8653f657d711859b3a5194))
* **ui:** move eraser, smudge, clone stamp, fill and filter panels onto the stroke block ([#377](https://github.com/centuryglass/IntraPaint/issues/377)) ([2833514](https://github.com/centuryglass/IntraPaint/commit/2833514dd4dddf1dc504edde10d0365cf17b78a4))
* **ui:** move guidance and steps into the generation action block ([#594](https://github.com/centuryglass/IntraPaint/issues/594)) ([2377194](https://github.com/centuryglass/IntraPaint/commit/23771944dd1c6165f141554ecbd8d2760bd64234))
* **ui:** move Layers, Color and Navigation into their own dock group ([#365](https://github.com/centuryglass/IntraPaint/issues/365)) ([0099b07](https://github.com/centuryglass/IntraPaint/commit/0099b07e0345a21857dfcd4700f0d81d9d6ec13f))
* **ui:** outline docks, rails and separators in a themed panel edge color ([#514](https://github.com/centuryglass/IntraPaint/issues/514)) ([471afa4](https://github.com/centuryglass/IntraPaint/commit/471afa4747e3e81a17909ba088b33b60022c3b3a))
* **ui:** pack the stroke tool panels' strip sections into columns ([#671](https://github.com/centuryglass/IntraPaint/issues/671)) ([170a874](https://github.com/centuryglass/IntraPaint/commit/170a8742a53a27136ba720c048d49f977a9d0f5c))
* **ui:** pick a random loading indicator design for each load ([#333](https://github.com/centuryglass/IntraPaint/issues/333)) ([6c6c763](https://github.com/centuryglass/IntraPaint/commit/6c6c763076ad422e371efb7238670b9012c850c4))
* **ui:** plan a panel's orientation from its size, not its dock area ([#447](https://github.com/centuryglass/IntraPaint/issues/447)) ([9dec84d](https://github.com/centuryglass/IntraPaint/commit/9dec84ddd7b0d4d1a2c74ae764adf45abf9c7fab))
* **ui:** preview clone stamping in the Clone stamp tool panel ([#535](https://github.com/centuryglass/IntraPaint/issues/535)) ([b6786c1](https://github.com/centuryglass/IntraPaint/commit/b6786c1a684e3101dca0e29488f7b8e68b06b436)), closes [#405](https://github.com/centuryglass/IntraPaint/issues/405)
* **ui:** preview filtering in the Filter tool panel ([#478](https://github.com/centuryglass/IntraPaint/issues/478)) ([4578ea6](https://github.com/centuryglass/IntraPaint/commit/4578ea606d08b98f7546c17a4bf5d588d93cdd07))
* **ui:** preview smudging in the Smudge tool panel ([#470](https://github.com/centuryglass/IntraPaint/issues/470)) ([481a04c](https://github.com/centuryglass/IntraPaint/commit/481a04cb20bd398b4516bedc3c640e8f410ef507))
* **ui:** rebuild the Stable Diffusion panel as sections with a pinned Generate and a pinned strip prompt column ([#436](https://github.com/centuryglass/IntraPaint/issues/436)) ([597e377](https://github.com/centuryglass/IntraPaint/commit/597e377b0fd34708c3d14ddfb2fe36ee9649beda))
* **ui:** redesign the canvas bottom bar ([#590](https://github.com/centuryglass/IntraPaint/issues/590))  ([2c40f07](https://github.com/centuryglass/IntraPaint/commit/2c40f07ca834c77f93679c7a5abef78a6cbb5442))
* **ui:** redesign the generation area tool panel ([#614](https://github.com/centuryglass/IntraPaint/issues/614)) ([f7bf9ab](https://github.com/centuryglass/IntraPaint/commit/f7bf9ab375cdfd68b50f8d270712b8540dd3d325)), closes [#323](https://github.com/centuryglass/IntraPaint/issues/323)
* **ui:** redesign the layer transform panel around the geometry block, with Revert and Clear transform ([#522](https://github.com/centuryglass/IntraPaint/issues/522)) ([d9f3070](https://github.com/centuryglass/IntraPaint/commit/d9f3070bbb7ab731154d1f240b197a9ffee867e4))
* **ui:** redesign the MyPaint brush panel with named tiles, category chips, favorites and brush dynamics ([#400](https://github.com/centuryglass/IntraPaint/issues/400)) ([f1dc7a2](https://github.com/centuryglass/IntraPaint/commit/f1dc7a2025fad025c8c62bfbb69a839d0fca6fc2))
* **ui:** redesign the selection tool panels ([#315](https://github.com/centuryglass/IntraPaint/issues/315)) ([#430](https://github.com/centuryglass/IntraPaint/issues/430)) ([c9d4439](https://github.com/centuryglass/IntraPaint/commit/c9d443971f5d8add8daf090366e9a334cbdea6fd))
* **ui:** redesign the settings window with a category sidebar, search and typed controls ([#712](https://github.com/centuryglass/IntraPaint/issues/712)) ([55ec414](https://github.com/centuryglass/IntraPaint/commit/55ec414d5c7f0023345daf6a97085a999917f103))
* **ui:** redesign the shape tool panel with segmented shape type and join, and one Outline section ([#475](https://github.com/centuryglass/IntraPaint/issues/475)) ([035cb79](https://github.com/centuryglass/IntraPaint/commit/035cb790e3b2acfce282a61849db496ecb6e93bb)), closes [#316](https://github.com/centuryglass/IntraPaint/issues/316)
* **ui:** redesign the text tool panel with text box first, Font and Style sections, and one box-fit choice ([#479](https://github.com/centuryglass/IntraPaint/issues/479)) ([51ae401](https://github.com/centuryglass/IntraPaint/commit/51ae4014c85573343edbfbda47277c5ed3a89374)), closes [#317](https://github.com/centuryglass/IntraPaint/issues/317) [#255](https://github.com/centuryglass/IntraPaint/issues/255)
* **ui:** render the brush stroke preview with the real brush ([#415](https://github.com/centuryglass/IntraPaint/issues/415)) ([a022ec5](https://github.com/centuryglass/IntraPaint/commit/a022ec52ba4fe915e30e0ffb09b28d077e8eda17))
* **ui:** replace the generation area tool icon with a lit window ([#709](https://github.com/centuryglass/IntraPaint/issues/709)) ([bfa1bfb](https://github.com/centuryglass/IntraPaint/commit/bfa1bfbc7d62944b4acb11f23eda7a9d13ff825c))
* **ui:** restore window geometry safely across display changes ([#351](https://github.com/centuryglass/IntraPaint/issues/351)) ([48e6838](https://github.com/centuryglass/IntraPaint/commit/48e6838ba25e95edf456c10f7585f394d87322cf))
* **ui:** restyle the GLID and test generator panels onto kit sections ([#639](https://github.com/centuryglass/IntraPaint/issues/639)) ([3f37ebf](https://github.com/centuryglass/IntraPaint/commit/3f37ebf1a258793ac5bda75b93764e8673c6973d))
* **ui:** rich tooltips with keycap-styled key bindings ([#347](https://github.com/centuryglass/IntraPaint/issues/347)) ([cde9140](https://github.com/centuryglass/IntraPaint/commit/cde9140ad97d98e48e7426f577a3dbacce19faf9))
* **ui:** rounded menus and tooltips with hard shadows ([#291](https://github.com/centuryglass/IntraPaint/issues/291)) ([3c4ec08](https://github.com/centuryglass/IntraPaint/commit/3c4ec08206c3fc4d3b395e80012f580cd14a03b0))
* **ui:** shared dialog footer button row ([#695](https://github.com/centuryglass/IntraPaint/issues/695)) ([81c7b31](https://github.com/centuryglass/IntraPaint/commit/81c7b31ee73085ea721ce94fc511bc98b761c89c))
* **ui:** shared stroke block for paint tool panels, starting with Draw ([#373](https://github.com/centuryglass/IntraPaint/issues/373)) ([3ba3015](https://github.com/centuryglass/IntraPaint/commit/3ba301588f39c0c50ea9b2b4408b5677e9742194))
* **ui:** show a floating panel's rail button in its own title bar ([#386](https://github.com/centuryglass/IntraPaint/issues/386)) ([d2588e4](https://github.com/centuryglass/IntraPaint/commit/d2588e4c207b19d74b12c5c72565ce366dbe7f2e))
* **ui:** show key bindings in tool and layer button tooltips ([#290](https://github.com/centuryglass/IntraPaint/issues/290)) ([55b201a](https://github.com/centuryglass/IntraPaint/commit/55b201ac4eafaf0c4ad7093ca85e43d23f0fbf76))
* **ui:** show one panel per dock group, with the edge rails as its only tabs ([#379](https://github.com/centuryglass/IntraPaint/issues/379)) ([63e0f8a](https://github.com/centuryglass/IntraPaint/commit/63e0f8ae8cd6c367b0af0aa21ee0c36fc104afd6))
* **ui:** show the enabled ControlNet unit count on its rail button while the panel is hidden ([#471](https://github.com/centuryglass/IntraPaint/issues/471)) ([2cb8d25](https://github.com/centuryglass/IntraPaint/commit/2cb8d2544499ade76614342fc15210fe296670b3)), closes [#451](https://github.com/centuryglass/IntraPaint/issues/451)
* **ui:** show the layer count in the floating layer panel's title bar ([#617](https://github.com/centuryglass/IntraPaint/issues/617)) ([1b8be96](https://github.com/centuryglass/IntraPaint/commit/1b8be966817a702e9cb5a690ffbbd6303d6b6955)), closes [#607](https://github.com/centuryglass/IntraPaint/issues/607)
* **ui:** show titles, icons and action-named buttons in message boxes ([#705](https://github.com/centuryglass/IntraPaint/issues/705)) ([ad26a90](https://github.com/centuryglass/IntraPaint/commit/ad26a9055f4a93230e3a71b9b38063e64c5176ec))
* **ui:** slim tool strip with an active tool header, and a minimum canvas size ([#370](https://github.com/centuryglass/IntraPaint/issues/370)) ([00d509e](https://github.com/centuryglass/IntraPaint/commit/00d509e9ce195f512d65e58a86610f524e4c85ce))
* **ui:** split a panel beside a group from the dock menu, and share panel moves in dock_placement ([#384](https://github.com/centuryglass/IntraPaint/issues/384)) ([6f347ad](https://github.com/centuryglass/IntraPaint/commit/6f347ad605127e11fd78de1f55dd068760947b5c))
* **ui:** store named dock layouts and apply them at runtime ([#649](https://github.com/centuryglass/IntraPaint/issues/649)) ([2f01cf1](https://github.com/centuryglass/IntraPaint/commit/2f01cf12ab86f4a488b2af303b51dda490fd9092))
* **ui:** use two tool columns in the horizontal tool panel when buttons keep their size ([#395](https://github.com/centuryglass/IntraPaint/issues/395)) ([480c3f9](https://github.com/centuryglass/IntraPaint/commit/480c3f92b9f23bc98280a626eb2ca531ba2c8474))


### Bug Fixes

* **agents:** pin issue fetches to origin and add the OpenCode issue-cache hook ([#298](https://github.com/centuryglass/IntraPaint/issues/298)) ([6263b11](https://github.com/centuryglass/IntraPaint/commit/6263b117bc98b3af9f51ebd205291050bc676cae))
* **brush-preview:** keep the stroke visible against the preview background ([#434](https://github.com/centuryglass/IntraPaint/issues/434)) ([533ba5e](https://github.com/centuryglass/IntraPaint/commit/533ba5e5fbf5258f35023c4a5122d96f531c2cc9))
* **brushes:** stop MyPaintLayerSurface callbacks from leaking the surface ([#559](https://github.com/centuryglass/IntraPaint/issues/559)) ([889d6e6](https://github.com/centuryglass/IntraPaint/commit/889d6e6806dd2c96a2f83aa8294523551bfed74b))
* clear undo history when opening or creating an image, and drop the previous image's generated options ([#337](https://github.com/centuryglass/IntraPaint/issues/337)) ([18b6d72](https://github.com/centuryglass/IntraPaint/commit/18b6d72b361010efea868437abf4b2165053845d))
* **config:** correct typos and swapped backend names in setting labels ([#518](https://github.com/centuryglass/IntraPaint/issues/518)) ([064879a](https://github.com/centuryglass/IntraPaint/commit/064879a30ae6f32e2f017dd326924a4b5f7b819d))
* **config:** disconnect widget config callbacks on destroyed ([#462](https://github.com/centuryglass/IntraPaint/issues/462)) ([f7c4ce9](https://github.com/centuryglass/IntraPaint/commit/f7c4ce9b89bb4d5f4957a12547c4fbc7e960bfd7))
* **config:** report speed-modifier keybinding conflicts instead of raising KeyError ([#359](https://github.com/centuryglass/IntraPaint/issues/359)) ([eb35be6](https://github.com/centuryglass/IntraPaint/commit/eb35be6b848875512b35528ece7daf5053f296d8)), closes [#357](https://github.com/centuryglass/IntraPaint/issues/357)
* **config:** show the WebUI setting type error instead of its translation context ([#566](https://github.com/centuryglass/IntraPaint/issues/566)) ([5d3af58](https://github.com/centuryglass/IntraPaint/commit/5d3af5888d833e8e4fc2c7d2d59796eeacf3b402))
* **config:** show translated option names while saving the stored option ([#340](https://github.com/centuryglass/IntraPaint/issues/340)) ([cb16639](https://github.com/centuryglass/IntraPaint/commit/cb16639fe4ed255d07330a7b5605b157b4263f6c))
* **config:** stop translating stored config option strings ([#336](https://github.com/centuryglass/IntraPaint/issues/336)) ([db102b0](https://github.com/centuryglass/IntraPaint/commit/db102b0900f8e3b74f16d36b643c883191a39696))
* **controlnet:** save a control image path typed into the path field ([#536](https://github.com/centuryglass/IntraPaint/issues/536)) ([69d3579](https://github.com/centuryglass/IntraPaint/commit/69d357906f6632fb4a6a0cf9d9b4f6ea4ce84c36))
* **controlnet:** show a unit list and a preview column in strips ([#591](https://github.com/centuryglass/IntraPaint/issues/591)) ([2762c96](https://github.com/centuryglass/IntraPaint/commit/2762c9634c16f597df2a19a2c8112bce2657c038)), closes [#583](https://github.com/centuryglass/IntraPaint/issues/583)
* fall back to a system lrelease when PySide6 doesn't bundle one ([#641](https://github.com/centuryglass/IntraPaint/issues/641)) ([31b6770](https://github.com/centuryglass/IntraPaint/commit/31b67702d3a791879a311ad57edbdefc4c3c429b))
* **filters:** pivot contrast on a fixed mid-gray ([#472](https://github.com/centuryglass/IntraPaint/issues/472)) ([33323cb](https://github.com/centuryglass/IntraPaint/commit/33323cb98c93992b69ba09ae777e248eb850dfc1)), closes [#192](https://github.com/centuryglass/IntraPaint/issues/192)
* **filters:** stop applying a filter leaving its task in a reference cycle ([#589](https://github.com/centuryglass/IntraPaint/issues/589)) ([fc971dd](https://github.com/centuryglass/IntraPaint/commit/fc971dd7af42cfcde438e69b7b9968d82c046355))
* **formats:** keep EPS files away from Ghostscript through Qt's image plugins ([#292](https://github.com/centuryglass/IntraPaint/issues/292)) ([89bfe5f](https://github.com/centuryglass/IntraPaint/commit/89bfe5f93f1cd905320796e71726972a15414736))
* **generation:** run WebUI generation through sd-backend-client ([#275](https://github.com/centuryglass/IntraPaint/issues/275)) ([8f637fb](https://github.com/centuryglass/IntraPaint/commit/8f637fb9bb4d192543837d7b77f24804dd0525c5))
* **hotkeys:** filter key presses on focused windows, and report stale event sources ([#463](https://github.com/centuryglass/IntraPaint/issues/463)) ([8599e7a](https://github.com/centuryglass/IntraPaint/commit/8599e7a5027604bb0b7bc7c9fd4b46563153e412))
* **layers:** hold a layer's parent weakly so groups don't leave reference cycles ([#564](https://github.com/centuryglass/IntraPaint/issues/564)) ([b83f6e5](https://github.com/centuryglass/IntraPaint/commit/b83f6e5be5a8774cc5c1854adb91185c57bb716b))
* **layers:** keep a base layer's alpha when merging down onto an alpha-locked layer ([#701](https://github.com/centuryglass/IntraPaint/issues/701)) ([ab5001c](https://github.com/centuryglass/IntraPaint/commit/ab5001c328ffb80ae68fd5ad1de799792f53fea9)), closes [#212](https://github.com/centuryglass/IntraPaint/issues/212)
* **layers:** keep layers' visibility when undoing changes made inside a hidden group ([#452](https://github.com/centuryglass/IntraPaint/issues/452)) ([a319ac9](https://github.com/centuryglass/IntraPaint/commit/a319ac93cf8200a092015db3c0dd25de4ef1f81d))
* **layers:** let visibility changes bypass the locked-layer check ([#444](https://github.com/centuryglass/IntraPaint/issues/444)) ([7a81cb6](https://github.com/centuryglass/IntraPaint/commit/7a81cb64355e87e3d8d83045bf57defe807ccf42))
* **layers:** make ImageStack.batching_content_updates nestable and exception-safe ([#282](https://github.com/centuryglass/IntraPaint/issues/282)) ([90c1072](https://github.com/centuryglass/IntraPaint/commit/90c1072b3a43a965c040ed252a65a5aa2869cdae))
* **layers:** name every loaded image's layer "layer 1" ([#349](https://github.com/centuryglass/IntraPaint/issues/349)) ([6f43de2](https://github.com/centuryglass/IntraPaint/commit/6f43de2cf51a5437fef8127f31cbf59ed7ff64c5))
* **layers:** stop recursive_child_layers leaving a reference cycle ([#502](https://github.com/centuryglass/IntraPaint/issues/502)) ([df5bdd2](https://github.com/centuryglass/IntraPaint/commit/df5bdd2e91b408f18fd9ab5ab4e96404ac5f5294))
* **layers:** toggle a layer's visibility without changing its group or siblings ([#469](https://github.com/centuryglass/IntraPaint/issues/469)) ([6b90882](https://github.com/centuryglass/IntraPaint/commit/6b908827da4693ffcde4db24aad0afa626d621c1))
* **navigation:** hide the navigation window's zoom slider and hints when they don't fit ([#540](https://github.com/centuryglass/IntraPaint/issues/540)) ([abc3a5e](https://github.com/centuryglass/IntraPaint/commit/abc3a5e1977932ee5040a977715aacd057653dff))
* silence benign Qt warning when dragging docks under Wayland ([#644](https://github.com/centuryglass/IntraPaint/issues/644)) ([113dd7b](https://github.com/centuryglass/IntraPaint/commit/113dd7b8251652ef917480fe9b9b16005d9513bd))
* stop outline and preview line animations while hidden or empty ([#610](https://github.com/centuryglass/IntraPaint/issues/610)) ([b9418f4](https://github.com/centuryglass/IntraPaint/commit/b9418f42b4122a3d7bddf144593f4fa7210d6492))
* stop startup timer warnings and a stray window from the layer panel ([#623](https://github.com/centuryglass/IntraPaint/issues/623)) ([22c7c14](https://github.com/centuryglass/IntraPaint/commit/22c7c14402e66d59de100e67388b848e72506659))
* stop the window clamp from resizing the main window forever ([#611](https://github.com/centuryglass/IntraPaint/issues/611)) ([088189d](https://github.com/centuryglass/IntraPaint/commit/088189ddc69939cc0ca823bc359b7ead2e5a1ce1))
* **tools:** clamp brush size keybindings at the size range edges ([#485](https://github.com/centuryglass/IntraPaint/issues/485)) ([8b2430f](https://github.com/centuryglass/IntraPaint/commit/8b2430f16bb00293910af68a99622159f5b1da67))
* **tools:** keep the transform tool's aspect ratio lock after selecting another layer ([#523](https://github.com/centuryglass/IntraPaint/issues/523)) ([a87ed09](https://github.com/centuryglass/IntraPaint/commit/a87ed098a9e6975d0c4d72e8d45bc47207f5720d))
* **tools:** save untranslated shape tool options in Cache ([#517](https://github.com/centuryglass/IntraPaint/issues/517)) ([1e7e8ff](https://github.com/centuryglass/IntraPaint/commit/1e7e8ffd6048b0be7dfe17e1adfa9d049a6a7aab)), closes [#476](https://github.com/centuryglass/IntraPaint/issues/476)
* **tools:** skip hidden layers when picking a layer by clicking the canvas ([#735](https://github.com/centuryglass/IntraPaint/issues/735)) ([4b0a77d](https://github.com/centuryglass/IntraPaint/commit/4b0a77ddae5222db875345838a08005c9bc29f46))
* treat an empty modifier binding as unbound instead of raising ([#438](https://github.com/centuryglass/IntraPaint/issues/438)) ([8cf0a6b](https://github.com/centuryglass/IntraPaint/commit/8cf0a6bf64de7debb3da5d27b3ef7df5fe5344f0))
* **ui:** align generation panel fields at expanded side widths ([#593](https://github.com/centuryglass/IntraPaint/issues/593)) ([358dda5](https://github.com/centuryglass/IntraPaint/commit/358dda5ef987cb14b87f529d47a1a9e371a6bdb2))
* **ui:** break the reference cycles tool control panels were left in ([#560](https://github.com/centuryglass/IntraPaint/issues/560)) ([a068389](https://github.com/centuryglass/IntraPaint/commit/a068389c230d8b4a317246867fadc00255925d6e)), closes [#549](https://github.com/centuryglass/IntraPaint/issues/549)
* **ui:** call the base resizeEvent from ImagePanel ([#567](https://github.com/centuryglass/IntraPaint/issues/567)) ([ed3ee15](https://github.com/centuryglass/IntraPaint/commit/ed3ee15cd835cdeff1554f9d04ad98c0d6be85c3))
* **ui:** call the denoising step count "Steps" everywhere ([#634](https://github.com/centuryglass/IntraPaint/issues/634)) ([4a5c27e](https://github.com/centuryglass/IntraPaint/commit/4a5c27ecab0c2d9e2e27c382046be2b81ec17e6f))
* **ui:** call the generation area by one name ([#621](https://github.com/centuryglass/IntraPaint/issues/621)) ([7c77715](https://github.com/centuryglass/IntraPaint/commit/7c777154d875ae8ef273a38c6e9bbc9670c349ed))
* **ui:** call the guidance setting "CFG scale" everywhere ([#632](https://github.com/centuryglass/IntraPaint/issues/632)) ([fc3baad](https://github.com/centuryglass/IntraPaint/commit/fc3baad1d1faa9c58f8b515472125e8bfb3cba7f))
* **ui:** correct small panel bugs from the UI panel review ([#346](https://github.com/centuryglass/IntraPaint/issues/346)) ([5ee1be9](https://github.com/centuryglass/IntraPaint/commit/5ee1be921c2d217028e63b978d57ff65d3d0055a))
* **ui:** draw keycaps as black text on a white plate ([#388](https://github.com/centuryglass/IntraPaint/issues/388)) ([7f56294](https://github.com/centuryglass/IntraPaint/commit/7f5629418ddb6432b6e5a251d318aa7b6952c015))
* **ui:** draw the outline of floating panels over their content ([#605](https://github.com/centuryglass/IntraPaint/issues/605)) ([6863f5a](https://github.com/centuryglass/IntraPaint/commit/6863f5ae158d4d854ee3f04f449f820b5c79c6ef))
* **ui:** free dropped panels without a cyclic collection, and delete FlowLayout's items ([#464](https://github.com/centuryglass/IntraPaint/issues/464)) ([cd18ec7](https://github.com/centuryglass/IntraPaint/commit/cd18ec7411e9c2a12bc01e17fb50ba83528b72a9))
* **ui:** give the panel corner notch the dock menu and a triangle-shaped hit area ([#409](https://github.com/centuryglass/IntraPaint/issues/409)) ([4c89b84](https://github.com/centuryglass/IntraPaint/commit/4c89b847652c4e61da8536168cb0d14809fab363))
* **ui:** give the stroke tools' checkboxes their own rows in strips ([#646](https://github.com/centuryglass/IntraPaint/issues/646)) ([f1ea158](https://github.com/centuryglass/IntraPaint/commit/f1ea15858dfa18e09df7ee490a8e66ff04150ef6))
* **ui:** hide a dock before tabifying it, so 'Tab with' works on Qt 6.12 ([#604](https://github.com/centuryglass/IntraPaint/issues/604)) ([561a1d4](https://github.com/centuryglass/IntraPaint/commit/561a1d464be2cffe463eaa29fa1f9a071c492f50))
* **ui:** hold panel section and fit-item callbacks weakly ([#505](https://github.com/centuryglass/IntraPaint/issues/505)) ([b065534](https://github.com/centuryglass/IntraPaint/commit/b065534789976263ae1fea2cf6d21101e34e53be))
* **ui:** Improve loading indicator text formatting ([#368](https://github.com/centuryglass/IntraPaint/issues/368)) ([62a8ded](https://github.com/centuryglass/IntraPaint/commit/62a8dedcbbf0e4f05a892907cf4c9d4c253eb612))
* **ui:** inset docked panels from the window edge ([#456](https://github.com/centuryglass/IntraPaint/issues/456)) ([23d7b97](https://github.com/centuryglass/IntraPaint/commit/23d7b978b4805f60848e4dc73a96352e1d44af3c))
* **ui:** keep a size field's boxes visible after it changes orientation ([#435](https://github.com/centuryglass/IntraPaint/issues/435)) ([fcd8987](https://github.com/centuryglass/IntraPaint/commit/fcd8987db2676b78eda9ed2646e6508662a8f387))
* **ui:** keep a small layer panel in side mode and drop its early scroll bar ([#637](https://github.com/centuryglass/IntraPaint/issues/637)) ([36d5d24](https://github.com/centuryglass/IntraPaint/commit/36d5d2466b07832c2909285e7a75da92f58f413e))
* **ui:** keep filter dialogs within the screen size ([#697](https://github.com/centuryglass/IntraPaint/issues/697)) ([d6ec48e](https://github.com/centuryglass/IntraPaint/commit/d6ec48e39f4c8e2e4a152a988ebefeeb45519f8e))
* **ui:** keep generated image selector zoom as a ratio and drop it when the frame changes ([#281](https://github.com/centuryglass/IntraPaint/issues/281)) ([409554d](https://github.com/centuryglass/IntraPaint/commit/409554dc0e8620a4d2742d6c6a35caab6eaa2161))
* **ui:** keep stroke block controls grouped and capped in side and strip layouts ([#397](https://github.com/centuryglass/IntraPaint/issues/397)) ([25389e7](https://github.com/centuryglass/IntraPaint/commit/25389e7ae323e21df2564937719ad5f2c4a57fa8))
* **ui:** label the generation resolution consistently, and fix the mislabeled maximum ([#619](https://github.com/centuryglass/IntraPaint/issues/619)) ([f0f1fc0](https://github.com/centuryglass/IntraPaint/commit/f0f1fc05060648b8d3b7c781a7a43802acde3b85))
* **ui:** let the layer panel shrink after the labeled action bar shows ([#655](https://github.com/centuryglass/IntraPaint/issues/655)) ([ec71d3b](https://github.com/centuryglass/IntraPaint/commit/ec71d3bcf2845be9ed6c46662331c9ef317c7c12))
* **ui:** let the Resize canvas dialog shrink after being enlarged ([#693](https://github.com/centuryglass/IntraPaint/issues/693)) ([4b10309](https://github.com/centuryglass/IntraPaint/commit/4b103094e32134e5ab3f8625a18d1e0b1ec38a4c)), closes [#659](https://github.com/centuryglass/IntraPaint/issues/659)
* **ui:** match the pen pressure link to the panel redesign ([#389](https://github.com/centuryglass/IntraPaint/issues/389)) ([ef8a01c](https://github.com/centuryglass/IntraPaint/commit/ef8a01c9f027d0b39ae486d314e2ee79320eb5af))
* **ui:** move a panel's rail button when the dock menu moves it to the right or bottom edge ([#382](https://github.com/centuryglass/IntraPaint/issues/382)) ([875ad1a](https://github.com/centuryglass/IntraPaint/commit/875ad1a47aa7523b2a0884b26f9950d8a9d45ee3))
* **ui:** pass dock drags over image canvases ([#497](https://github.com/centuryglass/IntraPaint/issues/497)) ([696d6b9](https://github.com/centuryglass/IntraPaint/commit/696d6b9a16f25f24dff0361276eafbabfae4406a))
* **ui:** pick the panel orientation that scrolls less when both overflow ([#616](https://github.com/centuryglass/IntraPaint/issues/616)) ([db1a7a9](https://github.com/centuryglass/IntraPaint/commit/db1a7a9df4ade07258c2b2bddf82a790107d40ef)), closes [#609](https://github.com/centuryglass/IntraPaint/issues/609)
* **ui:** plan the color picker's layout from measured minimum sizes ([#578](https://github.com/centuryglass/IntraPaint/issues/578)) ([f07a57b](https://github.com/centuryglass/IntraPaint/commit/f07a57b828abe185fba8b0d45b790bd32eeecf6c)), closes [#412](https://github.com/centuryglass/IntraPaint/issues/412) [#413](https://github.com/centuryglass/IntraPaint/issues/413)
* **ui:** plan the filter and clone stamp sections with the stroke block ([#587](https://github.com/centuryglass/IntraPaint/issues/587)) ([98003c0](https://github.com/centuryglass/IntraPaint/commit/98003c08eee42a6bbfc0c82a6b550070c99452fe)), closes [#402](https://github.com/centuryglass/IntraPaint/issues/402)
* **ui:** put the stroke preview after the Filter and Source columns in strips ([#653](https://github.com/centuryglass/IntraPaint/issues/653)) ([111539f](https://github.com/centuryglass/IntraPaint/commit/111539f91464a7424a3c89b52cb468fd02ce2400)), closes [#630](https://github.com/centuryglass/IntraPaint/issues/630)
* **ui:** put the stroke preview below the fields in side panels when there's room ([#642](https://github.com/centuryglass/IntraPaint/issues/642)) ([a0b8241](https://github.com/centuryglass/IntraPaint/commit/a0b82419c273fd4f0f8c743d2c3c550443fd2f47))
* **ui:** raise the loading indicator above the central widget ([#362](https://github.com/centuryglass/IntraPaint/issues/362)) ([5741b8e](https://github.com/centuryglass/IntraPaint/commit/5741b8e21dd115f1bec45cbcd4a2ce642a64ac60))
* **ui:** re-measure flow widgets whose planned wrap width missed ([#651](https://github.com/centuryglass/IntraPaint/issues/651)) ([7ac13bd](https://github.com/centuryglass/IntraPaint/commit/7ac13bd982be78b01ac177717ce5208cd4d020c9))
* **ui:** remove inpaint full-res and padding controls from selection panels ([#348](https://github.com/centuryglass/IntraPaint/issues/348)) ([314a9a1](https://github.com/centuryglass/IntraPaint/commit/314a9a1be62a25aa48c1ef5182ae9deb5e386b75)), closes [#302](https://github.com/centuryglass/IntraPaint/issues/302)
* **ui:** rename "Inpaint full resolution" padding to "Context" ([#638](https://github.com/centuryglass/IntraPaint/issues/638)) ([f8f7fc2](https://github.com/centuryglass/IntraPaint/commit/f8f7fc2508c6b82a9c578d2ce753f7273c245f1f)), closes [#532](https://github.com/centuryglass/IntraPaint/issues/532) [#516](https://github.com/centuryglass/IntraPaint/issues/516)
* **ui:** rename "Interrogate" to "Describe" ([#575](https://github.com/centuryglass/IntraPaint/issues/575)) ([2da248e](https://github.com/centuryglass/IntraPaint/commit/2da248e2892bfb642caf1ff72a837a54bcd4161a))
* **ui:** rename the selection fill tool to "Magic wand" ([#586](https://github.com/centuryglass/IntraPaint/issues/586)) ([1315783](https://github.com/centuryglass/IntraPaint/commit/1315783cfd909c2e85c626c376a5ef37582ebcdc))
* **ui:** return focus to the image on Escape in a floating panel's field ([#699](https://github.com/centuryglass/IntraPaint/issues/699)) ([53b11f7](https://github.com/centuryglass/IntraPaint/commit/53b11f744f5b4ab4dfce7f531da54322bb25d6c8)), closes [#465](https://github.com/centuryglass/IntraPaint/issues/465)
* **ui:** scale loading indicator text with its bounds ([#364](https://github.com/centuryglass/IntraPaint/issues/364)) ([782a1b9](https://github.com/centuryglass/IntraPaint/commit/782a1b97b887ef62c70f6f5269e6b7ff471e0d5b))
* **ui:** show the unavailable message for generators with no status ([#698](https://github.com/centuryglass/IntraPaint/issues/698)) ([0b1a7ed](https://github.com/centuryglass/IntraPaint/commit/0b1a7ed73045baac4832bafdd27802c560b46dda)), closes [#661](https://github.com/centuryglass/IntraPaint/issues/661)
* **ui:** show the warning icon on warning dialogs ([#694](https://github.com/centuryglass/IntraPaint/issues/694)) ([af2c45e](https://github.com/centuryglass/IntraPaint/commit/af2c45e444cb0baeef714b470f0169c6a4d0c2ad)), closes [#662](https://github.com/centuryglass/IntraPaint/issues/662)
* **ui:** stop dock rails, docks and the image view forming reference cycles ([#511](https://github.com/centuryglass/IntraPaint/issues/511)) ([00df721](https://github.com/centuryglass/IntraPaint/commit/00df7218983ec55db2b440207a888d8aacfe5617))
* **ui:** stop docks shrinking panels where their content would escape ([#585](https://github.com/centuryglass/IntraPaint/issues/585)) ([aa161fe](https://github.com/centuryglass/IntraPaint/commit/aa161fedcc16f6c44a510fb7ba2208493ccf6206))
* **ui:** stop ImagePanel's scale handler from leaving a reference cycle ([#503](https://github.com/centuryglass/IntraPaint/issues/503)) ([c697223](https://github.com/centuryglass/IntraPaint/commit/c6972235eef7118ee3c1b17b2c1267c2a6dc48f3))
* **ui:** stop InkStyle.styleHint dereferencing stale layout-item wrappers ([#461](https://github.com/centuryglass/IntraPaint/issues/461)) ([8225870](https://github.com/centuryglass/IntraPaint/commit/822587051ae9f5d2f49ca2a63cba0194f0473847))
* **ui:** stop pen pressure reveal from replanning the tool panel on every tablet event ([#441](https://github.com/centuryglass/IntraPaint/issues/441)) ([414188a](https://github.com/centuryglass/IntraPaint/commit/414188a4056349a6cda1d7ef8ee9e8eb6ee94676))
* **ui:** stop ReflowingButtonGroup leaving a reference cycle ([#572](https://github.com/centuryglass/IntraPaint/issues/572)) ([a98a70e](https://github.com/centuryglass/IntraPaint/commit/a98a70e533245a5428f3251f23fc4b2dda8bcc07))
* **ui:** stop restored dock layouts leaving old tab bars drawn over the window ([#375](https://github.com/centuryglass/IntraPaint/issues/375)) ([3e1d945](https://github.com/centuryglass/IntraPaint/commit/3e1d94547bf90f0a1543d43fccba3f8240f231cf))
* **ui:** stop SegmentedControl eliding labels at its own size hint ([#474](https://github.com/centuryglass/IntraPaint/issues/474)) ([bf4d666](https://github.com/centuryglass/IntraPaint/commit/bf4d6667669fad07b64bc26b972cf4a0532a08c8))
* **ui:** stop selection outlines forming a reference cycle ([#501](https://github.com/centuryglass/IntraPaint/issues/501)) ([705413b](https://github.com/centuryglass/IntraPaint/commit/705413bb224dbbb34214c82f3f63796c439573b9))
* **ui:** stop the bug dialog reopening when a tooltip or toolbar triggers a style error ([#366](https://github.com/centuryglass/IntraPaint/issues/366)) ([8299e37](https://github.com/centuryglass/IntraPaint/commit/8299e37a5ee72cd222e50e872ef7f2337d27b45e))
* **ui:** stop the color panel growing without bound when a floating dock shrinks ([#371](https://github.com/centuryglass/IntraPaint/issues/371)) ([97a53a0](https://github.com/centuryglass/IntraPaint/commit/97a53a0b3888041a8911a1a7a7186249f394bcb5))
* **ui:** stop the stroke preview flipping between beside and below while a panel is resized ([#633](https://github.com/centuryglass/IntraPaint/issues/633)) ([7c37868](https://github.com/centuryglass/IntraPaint/commit/7c378686d017938285f1440acb1b54a85a45fed3))
* **ui:** stop transform handles forming reference cycles with their outline ([#521](https://github.com/centuryglass/IntraPaint/issues/521)) ([400343f](https://github.com/centuryglass/IntraPaint/commit/400343f10defcfd7f69482a196f20e998f42356c))
* **ui:** stop wrapping layout items with itemAt, and fail tests that do ([#467](https://github.com/centuryglass/IntraPaint/issues/467)) ([fbad157](https://github.com/centuryglass/IntraPaint/commit/fbad1573c025b97d6a9f7a2a46bfd0742bda1e6e)), closes [#459](https://github.com/centuryglass/IntraPaint/issues/459)
* **ui:** tidy the layer panel's strip, mode row and floating header ([#606](https://github.com/centuryglass/IntraPaint/issues/606)) ([ce9b162](https://github.com/centuryglass/IntraPaint/commit/ce9b162e192cf93af67cb62d5f67949582e0aeb6))
* **ui:** use sentence case for tool names and control labels ([#613](https://github.com/centuryglass/IntraPaint/issues/613)) ([4308fa2](https://github.com/centuryglass/IntraPaint/commit/4308fa280db6cdb7b828d965d09fc48a356d5fca)), closes [#533](https://github.com/centuryglass/IntraPaint/issues/533)


### Performance Improvements

* **color:** build each color picker layout once and move the parts between them ([#561](https://github.com/centuryglass/IntraPaint/issues/561)) ([d5cecc1](https://github.com/centuryglass/IntraPaint/commit/d5cecc138ebf1c83aaa2cb4162345832600d4999))
* drive the outline dash animations with a low-rate timer ([#602](https://github.com/centuryglass/IntraPaint/issues/602)) ([508ebe7](https://github.com/centuryglass/IntraPaint/commit/508ebe71a82dfa974c94df495cc5e3519250d30b))
* only poll hotkeys when the window is active ([#603](https://github.com/centuryglass/IntraPaint/issues/603)) ([ad28120](https://github.com/centuryglass/IntraPaint/commit/ad2812061a99310e4b673768532f1f0332f03ce6))
* **selection:** store the selection mask as Alpha8 and skip whole-image work per edit ([#272](https://github.com/centuryglass/IntraPaint/issues/272)) ([d657c00](https://github.com/centuryglass/IntraPaint/commit/d657c00b71a22797f26c7cdebf4a69c39f3b66ba))
* **selection:** trace selection outlines in time proportional to the selection ([#686](https://github.com/centuryglass/IntraPaint/issues/686)) ([b08583e](https://github.com/centuryglass/IntraPaint/commit/b08583e39da91f1e47a51615191ace7b5ae596ae)), closes [#647](https://github.com/centuryglass/IntraPaint/issues/647)
* **selection:** trace selection outlines with fewer points ([#457](https://github.com/centuryglass/IntraPaint/issues/457)) ([4737ea2](https://github.com/centuryglass/IntraPaint/commit/4737ea293f4893a3e0ad1674997b69f2133ccb59))
* stop the dock tab bar relayout loop that burned a CPU core while idle ([#601](https://github.com/centuryglass/IntraPaint/issues/601)) ([8c9c410](https://github.com/centuryglass/IntraPaint/commit/8c9c41061ef1c1bb0db842a25cb4d55fe465fa08))
* **ui:** measure each fit placement and dock panel header once per plan ([#568](https://github.com/centuryglass/IntraPaint/issues/568)) ([96a126e](https://github.com/centuryglass/IntraPaint/commit/96a126e0d0d3ba52343f2833d79845c760be8611))

## [1.4.0](https://github.com/centuryglass/IntraPaint/compare/v1.3.0...v1.4.0) (2026-10-10)


### Features

* **upscaling:** add tile ControlNet strength, start and end controls ([#267](https://github.com/centuryglass/IntraPaint/issues/267)) ([b7c1026](https://github.com/centuryglass/IntraPaint/commit/b7c10260f28db88efdd9709fb909a650adc52a76))


### Bug Fixes

* **generation:** run ComfyUI generation through sd-backend-client ([#250](https://github.com/centuryglass/IntraPaint/issues/250)) ([0f0aa09](https://github.com/centuryglass/IntraPaint/commit/0f0aa0944d90b71bc5795df72e28918e4079d571)), closes [#103](https://github.com/centuryglass/IntraPaint/issues/103)
* **generation:** stop Stable Diffusion upscaling from crashing when it applies the result ([#264](https://github.com/centuryglass/IntraPaint/issues/264)) ([d590be4](https://github.com/centuryglass/IntraPaint/commit/d590be436d3b95eb8995e355588b809ff11e3c82))
* **layers:** render scaled and rotated layers from an image-space raster ([#249](https://github.com/centuryglass/IntraPaint/issues/249)) ([22d2782](https://github.com/centuryglass/IntraPaint/commit/22d2782f3862dbc121c066367102e195ad354412))

## [1.3.0](https://github.com/centuryglass/IntraPaint/compare/v1.2.0...v1.3.0) (2026-10-09)


### Highlights

* **IntraPaint Ink**, a new dark theme with a bundled font, is the default for new installs. Existing installs keep their saved theme: switch under Edit > Settings > Interface > Theme.
* A rewritten color picker: a foreground/background color pair, an OKHSV wheel, RGB, HSV and OKLCH sliders, and saved and recent colors.
* Generation area overhaul: frames with a resolution rule, context pins, drag and resize handles, Shift + scroll wheel padding, and an area that follows selection edits.
* Copy and paste images through the system clipboard, and rulers beside the image viewer.
* Linux release bundles, built and launch-tested in CI alongside the Windows bundle.
* Dozens of fixes to layers, undo, selection and the editing tools, many found by a much larger test suite.


### Removed

* EPS and PostScript files can no longer be opened or saved. Pillow opens them by running them in Ghostscript, which is a security risk, and they convert poorly. A file with an unsupported extension now gets the normal load error dialog. ([9d87a80](https://github.com/centuryglass/IntraPaint/commit/9d87a80f1cdadff6cc96d41dde700964d7de533d))


### Features

* **build:** build Linux release bundles, and launch-test both the Linux and Windows bundles in CI. PyInstaller is updated, because bundles built with the old version crashed on startup ([8d3eda1](https://github.com/centuryglass/IntraPaint/commit/8d3eda133e1494d0a67853743b3bea958516878c)) ([85da0d6](https://github.com/centuryglass/IntraPaint/commit/85da0d6da68cd95a4f4cda5b0454396aceeea86c))
* **color:** add a background color, swap/reset shortcuts and a color pair widget ([#123](https://github.com/centuryglass/IntraPaint/issues/123)) ([27f0456](https://github.com/centuryglass/IntraPaint/commit/27f0456cb4e4ced73123d34852fe8f8882b0daa3))
* **color:** add an OKHSV ring + square Wheel tab to the color picker ([#157](https://github.com/centuryglass/IntraPaint/issues/157)) ([137ab54](https://github.com/centuryglass/IntraPaint/commit/137ab540d72f74213781a80f5e2870ea9f0360ba))
* **color:** add RGB, HSV and OKLCH gradient sliders to the color picker ([#167](https://github.com/centuryglass/IntraPaint/issues/167)) ([36461c2](https://github.com/centuryglass/IntraPaint/commit/36461c209abcc17fb1681bfb02f15813d8e7c485))
* **color:** add saved colors and a recent colors row to the color picker ([#195](https://github.com/centuryglass/IntraPaint/issues/195)) ([457433c](https://github.com/centuryglass/IntraPaint/commit/457433c3c8e37408bf7de54874a71d1ac014efdc))
* **color:** finish the color picker with a header and size-based layouts ([#197](https://github.com/centuryglass/IntraPaint/issues/197)) ([a123c8e](https://github.com/centuryglass/IntraPaint/commit/a123c8e2ea408eb1cc6df87d76d298e9f213e8e4))
* copy and paste images through the system clipboard ([#241](https://github.com/centuryglass/IntraPaint/issues/241)) ([b0f4de5](https://github.com/centuryglass/IntraPaint/commit/b0f4de5a3b113f56a0e05ada686d946464a3c41d))
* **generation:** add context pins to stretch the inpaint crop ([#106](https://github.com/centuryglass/IntraPaint/issues/106)) ([c4b0f31](https://github.com/centuryglass/IntraPaint/commit/c4b0f31caa66928feea59cf0cc729bc6c905c822))
* **generation:** add generation area frames and a resolution rule ([#88](https://github.com/centuryglass/IntraPaint/issues/88)) ([a777d4f](https://github.com/centuryglass/IntraPaint/commit/a777d4ffd1ffda664e751f58a1bc47fe213690f4))
* **generation:** change inpaint padding with Shift + scroll wheel ([#108](https://github.com/centuryglass/IntraPaint/issues/108)) ([fbb3a68](https://github.com/centuryglass/IntraPaint/commit/fbb3a68e54c3a7a92fdc7a7070f48ac021bb55d5))
* **generation:** drag the generation area by grab point and resize it with handles ([#156](https://github.com/centuryglass/IntraPaint/issues/156)) ([7578c96](https://github.com/centuryglass/IntraPaint/commit/7578c96df072218820f0c119f9965692d1ba9827))
* **generation:** move the generation area to follow selection edits ([#118](https://github.com/centuryglass/IntraPaint/issues/118)) ([6c0a481](https://github.com/centuryglass/IntraPaint/commit/6c0a481c9b84a82adad10dd2c363e514fe8be0bc))
* **layers:** add Layers &gt; Merge group and Layers &gt; Merge all visible, with keybindings ([#70](https://github.com/centuryglass/IntraPaint/issues/70)) ([cc46360](https://github.com/centuryglass/IntraPaint/commit/cc463605ba8a89d84d8988d969daaad8410f1ff3))
* **layers:** keep text layers editable when saving to .ora ([#130](https://github.com/centuryglass/IntraPaint/issues/130)) ([a972206](https://github.com/centuryglass/IntraPaint/commit/a972206345f9a72b0d481571d0634e31869edbdb))
* **ui:** add rulers beside the image viewer ([#131](https://github.com/centuryglass/IntraPaint/issues/131)) ([90c84c5](https://github.com/centuryglass/IntraPaint/commit/90c84c5d7de8086290726c33efb67bf1ac190a65))
* **ui:** add the IntraPaint Ink theme with a bundled font as the default ([#207](https://github.com/centuryglass/IntraPaint/issues/207)) ([9de015a](https://github.com/centuryglass/IntraPaint/commit/9de015aedf7e1d41c59b3e4f26fb9c6ada30c0e5))
* **ui:** draw controls with an IntraPaint Ink QProxyStyle ([#230](https://github.com/centuryglass/IntraPaint/issues/230)) ([f520935](https://github.com/centuryglass/IntraPaint/commit/f520935872fcaa389b07f2e93e34ccaa14a7f818))
* **ui:** draw tool tiles, key hints, side tabs and frames in the Ink look ([#235](https://github.com/centuryglass/IntraPaint/issues/235)) ([4f5de9f](https://github.com/centuryglass/IntraPaint/commit/4f5de9f385bc576a72341344a4f5aba6dd9937a3))
* **ui:** recolor black line icons from the dark palette ([#232](https://github.com/centuryglass/IntraPaint/issues/232)) ([3ae073c](https://github.com/centuryglass/IntraPaint/commit/3ae073ccfb15eafcc450ae4cdc059e3ccc8d995e))
* **ui:** use the Ink signal color for discarding actions and lock alerts ([#246](https://github.com/centuryglass/IntraPaint/issues/246)) ([3776ba3](https://github.com/centuryglass/IntraPaint/commit/3776ba332e4afa7f7fcb4bb6a9eabf802339a70c))


### Bug Fixes

* **brushes:** load the bundled libmypaint first and bundle only the platform's build ([#129](https://github.com/centuryglass/IntraPaint/issues/129)) ([4c2d1c4](https://github.com/centuryglass/IntraPaint/commit/4c2d1c4768bfc85fdd9e37a851c8b587868d9736))
* **build:** build the fill tool's image_fill module under Cython 3.3, which stopped fresh installs from starting ([3ad8949](https://github.com/centuryglass/IntraPaint/commit/3ad89493ffe26294512e8b4083b9ded34adc98d4))
* **build:** include the fill tools in packaged bundles ([#100](https://github.com/centuryglass/IntraPaint/issues/100)) ([7e20d82](https://github.com/centuryglass/IntraPaint/commit/7e20d82e82ef14e52f150b70b58bb3192309dbae))
* **color:** stop File &gt; New overwriting brush color, fix off-canvas color sampling, guard shape tool color sync ([#91](https://github.com/centuryglass/IntraPaint/issues/91)) ([1a07555](https://github.com/centuryglass/IntraPaint/commit/1a0755572119dfd72abd25e0952cbc3bf40f7e08))
* **comfyui:** apply the denoising strength and step count in Stable Diffusion upscaling ([#104](https://github.com/centuryglass/IntraPaint/issues/104)) ([a72609a](https://github.com/centuryglass/IntraPaint/commit/a72609a903fa4d4f8089bb27f0cfbd724106c867))
* **comfyui:** avoid crashing on unexpected fields in ComfyUI image references ([#257](https://github.com/centuryglass/IntraPaint/issues/257)) ([77b4990](https://github.com/centuryglass/IntraPaint/commit/77b49903f30666d1f8d4c9ce2c8e03041d565c9f))
* **config:** fix a race when creating the data and log directories ([#194](https://github.com/centuryglass/IntraPaint/issues/194)) ([24bb407](https://github.com/centuryglass/IntraPaint/commit/24bb40720d6bc54c281349539e14f1b53012e87c))
* **config:** stop Config.set deadlocking when a worker thread saves ([#95](https://github.com/centuryglass/IntraPaint/issues/95)) ([706add1](https://github.com/centuryglass/IntraPaint/commit/706add1f4f9bac37f81137be02a8bc8c3af2abcd))
* **config:** write config JSON atomically so crashes can't wipe settings ([#75](https://github.com/centuryglass/IntraPaint/issues/75)) ([e054e65](https://github.com/centuryglass/IntraPaint/commit/e054e6506c69ebeba7c109155c326511dcddf6f4)), closes [#30](https://github.com/centuryglass/IntraPaint/issues/30)
* **filters:** keep RGBA color balance output validly premultiplied ([#202](https://github.com/centuryglass/IntraPaint/issues/202)) ([2f16df4](https://github.com/centuryglass/IntraPaint/commit/2f16df4bcbd722089993a28c8a41ff5bb461516e)), closes [#160](https://github.com/centuryglass/IntraPaint/issues/160)
* fix crashes and memory corruption caused by image pixel views outliving their image ([a4e89cd](https://github.com/centuryglass/IntraPaint/commit/a4e89cd084733e5d612ea16ff91b3f63b3c106ad))
* **formats:** stop offering formats that can never load or save, and fix JPEG 2000 saves ([#198](https://github.com/centuryglass/IntraPaint/issues/198)) ([aaf8068](https://github.com/centuryglass/IntraPaint/commit/aaf806865e451765359398017f408c8873efb355))
* **generation:** keep the selection inside the generation area when applying a frame ([#243](https://github.com/centuryglass/IntraPaint/issues/243)) ([2edf40a](https://github.com/centuryglass/IntraPaint/commit/2edf40ace71062eb03d81afed1aaba0c7e44c079))
* **layers:** fix layer panel layout glitches with nested groups ([#201](https://github.com/centuryglass/IntraPaint/issues/201)) ([0fcb99f](https://github.com/centuryglass/IntraPaint/commit/0fcb99f12ec337f2e53139ab8e35e15f42f78369))
* **layers:** keep a copied layer's opacity and composite mode when pasting ([#214](https://github.com/centuryglass/IntraPaint/issues/214)) ([01e99c1](https://github.com/centuryglass/IntraPaint/commit/01e99c1832d233056e1cd6b270dc9d9b48975fb2))
* **layers:** keep the composite when flattening over translucent content ([#244](https://github.com/centuryglass/IntraPaint/issues/244)) ([fa6e8b5](https://github.com/centuryglass/IntraPaint/commit/fa6e8b5fa2a4103251d1370a7121a62955b04895))
* **layers:** make Layer to image size work on groups and text layers without a locked-layer error, keep a rotated layer's pixels when cropping or resizing it, keep a hidden layer's content when flattening it, and make cutting from a text layer one undo step ([#238](https://github.com/centuryglass/IntraPaint/issues/238)) ([413812f](https://github.com/centuryglass/IntraPaint/commit/413812f850b0b362d1db922e06ac9e56bbee0c51))
* **layers:** place a duplicated layer directly above the original, keep a duplicated group's isolation and visibility, and make duplicating a group, creating a transformed layer and pasting one undo step each ([#214](https://github.com/centuryglass/IntraPaint/issues/214)) ([01e99c1](https://github.com/centuryglass/IntraPaint/commit/01e99c1832d233056e1cd6b270dc9d9b48975fb2))
* **layers:** refresh a group's cached image when its own opacity or mode changes ([#179](https://github.com/centuryglass/IntraPaint/issues/179)) ([a013307](https://github.com/centuryglass/IntraPaint/commit/a013307bcc826e9aaee5c4ac865f3431f6a62a56)), closes [#166](https://github.com/centuryglass/IntraPaint/issues/166)
* **layers:** report the old area when a layer moves, shrinks or is smoothly sampled ([#220](https://github.com/centuryglass/IntraPaint/issues/220)) ([c708024](https://github.com/centuryglass/IntraPaint/commit/c7080240ca1b52c0d0760da492d34ad36b3e4f8d))
* **layers:** restore layer order when undoing a canvas crop that deleted layers ([#214](https://github.com/centuryglass/IntraPaint/issues/214)) ([01e99c1](https://github.com/centuryglass/IntraPaint/commit/01e99c1832d233056e1cd6b270dc9d9b48975fb2))
* **layers:** show a hidden layer group's content in its layer panel preview ([#222](https://github.com/centuryglass/IntraPaint/issues/222)) ([8599c01](https://github.com/centuryglass/IntraPaint/commit/8599c0116fbd277e66ecf3a09cf8e9f4ae8d91a9)), closes [#208](https://github.com/centuryglass/IntraPaint/issues/208)
* **layers:** stop menu flips moving the layer two pixels, and rotate flipped layers the right way ([#180](https://github.com/centuryglass/IntraPaint/issues/180)) ([6a00c8e](https://github.com/centuryglass/IntraPaint/commit/6a00c8e011106cc87f68d28edf6d76fa79957df4))
* **layers:** stop non-isolated groups compositing the content beneath them over itself ([#228](https://github.com/centuryglass/IntraPaint/issues/228)) ([6424f97](https://github.com/centuryglass/IntraPaint/commit/6424f97e8f2462a8ca1d7676a4e2fc5193fd7fab))
* **layout:** fix tab drop order, tab box stretch drift and divider height limits, and test the layout code ([#219](https://github.com/centuryglass/IntraPaint/issues/219)) ([1d6ea03](https://github.com/centuryglass/IntraPaint/commit/1d6ea03d23119e1cd42bd4896b22ff066558b39e))
* **ora:** keep the active layer when loading an .ora file where a nested group follows it ([#217](https://github.com/centuryglass/IntraPaint/issues/217)) ([911c29c](https://github.com/centuryglass/IntraPaint/commit/911c29ce7ea94d596ebcb3417e8193e4a0a1c1f8))
* **ora:** saving no longer fails on layer names with path separators, and src paths use '/' on Windows ([#94](https://github.com/centuryglass/IntraPaint/issues/94)) ([d08816e](https://github.com/centuryglass/IntraPaint/commit/d08816e1dd7656aa002db7dcad67f97b005b4272))
* pause garbage collection while applying Qt styles and themes ([#196](https://github.com/centuryglass/IntraPaint/issues/196)) ([ef23f6d](https://github.com/centuryglass/IntraPaint/commit/ef23f6d4dfc1f08361879cb9027ae038b3639e47)), closes [#153](https://github.com/centuryglass/IntraPaint/issues/153)
* replace deprecated QColor.isValidColor calls ([#68](https://github.com/centuryglass/IntraPaint/issues/68)) ([017b805](https://github.com/centuryglass/IntraPaint/commit/017b805944da893a4182cf98041f545eb13e03db))
* **selection:** filters apply to every region of a multi-region selection ([#122](https://github.com/centuryglass/IntraPaint/issues/122)) ([d716c82](https://github.com/centuryglass/IntraPaint/commit/d716c825c25d947cbcb544882b0b83491af6cb8e)), closes [#117](https://github.com/centuryglass/IntraPaint/issues/117)
* **selection:** join outline sections after nearby edits and grow/shrink by the exact radius ([#224](https://github.com/centuryglass/IntraPaint/issues/224)) ([f5bb4d8](https://github.com/centuryglass/IntraPaint/commit/f5bb4d88c1bb37203027dc85e61ad5f737d5def2)), closes [#23](https://github.com/centuryglass/IntraPaint/issues/23) [#209](https://github.com/centuryglass/IntraPaint/issues/209)
* **selection:** keep selection brush strokes one-bit, and pin them with golden tests ([#159](https://github.com/centuryglass/IntraPaint/issues/159)) ([51fe090](https://github.com/centuryglass/IntraPaint/commit/51fe0904db4f60d3ba8671c1a8b63130106d0e35))
* **selection:** make closing a free selection polygon one undo step, and sample the right pixel in selection fill's color mode on a moved layer ([#218](https://github.com/centuryglass/IntraPaint/issues/218)) ([79024b5](https://github.com/centuryglass/IntraPaint/commit/79024b53727556221b04823ea779b65a2dd67738))
* **smudge:** composite strokes in 16 bits per channel to keep color ([#204](https://github.com/centuryglass/IntraPaint/issues/204)) ([216f7bc](https://github.com/centuryglass/IntraPaint/commit/216f7bc11fc1805eccc95751fd51bc2392573fee)), closes [#110](https://github.com/centuryglass/IntraPaint/issues/110)
* start without the fill tools when the image_fill build is missing ([#96](https://github.com/centuryglass/IntraPaint/issues/96)) ([7b794e7](https://github.com/centuryglass/IntraPaint/commit/7b794e73ca1d43732f79df256bba86d3623cb39b))
* **testing:** keep test runs out of the real user data and log dirs ([#200](https://github.com/centuryglass/IntraPaint/issues/200)) ([29588b9](https://github.com/centuryglass/IntraPaint/commit/29588b960b429920b44ed603d8f31e4ad1959d15))
* **text:** update the text tool panel and outline when undoing or redoing a text edit, and accept a height equal to the layer's width ([#221](https://github.com/centuryglass/IntraPaint/issues/221)) ([aa6b76b](https://github.com/centuryglass/IntraPaint/commit/aa6b76b57af2a1e41c9cc6c95acadf157f8e253f))
* **tools:** deliver each canvas mouse event to the tool once, and add transform tool tests ([#87](https://github.com/centuryglass/IntraPaint/issues/87)) ([9a05cb2](https://github.com/centuryglass/IntraPaint/commit/9a05cb2b08630c833b6b2e69ae41c27d8e45c1e8)), closes [#76](https://github.com/centuryglass/IntraPaint/issues/76)
* **tools:** keep a modifier key's delegated tool active when other modifiers change ([#213](https://github.com/centuryglass/IntraPaint/issues/213)) ([6bcdc45](https://github.com/centuryglass/IntraPaint/commit/6bcdc454049bd1e27870789814a55735998a7ddd))
* **tools:** make rotate drags follow the cursor and keep the origin on resize ([#120](https://github.com/centuryglass/IntraPaint/issues/120)) ([05103f5](https://github.com/centuryglass/IntraPaint/commit/05103f52757d06be395c7defa51383af7d4d2c0f))
* **tools:** scale and rotate layers about the transformation origin ([#89](https://github.com/centuryglass/IntraPaint/issues/89)) ([5a8c93a](https://github.com/centuryglass/IntraPaint/commit/5a8c93abe332de4a427af7c1e05a6ce44b906a72))
* **tools:** show the same X/Y in the text and transform tools ([#223](https://github.com/centuryglass/IntraPaint/issues/223)) ([cc23163](https://github.com/centuryglass/IntraPaint/commit/cc231633ff7b81b6c042664161c79991057cac84))
* **ui:** ask before closing the main window ([#92](https://github.com/centuryglass/IntraPaint/issues/92)) ([7254763](https://github.com/centuryglass/IntraPaint/commit/72547632fcac6434da11bd04cee1e0828731d8b7))
* **ui:** draw key hint symbols with bundled fallback fonts, so they look the same on every machine ([#227](https://github.com/centuryglass/IntraPaint/issues/227)) ([5d942fe](https://github.com/centuryglass/IntraPaint/commit/5d942fe8a77859632d182e10f86fef8d135487e8))
* **ui:** make the Select Color dialog title translatable ([09ba4c6](https://github.com/centuryglass/IntraPaint/commit/09ba4c627669ada9713ae5f63064637c7d35b1e9))
* **ui:** show MyPaint brushes in scrolling icon lists sized to the panel ([#240](https://github.com/centuryglass/IntraPaint/issues/240)) ([f64f1bc](https://github.com/centuryglass/IntraPaint/commit/f64f1bc33ea9e71765b1db4c8edb6426e5b1e889))
* **ui:** size the layer, layer transform, color and toggle controls to fit their contents ([#239](https://github.com/centuryglass/IntraPaint/issues/239)) ([cea6701](https://github.com/centuryglass/IntraPaint/commit/cea67016943f2436382dd9ecfb1ac529594ee0ac))
* **ui:** stop clipping dock tab bars, key hints, selection buttons and the text preview ([#242](https://github.com/centuryglass/IntraPaint/issues/242)) ([49830fc](https://github.com/centuryglass/IntraPaint/commit/49830fc952a8db8db45b63b9c91d58e805de8011))
* **undo:** keep recording undo history after an error inside a grouped action, keep alpha lock working after Undo with nothing to undo, make Image &gt; Scale image one undo step on large images, and apply the "Maximum undo count" setting ([b6a87cf](https://github.com/centuryglass/IntraPaint/commit/b6a87cfed365efee38b5772a98bb1c1646bbdfa8))
* use os.makedirs(exist_ok=True) to fix TOCTOU race in _adjust_defaults ([#97](https://github.com/centuryglass/IntraPaint/issues/97)) ([e573298](https://github.com/centuryglass/IntraPaint/commit/e573298abc208f9d0d03c3241e2b3f4cd0de9bd1))
* **util:** fix text sizing, alignment and parameter bugs found by new helper tests ([#181](https://github.com/centuryglass/IntraPaint/issues/181)) ([3042002](https://github.com/centuryglass/IntraPaint/commit/3042002f171fab68f5c08a1f32f7e54a4b9c7ddf))
* **view:** show the root layer group's opacity and mode once ([#205](https://github.com/centuryglass/IntraPaint/issues/205)) ([ac2174c](https://github.com/centuryglass/IntraPaint/commit/ac2174c38a25e3cd50176f50ab2fc1f8f40f7f8d)), closes [#150](https://github.com/centuryglass/IntraPaint/issues/150)
* **view:** stop using the deprecated QMouseEvent.pos() when panning ([#225](https://github.com/centuryglass/IntraPaint/issues/225)) ([c6c3e1b](https://github.com/centuryglass/IntraPaint/commit/c6c3e1b505468696364ee7f87202c20e81acf482))
* **webui:** send the opaque single-channel mask the ControlNet extension needs when inpainting ([f6340b7](https://github.com/centuryglass/IntraPaint/commit/f6340b74a763d4d2be80f69a49abaa15c2345e06))
* **webui:** send the tile ControlNet unit's end step as its end step, not its start step, in Stable Diffusion upscaling ([#104](https://github.com/centuryglass/IntraPaint/issues/104)) ([a72609a](https://github.com/centuryglass/IntraPaint/commit/a72609a903fa4d4f8089bb27f0cfbd724106c867))


### Performance Improvements

* **brush:** pin draw tool output with golden tests and make strokes about twice as fast ([#121](https://github.com/centuryglass/IntraPaint/issues/121)) ([656ad8e](https://github.com/centuryglass/IntraPaint/commit/656ad8e221fe5556961f8afaab97f5ab1e05018b))
* **brush:** pin MyPaint brush output with golden tests, fix alpha lock and mid-stroke rounding, cut tile callback overhead ([#143](https://github.com/centuryglass/IntraPaint/issues/143)) ([379def6](https://github.com/centuryglass/IntraPaint/commit/379def610d0acaa513f0193056f04d6f54336562))
* **smudge:** make long smudge strokes up to 30x faster and keep the window responsive ([#109](https://github.com/centuryglass/IntraPaint/issues/109)) ([32324a2](https://github.com/centuryglass/IntraPaint/commit/32324a2b97e9df85b54b404861c36b8c707b512f))


### Notes for people running from source

* Dependencies are pinned to exact versions. Packages the app never imported are removed from `requirements.txt`: scipy, regex, more-itertools, packaging, ipywidgets, protobuf and ipython. ([8137bc0](https://github.com/centuryglass/IntraPaint/commit/8137bc0e9647ba3c0353321cdf51010e9f4ba011))
* `pydantic` and `sd-backend-client` are new runtime requirements. ([#247](https://github.com/centuryglass/IntraPaint/issues/247)) ([a6ed3f9](https://github.com/centuryglass/IntraPaint/commit/a6ed3f9227b8f992915e3e98af52d5de329d0432))

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
