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
| Active layer | 当前图层 | 翻译 translate | [kk-sel] | 中 medium | 来源页即用「当前图层」；GIMP 中文界面混用「激活图层」和「活动图层」/ the source page uses 当前图层; GIMP's zh UI mixes 激活图层 and 活动图层. |
| Isolation (layer group) | 隔离 | 翻译 translate | — | 低 low | Photoshop 同类概念叫「隔离混合」；Krita 中文手册把相反的设置称为图层组的「穿透模式」([kk-layers])；需母语者确认 / PS calls the related concept 隔离混合; the Krita zh manual calls the opposite group setting 穿透模式 (pass-through mode) ([kk-layers]); needs a native check. |
| Lock, transparency lock | 锁定, 锁定透明区域 | 翻译 translate | [ps-blend] | 中 medium | Photoshop 中文帮助作「锁定透明区域」，GIMP 中文界面作「锁定透明通道」([gimp-po]) / the Photoshop zh help uses 锁定透明区域 and GIMP's zh UI uses 锁定透明通道 ([gimp-po]). |
| Merge, flatten | 合并, 拼合 | 翻译 translate | [gimp-po] | 中 medium | GIMP 中文界面有「向下合并」「合并可见图层」，Flatten Image 作「平整图像」；IntraPaint 的「Flatten layer」把单个图层的活状态折叠为静态像素：组先折叠子图层再合并为一个图像图层，文字栅格化，混合模式与不透明度归位并相应调整像素，旋转缩放应用到像素。「拼合」跟随 Photoshop 的「拼合图像」；IntraPaint 没有全图拼合操作，「拼合图层」不会混淆；「栅格化」只覆盖文字一步 / GIMP's zh UI has 向下合并 and 合并可见图层, and renders Flatten Image as 平整图像; IntraPaint's "Flatten layer" collapses one layer's live state into static pixels: a group's children are each collapsed and then merged into one image layer, text rasterizes, blend mode and opacity reset with the pixels adjusted, and rotation and scale apply at the pixel level. 拼合 follows Photoshop's 拼合图像; IntraPaint has no whole-image flatten for 拼合图层 to be confused with, and 栅格化 (rasterize) would cover only the text step. |
| Canvas | 画布 | 翻译 translate | [kk-images] | 高 high | — |
| Scale (verb) | 缩放 | 翻译 translate | [kk-images] | 高 high | — |
| Crop | 裁剪 | 翻译 translate | [kk-images] | 高 high | 其他软件亦作「裁切」「剪裁」/ other apps also use 裁切 and 剪裁. |
| Selection | 选区 | 翻译 translate | [kk-sel] | 高 high | GIMP 中文同样作「选区」/ same term in GIMP zh. |
| Add, Subtract, Replace, Intersect | 添加, 减去, 替换, 相交 | 翻译 translate | [kk-sel] | 高 high | Krita 中文手册列出这四种模式 / Krita zh lists exactly these four. |
| Opacity | 不透明度 | 翻译 translate | [kk-images] | 高 high | GIMP 和 dtlnor 汉化包同样作「不透明度」；diffus-me 汉化包简作「透明度」/ GIMP and the dtlnor pack also use 不透明度; the diffus-me pack shortens it to 透明度. |
| Hardness | 硬度 | 翻译 translate | [comfy-zh] | 高 high | — |
| Pen pressure | 笔压 | 翻译 translate | — | 低 low | 未找到使用「笔压」的可链接来源；Photoshop 中文帮助作「钢笔压力」([ps-pressure])，GIMP 中文界面作「压力」/ no linkable source found for 笔压; the Photoshop zh help uses 钢笔压力 ([ps-pressure]) and GIMP's zh UI uses 压力. |
| Antialiasing | 抗锯齿 | 翻译 translate | [a1-diffus] | 高 high | 汉化包中已验证 / confirmed in the A1111 zh pack. |
| Blend mode | 混合模式 | 翻译 translate | [kk-layers] | 高 high | 模式名按 Photoshop 中文帮助 ([ps-blend])：Multiply 正片叠底、Screen 滤色、Color Dodge 颜色减淡；Qt 合成名 Source Atop、Destination Out 保留英文 / named modes follow the Photoshop zh help ([ps-blend]); Qt composition names stay English. |
| Foreground / background color | 前景色 / 背景色 | 翻译 translate | [kk-sel] | 高 high | 来源页有「填充前景色」/ 填充前景色 appears in the source page. |
| Color picker | 取色器 | 翻译 translate | [comfy-zh] | 中 medium | Photoshop 的工具叫「吸管」([ps-eyedropper])，GIMP 中文界面作「颜色拾取」；「取色器」更通用 / PS calls the tool 吸管 ([ps-eyedropper]) and GIMP's zh UI uses 颜色拾取; 取色器 is the generic label. |
| Fill | 填充 | 翻译 translate | [kk-sel] | 高 high | GIMP 中文作「油漆桶填充」/ same concept in GIMP zh. |
| Threshold | 阈值 | 翻译 translate | [gimp-fuzzy] | 高 high | — |
| Sample merged | 合并采样 | 翻译 translate | — | 低 low | 未找到使用「合并采样」的来源；GIMP 中文作「位样合并」([gimp-clone])，Photoshop 的取样选项作「所有图层」([ps-clone]) / no source found that uses 合并采样; GIMP zh uses 位样合并 ([gimp-clone]) and Photoshop's sample option is 所有图层 ([ps-clone]). |
| Smudge | 涂抹 | 翻译 translate | [gimp-po] | 高 high | GIMP 中文工具名为「涂抹」/ the GIMP zh tool name is 涂抹. |
| Clone stamp, source | 仿制图章, 源 | 翻译 translate | [ps-clone] | 中 medium | Photoshop 中文帮助作「仿制图章工具」和「克隆源」面板；GIMP 中文作「克隆」与「源」([gimp-clone]) / the Photoshop zh help uses 仿制图章工具 and the 克隆源 panel; GIMP zh uses 克隆 and 源 ([gimp-clone]). |
| Filter | 滤镜 | 翻译 translate | [kk-layers] | 高 high | — |
| Posterize | 色调分离 | 翻译 translate | — | 低 low | Photoshop 中文用词，未找到可链接的来源；GIMP 中文界面作「色相分离」，字面上指色相，含义不准 / the PS zh term, with no linkable source found; GIMP's zh UI uses 色相分离, which literally names hue and misdescribes the filter. |
| Scaling algorithms | Nearest 最邻近, Bilinear 双线性, Bicubic 双三次 | 翻译 translate | [a1-dtlnor] | 中 medium | dtlnor 汉化包作「最邻近」「双线性」「双立方」；「双三次」是数学文献中更常见的叫法，需母语者确认；Lanczos、Hamming、Box 是专名，保留拉丁字母 / the dtlnor pack uses 最邻近, 双线性 and 双立方; 双三次 is the more common term in technical writing and needs a native check; Lanczos, Hamming and Box are names and stay Latin. |
| Line join | 接合 | 翻译 translate | [gimp-po] | 中 medium | 跟随 GIMP 中文界面「接合样式」「斜接」「倒角连接」：Miter 斜接、Bevel 倒角、Round 圆角 / follows GIMP's zh UI (接合样式, 斜接, 倒角连接): Miter 斜接, Bevel 倒角, Round 圆角. |
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
| Mask | 蒙版 | 翻译 translate | [a1-dtlnor] | 高 high | 两个 A1111 汉化包、Photoshop 和 Krita 都用「蒙版」；ComfyUI 中文界面以「遮罩」为主（编辑器标题作「遮罩编辑器」），也混用「蒙版编辑器」/ both A1111 packs, Photoshop and Krita use 蒙版; ComfyUI's zh UI is predominantly 遮罩 (its editor is titled 遮罩编辑器), mixing in 蒙版编辑器 strings. |
| Masked content | 蒙版内容 | 翻译 translate | — | 低 low | 由 diffus-me 的「蒙版蒙住的内容」缩短而来，两个汉化包都没有「蒙版内容」；dtlnor 作「重绘参考内容」/ shortened from diffus-me's 蒙版蒙住的内容, so neither pack uses 蒙版内容 itself; dtlnor uses 重绘参考内容. |
| Masked content option values: fill, original, latent noise, latent nothing | 填充, 原图, 潜空间噪声, 空白潜空间 | 翻译 translate | [a1-diffus], [a1-dtlnor] | 中 medium | 「填充」「原图」取自 diffus-me，「潜空间噪声」「空白潜空间」取自 dtlnor；是配置文件存储值，#297 修复前暂不翻译 / 填充 and 原图 come from diffus-me, 潜空间噪声 and 空白潜空间 from dtlnor; these are stored config values, untranslated until #297 is fixed. |
| Prompt | 提示词 | 翻译 translate | [a1-dtlnor] | 高 high | — |
| Negative prompt | 负面提示词 | 翻译 translate | [a1-dtlnor], [kad-zh] | 高 high | dtlnor 汉化包和 krita-ai-diffusion 中文界面都作「负面提示词」，教程与术语站多用同词；diffus-me 作「反向提示词」/ the dtlnor pack and krita-ai-diffusion's zh UI both use 负面提示词, as do most tutorials and glossaries; diffus-me uses 反向提示词. |
| Prompt style | 风格模板 | 翻译 translate | [a1-dtlnor] | 中 medium | dtlnor 汉化包作「风格模版」，diffus-me 作「模板风格」；「模板」是规范写法 / the dtlnor pack writes 风格模版 and diffus-me 模板风格; 模板 is the standard spelling of the 模版 variant. |
| CFG scale | CFG Scale | 保留 keep | [a1-dtlnor] | 高 high | 社区常见译法「提示词相关性(CFG Scale)」；紧凑标签保留英文 / community renders it 提示词相关性(CFG Scale); keep the acronym in the compact label. |
| Steps | 采样步数 | 翻译 translate | [a1-dtlnor] | 中 medium | 汉化包作「采样迭代步数(Steps)」/ packs use 采样迭代步数(Steps). |
| Sampler, sampling method | 采样器, 采样方法 | 翻译 translate | [a1-dtlnor] | 高 high | ComfyUI 中文数据类别同样作「采样器」/ also 采样器 in ComfyUI zh. |
| Scheduler | 调度器 | 翻译 translate | [a1-dtlnor] | 高 high | ComfyUI 中文类别同样作「调度器」/ also 调度器 in ComfyUI zh. |
| Seed | 随机种子 | 翻译 translate | [a1-dtlnor] | 高 high | 「Use a random seed」作「使用随机种子」/ "Use a random seed" = 使用随机种子. |
| Variation seed, variation strength | 差异种子, 差异强度 | 翻译 translate | [a1-dtlnor] | 中 medium | 汉化包作「差异随机种子」/ pack uses 差异随机种子. |
| Denoising strength | 重绘幅度 | 翻译 translate | [a1-dtlnor] | 高 high | 两个包一致；字面「去噪强度」较少见 / both packs agree; literal 去噪强度 is uncommon. |
| Batch size, batch count | 每批数量, 生成批次 | 翻译 translate | [a1-dtlnor], [a1-diffus] | 高 high | 两个汉化包一致，正是 WebUI 中文用户现在读到的搭配；ComfyUI 中文作「批次数量」，教程亦见「批次数」/ both packs agree, which is the pairing WebUI zh users read today; ComfyUI zh uses 批次数量 and tutorials also write 批次数. |
| Model, checkpoint | 模型 | 翻译 translate | [a1-dtlnor] | 高 high | dtlnor 作「主模型」；字面「检查点」会误导 / dtlnor: 主模型; avoid literal 检查点. |
| VAE, tiled VAE | VAE, 分块 VAE | 翻译 translate | [a1-dtlnor] | 高 high | — |
| LoRA | LoRA | 保留 keep | [a1-terms] | 高 high | — |
| LCM mode | LCM 模式 | 保留 keep | — | 低 low | LCM 保留拉丁字母，「mode」作「模式」/ LCM stays Latin; mode = 模式. |
| ControlNet | ControlNet | 保留 keep | [comfy-zh] | 高 high | — |
| ControlNet unit | 控制单元 | 翻译 translate | [a1-dtlnor] | 高 high | 汉化包把「ControlNet Unit 0」译作「控制单元 0」/ the pack renders "ControlNet Unit 0" as 控制单元 0. |
| Preprocessor | 预处理器 | 翻译 translate | [a1-dtlnor] | 高 high | — |
| Control weight | 控制强度 | 翻译 translate | [a1-dtlnor] | 中 medium | 亦作「权重」「控制权重」/ also 权重 or 控制权重. |
| Control step | 控制介入时机, 控制结束时机 | 翻译 translate | [a1-dtlnor] | 中 medium | 汉化包用词；该值是步数的比例而非步数，「时机」比「步数」更贴切 / the pack's terms; the value is a fraction of the steps, not a step count, so 时机 (timing) fits better than 步数. |
| Describe | 反推提示词 | 翻译 translate | [a1-diffus] | 中 medium | diffus-me 作「反推提示词」，dtlnor 作「提示词反推」；「Describe」这个改名只针对英文，中文沿用社区熟悉的「反推」/ diffus-me uses 反推提示词 and dtlnor 提示词反推; the "Describe" rename is English-specific, so Chinese keeps the community's familiar 反推 term. |
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
| Context | 周边范围 | 翻译 translate | — | 低 low | 局部重绘时生成器看到的选区周边图像，滑块以「whole area」收尾；「上下文」偏文字语境，也与本文件「需要上下文才能翻译的字符串」撞词；WebUI「Only masked padding」的汉化「预留像素」（两个汉化包一致）只指边距，盖不住整档 / the image around the selection that the generator sees while inpainting, with the slider ending at "whole area"; 上下文 reads as textual context and collides with this file's own "strings that need context" wording, and the WebUI packs' 预留像素 for "Only masked padding" names only the pixel margin, not the whole range. |
| Context pin | 周边范围锚点 | 翻译 translate | — | 低 low | 「锚点」是图形软件常见词（如 Photoshop 的锚点工具），「固定点」少见 / 锚点 (anchor point) is a common graphics term (Photoshop's anchor-point tools, for example); 固定点 is not. |
| Generated image options | 生成图像选项 | 翻译 translate | — | 低 low | — |
| Image generator | 图像生成器 | 翻译 translate | — | 低 low | — |
| Panel, rail, dock, float | 面板, 面板栏, 停靠, 浮动 | 翻译 translate | — | 低 low | Qt 中文用「停靠」「浮动」；rail 无通用译法，「面板栏」沿用「菜单栏」「工具栏」「状态栏」的构词，与 VS Code 中文给边缘条起的「活动栏」同类 / Qt zh uses 停靠 and 浮动; rail has no standard term, and 面板栏 follows the 菜单栏/工具栏/状态栏 word family, like VS Code zh's 活动栏 for its edge strip. |
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

- 名词/动词同形的英文词：Fill、Clear、Select、Transform、Stroke、Invert、Float、Dock 等在中文里名词、动词通常同形（填充、清除、选择、变换、描边、反转、浮动、停靠），但 Filter 不同：名词是「滤镜」，动词（筛选列表）是「筛选」或「过滤」；Outline 作名词是「轮廓」，作动词是「描边」。翻译前仍要查看代码上下文。
  English noun/verb words: Fill, Clear, Select, Transform, Stroke, Invert, Float, Dock and similar usually take one Chinese word for both (填充, 清除, 选择, 变换, 描边, 反转, 浮动, 停靠), but Filter differs: the noun is 滤镜 and the verb (filtering a list) is 筛选 or 过滤; Outline as a noun is 轮廓 and as a verb 描边. Check the code context before translating.
- 存储值：编辑模式、「Masked content」的值、分辨率规则等同时是配置文件保存的值，在 #297 修复前不出现在翻译文件中。
  Stored values: the edit modes, the "Masked content" values, the resolution rules and similar options are also values saved in config files, and stay out of translation files until #297 is fixed.
- 单位与短标签：px、pt、deg、x 以及 W:、H:、X:、R、G、B、H、S、V、L、C 保留拉丁字母。
  Unit and short labels: px, pt, deg, x and W:, H:, X:, R, G, B, H, S, V, L, C stay in Latin script.

## 翻译风格 / Style

- 简体中文（zh_CN），与繁体（zh_TW）用词区分，优先采用中国大陆软件界用语（图层、选区、图像，而非图層、選取範圍、影像）。
- Simplified Chinese (zh_CN), distinct from Traditional Chinese (zh_TW); prefer mainland Chinese software wording (图层, 选区, 图像 over 圖層, 選取範圍, 影像).
- 语气中性直陈；按钮用短语动词，不加句末标点（保存、取消、删除）。
- Neutral declarative tone; buttons are verb phrases with no trailing punctuation (保存, 取消, 删除).
- 中文句内用全角标点（，。：）；拉丁字母和数字保持半角，与中文之间加半角空格（如「采样步数 80」）。
- Chinese sentences use full-width punctuation (，。：); Latin letters and digits stay half-width, with a half-width space between them and Chinese text (for example 采样步数 80).
- 以冒号结尾的英文标签（「Opacity:」）译文以全角冒号结尾（「不透明度：」），与 GIMP 中文界面一致；其他标签不加句末标点。
- An English label that ends in a colon ("Opacity:") ends in a full-width colon in Chinese (不透明度：), as in GIMP's zh UI; other labels take no trailing punctuation.
- 菜单快捷字母（「Sl&iders」中的 &）按中文软件惯例放在译文末尾的括号里：「滑块(&I)」。
- Menu accelerators (the & in "Sl&iders") follow the Chinese software convention of a bracketed letter after the translation: 滑块(&I).
- 中文无大小写规则；菜单、对话框、面板的标题措辞可以更完整，标签更短，与各软件惯例一致。
- Chinese has no capitalization; menu, dialog and panel titles can be worded more fully and labels more briefly, following each program's conventions.

## 待解决问题 / Open questions

目前没有待解决问题；先前的问题都已在各自词条中决定。母语审校者请先复核低置信度词条，以及标注「需母语者确认」的说明（如 Isolation「隔离」、Bicubic「双三次」）。

No questions are open; the earlier ones are decided in their rows. A native-speaking reviewer should first re-check the low-confidence rows and the notes marked "needs a native check" (such as Isolation 隔离 and Bicubic 双三次).

[kk-layers]: https://docs.krita.org/zh_CN/user_manual/layers_and_masks.html
[kk-sel]: https://docs.krita.org/zh_CN/user_manual/selections.html
[kk-images]: https://docs.krita.org/zh_CN/user_manual/working_with_images.html
[kk-text]: https://docs.krita.org/zh_CN/reference_manual/dockers/text_properties.html
[gimp-po]: https://github.com/GNOME/gimp/blob/master/po/zh_CN.po
[gimp-clone]: https://docs.gimp.org/2.10/zh_CN/gimp-tool-clone.html
[gimp-fuzzy]: https://docs.gimp.org/2.10/zh_CN/gimp-tool-fuzzy-select.html
[ps-blend]: https://helpx.adobe.com/cn/photoshop/using/blending-modes.html
[ps-clone]: https://helpx.adobe.com/cn/photoshop/using/retouching-repairing-images.html
[ps-eyedropper]: https://helpx.adobe.com/cn/photoshop/using/choosing-colors.html
[ps-pressure]: https://helpx.adobe.com/cn/photoshop/using/painting-tools.html
[a1-dtlnor]: https://github.com/dtlnor/stable-diffusion-webui-localization-zh_CN/blob/Anne/localizations/zh_CN.json
[a1-diffus]: https://github.com/diffus-me/stable-diffusion-webui-localization/blob/main/zh_CN.json
[a1-terms]: https://github.com/dtlnor/stable-diffusion-webui-localization-zh_CN/blob/Anne/Terminology.md
[comfy-zh]: https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/locales/zh/main.json
[kad-zh]: https://github.com/Acly/krita-ai-diffusion/blob/main/ai_diffusion/language/zh-cn.json
