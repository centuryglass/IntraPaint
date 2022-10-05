# Runs the inpainting UI and image generation together
from startup.utils import *

# argument parsing:
parser = buildArgParser(defaultModel='inpaint.pt', includeEditParams=False)
parser.add_argument('--mode', type = str, required = False, default = 'stable',
                    help = 'Set where inpainting operations should be completed. \nOptions:\n'
                    + '"stable": A remote server handles inpainting over a network connection using stable-diffusion.\n'
                    + '"web": A remote server handles inpainting over a network connection using GLID-3-XL.\n'
                    + '"local": Handle inpainting on the local machine (requires a GPU with ~10GB VRAM).\n'
                    + '"mock": No actual inpainting performed, for UI testing only')
parser.add_argument('--init_edit_image', type=str, required = False, default = None,
                   help='initial image to edit')
parser.add_argument('--edit_width', type = int, required = False, default = 256,
                    help='width of the edit image in the generation frame (need to be multiple of 8)')

parser.add_argument('--edit_height', type = int, required = False, default = 256,
                            help='height of the edit image in the generation frame (need to be multiple of 8)')
parser.add_argument('--timelapse_path', type = str, required = False,
                            help='subdirectory to store snapshots for creating a timelapse of all editing operations')
parser.add_argument('--server_url', type = str, required = False, default = '',
                    help='Image generation server URL (web mode only. If not provided and mode=web, you will be '
                        + 'prompted for a URL on launch.')
parser.add_argument('--fast_ngrok_connection', type = str, required = False, default = '',
                    help='If true, connection rates will not be limited when using ngrok. This may cause rate limiting'
                        + 'if running in web mode without a paid account.')
args = parser.parse_args()

controller = None
controllerMode = args.mode
if controllerMode == 'stable':
    from inpainting.controller.stable_diffusion_controller import StableDiffusionController
    controller = StableDiffusionController(args)
elif controllerMode == 'web':
    from inpainting.controller.web_client_controller import WebClientController
    controller = WebClientController(args)
elif controllerMode == 'local':
    from inpainting.controller.local_controller import LocalDeviceController
    controller = LocalDeviceController(args)
elif controllerMode == 'mock':
    from inpainting.controller.mock_controller import MockController
    controller = MockController(args)
else:
    raise Exception(f'Exiting: invalid mode "{controllerMode}"')
controller.startApp()
