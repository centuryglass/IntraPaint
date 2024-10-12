# Stable-Diffusion Image Generation Controls

This guide covers the controls IntraPaint provides for AI image generation.  To access these controls, first install and configure Stable-Diffusion following instructions [here](../README.md#ai-setup-stable-diffusion), and activate it in the [generator selection window](./menu_options.md#image-generator-selection-window).

---
## Table of Contents
1. [Image Generation Panel](#image-generation-panel)
2. [ControlNet Panel](#controlnet-panel)
3. [Prompt control formatting](#prompt-control-formatting)
4. [Denoising strength comparisons](#denoising-strength-comparisons)
5. [Sampling methods](#sampling-methods)
---

## Image Generation Panel
This panel is the main place where you'll control image generation.

<img src="./labeled_screenshots/gen_panel.png" alt="Screenshot of the image generation panel, with specific elements numbered."/>

1. **Image generation tab**: Show or hide the generate panel, or move it to any of the window tab bars.  When inactive or minimized, a smaller generate button will be added to the toolbar.
2. **"Edit mode" dropdown**: Switch between the three main image generation modes:
   - **Inpaint**: Only selected content in the image generation area is changed.
   - **Image to Image**: The entire image generation area is changed, but previous image content affects the new image.
   - **Text to Image**: Previous image content is ignored, a new image is generated using only prompt data and other settings.
3. **"Sampling method" dropdown**: Selects between different mathematical approaches to dividing the image generation process into steps.  The differences between these can be subtle, see [sampling methods](#sampling-methods) below for more details.
4. **"Masked content" dropdown**: Controls how selected areas are processed when inpainting, usually best left unchanged. Available options:
    - **original**: Make no changes to inpainting content before generating. This is the best option in most circumstances.
    - **fill**:  Fill the inpainting selection with a solid color before generating. This is sometimes useful when trying to completely remove elements, but is usually best done manually with the brush tool.
    - **latent noise**:  Fill the inpainting selection with random noise before generating.  When used with denoising strength set around 0.7-0.8, this can be useful for filling in empty space around an existing image.
    - **latent nothing**:  Completely zeroes out the inpainting content before generating.
5. **Prompt**: Describe in plain text exactly what kind of imagery the model should generate. Prompts can also use various control formats to affect image generation, see [prompt control formatting](#prompt-control-formatting) below for details.
6. **Negative Prompt**: Describe in plain text exactly what kind of imagery the model should *not* generate. All prompt control formats also work on the negative prompt.
7. **Generation size**: The resolution of generated images.  Most Stable-Diffusion models can be somewhat flexible with this, but usually provide best performance at specific resolutions. See also: [generation resolution tips](./inpainting_guide.md#generation-resolution-tips)
8. **Batch size**:  The number of images to generate at once.  Generating multiple images at the same time can be faster, but requires more VRAM.
9. **Batch count**: The number of image batches to generate in sequence before switching to the selection view. This doesn't increase VRAM usage like batch size does, but it provides no speed benefits compared to generating batches individually.
10. **Sampling steps**: Controls how many steps the generator takes to create images. Increasing step count makes image generation take longer, but often provides better results.  Benefits of increasing step count are usually fairly low above 30 steps. Certain specialty models (e.g. LCM and Turbo) can produce good results at far fewer steps.
11. **Guidance scale**: Controls how strongly the generator will follow the prompt. Low values produce more random imagery, while high values de-prioritize image composition to focus more on exactly matching the AI model's understanding of your prompt.  Values in the 6-12 range usually produce the best results.
12. **Denoising strength**: In "Inpaint" and "Image to Image" modes, this controls exactly how much of the source image the AI generator will include in its output. See [denoising strength comparisons](#denoising-strength-comparisons) below for examples.
13. **"Inpaint Full Resolution" checkbox**:  When inpainting, crop to selected content within the generated area, increasing detail quality at the cost of situational awareness. Refer to the [inpainting guide](./inpainting_guide.md) for more details about using this effectively.
14. **"Inpaint Full Resolution" padding slider**:  When "inpaint full resolution" is checked, this controls how much extra padding space is left around selected content when cropping for inpainting. This allows you to finely balance the trade-offs between detail quality and situational awareness.
15. **"Seed" input**: A number used to control randomness during image generation.  If all other factors are unchanged, using the same seed value should produce the same images each time. If set to -1, a different random seed will be used each time you generate images.
16. **Last seed value**: Holds the seed used the last time the generate button was pressed.
17. **Interrogate button**: Use AI image analysis to automatically generate a description of the edited image.
18. **Generate button**: Click to trigger AI image generation, creating or altering image content to insert into the [image generation area](./inpainting_guide.md#generation-area). Clicking this will switch IntraPaint to the [generated image selection view](./controls.md#generated-image-selection-view).

---

## ControlNet Panel

[ControlNet](https://github.com/lllyasviel/ControlNet) is an add-on for Stable-Diffusion that lets you restrict image generation in useful ways, usually by forcing it to not change parts of a source image.  The first three examples under [this section of the README](../README.md#why-combine-ai-and-traditional-tools) all use the ControlNet sketch module to preserve initial image composition.


If the ControlNet tab isn't visible or isn't working properly, refer to [this section of the FAQ](../README.md#q-where-are-the-controlnet-options).


ControlNet works with two components: a pre-processing **module**, and an AI **model**. The module identifies the elements that need to be preserved, and the model forces stable-diffusion to preserve those elements.  Not all modules and models are compatible, but it's usually obvious from their names which ones are meant to be used together.
The wide variety of ControlNet models and modules available can be challenging to sort through, but I've found [this guide](https://education.civitai.com/civitai-guide-to-controlnet/#what-do-the-models-do) to be extremely helpful for sorting through them all.

<img src="./labeled_screenshots/controlnet_panel.png" alt="Screenshot of the ControlNet panel, with specific elements numbered."/>

1. **ControlNet tab**: Show or hide the generate panel, or move it to any of the window tab bars.
2. **ControlNet unit tabs**: Up to three different ControlNet units can be used at once. These tabs let you switch between the three and configure them independently.
3. **"Enable ControlNet Unit" checkbox**: Enable or disable the current ControlNet unit.
4. **"Low VRAM" checkbox**: Systems with limited VRAM might fail to generate images with ControlNet active. Selecting this option will fix some of these issues, but may also slow down image generation.
5. **"Pixel Perfect" checkbox**: Enables hidden automatic size adjustments to improve ControlNet results. In most cases, it's probably best to just keep this checked.
6. **"Generation Area as Control" checkbox**: Most ControlNet modules need an initial image to function. If this box is checked, the contents of the image generation area will be used.
7. **"Set Control Image" button**: This button lets you select a separate image file to use as the control image.
8. **Control image file path**: Shows the path of the selected control image, if any.
9. **"Control Type" dropdown**:  An optional dropdown that lets you limit module and model dropdowns to a few useful presets.  This option won't be available if you're using the Forge WebUI to handle Stable-Diffusion.
10. **"Control Module" dropdown**: Selects the pre-processing module used to prepare the control image for use.
11. **"Control Model" dropdown**: Selects the control model used to guide image generation.
12. **"Control Weight" slider**: Controls how strictly the model will guide image generation. 1.0 is the default value, lower values decrease the effect of ControlNet.
13. **"Starting Control Step" slider**: Sets the step in the image generation process where ControlNet is activated, as a fraction of the total step count.  The default is 0.0, which starts ControlNet before the first.
14. **"Ending Control Step" slider**: Sets the step in the image generation process where ControlNet is deactivated, as a fraction of the total step count.  The default is 1.0, which starts the process at the first step.
15. **Possible extra model/module controls**: Some modules or models might add extra controls. If they do, those will be shown here.


---
## Prompt control formatting:
Prompt text can be formatted in various ways to control its behavior. These controls are provided by the [Automatic1111 webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Features) and can be altered by various webui extensions.

| Control             | Example                                             | Description                                                                                                                                                |
|---------------------|-----------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Boost attention     | `red and (blue)`                                    | `blue` is treated as 1.1x more important                                                                                                                   |
| Decrease attention  | `cat and [dog]`                                     | `dog` is treated as 1.1x less important                                                                                                                    |
| Precise attention   | `(field:2.0) of (flowers:0.5)`                      | `field` is prioritized 4x more than `flowers`                                                                                                              |
| Literal characters  | `special characters \(\)\[\]`                       | Bracket characters are taken literally, and don't affect attention                                                                                         |
| Prompt editing      | `blue sky, [painting:photograph:8]`                 | After eight steps, the prompt switches from `painting` to `photograph`                                                                                     |
| Alternating prompts | `a friendly [dog\|cat]`                             | Switch between `dog` and `cat` after each image generation step                                                                                            |
| Composable prompts  | `photograph of a house:0.5 AND charcoal sketch:1.0` | Sections split by AND are treated as individual prompts, to be applied simultaneously. The numbers at the end control how much that prompt is prioritized. |



## Denoising strength comparisons
The examples below were created by applying increasing denoising strengths to a small elliptical area within an AI-generated image using inpainting mode. All other parameters remain the same for each option.

| Strength       | Example                                                                    | Description                                                                                                                                                                                                                                                                                                                                                                  |
|----------------|----------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 0.0 (unedited) | ![0.0 denoising strength example](../examples/denoising/denoising_0.png)   | At zero denoising strength, inpainting and image to image do nothing at all.                                                                                                                                                                                                                                                                                                 |
| 0.1            | ![0.1 denoising strength example](../examples/denoising/denoising_0.1.png) | Only the tiniest changes are visible. Because the image is inpainted at a higher resolution than it was originally generated at, even this strength shows slight improvements in details.                                                                                                                                                                                    |
| 0.2            | ![0.2 denoising strength example](../examples/denoising/denoising_0.2.png) | Changes increase in strength, but are still minimal. Some details are improved, but others actually look slightly worse, as the generator has enough leeway to emphasize them but not enough to fix them. This is the lowest strength I regularly use, mostly when editing areas where I want only very slight corrections                                                   |
| 0.3            | ![0.3 denoising strength example](../examples/denoising/denoising_0.3.png) | The original image was generated with the base Stable-Diffusion 1.5 model, but the inpainting is using the fine-tuned [CyberRealistic model](https://huggingface.co/cyberdelia/CyberRealistic/tree/main).  The difference in realism between the two models starts to become apparent at this step.                                                                          |
| 0.4            | ![0.4 denoising strength example](../examples/denoising/denoising_0.4.png) | The most significant errors have been corrected, but overall composition is still mostly the same. This is the strength I usually for refining sketches and rough details.                                                                                                                                                                                                   |
| 0.5            | ![0.5 denoising strength example](../examples/denoising/denoising_0.5.png) | Original image content and new image content are roughly equal in weight. The broad details are still the same, but individual elements start to move from their former places.                                                                                                                                                                                              |
| 0.6            | ![0.6 denoising strength example](../examples/denoising/denoising_0.6.png) | New content starts to outweigh old content. This strength is good for fixing significant errors like malformed limbs.                                                                                                                                                                                                                                                        |
| 0.7            | ![0.7 denoising strength example](../examples/denoising/denoising_0.7.png) | Content sharply diverges from the original. The need to follow the prompt (some variant of "bonsai, cabinet of curiosities in the ancient archives") now outweighs the need to make changes fit in with the old image content.                                                                                                                                               |
| 0.8            | ![0.8 denoising strength example](../examples/denoising/denoising_0.8.png) | Original image content is no longer relevant enough to keep the edges coherent, and we start to see a distinct border around the inpainting area.  This strength is still useful sometimes, but usually requires extra work to blend in the content. This usually involves the [smudge tool](./tool_guide.md#-smudge-tool-m), lower strength inpainting operations, or both. |
| 0.9            | ![0.9 denoising strength example](../examples/denoising/denoising_0.9.png) | A tiny increase in detail over the last step, but errors at the edges of the inpainting selection become even more pronounced.                                                                                                                                                                                                                                               |
| 1.0            | ![1.0 denoising strength example](../examples/denoising/denoising_1.0.png) | Details become strikingly different, original image content is completely lost. The shape of the inpainting selection and the area outside the selection still have some influence on the image, but not much.                                                                                                                                                               |


## Sampling methods
The sampling method controls how the image diffusion process is divided into smaller steps to produce the final image. Each of these will tend towards slightly different results, but the differences are usually minor. Here's a brief glossary:
- Euler: The simplest sampling process, usually a good default.
- UniPC (Unified Predictor-Corrector): A more efficient sampling method that can produce decent images in 5-10 steps.
- Ancestral (A) samplers: Any sampler ending in "A" adds extra randomness to the process.
- Karras samplers: Use gradually decreasing amounts of randomness, potentially improving image quality.
- LCM: Very fast image generation (5-10 steps), but requires either an LCM LORA or an LCM model.
- DPM (Diffusion probabilistic model solver): Solver variants released in 2022.
- Heun: A slower but more precise variant of Euler.
- LMS (Linear Multi-Step), PLMS (Pseudo Linear Multi-Step), and DDIM (Denoising Diffusion Implicit Model): Older methods, not commonly used.
- Turbo: Extremely fast image generation (1 step), but requires an SDXL Turbo model.
