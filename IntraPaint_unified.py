# Runs the inpainting UI and image generation together
import sys
from PyQt5.QtWidgets import QApplication
from edit_ui.main_window import MainWindow
from startup.utils import *

# argument parsing:
parser = buildArgParser(defaultModel='inpaint.pt', includeEditParams=False)
parser.add_argument('--init_edit_image', type=str, required = False, default = None,
                   help='initial image to edit')
parser.add_argument('--edit_width', type = int, required = False, default = 256,
                    help='width of the edit image in the generation frame (need to be multiple of 8)')

parser.add_argument('--edit_height', type = int, required = False, default = 256,
                            help='height of the edit image in the generation frame (need to be multiple of 8)')
parser.add_argument('--timelapse_path', type = str, required = False,
                            help='subdirectory to store snapshots for creating a timelapse of all editing operations')
parser.add_argument('--ui_test', dest='ui_test', action='store_true') # Test UI without loading real functionality
args = parser.parse_args()

if args.ui_test:
    print('Testing inpainting UI without loading image generation')
    app = QApplication(sys.argv)
    screen = app.primaryScreen()
    size = screen.availableGeometry()
    def inpaint(selection, mask, prompt, batch_size, num_batches, showSample,
            negative = "",
            guidanceScale = 5,
            skipSteps = 0):
        print("Mock inpainting call:")
        print(f"\tselection: {selection}")
        print(f"\tmask: {mask}")
        print(f"\tprompt: {prompt}")
        print(f"\tbatchSize: {batch_size}")
        print(f"\tbatchCount: {num_batches}")
        print(f"\tshowSample: {showSample}")
        print(f"\tnegative: {negative}")
        print(f"\tguidanceScale: {guidanceScale}")
        print(f"\tskipSteps: {skipSteps}")
        testSample = Image.open(open('mask.png', 'rb')).convert('RGB')
        showSample(testSample, 0, 0)
    d = MainWindow(size.width(), size.height(), None, inpaint)
    d.setGeometry(0, 0, size.width(), size.height())
    d.applyArgs(args)
    d.show()
    app.exec_()
    sys.exit()

import gc
import os
from PIL import Image
import torch
from torchvision.transforms import functional as TF
import numpy as np

from startup.load_models import loadModels
from startup.create_sample_function import createSampleFunction
from startup.generate_samples import generateSamples
from startup.ml_utils import *

device = torch.device('cuda:0' if (torch.cuda.is_available() and not args.cpu) else 'cpu')
print('Using device:', device)
if args.seed >= 0:
    torch.manual_seed(args.seed)


model_params, model, diffusion, ldm, bert, clip_model, clip_preprocess, normalize = loadModels(device,
        model_path=args.model_path,
        bert_path=args.bert_path,
        kl_path=args.kl_path,
        steps = args.steps,
        clip_guidance = args.clip_guidance,
        cpu = args.cpu,
        ddpm = args.ddpm,
        ddim = args.ddim)
print("Loaded models")

app = QApplication(sys.argv)
screen = app.primaryScreen()
size = screen.availableGeometry()
def inpaint(selection, mask, prompt, batch_size, num_batches, showSample,
        negative = "",
        guidanceScale = 5,
        skipSteps = 0):
    gc.collect()
    if not isinstance(selection, Image.Image):
        raise Exception(f'Expected PIL Image selection, got {selection}')
    if not isinstance(mask, Image.Image):
        raise Exception(f'Expected PIL Image mask, got {mask}')
    if selection.width != mask.width:
        raise Exception(f'Selection and mask widths should match, found {selection.width} and {mask.width}')
    if selection.height != mask.height:
        raise Exception(f'Selection and mask widths should match, found {selection.width} and {mask.width}')



    sample_fn, clip_score_fn = createSampleFunction(
            device,
            model,
            model_params,
            bert,
            clip_model,
            clip_preprocess,
            ldm,
            diffusion,
            normalize,
            image=None,
            mask=mask,
            prompt=prompt,
            negative=negative,
            guidance_scale=guidanceScale,
            batch_size=batch_size,
            edit=selection,
            width=selection.width,
            height=selection.height,
            edit_width=selection.width,
            edit_height=selection.height,
            cutn=args.cutn,
            clip_guidance=args.clip_guidance,
            skip_timesteps=skipSteps,
            ddpm=args.ddpm,
            ddim=args.ddim)
    def save_sample(i, sample, clip_score=False):
        foreachImageInSample(
                sample,
                batch_size,
                ldm,
                lambda k, img: showSample(img, k, i))

    generateSamples(device, ldm, diffusion, sample_fn, save_sample, batch_size, num_batches, selection.width, selection.height)

d = MainWindow(size.width(), size.height(), None, inpaint)
d.applyArgs(args)
d.setGeometry(0, 0, size.width(), size.height())
d.show()
app.exec_()
sys.exit()
