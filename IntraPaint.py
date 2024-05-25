"""
Runs the main IntraPaint inpainting UI.
Assuming you're running the A1111 stable-diffusion API on the same machine with default settings, running
`python IntraPaint.py` should be all you need. For more information on options, run `python IntraPaint.py --help`
"""
from typing import Any
from src.controller.mock_controller import MockController
try:
    from src.controller.stable_diffusion_controller import StableDiffusionController
except ImportError as stable_import_error:
    print(f'Stable-diffusion mode not available: {stable_import_error}')
    StableDiffusionController = None
try:
    from src.controller.web_client_controller import WebClientController
except ImportError as web_import_error:
    print(f'Network GLID-3-XL mode not available: {web_import_error}')
    WebClientController = None
try:
    from src.controller.local_controller import LocalDeviceController
    import torch
    from src.glid_3_xl.ml_utils import get_device
except ImportError as local_err:
    print(f'Local GLID-3-XL mode not available: {local_err}')
    LocalDeviceController = None
    torch = None
from src.util.arg_parser import build_arg_parser

DEFAULT_SD_URL = 'http://localhost:7860'
DEFAULT_GLID_URL = 'http://localhost:5555'
DEFAULT_GLID_MODEL = 'glid_3_xl/models/inpaint.pt'
MIN_GLID_VRAM = 8000000000  # This is just a rough estimate.


def parse_args_and_start() -> None:
    """Apply args, and start in the appropriate image generation mode."""
    # argument parsing:
    parser = build_arg_parser(default_model=DEFAULT_GLID_MODEL, include_edit_params=False)
    parser.add_argument('--mode', type=str, required=False, default='auto',
                        help='Set where inpainting operations should be completed. \nOptions:\n'
                             '"auto": Attempt to guess at the most appropriate editing mode.\n'
                             '"stable": A remote server handles inpainting over a network using stable-diffusion.\n'
                             '"web": A remote server handles inpainting over a network using GLID-3-XL.\n'
                             '"local": Handle inpainting on the local machine (requires a GPU with ~10GB VRAM).\n'
                             '"mock": No actual inpainting performed, for UI testing only')
    parser.add_argument('--init_edit_image', type=str, required=False, default=None,
                        help='initial image to edit')
    parser.add_argument('--edit_width', type=int, required=False, default=256,
                        help='width of the edit image in the generation frame (need to be multiple of 8)')

    parser.add_argument('--edit_height', type=int, required=False, default=256,
                        help='height of the edit image in the generation frame (need to be multiple of 8)')
    parser.add_argument('--timelapse_path', type=str, required=False,
                        help='subdirectory to store snapshots for creating a timelapse of all editing operations')
    parser.add_argument('--server_url', type=str, required=False, default='',
                        help='Image generation server URL (web mode only. If not provided and mode=web or stable, you'
                             ' will be prompted for a URL on launch.')
    parser.add_argument('--fast_ngrok_connection', type=str, required=False, default='',
                        help='If true, connection rates will not be limited when using ngrok. This may cause rate '
                             'limiting if running in web mode without a paid account.')
    args = parser.parse_args()

    controller_mode = str(args.mode)

    def health_check(controller_type: Any, url: str) -> bool:
        """Check if a web repo initialized and passes health checks."""
        return controller_type is not None and controller_type.health_check(url)

    if controller_mode == 'auto' and args.server_url != '':
        controller_mode = 'stable' if health_check(StableDiffusionController, args.server_url) \
                else 'web' if health_check(WebClientController, args.server_url) else 'auto'
    if controller_mode == 'auto':
        print(f'Unable to identify server type for url "{args.server_url}", checking default localhost ports...')
        if health_check(StableDiffusionController, DEFAULT_SD_URL):
            args.server_url = DEFAULT_SD_URL
            controller_mode = 'stable'
        elif health_check(WebClientController, DEFAULT_GLID_URL):
            args.server_url = DEFAULT_GLID_URL
            controller_mode = 'web'
        else:
            print('Failed to identify webservice, trying local mode.')
            controller_mode = 'local'

    match controller_mode:
        case 'local':
            if torch is None or LocalDeviceController is None:
                raise RuntimeError('Missing required dependencies for local GLID-3-XL mode.')
            device = get_device()
            (mem_free, mem_total) = torch.cuda.mem_get_info(device)
            if mem_free < MIN_GLID_VRAM:
                raise RuntimeError(f'Not enough VRAM to run local, expected >= {MIN_GLID_VRAM}, found '
                                   f'{mem_free} of {mem_total}')
            controller = LocalDeviceController(args)
        case 'stable' if health_check(StableDiffusionController, args.server_url):
            controller = StableDiffusionController(args)
        case 'web' if health_check(WebClientController, args.server_url):
            controller = WebClientController(args)
        case 'mock':
            controller = MockController(args)
        case _:
            raise RuntimeError(f'Exiting: invalid or unsupported mode "{controller_mode}"')
    controller.start_app()


if __name__ == '__main__':
    parse_args_and_start()
