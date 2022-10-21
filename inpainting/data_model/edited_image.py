from PyQt5.QtGui import QImage
from PyQt5.QtCore import QObject, QRect, QPoint, QSize, pyqtSignal
from PIL import Image, PngImagePlugin
from inpainting.image_utils import qImageToImage, imageToQImage
import re

class EditedImage(QObject):
    contentChanged = pyqtSignal()
    selectionChanged = pyqtSignal(QRect)
    sizeChanged = pyqtSignal(QSize)

    def __init__(self, config, initialImage):
        super().__init__()
        self._config = config
        self._qimage = None
        self._metadata = None
        self.setSelectionBounds(QRect(QPoint(0, 0), self._config.get('maxEditSize')))
        if initialImage is not None:
            self.setImage(initialImage)

    def hasImage(self):
        """Returns whether image data is currently loaded"""
        return self._qimage is not None

    def getQImage(self):
        """Returns the image currently being edited as a QImage object"""
        if not self.hasImage():
            raise Exception('No image has been loaded')
        return self._qimage

    def getPilImage(self):
        """Returns the image currently being edited as a PIL Image object"""
        if not self.hasImage():
            raise Exception('No image has been loaded')
        return qImageToImage(self._qimage)

    def setImage(self, image):
        """Loads a new image to be edited from a file path, QImage, or PIL image."""
        oldSize = None if not self.hasImage() else self.size()
        if isinstance(image, str):
            image = Image.open(image)
            if hasattr(image, 'info') and image.info is not None:
                self._metadata = image.info
            else:
                self._metadata = None
            if 'parameters' in self._metadata:
                paramStr = self._metadata['parameters']
                match = re.match('^(.*\n?.*)\nSteps: (\d+), Sampler: (.*), CFG scale: (.*), Seed: (.+), Size.*', paramStr)
                if match:
                    prompt = match.group(1)
                    negative = ''
                    steps = int(match.group(2))
                    sampler = match.group(3)
                    cfgScale = float(match.group(4))
                    seed = int(match.group(5))
                    dividerMatch = re.match('^(.*)\nNegative prompt: (.*)$', prompt)
                    if dividerMatch:
                        prompt = dividerMatch.group(1)
                        negative = dividerMatch.group(2)
                    print('Detected saved image gen data, applying to UI')
                    try:
                        self._config.set('prompt', prompt)
                        self._config.set('negativePrompt', negative)
                        self._config.set('samplingSteps', steps)
                        self._config.set('samplingMethod', sampler)
                        self._config.set('cfgScale', cfgScale)
                        print(f"seed: {seed}")
                        self._config.set('seed', seed)
                    except Exception as err:
                        print(f'Failed to load image gen data from metadata: {err}')
                else:
                    print(f"Warning: image parameters do not match expected patterns, cannot be used. parameters:{paramStr}")
            self._qimage = imageToQImage(image)
            self._qimage.convertTo(QImage.Format_RGB888)
            if self._qimage.isNull():
                self._qimage = None
                raise Exception(f"'{image}' is not a valid image file.")
        elif isinstance(image, QImage):
            self._qimage = image
        elif isinstance(image, Image.Image):
            self._qimage = imageToQImage(image)
        else:
            raise Exception("ImageViewer.setImage: image was not a string, QImage, or PIL Image")
        # Make sure the selection still fits within image bounds:
        lastSelection = self._selection
        self.setSelectionBounds(self._selection)
        # If setSelectionBounds changed anything, it will have already emitted both these signals:
        if lastSelection == self._selection:
            self.selectionChanged.emit(self.getSelectionBounds())
        if self.size() != oldSize:
            self.sizeChanged.emit(self.size())
        self.contentChanged.emit()

    def size(self):
        if not self.hasImage():
            raise Exception('No image has been loaded')
        return self._qimage.size()

    def width(self):
        return self.size().width()

    def height(self):
        return self.size().height()

    def getMaxSelectionSize(self):
        maxSize = self._config.get('maxEditSize')
        # If scaling is enabled, size boxes shouldn't be constrained by max edit size:
        if self._config.get('scaleSelectionBeforeInpainting'):
            maxSize = self.size()
        # If not scaling, make sure maxSize is a multiple of 64:
        else:
            maxSize = QSize(min(maxSize.width(), self.width() - (self.width() % 64)),
                    min(maxSize.height(), self.height() - (self.height() % 64)))
        return maxSize

    def getSelectionBounds(self):
        return QRect(self._selection.topLeft(), self._selection.size())

    def setSelectionBounds(self, boundsRect):
        assert isinstance(boundsRect, QRect)
        if not self.hasImage():
            self._selection = boundsRect
            return
        initialBounds = boundsRect
        boundsRect = QRect(initialBounds.topLeft(), initialBounds.size())
        # Make sure that the selection fits within allowed size limits:
        minSize = self._config.get('minEditSize')
        maxSize = self.getMaxSelectionSize()
        if boundsRect.width() > self._qimage.width():
            boundsRect.setWidth(self._qimage.width())
        if boundsRect.width() > maxSize.width():
            boundsRect.setWidth(maxSize.width())
        if boundsRect.width() < minSize.width():
            boundsRect.setWidth(minSize.width())
        if boundsRect.height() > self._qimage.height():
            boundsRect.setHeight(self._qimage.height())
        if boundsRect.height() > maxSize.height():
            boundsRect.setHeight(maxSize.height())
        if boundsRect.height() < minSize.height():
            boundsRect.setHeight(minSize.height())

        # make sure the selection is within the image bounds:
        if boundsRect.left() > (self._qimage.width() - boundsRect.width()):
            boundsRect.moveLeft(self._qimage.width() - boundsRect.width())
        if boundsRect.left() < 0:
            boundsRect.moveLeft(0)
        if boundsRect.top() > (self._qimage.height() - boundsRect.height()):
            boundsRect.moveTop(self._qimage.height() - boundsRect.height())
        if boundsRect.top() < 0:
            boundsRect.moveTop(0)
        if boundsRect != self._selection:
            self._selection = QRect(boundsRect.topLeft(), boundsRect.size())
            self.selectionChanged.emit(self.getSelectionBounds())
        
    def getSelectionContent(self):
        """Gets a copy of the image, cropped to the current selection area."""
        if not self.hasImage():
            raise Exception('No image has been loaded')
        cropped_image = self._qimage.copy(self._selection.left(),
                self._selection.top(),
                self._selection.width(),
                self._selection.height())
        return qImageToImage(cropped_image)

    def setSelectionContent(self, imageData):
        """Gets a copy of the image, cropped to the current selection area."""
        if not self.hasImage():
            raise Exception('No image has been loaded')
        pilImage = self.getPilImage()
        pilImage.paste(imageData, (self._selection.x(), self._selection.y()))
        self.setImage(pilImage)
        self.contentChanged.emit()

    def hasMetadata(self):
        return bool(self._metadata and len(self._metadata) > 0)

    def getMetadata(self):
        return self._metadata

    def saveImage(self, imagePath):
        if not self.hasImage():
            raise Exception('No image has been loaded')
        if self.hasMetadata():
            image = qImageToImage(self._qimage)
            info = PngImagePlugin.PngInfo()
            for key in self._metadata:
                info.add_itxt(key, self._metadata[key])
            image.save(imagePath, 'PNG', pnginfo=info)
        else:
            self._qimage.save(imagePath)
