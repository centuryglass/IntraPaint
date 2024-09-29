# AI Inpainting with IntraPaint
I’ve spent the last two years experimenting with AI-driven image editing, and I’ve collected some useful tricks to get
the best results with inpainting.  This guide will help you get the results you want with minimal hassle.


If you don't have any previous experience with AI image editing with Stable-Diffusion, you may want to review
the [Stable-Diffusion guide](./doc/stable-diffusion.md) first.
---
## Table of Contents
1. [Key Terms](#key-terms)
---

## Key Terms
These concepts and controls are specific to AI inpainting, understanding them will help you get the most out of IntraPaint.

## Generation Area
The section of an image where the AI can make changes. In IntraPaint, the Generation Area is shown as a dotted
rectangle within the image, and you can use the [Generation Area tool](./doc/tools.md#image-generation-area-tool-g) to
change its size and placement.


The way the generation area is used varies depending on the image editing mode:
- Text-to-Image: The original content in the generation area is erased and replaced.
- Image-to-Image: The AI modifies the generation area while ignoring areas outside of it, which can cause visible seams.
- Inpainting: Only selected content within the generation area is modified, but the AI can still “see” the entire generation area (unless "inpaint full resolution" is enabled).

### Generation resolution
The dimensions of the generated content. If the generation resolution doesn't match the generation area, the output
will be scaled accordingly. This may result in quality loss or detail artifacts, so in most cases it's best to not use
a generation resolution that's larger than the generation area.  In IntraPaint, you can set this within the 
Image Generation tab, or at the bottom of the Generation Area tool panel.

### "Inpaint Full Resolution" Checkbox
When enabled, the image generator uses a reduced portion of the generation area, focusing only on the selected
inpainting areas. This gives higher detail at the cost of overall image awareness. This option is only valid when 
inpainting.  It can be found in the Image Generation tab, and in the tool panel for each selection tool.

### “Inpaint Full Res. Padding”
When "Inpaint Full Resolution" is checked, padding is added around the inpaint selection to prevent seams. You can
control the padding size with this option, though it will be cropped if it exceeds the generation area. Controls for
this option are located beneath the "Inpaint Full Resolution" checkbox.  When active, the padding rectangle will be 
drawn within the generation area around selected content.

---

# AI .odel selection
Choosing the right model is crucial for achieving the best results. Here are some tips for model selection:

## Base model selection
Most Stable-Diffusion models are variants of two different base model types, each with its own strengths and weaknesses.
- Stable-Diffusion 1.5 (SD1.5): More efficient for inpainting tasks. Variants usually perform poorly at resolutions above 512x512, but can still deliver great results on small areas.
- Stable-Diffusion XL (SDXL): Best for whole-image generation. Slower, but works well for larger compositions.

### Other notable base models
- [CommonCanvas](https://huggingface.co/papers/2310.16825): Uses the same architecture as Stable-Diffusion, trained from scratch on a dataset that uses only Creative-Commons licensed images.
- Stable-Diffusion 2.1: An intermediate model with capabilities roughly between Stable-Diffusion 1.5 and Stable-Diffusion XL, not frequently used.
- Stable-Diffusion 3: Exceeds the capabilities of SDXL in many respects, but notoriously poor at reliably generating humans and animals without serious errors.
- Flux: Not a Stable-Diffusion model, but many Stable-Diffusion clients support it. Its capabilities dramatically surpass SDXL, but it's even slower and more resource-intensive.

### Community Models
It's rarely recommended to use the base models directly, as they are usually surpassed by fine-tuned model variants and mixes released by hobbyists and enthusiasts on platforms like HuggingFace and Civitai. Some models specialize in styles (anime, realism), while others are general improvements. Keep experimenting since new models are released frequently.

---
# Tips and Tricks

## General tips:

### Generation Resolution Tips
- **Know Your Model’s Capabilities**: Models based on SD1.5 work best at 512x512 but can stretch to 640x640 or higher for some community fine-tunes. SDXL handles 1024x1024 or larger more comfortably.
- **Use Downscaling for Detail Work**: Set your generation resolution higher than your generation area size to allow for error correction during downscaling.

### Generation Area control
Balancing fine detail with scene awareness is key.
- *Fine Detail*: For maximum focus and accuracy, select small areas and enable "inpaint full resolution" with low padding.
- *Scene Awareness*: To help the image generator recognize patterns or maintain composition, increase padding or generation area size. You can extend padding by right-clicking with the selection brush to add a single pixel outside the selection—this extends the padding without affecting content.

### Selecting areas for inpainting:
- Small changes are good: The less that the AI has to do in a single operation, the less likely it'll be to get something critically wrong, and small changes generate faster..  Gen. area control is especially important when doing this.
- If generating a pattern or repeating features, it usually works best to select the whole thing at once.  AI is better at redoing an entire pattern than it is at fixing a small area while matching the overall pattern exactly.

### Prompt adjusting:
- Since the AI only sees the gen. area, leaving anything in the prompt that's outside of the gen. area is likely to result in duplicate content, especially at higher denoising strength. Consider temporarily removing parts, or adding more text related to the specific spot you're editing.
- At lower denoising strengths (< 50% or so), image context often matters more than prompt context, so you often won't need to change the prompt much.

### Misc. tricks and tips:
- If a particular inpainting result is extremely good in most ways, but gets one area wrong:
  * Right click the image option in the selection screen, click "send to new layer", exit the selection screen
  * Select the new layer, erase the part that you don't like, select "merge down" to manually add the rest of the change to the edited layer.
- It's way easier to get the AI to do exactly what you want if you can manually start the process.  It's easier to roughly sketch a scene and let the AI clean it up than it is to get the AI to make that same exact scene using only prompting.
- AI is extremely good at cleaning up rough edges, you can copy/paste whole blocks of content, crudely scale and transform image regions, or drop in mismatched sketches, and a quick inpainting pass will clean it up easily.
- Sometimes models will have issues matching colors across gradients, especially older models.  Use the smudge tool to smooth out visible seams and inpaint again at a lower denoising strength to fix these issues.
- AI upscaling is extremely effective, but it's much easier to fix large-scale image issues when the image is lower-resolution.  Sometimes it's even worthwhile to scale down an image to make large-scale changes go more smoothly, then upscale it again once the issues are resolved.

### ControlNet tricks:
- When inpainting with ControlNet, you can increase the denoising strength much higher, even up to 100%, and ControlNet will make sure the appropriate content is still preserved.
- If you want to clean up fine details and textures but change almost nothing about the overall composition, use the tile ControlNet module. It ensures that individual multi-pixel blocks within the image stay around the same average color.
- To refine a quick sketch, preserving shapes but improving details, the scribble model is ideal.
- The Canny module preserves lines within the image, making it ideal for coloring line-art. Canny is much stricter at preserving line shape when compared to the scribble module, so it's best used with line-art that's already highly refined.
