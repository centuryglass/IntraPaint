"""
Starts the GLID-3-XL image inpainting server.
"""
import os.path
import sys

from src.glid_3_xl.load_models import load_models
from src.glid_3_xl.ml_utils import get_device
from src.util.arg_parser import build_arg_parser
from colabFiles.server import start_server
from src.util.optional_import import check_import
from src.util.shared_constants import PROJECT_DIR

if not check_import('ldm'):
    expected_ldm_path = f'{PROJECT_DIR}/latent-diffusion'
    if os.path.exists(expected_ldm_path):
        sys.path.append(expected_ldm_path)
    if not check_import('ldm'):
        print('Missing required latent-diffusion repository, please run `git clone https://github.com/CompVis/'
              'latent-diffusion.git` within the IntraPaint directory.')
        sys.exit(1)

    # pytorch-lightning changed the location of one needed dependency, but latent-diffusion was never updated.
    # This only requires a single minor update, so make that change here if necessary:
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
    if not check_import('taming'):
        print('Missing required taming-transformers repository, please run `git clone https://github.com/CompVis/'
              'taming-transformers.git` within the IntraPaint directory.')
        sys.exit(1)

# argument parsing:
parser = build_arg_parser(include_gen_params=False, include_edit_params=False)
parser.add_argument('--port', type=int, default=5555, required=False,
                    help='Port used when running in server mode.')
args = parser.parse_args()

device = get_device()
print('Using device:', device)
model_data = load_models(device, model_path=args.model_path, bert_path=args.bert_path, kl_path=args.kl_path,
                         steps=args.steps, clip_guidance=args.clip_guidance, cpu=args.cpu, ddpm=args.ddpm,
                         ddim=args.ddim)
model_params, model, diffusion, ldm, bert, clip_model, clip_preprocess, normalize = model_data
app = start_server(device, model_params, model, diffusion, ldm, bert, clip_model, clip_preprocess, normalize)
app.run(port=args.port, host='0.0.0.0')
