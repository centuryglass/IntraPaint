<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="zh_CN" sourcelanguage="en_US">
<context>
    <name>config.a1111_config</name>
    <message>
        <location filename="../../src/config/a1111_config.py"/>
        <source>key "{key}" had unexpected type {value_type}, value {value}</source>
        <translation>配置项“{key}”的类型 {value_type} 不符合预期，值为 {value}</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>Stable Diffusion model:</source>
        <translation>Stable Diffusion 模型：</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>Active image generation model</source>
        <translation>当前使用的图像生成模型</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>Stable Diffusion</source>
        <translation>Stable Diffusion</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>Stable Diffusion WebUI image generator</source>
        <translation>Stable Diffusion WebUI 图像生成器</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>Only keep one model on GPU/TPU</source>
        <translation>仅在 GPU/TPU 上保留一个模型</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>If selected, checkpoints after the first are cached in RAM instead</source>
        <translation>选中后，第一个之后的模型改为缓存在内存（RAM）中</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>Max checkpoints loaded:</source>
        <translation>最多加载的模型数：</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>Number of image generation models to keep in memory.</source>
        <translation>在内存中保留的图像生成模型数量。</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>Stable Diffusion VAE model:</source>
        <translation>Stable Diffusion VAE 模型：</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>VAE model used for final image data creation.</source>
        <translation>用于生成最终图像数据的 VAE 模型。</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>Stable Diffusion VAE models cached:</source>
        <translation>缓存的 Stable Diffusion VAE 模型数：</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>Number of VAE models to keep in memory.</source>
        <translation>在内存中保留的 VAE 模型数量。</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>CLIP skip:</source>
        <translation>CLIP 跳过层：</translation>
    </message>
    <message>
        <location filename="../config/a1111_setting_definitions.json"/>
        <source>How many of the text encoder's final layers to skip when reading the prompt.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>config.application_config</name>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <location filename="../../src/controller/image_generation/sd_generator.py"/>
        <location filename="../config/application_config_definitions.json"/>
        <source>Stable Diffusion</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <location filename="../../src/controller/image_generation/glid3_webservice_generator.py"/>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <location filename="../config/application_config_definitions.json"/>
        <source>GLID-3-XL</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <location filename="../config/application_config_definitions.json"/>
        <source>Developer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <location filename="../config/application_config_definitions.json"/>
        <source>Files</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Language:</source>
        <translation>语言：</translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Language of the user interface (requires restart). "System language" uses the system's language when IntraPaint has a translation for it, and English otherwise. Languages marked machine-translated were translated by AI models, not people: report wrong or confusing wording at https://github.com/centuryglass/IntraPaint/issues.</source>
        <translation>用户界面的语言（需要重启）。“系统语言”在 IntraPaint 有对应翻译时使用系统的语言，否则使用英语。标为“机器翻译”的语言由 AI 模型翻译，而非人工翻译：如发现错误或难以理解的措辞，请在 https://github.com/centuryglass/IntraPaint/issues 报告。</translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>System language</source>
        <translation>系统语言</translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Interface</source>
        <translation>界面</translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Appearance</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Style:</source>
        <translation>样式：</translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Qt style to use for the user interface</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Fusion</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Theme:</source>
        <translation>主题：</translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Theme to use for the user interface (may require restart)</source>
        <translation>用户界面使用的主题（可能需要重启）</translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>intrapaint_ink</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>None</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Overlay scroll bars:</source>
        <translation>叠加式滚动条：</translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>With the IntraPaint Ink theme, draw thin scroll bars over the content they scroll, instead of beside it.</source>
        <translation>使用 IntraPaint Ink 主题时，将细滚动条绘制在所滚动的内容上方，而不是旁边。</translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Rounded menus and tooltips:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>With the IntraPaint Ink theme, draw menus and tooltips with rounded corners and a shadow. This needs a compositing window manager: turn it off if they show black corners on X11 (may require restart).</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Font size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Font point size to use for user interface text (may require restart)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Tab font size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Font point size to use for panel rail labels (may require restart)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Key hint font size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Font point size to use for key hint labels.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Per-tool brush crosshairs:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Give each variable-size brush tool its own crosshair shape, so the active tool can be told apart at the pointer. Turn this off to use the same crosshair for all of them.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Maximum recent tool icons:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Most recent-tool buttons to show in the panel rail. Fewer show when the window is too short for them.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Layout</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show active tool control hints:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show control hints for the active tool below the image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show rulers:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show rulers with image pixel coordinates above and to the left of the image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Highlight generation area and selection on rulers:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Mark the generation area and the selection's bounds with bars along the rulers.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Ruler generation area color:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Color of the generation area's bar on the rulers. Leave empty to use the theme's accent color. The selection's bar uses the selection overlay color. Both are drawn opaque, lightened or darkened as needed to stand out against the ruler.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Ruler font size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Font point size for ruler labels. The rulers' thickness scales with it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Animate selected content outlines</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Enable or disable animated selection outlines</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Animate area outlines and preview lines</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Enable or disable animation on the generation area outline, selected content area outline, and line previews.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Use a static loading indicator:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show a still frame for the whole load instead of an animated loading indicator.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show selected content overlay:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Fill selected image areas with the selection overlay. When off, only the selection outline is drawn, which stays animated if outline animation is on.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Animate selected content overlay:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Enable or disable selection overlay animation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Selection overlay color:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Overlay color used to highlight selected image areas</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show selections in generated image options:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Draw the selection borders when choosing inpainted image options.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show generated images zoomed to changes:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>When zooming in on individual inpainting options, focus the change region.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show generated image options at original size</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Preview AI-generated image options at their original size, instead of the size they would be scaled to if inserted into the generation area..</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>OpenGL acceleration:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Use OpenGL to accelerate image rendering.  Currently somewhat buggy, breaks several layer rendering modes.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Default image size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Default size when creating new images</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Editing</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Size</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Maximum image size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Maximum size to allow when creating or resizing images</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Maximum generation area size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Maximum size in pixels of the generation area</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Minimum generation area size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Minimum size in pixels of the generation area</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Maximum generation resolution:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>The largest generation resolution, in pixels, that the "Match area, upscale small areas" rule scales a small generation area up to. Areas larger than this keep their own size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Minimum generation resolution:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Minimum size in pixels allowed for AI image generation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Minimum upscaled resolution side:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>With the 'Match area, upscale small areas' resolution rule, generation areas with a shorter side below this size are scaled up by a whole-number factor until the shorter side reaches it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Generation area follows selection:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>In inpainting mode, how the generation area moves after the selection or context pins change. 'Minimal move' moves it only as far as needed to contain the selection, its context pins and inpaint context. 'Center on selection' centers it on them. 'Off' leaves it in place. The area is never resized, and undo and redo never move it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Minimal move</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Center on selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Off</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Label the generation area under the Manual resolution rule</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>While the resolution rule is 'Manual', show the generation resolution in a label on the generation area's top edge. The rule is saved between sessions, so the label keeps a resolution that no longer follows the generation area in view.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Favorite MyPaint brushes:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Brushes to list in the 'Favorites' tab of the brush selection window</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Maximum undo count:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Number of actions that can be reversed using the 'undo' option. Changes apply after restarting IntraPaint.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Saved colors:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Colors saved in the color picker's Palettes tab, at most 64.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Upscale mode:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Upscaling mode used when the inpainting resolution doesn't match the generation area size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Downscale mode:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Downscaling mode used when the inpainting resolution doesn't match the generation area size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Pen tablet pressure curve:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Controls how pen tablet pressure values are applied. The x-axis represents the pressure value reported by the drawing tablet, and the y-axis represents the actual pressure value IntraPaint will register when it receives that value.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Drawing tablet settings</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Describe model (WebUI only):</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Model used when auto-generating appropriate prompts using the Describe action. Supported values will vary based on what extensions you've installed into the Stable Diffusion WebUI, but 'clip' should always be accepted.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Blend inpainting past the selection:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Let the soft edge of inpainted content extend past the selection edge, by the reach of the mask blur. When off, inpainting never changes pixels outside the selection.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Mask blur:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>How much to blur the inpainting mask, in pixels at the generation resolution, so generated content blends smoothly into the original image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Clear context pins after generating</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Remove all context pins when a generated image is applied to the image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>GLID-3-XL model path:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Path to the main GLID-3-XL model file</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Models</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>BERT model path:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Path to the BERT language model file</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>GLID-3-XL VAE model path:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Path to the VAE latent image encoding/decoding model file</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>CLIP model name:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Name of the CLIP language model to use.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Enable global error handler:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Attempt to catch and report global application errors instead of crashing. Disabling this makes it easier to debug certain errors.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn about keybinding issues:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show an alert when keybinding issues are found on startup.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Alerts</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when saving without layers:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show a warning popup when saving a multi-layer image in a format that discards layer data.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when saving without transparency:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show a warning popup when saving an image with transparency in a format that doesn't support it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when saving without metadata:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show a warning popup when saving an image in a format that discards metadata.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when saving drops EXIF, XMP, IPTC or comments:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show a warning popup, listing what would be lost, when saving an image in a format that can't keep all of its metadata.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when saving in a format that cannot be loaded:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show a warning popup when saving an image in a format that can't be loaded.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when saving in a format that changes image size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show a warning popup when saving an image in a format requires a specific resolution.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when saving in a format that removes color:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show a warning popup when saving an image in a format that does not support color.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when loading libmypaint fails:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Show a warning popup when the brush tool cannot be used because of missing libraries.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Always save metadata:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Always save metadata when no previous metadata exists(confirm), never do that(cancel), or ask every time(always_ask).</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>confirm</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>cancel</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>always_ask</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Always update metadata:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Always update metadata when images are saved(confirm), never do that(cancel), or ask every time(always_ask).</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when cropping deletes layers:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when cropping the image or a layer group deletes one or more layers.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when layer lock or visibility forces new layer creation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Warn when image generation creates a new layer because it cannot insert into the active layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Added font directory:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Directory to search for additional font files to load</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Added MyPaint brush directory:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Directory to search for additional MyPaint brush files to load</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>libmypaint library directory:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Directory to search for libmypaint library files if unable to load default libraries</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Autosave a recovery copy:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Periodically save a copy of the open image, and offer to restore it if IntraPaint closes without quitting normally. The copy is deleted when you quit, save, or open another image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Autosave after idle seconds:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Seconds without changes before the recovery copy is updated.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Autosave at least every N seconds:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/application_config_definitions.json"/>
        <source>Longest time between recovery copy updates while you keep editing without a pause. Updates still wait for the current brush stroke or image generation to finish.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>config.cache</name>
    <message>
        <location filename="../../src/config/cache.py"/>
        <source>None</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Generation area size:</source>
        <translation>生成区域大小：</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Current size in pixels of the generation area</source>
        <translation>生成区域的当前大小（像素）</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Cache</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Generation resolution:</source>
        <translation>生成分辨率：</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Current/initial generation resolution: the size in pixels the AI image generator works at</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Resolution rule:</source>
        <translation>分辨率规则：</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>How the generation resolution follows generation area size changes. 'Match area' sets the resolution to the area size. 'Match area, upscale small areas' also scales small areas up by a whole-number factor until the shorter side reaches the minimum set in settings. 'Manual' leaves the resolution alone. Editing the resolution by hand selects 'Manual'.</source>
        <translatorcomment>glossary: not "Scale" - "scales small areas up" means enlarging them, which the glossary renders as Upscale (放大).</translatorcomment>
        <translation>生成分辨率如何随生成区域大小的变化而变化。“匹配区域”将分辨率设为区域大小。“匹配区域并放大小区域”还会把较小的区域按整数倍放大，直到较短边达到设置中的最小值。“手动”保持分辨率不变。手动修改分辨率会选中“手动”。</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Match area</source>
        <translation>匹配区域</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Match area, upscale small areas</source>
        <translation>匹配区域并放大小区域</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Manual</source>
        <translation>手动</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Foreground color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Foreground color, used to paint with the brush, draw, fill and text tools. The key keeps its older name so existing cache files still load.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Background color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Background color, swapped with the foreground color by the swap colors shortcut.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Color slider mode:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Color model the color picker's sliders edit.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>RGB</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>HSV</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>OKLCH</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Color panel tab:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Tab the Color panel shows while it is too small for its sections.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>wheel</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>sliders</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>saved</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>New image background color:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Last new image background color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>New image uses the background color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Whether new images are filled with the current background color instead of the last new image background color.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Text background color:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Last background color (text tool)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Text Tool</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Color threshold:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Sets how closely colors need to match the clicked color to be selected. 0.0 only changes exact matching colors, higher values are more permissive.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Pattern:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Fill tool Qt brush style to apply</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Fill Tool</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Sample merged</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>If checked, fill based on the entire image contents, not just the current layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Fill area</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Which area the magic wand selects: 'Connected' selects the connected region matching the clicked color, 'By color' selects every pixel within the color threshold of the clicked color, and 'Holes' selects the enclosed gaps in the current selection.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Connected</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>By color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Holes</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Paint selection only</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>If checked, only paint within the selection bounds</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Current/initial brush size (in pixels) for the MyPaint brush tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Paint Tool</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Selection mode:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>How new selection shapes combine with the existing selection: 'Add' adds to it, 'Subtract' removes from it, 'Replace' discards it, and 'Intersect' keeps only the overlap. The selection add and subtract modifiers override this for one gesture.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Add</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Subtract</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Replace</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Intersect</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Fixed 1:1 aspect ratio</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>If checked, rectangle and ellipse selections are always square or circular, as if the fixed aspect ratio modifier were held.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Current/initial brush size (in pixels) for the selection tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Brush Selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Current/initial brush size (in pixels) for the draw tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Draw Tool</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Opacity:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Draw tool color opacity</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Hardness:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Draw tool brush hardness</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Pen pressure=size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects draw tool brush size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Pen pressure=opacity:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects draw tool brush opacity.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Pen pressure=hardness:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects draw tool brush hardness.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Draw tool Qt brush style to apply</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Antialiasing</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Smooth out jagged edges.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Eraser size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Current/initial brush size (in pixels) for the eraser tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Eraser Tool</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Filter:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Selected image filter</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Filter Tool</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Filter parameters:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Cached parameters for all filters</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Current/initial brush size (in pixels) for the filter tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Filter tool color opacity</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Filter tool brush hardness</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects filter tool brush size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects filter tool brush opacity.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects filter tool brush hardness.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Current/initial brush size (in pixels) for the smudge tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Smudge Tool</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Smudge tool color opacity</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Smudge tool brush hardness</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects smudge tool brush size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects smudge tool brush opacity.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects smudge tool brush hardness.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Current/initial brush size (in pixels) for the clone stamp tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Clone Stamp Tool</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Clone stamp tool color opacity</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Clone stamp tool brush hardness</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects clone stamp tool brush size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects clone stamp tool brush opacity.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Drawing tablet pen pressure affects clone stamp tool brush hardness.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Source mode:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Control if and when the source point tracks cursor movement.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Fixed offset</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Dynamic offset</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Fixed position</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Shape type:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Type of shape to draw.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Shape Tool</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Vertex count:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Polygon vertex count.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Inner radius fraction:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Distance from the center to inner star points, as a fraction of the distance to the outer points</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Line color source:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Where the shape outline color comes from: the foreground color, or the custom line color.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>From foreground</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Custom color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Custom line color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Shape outline color when the line color source is custom.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Line style:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Shape outline drawing style.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Line join style:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Shape outline connection drawing style.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Dash pattern:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Dash length followed by space length, for any number of dash/space pairs.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Line width:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Shape tool line width.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Shape fill pattern</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Fill color source:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Where the shape fill color comes from: the background color, the foreground color, or the custom fill color.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>From background</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Custom fill color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Shape fill color when the fill color source is custom.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Saved main window geometry</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>JSON with the main window's normal bounds, window state and display when it last closed.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Window placement</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Saved panel layout</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Base64 QMainWindow.saveState data with the panel docks' placement when the window last closed.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Named panel layouts</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Panel layouts the user saved by name, each holding the dock arrangement only: base64 QMainWindow.saveState data under 'state'.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Layer thumbnail size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Size of the previews in the layer panel's rows. 'Auto' uses large previews when the panel has room for them.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Auto</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Small</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Medium</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Large</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Prompt:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Description that generated images should match.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Image generation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Negative prompt:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Description that generated images should not match.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>CFG scale:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Controls how strongly the prompt and negative prompt are applied, through classifier-free guidance (CFG).</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Batch size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Number of image options to simultaneously create in a single image editing operation.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Batch count:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Number of image batches to create in a single image editing operation. Increasing this value doesn't require additional memory, but it slows down image editing more than increasing the batch size does.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Edit mode:</source>
        <translation>编辑模式：</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Stable Diffusion image editing mode. 'Text to Image' completely replaces the selected image section with new content, 'Image to Image' creates altered versions of the image selection, and 'Inpaint' works like 'Image to Image' except that it only changes the selected parts of the generation area</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Inpaint</source>
        <translation>局部重绘</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Image to Image</source>
        <translation>图生图</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Text to Image</source>
        <translation>文生图</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Masked content:</source>
        <translation>蒙版内容：</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Determines what should be used to fill the masked area before inpainting. 'fill' replaces it with a solid color, 'original' keeps it as-is, 'latent noise' replaces it with random data, and 'latent nothing' clears it. Unless you're inpainting with a denoising strength &gt;0.8, 'original' will almost always be the best option</source>
        <translation>决定局部重绘前用什么填充蒙版区域。“填充”用纯色替换，“原图”保持原样，“潜空间噪声”用随机数据替换，“空白潜空间”将其清空。除非以大于 0.8 的重绘幅度进行局部重绘，否则“原图”几乎总是最佳选项</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>fill</source>
        <translation>填充</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>original</source>
        <translation>原图</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>latent noise</source>
        <translation>潜空间噪声</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>latent nothing</source>
        <translation>空白潜空间</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Steps:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Number of diffusion operations to perform when generating image data. Higher values take longer, but often produce more detailed and accurate results. Different Stable Diffusion models and samplers have different requirements, but in most cases setting this higher than 30 has only minimal benefits</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Denoising strength:</source>
        <translation>重绘幅度：</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Controls how dramatically inpainting and image-to-image operations will change the initial image data. At 0.0, the image will be completely unedited, at 1.0 the image will be completely different</source>
        <translation>控制局部重绘和图生图操作对初始图像数据的改变程度。为 0.0 时图像完全不变，为 1.0 时图像完全不同</translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Sampling method:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Mathematical technique used to transform image data during the generation process. 'Euler a' works well in most cases, but certain models or extensions might perform better with other options.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Scheduler:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Algorithm used to divide  the image generation process into steps.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>default</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Layer expand mode:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Sets which layers should be expanded to fill the image when resized</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Expand all unlocked layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Only expand full-image layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Do not expand layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Resize image canvas</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Crop layers to new image bounds</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Sets whether layers should be cropped to image bounds when the image is resized.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Width:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Width in pixels of the line Edit &gt; Stroke selection draws.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Stroke selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Position:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Whether Edit &gt; Stroke selection draws its line inside, centered on, or outside the selection edge.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>inside</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>center</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>outside</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Save as an animation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Saves each top-level layer as one frame of the animation. When unchecked, the image is saved flattened.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Save animation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Default frame duration (ms):</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Display time in milliseconds for frames whose layer names have no duration tag like "(120ms)".</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Loop forever</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Repeats the animation until it is stopped.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Loop count:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Number of times the animation repeats when it doesn't loop forever.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Seed:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Number used to control pseudo-random aspects of image generation, in most cases using the same seed with the same settings and inputs will always produce the same results. If set to -1, a different random seed will be used for each image generation. </source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Last seed:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Last seed used for image generation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Limit context to the selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>On: generate only the selection and the context around it, at the full generation resolution, for finer detail. Off: generate the whole generation area.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Context:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>How far past the selection, in pixels, the generator sees while context is limited. Less context gives finer detail, and more gives better awareness of the surrounding image. Context pins stretch it further.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Detail reference count (cutn):</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Determines how many random cutouts from the input image are used to guide image generation (GLID-3-XL). Higher values can introduce more detail and variation, but may also introduce more noise and irrelevant information.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Skip steps:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Number of diffusion steps to skip (GLID-3-XL). Higher values will result in faster image generation with decreased detail and accuracy.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Stable Diffusion model:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Stable Diffusion model to use for image generation.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>CLIP skip:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>How many of the text encoder's final layers to skip when reading the prompt. Usually best left at one, but some models produce better results at two.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Model config:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Configuration file used when loading image generation models.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>auto</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>ComfyUI</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Load checkpoint as inpainting model</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Load the selected Stable Diffusion model as an inpainting model.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Use tiled VAE image encoding</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Encode and decode latent images in tiled blocks, decreasing GPU memory use.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>VAE tile size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Tile size when using tiled VAE encoding/decoding.  Smaller values decrease memory further, but may increase image generation time.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Tiling</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Generate tiling images that can be seamlessly repeated. Inpainting ignores the context limit while tiling is on.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>WebUI</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Restore faces</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Use a face restoration model to correct image data after Stable Diffusion runs. In most cases you'll probably get better results without it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Variation seed:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Controls randomness across images generated in the same batch.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Last variation seed:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Last variation seed used for image generation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Variation strength:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Controls the amount of variation within images in the same batch. Lower values will have less variation. If set to zero, this setting is ignored.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Resize seed from alternate resolution</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>If enabled, reusing the same seed value will produce a similar image even if the resolution changes.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Resize from resolution:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Generated images using the same seed will match images created at this resolution, regardless of generation resolution.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Image scaling behavior:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Controls how multi-layer images are scaled.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Independent layer scaling</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Scale merged, keep source layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Scale merged, discard source layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Stable Diffusion upscaling:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>If selected, Stable Diffusion will be used for upscaling, and settings within the Image Generation panel will affect the upscaling process.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>ControlNet</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Controls how much freedom Stable Diffusion will be given to adjust the image during upscaling.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Stable Diffusion Upscale</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Number of denoising steps to use when upscaling with Stable Diffusion</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Tile ControlNet model list:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>List of ControlNet tile model options for Stable Diffusion upscaling.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Use the "Ultimate SD Upscale" script:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>If selected, the "Ultimate SD Upscale" script will be used for enhanced image upscaling</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Soft inpainting</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Treat the blurred edge of the inpainting mask as a gradual, per-pixel change, so inpainted content blends into its surroundings at high denoising strength. A wider mask blur widens the gradual band.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/cache_value_definitions.json"/>
        <source>Stable Diffusion</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>config.config</name>
    <message>
        <location filename="../../src/config/config.py"/>
        <source>Config definition file not found at {definition_path}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config.py"/>
        <source>Config value definition for {key} had invalid data type {value_type}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config.py"/>
        <source>Loading {key} failed: {err}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config.py"/>
        <source>Reading JSON config definitions failed: {err}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config.py"/>
        <source>Reading JSON config values failed: {err}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config.py"/>
        <source>Tried to access unknown config value "{key}"</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config.py"/>
        <source>Tried to track fixed options for key "{key}", which does not have a fixed list of options.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config.py"/>
        <source>Tried to get key code "{key}", found "{code_string}"</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config.py"/>
        <source>Tried to add duplicate config entry for key "{key}"</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config.py"/>
        <source>{path} was written by a newer version of IntraPaint (config version {version}). Its values will load, but changes won't be saved.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>config.config_entry</name>
    <message>
        <location filename="../../src/config/config_entry.py"/>
        <source>Tried to read {key}.{inner_key} from type {type_name}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config_entry.py"/>
        <source>Config value "{key}" does not have an associated options list</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config_entry.py"/>
        <source>unexpected type:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/config_entry.py"/>
        <source>{key}: missing value</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>config.key_config</name>
    <message>
        <location filename="../../src/config/key_config.py"/>
        <source>Warning</source>
        <translation>警告</translation>
    </message>
    <message>
        <location filename="../../src/config/key_config.py"/>
        <source>Errors found in configurable key bindings:
</source>
        <translation>可配置的快捷键中发现错误：
</translation>
    </message>
    <message>
        <location filename="../../src/config/key_config.py"/>
        <source>"{key_binding_name}" should be a modifier key (Ctrl, Alt, Shift), found "{key_value}"</source>
        <translation>“{key_binding_name}”应为修饰键（Ctrl、Alt、Shift），实际为“{key_value}”</translation>
    </message>
    <message>
        <location filename="../../src/config/key_config.py"/>
        <source>"{key_binding_name}" assigned unexpected modifier key "{key_value}", this may cause problems</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/key_config.py"/>
        <source>"{key_binding_name}" value "{key_value}" is not a recognized key</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/config/key_config.py"/>
        <source>Key "{key_str}" is shared between options {key_names}, some keys may not work.</source>
        <translation>按键“{key_str}”同时分配给了选项 {key_names}，部分按键可能无法使用。</translation>
    </message>
    <message>
        <location filename="../../src/config/key_config.py"/>
        <source>"{key_str}" is also bound to: {key_names}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <location filename="../config/key_config_definitions.json"/>
        <source>Keybindings</source>
        <translation>快捷键</translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Line drawing modifier:</source>
        <translation>直线绘制修饰键：</translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>When held, drawing tools will draw a line from the last point.</source>
        <translation>按住时，绘图工具从上一个点画出直线。</translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Modifiers</source>
        <translation>修饰键</translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Fixed angle modifier:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>When held, drawing tools will be constrained to a fixed angle.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Brush size drag modifier:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Held with the right mouse button, dragging in a brush tool sets the brush size from the drag distance. Escape restores the previous size. On Linux, some desktops (KDE Plasma, Xfce) use Alt+right-drag to resize windows, and the drag never reaches IntraPaint. Either change the desktop's window-resize modifier, or bind this to another modifier.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Pan view key:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>While held, click and drag with the left mouse button to pan the image view. Ignored while a text field has focus.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Navigation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Selection add modifier:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>When held as a selection gesture starts, the gesture adds to the selection whatever the selection mode is. Held together with the subtract modifier, the gesture intersects with the selection.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Selection subtract modifier:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>When held as a selection gesture starts, the gesture subtracts from the selection whatever the selection mode is. On Linux, many window managers (XFCE, Cinnamon, MATE, KDE Plasma 5) use Alt+drag to move windows, and the press never reaches IntraPaint. Either change the window manager's window-move modifier to Super, or bind this to another modifier such as Meta.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Selection replace modifier:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>When held as a selection gesture starts, the gesture replaces the selection whatever the selection mode is. It takes priority over the add and subtract modifiers.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Fixed aspect ratio modifier:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>When held, shape and transform tools will keep a fixed aspect ratio.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Color picker override modifier:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>When held, temporarily switch from the brush or fill tool to the color picker.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Compare With Original Modifier:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>While held in the generated image selector's single view, the original image content shows in place of the focused option.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Context scroll modifier:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>When held, the scroll wheel changes inpaint context over the image or the navigation panel, with any tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Zoom in:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Zoom in on image content</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Zoom out:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Zoom out on image content</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Toggle zoom:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch between close-up and zoomed out views</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Pan left/decrease width:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Scroll the image view left, or decrease layer width in the layer transformation and text tools.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Pan right/increase width:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Scroll the image view right, or increase layer width in the layer transformation and text tools.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Pan up/increase height:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Scroll the image view up, or increase layer height in the layer transformation and text tools.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Pan down/decrease height:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Scroll the image view down, or decrease layer height in the layer transformation and text tools.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move left:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move the generation area left, move active layer left, or view previous generated image option</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move left more:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Same as "Move left", but in steps of 10 pixels.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move right:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move the generation area right, move active layer right, or view next generated image option</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move right more:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Same as "Move right", but in steps of 10 pixels.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move up:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move the generation area up, move active layer up, or zoom in on first generated image option</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move up more:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Same as "Move up", but in steps of 10 pixels.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move down:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move the generation area down, move active layer down, or zoom to show all generated image options</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move down more:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Same as "Move down", but in steps of 10 pixels.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show/hide Layers panel:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show and focus the Layers panel, or hide it if it is showing</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show/hide Navigation panel:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show and focus the Navigation panel, or hide it if it is showing</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show/hide Tools panel:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show and focus the Tools panel, or hide it if it is showing</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show/hide Image Generation panel:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show and focus the Image Generation panel, or hide it if it is showing</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show/hide ControlNet panel:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show and focus the ControlNet panel, or hide it if it is showing</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the draw tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the draw tool to draw into the image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Tool Selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the eraser tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the eraser tool to erase image content.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the filter tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the filter tool to apply image filters to brush strokes.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the smudge tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the smudge tool to smudge image content.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the clone stamp tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the clone stamp tool to copy image content.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the color picker tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the color picker tool to change the brush color.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the layer transformation tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the layer transformation tool to move, scale, or rotate layers.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the selection brush tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the selection brush tool to mark areas for editing.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the magic wand tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the magic wand tool to select areas of similar color.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the shape selection tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the shape selection tool to mark areas for editing.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the free selection tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the free selection tool to mark areas for editing.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the fill tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the fill tool to fill areas with solid colors.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the text tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the text tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the shape drawing tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the shape drawing tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the generation area tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the generation area tool to pick an image area for AI image generation.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Previous generation area size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch the generation area back to the size used before the current one. Pressing it again switches back.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the brush tool:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Activate the brush tool to paint into the image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Decrease brush size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Decrease the size of the active brush</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Tool Shortcuts</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Increase brush size:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Increase the size of the active brush</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Decrease brush opacity:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Decrease the opacity of the active brush</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Increase brush opacity:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Increase the opacity of the active brush</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set brush opacity to 10%:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the opacity of the active brush to 10%.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set brush opacity to 20%:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the opacity of the active brush to 20%.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set brush opacity to 30%:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the opacity of the active brush to 30%.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set brush opacity to 40%:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the opacity of the active brush to 40%.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set brush opacity to 50%:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the opacity of the active brush to 50%.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set brush opacity to 60%:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the opacity of the active brush to 60%.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set brush opacity to 70%:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the opacity of the active brush to 70%.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set brush opacity to 80%:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the opacity of the active brush to 80%.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set brush opacity to 90%:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the opacity of the active brush to 90%.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set brush opacity to 100%:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the opacity of the active brush to 100%.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Decrease brush hardness:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Decrease the hardness of the active brush</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Increase brush hardness:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Increase the hardness of the active brush</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate layer counter-clockwise/text size down:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotates the layer when the layer transformation tool is active, or decrease font size in the text tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate layer clockwise/text size up:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotates the layer when the layer transformation tool is active, or increase font size in the text tool.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Cycle selection mode</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Steps the selection mode through Replace, Add, Subtract and Intersect while a selection tool is active.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Toggle sample merged</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Toggles the Sample merged option while the magic wand tool is active. Unbound by default.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Toggle selection shape</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switches between rectangle and ellipse while the shape selection tool is active. Pressing the shape selection tool's own key again does the same. Unbound by default.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>New...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Open a new image for editing.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Menu Shortcuts</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>File Menu</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Save</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Save current image as .png or .ora.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Save as...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Save current image as .png or .inpt at a new file path.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Open...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Open an image file for editing.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Open as layers...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Open images as new layers.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Revert</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Reload the image from its file.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Quit</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Closes the application.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Undo</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Undo the last action taken</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Edit Menu</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Redo</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Re-apply the last action reversed with undo.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Cut</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Remove selected image content in the active layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Copy</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Copy selected image content in the active layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Copy merged</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Copy selected image content from all visible layers combined.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Paste</source>
        <translation>粘贴</translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Insert copied image data into a new layer.</source>
        <translation>将复制的图像数据粘贴到新图层中。</translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Clear</source>
        <translation>清除</translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Delete selected image content in the active layer.</source>
        <translation>删除当前图层中所选的图像内容。</translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Fill with foreground color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Fill the selected area of the active layer with the foreground color.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Fill with background color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Fill the selected area of the active layer with the background color.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Stroke selection...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Draw a line along the selection outline on the active layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Swap colors</source>
        <translation>交换颜色</translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Swap the foreground and background colors.</source>
        <translation>交换前景色和背景色。</translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Reset colors</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Set the foreground color to black and the background color to white.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Keyboard shortcuts...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Open the settings window at the keybinding settings.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Preferences...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Open the application settings window.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Zoom in</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Zoom in on image content.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>View Menu</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Zoom out</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Zoom out from image content.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Actual size (100%)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show the image at its actual size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Fit image in window</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Fit the whole image in the view and center it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Zoom to generation area</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Center the view on the generation area and zoom to fit it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Tool control hints</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show or hide the active tool control hints below the image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Selection overlay</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show or hide the selection overlay fill. The selection outline stays visible.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Reset panel layout</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Put every panel back where it starts on first run, and open it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Window Menu</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Save current layout...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Save the current panel arrangement under a name, so it can be applied later.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Manage layouts...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Apply, rename or delete saved panel layouts.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rulers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show or hide the rulers beside the image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Full screen</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch the main window between full screen and its previous size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Canvas size...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Change the image size without scaling layers.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Image Menu</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Scale image...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Scale image content to a new size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Flip image horizontally</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Mirror every layer, the selection and the generation area from left to right.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Flip image vertically</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Mirror every layer, the selection and the generation area from top to bottom.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate image 90° CW</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate the whole image 90 degrees clockwise, swapping its width and height.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate image 90° CCW</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate the whole image 90 degrees counter-clockwise, swapping its width and height.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate image 180°</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate the whole image 180 degrees.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Crop to selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Crop the image to fit the current selected area.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Crop to generation area</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Crop the image to fit the generation area.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Fit canvas to layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Resize the image to fit all layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Image metadata...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Update image metadata that will be saved with the file.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Select image generator...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Selects an AI image generator</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Generation Menu</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Generate</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Start AI image generation.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Reopen last generated options</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Reopens the last batch of generated images so another option can be chosen.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Select all</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Select the entire image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Select Menu</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Deselect all</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Clear the selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Invert selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Swap selected and unselected areas</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Select layer content</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Select all non-transparent pixels in the active layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Select all layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Select every layer in the layer panel</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Grow selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Expand the selection bounds</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Shrink selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Shrink the selection bounds</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Clear context pins</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Remove all context pins</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>New layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Create a new layer above the active layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Layer Menu</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>New layer group</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Create a new layer group above the active layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Group selected layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move the selected layers into a new layer group.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Duplicate layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Create a duplicate of each selected layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rename layer...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Edit the active layer's name in the layer panel.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Delete layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Delete the selected layers.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Select previous layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the next layer up.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Select next layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Switch to the next layer down.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Extend layer selection up</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Add the layer above the active layer to the selected layers.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Extend layer selection down</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Add the layer below the active layer to the selected layers.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move layer up</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move the active layer up</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move layer down</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move the active layer down</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move layer to top</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Move the active layer above all others</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Merge layer down</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Merge the active layer with the one below it</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Merge group</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Merge the active layer group into a single image layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Merge visible</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Merge all visible layers into a single image layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Flatten layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Simplify a layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Layer to image size</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Expand or crop the active layer to match the image bounds.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Crop layer to selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Crop the layer to fit the current selected area.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Crop layer to content</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Crop transparent borders in the active layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Mirror layer horizontally</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Flip layer content horizontally</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Mirror layer vertically</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Flip layer content vertically</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate layer 90° CW</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate the active layer 90 degrees clockwise.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate layer 90° CCW</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Rotate the active layer 90 degrees counter-clockwise.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Repeat last filter</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Apply the last filter again with the same settings</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Filters Menu</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>RGBA color balance...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Adjust RGBA color channels</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Brightness/contrast...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Adjust image brightness/contrast</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Blur...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Image blurring</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Sharpen...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Sharpen image details</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Posterize...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Simplify layer color palette</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Saturation...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Adjust image color saturation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Invert...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Invert image colors</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>View saved prompt styles...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Access saved Stable Diffusion prompt styles</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>View LoRA models...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Access available LoRA models.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>LCM mode</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Apply appropriate settings for the LCM LoRA.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Clear GPU memory</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Remove cached models from GPU memory in ComfyUI.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>IntraPaint help</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Open a page with links to all of IntraPaint's documentation and tutorials in a web browser.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Help Menu</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Report a bug</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Open IntraPaint's GitHub issue tracker in a web browser.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Release notes</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Open the list of IntraPaint releases and their changes in a web browser.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>About IntraPaint...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show IntraPaint's version, license and project links.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>About Qt...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../config/key_config_definitions.json"/>
        <source>Show the version and license of the Qt toolkit IntraPaint is built on.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>controller.app_controller</name>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Restart required</source>
        <translation>需要重启</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>The new maximum undo count will apply after IntraPaint is restarted.</source>
        <translation>新的最大撤销次数将在 IntraPaint 重启后生效。</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>&amp;File</source>
        <translation>文件(&amp;F)</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>&amp;Edit</source>
        <translation>编辑(&amp;E)</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>&amp;View</source>
        <translation>视图(&amp;V)</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>&amp;Image</source>
        <translation>图像(&amp;I)</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>&amp;Layer</source>
        <translation>图层(&amp;L)</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>&amp;Select</source>
        <translation>选择(&amp;S)</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Fil&amp;ters</source>
        <translation>滤镜(&amp;T)</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Repeat {filter_name}</source>
        <translation>重复“{filter_name}”</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>&amp;Window</source>
        <translation>窗口(&amp;W)</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>&amp;Help</source>
        <translation>帮助(&amp;H)</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Layout not applied</source>
        <translation>未能应用布局</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>The layout "{layout_name}" could not be restored. It may be corrupt or saved by an older version. Delete it in Manage layouts.</source>
        <translation>无法恢复布局“{layout_name}”。它可能已损坏，或由旧版本保存。请在“管理布局”中将其删除。</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Layouts</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Open recent</source>
        <translation>最近打开</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Clear recent files</source>
        <translation>清空最近文件列表</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Stack</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Transform</source>
        <translation>变换</translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>About IntraPaint</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>&lt;h3&gt;IntraPaint {version}&lt;/h3&gt;&lt;p&gt;An image editor that combines digital painting tools with AI image generation and inpainting.&lt;/p&gt;&lt;p&gt;Free software, released under the &lt;a href="{license_link}"&gt;GNU General Public License v3&lt;/a&gt;.&lt;/p&gt;&lt;p&gt;&lt;a href="{project_link}"&gt;Project page&lt;/a&gt; - &lt;a href="{issues_link}"&gt;Report a bug&lt;/a&gt;&lt;/p&gt;</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Loading image generator failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Unable to load the {generator_name} image generator</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Quit without saving</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/app_controller.py"/>
        <source>Create without saving</source>
        <translation type="unfinished"></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/controller/app_controller.py"/>
        <source>ControlNet: %n of {enabled} enabled unit(s) skipped. Inpainting units only apply in Inpaint mode.</source>
        <comment>Tooltip of the ControlNet rail button</comment>
        <translation><numerusform>ControlNet：已启用的 {enabled} 个控制单元中有 %n 个被跳过。局部重绘控制单元仅在局部重绘模式下生效。</numerusform></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/controller/app_controller.py"/>
        <source>ControlNet: %n unit(s) on</source>
        <comment>Tooltip of the ControlNet rail button</comment>
        <translation><numerusform>ControlNet：已启用 %n 个控制单元</numerusform></translation>
    </message>
    <message>
        <source>ControlNet: 1 unit on</source>
        <comment>Tooltip of the ControlNet rail button</comment>
        <translation type="vanished">ControlNet：已启用 1 个控制单元</translation>
    </message>
    <message>
        <source>ControlNet: {count} units on</source>
        <comment>Tooltip of the ControlNet rail button</comment>
        <translation type="vanished">ControlNet：已启用 {count} 个控制单元</translation>
    </message>
    <message>
        <source>ControlNet: {count} of {enabled} units on are skipped. Inpainting units only apply in Inpaint mode.</source>
        <comment>Tooltip of the ControlNet rail button</comment>
        <translation type="vanished">ControlNet：已启用的 {enabled} 个控制单元中有 {count} 个被跳过。局部重绘控制单元仅在局部重绘模式下生效。</translation>
    </message>
</context>
<context>
    <name>controller.autosave_controller</name>
    <message>
        <location filename="../../src/controller/autosave_controller.py"/>
        <source>Restore failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/autosave_controller.py"/>
        <source>The recovery copy could not be opened: {error}</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>controller.image_generation.glid3_webservice_generator</name>
    <message>
        <location filename="../../src/controller/image_generation/glid3_webservice_generator.py"/>
        <source>GLID-3-XL image generation server</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_webservice_generator.py"/>
        <source>&lt;h2&gt;GLID-3-XL server setup&lt;/h2&gt;</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_webservice_generator.py"/>
        <source>
&lt;h3&gt;GLID-3-XL server setup:&lt;/h3&gt;
&lt;ol&gt;
    &lt;li&gt;
        If you are running the pre-packaged version of IntraPaint, or if you want to manage the GLID-3-XL server
        separately, run the following to get the required code and set up a new anaconda virtual environment:
        {commands}
    &lt;/li&gt;
</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_webservice_generator.py"/>
        <source>
    &lt;li&gt;
        Start the server by running "&lt;code&gt;python IntraPaint_server.py&lt;/code&gt;". If you are using a model other than the
        default inpaint.pt, instead run "&lt;code&gt;python Intrapaint_server.py --model_path models/model.pt&lt;/code&gt;", replacing
        "model.pt" with the file name of whatever model you are using. If the setup was successful, something like
         "* Running on http://192.168.0.XXX:5555" will be printed in the console  after a short delay. You may now click the
         "activate" button below, entering that URL when prompted.
    &lt;/li&gt;
&lt;/ol&gt;
&lt;h4&gt;Former Google Colab approach:&lt;/h4&gt;
&lt;p&gt;
    The original preferred way to use this mode relied on a Google Colab notebook, found 
    &lt;a href="https://github.com/centuryglass/IntraPaint/blob/colab-refactor/colabFiles/IntraPaint_colab_server.ipynb"&gt;
    here&lt;/a&gt;. This approach is discouraged by Google and no longer seems to work using the free tier of Google Colab.
    This approach might still work on the paid tier, or if additional steps are taken to replace 
    the ngrok service formerly used to handle external connections. 
&lt;/p&gt;
</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_webservice_generator.py"/>
        <source>
&lt;h2&gt;Colab server setup&lt;/h2&gt;
&lt;p&gt;
    This is the easier way to set up this mode. It does not require a powerful GPU, but it does require an internet
     connection and a Google account.
&lt;/p&gt;
&lt;ol&gt;
    &lt;li&gt;
        You'll need a free ngrok account to handle the connection between IntraPaint and  the Colab Notebook. Sign up
        for that account at &lt;a&gt;https://ngrok.com&lt;/a&gt;
    &lt;/li&gt;
    &lt;li&gt;
        After you sign up for an ngrok account, log in to their site and find your ngrok AuthToken on 
        &lt;a href="https://dashboard.ngrok.com/get-started/your-authtoken"&gt;this page. Copy it, and save it somewhere safe
        (e.g. a password manager).
    &lt;/li&gt;
    &lt;li&gt;
        Open the &lt;a href="https://colab.research.google.com/github/centuryglass/IntraPaint/blob/colab-refactor
        /colabFiles/IntraPaint_colab_server.ipynb"&gt;IntraPaint Server notebook&lt;/a&gt; in Google Colab.
    &lt;/li&gt;
    &lt;li&gt;
        Click "connect" in the upper right, after making sure that the dropdown to the right of the connect button is
        set to "GPU". If you don't pay for Google Colab there is a chance that a GPU server won't be available, and
        you'll have to try again later.
    &lt;/li&gt;
    &lt;li&gt;
        By default, the server uses Google Drive to save configuration info to simplify the process of starting it
        again later.  If you don't want to do this, scroll down through the notebook, find where it says
        "use_google_drive=True", and change it to "use_google_drive=False"
    &lt;/li&gt;
    &lt;li&gt;
        If you have an extra 10GB of space free in Google Drive, you can scroll down, find the line that says
        "save_missing_models_to_drive=False", and change False to True, and it will start up much more quickly in the
         future.
    &lt;/li&gt;
    &lt;li&gt;
        Under the "Runtime" menu, select "Run All".  You'll see a popup warning you that the notebook is not from
         Google. Click "Run anyway".
    &lt;/li&gt;
    &lt;li&gt;
        If you chose to use Google Drive, another popup will appear asking you to grant permission to access Google
        Drive. Click "Connect to Google Drive", and follow on-screen instructions to allow it to read and write files.
    &lt;/li&gt;'
    &lt;li&gt;
        Below the first section of code on the page, a dialog asking you to enter your ngrok AuthToken will appear.
        Paste in the auth token you saved earlier, and press enter. If you are using Google Drive, you won't need to do
         this again the next time you start the server.
    &lt;/li&gt;
    &lt;li&gt;
        Scroll down, and the server URL you need should be printed at the end of all log entries after a few minutes.
        Click the "activate" button below these instructions, and enter that URL when prompted.
    &lt;/li&gt;'
&lt;/ol&gt;</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_webservice_generator.py"/>
        <source>No GLID-3-XL server address was provided.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_webservice_generator.py"/>
        <source>Could not find a valid GLID-3-XL server at "{server_address}"</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>controller.image_generation.glid3_xl_generator</name>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>GLID-3-XL image generation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>
&lt;h1&gt;GLID-3-XL&lt;/h1&gt;
&lt;p&gt;
    GLID-3-XL was the best inpainting model available until August 2022, and the first model supported by IntraPaint.
    IntraPaint continues to support it for the sake of preserving historically interesting image generation models.
&lt;/p&gt;
&lt;h2&gt;Generator capabilities and limits:&lt;/h2&gt;
&lt;ul&gt;
    &lt;li&gt;Requires approximately 8GB of VRAM.&lt;/li&gt;
    &lt;li&gt;Inpainting is supported at an ideal resolution of 256x256, with limited support for other resolutions.&lt;/li&gt;
    &lt;li&gt;Supports positive and negative prompting with variable guidance strength&lt;/li&gt;
    &lt;li&gt;Capable of generating images in batches, with max batch size dependent on available VRAM.&lt;/li&gt;
    &lt;li&gt;Some stylistic flexibility, but limited ability to understand complex prompts.&lt;/li&gt;
&lt;/ul&gt;
</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>
&lt;h2&gt;GLID-3-XL server setup&lt;/h2&gt;</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>
&lt;h2&gt;GLID-3-XL server setup&lt;/h2&gt;
&lt;p&gt;
     Because GLID-3-XL is mainly a historical curiosity at this point, few steps have been taken to simplify the
    setup process. As the software involved becomes increasingly outdated, further steps may be necessary to get this
    generator to work.
&lt;/p&gt;</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>
&lt;h3&gt;Prerequisites:&lt;/h3&gt;
&lt;p&gt;
    Running GLID-3-XL requires a NVIDIA GPU with at least 8GB of VRAM. Other GPUs or slightly less memory might work,
    but are not tested. You will also need to install the following software:
&lt;/p&gt;
&lt;ul&gt;
    &lt;li&gt;&lt;a href="https://www.python.org/"&gt;Python3&lt;/a&gt;&lt;/li&gt;
    &lt;li&gt;&lt;a href="https://git-scm.com/"&gt;Git&lt;/a&gt;&lt;/li&gt;
    &lt;li&gt;
        &lt;a href="https://developer.nvidia.com/cuda-toolkit"&gt;CUDA&lt;/a&gt; (if using a NVIDIA graphics card)
    &lt;/li&gt;
    &lt;li&gt;&lt;a href="https://www.anaconda.com/download/"&gt;Anaconda&lt;/a&gt;&lt;/li&gt;
&lt;/ul&gt;
&lt;p&gt;
    Depending on your system, you may need to take extra steps to add Python, Git, and Anaconda to your system path, or
    perform other configuration steps. Refer to the sites linked above for full documentation.
&lt;/p&gt;
</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>
&lt;h3&gt;IntraPaint setup via Git:&lt;/h3&gt;
&lt;p&gt;
    You are currently running the pre-packaged version of IntraPaint, which excludes some of the components needed to
    run GLID-3-XL. You will need to switch to the Git version by running the following commands in a terminal window:
&lt;/p&gt;
{commands}
&lt;p&gt;
    When following the instructions below, make sure you run all terminal commands in this new IntraPaint folder with
    the "intrapaint-glid" anaconda environment active.
&lt;/p&gt;
</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>
&lt;h3&gt;Installing dependencies:&lt;/h3&gt;
&lt;ol&gt;
    &lt;li&gt;
        Within the the terminal in the IntraPaint directory, install the appropriate versions of torch and torchvision
        using the commands found &lt;a href="https://pytorch.org/get-started/locally/"&gt;here&lt;/a&gt;.
    &lt;/li&gt;
    &lt;li&gt;
        Run the following commands to install additional dependencies:
        {commands}
    &lt;/li&gt;
    &lt;li&gt;
        Download one or more GLID-3-XL inpainting models, and place them in the "IntraPaint/models/" directory.
        These are the main options available:
        &lt;ul&gt;
            &lt;li&gt;
                &lt;a href="https://dall-3.com/models/glid-3-xl/"&gt;inpaint.pt&lt;/a&gt;: The original GLID-3-XL inpainting model.
            &lt;/li&gt;
            &lt;li&gt;
                &lt;a href="https://huggingface.co/laion/ongo/resolve/main/ongo.pt"&gt;ongo.pt&lt;/a&gt;: Trained by
                LAION on paintings from the Wikiart dataset.
            &lt;/li&gt;
            &lt;li&gt;
                &lt;a href="https://huggingface.co/laion/erlich/resolve/main/model/ema_0.9999_120000.pt"&gt;erlich.pt&lt;/a&gt;:
                Trained on the LAION large logo dataset.
            &lt;/li&gt;
        &lt;/ul&gt;
    &lt;/li&gt;</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>
    &lt;li&gt;
        Start IntraPaint by running "&lt;code&gt;python IntraPaint.py&lt;/code&gt;". If you are using a model other than the default
        inpaint.pt, instead run "&lt;code&gt;python Intrapaint_server.py  --model_path models/model.pt&lt;/code&gt;", replacing
        "model.pt" with the file name of whatever model you are using.
    &lt;/li&gt;
&lt;/ol&gt;
&lt;p&gt;Once these steps are completed, you should be able to activate this generator without any errors.&lt;/p&gt;
</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>Required dependencies are missing: &lt;code&gt;{dependency_list}&lt;/code&gt;</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>Not enough VRAM for the GLID-3-XL generator: {mem_free} free memory found, expected at least {min_vram}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>{model_name} model file expected at "{model_path}" is missing</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/glid3_xl_generator.py"/>
        <source>Missing required {repo_name} repository, please run `git clone {repo_url}` within the IntraPaint directory.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>controller.image_generation.null_generator</name>
    <message>
        <location filename="../../src/controller/image_generation/null_generator.py"/>
        <source>No image generator</source>
        <translation>无图像生成器</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/null_generator.py"/>
        <source>&lt;p&gt;IntraPaint does not need an image generator to function.  If you don't want to set up an image generator, you can still use it like any other image editor.</source>
        <translation>&lt;p&gt;IntraPaint 不需要图像生成器也能使用。如果不想设置图像生成器，仍可以像其他图像编辑器一样使用它。</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/null_generator.py"/>
        <source>This option has no setup requirements.</source>
        <translation>此选项无需任何设置。</translation>
    </message>
</context>
<context>
    <name>controller.image_generation.sd_adapters.progress_adapter</name>
    <message>
        <location filename="../../src/controller/image_generation/sd_adapters/progress_adapter.py"/>
        <source>Waiting, position {queue_number} in queue.</source>
        <translation>等待中，排在队列第 {queue_number} 位。</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_adapters/progress_adapter.py"/>
        <source>Waiting...</source>
        <translation>等待中...</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_adapters/progress_adapter.py"/>
        <source>Generating...</source>
        <translation>正在生成...</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_adapters/progress_adapter.py"/>
        <source>Batch {batch_num} of {num_batches}:</source>
        <translation>第 {batch_num}/{num_batches} 批：</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_adapters/progress_adapter.py"/>
        <source>ETA: {minutes}:{seconds}</source>
        <translation>预计剩余 {minutes}:{seconds}</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_adapters/progress_adapter.py"/>
        <source>ETA: {seconds}s</source>
        <translation>预计剩余 {seconds} 秒</translation>
    </message>
</context>
<context>
    <name>controller.image_generation.sd_comfyui_generator</name>
    <message>
        <location filename="../../src/controller/image_generation/sd_comfyui_generator.py"/>
        <source>Stable Diffusion ComfyUI API</source>
        <translation>Stable Diffusion ComfyUI API</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_comfyui_generator.py"/>
        <source>&lt;h2&gt;Stable Diffusion: via ComfyUI API&lt;/h2&gt;</source>
        <translation>&lt;h2&gt;Stable Diffusion：通过 ComfyUI API&lt;/h2&gt;</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_comfyui_generator.py"/>
        <source>
&lt;h3&gt;About ComfyUI&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://www.comfy.org/"&gt;ComfyUI&lt;/a&gt; is a popular Stable Diffusion interface with complex and powerful
    node-based controls. When ComfyUI is running, IntraPaint can access Stable Diffusion image generation by
    sending requests to ComfyUI.  You can run ComfyUI on the same computer as IntraPaint, or remotely on a separate
     server.
&lt;/p&gt;
&lt;p&gt;
    When connected, IntraPaint provides controls for ComfyUI in the &lt;b&gt;Image Generation&lt;/b&gt; tab and in the &lt;b&gt;settings
    window&lt;/b&gt; under the Stable Diffusion category. You can also access ComfyUI's interface directly through a web 
    browser at &lt;a href="http://localhost:8188/"&gt;localhost:8188&lt;/a&gt;.
&lt;/p&gt;
</source>
        <translation>
&lt;h3&gt;关于 ComfyUI&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://www.comfy.org/"&gt;ComfyUI&lt;/a&gt; 是一款流行的 Stable Diffusion 界面，提供复杂而强大的基于节点的控制方式。ComfyUI
    运行时，IntraPaint 可以通过向 ComfyUI 发送请求来使用 Stable Diffusion 图像生成。ComfyUI
    可以与 IntraPaint 运行在同一台电脑上，也可以远程运行在另一台服务器上。

&lt;/p&gt;
&lt;p&gt;
    连接后，IntraPaint 会在&lt;b&gt;图像生成&lt;/b&gt;面板和&lt;b&gt;设置窗口&lt;/b&gt;的 Stable Diffusion 类别中提供 ComfyUI
    的控制选项。也可以直接在网页浏览器中通过 &lt;a href="http://localhost:8188/"&gt;localhost:8188&lt;/a&gt;
    访问 ComfyUI 自己的界面。
&lt;/p&gt;
</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_comfyui_generator.py"/>
        <source>
&lt;h1&gt;Stable Diffusion ComfyUI Generator Setup&lt;/h1&gt;
&lt;p&gt;
    To use the Stable Diffusion ComfyUI generator, you will need to download at least one Stable Diffusion model file, 
    install ComfyUI, and start it.  This guide will explain each of those steps.
&lt;/p&gt;</source>
        <translatorcomment>glossary: not "Steps" - the steps of this setup guide, not sampling steps.</translatorcomment>
        <translation>
&lt;h1&gt;Stable Diffusion ComfyUI 生成器设置&lt;/h1&gt;
&lt;p&gt;
    要使用 Stable Diffusion ComfyUI 生成器，需要下载至少一个 Stable Diffusion 模型文件、安装
    ComfyUI，然后启动它。本指南将逐一说明这些步骤。
&lt;/p&gt;</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_comfyui_generator.py"/>
        <source>
&lt;hr/&gt;
&lt;h2&gt;Installing ComfyUI: Available options&lt;/h2&gt;
&lt;p&gt;
    There are a few different ways you can install ComfyUI. The recommended method is to use
    &lt;a href="https://github.com/LykosAI/StabilityMatrix?tab=readme-ov-file#stability-matrix"&gt;Stability Matrix&lt;/a&gt;,
    but other methods are covered here for the sake of completeness.
&lt;/p&gt;
&lt;hr/&gt;
&lt;h2&gt;Option 1: Stability Matrix&lt;/h2&gt;
&lt;p&gt;
    Installation through Stability Matrix is the recommended method. This method is the simplest option, provides a lot
    of helpful extra resources, and supports Windows, macOS and Linux.  This method also lets you easily install and use
    Stable Diffusion WebUI, the other Stable Diffusion client that IntraPaint can use.
&lt;/p&gt;</source>
        <translation>
&lt;hr/&gt;
&lt;h2&gt;安装 ComfyUI：可选方法&lt;/h2&gt;
&lt;p&gt;
    安装 ComfyUI 有几种不同的方法。推荐使用
    &lt;a href="https://github.com/LykosAI/StabilityMatrix?tab=readme-ov-file#stability-matrix"&gt;Stability Matrix&lt;/a&gt;，为完整起见，这里也介绍其他方法。

&lt;/p&gt;
&lt;hr/&gt;
&lt;h2&gt;方法 1：Stability Matrix&lt;/h2&gt;
&lt;p&gt;
    推荐通过 Stability Matrix 安装。这是最简单的方法，提供许多实用的额外资源，并支持
    Windows、macOS 和 Linux。使用这种方法还可以轻松安装并使用
    Stable Diffusion WebUI，即 IntraPaint 可以使用的另一个 Stable Diffusion 客户端。
&lt;/p&gt;</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_comfyui_generator.py"/>
        <source>
&lt;hr/&gt;
&lt;h2&gt;Option 2: Prepackaged Windows version&lt;/h2&gt;
&lt;p&gt;
    If you're using Windows and don't need any of the extra features in Stability Matrix, you can download a 
    prepackaged version of ComfyUI from GitHub.
&lt;/p&gt;
&lt;ol&gt;
    &lt;li&gt;
        Download &lt;b&gt;ComfyUI_windows_portable_nvidia.7z&lt;/b&gt; from the most recent version listed on the &lt;a href=
        "https://github.com/comfyanonymous/ComfyUI/releases"&gt;ComfyUI GitHub release page&lt;/a&gt;.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Extract the downloaded package into a new folder. If you're not using Windows 11, you may need to install
        &lt;a href="https://www.7-zip.org"&gt;7-Zip&lt;/a&gt; to extract the compressed files.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        If you haven't already found at least one Stable Diffusion model file, do that now. Copy it into the 
        ComfyUI folder under &lt;b&gt;ComfyUI\models\checkpoints&lt;/b&gt;.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Launch the &lt;b&gt;run_nvidia_gpu.bat&lt;/b&gt; file in the ComfyUI folder to start Stable Diffusion. A terminal window
        will open and print startup information as Comfy initializes.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Once you see &lt;b&gt;"To see the GUI go to: http://127.0.0.1:8188"&lt;/b&gt; in the terminal window, Stable Diffusion is
        ready to use.  Back in IntraPaint, click the "Activate" button below to connect to Stable Diffusion. &lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        In the future, the only step you'll need to repeat from this list is launching &lt;b&gt;run_nvidia_gpu.bat&lt;/b&gt; and
        waiting for it to finish starting up. If you do this before launching IntraPaint, it will automatically connect
        to the ComfyUI image generator on startup.
    &lt;/li&gt;
&lt;/ol&gt;
&lt;hr/&gt;
&lt;h3&gt;Option 3: Running directly in Python&lt;/h3&gt;
&lt;p&gt;
    This method requires a lot more technical knowledge than the previous ones, but it also provides the most
    flexibility and requires the least amount of storage space.  This is only recommended if you've set up a Python
    virtual environment and debugged Python dependency issues before, or if you're interested in teaching yourself to
    do so.
&lt;/p&gt;
&lt;p&gt;
    Because this option isn't recommended, IntraPaint won't provide a full guide.
    &lt;a href="https://github.com/comfyanonymous/ComfyUI?tab=readme-ov-file#manual-install-windows-linux"&gt;
    ComfyUI's manual installation instructions&lt;/a&gt; should help you get started. If you run into any problems,
    searching the &lt;a href="https://github.com/comfyanonymous/ComfyUI/issues"&gt;ComfyUI issues page&lt;/a&gt; will 
    probably help you find a solution.
&lt;/p&gt;
</source>
        <translation>
&lt;hr/&gt;
&lt;h2&gt;方法 2：预打包的 Windows 版本&lt;/h2&gt;
&lt;p&gt;
    如果使用 Windows，并且不需要 Stability Matrix 的额外功能，可以从 GitHub 下载预打包的
    ComfyUI 版本。
&lt;/p&gt;
&lt;ol&gt;
    &lt;li&gt;
        在 &lt;a href=
        "https://github.com/comfyanonymous/ComfyUI/releases"&gt;ComfyUI GitHub 发布页面&lt;/a&gt;中找到最新版本，下载其中的 &lt;b&gt;ComfyUI_windows_portable_nvidia.7z&lt;/b&gt;。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        将下载的压缩包解压到一个新文件夹中。如果使用的不是 Windows 11，可能需要先安装
        &lt;a href="https://www.7-zip.org"&gt;7-Zip&lt;/a&gt; 才能解压这些压缩文件。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        如果还没有找到至少一个 Stable Diffusion 模型文件，现在就去找。将它复制到
        ComfyUI 文件夹下的 &lt;b&gt;ComfyUI\models\checkpoints&lt;/b&gt; 中。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        运行 ComfyUI 文件夹中的 &lt;b&gt;run_nvidia_gpu.bat&lt;/b&gt; 文件以启动 Stable Diffusion。终端窗口会打开，并在
        ComfyUI 初始化时显示启动信息。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        当终端窗口中出现&lt;b&gt;“To see the GUI go to: http://127.0.0.1:8188”&lt;/b&gt;时，Stable Diffusion
        就可以使用了。回到 IntraPaint，点击下方的“激活”按钮即可连接到 Stable Diffusion。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        以后，这些步骤中只需重复一步：运行 &lt;b&gt;run_nvidia_gpu.bat&lt;/b&gt;
        并等待它启动完成。如果在启动 IntraPaint 之前完成这一步，IntraPaint 会在启动时自动连接到
        ComfyUI 图像生成器。
    &lt;/li&gt;
&lt;/ol&gt;
&lt;hr/&gt;
&lt;h3&gt;方法 3：直接在 Python 中运行&lt;/h3&gt;
&lt;p&gt;
    这种方法比前两种需要多得多的技术知识，但灵活性最高，占用的存储空间也最少。只有在以前搭建过
    Python 虚拟环境并排查过 Python
    依赖问题，或者有兴趣自学这些内容时，才推荐使用这种方法。

&lt;/p&gt;
&lt;p&gt;
    由于不推荐这种方法，IntraPaint 不提供完整指南。
    &lt;a href="https://github.com/comfyanonymous/ComfyUI?tab=readme-ov-file#manual-install-windows-linux"&gt;
    ComfyUI 的手动安装说明&lt;/a&gt;可以帮助入门。如果遇到问题，在 &lt;a href="https://github.com/comfyanonymous/ComfyUI/issues"&gt;ComfyUI Issues 页面&lt;/a&gt;中搜索，通常能找到解决方法。


&lt;/p&gt;
</translation>
    </message>
    <message>
        <source>
&lt;h3&gt;About ComfyUI&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://www.comfy.org/"&gt;ComfyUI&lt;/a&gt; is a popular Stable Diffusion interface with complex and powerful
    node-based controls. When the ComfyUI is running, IntraPaint can access Stable Diffusion image generation by
    sending requests to ComfyUI.  You can run ComfyUI on the same computer as IntraPaint, or remotely on a separate
     server.
&lt;/p&gt;
&lt;p&gt;
    When connected, IntraPaint provides controls for ComfyUI in the &lt;b&gt;Image Generation&lt;/b&gt; tab and in the &lt;b&gt;settings
    window&lt;/b&gt; under the Stable Diffusion category. You can also access ComfyUI's interface directly through a web 
    browser at &lt;a href="http://localhost:8188/"&gt;localhost:8188&lt;/a&gt;.
&lt;/p&gt;
</source>
        <translation type="vanished">
&lt;h3&gt;关于 ComfyUI&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://www.comfy.org/"&gt;ComfyUI&lt;/a&gt; 是一款流行的 Stable Diffusion 界面，提供复杂而强大的基于节点的控制方式。ComfyUI
    运行时，IntraPaint 可以通过向 ComfyUI 发送请求来使用 Stable Diffusion 图像生成。ComfyUI
    可以与 IntraPaint 运行在同一台电脑上，也可以远程运行在另一台服务器上。

&lt;/p&gt;
&lt;p&gt;
    连接后，IntraPaint 会在&lt;b&gt;图像生成&lt;/b&gt;面板和&lt;b&gt;设置窗口&lt;/b&gt;的 Stable Diffusion 类别中提供 ComfyUI
    的控制选项。也可以直接在网页浏览器中通过 &lt;a href="http://localhost:8188/"&gt;localhost:8188&lt;/a&gt;
    访问 ComfyUI 自己的界面。
&lt;/p&gt;
</translation>
    </message>
    <message>
        <source>
&lt;h1&gt;Stable Diffusion ComfyUI Generator Setup&lt;/h1&gt;
&lt;p&gt;
    To use the Stable Diffusion ComfyUI generator, you will to download at least one Stable Diffusion model file, 
    install ComfyUI, and start it.  This guide will explain each of those steps.
&lt;/p&gt;</source>
        <translatorcomment>glossary: not "Steps" - the steps of this setup guide, not sampling steps.</translatorcomment>
        <translation type="vanished">
&lt;h1&gt;Stable Diffusion ComfyUI 生成器设置&lt;/h1&gt;
&lt;p&gt;
    要使用 Stable Diffusion ComfyUI 生成器，需要下载至少一个 Stable Diffusion 模型文件、安装
    ComfyUI，然后启动它。本指南将逐一说明这些步骤。
&lt;/p&gt;</translation>
    </message>
</context>
<context>
    <name>controller.image_generation.sd_generator</name>
    <message>
        <location filename="../../src/controller/image_generation/sd_generator.py"/>
        <source>
&lt;p&gt;
    Released in August 2022, Stable Diffusion remains the most versatile and useful free image generation model.
&lt;/p&gt;
&lt;h2&gt;Generator capabilities and limits:&lt;/h2&gt;
&lt;ul&gt;
    &lt;li&gt;Requires only 4GB of VRAM, or 8GB if using an SDXL model.&lt;/li&gt;
    &lt;li&gt;Tuned for an ideal resolution of 512x512 (1024x1024 for SDXL).&lt;/li&gt;
    &lt;li&gt;
     Because it's relatively easy to re-train, a vast library of free &lt;b&gt;fine-tuned variant models&lt;/b&gt; are
     available.
    &lt;/li&gt;
    &lt;li&gt;
        The strength of AI image changes can be controlled precisely using the &lt;b&gt;denoising strength&lt;/b&gt; option.
    &lt;/li&gt;
    &lt;li&gt;
        Able to use &lt;b&gt;LoRAs&lt;/b&gt;, miniature extension models adding support for new styles and subjects.
    &lt;/li&gt;
    &lt;li&gt;
        Supports positive and negative prompting, where (parentheses) draw additional attention to prompt sections,
        and [square brackets] reduce attention.
    &lt;/li&gt;
    &lt;li&gt;
        Supports &lt;b&gt;ControlNet&lt;/b&gt; models, allowing image generation to be guided by arbitrary constraints like depth
        maps, existing image lines, and pose analysis.
    &lt;/li&gt;
&lt;/ul&gt;
</source>
        <translation>
&lt;p&gt;
    Stable Diffusion 于 2022 年 8 月发布，至今仍是用途最广、最实用的免费图像生成模型。
&lt;/p&gt;
&lt;h2&gt;生成器的能力与限制：&lt;/h2&gt;
&lt;ul&gt;
    &lt;li&gt;只需 4GB 显存，使用 SDXL 模型时需要 8GB。&lt;/li&gt;
    &lt;li&gt;针对 512x512 的理想分辨率调校（SDXL 为 1024x1024）。&lt;/li&gt;
    &lt;li&gt;
     由于重新训练相对容易，有大量免费的&lt;b&gt;微调变体模型&lt;/b&gt;可供使用。

    &lt;/li&gt;
    &lt;li&gt;
        可以通过&lt;b&gt;重绘幅度&lt;/b&gt;选项精确控制 AI 修改图像的强度。
    &lt;/li&gt;
    &lt;li&gt;
        可以使用 &lt;b&gt;LoRA&lt;/b&gt;，一种为新风格和新主题提供支持的小型扩展模型。
    &lt;/li&gt;
    &lt;li&gt;
        支持正面和负面提示词：用圆括号 ()
        括起的提示词部分会获得更多关注，用方括号 [] 括起的部分则会减少关注。
    &lt;/li&gt;
    &lt;li&gt;
        支持 &lt;b&gt;ControlNet&lt;/b&gt;
        模型，可以用深度图、现有图像的线条、姿态分析等任意约束来引导图像生成。
    &lt;/li&gt;
&lt;/ul&gt;
</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_generator.py"/>
        <source>
&lt;h3&gt;Stability Matrix installation and setup&lt;/h3&gt;
&lt;ol&gt;
    &lt;li&gt;
        Download the appropriate version of Stability Matrix for your system:
        &lt;ul&gt;
            &lt;li&gt;
                &lt;a
                 href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-win-x64.zip"
                 &gt;Windows 10, 11
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;
                &lt;a
              href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-macos-arm64.dmg"
                 &gt;macOS, Apple Silicon
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;
                &lt;a
                href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-linux-x64.zip"
                &gt;Linux AppImage
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;&lt;a href="https://aur.archlinux.org/packages/stabilitymatrix"&gt; Arch Linux AUR&lt;/a&gt;&lt;/li&gt;
        &lt;/ul&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Extract and launch the downloaded file. On the first launch it will ask you to select a data directory, and ask
        you to select a package to install. Choose &lt;b&gt;"{generator_package}"&lt;/b&gt;, and wait for installation to finish.
        From here, Stability Matrix will go to the &lt;img src='{packages_icon}'/&gt;
        &lt;b&gt;Packages&lt;/b&gt; tab, where you can configure or launch the WebUI, or install alternate Stable Diffusion
        packages.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        If you've already downloaded Stable Diffusion or ControlNet models, go to the 
         &lt;img src='{checkpoints_icon}'/&gt;&lt;b&gt;Checkpoint Manager&lt;/b&gt; tab on the left.
         Click the "&lt;big&gt;⋯&lt;/big&gt;" menu button on the upper right, and choose "Models Folder", and it will open the 
         folder you need in the system file manager.  Copy Stable Diffusion models into the "StableDiffusion"
         subfolder, and copy any ControlNet models to the "ControlNet" subfolder.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        If you haven't downloaded any Stable Diffusion models yet, you can do that in Stability Matrix.
        Go to the &lt;img src='{models_icon}'/&gt;&lt;b&gt;Model Browser&lt;/b&gt; tab to find and
        download a Stable Diffusion model file.&lt;br/&gt;
    &lt;/li&gt;
    {post_install_generator_setup}
    &lt;li&gt;
        On the &lt;img src='{packages_icon}'/&gt;&lt;b&gt;Packages&lt;/b&gt; tab, click the
        &lt;b&gt;Launch&lt;/b&gt; button under &lt;b&gt;"{generator_package}"&lt;/b&gt;.  A log screen will open up, showing the status of the
        package as it starts up.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Once the &lt;b&gt;"Open Web UI"&lt;/b&gt; button appears at the top of the window, Stable Diffusion is ready to use.  Back
        in IntraPaint, click the "Activate" button below to connect to Stable Diffusion. &lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        In the future, the only steps you'll need to repeat from this list are launching Stability Matrix and clicking
        the "Launch" button. If you do this before launching IntraPaint, it will automatically connect to this image
        generator on startup.
    &lt;/li&gt;
&lt;/ol&gt;
</source>
        <translatorcomment>glossary: not "Steps" - the steps of this setup guide, not sampling steps.</translatorcomment>
        <translation>
&lt;h3&gt;Stability Matrix 的安装与设置&lt;/h3&gt;
&lt;ol&gt;
    &lt;li&gt;
        根据系统下载对应版本的 Stability Matrix：
        &lt;ul&gt;
            &lt;li&gt;
                &lt;a
                 href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-win-x64.zip"
                 &gt;Windows 10, 11
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;
                &lt;a
              href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-macos-arm64.dmg"
                 &gt;macOS, Apple Silicon
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;
                &lt;a
                href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-linux-x64.zip"
                &gt;Linux AppImage
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;&lt;a href="https://aur.archlinux.org/packages/stabilitymatrix"&gt; Arch Linux AUR&lt;/a&gt;&lt;/li&gt;
        &lt;/ul&gt;
    &lt;/li&gt;
    &lt;li&gt;
        解压并运行下载的文件。首次启动时，程序会要求选择数据目录，并选择要安装的软件包。请选择&lt;b&gt;“{generator_package}”&lt;/b&gt;，然后等待安装完成。之后
        Stability Matrix 会转到 &lt;img src='{packages_icon}'/&gt;
        &lt;b&gt;Packages&lt;/b&gt; 选项卡，可以在这里配置或启动 WebUI，或安装其他 Stable Diffusion
        软件包。
&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        如果已经下载了 Stable Diffusion 或 ControlNet 模型，请转到左侧的
         &lt;img src='{checkpoints_icon}'/&gt;&lt;b&gt;Checkpoint Manager&lt;/b&gt; 选项卡。点击右上角的“&lt;big&gt;⋯&lt;/big&gt;”菜单按钮，选择“Models Folder”，系统文件管理器中就会打开所需的文件夹。将 Stable Diffusion 模型复制到“StableDiffusion”子文件夹，将 ControlNet 模型复制到“ControlNet”子文件夹。


&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        如果还没有下载任何 Stable Diffusion 模型，可以在 Stability Matrix
        中下载。转到 &lt;img src='{models_icon}'/&gt;&lt;b&gt;Model Browser&lt;/b&gt; 选项卡，查找并下载 Stable Diffusion
        模型文件。&lt;br/&gt;
    &lt;/li&gt;
    {post_install_generator_setup}
    &lt;li&gt;
        在 &lt;img src='{packages_icon}'/&gt;&lt;b&gt;Packages&lt;/b&gt; 选项卡中，点击&lt;b&gt;“{generator_package}”&lt;/b&gt;下方的
        &lt;b&gt;Launch&lt;/b&gt; 按钮。日志界面会打开，显示软件包启动时的状态。
&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        当窗口顶部出现&lt;b&gt;“Open Web UI”&lt;/b&gt;按钮时，Stable Diffusion 就可以使用了。回到
        IntraPaint，点击下方的“激活”按钮即可连接到 Stable Diffusion。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        以后，这些步骤中只需重复两步：启动 Stability Matrix
        并点击“Launch”按钮。如果在启动 IntraPaint
        之前完成这些操作，IntraPaint 会在启动时自动连接到此图像生成器。
    &lt;/li&gt;
&lt;/ol&gt;
</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_generator.py"/>
        <source>
&lt;h2&gt;Getting Stable Diffusion Model Files&lt;/h2&gt;
&lt;p&gt;
    To use Stable Diffusion, you'll need at least one Stable Diffusion model file.  These files (also called
    checkpoints), contain the data structures that Stable Diffusion uses to create images.  A huge variety of
    fine-tuned models are available on sites like &lt;a href="https://civitai.com/"&gt;CivitAI&lt;/a&gt; and
    &lt;a href="https://huggingface.co/"&gt;Hugging Face&lt;/a&gt;, each with its own strengths and weaknesses.
&lt;/p&gt;
&lt;p&gt;
    If you want to use Stable Diffusion with ControlNet, you will also need to download ControlNet model files.
    Each ControlNet model provides a new way to control image generation. The official ControlNet models for use with
    Stable Diffusion 1.5 model variants can be downloaded from
    &lt;a href="https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors/tree/main"&gt;this page on Hugging
    Face&lt;/a&gt;. More options, including ones with support for Stable Diffusion XL, are linked on the 
    Stable Diffusion WebUI ControlNet extension 
    &lt;a href="https://github.com/Mikubill/sd-webui-controlnet/wiki/Model-download#official-controlnet-11-models"&gt;
    GitHub wiki&lt;/a&gt;.
&lt;/p&gt;
</source>
        <translation>
&lt;h2&gt;获取 Stable Diffusion 模型文件&lt;/h2&gt;
&lt;p&gt;
    要使用 Stable Diffusion，至少需要一个 Stable Diffusion 模型文件。这些文件（也称为
    checkpoint）包含 Stable Diffusion 用来生成图像的数据结构。在
    &lt;a href="https://civitai.com/"&gt;CivitAI&lt;/a&gt; 和
    &lt;a href="https://huggingface.co/"&gt;Hugging Face&lt;/a&gt; 等网站上可以找到大量微调模型，各有优缺点。
&lt;/p&gt;
&lt;p&gt;
    如果要将 Stable Diffusion 与 ControlNet 一起使用，还需要下载 ControlNet 模型文件。每个
    ControlNet 模型都提供一种控制图像生成的新方式。适用于 Stable Diffusion 1.5 系列模型的官方
    ControlNet 模型可以从
    &lt;a href="https://huggingface.co/comfyanonymous/ControlNet-v1-1_fp16_safetensors/tree/main"&gt;Hugging Face
    上的这个页面&lt;/a&gt;下载。更多选择（包括支持 Stable Diffusion XL 的模型）列在
    Stable Diffusion WebUI ControlNet 扩展的
    &lt;a href="https://github.com/Mikubill/sd-webui-controlnet/wiki/Model-download#official-controlnet-11-models"&gt;
    GitHub wiki&lt;/a&gt; 上。
&lt;/p&gt;
</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_generator.py"/>
        <source>ControlNet preview failed</source>
        <translation>ControlNet 预览失败</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_generator.py"/>
        <source>Loading ControlNet preprocessor preview failed: {err}</source>
        <translation>加载 ControlNet 预处理器预览失败：{err}</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_generator.py"/>
        <source>&amp;Generation</source>
        <translation>生成(&amp;G)</translation>
    </message>
    <message>
        <source>
&lt;h3&gt;Stability Matrix installation and setup&lt;/h3&gt;
&lt;ol&gt;
    &lt;li&gt;
        Download the appropriate version of Stability Matrix for your system:
        &lt;ul&gt;
            &lt;li&gt;
                &lt;a
                 href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-win-x64.zip"
                 &gt;Windows 10, 11
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;
                &lt;a
              href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-macos-arm64.dmg"
                 &gt;macOS, Apple Silicon
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;
                &lt;a
                href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-linux-x64.zip"
                &gt;Linux AppImage
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;&lt;a href="https://aur.archlinux.org/packages/stabilitymatrix"&gt; Arch Linux AUR&lt;/a&gt;&lt;/li&gt;
        &lt;/ul&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Extract and launch the downloaded file. On the first launch it will ask you to select a data directory, and ask
        you to select a package to install. Choose &lt;b&gt;"{generator_package}"&lt;/b&gt;, and wait for installation to finish.
        From here, Stability-Matrix will go to the &lt;img src='{packages_icon}'/&gt;
        &lt;b&gt;Packages&lt;/b&gt; tab, where you can configure or launch the WebUI, or install alternate Stable Diffusion
        packages.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        If you've already downloaded Stable Diffusion or ControlNet models, go to the 
         &lt;img src='{checkpoints_icon}'/&gt;&lt;b&gt;Checkpoint Manager&lt;/b&gt; tab on the left.
         Click the "&lt;big&gt;⋯&lt;/big&gt;" menu button on the upper right, and choose "Models Folder", and it will open the 
         folder you need in the system file manager.  Copy Stable Diffusion models into the "StableDiffusion"
         subfolder, and copy any ControlNet models to the "ControlNet" subfolder.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        If you haven't downloaded any Stable Diffusion models yet, you can do that in Stability Matrix.
        Go to the &lt;img src='{models_icon}'/&gt;&lt;b&gt;Model Browser&lt;/b&gt; tab to find and
        download a Stable Diffusion model file.&lt;br/&gt;
    &lt;/li&gt;
    {post_install_generator_setup}
    &lt;li&gt;
        On the &lt;img src='{packages_icon}'/&gt;&lt;b&gt;Packages&lt;/b&gt; tab, click the
        &lt;b&gt;Launch&lt;/b&gt; button under &lt;b&gt;"{generator_package}"&lt;/b&gt;.  A log screen will open up, showing the status of the
        package as it starts up.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Once the &lt;b&gt;"Open Web UI"&lt;/b&gt; button appears at the top of the window, Stable Diffusion is ready to use.  Back
        in IntraPaint, click the "Activate" button below to connect to Stable Diffusion. &lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        In the future, the only steps you'll need to repeat from this list are launching Stability Matrix and clicking
        the "Launch" button. If you do this before launching IntraPaint, it will automatically connect to this image
        generator on startup.
    &lt;/li&gt;
&lt;/ol&gt;
</source>
        <translatorcomment>glossary: not "Steps" - the steps of this setup guide, not sampling steps.</translatorcomment>
        <translation type="vanished">
&lt;h3&gt;Stability Matrix 的安装与设置&lt;/h3&gt;
&lt;ol&gt;
    &lt;li&gt;
        根据系统下载对应版本的 Stability Matrix：
        &lt;ul&gt;
            &lt;li&gt;
                &lt;a
                 href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-win-x64.zip"
                 &gt;Windows 10, 11
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;
                &lt;a
              href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-macos-arm64.dmg"
                 &gt;macOS, Apple Silicon
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;
                &lt;a
                href="https://github.com/LykosAI/StabilityMatrix/releases/latest/download/StabilityMatrix-linux-x64.zip"
                &gt;Linux AppImage
                &lt;/a&gt;
            &lt;/li&gt;
            &lt;li&gt;&lt;a href="https://aur.archlinux.org/packages/stabilitymatrix"&gt; Arch Linux AUR&lt;/a&gt;&lt;/li&gt;
        &lt;/ul&gt;
    &lt;/li&gt;
    &lt;li&gt;
        解压并运行下载的文件。首次启动时，程序会要求选择数据目录，并选择要安装的软件包。请选择&lt;b&gt;“{generator_package}”&lt;/b&gt;，然后等待安装完成。之后
        Stability Matrix 会转到 &lt;img src='{packages_icon}'/&gt;
        &lt;b&gt;Packages&lt;/b&gt; 选项卡，可以在这里配置或启动 WebUI，或安装其他 Stable Diffusion
        软件包。
&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        如果已经下载了 Stable Diffusion 或 ControlNet 模型，请转到左侧的
         &lt;img src='{checkpoints_icon}'/&gt;&lt;b&gt;Checkpoint Manager&lt;/b&gt; 选项卡。点击右上角的“&lt;big&gt;⋯&lt;/big&gt;”菜单按钮，选择“Models Folder”，系统文件管理器中就会打开所需的文件夹。将 Stable Diffusion 模型复制到“StableDiffusion”子文件夹，将 ControlNet 模型复制到“ControlNet”子文件夹。


&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        如果还没有下载任何 Stable Diffusion 模型，可以在 Stability Matrix
        中下载。转到 &lt;img src='{models_icon}'/&gt;&lt;b&gt;Model Browser&lt;/b&gt; 选项卡，查找并下载 Stable Diffusion
        模型文件。&lt;br/&gt;
    &lt;/li&gt;
    {post_install_generator_setup}
    &lt;li&gt;
        在 &lt;img src='{packages_icon}'/&gt;&lt;b&gt;Packages&lt;/b&gt; 选项卡中，点击&lt;b&gt;“{generator_package}”&lt;/b&gt;下方的
        &lt;b&gt;Launch&lt;/b&gt; 按钮。日志界面会打开，显示软件包启动时的状态。
&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        当窗口顶部出现&lt;b&gt;“Open Web UI”&lt;/b&gt;按钮时，Stable Diffusion 就可以使用了。回到
        IntraPaint，点击下方的“激活”按钮即可连接到 Stable Diffusion。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        以后，这些步骤中只需重复两步：启动 Stability Matrix
        并点击“Launch”按钮。如果在启动 IntraPaint
        之前完成这些操作，IntraPaint 会在启动时自动连接到此图像生成器。
    &lt;/li&gt;
&lt;/ol&gt;
</translation>
    </message>
</context>
<context>
    <name>controller.image_generation.sd_webui_generator</name>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>Stable Diffusion WebUI API</source>
        <translation>Stable Diffusion WebUI API</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>&lt;h2&gt;Stable Diffusion: via WebUI API&lt;/h2&gt;</source>
        <translation>&lt;h2&gt;Stable Diffusion：通过 WebUI API&lt;/h2&gt;</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>
&lt;h3&gt;About the Stable Diffusion WebUI&lt;/h3&gt;
&lt;p&gt;
    The &lt;a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui?tab=readme-ov-file#stable-diffusion-web-ui"&gt;
    Stable Diffusion WebUI&lt;/a&gt; is one of the first interfaces created for using Stable Diffusion. When the WebUI is
    running and configured correctly, IntraPaint can access Stable Diffusion image generation by sending requests to
    the WebUI. You can run the WebUI on the same computer as IntraPaint, or remotely on a separate server.
&lt;/p&gt;
&lt;p&gt;
    When connected, IntraPaint provides controls for the WebUI in the &lt;b&gt;Image Generation&lt;/b&gt; tab and in the &lt;b&gt;settings
    window&lt;/b&gt; under the Stable Diffusion category. When running, you can also access the WebUI's own interface
    directly through your web browser at &lt;a href="http://localhost:7860/"&gt;localhost:7860&lt;/a&gt;.
&lt;/p&gt;
&lt;h3&gt;About Stable Diffusion WebUI Forge&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge?tab=readme-ov-file#stable-diffusion-webui-forge"&gt;
    Stable Diffusion WebUI Forge&lt;/a&gt; is a popular variant of the original Stable Diffusion WebUI, that adds significant
    improvements to image generation speed and efficiency. It also adds a large number of experimental features that 
    cause compatibility issues. IntraPaint provides some support for WebUI Forge, but ControlNet will not work with
    recent versions.
&lt;/p&gt;
&lt;h3&gt;About Stable Diffusion WebUI reForge&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://github.com/Panchovix/stable-diffusion-webui-reForge?tab=readme-ov-file#stable-diffusion-webui-forgereforge"&gt;
    Stable Diffusion WebUI reForge&lt;/a&gt; is a third version of the WebUI that includes the improved performance of
    WebUI Forge without any of the compatibility issues. &lt;b&gt;This is the recommended version to use with IntraPaint&lt;/b&gt;.
&lt;/p&gt;
</source>
        <translation>
&lt;h3&gt;关于 Stable Diffusion WebUI&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui?tab=readme-ov-file#stable-diffusion-web-ui"&gt;
    Stable Diffusion WebUI&lt;/a&gt; 是最早用于运行 Stable Diffusion 的界面之一。WebUI
    运行且配置正确时，IntraPaint 可以通过向 WebUI 发送请求来使用 Stable Diffusion 图像生成。WebUI
    可以与 IntraPaint 运行在同一台电脑上，也可以远程运行在另一台服务器上。
&lt;/p&gt;
&lt;p&gt;
    连接后，IntraPaint 会在&lt;b&gt;图像生成&lt;/b&gt;面板和&lt;b&gt;设置窗口&lt;/b&gt;的 Stable Diffusion 类别中提供 WebUI
    的控制选项。WebUI 运行时，也可以直接在网页浏览器中通过 &lt;a href="http://localhost:7860/"&gt;localhost:7860&lt;/a&gt;
    访问 WebUI 自己的界面。
&lt;/p&gt;
&lt;h3&gt;关于 Stable Diffusion WebUI Forge&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge?tab=readme-ov-file#stable-diffusion-webui-forge"&gt;
    Stable Diffusion WebUI Forge&lt;/a&gt; 是原版 Stable Diffusion WebUI
    的一个流行变体，大幅提升了图像生成的速度和效率。它还加入了大量会导致兼容性问题的实验性功能。IntraPaint 对 WebUI
    Forge 提供部分支持，但 ControlNet 无法在较新版本中使用。

&lt;/p&gt;
&lt;h3&gt;关于 Stable Diffusion WebUI reForge&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://github.com/Panchovix/stable-diffusion-webui-reForge?tab=readme-ov-file#stable-diffusion-webui-forgereforge"&gt;
    Stable Diffusion WebUI reForge&lt;/a&gt; 是 WebUI 的第三个版本，具备 WebUI
    Forge 的性能改进，同时没有任何兼容性问题。&lt;b&gt;这是推荐与 IntraPaint 搭配使用的版本&lt;/b&gt;。
&lt;/p&gt;
</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>
&lt;h1&gt;Stable Diffusion WebUI Generator Setup&lt;/h1&gt;
&lt;p&gt;
    To use the Stable Diffusion WebUI generator, you will need to download at least one Stable Diffusion model file, 
    install the WebUI, enable API access, and start the WebUI.  This guide will explain each of those steps.
&lt;/p&gt;</source>
        <translatorcomment>glossary: not "Steps" - the steps of this setup guide, not sampling steps.</translatorcomment>
        <translation>
&lt;h1&gt;Stable Diffusion WebUI 生成器设置&lt;/h1&gt;
&lt;p&gt;
    要使用 Stable Diffusion WebUI 生成器，需要下载至少一个 Stable Diffusion 模型文件、安装 WebUI、启用 API 访问，然后启动
    WebUI。本指南将逐一说明这些步骤。
&lt;/p&gt;</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>
&lt;hr/&gt;
&lt;h2&gt;Installing Stable Diffusion WebUI: Available options&lt;/h2&gt;
&lt;p&gt;
    There are a few different ways you can install the WebUI. The recommended method is to use
    &lt;a href="https://github.com/LykosAI/StabilityMatrix?tab=readme-ov-file#stability-matrix"&gt;Stability Matrix&lt;/a&gt;,
    but other methods are covered here for the sake of completeness.
&lt;/p&gt;
&lt;hr/&gt;
&lt;h2&gt;Option 1: Stability Matrix&lt;/h2&gt;
&lt;p&gt;
    Installation through Stability Matrix is the recommended method. This method is the simplest option, provides a lot
    of helpful extra resources, and supports Windows, macOS and Linux.  This method also lets you switch between the
    original WebUI and the Forge version easily, or even install ComfyUI if you want to try IntraPaint's
    Stable Diffusion ComfyUI image generator.
&lt;/p&gt;</source>
        <translation>
&lt;hr/&gt;
&lt;h2&gt;安装 Stable Diffusion WebUI：可选方法&lt;/h2&gt;
&lt;p&gt;
    安装 WebUI 有几种不同的方法。推荐使用
    &lt;a href="https://github.com/LykosAI/StabilityMatrix?tab=readme-ov-file#stability-matrix"&gt;Stability Matrix&lt;/a&gt;，为完整起见，这里也介绍其他方法。

&lt;/p&gt;
&lt;hr/&gt;
&lt;h2&gt;方法 1：Stability Matrix&lt;/h2&gt;
&lt;p&gt;
    推荐通过 Stability Matrix 安装。这是最简单的方法，提供许多实用的额外资源，并支持
    Windows、macOS 和 Linux。使用这种方法还可以轻松地在原版 WebUI
    和 Forge 版本之间切换；如果想试用 IntraPaint 的
    Stable Diffusion ComfyUI 图像生成器，甚至还可以安装 ComfyUI。
&lt;/p&gt;</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>
    &lt;li&gt;
        On the &lt;img src='{packages_icon}'/&gt;&lt;b&gt;Packages&lt;/b&gt; tab, click the
        &lt;img src='{settings_icon}'/&gt;&lt;b&gt;Settings&lt;/b&gt; button next to the WebUI
        package to open the launch options.  Scroll to the bottom of the list, and find the &lt;b&gt;"Extra Launch Arguments"
        &lt;/b&gt; text field. Enter &lt;b&gt;--api&lt;/b&gt; into that text field, and click the &lt;b&gt;"Save"&lt;/b&gt; button.  This step is
         needed to make the WebUI accept image generation requests from IntraPaint.
        &lt;br/&gt;
    &lt;/li&gt;
</source>
        <translation>
    &lt;li&gt;
        在 &lt;img src='{packages_icon}'/&gt;&lt;b&gt;Packages&lt;/b&gt; 选项卡中，点击 WebUI 软件包旁边的
        &lt;img src='{settings_icon}'/&gt;&lt;b&gt;Settings&lt;/b&gt; 按钮，打开启动选项。滚动到列表底部，找到
        &lt;b&gt;“Extra Launch Arguments”&lt;/b&gt; 文本框。在该文本框中输入 &lt;b&gt;--api&lt;/b&gt;，然后点击
        &lt;b&gt;“Save”&lt;/b&gt; 按钮。只有这样，WebUI 才会接受来自
        IntraPaint 的图像生成请求。
        &lt;br/&gt;
    &lt;/li&gt;
</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>
&lt;hr/&gt;
&lt;h2&gt;Option 2: WebUI Forge one-click installer&lt;/h2&gt;
&lt;p&gt;
    Stable Diffusion WebUI Forge provides a &lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge/releases/download/previous/webui_forge_cu121_torch21_f0017.7z"&gt;
    one-click Windows installation package&lt;/a&gt; you can use to easily install the WebUI. This won't work outside of
    Windows and requires a bit more file management, but it's still a good option if you don't need the extra features
    in Stability Matrix.
&lt;/p&gt;
&lt;ol&gt;
    &lt;li&gt;
        Download the last stable package version &lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge/releases/download/previous/webui_forge_cu121_torch21_f0017.7z"&gt;
        here&lt;/a&gt;. There are several other options linked on the
        &lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge?tab=readme-ov-file#installing-forge"&gt;
        WebUI Forge README&lt;/a&gt; you can try, but newer versions may cause compatibility issues.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Extract the downloaded package into a new folder. If you're not using Windows 11, you may need to install
        &lt;a href="https://www.7-zip.org"&gt;7-Zip&lt;/a&gt; to extract the compressed files.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Within the new WebUI-Forge folder, open the &lt;b&gt;webui\webui-user.bat&lt;/b&gt; file in a text editor. Find the 
        "&lt;b&gt;set COMMANDLINE_ARGS=&lt;/b&gt;" line near the top of the file, and change it to 
        "&lt;b&gt;set COMMANDLINE_ARGS=--api&lt;/b&gt;".  Save and close the file. This step is needed to make the WebUI accept
        image generation requests from IntraPaint.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        If you haven't already found at least one Stable Diffusion model file, do that now. Copy it into the 
        WebUI-Forge folder under &lt;b&gt;webui\models\Stable-diffusion&lt;/b&gt;.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Launch the &lt;b&gt;run.bat&lt;/b&gt; file in the WebUI-Forge folder to start Stable Diffusion.  A terminal window will
        open and print startup information as the WebUI initializes.&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        Once you see &lt;b&gt;"Running on local URL:  http://0.0.0.0:7860"&lt;/b&gt; in the terminal window, Stable Diffusion is
        ready to use.  Back in IntraPaint, click the "Activate" button below to connect to Stable Diffusion. &lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        In the future, the only step you'll need to repeat from this list is launching &lt;b&gt;run.bat&lt;/b&gt; and waiting
        for it to finish starting up. If you do this before launching IntraPaint, it will automatically connect to
        the WebUI-Forge image generator on startup.
    &lt;/li&gt;
&lt;/ol&gt;
&lt;hr/&gt;
&lt;h3&gt;Option 3: Running directly in Python&lt;/h3&gt;
&lt;p&gt;
    This method requires a lot more technical knowledge than the previous ones, but it also provides the most
    flexibility and requires the least amount of storage space.  This is only recommended if you've set up a Python
    virtual environment and debugged Python dependency issues before, or if you're interested in teaching yourself to
    do so.
&lt;/p&gt;
&lt;p&gt;
    Because this option isn't recommended, IntraPaint won't provide a full guide. The
    &lt;a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui?tab=readme-ov-file#automatic-installation-on-windows"&gt;
    Stable Diffusion WebUI installation instructions&lt;/a&gt; should help you get started. If you run into any problems,
    searching the &lt;a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui/issues"&gt;WebUI issues page&lt;/a&gt; will 
    probably help you find a solution.
&lt;/p&gt;
</source>
        <translation>
&lt;hr/&gt;
&lt;h2&gt;方法 2：WebUI Forge 一键安装包&lt;/h2&gt;
&lt;p&gt;
    Stable Diffusion WebUI Forge 提供了一个&lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge/releases/download/previous/webui_forge_cu121_torch21_f0017.7z"&gt;
    Windows 一键安装包&lt;/a&gt;，可以用它轻松安装 WebUI。这种方法只适用于
    Windows，并且需要多做一些文件管理，但如果不需要 Stability Matrix
    的额外功能，它仍是不错的选择。
&lt;/p&gt;
&lt;ol&gt;
    &lt;li&gt;
        下载最后一个稳定版本的&lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge/releases/download/previous/webui_forge_cu121_torch21_f0017.7z"&gt;
        Forge 安装包&lt;/a&gt;。&lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge?tab=readme-ov-file#installing-forge"&gt;
        WebUI Forge README&lt;/a&gt; 中还列出了其他几种可以尝试的选项，但较新的版本可能会导致兼容性问题。
&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        将下载的压缩包解压到一个新文件夹中。如果使用的不是 Windows 11，可能需要先安装
        &lt;a href="https://www.7-zip.org"&gt;7-Zip&lt;/a&gt; 才能解压这些压缩文件。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        在新的 WebUI-Forge 文件夹中，用文本编辑器打开 &lt;b&gt;webui\webui-user.bat&lt;/b&gt; 文件。找到文件开头附近的“&lt;b&gt;set COMMANDLINE_ARGS=&lt;/b&gt;”这一行，将其改为“&lt;b&gt;set COMMANDLINE_ARGS=--api&lt;/b&gt;”。保存并关闭文件。只有这样，WebUI
        才会接受来自 IntraPaint
        的图像生成请求。
&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        如果还没有找到至少一个 Stable Diffusion 模型文件，现在就去找。将它复制到
        WebUI-Forge 文件夹下的 &lt;b&gt;webui\models\Stable-diffusion&lt;/b&gt; 中。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        运行 WebUI-Forge 文件夹中的 &lt;b&gt;run.bat&lt;/b&gt; 文件以启动 Stable Diffusion。终端窗口会打开，并在
        WebUI 初始化时显示启动信息。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        当终端窗口中出现&lt;b&gt;“Running on local URL:  http://0.0.0.0:7860”&lt;/b&gt;时，Stable Diffusion
        就可以使用了。回到 IntraPaint，点击下方的“激活”按钮即可连接到 Stable Diffusion。&lt;br/&gt;
    &lt;/li&gt;
    &lt;li&gt;
        以后，这些步骤中只需重复一步：运行 &lt;b&gt;run.bat&lt;/b&gt;
        并等待它启动完成。如果在启动 IntraPaint 之前完成这一步，IntraPaint 会在启动时自动连接到
        WebUI-Forge 图像生成器。
    &lt;/li&gt;
&lt;/ol&gt;
&lt;hr/&gt;
&lt;h3&gt;方法 3：直接在 Python 中运行&lt;/h3&gt;
&lt;p&gt;
    这种方法比前两种需要多得多的技术知识，但灵活性最高，占用的存储空间也最少。只有在以前搭建过
    Python 虚拟环境并排查过 Python
    依赖问题，或者有兴趣自学这些内容时，才推荐使用这种方法。

&lt;/p&gt;
&lt;p&gt;
    由于不推荐这种方法，IntraPaint 不提供完整指南。
    &lt;a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui?tab=readme-ov-file#automatic-installation-on-windows"&gt;
    Stable Diffusion WebUI 安装说明&lt;/a&gt;可以帮助入门。如果遇到问题，在 &lt;a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui/issues"&gt;WebUI Issues 页面&lt;/a&gt;中搜索，通常能找到解决方法。


&lt;/p&gt;
</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>Updating prompt styles failed</source>
        <translation>更新风格模板失败</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>Failed to load Stable Diffusion settings</source>
        <translation>无法加载 Stable Diffusion 设置</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>Failed to save Stable Diffusion settings</source>
        <translation>无法保存 Stable Diffusion 设置</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>The connection to the Stable Diffusion WebUI image generator was lost. Connected generator settings will not be available.</source>
        <translation>与 Stable Diffusion WebUI 图像生成器的连接已断开。生成器提供的设置将不可用。</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/sd_webui_generator.py"/>
        <source>The connection to the Stable Diffusion WebUI image generator was lost. Any changes to connected generator settings were not saved.</source>
        <translation>与 Stable Diffusion WebUI 图像生成器的连接已断开。对生成器提供的设置所做的更改未能保存。</translation>
    </message>
    <message>
        <source>
&lt;h3&gt;About the Stable Diffusion WebUI&lt;/h3&gt;
&lt;p&gt;
    The &lt;a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui?tab=readme-ov-file#stable-diffusion-web-ui"&gt;
    Stable Diffusion WebUI&lt;/a&gt; is one of the first interfaces created for using Stable Diffusion. When the WebUI is
    running and configured correctly, IntraPaint can access Stable Diffusion image generation by sending requests to
    the WebUI. You can run the WebUI on the same computer as IntraPaint, or remotely on a separate server.
&lt;/p&gt;
&lt;p&gt;
    When connected, IntraPaint provides controls for the WebUI in the &lt;b&gt;Image Generation&lt;/b&gt; tab and in the &lt;b&gt;settings
    window&lt;/b&gt; under the Stable Diffusion category. When running, you can also access the WebUI's own interface
    directly through your web browser at &lt;a href="http://localhost:7860/"&gt;localhost:7860&lt;/a&gt;.
&lt;/p&gt;
&lt;h3&gt;About Stable Diffusion WebUI Forge&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge?tab=readme-ov-file#stable-diffusion-webui-forge"&gt;
    Stable Diffusion WebUI Forge&lt;/a&gt; is a popular variant of the original Stable Diffusion WebUI, that adds significant
    improvements to image generation speed and efficiency. It also adds a large number of experimental features that 
    cause compatibility issues. IntraPaint provides some support for WebUI Forge, but ControlNet will not work with
    recent versions.
&lt;/p&gt;
&lt;h3&gt;About Stable Diffusion WebUI reForge&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://github.com/Panchovix/stable-diffusion-webui-reForge?tab=readme-ov-file#stable-diffusion-webui-forgereforge"&gt;
    Stable Diffusion WebUI re Forge&lt;/a&gt; is a third version of the WebUI that includes the improved performance of
    WebUI Forge without any of the compatibility issues. &lt;b&gt;This is the recommended version to use with IntraPaint&lt;/b&gt;.
&lt;/p&gt;
</source>
        <translation type="vanished">
&lt;h3&gt;关于 Stable Diffusion WebUI&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui?tab=readme-ov-file#stable-diffusion-web-ui"&gt;
    Stable Diffusion WebUI&lt;/a&gt; 是最早用于运行 Stable Diffusion 的界面之一。WebUI
    运行且配置正确时，IntraPaint 可以通过向 WebUI 发送请求来使用 Stable Diffusion 图像生成。WebUI
    可以与 IntraPaint 运行在同一台电脑上，也可以远程运行在另一台服务器上。
&lt;/p&gt;
&lt;p&gt;
    连接后，IntraPaint 会在&lt;b&gt;图像生成&lt;/b&gt;面板和&lt;b&gt;设置窗口&lt;/b&gt;的 Stable Diffusion 类别中提供 WebUI
    的控制选项。WebUI 运行时，也可以直接在网页浏览器中通过 &lt;a href="http://localhost:7860/"&gt;localhost:7860&lt;/a&gt;
    访问 WebUI 自己的界面。
&lt;/p&gt;
&lt;h3&gt;关于 Stable Diffusion WebUI Forge&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge?tab=readme-ov-file#stable-diffusion-webui-forge"&gt;
    Stable Diffusion WebUI Forge&lt;/a&gt; 是原版 Stable Diffusion WebUI
    的一个流行变体，大幅提升了图像生成的速度和效率。它还加入了大量会导致兼容性问题的实验性功能。IntraPaint 对 WebUI
    Forge 提供部分支持，但 ControlNet 无法在较新版本中使用。

&lt;/p&gt;
&lt;h3&gt;关于 Stable Diffusion WebUI reForge&lt;/h3&gt;
&lt;p&gt;
    &lt;a href="https://github.com/Panchovix/stable-diffusion-webui-reForge?tab=readme-ov-file#stable-diffusion-webui-forgereforge"&gt;
    Stable Diffusion WebUI reForge&lt;/a&gt; 是 WebUI 的第三个版本，具备 WebUI
    Forge 的性能改进，同时没有任何兼容性问题。&lt;b&gt;这是推荐与 IntraPaint 搭配使用的版本&lt;/b&gt;。
&lt;/p&gt;
</translation>
    </message>
</context>
<context>
    <name>controller.image_generation.test_generator</name>
    <message>
        <location filename="../../src/controller/image_generation/test_generator.py"/>
        <source>Test/development image generator</source>
        <translation>测试/开发用图像生成器</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/test_generator.py"/>
        <source>Mock image generator, for testing and development</source>
        <translation>模拟图像生成器，用于测试和开发</translation>
    </message>
    <message>
        <location filename="../../src/controller/image_generation/test_generator.py"/>
        <source>No setup required.</source>
        <translation>无需设置。</translation>
    </message>
</context>
<context>
    <name>controller.image_io</name>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Save failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Open failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Saving as "{file_path}" failed due to an unknown error, try saving in a different format or to a different disk.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Saving files with the  "{extension}" extension is not supported, try again with a supported image file format.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Tried to save with no file extension as "{file_path}", add a valid image file extension and try again.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Reload failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Image path "{file_path}" is not a valid image file.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Enter an image path or click "Open Image" first.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Reload without saving</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Open without saving</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Untitled</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Metadata updated</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>On save, current image generation parameters will be stored within the image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Opening layers failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Could not open the following images: {file_list}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Open every frame?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Open all frames</source>
        <translation type="unfinished"></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/controller/image_io.py"/>
        <source>{file_name} has %n frame(s). Opening each one as a layer will use about {size_gb:.1f} GB of memory.

Choose "No" to open only the first frame.</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Save image generation metadata?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>No image metadata is cached, would you like to save image generation parameters to this image?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Update image generation metadata?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Image generation parameters have changed, would you like this image to be saved with the most recent values?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Layers will not be saved</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>To save layer data, images must be saved in .ora format. To save each layer as an animation frame, use one of the following formats: {animation_formats}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Transparency will not be fully saved</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>To preserve transparency, save using one of the following file formats: {alpha_formats}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Image generation metadata will not be saved</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>To preserve image generation metadata, save using one of the following file formats: {metadata_formats}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Some metadata will not be saved</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Saving as {file_format} drops: {dropped}. The .ora format keeps all of it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>comment</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>text entries</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>EXIF tags</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>XMP</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>IPTC</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>{part}: {items}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>This format cannot be opened again</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>IntraPaint can write images in the {file_format} format, but cannot load them. Use another file format if you want to be able to load this image in IntraPaint again.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>This format will change the image size</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>The image is {width_px}x{height_px}, but the {file_format} format saves all images at {saved_width_px}x{saved_height_px} resolution. Use another file format if you want to preserve the original image size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>Color will not be saved</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/controller/image_io.py"/>
        <source>The {file_format} format saves the image without color. Use another format if you want to preserve image colors.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>controller.tool_controller</name>
    <message>
        <location filename="../../src/controller/tool_controller.py"/>
        <source>Failed to load libmypaint brush library files</source>
        <translation>无法加载 libmypaint 画笔库文件</translation>
    </message>
    <message>
        <location filename="../../src/controller/tool_controller.py"/>
        <source>The brush tool will not be available unless this is fixed.</source>
        <translation>在修复此问题之前，画笔工具将不可用。</translation>
    </message>
</context>
<context>
    <name>excepthook</name>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>Bug Detected</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>&lt;big&gt;&lt;b&gt;A programming error has been detected during the execution of this program.&lt;/b&gt;&lt;/big&gt;</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>It probably isn't fatal, but should be reported to the developers nonetheless.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>Report bug...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>Copy traceback...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>

Please remember to include the traceback from the Details expander.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>Quit</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>Traceback Copied</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>The traceback has now been copied to the clipboard.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>Quit (your work can be recovered next launch)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/qtexcepthook.py"/>
        <source>Quit (unsaved changes will be lost)</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>image.animation</name>
    <message>
        <location filename="../../src/image/animation.py"/>
        <source>Frame {frame_number}</source>
        <translation>帧 {frame_number}</translation>
    </message>
</context>
<context>
    <name>image.composite_mode</name>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Normal</source>
        <translation>正常</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Multiply</source>
        <translation>正片叠底</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Screen</source>
        <translation>滤色</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Overlay</source>
        <translation>叠加</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Darken</source>
        <translation>变暗</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Lighten</source>
        <translation>变亮</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Color Dodge</source>
        <translation>颜色减淡</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Color Burn</source>
        <translation>颜色加深</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Hard Light</source>
        <translation>强光</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Soft Light</source>
        <translation>柔光</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Difference</source>
        <translation>差值</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Color</source>
        <translation>颜色</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Luminosity</source>
        <translation>明度</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Hue</source>
        <translation>色相</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Saturation</source>
        <translation>饱和度</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Plus</source>
        <translation>Plus</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Destination In</source>
        <translation>Destination In</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Destination Out</source>
        <translation>Destination Out</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Source Atop</source>
        <translation>Source Atop</translation>
    </message>
    <message>
        <location filename="../../src/image/composite_mode.py"/>
        <source>Destination Atop</source>
        <translation>Destination Atop</translation>
    </message>
</context>
<context>
    <name>image.filter.blur</name>
    <message>
        <location filename="../../src/image/filter/blur.py"/>
        <source>Simple</source>
        <translation>简单</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/blur.py"/>
        <source>Box</source>
        <translatorcomment>glossary: not "Box" - this is the box blur, not the Box scaling algorithm; Photoshop zh calls it 方框模糊.</translatorcomment>
        <translation>方框</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/blur.py"/>
        <source>Gaussian</source>
        <translation>高斯</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/blur.py"/>
        <source>Blur</source>
        <translation>模糊</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/blur.py"/>
        <source>Blur the image</source>
        <translation>模糊图像</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/blur.py"/>
        <source>Blurring mode:</source>
        <translation>模糊模式：</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/blur.py"/>
        <source>Image blurring algorithm</source>
        <translation>图像模糊算法</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/blur.py"/>
        <source>Radius:</source>
        <translation>半径：</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/blur.py"/>
        <source>Pixel blur radius (no effect in simple mode).</source>
        <translation>模糊半径（像素），在“简单”模式下无效。</translation>
    </message>
</context>
<context>
    <name>image.filter.brightness_contrast</name>
    <message>
        <location filename="../../src/image/filter/brightness_contrast.py"/>
        <source>Brightness/contrast</source>
        <translation>亮度/对比度</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/brightness_contrast.py"/>
        <source>Adjust image brightness and contrast.</source>
        <translation>调整图像的亮度和对比度。</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/brightness_contrast.py"/>
        <source>Brightness:</source>
        <translation>亮度：</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/brightness_contrast.py"/>
        <source>Contrast</source>
        <translation>对比度</translation>
    </message>
</context>
<context>
    <name>image.filter.filter</name>
    <message>
        <location filename="../../src/image/filter/filter.py"/>
        <source>Apply image filter</source>
        <translation>应用图像滤镜</translation>
    </message>
</context>
<context>
    <name>image.filter.invert</name>
    <message>
        <location filename="../../src/image/filter/invert.py"/>
        <source>Invert</source>
        <translation>反相</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/invert.py"/>
        <source>Invert image colors</source>
        <translation>反相图像颜色</translation>
    </message>
</context>
<context>
    <name>image.filter.posterize</name>
    <message>
        <location filename="../../src/image/filter/posterize.py"/>
        <source>Posterize</source>
        <translation>色调分离</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/posterize.py"/>
        <source>Reduce color range by reducing image color bit count.</source>
        <translation>通过降低图像的颜色位数来减少颜色范围。</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/posterize.py"/>
        <source>Bit count:</source>
        <translation>位数：</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/posterize.py"/>
        <source>Image color bits to preserve (1-8)</source>
        <translation>要保留的图像颜色位数（1-8）</translation>
    </message>
</context>
<context>
    <name>image.filter.rgb_color_balance</name>
    <message>
        <location filename="../../src/image/filter/rgb_color_balance.py"/>
        <source>RGBA color balance</source>
        <translation>RGBA 色彩平衡</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/rgb_color_balance.py"/>
        <source>Adjust color balance</source>
        <translation>调整色彩平衡</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/rgb_color_balance.py"/>
        <source>Red</source>
        <translation>红色</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/rgb_color_balance.py"/>
        <source>Green</source>
        <translation>绿色</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/rgb_color_balance.py"/>
        <source>Blue</source>
        <translation>蓝色</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/rgb_color_balance.py"/>
        <source>Alpha</source>
        <translation>Alpha</translation>
    </message>
</context>
<context>
    <name>image.filter.saturation</name>
    <message>
        <location filename="../../src/image/filter/saturation.py"/>
        <source>Saturation</source>
        <translation>饱和度</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/saturation.py"/>
        <source>Adjust image color saturation</source>
        <translation>调整图像的色彩饱和度</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/saturation.py"/>
        <source>Saturation multiplier</source>
        <translation>饱和度倍数</translation>
    </message>
</context>
<context>
    <name>image.filter.sharpen</name>
    <message>
        <location filename="../../src/image/filter/sharpen.py"/>
        <source>Sharpen</source>
        <translation>锐化</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/sharpen.py"/>
        <source>Sharpen the image</source>
        <translation>锐化图像</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/sharpen.py"/>
        <source>Factor</source>
        <translation>系数</translation>
    </message>
    <message>
        <location filename="../../src/image/filter/sharpen.py"/>
        <source>Sharpness factor (1.0: no change)</source>
        <translation>锐化系数（1.0：不变）</translation>
    </message>
</context>
<context>
    <name>image.layers.image_layer</name>
    <message>
        <location filename="../../src/image/layers/image_layer.py"/>
        <source>Layer cropping failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_layer.py"/>
        <source>Layer has no image content.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_layer.py"/>
        <source>Layer is already cropped to fit image content.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_layer.py"/>
        <source>No layer content is selected.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_layer.py"/>
        <source>Selection contains the entire layer.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>image.layers.image_stack</name>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>new image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>merge layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>merge visible layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>resize layer to image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>cut/clear selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>fill selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>stroke selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>resize image canvas</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>crop layer to selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Merged</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Paste layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Resizing image canvas failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Image scaling failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Locked layer {layer_name} would be affected, unlock the layer before retrying</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Locked layers {comma_separated_layer_names} would be affected, unlock these layers before retrying.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Crop to selection bounds failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Nothing is selected, select an area in the image first.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>The selection does not cover any part of the layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>The selection does not cut out any part of the layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>All selected layers are either fully covered by the selection or do not intersect with it at all.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Error: tried to change a locked layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Unlock the layer before attempting any changes.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Merging layers failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Only visible layers can be merged.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Flattening layer failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Only visible layers can be flattened.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>The layer below is a layer group, flatten the group into a single image layer first.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Layer "{layer_name}" is in a locked group</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Unlock the layer group before trying to change layers within the group.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Blocked action on main layer group</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>To edit the main layer group, edit its layers individually or use the options under the Image menu.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Warning: cropping deleted layer(s)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>&lt;p&gt;Cropping the image deleted the following layers:&lt;/p&gt;&lt;ul&gt;{layer_names}&lt;/ul&gt;</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Hidden layers will be deleted</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/image_stack.py"/>
        <source>Merging will delete the following hidden layers within groups: {layer_names}. Continue?</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>image.layers.non_destructive_layer</name>
    <message>
        <location filename="../../src/image/layers/non_destructive_layer.py"/>
        <source>Convert layer to image?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/non_destructive_layer.py"/>
        <source>Attempted action: &lt;b&gt;{action_name}&lt;/b&gt;. To complete this action, layer "{layer_name}" must be converted to an image layer, and you will no longer be able to edit its original content. Continue?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/non_destructive_layer.py"/>
        <source>Convert layers to image?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/image/layers/non_destructive_layer.py"/>
        <source>Attempted action: &lt;b&gt;{action_name}&lt;/b&gt;. To complete this action, {num_layers} layers must be converted to image layers, and you will no longer be able to edit their original content. Continue?</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>image.layers.selection_layer</name>
    <message>
        <location filename="../../src/image/layers/selection_layer.py"/>
        <source>Selection</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>tools.base_tool</name>
    <message>
        <location filename="../../src/tools/base_tool.py"/>
        <source>{pan_key}+{left_mouse_icon} or {middle_mouse_icon}, drag: pan view</source>
        <translation>{pan_key}+{left_mouse_icon} 或 {middle_mouse_icon} 拖动：平移视图</translation>
    </message>
    <message>
        <location filename="../../src/tools/base_tool.py"/>
        <source>{middle_mouse_icon}, drag: pan view</source>
        <translation>{middle_mouse_icon} 拖动：平移视图</translation>
    </message>
    <message>
        <location filename="../../src/tools/base_tool.py"/>
        <source>{v_scroll_icon}: zoom</source>
        <translation>{v_scroll_icon}：缩放</translation>
    </message>
    <message>
        <location filename="../../src/tools/base_tool.py"/>
        <source>{modifier_or_modifiers}: Fixed aspect ratio</source>
        <translation>{modifier_or_modifiers}：固定宽高比</translation>
    </message>
</context>
<context>
    <name>tools.brush_tool</name>
    <message>
        <location filename="../../src/tools/brush_tool.py"/>
        <source>{modifier_or_modifiers}+{left_mouse_icon}: draw line</source>
        <translation>{modifier_or_modifiers}+{left_mouse_icon}：绘制直线</translation>
    </message>
    <message>
        <location filename="../../src/tools/brush_tool.py"/>
        <source>{modifier_or_modifiers}: fixed angle</source>
        <translation>{modifier_or_modifiers}：固定角度</translation>
    </message>
    <message>
        <location filename="../../src/tools/brush_tool.py"/>
        <source>{modifier_or_modifiers}+{right_mouse_icon} drag: brush size</source>
        <translation>{modifier_or_modifiers}+{right_mouse_icon} 拖动：画笔大小</translation>
    </message>
    <message>
        <location filename="../../src/tools/brush_tool.py"/>
        <source>{right_mouse_icon}: quick options</source>
        <translation>{right_mouse_icon}：快捷选项</translation>
    </message>
    <message>
        <location filename="../../src/tools/mypaint_brush_tool.py"/>
        <source>Brush</source>
        <translation>画笔</translation>
    </message>
    <message>
        <location filename="../../src/tools/mypaint_brush_tool.py"/>
        <source>Paint into the image</source>
        <translation>在图像上绘画</translation>
    </message>
    <message>
        <location filename="../../src/tools/mypaint_brush_tool.py"/>
        <source>{left_mouse_icon}: draw</source>
        <translation>{left_mouse_icon}：绘制</translation>
    </message>
</context>
<context>
    <name>tools.clone_stamp_tool</name>
    <message>
        <location filename="../../src/tools/clone_stamp_tool.py"/>
        <source>Clone stamp</source>
        <translation>仿制图章</translation>
    </message>
    <message>
        <location filename="../../src/tools/clone_stamp_tool.py"/>
        <source>Copy image content from one area to another</source>
        <translation>将图像内容从一个区域复制到另一个区域</translation>
    </message>
    <message>
        <location filename="../../src/tools/clone_stamp_tool.py"/>
        <source>{right_mouse_icon}: set source - {left_mouse_icon}: draw</source>
        <translation>{right_mouse_icon}：设置源 - {left_mouse_icon}：绘制</translation>
    </message>
    <message>
        <location filename="../../src/tools/clone_stamp_tool.py"/>
        <source>Offset:</source>
        <translation>偏移：</translation>
    </message>
    <message>
        <location filename="../../src/tools/clone_stamp_tool.py"/>
        <source>Position:</source>
        <translation>位置：</translation>
    </message>
    <message>
        <location filename="../../src/tools/clone_stamp_tool.py"/>
        <source>Update selection only</source>
        <translation>仅更新选区</translation>
    </message>
</context>
<context>
    <name>tools.context_pin_dragger</name>
    <message>
        <location filename="../../src/tools/context_pin_dragger.py"/>
        <source>{right_mouse_icon}: add, move or remove context pin</source>
        <translation>{right_mouse_icon}：添加、移动或删除周边范围锚点</translation>
    </message>
</context>
<context>
    <name>tools.draw_tool</name>
    <message>
        <location filename="../../src/tools/draw_tool.py"/>
        <source>Draw</source>
        <translation>绘图</translation>
    </message>
    <message>
        <location filename="../../src/tools/draw_tool.py"/>
        <source>Draw into the image</source>
        <translation>在图像上绘制</translation>
    </message>
    <message>
        <location filename="../../src/tools/draw_tool.py"/>
        <source>{left_mouse_icon}: draw</source>
        <translation>{left_mouse_icon}：绘制</translation>
    </message>
</context>
<context>
    <name>tools.eraser_tool</name>
    <message>
        <location filename="../../src/tools/eraser_tool.py"/>
        <source>Erase</source>
        <translation>橡皮擦</translation>
    </message>
    <message>
        <location filename="../../src/tools/eraser_tool.py"/>
        <source>Erase image layer content</source>
        <translation>擦除图像图层内容</translation>
    </message>
    <message>
        <location filename="../../src/tools/eraser_tool.py"/>
        <source>{left_mouse_icon}: erase</source>
        <translation>{left_mouse_icon}：擦除</translation>
    </message>
</context>
<context>
    <name>tools.eyedropper_tool</name>
    <message>
        <location filename="../../src/tools/eyedropper_tool.py"/>
        <source>Color picker</source>
        <translation>取色器</translation>
    </message>
    <message>
        <location filename="../../src/tools/eyedropper_tool.py"/>
        <source>Select a brush or background color</source>
        <translation>选取画笔颜色或背景色</translation>
    </message>
    <message>
        <location filename="../../src/tools/eyedropper_tool.py"/>
        <source>{left_mouse_icon}: pick color - {right_mouse_icon}: pick background color - </source>
        <translation>{left_mouse_icon}：取色 - {right_mouse_icon}：取背景色 - </translation>
    </message>
</context>
<context>
    <name>tools.fill_tool</name>
    <message>
        <location filename="../../src/tools/fill_tool.py"/>
        <source>Color fill</source>
        <translation>颜色填充</translation>
    </message>
    <message>
        <location filename="../../src/tools/fill_tool.py"/>
        <source>Fill areas with solid colors</source>
        <translation>用纯色填充区域</translation>
    </message>
    <message>
        <location filename="../../src/tools/fill_tool.py"/>
        <source>{left_mouse_icon}: fill</source>
        <translation>{left_mouse_icon}：填充</translation>
    </message>
</context>
<context>
    <name>tools.filter_tool</name>
    <message>
        <location filename="../../src/tools/filter_tool.py"/>
        <source>Filter brush</source>
        <translation>滤镜画笔</translation>
    </message>
    <message>
        <location filename="../../src/tools/filter_tool.py"/>
        <source>Draw to apply an image filter</source>
        <translation>绘制以应用图像滤镜</translation>
    </message>
    <message>
        <location filename="../../src/tools/filter_tool.py"/>
        <source>{left_mouse_icon}: filter</source>
        <translation>{left_mouse_icon}：应用滤镜</translation>
    </message>
</context>
<context>
    <name>tools.generation_area_tool</name>
    <message>
        <location filename="../../src/tools/generation_area_tool.py"/>
        <source>Generation area</source>
        <translation>生成区域</translation>
    </message>
    <message>
        <location filename="../../src/tools/generation_area_tool.py"/>
        <source>Select an image region for AI image generation</source>
        <translation>选择用于 AI 图像生成的图像区域</translation>
    </message>
    <message>
        <location filename="../../src/tools/generation_area_tool.py"/>
        <source>{left_mouse_icon}: move area - {right_mouse_icon}: resize area</source>
        <translation>{left_mouse_icon}：移动区域 - {right_mouse_icon}：调整区域大小</translation>
    </message>
    <message>
        <location filename="../../src/tools/generation_area_tool.py"/>
        <source>{left_mouse_icon}: move area, or drag a handle to resize - {right_mouse_icon}: resize area</source>
        <translation>{left_mouse_icon}：移动区域，或拖动控制点调整大小 - {right_mouse_icon}：调整区域大小</translation>
    </message>
    <message>
        <location filename="../../src/tools/generation_area_tool.py"/>
        <source>{modifier_or_modifiers}: free aspect ratio on corner handles, fixed aspect ratio with {right_mouse_icon}</source>
        <translation>{modifier_or_modifiers}：拖动角控制点时不固定宽高比，用 {right_mouse_icon} 调整时固定宽高比</translation>
    </message>
</context>
<context>
    <name>tools.lasso_selection_tool</name>
    <message>
        <location filename="../../src/tools/free_selection_tool.py"/>
        <source>Free selection</source>
        <translation>自由选区</translation>
    </message>
    <message>
        <location filename="../../src/tools/free_selection_tool.py"/>
        <source>Select or deselect polygonal areas</source>
        <translation>选择或取消选择多边形区域</translation>
    </message>
    <message>
        <location filename="../../src/tools/free_selection_tool.py"/>
        <source>{left_mouse_icon}: add or move point&lt;br/&gt;{enter_key} or {left_mouse_icon}+first point: finish selection&lt;br/&gt;{escape_key}: cancel selection</source>
        <translation>{left_mouse_icon}：添加或移动点&lt;br/&gt;{enter_key} 或 {left_mouse_icon}+第一个点：完成选区&lt;br/&gt;{escape_key}：取消选区</translation>
    </message>
</context>
<context>
    <name>tools.layer_transform_tool</name>
    <message>
        <location filename="../../src/tools/layer_transform_tool.py"/>
        <source>Transform layers</source>
        <translation>变换图层</translation>
    </message>
    <message>
        <location filename="../../src/tools/layer_transform_tool.py"/>
        <source>Move, scale, or rotate the active layer.</source>
        <translation>移动、缩放或旋转当前图层。</translation>
    </message>
    <message>
        <location filename="../../src/tools/layer_transform_tool.py"/>
        <source>{left_mouse_icon}: select layer&lt;br/&gt;{left_mouse_icon}, drag: move layer&lt;br/&gt;{right_mouse_icon}: choose from layers under cursor</source>
        <translation>{left_mouse_icon}：选择图层&lt;br/&gt;{left_mouse_icon} 拖动：移动图层&lt;br/&gt;{right_mouse_icon}：从光标下的图层中选择</translation>
    </message>
</context>
<context>
    <name>tools.magic_wand_tool</name>
    <message>
        <location filename="../../src/tools/magic_wand_tool.py"/>
        <source>Magic wand</source>
        <translation>魔棒</translation>
    </message>
    <message>
        <location filename="../../src/tools/magic_wand_tool.py"/>
        <source>Select areas of similar color</source>
        <translation>选择颜色相近的区域</translation>
    </message>
    <message>
        <location filename="../../src/tools/magic_wand_tool.py"/>
        <source>{left_mouse_icon}: select</source>
        <translation>{left_mouse_icon}：选择</translation>
    </message>
</context>
<context>
    <name>tools.selection_tool</name>
    <message>
        <location filename="../../src/tools/selection_brush_tool.py"/>
        <source>Selection brush</source>
        <translation>选区画笔</translation>
    </message>
    <message>
        <location filename="../../src/tools/selection_brush_tool.py"/>
        <source>Draw to select areas for editing or inpainting.</source>
        <translation>绘制以选择要编辑或局部重绘的区域。</translation>
    </message>
    <message>
        <location filename="../../src/tools/selection_brush_tool.py"/>
        <source>{left_mouse_icon}: select</source>
        <translation>{left_mouse_icon}：选择</translation>
    </message>
</context>
<context>
    <name>tools.shape_selection_tool</name>
    <message>
        <location filename="../../src/tools/shape_selection_tool.py"/>
        <source>Rectangle/Ellipse selection</source>
        <translation>矩形/椭圆选区</translation>
    </message>
    <message>
        <location filename="../../src/tools/shape_selection_tool.py"/>
        <source>Select or deselect rectangles or ellipses</source>
        <translation>选择或取消选择矩形或椭圆区域</translation>
    </message>
    <message>
        <location filename="../../src/tools/shape_selection_tool.py"/>
        <source>{left_mouse_icon}, drag: select</source>
        <translation>{left_mouse_icon} 拖动：选择</translation>
    </message>
</context>
<context>
    <name>tools.shape_tool</name>
    <message>
        <location filename="../../src/tools/shape_tool.py"/>
        <source>Draw shapes</source>
        <translation>绘制形状</translation>
    </message>
    <message>
        <location filename="../../src/tools/shape_tool.py"/>
        <source>Create rectangles, ellipses, and other polygons</source>
        <translation>创建矩形、椭圆和其他多边形</translation>
    </message>
    <message>
        <location filename="../../src/tools/shape_tool.py"/>
        <source>{left_mouse_icon}, drag: draw shape</source>
        <translation>{left_mouse_icon} 拖动：绘制形状</translation>
    </message>
</context>
<context>
    <name>tools.smudge_tool</name>
    <message>
        <location filename="../../src/tools/smudge_tool.py"/>
        <source>Smudge</source>
        <translation>涂抹</translation>
    </message>
    <message>
        <location filename="../../src/tools/smudge_tool.py"/>
        <source>Smudge image content</source>
        <translation>涂抹图像内容</translation>
    </message>
    <message>
        <location filename="../../src/tools/smudge_tool.py"/>
        <source>{left_mouse_icon}: smudge</source>
        <translation>{left_mouse_icon}：涂抹</translation>
    </message>
</context>
<context>
    <name>tools.text_tool</name>
    <message>
        <location filename="../../src/tools/text_tool.py"/>
        <source>Text</source>
        <translation>文字</translation>
    </message>
    <message>
        <location filename="../../src/tools/text_tool.py"/>
        <source>Add text to a text layer</source>
        <translation>向文字图层添加文字</translation>
    </message>
    <message>
        <location filename="../../src/tools/text_tool.py"/>
        <source>{left_mouse_icon}: select text layer&lt;br/&gt;{left_mouse_icon}, drag: create new layer or move active</source>
        <translation>{left_mouse_icon}：选择文字图层&lt;br/&gt;{left_mouse_icon} 拖动：创建新图层或移动当前图层</translation>
    </message>
</context>
<context>
    <name>ui.generated_image_selector</name>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>{ready} of {total} ready</source>
        <translation>已就绪 {ready}/{total}</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>{ready} of {total} ready - {progress}</source>
        <translation>已就绪 {ready}/{total} - {progress}</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Only inpainted options have a selection.</source>
        <translation>只有局部重绘的选项才有选区。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Original image content</source>
        <translation>原始图像内容</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Current image content</source>
        <translation>当前图像内容</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Option {index}</source>
        <translation>选项 {index}</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Select this option</source>
        <translation>选择此选项</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Save to new file</source>
        <translation>保存为新文件</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Send to new layer</source>
        <translation>发送到新图层</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Saved image option to {image_path}</source>
        <translation>已将图像选项保存到“{image_path}”</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Created new layer "{layer_name}"</source>
        <translation>已创建新图层“{layer_name}”</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Cancelled saving image option to file.</source>
        <translation>已取消将图像选项保存到文件。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Failed to insert into layer "{layer_name}"</source>
        <translation>无法插入到图层“{layer_name}”中</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Changes were blocked because the layer is locked. </source>
        <translation>更改被阻止，因为该图层已锁定。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Changes were blocked because the layer is hidden. </source>
        <translation>更改被阻止，因为该图层已隐藏。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>The active layer is not an image layer, image content cannot be inserted. </source>
        <translation>当前图层不是图像图层，无法插入图像内容。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>The layer or a group around it uses a blend mode, opacity or isolation that would change how the result looks. </source>
        <translation>该图层或其所在的组使用了会改变结果外观的混合模式、不透明度或隔离设置。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>A layer above it draws over the edited area, which would show the result twice. </source>
        <translation>其上方的图层覆盖了编辑区域，结果会显示两次。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>Image content was added as new layer "{new_layer_name}" at the top of the layer stack</source>
        <translation>图像内容已作为新图层“{new_layer_name}”添加到图层堆栈顶部。</translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/generated_image_selector.py"/>
        <source>{mode}, {width} x {height}, %n option(s)</source>
        <translation><numerusform>{mode}，{width} x {height}，%n 个选项</numerusform></translation>
    </message>
</context>
<context>
    <name>ui.generated_option_view</name>
    <message>
        <location filename="../../src/ui/generated_option_view.py"/>
        <source>Original</source>
        <translation>原图</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_option_view.py"/>
        <source>Current</source>
        <translation>当前</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_option_view.py"/>
        <source>{label} of {count}</source>
        <translation>{label}（共 {count} 个）</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_option_view.py"/>
        <source>Hold {key} to compare</source>
        <translation>按住 {key} 对比</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_option_view.py"/>
        <source>Click to use</source>
        <translation>点击使用</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_option_view.py"/>
        <source>Generating</source>
        <translation>正在生成</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_option_view.py"/>
        <source>Waiting</source>
        <translation>等待中</translation>
    </message>
</context>
<context>
    <name>ui.generated_selector_bars</name>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Choose a result</source>
        <translation>选择结果</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Grid</source>
        <translation>网格</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Single</source>
        <translation>单张</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Show every option</source>
        <translation>显示所有选项</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Show the focused option up close</source>
        <translation>放大显示当前选项</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>View</source>
        <translation>视图</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Show selection, zoom to changes and full resolution</source>
        <translation>显示选区、缩放到更改区域和全分辨率</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Zoom to changes</source>
        <translation>缩放到更改区域</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Show selection</source>
        <translation>显示选区</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Full resolution</source>
        <translation>全分辨率</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Cancel</source>
        <translation>取消</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Stop generating and return to the editor.</source>
        <translation>停止生成并返回编辑器。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Close</source>
        <translation>关闭</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Close without choosing. These options stay available to re-open.</source>
        <translation>不做选择直接关闭。这些选项之后仍可重新打开。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Stop</source>
        <translation>停止</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Stop generating and keep the finished options.</source>
        <translation>停止生成，保留已完成的选项。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Stopping...</source>
        <translation>正在停止...</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>‹ Previous</source>
        <translation>‹ 上一个</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Next ›</source>
        <translation>下一个 ›</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Previous option</source>
        <translation>上一个选项</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Next option</source>
        <translation>下一个选项</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Send to new layer</source>
        <translation>发送到新图层</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Save to file...</source>
        <translation>保存到文件...</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>More</source>
        <translation>更多</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Use option {index}</source>
        <translation>使用选项 {index}</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Keep original</source>
        <translation>保留原图</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Keep current</source>
        <translation>保留当前图像</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Use original</source>
        <translation>使用原图</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Apply the focused option and return to the editor.</source>
        <translation>应用当前选项并返回编辑器。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>This option is still generating.</source>
        <translation>此选项仍在生成中。</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>Controls</source>
        <translation>控制提示</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>{keys} browse</source>
        <translation>{keys} 浏览</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>{first_key}-{last_key} open option</source>
        <translation>{first_key}-{last_key} 打开选项</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>{keys} single view</source>
        <translation>{keys} 单张视图</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>{keys} zoom</source>
        <translation>{keys} 缩放</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>{keys} hold: original</source>
        <translation>{keys} 按住查看原图</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>{keys} back to grid</source>
        <translation>{keys} 返回网格</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>{pan_key}+{left_mouse_icon} or {middle_mouse_icon} pan</source>
        <translation>{pan_key}+{left_mouse_icon} 或 {middle_mouse_icon} 平移</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>{middle_mouse_icon} pan</source>
        <translation>{middle_mouse_icon} 平移</translation>
    </message>
    <message>
        <location filename="../../src/ui/generated_selector_bars.py"/>
        <source>{v_scroll_icon} zoom</source>
        <translation>{v_scroll_icon} 缩放</translation>
    </message>
</context>
<context>
    <name>ui.graphics_items.manual_resolution_label</name>
    <message>
        <location filename="../../src/ui/graphics_items/manual_resolution_label.py"/>
        <source>Manual resolution: {width} x {height}</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.input_fields.fill_style_combo_box</name>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Solid</source>
        <translation>实心</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>None</source>
        <translation>无</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Dithered, 94%</source>
        <translation>抖动，94%</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Dithered, 88%</source>
        <translation>抖动，88%</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Dithered, 62%</source>
        <translation>抖动，62%</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Dithered, 50%</source>
        <translation>抖动，50%</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Dithered, 38%</source>
        <translation>抖动，38%</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Dithered, 12%</source>
        <translation>抖动，12%</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Dithered, 6%</source>
        <translation>抖动，6%</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Diagonal lines 1</source>
        <translation>斜线 1</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Diagonal lines 2</source>
        <translation>斜线 2</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Horizontal lines</source>
        <translation>水平线</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Vertical lines</source>
        <translation>垂直线</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Crossed lines</source>
        <translation>交叉线</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/fill_style_combo_box.py"/>
        <source>Diagonal crossed lines</source>
        <translation>斜交叉线</translation>
    </message>
</context>
<context>
    <name>ui.input_fields.geometry_block</name>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>X</source>
        <translation>X</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Y</source>
        <translation>Y</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>W</source>
        <translation>宽度</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>H</source>
        <translation>高度</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Scale X</source>
        <translation>缩放 X</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Scale Y</source>
        <translation>缩放 Y</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Angle</source>
        <translation>角度</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Horizontal position</source>
        <translation>水平位置</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Vertical position</source>
        <translation>垂直位置</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Width</source>
        <translation>宽度</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Height</source>
        <translation>高度</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Horizontal scale</source>
        <translation>水平缩放</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Vertical scale</source>
        <translation>垂直缩放</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Rotation angle</source>
        <translation>旋转角度</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Lock the width:height ratio</source>
        <translation>锁定宽高比</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>Lock the width:height ratio ({modifier} locks it temporarily)</source>
        <translation>锁定宽高比（按住 {modifier} 可临时锁定）</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source> px</source>
        <translation> px</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source> deg</source>
        <translation> deg</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>x</source>
        <translation>x</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/geometry_block.py"/>
        <source>%</source>
        <translation>%</translation>
    </message>
</context>
<context>
    <name>ui.input_fields.number_field</name>
    <message>
        <location filename="../../src/ui/input_fields/number_field.py"/>
        <source>Pen pressure changes this value</source>
        <translation>笔压会改变此值</translation>
    </message>
</context>
<context>
    <name>ui.input_fields.pen_join_style_combo_box</name>
    <message>
        <location filename="../../src/ui/input_fields/pen_join_style_combo_box.py"/>
        <source>Round</source>
        <translation>圆角</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/pen_join_style_combo_box.py"/>
        <source>Bevel</source>
        <translation>倒角</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/pen_join_style_combo_box.py"/>
        <source>Miter</source>
        <translation>斜接</translation>
    </message>
</context>
<context>
    <name>ui.input_fields.pen_style_combo_box</name>
    <message>
        <location filename="../../src/ui/input_fields/pen_style_combo_box.py"/>
        <source>Solid</source>
        <translation>实线</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/pen_style_combo_box.py"/>
        <source>Dash</source>
        <translation>虚线</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/pen_style_combo_box.py"/>
        <source>Dotted</source>
        <translation>点线</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/pen_style_combo_box.py"/>
        <source>Dash-dot</source>
        <translation>点划线</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/pen_style_combo_box.py"/>
        <source>Dash-dot-dot</source>
        <translation>双点划线</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/pen_style_combo_box.py"/>
        <source>Custom pattern</source>
        <translation>自定义样式</translation>
    </message>
</context>
<context>
    <name>ui.input_fields.pressure_curve_input</name>
    <message>
        <location filename="../../src/ui/input_fields/pressure_curve_input.py"/>
        <source>Input: {input_fraction}, Output: {output_fraction}</source>
        <translation>输入：{input_fraction}，输出：{output_fraction}</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/pressure_curve_input.py"/>
        <source>Reset</source>
        <translation>重置</translation>
    </message>
</context>
<context>
    <name>ui.input_fields.seed_value_spinbox</name>
    <message>
        <location filename="../../src/ui/input_fields/seed_value_spinbox.py"/>
        <source>Reuse last seed value</source>
        <translation>重用上次的随机种子</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/seed_value_spinbox.py"/>
        <source>Use a random seed</source>
        <translation>使用随机种子</translation>
    </message>
</context>
<context>
    <name>ui.input_fields.selection_mode_bar</name>
    <message>
        <location filename="../../src/ui/input_fields/selection_mode_bar.py"/>
        <source>Replace</source>
        <translation>替换</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/selection_mode_bar.py"/>
        <source>Add</source>
        <translation>添加</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/selection_mode_bar.py"/>
        <source>Subtract</source>
        <translation>减去</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/selection_mode_bar.py"/>
        <source>Intersect</source>
        <translation>相交</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/selection_mode_bar.py"/>
        <source>Discard the selection, and select only new areas</source>
        <translation>放弃当前选区，只选择新区域</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/selection_mode_bar.py"/>
        <source>Add new areas to the selection</source>
        <translation>将新区域添加到选区</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/selection_mode_bar.py"/>
        <source>Remove new areas from the selection</source>
        <translation>从选区中减去新区域</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/selection_mode_bar.py"/>
        <source>Keep only the part of the selection inside new areas</source>
        <translation>只保留选区中位于新区域内的部分</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/selection_mode_bar.py"/>
        <source>{description} (hold {keys})</source>
        <translation>{description}（按住 {keys}）</translation>
    </message>
</context>
<context>
    <name>ui.input_fields.setting_fields</name>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Theme default</source>
        <translation>主题默认</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Use the theme's color</source>
        <translation>使用主题的颜色</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Choose a color</source>
        <translation>选择颜色</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Browse...</source>
        <translation>浏览...</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Choose a directory</source>
        <translation>选择目录</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Width</source>
        <translation>宽度</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Height</source>
        <translation>高度</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Unbound</source>
        <translation>未绑定</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Click, then press the key or key combination to bind</source>
        <translation>点击后，按下要绑定的键或组合键</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Key binding</source>
        <translation>快捷键</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>Bind an additional key</source>
        <translation>再绑定一个按键</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>"{key}" is already bound to this action</source>
        <translation>“{key}”已绑定到此操作</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/setting_fields.py"/>
        <source>That key can't be bound. Accent (dead) keys and some special keys aren't supported.</source>
        <translation>无法绑定该键。不支持重音键（死键）和部分特殊键。</translation>
    </message>
</context>
<context>
    <name>ui.input_fields.size_field</name>
    <message>
        <location filename="../../src/ui/input_fields/size_field.py"/>
        <source>W:</source>
        <translation>宽度：</translation>
    </message>
    <message>
        <location filename="../../src/ui/input_fields/size_field.py"/>
        <source>H:</source>
        <translation>高度：</translation>
    </message>
</context>
<context>
    <name>ui.metadata_mode</name>
    <message>
        <location filename="../../src/ui/metadata_mode.py"/>
        <source>Opening the image failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/metadata_mode.py"/>
        <source>--print needs an image: IntraPaint.py --metadata &lt;image&gt; --print</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/metadata_mode.py"/>
        <source>{file_name} has no metadata.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.animation_save_modal</name>
    <message>
        <location filename="../../src/ui/modal/animation_save_modal.py"/>
        <source>Save animation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/animation_save_modal.py"/>
        <source>Each top-level layer is saved as one frame, with the bottom layer first. A frame lasts as long as the "(120ms)" tag at the end of its layer name says.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.color_dialog</name>
    <message>
        <location filename="../../src/ui/modal/color_dialog.py"/>
        <source>Select Color</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.dialog_footer</name>
    <message>
        <location filename="../../src/ui/modal/dialog_footer.py"/>
        <source>Cancel</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.image_filter_modal</name>
    <message>
        <location filename="../../src/ui/modal/image_filter_modal.py"/>
        <source>Change selected areas only</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_filter_modal.py"/>
        <source>Change active layer only</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_filter_modal.py"/>
        <source>Scope</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_filter_modal.py"/>
        <source>Apply {filter_name}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_filter_modal.py"/>
        <source>Hold to compare</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_filter_modal.py"/>
        <source>Hold to show the original image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_filter_modal.py"/>
        <source>Hold to show the original image. Holding {key} does the same.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.image_scale_modal</name>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Scale image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Basic</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Scale with a basic image scaling algorithm.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Generator</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Scale with one of the image generator's scaling modes.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>AI upscaling</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Upscale with Stable Diffusion, adding detail while scaling.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Scaling algorithm:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Upscale method:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Assisting upscale method:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Size</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>AI upscaling settings</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Pixels</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Enter the new size in pixels.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Percent</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Enter the new size as a percentage of the current size.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>New size: {width} x {height} px, {memory} per layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Tile ControlNet model:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>An optional ControlNet Tile model for stabilizing Stable Diffusion upscaling.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/image_scale_modal.py"/>
        <source>Tile ControlNet preprocessor:</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.layout_name_modal</name>
    <message>
        <location filename="../../src/ui/modal/layout_name_modal.py"/>
        <source>Save panel layout</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/layout_name_modal.py"/>
        <source>Rename panel layout</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/layout_name_modal.py"/>
        <source>Layout name:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/layout_name_modal.py"/>
        <source>Save layout</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/layout_name_modal.py"/>
        <source>Enter a name for the layout.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/layout_name_modal.py"/>
        <source>Replace layout?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/layout_name_modal.py"/>
        <source>A layout named "{layout_name}" already exists. Replace it?</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.login_modal</name>
    <message>
        <location filename="../../src/ui/modal/login_modal.py"/>
        <source>Enter image generation server credentials:</source>
        <translation>输入图像生成服务器的登录凭据：</translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/login_modal.py"/>
        <source>Username:</source>
        <translation>用户名：</translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/login_modal.py"/>
        <source>Password:</source>
        <translation>密码：</translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/login_modal.py"/>
        <source>Log in</source>
        <translation>登录</translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/login_modal.py"/>
        <source>Username and password cannot be empty.</source>
        <translation>用户名和密码不能为空。</translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/login_modal.py"/>
        <source>Unknown error, try again.</source>
        <translation>未知错误，请重试。</translation>
    </message>
</context>
<context>
    <name>ui.modal.manage_layouts_modal</name>
    <message>
        <location filename="../../src/ui/modal/manage_layouts_modal.py"/>
        <source>Manage panel layouts</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/manage_layouts_modal.py"/>
        <source>Apply layout</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/manage_layouts_modal.py"/>
        <source>Rename</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/manage_layouts_modal.py"/>
        <source>Delete</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/manage_layouts_modal.py"/>
        <source>Close</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/manage_layouts_modal.py"/>
        <source>Delete layout?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/manage_layouts_modal.py"/>
        <source>Delete the layout "{layout_name}"?</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.modal_utils</name>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Open Image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Open Images as Layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Save Image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Open failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Images and IntraPaint projects</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Images</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Don't show this again</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Remember my choice</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Restore unsaved work?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>IntraPaint closed without quitting normally while editing "{file_path}". A recovery copy was saved at {saved_time}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>IntraPaint closed without quitting normally while editing an image that was never saved. A recovery copy was saved at {saved_time}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Restore opens the copy. Discard deletes it. Later keeps it and asks again the next time IntraPaint starts.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Restore</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Discard</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Later</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Save changes to "{file_name}"?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Changes you haven't saved will be lost.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/modal_utils.py"/>
        <source>Save</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.new_image_modal</name>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Create new image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Create</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Size</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>{width} x {height} px, {memory} per layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Size presets</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Background</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Default image size ({width} x {height})</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Use the default image size from the application settings.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Generation resolution ({width} x {height})</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Use the size that images are generated at.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Generation area ({width} x {height})</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Use the size of the current image generation area.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Clipboard image ({width} x {height})</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Use the size of the image on the clipboard.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Transparent</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>White</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Black</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Background color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/new_image_modal.py"/>
        <source>Custom color...</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.resize_canvas_modal</name>
    <message>
        <location filename="../../src/ui/modal/resize_canvas_modal.py"/>
        <source>Resize image canvas</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/resize_canvas_modal.py"/>
        <source>Size and position</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/resize_canvas_modal.py"/>
        <source>Layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/resize_canvas_modal.py"/>
        <source>Drag the preview to move the image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/resize_canvas_modal.py"/>
        <source>X-offset</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/resize_canvas_modal.py"/>
        <source>Y-offset</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/resize_canvas_modal.py"/>
        <source>Horizontal offset of the image within the resized canvas</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/resize_canvas_modal.py"/>
        <source>Vertical offset of the image within the resized canvas</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/resize_canvas_modal.py"/>
        <source>New size: {width} x {height} px ({width_change} x {height_change})
{memory} per layer</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.save_loss_modal</name>
    <message>
        <location filename="../../src/ui/modal/save_loss_modal.py"/>
        <source>Save will lose data</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/save_loss_modal.py"/>
        <source>Saving in this format will lose the following:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/save_loss_modal.py"/>
        <source>Don't warn about this again</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/save_loss_modal.py"/>
        <source>Save as .ora</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/save_loss_modal.py"/>
        <source>Save anyway</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/save_loss_modal.py"/>
        <source>Cancel</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/save_loss_modal.py"/>
        <source>Details</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.settings_controls</name>
    <message>
        <location filename="../../src/ui/modal/settings_controls.py"/>
        <source>Ask</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_controls.py"/>
        <source>Always</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_controls.py"/>
        <source>Never</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_controls.py"/>
        <source>Minimal move</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_controls.py"/>
        <source>Center</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_controls.py"/>
        <source>Off</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.settings_modal</name>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Settings</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Settings file locations</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>IntraPaint saves its settings to these files. This section is only for reference, their locations cannot be changed here.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Save</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Search settings</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>No settings match the search.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Restore defaults</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Set every setting in this section back to its default value. Nothing changes until you click Save.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Open folder</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Show the folder containing this file</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Reset to default: {default}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Reset {setting} to default</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Enabled</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>Disabled</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/settings_modal.py"/>
        <source>(empty)</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.modal.stroke_selection_modal</name>
    <message>
        <location filename="../../src/ui/modal/stroke_selection_modal.py"/>
        <source>Stroke selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/stroke_selection_modal.py"/>
        <source>Color:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/stroke_selection_modal.py"/>
        <source>Select color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/stroke_selection_modal.py"/>
        <source>Select the color of the line</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/stroke_selection_modal.py"/>
        <source>Inside</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/stroke_selection_modal.py"/>
        <source>Centered</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/stroke_selection_modal.py"/>
        <source>Outside</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/stroke_selection_modal.py"/>
        <source>Draw the line inside the selection edge.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/stroke_selection_modal.py"/>
        <source>Center the line on the selection edge.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/modal/stroke_selection_modal.py"/>
        <source>Draw the line outside the selection edge.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.color_panel</name>
    <message>
        <location filename="../../src/ui/panel/color_panel.py"/>
        <source>Wheel</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/color_panel.py"/>
        <source>Sliders</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/color_panel.py"/>
        <source>Recent</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/color_panel.py"/>
        <source>Saved</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/color_panel.py"/>
        <source>H {hue}, S {saturation}%, V {value}%</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.controlnet_panel</name>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>ControlNet</source>
        <translation>ControlNet</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>WebUI</source>
        <translation>WebUI</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>ComfyUI</source>
        <translation>ComfyUI</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Reset this unit to its default settings</source>
        <translation>将此控制单元重置为默认设置</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>{unit_number} {control_type}</source>
        <comment>ControlNet unit tab title</comment>
        <translation>{unit_number} {control_type}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Unit {unit_number}: on</source>
        <translation>控制单元 {unit_number}：已启用</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Unit {unit_number}: off</source>
        <translation>控制单元 {unit_number}：未启用</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Unit {unit_number}: on, skipped outside Inpaint mode</source>
        <translation>控制单元 {unit_number}：已启用，非局部重绘模式下跳过</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Skipped outside Inpaint mode</source>
        <translation>非局部重绘模式下跳过</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>This preprocessor needs the inpainting mask, so requests skip the unit in other edit modes</source>
        <translation>此预处理器需要局部重绘蒙版，因此在其他编辑模式下，请求会跳过此控制单元</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Enabled</source>
        <translation>启用</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Apply this ControlNet unit when generating images</source>
        <translation>生成图像时应用此控制单元</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Edit settings</source>
        <translation>编辑设置</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Hide settings</source>
        <translation>隐藏设置</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Change the unit's settings without turning it on</source>
        <translation>修改此控制单元的设置，但不启用它</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Unit</source>
        <translation>控制单元</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Control image</source>
        <translation>控制图像</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Preprocessor</source>
        <translation>预处理器</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Strength</source>
        <translation>强度</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Preview</source>
        <comment>Preprocessor preview section title</comment>
        <translation>预览</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Generation area</source>
        <translation>生成区域</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Image file</source>
        <translation>图像文件</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Use the generation area's content as the control image</source>
        <translation>使用生成区域的内容作为控制图像</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Use an image file as the control image</source>
        <translation>使用图像文件作为控制图像</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Image file path</source>
        <translation>图像文件路径</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>...</source>
        <comment>Button that opens a file picker</comment>
        <translation>...</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Choose a control image file</source>
        <translation>选择控制图像文件</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Type</source>
        <translation>类型</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Model</source>
        <translation>模型</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Preview</source>
        <translation>预览</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Show what the preprocessor makes of the control image</source>
        <translation>显示预处理器对控制图像的处理结果</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Low VRAM</source>
        <translation>低显存</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Pixel perfect</source>
        <translation>完美像素</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Weight</source>
        <translation>权重</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Start</source>
        <translation>开始</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>End</source>
        <translation>结束</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>generation area</source>
        <comment>Control image section summary</comment>
        <translation>生成区域</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>no image</source>
        <comment>Control image section summary</comment>
        <translation>无图像</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>{preprocessor}, {model}</source>
        <comment>Preprocessor section summary</comment>
        <translation>{preprocessor}，{model}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>weight {weight}, steps {start}-{end}</source>
        <comment>Strength section summary</comment>
        <translatorcomment>glossary: not "Steps" - the start and end values are fractions of the sampling steps, so they take the glossary's 时机 for the control step range, not 采样步数.</translatorcomment>
        <translation>权重 {weight}，时机 {start}-{end}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>{control_type} · {preprocessor}</source>
        <comment>First line of a disabled unit's summary</comment>
        <translation>{control_type} · {preprocessor}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Weight {weight}, steps {start}-{end}</source>
        <comment>A disabled unit's summary</comment>
        <translatorcomment>glossary: not "Steps" - the start and end values are fractions of the sampling steps, so they take the glossary's 时机 for the control step range, not 采样步数.</translatorcomment>
        <translation>权重 {weight}，时机 {start}-{end}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Image file: {file_name}</source>
        <comment>A disabled unit's summary</comment>
        <translation>图像文件：{file_name}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Control image: generation area</source>
        <comment>A disabled unit's summary</comment>
        <translation>控制图像：生成区域</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Control weight:</source>
        <translation>控制强度：</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Starting control step:</source>
        <translation>控制介入时机：</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>Ending control step:</source>
        <translation>控制结束时机：</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>A multiplier that controls how strongly the ControlNet unit will affect image generation.</source>
        <translation>一个倍数，控制此控制单元对图像生成的影响强度。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>The step in the image generation process where the ControlNet unit will be enabled, as a fraction of the total step count.</source>
        <translation>图像生成过程中启用此控制单元的时机，以占总采样步数的比例表示。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/controlnet_panel.py"/>
        <source>The step in the image generation process where the ControlNet unit will be disabled, as a fraction of the total step count.</source>
        <translation>图像生成过程中停用此控制单元的时机，以占总采样步数的比例表示。</translation>
    </message>
</context>
<context>
    <name>ui.panel.generators.comfyui_advanced_controls</name>
    <message>
        <location filename="../../src/ui/panel/generators/comfyui_advanced_controls.py"/>
        <source>Model loading</source>
        <translation>模型加载</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/comfyui_advanced_controls.py"/>
        <source>Encoding</source>
        <translation>编码</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/comfyui_advanced_controls.py"/>
        <source>Tiled VAE encoding</source>
        <translation>分块 VAE 编码</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/comfyui_advanced_controls.py"/>
        <source>{config} config</source>
        <translation>{config} 配置</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/comfyui_advanced_controls.py"/>
        <source>inpainting model</source>
        <translation>局部重绘模型</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/comfyui_advanced_controls.py"/>
        <source>tiled VAE {size}</source>
        <translation>分块 VAE {size}</translation>
    </message>
</context>
<context>
    <name>ui.panel.generators.glid_panel</name>
    <message>
        <location filename="../../src/ui/panel/generators/glid_panel.py"/>
        <source>Image generation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/glid_panel.py"/>
        <source>GLID-3-XL</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/glid_panel.py"/>
        <source>Prompt</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/glid_panel.py"/>
        <source>Sampling</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/glid_panel.py"/>
        <source>Scaling</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/glid_panel.py"/>
        <source>Negative prompt</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.generators.sd_webui_panel</name>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Image generation</source>
        <translation>图像生成</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>WebUI</source>
        <translation>WebUI</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>ComfyUI</source>
        <translation>ComfyUI</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Prompt</source>
        <translation>提示词</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Mask</source>
        <translation>蒙版</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Sampling</source>
        <translation>采样</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Size and batch</source>
        <translation>尺寸与批次</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Advanced</source>
        <translation>高级</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Inpainting and size</source>
        <translation>局部重绘与尺寸</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Model</source>
        <translation>模型</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>CFG scale</source>
        <translation>CFG Scale</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Steps</source>
        <translation>采样步数</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Negative prompt</source>
        <translation>负面提示词</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Last seed {seed}</source>
        <translation>上次随机种子 {seed}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>whole area</source>
        <comment>Inpaint context while it covers the whole generation area</comment>
        <translation>整个区域</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Inpainting ignores the context limit while tiling is on.</source>
        <translation>平铺开启时，局部重绘会忽略周边范围限制。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Tiling on</source>
        <translation>平铺已开启</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Generated images tile, and inpainting ignores the context limit. Click to turn tiling off.</source>
        <translation>生成的图像可无缝平铺，局部重绘会忽略周边范围限制。点击关闭平铺。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>LoRA</source>
        <translation>LoRA</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Choose LoRA models to add to the prompt</source>
        <translation>选择要添加到提示词中的 LoRA 模型</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Styles</source>
        <translation>风格模板</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Add saved prompt styles to the prompt</source>
        <translation>将已保存的风格模板添加到提示词</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Describe</source>
        <translation>反推提示词</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Replace the prompt with a description of the generation area</source>
        <translation>用生成区域内容的描述替换提示词</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Select image generator...</source>
        <translation>选择图像生成器...</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Stable Diffusion settings...</source>
        <translation>Stable Diffusion 设置...</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>LCM mode</source>
        <translation>LCM 模式</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Clear GPU memory</source>
        <translation>清理显存</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Remove cached models from GPU memory in ComfyUI.</source>
        <translation>从 ComfyUI 的显存中移除缓存的模型。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Image to image: ignores the mask</source>
        <translation>图生图：忽略蒙版</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Text to image: ignores the canvas</source>
        <translation>文生图：忽略画布</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>{count} x {width}x{height}</source>
        <comment>Generate button summary: image count and size</comment>
        <translation>{count} 张，{width}x{height}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>Setup...</source>
        <translation>设置...</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>blur {blur}</source>
        <comment>Mask section summary</comment>
        <translation>模糊 {blur}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>blur {blur}, soft inpainting</source>
        <comment>Mask section summary</comment>
        <translation>模糊 {blur}，柔和局部重绘</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>seed {seed}, {sampler}</source>
        <comment>Sampling section summary while the seed is fixed</comment>
        <translation>随机种子 {seed}，{sampler}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>{width} x {height}, count {count}</source>
        <comment>Size and batch section summary</comment>
        <translation>{width} x {height}，{count} 批</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/stable_diffusion_panel.py"/>
        <source>defaults</source>
        <translation>默认</translation>
    </message>
</context>
<context>
    <name>ui.panel.generators.soft_inpainting_controls</name>
    <message>
        <location filename="../../src/ui/panel/generators/soft_inpainting_controls.py"/>
        <source>Soft inpainting settings</source>
        <translation>柔和局部重绘设置</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/soft_inpainting_controls.py"/>
        <source>Soft inpainting works best with a mask blur of {blur} or more: the blurred edge sets how gradually the content changes.</source>
        <translation>蒙版模糊为 {blur} 或以上时，柔和局部重绘效果最好：模糊的边缘决定内容变化的渐变程度。</translation>
    </message>
</context>
<context>
    <name>ui.panel.generators.testing_panel</name>
    <message>
        <location filename="../../src/ui/panel/generators/testing_panel.py"/>
        <source>Test generator</source>
        <translation>测试生成器</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/testing_panel.py"/>
        <source>--mode mock</source>
        <translation>--mode mock</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/testing_panel.py"/>
        <source>Inpaint</source>
        <translation>局部重绘</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/testing_panel.py"/>
        <source>Img2img</source>
        <translation>图生图</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/testing_panel.py"/>
        <source>Txt2img</source>
        <translation>文生图</translation>
    </message>
</context>
<context>
    <name>ui.panel.generators.webui_advanced_controls</name>
    <message>
        <location filename="../../src/ui/panel/generators/webui_advanced_controls.py"/>
        <source>Seed variation</source>
        <translation>差异种子</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/webui_advanced_controls.py"/>
        <source>Output</source>
        <translation>输出</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/webui_advanced_controls.py"/>
        <source>Last variation seed {seed}</source>
        <translation>上次差异种子 {seed}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/webui_advanced_controls.py"/>
        <source>Resize seed from</source>
        <translation>从以下分辨率调整随机种子</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/webui_advanced_controls.py"/>
        <source>Off</source>
        <comment>Variation strength is zero</comment>
        <translation>关闭</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/webui_advanced_controls.py"/>
        <source>variation {strength}</source>
        <translation>差异强度 {strength}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/webui_advanced_controls.py"/>
        <source>tiling</source>
        <translation>平铺</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/webui_advanced_controls.py"/>
        <source>restore faces</source>
        <translation>面部修复</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/generators/webui_advanced_controls.py"/>
        <source>seed resize</source>
        <translation>随机种子尺寸调整</translation>
    </message>
</context>
<context>
    <name>ui.panel.image_panel</name>
    <message>
        <location filename="../../src/ui/panel/image_panel.py"/>
        <source>Hide rulers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/image_panel.py"/>
        <source>Highlight generation area and selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/image_panel.py"/>
        <source>Lock guides</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/image_panel.py"/>
        <source>Clear guides</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.layer.layer_visibility_button</name>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_visibility_button.py"/>
        <source>Toggle layer visibility</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_visibility_button.py"/>
        <source>Toggle layer visibility. The layer is visible, but the group "{group_name}" hides it.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.layer_ui.blend_mode_combo_box</name>
    <message>
        <location filename="../../src/ui/panel/layer_ui/blend_mode_combo_box.py"/>
        <source>Compositing (alpha only)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/blend_mode_combo_box.py"/>
        <source>Layer blend mode</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.layer_ui.layer_flags</name>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_flags.py"/>
        <source>Lock</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_flags.py"/>
        <source>Toggle layer lock</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_flags.py"/>
        <source>Alpha lock</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_flags.py"/>
        <source>Toggle layer transparency lock</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_flags.py"/>
        <source>Isolate</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_flags.py"/>
        <source>Toggle layer group isolation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_flags.py"/>
        <source>Layer groups below full opacity or outside Normal mode are always isolated</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.layer_ui.layer_list</name>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_list.py"/>
        <source>{width} x {height}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_list.py"/>
        <source>The whole image. Click to select it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_list.py"/>
        <source>Into {name}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_list.py"/>
        <source>Above {name}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_list.py"/>
        <source>Below {name}</source>
        <translation type="unfinished"></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/layer_ui/layer_list.py"/>
        <source>%n layer(s) into {name}</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/layer_ui/layer_list.py"/>
        <source>%n layer(s) above {name}</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/layer_ui/layer_list.py"/>
        <source>%n layer(s) below {name}</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
</context>
<context>
    <name>ui.panel.layer_ui.layer_menu</name>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Move up</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Move down</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Move to top</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Duplicate</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Delete</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Group selected layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Merge down</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Merge group</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Merge all visible</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Flatten</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Rename</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Clear selected pixels</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Copy selected to new layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Layer to image size</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Crop layer to content</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Crop layer to selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Mirror vertically</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Mirror horizontally</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Rotate 90° clockwise</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Rotate 90° counter-clockwise</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Select layer contents</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Select contents of selected layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Crop and resize</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Mirror and rotate</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>{src_layer_name} copied content</source>
        <translation type="unfinished"></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Duplicate %n layer(s)</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>Delete %n layer(s)</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/layer_ui/layer_menu.py"/>
        <source>%n layer(s)</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
</context>
<context>
    <name>ui.panel.layer_ui.layer_panel</name>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Image Layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Add layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Create a new layer above the current active layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Add layer group</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Create a new layer group above the current active layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Duplicate layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Create a duplicate of the active layer above it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Create a duplicate of each selected layer above it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Delete layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Delete the active layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Delete every selected layer.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Move layer up</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Move the active layer up.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Move layer down</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Move the active layer down.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Merge down</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Merge the active layer with the one below it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>New</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Group</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Duplicate</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Up</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Down</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Merge</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Delete</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Thumbnails:</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Select previous layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>Select next layer</source>
        <translation type="unfinished"></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>%n layer(s) selected</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/layer_ui/layer_panel.py"/>
        <source>%n layer(s)</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
</context>
<context>
    <name>ui.panel.layer_ui.layer_properties</name>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_properties.py"/>
        <source>Opacity</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_properties.py"/>
        <source>Layer opacity</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_properties.py"/>
        <source>"{layer_name}" is locked</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_properties.py"/>
        <source>Unlock</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.layer_ui.layer_row</name>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_row.py"/>
        <source> · </source>
        <comment>separates the parts of a layer row's meta line</comment>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_row.py"/>
        <source>{percent}%</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_row.py"/>
        <source>Aa</source>
        <comment>marks text layer thumbnails</comment>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_row.py"/>
        <source>Show or hide the layers in this group</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_row.py"/>
        <source>{width} x {height} px at ({x}, {y})</source>
        <comment>layer thumbnail tooltip</comment>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_row.py"/>
        <source>{width} x {height} px, transformed to cover {cover_w} x {cover_h} at ({x}, {y})</source>
        <comment>layer thumbnail tooltip</comment>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/layer_ui/layer_row.py"/>
        <source>Empty group</source>
        <comment>layer thumbnail tooltip</comment>
        <translation type="unfinished"></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/layer_ui/layer_row.py"/>
        <source>%n layer(s)</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
</context>
<context>
    <name>ui.panel.mypaint_brush_dynamics</name>
    <message>
        <location filename="../../src/ui/panel/mypaint_brush_dynamics.py"/>
        <source>Setting</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/mypaint_brush_dynamics.py"/>
        <source>Base value</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.mypaint_brush_grid</name>
    <message>
        <location filename="../../src/ui/panel/mypaint_brush_grid.py"/>
        <source>Toggle favorite</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.mypaint_brush_panel</name>
    <message>
        <location filename="../../src/ui/panel/mypaint_brush_panel.py"/>
        <source>Favorites</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/mypaint_brush_panel.py"/>
        <source>All</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/mypaint_brush_panel.py"/>
        <source>Add to Favorites</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/mypaint_brush_panel.py"/>
        <source>Remove from Favorites</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/mypaint_brush_panel.py"/>
        <source>No brush</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/mypaint_brush_panel.py"/>
        <source>Brush category</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panel.generation_area_tool_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Position and size</source>
        <translation>位置和大小</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Size presets</source>
        <translation>预设尺寸</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Sent to generator</source>
        <translation>发送给生成器</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Fit</source>
        <translation>适配</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Recent</source>
        <translation>最近</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Custom</source>
        <translation>自定义</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Full image</source>
        <translation>整张图像</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Square</source>
        <translation>正方形</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Previous</source>
        <translation>上次</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Resize the generation area to cover the entire image.</source>
        <translation>将生成区域调整为覆盖整张图像。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Resize the generation area to the largest square that fits in the image.</source>
        <translation>将生成区域调整为图像内能容纳的最大正方形。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Resize the generation area to the last size it had ({key}).</source>
        <translation>将生成区域恢复为上一次的大小（{key}）。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Resize the generation area to a recently used size.</source>
        <translation>将生成区域调整为最近使用过的大小。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Sizes you use appear here.</source>
        <translation>使用过的尺寸会显示在这里。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>-</source>
        <translation>-</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>768 or 640x480</source>
        <translation>768 或 640x480</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Type a size like 768 or 640x480 and press Enter to resize the generation area.</source>
        <translation>输入 768 或 640x480 这样的尺寸并按 Enter 键，调整生成区域大小。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Not a size: try 768 or 640x480</source>
        <translation>不是有效尺寸：请尝试 768 或 640x480</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Generates at {width} x {height}</source>
        <translation>按 {width} x {height} 生成</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>{resolution}, {rule}</source>
        <translation>{resolution}，{rule}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Edit</source>
        <translation>编辑</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/generation_area_tool_panel.py"/>
        <source>Change the resolution and resolution rule in the Image generation panel.</source>
        <translation>在“图像生成”面板中修改分辨率和分辨率规则。</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.brush_selection_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/brush_selection_panel.py"/>
        <source>Select</source>
        <translation>选择</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/brush_selection_panel.py"/>
        <source>Deselect</source>
        <translation>取消选择</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/brush_selection_panel.py"/>
        <source>Brush</source>
        <translation>画笔</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/brush_selection_panel.py"/>
        <source>Hold {keys} to subtract.</source>
        <translation>按住 {keys} 减去。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/brush_selection_panel.py"/>
        <source>{keys} draws a straight line.</source>
        <translation>按住 {keys} 绘制直线。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/brush_selection_panel.py"/>
        <source>Right-click adds a context pin.</source>
        <translation>右键单击可添加周边范围锚点。</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.clone_stamp_tool_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/clone_stamp_tool_panel.py"/>
        <source>Source</source>
        <translation>源</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/clone_stamp_tool_panel.py"/>
        <source>Offset X</source>
        <translation>偏移 X</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/clone_stamp_tool_panel.py"/>
        <source>Offset Y</source>
        <translation>偏移 Y</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/clone_stamp_tool_panel.py"/>
        <source>Source X</source>
        <translation>源 X</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/clone_stamp_tool_panel.py"/>
        <source>Source Y</source>
        <translation>源 Y</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.eraser_tool_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/eraser_tool_panel.py"/>
        <source>Size</source>
        <translation>大小</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.fill_tool_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/fill_tool_panel.py"/>
        <source>Paint</source>
        <translation>颜料</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/fill_tool_panel.py"/>
        <source>Region</source>
        <translation>区域</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/fill_tool_panel.py"/>
        <source>How closely a color must match the clicked color to be filled. 0 fills only exact matches. Shared with the magic wand.</source>
        <translation>颜色与所点击的颜色需要多接近才会被填充。0 表示只填充完全相同的颜色。与魔棒共用。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/fill_tool_panel.py"/>
        <source>Fill based on the whole image instead of just the active layer. Shared with the magic wand.</source>
        <translation>根据整个图像而不仅是当前图层进行填充。与魔棒共用。</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.filter_tool_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/filter_tool_panel.py"/>
        <source>Filter</source>
        <translation>滤镜</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/filter_tool_panel.py"/>
        <source>Strength</source>
        <translation>强度</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/filter_tool_panel.py"/>
        <source>How strongly the filter is applied where you paint</source>
        <translation>在绘制处应用滤镜的强度</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.free_selection_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/free_selection_panel.py"/>
        <source>Free selection</source>
        <translation>自由选区</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/free_selection_panel.py"/>
        <source>Click adds a point. Enter closes the shape and applies it.</source>
        <translation>单击添加一个点。按 Enter 闭合形状并应用。</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.layer_transform_tool_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/layer_transform_tool_panel.py"/>
        <source>Revert</source>
        <translation>还原</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/layer_transform_tool_panel.py"/>
        <source>Restore the transform this layer had when you selected it</source>
        <translation>恢复此图层在被选中时的变换</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/layer_transform_tool_panel.py"/>
        <source>Clear transform</source>
        <translation>清除变换</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/layer_transform_tool_panel.py"/>
        <source>Remove all movement, scaling and rotation from this layer</source>
        <translation>移除此图层的所有移动、缩放和旋转</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/layer_transform_tool_panel.py"/>
        <source>Image</source>
        <translation>图像</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/layer_transform_tool_panel.py"/>
        <source>Layer</source>
        <translation>图层</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/layer_transform_tool_panel.py"/>
        <source>This layer has a perspective transform, which this tool can't edit. Revert and Clear transform still work.</source>
        <translation>此图层带有透视变换，此工具无法编辑。“还原”和“清除变换”仍然可用。</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.magic_wand_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/magic_wand_panel.py"/>
        <source>Fill area</source>
        <translation>填充区域</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.mypaint_brush_tool_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/mypaint_brush_tool_panel.py"/>
        <source>Size</source>
        <translation>大小</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/mypaint_brush_tool_panel.py"/>
        <source>Brush</source>
        <translation>画笔</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/mypaint_brush_tool_panel.py"/>
        <source>Brush dynamics</source>
        <translation>画笔动态</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/mypaint_brush_tool_panel.py"/>
        <source>Opacity and hardness come from the brush file.</source>
        <translation>不透明度和硬度由画笔文件决定。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/mypaint_brush_tool_panel.py"/>
        <source>{brush}. {hint}</source>
        <translation>{brush}。{hint}</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.selection_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Mode</source>
        <translation>模式</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Mode: {mode}</source>
        <translation>模式：{mode}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Selection</source>
        <translation>选区</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Select all</source>
        <translation>全选</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Clear</source>
        <translation>清除</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Clear pins</source>
        <translation>清除锚点</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>{description} ({shortcut})</source>
        <translation>{description}（{shortcut}）</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Select the whole image</source>
        <translation>选择整个图像</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Clear the selection</source>
        <translation>清除选区</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Remove all context pins. Right-click in the image with any selection tool to add, move or remove pins.</source>
        <translation>移除所有周边范围锚点。使用任意选区工具在图像中右键单击，可添加、移动或删除锚点。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Hold {add_keys} to add, {subtract_keys} to subtract.</source>
        <translation>按住 {add_keys} 添加，按住 {subtract_keys} 减去。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Hold {subtract_keys} to subtract.</source>
        <translation>按住 {subtract_keys} 减去。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Position: {x}, {y}</source>
        <translation>位置：{x}, {y}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Size: {width} x {height}</source>
        <translation>大小：{width} x {height}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>-</source>
        <translation>-</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>{width} x {height} at {x}, {y}</source>
        <translation>{width} x {height}，位于 {x}, {y}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py"/>
        <source>Nothing selected</source>
        <translation>未选择任何内容</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.shape_selection_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_selection_panel.py"/>
        <source>Shape</source>
        <translation>形状</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_selection_panel.py"/>
        <source>Fixed 1:1 ratio</source>
        <translation>固定 1:1 比例</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_selection_panel.py"/>
        <source>{description} Hold {keys} to fix the ratio for a single drag.</source>
        <translation>{description}按住 {keys} 可在单次拖动中固定比例。</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.shape_tool_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>Shape</source>
        <translation>形状</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>Outline</source>
        <translation>轮廓</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>Fill</source>
        <translation>填充</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>Vertices</source>
        <translation>顶点</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>Inner radius</source>
        <translation>内半径</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>Width</source>
        <translation>宽度</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>Color</source>
        <translation>颜色</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>Dash</source>
        <translation>虚线</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>Join</source>
        <translation>接合</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>none</source>
        <translation>无</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source> px</source>
        <translation> px</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>Dash and gap lengths in px, in pairs</source>
        <translation>虚线和间隔的长度（px），成对填写</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>{width} {style}</source>
        <translation>{width} {style}</translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>{shape}, %n point(s)</source>
        <translation><numerusform>{shape}，%n 个角</numerusform></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/panel/tool_control_panels/shape_tool_panel.py"/>
        <source>{shape}, %n vertex/vertices</source>
        <translation><numerusform>{shape}，%n 个顶点</numerusform></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/shape_mode.py"/>
        <source>Ellipse</source>
        <translation>椭圆</translation>
    </message>
    <message>
        <location filename="../../src/util/visual/shape_mode.py"/>
        <source>Rectangle</source>
        <translation>矩形</translation>
    </message>
    <message>
        <location filename="../../src/util/visual/shape_mode.py"/>
        <source>Polygon</source>
        <translation>多边形</translation>
    </message>
    <message>
        <location filename="../../src/util/visual/shape_mode.py"/>
        <source>Star</source>
        <translation>星形</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.smudge_tool_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/smudge_tool_panel.py"/>
        <source>Strength</source>
        <translation>强度</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/smudge_tool_panel.py"/>
        <source>How far the smudge carries color</source>
        <translation>涂抹带动颜色的距离</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.stroke_block</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/stroke_block.py"/>
        <source>Only inside selection</source>
        <translation>仅在选区内</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/stroke_block.py"/>
        <source>Stroke</source>
        <translation>描边</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/stroke_block.py"/>
        <source>Color and options</source>
        <translation>颜色和选项</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/stroke_block.py"/>
        <source>Options</source>
        <translation>选项</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/stroke_block.py"/>
        <source> px</source>
        <translation> px</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/stroke_block.py"/>
        <source>%</source>
        <translation>%</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_control_panels.text_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Enter text</source>
        <translation>输入文字</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Font</source>
        <translation>字体</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Style</source>
        <translation>样式</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Position and size</source>
        <translation>位置和大小</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Advanced</source>
        <translation>高级</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Preview</source>
        <translation>预览</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Type to filter fonts</source>
        <translatorcomment>glossary: not "Filter" - the verb, narrowing the font list as the user types, which the glossary's context notes render as 筛选.</translatorcomment>
        <translation>输入以筛选字体</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Font family</source>
        <translation>字体系列</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Size</source>
        <translation>字号</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Font size</source>
        <translation>字号</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>px</source>
        <translation>px</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>pt</source>
        <translation>pt</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Font size in pixels</source>
        <translation>以像素为单位的字号</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Font size in points</source>
        <translation>以磅为单位的字号</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source> px</source>
        <translation> px</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source> pt</source>
        <translation> pt</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>{family}, {size}</source>
        <translation>{family}，{size}</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Bold</source>
        <translation>粗体</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Italic</source>
        <translation>斜体</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Underline</source>
        <translation>下划线</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Strikethrough</source>
        <translation>删除线</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Overline</source>
        <translation>上划线</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Fixed pitch</source>
        <translation>等宽</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Kerning</source>
        <translation>字距调整</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Align left</source>
        <translation>左对齐</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Align center</source>
        <translation>居中对齐</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Align right</source>
        <translation>右对齐</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Text</source>
        <translation>文字</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Background</source>
        <translation>背景</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Same as brush color</source>
        <translation>与画笔颜色相同</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Text color. It is the same color the brush uses.</source>
        <translation>文字颜色，与画笔使用的颜色相同。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Background color, drawn behind the text while "Fill behind text" is on</source>
        <translation>背景色，开启“填充文字背景”时绘制在文字后面</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Use background color</source>
        <translation>使用背景色</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Set the text box fill color to the current background color</source>
        <translation>将文字框的填充颜色设为当前背景色</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Fill behind text</source>
        <translation>填充文字背景</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Fill the text box with the background color</source>
        <translation>用背景色填充文字框</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Box fit</source>
        <translation>适应方式</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Free</source>
        <translation>自由</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Fit font</source>
        <translation>适应字号</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Fit box</source>
        <translation>适应框</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Free: the font size and the box size are set separately</source>
        <translation>自由：字号和框的大小分别设置</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Fit font: the font size changes to fit the text in the box</source>
        <translation>适应字号：字号随文字变化，使文字适应框</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Fit box: the box resizes to fit the text</source>
        <translation>适应框：框调整大小以适应文字</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Overflows</source>
        <translation>溢出</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>The text is larger than its box, so part of it is cut off. Enlarge the box, or pick Fit font or Fit box.</source>
        <translation>文字大于其框，部分文字被截断。请放大框，或选择“适应字号”或“适应框”。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Stretch</source>
        <translation>拉伸</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Stretches the font horizontally, as a percentage of its normal width</source>
        <translation>水平拉伸字体，以正常宽度的百分比表示</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Stretch is unavailable for bitmap fonts, which cannot be stretched</source>
        <translation>位图字体无法拉伸，因此“拉伸”不可用</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>auto</source>
        <translation>自动</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>%</source>
        <translation>%</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>Outline = text box.
Turns red when the text does not fit.</source>
        <translation>轮廓 = 文字框。
文字放不下时变为红色。</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>fits box</source>
        <translation>未溢出</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py"/>
        <source>overflows</source>
        <translation>溢出</translation>
    </message>
</context>
<context>
    <name>ui.panel.tool_panel</name>
    <message>
        <location filename="../../src/ui/panel/tool_panel.py"/>
        <source>Key bindings...</source>
        <translation>快捷键...</translation>
    </message>
    <message>
        <location filename="../../src/ui/panel/tool_panel.py"/>
        <source>Pressure curve...</source>
        <translation>笔压曲线...</translation>
    </message>
</context>
<context>
    <name>ui.widget.anchor_grid</name>
    <message>
        <location filename="../../src/ui/widget/anchor_grid.py"/>
        <source>Place the current image at this corner, edge or the center of the new canvas</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.widget.brush_color_button</name>
    <message>
        <location filename="../../src/ui/widget/color_button.py"/>
        <source>Color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_button.py"/>
        <source>Select paint color</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.widget.canvas_bar</name>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Zoom</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Zoom in</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Zoom out</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Reset view</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Restore default image zoom and offset</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Rulers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Show rulers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Right-click for ruler highlight options</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Selection overlay</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Show selection overlay</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>When hidden, only the selection outline is drawn</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Navigation window</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Controls for this tool</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>More view options</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Highlight generation area and selection</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Tool control hints</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Show tool control hints</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/canvas_bar.py"/>
        <source>Hide tool control hints</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.widget.color_pair_widget</name>
    <message>
        <location filename="../../src/ui/widget/color_pair_widget.py"/>
        <source>Foreground color: click to change, or drag a color here</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_pair_widget.py"/>
        <source>Background color: click to change, or drag a color here</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_pair_widget.py"/>
        <source>Swap foreground and background colors</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_pair_widget.py"/>
        <source>Reset to a black foreground and a white background</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.widget.color_picker.color_comparison</name>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_comparison.py"/>
        <source>Left: the starting color, click to go back to it. Right: the new color.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.widget.color_picker.color_picker_header</name>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_picker_header.py"/>
        <source>Pick a color from anywhere on the screen</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_picker_header.py"/>
        <source>Screen color picking failed: {reason}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_picker_header.py"/>
        <source>Cursor at {x},{y}
Click to pick, or press Esc to cancel</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.widget.color_picker.color_slider_block</name>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Color model for the sliders</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Hatched parts of the track are colors sRGB cannot show.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>RGB</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>HSV</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>OKLCH</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>A</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Opacity, from 0 (transparent) to 255 (opaque)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>{mode} {first}, {second}, {third}, alpha {alpha}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>R</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Red</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>G</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Green</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>B</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Blue</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>H</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Hue, in degrees</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>S</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Saturation, in percent</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>V</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Value, in percent</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>L</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Perceptual lightness, in percent</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>C</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Chroma: 0 is gray, and the most saturated sRGB colors reach about 0.32</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/color_slider_block.py"/>
        <source>Perceptual hue, in degrees</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.widget.color_picker.hex_field</name>
    <message>
        <location filename="../../src/ui/widget/color_picker/hex_field.py"/>
        <source>Hex color: #RGB, #RRGGBB, or #AARRGGBB with alpha first</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.widget.color_picker.saved_colors_panel</name>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>Saved colors ({count}/{max_count})</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>{count} of {max_count}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>Click a color to use it. Drag colors here to save them, or drag to reorder them. Right-click a color to remove it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>Sa&amp;ve</source>
        <translation>保存(&amp;V)</translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>Add the current color to the saved colors</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>The saved colors are full. Remove one to save another.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>Re&amp;move</source>
        <translation>移除(&amp;M)</translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>Remove the current color from the saved colors</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>Remove</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>Recent colors</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>Colors you chose most recently, newest first. Click a color to use it again, or drag it to the saved colors.</source>
        <translation type="unfinished"></translation>
    </message>
    <message numerus="yes">
        <location filename="../../src/ui/widget/color_picker/saved_colors_panel.py"/>
        <source>%n color(s)</source>
        <translation type="unfinished"><numerusform></numerusform></translation>
    </message>
</context>
<context>
    <name>ui.widget.guide_handle_bar</name>
    <message>
        <location filename="../../src/ui/widget/guide_handle_bar.py"/>
        <source>Delete guide</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.widget.panel_header</name>
    <message>
        <location filename="../../src/ui/widget/panel_header.py"/>
        <source>Reset to defaults</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/widget/panel_header.py"/>
        <source>More</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.widget.quick_stroke_card</name>
    <message>
        <location filename="../../src/ui/widget/quick_stroke_card.py"/>
        <source>Recent colors: click to set the foreground color</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.window.dock_menu</name>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Tab with</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Split beside</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Move to edge</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Move all panels to edge</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Float</source>
        <translation>浮动</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Dock</source>
        <translation>停靠</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Hide panel</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>{front_title} (+{count})</source>
        <translation>{front_title}（+{count}）</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Left</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Right</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Top</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Bottom</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Above</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_menu.py"/>
        <source>Below</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.window.dock_notch</name>
    <message>
        <location filename="../../src/ui/window/dock_notch.py"/>
        <source>Drag to move panel</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.window.dock_rail</name>
    <message>
        <location filename="../../src/ui/window/dock_rail.py"/>
        <source>Generate</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/dock_rail.py"/>
        <source>Start image generation</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.window.extra_network_window</name>
    <message>
        <location filename="../../src/ui/window/extra_network_window.py"/>
        <source>LoRA Models</source>
        <translation>LoRA 模型</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/extra_network_window.py"/>
        <source>Close</source>
        <translation>关闭</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/extra_network_window.py"/>
        <source>LoRA</source>
        <translation>LoRA</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/extra_network_window.py"/>
        <source>Search LoRA models</source>
        <translation>搜索 LoRA 模型</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/extra_network_window.py"/>
        <source>Weight</source>
        <translation>权重</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/extra_network_window.py"/>
        <source>Weight of the selected LoRA in the prompt. Add the LoRA to the prompt to change it.</source>
        <translation>所选 LoRA 在提示词中的权重。将该 LoRA 添加到提示词后才能修改。</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/extra_network_window.py"/>
        <source>In prompt</source>
        <translation>已在提示词中</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/extra_network_window.py"/>
        <source>No LoRA models match the search.</source>
        <translation>没有与搜索匹配的 LoRA 模型。</translation>
    </message>
</context>
<context>
    <name>ui.window.floating_title_bar</name>
    <message>
        <location filename="../../src/ui/window/floating_title_bar.py"/>
        <source>Dock panel</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/floating_title_bar.py"/>
        <source>Hide panel</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.window.generator_setup_window</name>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>Image Generator Selection</source>
        <translatorcomment>glossary: not "Selection" - choosing a generator, not an image selection.</translatorcomment>
        <translation>选择图像生成器</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>Activate</source>
        <translation>激活</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>&lt;h1&gt;Image generator status:&lt;/h1&gt;</source>
        <translation>&lt;h1&gt;图像生成器状态：&lt;/h1&gt;</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>This image generator is active.</source>
        <translation>此图像生成器已激活。</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>This image generator is available, click "Activate" to attempt to use it.</source>
        <translation>此图像生成器可用，点击“激活”尝试使用它。</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>This image generator is not available: {error_reason}</source>
        <translation>此图像生成器不可用：{error_reason}</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>Unknown error encountered, please report this on the &lt;a href="https://github.com/centuryglass/IntraPaint/issues"&gt;GitHub issues page&lt;/a&gt;.</source>
        <translation>遇到未知错误，请在 &lt;a href="https://github.com/centuryglass/IntraPaint/issues"&gt;GitHub Issues 页面&lt;/a&gt;报告此问题。</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>&lt;h1&gt;Generator Options:&lt;/h1&gt;</source>
        <translation>&lt;h1&gt;可选生成器：&lt;/h1&gt;</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>&lt;u&gt;Preview: {generator_name}&lt;/u&gt;</source>
        <translation>&lt;u&gt;预览：{generator_name}&lt;/u&gt;</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>Description</source>
        <translation>说明</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/generator_setup_window.py"/>
        <source>Setup Guide</source>
        <translation>设置指南</translation>
    </message>
</context>
<context>
    <name>ui.window.main_window</name>
    <message>
        <location filename="../../src/ui/window/main_window.py"/>
        <source>Tools</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/main_window.py"/>
        <source>Image Generation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/main_window.py"/>
        <source>ControlNet</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/main_window.py"/>
        <source>Layers</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/main_window.py"/>
        <source>Color</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/main_window.py"/>
        <source>Navigation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/main_window.py"/>
        <source>Loading...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/main_window.py"/>
        <source>Inpainting failure</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/main_window.py"/>
        <source>Generation stopped before any images were ready.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/main_window.py"/>
        <source>Generation finished without any images.</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.window.metadata_window</name>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Image metadata</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Generation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>All metadata</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Other</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Raw text</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Show and edit the saved parameters text directly.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Prompt</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Negative prompt</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Apply to editor</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Apply</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Replace the editor setting with the saved value.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Update from editor</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Update</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Replace the saved value with the editor setting.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Apply all</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Replace every mapped editor setting with its saved value.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Update all</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Replace every mapped saved value with the editor setting. Other saved fields are kept.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Copy</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Copy the saved parameters text to the clipboard.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Field</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Value</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Editor</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>The editor setting, shown where it differs from the saved value.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>(empty)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Source</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Name</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Value of "{name}"</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Select a row to see its full value.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Value of "{name}" (read-only)</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Add field</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Generation parameters need a settings line first. Use "Update all" to create one.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Remove field</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Select a field to remove. A1111 reads a settings line with fewer than three fields as part of the prompt, so the last three can't be removed.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>New field</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>New field {number}</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Add text entry</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Remove</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Select a text entry or EXIF tag to remove.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>new_entry</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Remove location data</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Remove the EXIF GPS tags, and the city, state, country and location fields of IPTC and XMP data. Captions, keywords and other text may still name a place.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Remove all metadata</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Remove every text entry, EXIF tag and embedded data block.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Save to file</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Apply the changes, and write the metadata into "{file_name}" now. The image itself is not saved.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>The image hasn't been saved yet, so there is no file to write to.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>IntraPaint can't write metadata into {file_format} files.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Saved the metadata to "{file_name}".</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Saved the metadata to "{file_name}". Your unsaved edits to the image are not in the file yet.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Saving the metadata failed</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Re-encode "{file_name}"?</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>This file's image data is JPEG-compressed. Writing its metadata means re-encoding it, which loses a little quality even at the highest setting.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Re-encode at quality 100</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Apply changes</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Close</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Discard changes</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Changes are not kept until you click "Apply changes". Saving the image writes applied changes.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>This image has no generation parameters. Use "Update all" to add the editor's settings.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>This image has no metadata.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>This image has no ComfyUI, NovelAI or InvokeAI data.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>{source}: nodes</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Not applied: {field} "{value}" ({reason})</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Text</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>A PNG or OpenRaster text entry, or a JPEG or GIF comment.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>EXIF</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>EXIF: Exif</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>EXIF: GPS</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>EXIF: Interop</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>IPTC</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>XMP</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>ICC</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>XMP packet</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Color profile</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Embedded. The image is converted to sRGB, and saved without a profile.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>The image hasn't been saved yet. Formats that keep metadata: {formats}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>This image has no metadata to save.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>{file_format} files keep no metadata. To keep it, save as one of: {formats}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Saving as {file_format} keeps all of this metadata.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Saving as {file_format} keeps: {kept}. It drops: {dropped}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>Saving as {file_format} drops all of this metadata: {dropped}.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>generation parameters</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>comment</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>text entries ({keys})</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/metadata_window.py"/>
        <source>EXIF tags</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.window.navigation_window</name>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Navigate</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Move view</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Left-click to pan, Shift + left-click to draw viewport</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Move gen. area</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>View</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Gen. area</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Reset view</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Zoom {percent}%</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Drag: pan</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Shift+drag: draw new view</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Right-click: add, move or remove context pins</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Drag: move area</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>Right-drag: resize area</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/navigation_window.py"/>
        <source>, </source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>ui.window.prompt_style_window</name>
    <message>
        <location filename="../../src/ui/window/prompt_style_window.py"/>
        <source>Saved Prompt Styles</source>
        <translation>已保存的风格模板</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/prompt_style_window.py"/>
        <source>Name:</source>
        <translation>名称：</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/prompt_style_window.py"/>
        <source>Prompt:</source>
        <translation>提示词：</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/prompt_style_window.py"/>
        <source>Negative:</source>
        <translation>负面提示词：</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/prompt_style_window.py"/>
        <source>Add to prompt</source>
        <translation>添加到提示词</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/prompt_style_window.py"/>
        <source>Replace prompt</source>
        <translation>替换提示词</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/prompt_style_window.py"/>
        <source>Save changes</source>
        <translation>保存更改</translation>
    </message>
    <message>
        <location filename="../../src/ui/window/prompt_style_window.py"/>
        <source>Close</source>
        <translation>关闭</translation>
    </message>
</context>
<context>
    <name>ui.window.standalone_metadata_window</name>
    <message>
        <location filename="../../src/ui/window/standalone_metadata_window.py"/>
        <source>{file_name} - Image metadata</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/standalone_metadata_window.py"/>
        <source>Save</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/standalone_metadata_window.py"/>
        <source>Save as...</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/standalone_metadata_window.py"/>
        <source>Save a copy with this metadata. A copy in another format is re-encoded from the image.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/standalone_metadata_window.py"/>
        <source>Changes are not kept until you click "Save".</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/standalone_metadata_window.py"/>
        <source>Embedded. Saving keeps it, since the image's colors depend on it.</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/standalone_metadata_window.py"/>
        <source>Close without saving</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/standalone_metadata_window.py"/>
        <source>Save a copy as PNG</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/standalone_metadata_window.py"/>
        <source>{file_format} files can't hold this metadata</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/ui/window/standalone_metadata_window.py"/>
        <source>IntraPaint can't write metadata into {file_format} files. Save a PNG copy of the image with the metadata instead?</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>util.shared_text</name>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>, </source>
        <comment>Separator between items in a display list</comment>
        <translation>、</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Generate</source>
        <translation>生成</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Start AI image generation or modification</source>
        <translation>开始 AI 图像生成或修改</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Editing failed</source>
        <translation>编辑失败</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>The selected layer is locked, unlock it or select a different layer.</source>
        <translation>所选图层已锁定，请解锁或选择其他图层。</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>The selected layer is in a locked group, unlock it or select a different layer.</source>
        <translation>所选图层位于已锁定的图层组中，请解锁该组或选择其他图层。</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>The selected layer is hidden, un-hide it before trying to edit it.</source>
        <translation>所选图层已隐藏，请先显示该图层再编辑。</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>The selected layer is in the hidden group "{group_name}", un-hide the group before trying to edit it.</source>
        <translation>所选图层位于隐藏的图层组“{group_name}”中，请先显示该组再编辑。</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>The selected layer is not an image layer, select an image layer first.</source>
        <translation>所选图层不是图像图层，请先选择一个图像图层。</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Changes are restricted to selected content only, but nothing is selected in this layer. Select layer content or enable changes in unselected areas.</source>
        <translation>更改仅限于所选内容，但此图层中没有选中任何内容。请选择图层内容，或允许在未选中的区域进行更改。</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Not authenticated</source>
        <translation>未通过身份验证</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Image generator connection</source>
        <translation>图像生成器连接</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Enter server URL:</source>
        <translation>输入服务器 URL：</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Request timed out</source>
        <translation>请求超时</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Server connection failed, enter a new URL or click "OK" to retry</source>
        <translation>服务器连接失败，请输入新的 URL，或点击“确定”重试</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Failed to connect to image generator at "{url}": Login cancelled.</source>
        <translation>无法连接到位于“{url}”的图像生成器：已取消登录。</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Failed to connect to image generator at "{url}".  Click "Activate" to try again or choose a different address. &lt;br/&gt; Full error text: &lt;br/&gt;&lt;blockquote&gt;{error_text}&lt;/blockquote&gt;</source>
        <translation>无法连接到位于“{url}”的图像生成器。点击“激活”重试，或选择其他地址。&lt;br/&gt;完整错误信息：&lt;br/&gt;&lt;blockquote&gt;{error_text}&lt;/blockquote&gt;</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Describe failed</source>
        <translation>反推提示词失败</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Open or create an image first.</source>
        <translation>请先打开或创建图像。</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Image generation failed</source>
        <translation>图像生成失败</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Nothing was selected in the generation area. Either use the selection tool to mark part of the generation area for inpainting, move the image generation area to cover selected content, or switch to another image generation mode.</source>
        <translation>生成区域内没有选中任何内容。请使用选区工具标记生成区域中要局部重绘的部分，或移动图像生成区域以覆盖已选中的内容，或切换到其他图像生成模式。</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Upscale failure</source>
        <translation>放大失败</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Upscaled image content</source>
        <translation>放大后的图像内容</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>None</source>
        <translation>无</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Bilinear</source>
        <translation>双线性</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Nearest</source>
        <translation>最邻近</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Hamming</source>
        <translation>Hamming</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Bicubic</source>
        <translation>双三次</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Lanczos</source>
        <translation>Lanczos</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>Box</source>
        <translation>Box</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>{modifier_or_modifiers}: pick color</source>
        <translation>{modifier_or_modifiers}：取色</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>{description}
Keys: {decrease} / {increase}</source>
        <translation>{description}
按键：{decrease} / {increase}</translation>
    </message>
    <message>
        <location filename="../../src/util/shared_text.py"/>
        <source>{description}
Key: {key}</source>
        <translation>{description}
按键：{key}</translation>
    </message>
    <message>
        <source>W:</source>
        <translation type="vanished">宽度：</translation>
    </message>
    <message>
        <source>H:</source>
        <translation type="vanished">高度：</translation>
    </message>
    <message>
        <source>X:</source>
        <translation type="vanished">X:</translation>
    </message>
    <message>
        <source>Y:</source>
        <translation type="vanished">Y:</translation>
    </message>
    <message>
        <source>Width:</source>
        <translation type="vanished">宽度：</translation>
    </message>
    <message>
        <source>Height:</source>
        <translation type="vanished">高度：</translation>
    </message>
    <message>
        <source>Color:</source>
        <translation type="vanished">颜色：</translation>
    </message>
    <message>
        <source>Size:</source>
        <translation type="vanished">大小：</translation>
    </message>
    <message>
        <source>Scale:</source>
        <translation type="vanished">缩放：</translation>
    </message>
    <message>
        <source>Zoom in</source>
        <translation type="vanished">放大</translation>
    </message>
    <message>
        <source>Reset zoom</source>
        <translation type="vanished">重置缩放</translation>
    </message>
    <message>
        <source>Keep aspect ratio</source>
        <translation type="vanished">保持宽高比</translation>
    </message>
    <message>
        <source>The AI image generator is busy creating other images, try again later.</source>
        <translation type="vanished">AI 图像生成器正忙于生成其他图像，请稍后重试。</translation>
    </message>
    <message>
        <source>Describing image</source>
        <translation type="vanished">正在反推提示词</translation>
    </message>
</context>
<context>
    <name>util.translation</name>
    <message>
        <location filename="../../src/util/translation.py"/>
        <source>{language} (machine-translated)</source>
        <translation>{language}（机器翻译）</translation>
    </message>
</context>
<context>
    <name>util.visual.image_format_utils</name>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>OpenRaster project</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>PNG image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>JPEG image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>WebP image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>AVIF image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>GIF image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Animated PNG image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>TIFF image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>BMP image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>BLP texture</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Windows cursor</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>DirectDraw surface</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>DIB image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Apple icon</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Windows icon</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>IFUNC image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>MPO photo</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>PCX image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>PDF document</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Palm pixmap</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>QOI image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>XBM bitmap</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>XPM pixmap</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>JPEG 2000 image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Netpbm image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>SGI image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>TGA image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Photoshop document</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Photo CD image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>FLI/FLC animation</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>FITS image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>SVG image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Intel DCX image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>GIMP brush</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>IPTC/NAA image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>FTEX texture</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Pixar image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>Sun raster image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>MSP image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>PFM image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>WBMP image</source>
        <translation type="unfinished"></translation>
    </message>
    <message>
        <location filename="../../src/util/visual/image_format_utils.py"/>
        <source>{extension} image</source>
        <translation type="unfinished"></translation>
    </message>
</context>
<context>
    <name>util.visual.magic_wand_area</name>
    <message>
        <location filename="../../src/util/visual/magic_wand_area.py"/>
        <source>Connected</source>
        <translation>连续</translation>
    </message>
    <message>
        <location filename="../../src/util/visual/magic_wand_area.py"/>
        <source>By color</source>
        <translation>按颜色</translation>
    </message>
    <message>
        <location filename="../../src/util/visual/magic_wand_area.py"/>
        <source>Holes</source>
        <translation>孔洞</translation>
    </message>
    <message>
        <location filename="../../src/util/visual/magic_wand_area.py"/>
        <source>Select the connected area around the click that matches its color.</source>
        <translation>选择点击处周围与其颜色相符的连续区域。</translation>
    </message>
    <message>
        <location filename="../../src/util/visual/magic_wand_area.py"/>
        <source>Select every pixel in the image that matches the clicked color, connected or not.</source>
        <translation>选择图像中与点击处颜色相符的所有像素，无论是否相连。</translation>
    </message>
    <message>
        <location filename="../../src/util/visual/magic_wand_area.py"/>
        <source>Select the gaps enclosed by the current selection, ignoring image content.</source>
        <translation>选择当前选区包围的空隙，忽略图像内容。</translation>
    </message>
</context>
</TS>
