![IntraPaint_banner.jpg](./resources/IntraPaint_banner.jpg)  

IntraPaint is a free and open source image editor with integrated AI image generation support, for Linux, Windows, and macOS.

## Goals:
- Combine standard image editing and digital painting tools with AI image generation and inpainting tools. Make it
  easier for established artists to integrate AI into their workflow, and for AI enthusiasts to adopt more traditional
  image editing tools and gain finer control over the images they create.

## Features:

### AI image generation features:
- Uses Stable-Diffusion, either running on the same machine or remotely over a network connection, via the --api option
  in either [Forge WebUI](https://github.com/lllyasviel/stable-diffusion-webui-forge) or the [Automatic1111 WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui).
- All AI features areSupports either completely new image generation (text to image), generating variant images (image to image), or 
  precise detail editing (inpainting), guided by natural-language descriptive prompts and various configurable
  parameters.
- Use ControlNet modules for more advanced AI guidance features (depth mapping, recoloring, pose duplication, etc.)
- Support for AI upscaling using stable-diffusion + ControlNet or through a bunch of different alternate models.
- Image interrogation to generate a prompt to describe any image.


### Standard raster editing features:
- All AI features are optional, IntraPaint still functions like standard image editing software when AI is disabled.
- Full-featured layer stack, with support for all the usual features: layer transformations, layer groups, advanced
  composition and blending modes, etc.
- Digital painting using the [libmypaint](https://github.com/mypaint/libmypaint) brush engine, full support for drawing
  tablets.
- All the usual tools you'd expect: selection, text editing, paint bucket, filters, etc.

### What can you do with this combination?
Benefit from partial automation: you draw the parts that you want to draw, let image generation take care of the parts
that you don't want to do.

|                                              |                                               |                                                                                        |
|----------------------------------------------|-----------------------------------------------|----------------------------------------------------------------------------------------|
| "Detailed painting of a brick wall"          | "line art, black and white, a strange person" | "warm colors/cool colors/impressionism/3D render/child's drawing/renaissance painting" |
| GIF: complicated interior behind a character | GIF: rough sketch becomes polished line art   | GIF: simple drawing alternates between styles and color patterns                       |
|Generate complex backgrounds                  | Polish and refine your sketches               | Add color, experiment with styles                                                      |

Control image generation visually. No complex prompts needed, scribble in rough art, describe it briefly, and let Stable-Diffusion figure out the details you want from visual cues.

Prompt: "a red lizard standing on a purple statue in an orange desert under a blue sky"

|                                                                         |                                                                               |                                                                                   |
|-------------------------------------------------------------------------|-------------------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| IMG: Initial image, not quite right                                     | IMG: Quick sketch, exactly matches description.                               | IMG: AI refined version of sketch                                                 |
| AI does okay with details, but struggles with combining them correctly. | I can easily get the composition right, but not with the same level of detail | IntraPaint drawing plus inpainting gives you the best of both with minimal hassle |

Generate images with levels of detail and precision far higher than unguided image generation allows.

|                                                                            |                                                  |                                                |
|----------------------------------------------------------------------------|--------------------------------------------------|------------------------------------------------|
| IMG: Huge empty canvas, partial landscape over tiles                       | GIF: refining details, selecting generated items | GIF: Sweep from low to high detail             |
| Generate images piece by piece to avoid image generation size restrictions | Use guided inpainting to refine small details    | Final results are dramatically higher quality. |


TODO:
- Link pre-built pyinstaller packages
- Direct installation instructions with git, python, pip
- libmypaint issues (mac especially)
- Stable-diffusion setup with stability matrix
- links to additional tutorials