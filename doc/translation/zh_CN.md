# 简体中文翻译词汇表

本文件为[英文词汇表](glossary.md)中每个词条选定一个简体中文译法，并给出决定、来源与置信度，供未来的翻译和审校使用。来源列是可验证的唯一依据：链接必须存在并实际出现该词；没有来源的主张标注为低置信度。相关流程见 [doc/machine_translation.md](../machine_translation.md)。

This is the Simplified Chinese per-language glossary. It decides one rendering for every term in the [English glossary](glossary.md), with a decision, a source and a confidence level, for translators and reviewers to use. The source column is the only part a monolingual maintainer can verify, so a claim without a source is marked low confidence. The process that uses this file is in [doc/machine_translation.md](../machine_translation.md).

本文件中的所有说明性文字（词条说明、风格、待解决问题等）先以简体中文书写，随后是英文翻译。

All descriptive text in this file (term notes, the style section, the open questions) is written first in Simplified Chinese, then translated into English.

## 图像编辑术语 / Image-editing terms

与 Photoshop、GIMP、Krita 共用的常规词汇，跟随这些软件的中文界面。

General vocabulary shared with Photoshop, GIMP and Krita; per-language glossaries follow those programs' localized UIs.

| English term | 选定译法 Chosen rendering | 决定 Decision | 来源 Source | 置信度 Confidence | 说明 Notes |
| --- | --- | --- | --- | --- | --- |
| Layer | 图层 | 翻译 translate | [kk-layers] | 高 high | 所有中文图形软件通用 / standard in every Chinese graphics program. |
| Layer group | 图层组 | 翻译 translate | [kk-layers] | 高 high | — |
| Active layer | 当前图层 | 翻译 translate | [kk-sel] | 中 medium | 来源页即用「当前图层」/ the source page uses this phrase; 备选「活动图层」/ alternative 活动图层. |
| Isolation (layer group) | 隔离 | 翻译 translate | — | 低 low | Photoshop 同类概念叫「隔离混合」/ PS calls the related concept 隔离混合; 需母语者确认 / needs a native check. |
| Lock, transparency lock | 锁定, 透明像素锁定 | 翻译 translate | — | 低 low | Photoshop 用词；GIMP 中文界面作「锁定透明区域」/ PS zh terms; GIMP zh uses 锁定透明区域. |
| Merge, flatten | 合并, 拼合 | 翻译 translate | [gimp] | 高 high | GIMP 中文手册用于「合并可见图层」「拼合图像」「向下合并」/ these appear in the GIMP zh manual. |
| Canvas | 画布 | 翻译 translate | [kk-images] | 高 high | — |
| Scale (verb) | 缩放 | 翻译 translate | [kk-images] | 高 high | — |
| Crop | 裁剪 | 翻译 translate | [kk-images] | 高 high | 其他软件亦作「裁切」「剪裁」/ other apps also use 裁切 and 剪裁. |
| Selection | 选区 | 翻译 translate | [kk-sel] | 高 high | GIMP 中文同样作「选区」/ same term in GIMP zh. |
| Add, Subtract, Replace, Intersect | 添加, 减去, 替换, 相交 | 翻译 translate | [kk-sel] | 高 high | Krita 中文手册列出这四种模式 / Krita zh lists exactly these four. |
| Opacity | 不透明度 | 翻译 translate | [kk-images] | 高 high | dtlnor 汉化包简作「透明度」/ the dtlnor pack shortens it to 透明度. |
| Hardness | 硬度 | 翻译 translate | [comfy-zh] | 高 high | — |
| Pen pressure | 笔压 | 翻译 translate | — | 低 low | Photoshop 用「钢笔压力」；两者都常见 / PS uses 钢笔压力; both are common. |
| Antialiasing | 抗锯齿 | 翻译 translate | [a1-diffus] | 高 high | 汉化包中已验证 / confirmed in the A1111 zh pack. |
| Blend mode | 混合模式 | 翻译 translate | [kk-layers] | 高 high | 模式名按 Photoshop 中文：Multiply 正片叠底、Screen 滤色、Color Dodge 颜色减淡；Qt 合成名 Source Atop、Destination Out 保留英文 / named modes follow PS zh; Qt composition names stay English. |
| Foreground / background color | 前景色 / 背景色 | 翻译 translate | [kk-sel] | 高 high | 来源页有「填充前景色」/ 填充前景色 appears in the source page. |
| Color picker | 取色器 | 翻译 translate | [comfy-zh] | 中 medium | Photoshop 的工具叫「吸管」；「取色器」更通用 / PS calls the tool 吸管; 取色器 is the generic label. |
| Fill | 填充 | 翻译 translate | [kk-sel] | 高 high | GIMP 中文作「油漆桶填充」/ same concept in GIMP zh. |
| Threshold | 阈值 | 翻译 translate | [gimp-fuzzy] | 高 high | — |
| Sample merged | 合并采样 | 翻译 translate | [gimp-clone] | 中 medium | GIMP 中文旧译「位样合并」，Photoshop 作「对所有图层取样」/ GIMP zh's old term is 位样合并; PS uses 对所有图层取样. |
| Smudge | 涂抹 | 翻译 translate | [gimp] | 高 high | GIMP 中文工具名为「涂抹」/ the GIMP zh tool page uses 涂抹. |
| Clone stamp, source | 仿制图章, 仿制源 | 翻译 translate | [gimp-clone] | 中 medium | GIMP 中文作「克隆」与「源」；Photoshop 称「仿制图章」/ GIMP zh uses 克隆 and 源; PS calls it 仿制图章. |
| Filter | 滤镜 | 翻译 translate | [kk-layers] | 高 high | — |
| Posterize | 色调分离 | 翻译 translate | — | 低 low | Photoshop 中文用词 / term in the PS zh UI; GIMP 中文页未译 / no zh GIMP page found. |
| Scaling algorithms | Nearest 邻近, Bilinear 双线性, Bicubic 双三次 | 翻译 translate | [a1-diffus] | 中 medium | Lanczos、Hamming、Box 是专名，保留拉丁字母 / Lanczos, Hamming, Box are names and stay Latin. |
| Line join | 连接 | 翻译 translate | — | 低 low | 选项按通用叫法：Miter 斜接、Bevel 斜角、Round 圆角 / options: 斜接, 斜角, 圆角; 需复核 / needs a check. |
| Vertex | 顶点 | 翻译 translate | — | 低 low | 常见几何学术语，「Vertex count」作「顶点数」/ standard geometry term; Vertex count = 顶点数. |
| Kerning | 字距调整 | 翻译 translate | [kk-text] | 高 high | Krita 中文手册「字距调整(Kerning)」/ exactly this in Krita zh. |

## Stable Diffusion 术语 / Stable Diffusion terms

Stable Diffusion 社区以及 A1111 WebUI、ComfyUI 界面的词汇。许多此类词通常保留英文或音译；本表先核对社区汉化再做决定。

Vocabulary from the Stable Diffusion community and the A1111 WebUI and ComfyUI interfaces. Many are usually kept in English or transliterated; this table checks community localizations before translating any.

| English term | 选定译法 Chosen rendering | 决定 Decision | 来源 Source | 置信度 Confidence | 说明 Notes |
| --- | --- | --- | --- | --- | --- |
| Image generation, generate | 图像生成, 生成 | 翻译 translate | [a1-dtlnor] | 高 high | 「Generate」按钮作「生成」/ the Generate button is 生成. |
| Inpainting, inpaint | 局部重绘 | 翻译 translate | [a1-terms] | 高 high | dtlnor 术语表明确将 inpaint 定为「局部重绘」/ fixed in the dtlnor terminology sheet. |
| Image to image, text to image | 图生图, 文生图 | 翻译 translate | [a1-terms] | 高 high | 两个汉化包一致 / both zh packs agree. |
| Mask | 蒙版 | 翻译 translate | [a1-dtlnor] | 高 high | ComfyUI 中文作「遮罩」/ ComfyUI zh uses 遮罩; 见待解决问题 / see open questions. |
| Masked content | 蒙版内容 | 翻译 translate | [a1-diffus] | 中 medium | dtlnor 作「重绘参考内容」，diffus-me 作「蒙版蒙住的内容」/ the two packs disagree. |
| Masked content option values: fill, original, latent noise, latent nothing | 填充, 原图, 潜空间噪声, 空白潜空间 | 翻译 translate | [a1-dtlnor] | 中 medium | 是配置文件存储值，暂不翻译 / stored config values, untranslated for now. |
| Prompt | 提示词 | 翻译 translate | [a1-dtlnor] | 高 high | — |
| Negative prompt | 反向提示词 | 翻译 translate | [a1-diffus] | 高 high | dtlnor 作「负面提示词」/ dtlnor uses 负面提示词. |
| Prompt style | 提示词风格 | 翻译 translate | [a1-dtlnor] | 中 medium | 菜单「Styles」可作「风格模版」/ menu label "Styles" → 风格模版. |
| CFG scale | CFG Scale | 保留 keep | [a1-dtlnor] | 高 high | 社区常见译法「提示词相关性(CFG Scale)」；紧凑标签保留英文 / community renders it 提示词相关性(CFG Scale); keep the acronym in the compact label. |
| Steps | 采样步数 | 翻译 translate | [a1-dtlnor] | 中 medium | 汉化包作「采样迭代步数(Steps)」/ packs use 采样迭代步数(Steps). |
| Sampler, sampling method | 采样器, 采样方法 | 翻译 translate | [a1-dtlnor] | 高 high | ComfyUI 中文数据类别同样作「采样器」/ also 采样器 in ComfyUI zh. |
| Scheduler | 调度器 | 翻译 translate | [a1-dtlnor] | 高 high | ComfyUI 中文类别同样作「调度器」/ also 调度器 in ComfyUI zh. |
| Seed | 随机种子 | 翻译 translate | [a1-dtlnor] | 高 high | 「Use a random seed」作「使用随机种子」/ "Use a random seed" = 使用随机种子. |
| Variation seed, variation strength | 差异种子, 差异强度 | 翻译 translate | [a1-dtlnor] | 中 medium | 汉化包作「差异随机种子」/ pack uses 差异随机种子. |
| Denoising strength | 重绘幅度 | 翻译 translate | [a1-dtlnor] | 高 high | 两个包一致；字面「去噪强度」较少见 / both packs agree; literal 去噪强度 is uncommon. |
| Batch size, batch count | 每批数量, 生成批次 | 翻译 translate | [a1-dtlnor] | 中 medium | 「生成批次」与「每批数量」语义接近，社区亦用「批次数」；见待解决问题 / 生成批次 sits close to batch size; see open questions. |
| Model, checkpoint | 模型 | 翻译 translate | [a1-dtlnor] | 高 high | dtlnor 作「主模型」；字面「检查点」会误导 / dtlnor: 主模型; avoid literal 检查点. |
| VAE, tiled VAE | VAE, 分块 VAE | 翻译 translate | [a1-dtlnor] | 高 high | — |
| LoRA | LoRA | 保留 keep | [a1-terms] | 高 high | — |
| LCM mode | LCM 模式 | 保留 keep | — | 低 low | LCM 保留拉丁字母，「mode」作「模式」/ LCM stays Latin; mode = 模式. |
| ControlNet | ControlNet | 保留 keep | [comfy-zh] | 高 high | — |
| ControlNet unit | ControlNet 单元 | 翻译 translate | [a1-dtlnor] | 中 medium | 汉化包作「控制单元」/ the pack uses 控制单元. |
| Preprocessor | 预处理器 | 翻译 translate | [a1-dtlnor] | 高 high | — |
| Control weight | 控制强度 | 翻译 translate | [a1-dtlnor] | 中 medium | 亦作「权重」「控制权重」/ also 权重 or 控制权重. |
| Control step | 起始控制步数, 结束控制步数 | 翻译 translate | [a1-dtlnor] | 中 medium | 汉化包作「控制介入时机」「控制结束时机」/ the pack uses 控制介入/结束时机. |
| Describe | 反推提示词 | 翻译 translate | [a1-dtlnor] | 中 medium | WebUI 的 Interrogate 即「提示词反推」；见待解决问题 / WebUI Interrogate = 提示词反推; see open questions. |
| CLIP skip | CLIP 跳过层 | 翻译 translate | [a1-diffus] | 高 high | — |
| Upscale | 放大 | 翻译 translate | [a1-diffus] | 高 high | Upscaler 作「放大算法」，方法标签作「放大方法」/ upscaler = 放大算法; method = 放大方法. |
| GPU memory, VRAM | 显存 | 翻译 translate | [a1-diffus] | 中 medium | 「Clear GPU memory」作「清理显存」/ "Clear GPU memory" = 清理显存. |
| Restore faces, tiling | 面部修复, 平铺 | 翻译 translate | [a1-dtlnor] | 高 high | 两个汉化包一致 / both zh packs agree. |

## IntraPaint 专有术语 / IntraPaint terms

IntraPaint 赋予自用含义的词，其他软件的中文化无法覆盖，因此自行选定并记录理由。

Words IntraPaint gives its own meaning. No other program's localization covers them, so each rendering is chosen here with its reasoning.

| English term | 选定译法 Chosen rendering | 决定 Decision | 来源 Source | 置信度 Confidence | 说明 Notes |
| --- | --- | --- | --- | --- | --- |
| Generation area | 生成区域 | 翻译 translate | — | 低 low | IntraPaint 专有；备选「生成范围」/ IntraPaint-specific; alternative 生成范围. |
| Generation resolution | 生成分辨率 | 翻译 translate | — | 低 low | — |
| Resolution rule | 分辨率规则 | 翻译 translate | — | 低 low | 选项「Match area 匹配区域、Match area, upscale small areas 匹配区域并放大小区域、Manual 手动」为存储值，暂不翻译 / option strings are stored values. |
| Context | 上下文 | 翻译 translate | — | 低 low | 指局部重绘时纳入周边图像的范围；备选「周边范围」；见待解决问题 / the surrounding image feeding inpaint; see open questions. |
| Context pin | 上下文固定点 | 翻译 translate | — | 低 low | 备选「锚点」；见待解决问题 / alternative 锚点; see open questions. |
| Generated image options | 生成图像选项 | 翻译 translate | — | 低 low | — |
| Image generator | 图像生成器 | 翻译 translate | — | 低 low | — |
| Panel, rail, dock, float | 面板, 面板栏, 停靠, 浮动 | 翻译 translate | — | 低 low | Qt 中文用「停靠」「浮动」；rail 无通用译法；见待解决问题 / rail has no standard term; see open questions. |
| Tool control hints | 工具控制提示 | 翻译 translate | — | 低 low | — |
| Speed modifier | 加速修饰键 | 翻译 translate | — | 低 low | 指按住后使调整更快的修饰键 / a held key that speeds up adjustments. |
| Selection brush | 选区画笔 | 翻译 translate | — | 低 low | — |
| Magic wand | 魔棒 | 翻译 translate | [kk-sel] | 高 high | Krita 中文手册提到某些软件称「魔棒」/ Krita zh mentions 魔棒. |
| Fit box, fit font | 适应框, 适应字号 | 翻译 translate | — | 低 low | 文字工具专用 / text tool specific. |
| Saved colors | 已保存颜色 | 翻译 translate | — | 低 low | — |

## 保留原文的名称 / Names kept as they are

产品、格式、模型或色彩模型名称，一律保留拉丁字母。

These product, format, model and color-model names stay in Latin script.

- 产品与后端 / Products and backends: IntraPaint, Stable Diffusion, ComfyUI, WebUI, Automatic1111 (A1111), Forge, GLID-3-XL, MyPaint, libmypaint, Qt.
- 模型与技术名 / Model and technique names: CLIP, BERT, VAE, LoRA, LCM, CFG, ControlNet, Ultimate SD Upscale.
- 格式与色彩模型 / Formats and color models: OpenRaster (`.ora`), PNG, RGB, RGBA, HSV, OKLCH, sRGB.
- 界面主题名 / Interface theme names: 例如「IntraPaint Ink」/ for example "IntraPaint Ink".

## 需要上下文才能翻译的字符串 / Strings that need context

- 英文里名词/动词同形的词（Fill、Clear、Select、Transform、Stroke、Invert 等）在中文中名词、动词同形（填充、清除、选择、变换、描边、反转），歧义大多消失；仍要在代码上下文里确认整体语义。中文中的对应词：填充、清除、选择、滤镜、变换、描边、描画、反转、浮动、停靠、绘画、绘制、擦除、合并的。English noun/verb pairs use the same Chinese word, so the ambiguity mostly disappears; check the code context anyway for the compound's sense.
- 存储值：编辑模式、「Masked content」的值、分辨率规则等同时是配置文件保存的值，在 #297 修复前不出现在翻译文件中。Stored config option values stay out of translation files until #297 is fixed.
- 单位与短标签：px、pt、deg、x 以及 W:、H:、X:、R、G、B、H、S、V、L、C 保留拉丁字母。Unit and short labels stay Latin.

## 翻译风格 / Style

- 简体中文（zh_CN），与繁体（zh_TW）用词区分，优先采用中国大陆软件界用语（图层、选区、图像，而非图層、選取範圍、影像）。
- Simplified Chinese (zh_CN), distinct from Traditional Chinese (zh_TW); prefer mainland Chinese software wording (图层, 选区, 图像 over 圖層, 選取範圍, 影像).
- 语气中性直陈；按钮用短语动词，不加句末标点（保存、取消、删除）。
- Neutral declarative tone; buttons are verb phrases with no trailing punctuation (保存, 取消, 删除).
- 中文句内用全角标点（，。：）；标签不以标点结尾；拉丁字母、数字与中文之间加半角空格（如「采样步数 80」）。Numbers and Latin text keep half-width characters; put a half-width space between Latin and Chinese.
- 中文无大小写规则；菜单、对话框、面板标题与标签的措辞照各软件惯例（标题更完整，标签更短）。Chinese has no capitalization; follow each program's conventions for titles vs labels.

## 待解决问题 / Open questions

以下是未来以中文为母语的审校者应最先核对的项目。

These are the first things a native-speaking reviewer should check.

- 蒙版 vs 遮罩：IntraPaint 的蒙版就是选区。A1111 中文和 Photoshop 用「蒙版」，ComfyUI 中文用「遮罩」，选哪个？/ Mask vs 遮罩: IntraPaint's mask *is* the selection; A1111 zh and Photoshop use 蒙版, ComfyUI zh uses 遮罩. Which?
- 反向提示词 vs 负面提示词：两个 A1111 汉化包各用一个。/ Negative prompt: 反向提示词 (diffus-me) vs 负面提示词 (dtlnor). Which?
- 生成批次 vs 批次数：汉化包用「生成批次」，社区教程常用「批次数」，与「每批数量」并列时哪个更清晰？/ Batch count: 生成批次 (both packs) vs 批次数 (common in tutorials). Which reads clearest next to 每批数量?
- Describe 描述 vs 反推提示词：IntraPaint 为与后端解耦而改名 Describe，但社区熟知的 WebUI 功能叫「提示词反推」。/ The WebUI feature is known to the community as 反推提示词, but IntraPaint renamed it "Describe".
- Context：译为「上下文」还是「周边范围」？Context pin 用「固定点」还是「锚点」？/ Context: 上下文 vs 周边范围; pin: 固定点 vs 锚点.
- Rail（面板栏）：View 菜单里标签面板条没有通用中文名，是否需要新造词？/ Rail: no standard Chinese term for the edge strip of panel tabs; invent one?

[kk-layers]: https://docs.krita.org/zh_CN/user_manual/layers_and_masks.html
[kk-sel]: https://docs.krita.org/zh_CN/user_manual/selections.html
[kk-images]: https://docs.krita.org/zh_CN/user_manual/working_with_images.html
[kk-text]: https://docs.krita.org/zh_CN/reference_manual/dockers/text_properties.html
[gimp]: https://docs.gimp.org/2.10/zh_CN/
[gimp-clone]: https://docs.gimp.org/2.10/zh_CN/gimp-tool-clone.html
[gimp-fuzzy]: https://docs.gimp.org/2.10/zh_CN/gimp-tool-fuzzy-select.html
[a1-dtlnor]: https://github.com/dtlnor/stable-diffusion-webui-localization-zh_CN/blob/Anne/localizations/zh_CN.json
[a1-diffus]: https://github.com/diffus-me/stable-diffusion-webui-localization/blob/main/zh_CN.json
[a1-terms]: https://github.com/dtlnor/stable-diffusion-webui-localization-zh_CN/blob/Anne/Terminology.md
[comfy-zh]: https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/locales/zh/main.json
