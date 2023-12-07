from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PIL import Image, ImageFilter
import os, glob, sys

from data_model.config import Config
from data_model.edited_image import EditedImage
from data_model.mask_canvas import MaskCanvas
from data_model.sketch_canvas import SketchCanvas

from ui.window.main_window import MainWindow
from ui.modal.new_image_modal import NewImageModal
from ui.modal.resize_canvas_modal import ResizeCanvasModal
from ui.modal.image_scale_modal import ImageScaleModal
from ui.modal.modal_utils import *

from controller.spacenav import SpacenavManager

# Optional spacenav support:
try:
    import spacenav, atexit
except ImportError:
    print('spaceMouse support not installed.')
    spacenav = None

class BaseInpaintController():
    """
    Shared base class for managing impainting. 

    Subclasses will need to override self._inpaint, and may also want to override self.startApp.
    """
    def __init__(self, args):
        self._app = QApplication(sys.argv)
        screen = self._app.primaryScreen()
        size = screen.availableGeometry()

        if size.height() < 1000:
            font = self._app.font()
            font.setPointSize(6)
            self._app.setFont(font)

        self._config = Config()
        self._adjustConfigDefaults()
        self._config.applyArgs(args)
        self._editedImage = EditedImage(self._config, args.init_image)
        self._window = None

        initialSelectionSize = self._editedImage.getSelectionBounds().size()
        self._maskCanvas = MaskCanvas(self._config, initialSelectionSize)
        self._sketchCanvas = SketchCanvas(self._config, initialSelectionSize)
        # Connect mask/sketch size to image selection size:
        def resizeCanvases(selectionBounds):
            size = selectionBounds.size()
            self._maskCanvas.resize(size)
            self._sketchCanvas.resize(size)
        self._editedImage.selectionChanged.connect(resizeCanvases)

        self._thread = None

        # Set up timelapse image saving if it is configured:
        timelapsePath = self._config.get('timelapsePath')
        if timelapsePath != '':
            # Make sure path exists, find first unused image index:
            if not os.path.exists(timelapsePath):
                os.mkdir(timelapsePath)
            elif os.path.isfile(timelapsePath):
                print("timelapsePath: expected directory path, got file: " + timelapsePath)
            self._nextTimelapseFrame = 0
            for name in glob.glob(f"{timelapsePath}/*.png"):
                n=int(os.path.splitext(ntpath.basename(name))[0])
                if n > self._lastTimelapseFrame:
                    self._nextTimelapseFrame = n + 1
            def saveTimelapseImage():
                filename = os.path.join(self._timelapsePath, f"{self._nextTimelapseFrame:05}.png")
                self._editedImage.saveImage(filename)
                self._nextTimelapseFrame += 1
            editedImage.contentChanged.connect(saveTimelapseImage)

    def _adjustConfigDefaults(self):
        # no-op, override to adjust config before data initialization
        return

    def initSettings(self, settingsModal):
        """ Returns false if disabled, true if settings were initialized"""
        return False

    def refreshSettings(self, settingsModal):
        raise Exception('refreshSettings not implemented!')

    def updateSettings(self, changedSettings):
        raise Exception('refreshSettings not implemented!')

    def windowInit(self):
        screen = self._app.primaryScreen()
        size = screen.availableGeometry()
        self._window = MainWindow(self._config, self._editedImage, self._maskCanvas, self._sketchCanvas, self)
        self._window.setGeometry(0, 0, size.width(), size.height())
        self._window.show()

    def startApp(self):
        self.windowInit()

        # Configure support for spacemouse panning, if relevant:
        self.navManager = SpacenavManager(self._window, self._editedImage)
        self.navManager.startThread()

        self._app.exec_()
        sys.exit()

    # File IO handling:
    def newImage(self):
        defaultSize = self._config.get('editSize')
        imageModal = NewImageModal(defaultSize.width(), defaultSize.height())
        imageSize = imageModal.showImageModal()
        if imageSize and ((not self._editedImage.hasImage()) or \
                requestConfirmation(self._window, "Create new image?", "This will discard all unsaved changes.")):
            newImage = Image.new('RGB', (imageSize.width(), imageSize.height()), color = 'white')
            self._editedImage.setImage(newImage)

    def saveImage(self):
        if not self._editedImage.hasImage():
            showErrorDialog(self._window, "Save failed", "Open an image first before trying to save.")
            return
        file, fileSelected = openImageFile(self._window, mode='save', selectedFile = self._config.get("lastFilePath"))
        try:
            if file and fileSelected:
                self._editedImage.saveImage(file)
                self._config.set("lastFilePath", file)
        except Exception as err:
            showErrorDialog(self._window, "Save failed", str(err))
            print(f"Saving image failed: {err}")

    def loadImage(self):
        file, fileSelected = openImageFile(self._window)
        if file and fileSelected:
            try:
                self._editedImage.setImage(file)
                self._config.set("lastFilePath", file)
            except Exception as err:
                showErrorDialog(self._window, "Open failed", err)

    def reloadImage(self):
        filePath = self._config.get("lastFilePath")
        if filePath == "":
            showErrorDialog(self._window, "Reload failed", f"Enter an image path or click 'Open Image' first.")
            return
        if not os.path.isfile(filePath):
            showErrorDialog(self._window, "Reload failed", f"Image path '{filePath}' is not a valid file.")
            return
        if (not self._editedImage.hasImage()) or \
                requestConfirmation(self._window, "Reload image?", "This will discard all unsaved changes."):
            self._editedImage.setImage(filePath)

    def resizeCanvas(self):
        if not self._editedImage.hasImage():
            showErrorDialog(self._window, "Unable to resize", "Load or create an image first before trying to resize.")
            return
        resizeModal = ResizeCanvasModal(self._editedImage.getQImage())
        newSize, offset = resizeModal.showResizeModal();
        if newSize is None:
            return
        newImage = Image.new('RGB', (newSize.width(), newSize.height()), color = 'white')
        newImage.paste(self._editedImage.getPilImage(), (offset.x(), offset.y()))
        self._editedImage.setImage(newImage)
        if offset.x() > 0 or offset.y() > 0:
            self._editedImage.setSelectionBounds(self._editedImage.getSelectionBounds().translated(offset))

    def scaleImage(self):
        if not self._editedImage.hasImage():
            showErrorDialog(self._window, "Unable to scale", "Load or create an image first before trying to scale.")
            return
        width = self._editedImage.width()
        height = self._editedImage.height()
        scaleModal = ImageScaleModal(width, height, self._config)
        newSize = scaleModal.showImageModal()
        if newSize is not None:
            self._scale(newSize)

    def _scale(self, newSize): # Override to allow ML upscalers:
        width = self._editedImage.width()
        height = self._editedImage.height()
        if newSize is None or (newSize.width() == width and newSize.height() == height):
            return
        image = self._editedImage.getPilImage()
        scaleMode = None
        if (newSize.width() <= width and newSize.height() <= height): #downscaling
            scaleMode = self._config.get('downscaleMode')
        else:
            scaleMode = self._config.get('upscaleMode')
        scaledImage = image.resize((newSize.width(), newSize.height()), scaleMode)
        self._editedImage.setImage(scaledImage)

    def _startThread(self, threadWorker, loadingText=None):
        if self._thread is not None:
            raise Exception('Tried to start a new async operation while the previous one is still running')
        self._window.setIsLoading(True, loadingText)
        self._thread = QThread()
        self._worker = threadWorker
        self._worker.moveToThread(self._thread);
        def clearWorker():
            self._thread.quit()
            self._window.setIsLoading(False)
            self._worker.deleteLater()
            self._worker = None
        self._worker.finished.connect(clearWorker)
        self._thread.started.connect(self._worker.run)
        def clearOldThread():
            self._thread.deleteLater()
            self._thread = None
        self._thread.finished.connect(clearOldThread)
        self._thread.start()

    # Image generation handling:


    def _inpaint(self):
        raise Exception('BaseInpaintController should not be used directly, use a subclass.')

    def _applyStatusUpdate(self, statusDict):
        return

    def startAndManageInpainting(self):
        if not self._editedImage.hasImage():
            showErrorDialog(self._window, "Failed", "Load an image for editing before trying to start inpainting.")
            return
        if self._thread is not None:
            showErrorDialog(self._window, "Failed", "Existing inpainting operation not yet finished, wait a little longer.")
            return
        upscaleMode = self._config.get('upscaleMode')
        downscaleMode = self._config.get('downscaleMode')
        def resizeImage(pilImage, width, height):
            """Resize a PIL image using the appropriate scaling mode:"""
            if width == pilImage.width and height == pilImage.height:
                return pilImage
            if width > pilImage.width or height > pilImage.height:
                return pilImage.resize((width, height), upscaleMode)
            return pilImage.resize((width, height), downscaleMode)

        selection = self._editedImage.getSelectionContent()

        # If sketch mode was used, write the sketch onto the image selection:
        inpaintImage = selection.copy()
        inpaintMask = self._maskCanvas.getImage()
        sketchImage = self._sketchCanvas.getImage()
        sketchImage = resizeImage(sketchImage, inpaintImage.width, inpaintImage.height).convert('RGBA')
        if self._sketchCanvas.hasSketch: 
            inpaintImage = inpaintImage.convert('RGBA')
            inpaintImage = Image.alpha_composite(inpaintImage, sketchImage).convert('RGB')
        keepSketch = self._sketchCanvas.hasSketch and self._config.get('saveSketchInResult')

        # If necessary, scale image and mask to match the edit size. Keep the unscaled version so it can be used for
        # compositing if "keep sketch" is checked.
        unscaledInpaintImage = inpaintImage.copy()

        
        editSize = self._config.get('editSize')
        if inpaintImage.width != editSize.width() or inpaintImage.height != editSize.height():
            inpaintImage = resizeImage(inpaintImage, editSize.width(), editSize.height())
        if inpaintMask.width != editSize.width() or inpaintMask.height != editSize.height():
            inpaintMask = resizeImage(inpaintMask, editSize.width(), editSize.height())

        doInpaint = lambda img, mask, save, statusSignal: self._inpaint(img, mask, save, statusSignal)
        config = self._config
        class InpaintThreadWorker(QObject):
            finished = pyqtSignal()
            imageReady = pyqtSignal(Image.Image, int)
            statusSignal = pyqtSignal(dict)
            errorSignal = pyqtSignal(Exception)

            def __init__(self):
                super().__init__()

            def run(self):
                def sendImage(img, idx):
                    self.imageReady.emit(img, idx)
                try:
                    doInpaint(inpaintImage, inpaintMask, sendImage, self.statusSignal)
                except Exception as err:
                    self.errorSignal.emit(err)
                self.finished.emit()
        worker = InpaintThreadWorker()

        def handleError(err):
            self._window.setSampleSelectorVisible(False)
            showErrorDialog(self._window, "Inpainting failure", err)
        worker.errorSignal.connect(handleError)

        def updateStatus(statusDict):
            self._applyStatusUpdate(statusDict)
        worker.statusSignal.connect(updateStatus)

        def loadSamplePreview(img, idx):
            if ((config.get('editMode') == 'Inpaint')) and (config.get('removeUnmaskedChanges') or img.width != selection.width or img.height != selection.height):
                pointFn = lambda p: 255 if p < 1 else 0
                if config.get('inpaintMasked') == 'Inpaint not masked':
                    pointFn = lambda p: 0 if p < 1 else 255
                maskAlpha = inpaintMask.convert('L').point(pointFn).filter(ImageFilter.GaussianBlur())
                img = resizeImage(img, selection.width, selection.height)
                maskAlpha = resizeImage(maskAlpha, selection.width, selection.height)
                img = Image.composite(unscaledInpaintImage if keepSketch else selection, img, maskAlpha)
            self._window.loadSamplePreview(img, idx)
        worker.imageReady.connect(loadSamplePreview)
        self._window.setSampleSelectorVisible(True)
        self._startThread(worker)

    def selectAndApplySample(self, sampleImage):
        if self._config.get('saveSketchInResult'):
            sourceSelection = self._editedImage.getSelectionContent()
            sketchImage = self._sketchCanvas.getImage().resize((sourceSelection.width, sourceSelection.height),
                    self._config.get('downscaleMode')).convert('RGBA')
            sourceSelection = Image.alpha_composite(sourceSelection.convert('RGBA'), sketchImage).convert('RGB')
            self._editedImage.setSelectionContent(sourceSelection)
            self._sketchCanvas.clear()
        if sampleImage is not None and isinstance(sampleImage, Image.Image):
            self._editedImage.setSelectionContent(sampleImage)

    # Misc. other features:

    def zoomOut(self):
        try:
            image = self._editedImage.getPilImage()
            # Find next unused number in ./zoom/xxxxx.png:
            zoomCount = 0
            while os.path.exists(f"zoom/{zoomCount:05}.png"):
                zoomCount += 1
            # Save current image, update zoom count:
            image.save(f"zoom/{zoomCount:05}.png")
            zoomCount += 1

            # scale image content to 86%, paste it centered into the image:
            newSize = (int(image.width * 0.86), int(image.height * 0.86))
            scaledImage = image.resize(newSize, self._config.get('downscaleMode'))
            newImage = Image.new('RGB', (image.width, image.height), color = 'white')
            insertAt = (int(image.width * 0.08), int(image.height * 0.08))
            newImage.paste(scaledImage, insertAt)
            self._editedImage.setImage(newImage)

            # reload zoom mask:
            self._maskCanvas.setImage('resources/zoomMask.png')
        except Exception as err:
            showErrorDialog(self._window, "Zoom failed", err)
