"""
Miscellaneous utility functions needed in many places
"""
from PIL import Image
import argparse
import base64
import requests
import io

def fetch(url_or_path):
    """Open a file from either a path or a URL."""
    if str(url_or_path).startswith('http://') or str(url_or_path).startswith('https://'):
        r = requests.get(url_or_path)
        r.raise_for_status()
        fd = io.BytesIO()
        fd.write(r.content)
        fd.seek(0)
        return fd
    return open(url_or_path, 'rb')

BASE_64_PREFIX = 'data:image/png;base64,'


def image_to_base64(pil_image, include_prefix=False):
    """Convert a PIL image to a base64 string."""
    if isinstance(pil_image, str):
        pil_image = Image.open(pil_image)
    buffer = io.BytesIO()
    pil_image.save(buffer, format='PNG')
    imageStr = str(base64.b64encode(buffer.getvalue()), 'utf-8')
    if include_prefix:
        imageStr = BASE_64_PREFIX + imageStr
    return imageStr


def load_image_from_base64(image_str):
    """Initialize a PIL image object from base64-encoded string data."""
    if image_str.startswith(BASE_64_PREFIX):
        image_str = image_str[len(BASE_64_PREFIX):]
    return Image.open(io.BytesIO(base64.b64decode(image_str)))

def build_arg_parser(default_model='inpaint.pt', include_edit_params=True, include_gen_params=True):
    """Create a command-line argument parser that includes options shared between several scripts"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_path', type=str, default = default_model,
                   help='path to the diffusion model')
    parser.add_argument('--kl_path', type=str, default = 'kl-f8.pt',
                       help='path to the LDM first stage model')
    parser.add_argument('--bert_path', type=str, default = 'bert.pt',
                       help='path to the LDM first stage model')
    parser.add_argument('--text', type = str, required = False, default = '',
                        help='your text prompt')
    parser.add_argument('--negative', type = str, required = False, default = '',
                        help='negative text prompt')

    parser.add_argument('--skip_timesteps', type=int, required = False, default = 0,
                       help='how many diffusion steps are gonna be skipped')

    parser.add_argument('--prefix', type = str, required = False, default = '',
                        help='prefix for output files')

    parser.add_argument('--num_batches', type = int, default = 1, required = False,
                        help='number of batches')

    parser.add_argument('--batch_size', type = int, default = 1, required = False,
                        help='batch size')
    parser.add_argument('--width', type = int, default = 256, required = False,
                        help='image size of output (multiple of 8)')

    parser.add_argument('--height', type = int, default = 256, required = False,
                        help='image size of output (multiple of 8)')

    parser.add_argument('--seed', type = int, default=-1, required = False,
                        help='random seed')

    parser.add_argument('--guidance_scale', type = float, default = 5.0, required = False,
                        help='classifier-free guidance scale')

    parser.add_argument('--steps', type = int, default = 0, required = False,
                        help='number of diffusion steps')
    if include_gen_params:
        parser.add_argument('--init_image', type=str, required = False, default = None,
                           help='init image to use')
    if include_edit_params: 
        parser.add_argument('--edit', type = str, required = True,
                            help='path to the image you want to edit (either an image file or .npy containing a numpy array of the image embeddings)')

        parser.add_argument('--edit_x', type = int, required = False, default = 0,
                            help='x position of the edit image in the generation frame (need to be multiple of 8)')

        parser.add_argument('--edit_y', type = int, required = False, default = 0,
                            help='y position of the edit image in the generation frame (need to be multiple of 8)')

        parser.add_argument('--edit_width', type = int, required = False, default = 0,
                            help='width of the edit image in the generation frame (need to be multiple of 8)')

        parser.add_argument('--edit_height', type = int, required = False, default = 0,
                            help='height of the edit image in the generation frame (need to be multiple of 8)')

        parser.add_argument('--mask', type = str, required = False,
                            help='path to a mask image. white pixels = keep, black pixels = discard. width = image width/8, height = image height/8')
    parser.add_argument('--cpu', dest='cpu', action='store_true')

    parser.add_argument('--clip_score', dest='clip_score', action='store_true')

    parser.add_argument('--clip_guidance', dest='clip_guidance', action='store_true')

    parser.add_argument('--clip_guidance_scale', type = float, default = 150, required = False,
                        help='Controls how much the image should look like the prompt') # may need to use lower value for ddim

    parser.add_argument('--cutn', type = int, default = 16, required = False,
                        help='Number of cuts')

    parser.add_argument('--ddim', dest='ddim', action='store_true') # turn on to use 50 step ddim

    parser.add_argument('--ddpm', dest='ddpm', action='store_true') # turn on to use 50 step ddim
    return parser
