# Stable-Diffusion Image Generation Controls
These controls are shown in either a panel at the bottom of the main window, or within a tab above the window, depending on how large the window is.  Additional controls can be found in the settings window (F9) under the "Stable-Diffusion" tab, and in the "Stable-Diffusion" menu.

# Image Generation Controls

## Prompt
Describe in plain text exactly what kind of imagery the model should generate. This text can be formatted in various ways to control its behavior. These controls are provided by the [Automatic1111 webui](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki/Features) and can be altered by various webui extensions.

| Control             | Example                                             | Description                                                                                                                                                |
|---------------------|-----------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Boost attention     | `red and (blue)`                                    | `blue` is treated as 1.1x more important                                                                                                                   |
| Decrease attention  | `cat and [dog]`                                     | `dog` is treated as 1.1x less important                                                                                                                    |
| Precise attention   | `(field:2.0) of (flowers:0.5)`                      | `field` is prioritized 4x more than `flowers`                                                                                                              |
| Literal characters  | `special characters \(\)\[\]`                       | Bracket characters are taken literally, and don't affect attention                                                                                         |
| Prompt editing      | `blue sky, [painting:photograph:8]`                 | After eight steps, the prompt switches from `painting` to `photograph`                                                                                     |
| Alternating prompts | `a friendly [dog\|cat]`                             | Switch between `dog` and `cat` after each image generation step                                                                                            |
| Composable prompts  | `photograph of a house:0.5 AND charcoal sketch:1.0` | Sections split by AND are treated as individual prompts, to be applied simultaneously. The numbers at the end control how much that prompt is prioritized. |

## Negative Prompt
Describe in plain text exactly what kind of imagery the model should *not* generate. All special controls described above can also be used in negative prompts.

## Edit mode
Switch between the three main image generation modes:
- Inpaint: Only selected content is changed during image generation.
- Image to Image: The entire image generation area is changed, but previous image content affects the new image.
- Text to Image: Previous image content is ignored, a new image is generated using only prompt data and other settings.

## Sampling steps
Controls how many steps the generator takes to create images. Increasing step count makes image generation take longer, but often provides better results.  Benefits of increasing step count are usually fairly low above 30 steps. Certain specialty models (LCM and Turbo) can produce good results at far fewer steps.

## Guidance scale
Controls how strongly the generator will follow the prompt. Low values produce more random imagery, while high values de-prioritize image composition to focus more on exactly matching the AI model's understanding of your prompt.  Values in the 6-12 range usually produce the best results.

## Denoising strength
This control only applies when using Inpaint and Image to Image modes, and controls exactly how much of the source image the AI generator will include in its output.
- 0.25 or less: Changes will be very minor, usually just slight adjustments to details.
- 0.25 - 0.5: Changes are more visible, but the image will usually still be very similar to the original.
- 0.5 - 0.75: Some elements from the original image are still present, but results are significantly different.
- 0.75 and up: The original image only has a tiny influence on generated content. At 1.0, the original image is completely ignored.

## Sampling method
This lets you select between different mathematical models that can be used for the image generation process. Each of these will tend towards slightly different results, but the differences are usually minor. Here's a brief glossary:
- Euler: The simplest sampling process, usually a good default.
- UniPC (Unified Predictor-Corrector): A more efficient sampling method that can produce decent images in 5-10 steps.
- Ancestral (A) samplers: Any sampler ending in "A" adds extra randomness to the process.
- Karras samplers: Use gradually decreasing amounts of randomness, potentially improving image quality.
- LCM: Very fast image generation (5-10 steps), but requires either an LCM LORA or an LCM model.
- DPM (Diffusion probabilistic model solver): Solver variants released in 2022.
- Heun: A slower but more precise variant of Euler.
- LMS (Linear Multi-Step), PLMS (Pseudo Linear Multi-Step), and DDIM (Denoising Diffusion Implicit Model): Older methods, not commonly used.
- Turbo: Extremely fast image generation (1 step), but requires an SDXL Turbo model.

## Seed
A number used to control randomness during image generation.  If all other factors are unchanged, using the same seed value should produce the same images each time. If set to -1, a different random seed will be used each time you generate images.

Batch size 

## ControlNet