"""
Runs the main IntraPaint inpainting UI.
Assuming you're running the A1111 stable-diffusion API on the same machine with default settings, running
`python IntraPaint.py` should be all you need. For more information on options, run `python IntraPaint.py --help`
"""
import atexit
import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

from src.controller.app_controller import AppController
from src.ui.modal.modal_utils import show_error_dialog
from src.util.arg_parser import build_arg_parser
from src.util.optional_import import check_import
from src.util.shared_constants import TIMELAPSE_MODE_FLAG, PROJECT_DIR

LOG_FILE_PATH = 'IntraPaint.log'
DEFAULT_GLID_MODEL = 'models/inpaint.pt'
MIN_GLID_VRAM = 8000000000  # This is just a rough estimate.

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
parser.add_argument(TIMELAPSE_MODE_FLAG, action='store_true',
                    help='makes minor changes to UI to simplify recording smooth timelapse editing footage')
parser.add_argument('--server_url', type=str, required=False, default='',
                    help='Image generation server URL (web mode only. If not provided and mode=web or stable, you'
                         ' will be prompted for a URL on launch.')
parser.add_argument('--fast_ngrok_connection', type=str, required=False, default='',
                    help='If true, connection rates will not be limited when using ngrok. This may cause rate '
                         'limiting if running in web mode without a paid account.')
parser.set_defaults(timelapse_mode=False)
args = parser.parse_args()

# Logging setup:
log_file_handler = logging.FileHandler(LOG_FILE_PATH)
log_file_handler.setLevel(logging.INFO)
log_formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(name)s: %(message)s')
log_file_handler.setFormatter(log_formatter)    # Also log to stdout if --verbose is set:
handlers = [log_file_handler]
if args.verbose:
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(logging.Formatter('#%(levelname)s: %(name)s:  %(message)s'))
    handlers.append(stdout_handler)
logging.basicConfig(level=logging.INFO, handlers=handlers)
logger = logging.getLogger(__name__)


def exit_log():
    """Log when IntraPaint exits under normal circumstances."""
    logger.info('IntraPaint exiting now.')


atexit.register(exit_log)

# If relevant directories exist, update paths for GLID-3-XL dependencies:
if not check_import('ldm'):
    expected_ldm_path = f'{PROJECT_DIR}/latent-diffusion'
    if os.path.exists(expected_ldm_path):
        sys.path.append(expected_ldm_path)

        # Newer versions of pytorch-lightning changed the location of one needed dependency, but latent-diffusion was
        # never updated. This only requires a single minor update, so make that change here if necessary:
        updated_file_path = f'{expected_ldm_path}/ldm/models/diffusion/ddpm.py'
        with open(updated_file_path, 'r+') as file:
            lines = file.readlines()
            for i, line in enumerate(lines):
                if 'from pytorch_lightning.utilities.distributed import rank_zero_only' in line:
                    lines[i] = 'from pytorch_lightning.utilities.rank_zero import rank_zero_only'
                    file.seek(0)
                    file.writelines(lines)
                    file.truncate()
                    break

if not check_import('taming'):
    expected_taming_path = f'{PROJECT_DIR}/taming-transformers'
    if os.path.exists(expected_taming_path):
        sys.path.append(expected_taming_path)

if __name__ == '__main__':
    try:
        controller = AppController(args)
        controller.start_app()
    except Exception as err:
        logger.exception('main crashed, error: %s', err)
        if QApplication.instance() is None:
            app = QApplication(sys.argv)
        show_error_dialog(None, title="IntraPaint failed to start", error=err)
        raise err
