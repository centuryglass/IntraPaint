# Runs the inpainting UI and image generation together
from startup.utils import *

# argument parsing:
parser = buildArgParser(defaultModel='inpaint.pt', includeEditParams=False)
parser.add_argument('--mode', type = str, required = False, default = 'auto',
                    help = 'Set where inpainting operations should be completed. \nOptions:\n'
                    + '"auto": Attempt to guess at the most appropriate editing mode.\n'
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
                    help='Image generation server URL (web mode only. If not provided and mode=web or stable, you will'
                        + ' be prompted for a URL on launch.')
parser.add_argument('--fast_ngrok_connection', type = str, required = False, default = '',
                    help='If true, connection rates will not be limited when using ngrok. This may cause rate limiting'
                        + 'if running in web mode without a paid account.')
args = parser.parse_args()

controller = None
controllerMode = args.mode

if controllerMode == 'auto':
    from controller.stable_diffusion_controller import StableDiffusionController
    from controller.web_client_controller import WebClientController
    if args.server_url != '':
        if StableDiffusionController.healthCheck(args.server_url):
            controllerMode = 'stable'
        elif WebClientController.healthCheck(args.server_url):
            controllerMode = 'web'
        else:
            print(f'Unable to identify server type for {args.server_url}, checking default localhost ports...')
    if controllerMode == 'auto':
        defaultSdUrl = 'http://localhost:7860'
        defaultGlidUrl = 'http://localhost:5555'
        if StableDiffusionController.healthCheck(defaultSdUrl):
            args.server_url = defaultSdUrl
            controllerMode = 'stable'
        elif WebClientController.healthCheck(defaultGlidUrl):
            args.server_url = defaultGlidUrl
            controllerMode = 'web'
        else:
            minVRAM = 8000000000 # This is just a rough estimate.
            try:
                import torch
                from startup.ml_utils import getDevice
                device = getDevice()
                (memFree, memTotal) = torch.cuda.mem_get_info(device)
                if memFree < minVRAM:
                    raise Exception(f"Not enough VRAM to run local, expected at least {minVRAM}, found {memFree} of {memTotal}")
                controllerMode = 'local'
            except Exception as err:
                print(f"Failed to start in local mode, defaulting to web. Exception: {err}")
                controllerMode = 'web'

if controllerMode == 'stable':
    from controller.stable_diffusion_controller import StableDiffusionController
    controller = StableDiffusionController(args)
elif controllerMode == 'web':
    from controller.web_client_controller import WebClientController
    controller = WebClientController(args)
elif controllerMode == 'local':
    from controller.local_controller import LocalDeviceController
    controller = LocalDeviceController(args)
elif controllerMode == 'mock':
    from controller.mock_controller import MockController
    controller = MockController(args)
else:
    raise Exception(f'Exiting: invalid mode "{controllerMode}"')
controller.startApp()
