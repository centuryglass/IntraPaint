import argparse
import sys
from startup.utils import *
from PyQt5.QtWidgets import QApplication
from edit_ui.main_window import MainWindow
from PyQt5 import QtCore
from PyQt5.QtWidgets import QInputDialog
from PIL import Image
import requests
import io

# argument parsing:
parser = argparse.ArgumentParser()
parser.add_argument('--text', type = str, required = False, default = '',
                    help='your text prompt')
parser.add_argument('--init_edit_image', type=str, required = False, default = None,
                   help='initial image to edit')
parser.add_argument('--edit_width', type = int, required = False, default = 256,
                    help='width of the edit image in the generation frame (need to be multiple of 8)')
parser.add_argument('--edit_height', type = int, required = False, default = 256,
                            help='height of the edit image in the generation frame (need to be multiple of 8)')
parser.add_argument('--server_url', type = str, required = False, default = '',
                    help='Image generation server URL. If not provided, you will be prompted for a URL on launch.')
parser.add_argument('--fast_ngrok_connection', type = str, required = False, default = '',
                    help='If true, connection rates will not be limited when using ngrok. This may cause rate limiting if you do not have a paid account.')
parser.add_argument('--timelapse_path', type = str, required = False,
                            help='subdirectory to store snapshots for creating a timelapse of all editing operations')

args = parser.parse_args()
app = QApplication(sys.argv)
screen = app.primaryScreen()
size = screen.availableGeometry()
global window
def inpaint(selection, mask, prompt, batchSize, batchCount, showSample, negative="", guidanceScale=5, skipSteps=0):
    body = {
        'batch_size': batchSize,
        'num_batches': batchCount,
        'edit': imageToBase64(selection),
        'mask': imageToBase64(mask),
        'prompt': prompt,
        'negative': negative,
        'guidanceScale': guidanceScale,
        'skipSteps': skipSteps,
        'width': selection.width,
        'height': selection.height
    }

    def errorCheck(serverResponse, contextStr):
        if serverResponse.status_code != 200:
            if serverResponse.content and ('application/json' in serverResponse.headers['content-type']) \
                    and serverResponse.json() and 'error' in serverResponse.json():
                raise Exception(f"{serverResponse.status_code} response to {contextStr}: {serverResponse.json()['error']}")
            else:
                print("RES")
                print(serverResponse.content)
                raise Exception(f"{serverResponse.status_code} response to {contextStr}: unknown error")
    res = requests.post(args.server_url, json=body, timeout=30)
    errorCheck(res, 'New inpainting request')
        
    # POST to args.server_url, check response
    # If invalid or error response, throw Exception
    samples = {}
    in_progress = True
    errorCount = 0
    maxErrors = 10
    # refresh times in microseconds:
    minRefresh = 300000
    maxRefresh = 60000000
    if('.ngrok.io' in args.server_url and not args.fast_ngrok_connection):
        # Free ngrok accounts only allow 20 connections per minute, lower the refresh rate to avoid failures:
        minRefresh = 3000000

    while in_progress:
        sleepTime = min(minRefresh * pow(2, errorCount), maxRefresh)
        print(f"Checking for response in {sleepTime//1000} ms...")
        QtCore.QThread.usleep(sleepTime)
        # GET server_url/sample, sending previous samples:
        res = None
        try:
            res = requests.get(f'{args.server_url}/sample', json={'samples': samples}, timeout=30)
            errorCheck(res, 'sample update request')
        except Exception as err:
            errorCount += 1
            print(f'Error {errorCount}: {err}')
            if errorCount > maxErrors:
                print('Inpainting failed, reached max retries.')
                break
            else:
                continue
        errorCount = 0 # Reset error count on success.


        # On valid response, for each entry in res.json.sample:
        jsonBody = res.json()
        if 'samples' not in jsonBody:
            continue
        for sampleName in jsonBody['samples'].keys():
            try:
                sampleImage = loadImageFromBase64(jsonBody['samples'][sampleName]['image'])
                idx = int(sampleName) % batchSize
                batch = int(sampleName) // batchSize
                showSample(sampleImage, idx, batch)
                samples[sampleName] = jsonBody['samples'][sampleName]['timestamp']
            except Exception as err:
                print(f'Warning: {err}')
                errorCount += 1
                continue
        in_progress = jsonBody['in_progress']

window = MainWindow(size.width(), size.height(), None, inpaint)
window.applyArgs(args)
window.setGeometry(0, 0, size.width(), size.height())
window.show()

def promptForURL(promptText):
    newUrl = QInputDialog.getText(window, 'Inpainting UI', promptText)
    if newUrl[1] == False: # User clicked 'Cancel'
        sys.exit()
    if newUrl[0] != '':
        args.server_url=newUrl[0]

# Get URL if one was not provided on the command line:
while args.server_url == '':
    promptForURL('Enter server URL:')

# Check connection:
def healthCheckPasses():
    try:
        res = requests.get(args.server_url, timeout=30)
        return res.status_code == 200 and ('application/json' in res.headers['content-type']) \
            and 'success' in res.json() and res.json()['success'] == True
    except Exception as err:
        print(f"error connecting to {args.server_url}: {err}")
        return False
while not healthCheckPasses():
    promptForURL('Server connection failed, enter a new URL or click "OK" to retry')
app.exec_()
sys.exit()
