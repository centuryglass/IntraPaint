"""
Runs the main IntraPaint inpainting UI.
Assuming you're running the A1111 stable-diffusion API on the same machine with default settings, running
`python IntraPaint.py` should be all you need. For more information on options, run `python IntraPaint.py --help`
"""

from controller.mock_controller import MockController
try:
    from controller.stable_diffusion_controller import StableDiffusionController
except ImportError as stable_import_error:
    print(f'Stable-diffusion mode not available: {stable_import_error}')
    StableDiffusionController = None
try:
    from controller.web_client_controller import WebClientController
except ImportError as web_import_error:
    print(f'Network GLID-3-XL mode not available: {web_import_error}')
    WebClientController = None
try:
    from controller.local_controller import LocalDeviceController
    import torch
    from glid_3_xl.ml_utils import get_device
except ImportError as local_err:
    print(f'Local GLID-3-XL mode not available: {local_err}')
    LocalDeviceController = None
    torch = None
from util.arg_parser import build_arg_parser

DEFAULT_SD_URL = 'http://localhost:7860'
DEFAULT_GLID_URL = 'http://localhost:5555'
MIN_GLID_VRAM = 8000000000 # This is just a rough estimate.

def parse_args_and_start() -> None:
    """Apply args, and start in the appropriate image generation mode."""
    # argument parsing:
    parser = build_arg_parser(default_model='glid_3_xl/models/inpaint.pt', include_edit_params=False)
    parser.add_argument('--mode', type = str, required = False, default = 'auto',
                        help = 'Set where inpainting operations should be completed. \nOptions:\n'
                        + '"auto": Attempt to guess at the most appropriate editing mode.\n'
                        + '"stable": A remote server handles inpainting over a network using stable-diffusion.\n'
                        + '"web": A remote server handles inpainting over a network using GLID-3-XL.\n'
                        + '"local": Handle inpainting on the local machine (requires a GPU with ~10GB VRAM).\n'
                        + '"mock": No actual inpainting performed, for UI testing only')
    parser.add_argument('--init_edit_image', type=str, required = False, default = None,
                       help='initial image to edit')
    parser.add_argument('--edit_width', type = int, required = False, default = 256,
                        help='width of the edit image in the generation frame (need to be multiple of 8)')

    parser.add_argument('--edit_height', type = int, required = False, default = 256,
                                help='height of the edit image in the generation frame (need to be multiple of 8)')
    parser.add_argument('--timelapse_path', type = str, required = False,
                                help='subdirectory to store snapshots for creating a timelapse of all editing ' +
                                'operations')
    parser.add_argument('--server_url', type = str, required = False, default = '',
                        help='Image generation server URL (web mode only. If not provided and mode=web or stable, you'
                            + ' will be prompted for a URL on launch.')
    parser.add_argument('--fast_ngrok_connection', type = str, required = False, default = '',
                        help='If true, connection rates will not be limited when using ngrok. This may cause rate '
                            + 'limiting if running in web mode without a paid account.')
    args = parser.parse_args()

    controller = None
    controller_mode = str(args.mode)

    if controller_mode == 'auto':
        if args.server_url != '':
            if StableDiffusionController is not None and StableDiffusionController.health_check(args.server_url):
                controller_mode = 'stable'
            elif WebClientController is not None and WebClientController.health_check(args.server_url):
                controller_mode = 'web'
            else:
                print(f'Unable to identify server type for {args.server_url}, checking default localhost ports...')
        if controller_mode == 'auto':
            if StableDiffusionController.health_check(DEFAULT_SD_URL):
                args.server_url = DEFAULT_SD_URL
                controller_mode = 'stable'
            elif WebClientController.health_check(DEFAULT_GLID_URL):
                args.server_url = DEFAULT_GLID_URL
                controller_mode = 'web'
            elif torch is not None:
                try:
                    device = get_device()
                    (mem_free, mem_total) = torch.cuda.mem_get_info(device)
                    if mem_free < MIN_GLID_VRAM:
                        raise RuntimeError(f'Not enough VRAM to run local, expected >= {MIN_GLID_VRAM}, found ' + \
                                f'{mem_free} of {mem_total}')
                    controller_mode = 'local'
                except RuntimeError as err:
                    print(f'Failed to start in local mode, defaulting to web. Exception: {err}')
                    controller_mode = 'web'

    if controller_mode == 'stable' and StableDiffusionController is not None:
        controller = StableDiffusionController(args)
    elif controller_mode == 'web' and WebClientController is not None:
        controller = WebClientController(args)
    elif controller_mode == 'local' and LocalDeviceController is not None:
        controller = LocalDeviceController(args)
    elif controller_mode == 'mock':
        controller = MockController(args)
    else:
        raise RuntimeError(f'Exiting: invalid or unsupported mode "{controller_mode}"')
    controller.start_app()

if __name__ == '__main__':
    parse_args_and_start()
