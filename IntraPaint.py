"""
Runs the main IntraPaint inpainting UI.
Assuming you're running the A1111 stable-diffusion API on the same machine with default settings, running
`python IntraPaint.py` should be all you need. For more information on options, run `python IntraPaint.py --help`
"""
import atexit
import logging
import os
import sys
import traceback

from PySide6.QtCore import QTranslator, QObject, QEvent
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen, QWidget, QDialog, QLabel, QMenu

from src.ui.modal.image_filter_modal import ImageFilterModal
from src.ui.modal.image_scale_modal import ImageScaleModal
from src.ui.modal.login_modal import LoginModal
from src.ui.modal.new_image_modal import NewImageModal
from src.ui.modal.resize_canvas_modal import ResizeCanvasModal
from src.ui.modal.settings_modal import SettingsModal
from src.ui.panel.layer_ui.layer_panel import LayerPanel
from src.ui.window.extra_network_window import ExtraNetworkWindow
from src.ui.window.generator_setup_window import GeneratorSetupWindow
from src.ui.window.image_window import ImageWindow
from src.ui.window.main_window import MainWindow
from src.ui.window.prompt_style_window import PromptStyleWindow
from src.util.arg_parser import build_arg_parser
from src.util.visual.geometry_utils import get_scaled_placement
from src.util.optional_import import check_import
from src.util.pyinstaller import is_pyinstaller_bundle
from src.util.shared_constants import TIMELAPSE_MODE_FLAG, PROJECT_DIR, LOG_DIR

DEFAULT_GLID_MODEL = f'{PROJECT_DIR}/models/inpaint.pt'

MODE_OPTION_HELP = ('Set how image generation operations should be completed. \nOptions:\n'
                    '"auto": Attempt to guess at the most appropriate image generation mode.\n'
                    '"stable": A remote server handles inpainting over a network using stable-diffusion.\n'
                    '"web": A remote server handles inpainting over a network using GLID-3-XL.\n'
                    '"none": No AI image generation capabilities, manual editing only.\n')
if not is_pyinstaller_bundle():
    MODE_OPTION_HELP += ('"local": Handle inpainting on the local machine (requires a GPU with ~10GB VRAM).\n'
                         '"mock": No actual inpainting performed, for UI testing only')

# argument parsing:
parser = build_arg_parser(include_edit_params=False, include_model_defaults=False)
parser.add_argument('--mode', type=str, required=False, default='auto', help=MODE_OPTION_HELP)
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
LOG_FILE_PATH = os.path.join(LOG_DIR, 'IntraPaint.log')
log_file_handler = logging.FileHandler(LOG_FILE_PATH)
log_file_handler.setLevel(logging.INFO)
log_formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(name)s: %(message)s')
log_file_handler.setFormatter(log_formatter)  # Also log to stdout if --verbose is set:
handlers = [log_file_handler]
if args.verbose:
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(logging.Formatter('#%(levelname)s: %(name)s:  %(message)s'))
    handlers.append(stdout_handler)  # type: ignore

logging.basicConfig(level=logging.INFO, handlers=handlers)
print(f'Logs will be saved at {LOG_FILE_PATH}')
logger = logging.getLogger(__name__)


def exit_log():
    """Log when IntraPaint exits under normal circumstances."""
    logger.info('IntraPaint exiting now.')


atexit.register(exit_log)

app = QApplication.instance() or QApplication(sys.argv)

if args.dev:
    # If a QWidget isn't properly assigned to a parent or hidden after being removed, it will pop up as a new window.
    # If the problem is addressed relatively quickly but not quickly enough to prevent this, we end up with tiny
    # windows that appear for an instant and then disappear.  This is undesirable, and tricky to debug. If running
    # in dev mode, this will cause an immediate crash whenever one of these invalid windows shows up, making it
    # much easier to fix them.
    print('Enabling invalid window debugging')


    class WindowEventFilter(QObject):
        """Crash whenever a window appears that's not in the list of expected window types"""

        def eventFilter(self, obj, event):
            """Check for appropriate top-level ShowEvents, consume no events."""
            if not isinstance(obj, QWidget) or isinstance(obj, (QSplashScreen, QDialog, MainWindow, ImageWindow,
                                                                ExtraNetworkWindow, GeneratorSetupWindow, LayerPanel,
                                                                PromptStyleWindow, ImageFilterModal, ImageScaleModal,
                                                                LoginModal, NewImageModal, ResizeCanvasModal, QMenu,
                                                                SettingsModal)):
                return False
            # noinspection SpellCheckingInspection
            if isinstance(obj, QLabel) and obj.objectName() == 'qtooltip_label':
                return False
            if event.type() == QEvent.Type.Show and obj.parentWidget() is None:
                print(f'unexpected window: {obj} at {obj.geometry()}')
                traceback.print_stack()
                sys.exit(1)
            return False

    event_filter = WindowEventFilter()
    app.installEventFilter(event_filter)

# close pyinstaller splash screen, if running from bundled executable:
try:
    # noinspection PyUnresolvedReferences
    import pyi_splash
    pyi_splash.close()
except ImportError:
    pass  # Not using the pyinstaller bundle

# show Qt splash screen:
splash_screen_image = QPixmap(f'{PROJECT_DIR}/resources/IntraPaint_banner.jpg')
screen = app.primaryScreen()
splash_screen_bounds = get_scaled_placement(screen.geometry(), splash_screen_image.size(), 10)
splash_screen_image = splash_screen_image.scaled(splash_screen_bounds.size())
splash_screen = QSplashScreen(screen, splash_screen_image)
splash_screen.setGeometry(splash_screen_bounds)
splash_screen.show()
splash_screen.raise_()
app.processEvents()

# Load translations:
translator = QTranslator()
for root, _, files in os.walk(f'{PROJECT_DIR}/resources/translations'):
    for file in files:
        if file.endswith('.qm'):
            assert translator.load(os.path.join(root, file)), f'Failed to load {file}'
app.installTranslator(translator)

# If relevant directories exist, update paths for GLID-3-XL dependencies:
if not is_pyinstaller_bundle():
    if not check_import('ldm'):
        expected_ldm_path = f'{PROJECT_DIR}/latent-diffusion'
        if os.path.exists(expected_ldm_path):
            sys.path.append(expected_ldm_path)
    else:
        expected_ldm_path = PROJECT_DIR

    # Newer versions of pytorch-lightning changed the location of one needed dependency, but latent-diffusion was
    # never updated. This only requires a single minor update, so make that change here if necessary:
    updated_file_path = f'{expected_ldm_path}/ldm/models/diffusion/ddpm.py'
    if os.path.exists(updated_file_path):
        with open(updated_file_path, 'r+') as module_file:
            lines = module_file.readlines()
            for i, line in enumerate(lines):
                if 'from pytorch_lightning.utilities.distributed import rank_zero_only' in line:
                    lines[i] = 'from pytorch_lightning.utilities.rank_zero import rank_zero_only'
                    module_file.seek(0)
                    module_file.writelines(lines)
                    module_file.truncate()
                    break

    if not check_import('taming'):
        expected_taming_path = f'{PROJECT_DIR}/taming-transformers'
        if os.path.exists(expected_taming_path):
            sys.path.append(expected_taming_path)

# These imports need to be delayed until after logging setup, translation, and import path tweaks:
# noinspection PyPep8
from src.controller.app_controller import AppController
# noinspection PyPep8
from src.ui.modal.modal_utils import show_error_dialog

if __name__ == '__main__':
    try:
        controller = AppController(args)

        splash_screen.finish(controller.menu_window)

        controller.start_app()
    except Exception as err:
        logger.exception('main crashed, error: %s', err)
        if QApplication.instance() is None:
            app = QApplication(sys.argv)
        show_error_dialog(None, title="IntraPaint failed to start", error=err)
        raise err
