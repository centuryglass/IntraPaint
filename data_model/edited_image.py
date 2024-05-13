"""
Manages an edited image.

Main features
-------------
    - Saving, loading, and editing image files.
    - Tracking changes to an image through Qt signals.
    - Loading image generation parameters from image file metadata (A1111 metadata format only).
    - Saving adjusted image generation parameters to image files.
"""

import re
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtCore import QObject, QRect, QPoint, QSize, pyqtSignal
from PIL import Image, PngImagePlugin
from ui.image_utils import qimage_to_pil_image, pil_image_to_qimage

class EditedImage(QObject):
    """
    Represents an edited image.

    Signals
    -------
    content_changed:
        Emitted whenever image data changes in any way, or when the selected area changes.
    selection_changed: QRect
        Emitted whenever the bounds of the selected area change.
    size_changed: QSize
        Emitted when the size of the image changes.

    Common Exceptions Raised
    ------------------------
    RuntimeError:
        If a function that interacts with image data is called, but no image is loaded.
    """
    content_changed = pyqtSignal()
    selection_changed = pyqtSignal(QRect)
    size_changed = pyqtSignal(QSize)


    def __init__(self, config, image_data):
        """
        Initializes the image based on config values and optional image data.

        Parameters
        ----------
        config: Config
            Used for loading initial selection size, and for applying metadata.
        image_data: PIL Image or QImage or str, optional
            If image_data is a string, it must be a valid image path in a format supported by PIL and PyQt5.
        """
        super().__init__()
        self._config = config
        self._qimage = None
        self._metadata = None
        self.set_selection_bounds(QRect(QPoint(0, 0), self._config.get('edit_size')))
        if image_data is not None:
            self.set_image(image_data)


    def has_image(self):
        """Returns whether image data is currently loaded"""
        return self._qimage is not None


    def get_qimage(self):
        """Returns the image currently being edited as a QImage object"""
        if not self.has_image():
            raise RuntimeError('No image has been loaded')
        return self._qimage


    def get_pil_image(self):
        """Returns the image currently being edited as a PIL Image object"""
        if not self.has_image():
            raise RuntimeError('No image has been loaded')
        return qimage_to_pil_image(self._qimage)


    def update_metadata(self):
        """
        Adds image editing parameters from config to the image metadata, in a format compatible with the A1111
        stable-diffusion webui. Parameters will be applied to the image file when save_image is called.
        """
        if not self.has_image():
            return
        prompt = self._config.get('prompt')
        negative = self._config.get('negative_prompt')
        steps = self._config.get('sampling_steps')
        sampler = self._config.get('sampling_method')
        cfg_scale = self._config.get('guidance_scale')
        seed = self._config.get('seed')
        params = f"{prompt}\nNegative prompt: {negative}\nSteps: {steps}, Sampler: {sampler}, CFG scale:" + \
                 f"{cfg_scale}, Seed: {seed}, Size: 512x512"
        if self._metadata is None:
            self._metadata = {}
        self._metadata['parameters'] = params


    def set_image(self, image):
        """
        Loads a new image to be edited.

        Parameters
        ----------
        image: PIL Image or QImage or str
            If image_data is a string, it must be a valid image path in a format supported by PIL and PyQt5. If
            the image has associated metadata in the A1111 stable-diffusion webui format, that metadata will be
            preserved.
        """
        old_size = None if not self.has_image() else self.size()
        if isinstance(image, str):
            self._load_image_from_path(image)
        elif isinstance(image, QImage):
            self._qimage = image
        elif isinstance(image, Image.Image):
            self._qimage = pil_image_to_qimage(image)
        else:
            raise RuntimeError("ImageViewer.set_image: image was not a string, QImage, or PIL Image")
        # Make sure the selection still fits within image bounds:
        last_selection = self._selection
        self.set_selection_bounds(self._selection)
        # If set_selection_bounds changed anything, it will have already emitted both these signals:
        if last_selection == self._selection:
            self.selection_changed.emit(self.get_selection_bounds())
        if self.size() != old_size:
            self.size_changed.emit(self.size())
        self.content_changed.emit()


    def size(self):
        """Returns the edited image size in pixels as a QSize object."""
        if not self.has_image():
            raise RuntimeError('No image has been loaded')
        return self._qimage.size()

    def width(self):
        """Returns the edited image width in pixels."""
        return self.size().width()

    def height(self):
        """Returns the edited image height in pixels."""
        return self.size().height()

    def get_max_selection_size(self):
        """
        Returns the largest area that can be selected within the image, based on image size and the 'max_edit_size'
        config property
        """
        max_size = self._config.get('max_edit_size')
        return QSize(min(max_size.width(), self.width()), min(max_size.height(), self.height()))


    def get_selection_bounds(self):
        """Returns the bounds of the area selected for editing within the image."""
        return QRect(self._selection.topLeft(), self._selection.size())


    def set_selection_bounds(self, bounds_rect):
        """
        Updates the bounds of the selected area within the image. If `bounds_rect` exceeds the maximum selection size
        or doesn't fit fully within the image bounds, the closest valid region will be selected.
        """
        assert isinstance(bounds_rect, QRect)
        if not self.has_image():
            self._selection = bounds_rect
            return
        initial_bounds = bounds_rect
        bounds_rect = QRect(initial_bounds.topLeft(), initial_bounds.size())
        # Make sure that the selection fits within allowed size limits:
        min_size = self._config.get('min_edit_size')
        max_size = self.get_max_selection_size()
        if bounds_rect.width() > self._qimage.width():
            bounds_rect.setWidth(self._qimage.width())
        if bounds_rect.width() > max_size.width():
            bounds_rect.setWidth(max_size.width())
        if bounds_rect.width() < min_size.width():
            bounds_rect.setWidth(min_size.width())
        if bounds_rect.height() > self._qimage.height():
            bounds_rect.setHeight(self._qimage.height())
        if bounds_rect.height() > max_size.height():
            bounds_rect.setHeight(max_size.height())
        if bounds_rect.height() < min_size.height():
            bounds_rect.setHeight(min_size.height())

        # make sure the selection is within the image bounds:
        if bounds_rect.left() > (self._qimage.width() - bounds_rect.width()):
            bounds_rect.moveLeft(self._qimage.width() - bounds_rect.width())
        if bounds_rect.left() < 0:
            bounds_rect.moveLeft(0)
        if bounds_rect.top() > (self._qimage.height() - bounds_rect.height()):
            bounds_rect.moveTop(self._qimage.height() - bounds_rect.height())
        if bounds_rect.top() < 0:
            bounds_rect.moveTop(0)
        if bounds_rect != self._selection:
            self._selection = QRect(bounds_rect.topLeft(), bounds_rect.size())
            self.selection_changed.emit(self.get_selection_bounds())


    def get_selection_content(self):
        """Returns the contents of the selection bounds as a PIL Image object."""
        if not self.has_image():
            raise RuntimeError('No image has been loaded')
        cropped_image = self._qimage.copy(self._selection.left(),
                self._selection.top(),
                self._selection.width(),
                self._selection.height())
        return qimage_to_pil_image(cropped_image)


    def set_selection_content(self, image_data):
        """
        Replaces the contents of the selection bounds with new image content.

        Parameters
        ----------
        image_data: Image
            PIL Image data to draw into the selection. If the size of the image doesn't match the size of the
            selection, it will be scaled to fit.
        """
        if not self.has_image():
            raise RuntimeError('No image has been loaded')
        painter = QPainter(self._qimage)
        new_content = pil_image_to_qimage(image_data)
        painter.drawImage(self._selection, new_content)
        self.selection_changed.emit(self.get_selection_bounds())
        self.content_changed.emit()


    def has_metadata(self):
        """Returns whether the image has associated metadata that will be saved when `save_image` is called"""
        return bool(self._metadata and len(self._metadata) > 0)


    def get_metadata(self):
        """Returns a dict containing this image's metadata."""
        return self._metadata


    def save_image(self, image_path):
        """Saves the image as a .PNG file to the given path, preserving metadata if possible."""
        if not self.has_image():
            raise RuntimeError('No image has been loaded')
        image = qimage_to_pil_image(self._qimage)
        if self.has_metadata():
            info = PngImagePlugin.PngInfo()
            for key in self._metadata:
                try:
                    info.add_itxt(key, self._metadata[key])
                except AttributeError as err:
                    # Encountered some sort of image metadata that PIL knows how to read but not how to write.
                    # I've seen this a few times, mostly with images edited in Krita. This data isn't important to
                    # me, so it'll just be discarded. If it's important to you, open a GitHub issue with details or
                    # submit a PR and I'll take care of it.
                    print(f"failed to preserve '{key}' in metadata: {err}")
            image.save(image_path, 'PNG', pnginfo=info)
        else:
            image.save(image_path)


    def _load_image_from_path(self, image_path):
        image = Image.open(image_path)
        if hasattr(image, 'info') and image.info is not None:
            self._metadata = image.info
        else:
            self._metadata = None
        if 'parameters' in self._metadata:
            param_str = self._metadata['parameters']
            match = re.match(r'^(.*\n?.*)\nSteps: (\d+), Sampler: (.*), CFG scale: (.*), Seed: (.+), Size.*',
                    param_str)
            if match:
                prompt = match.group(1)
                negative = ''
                steps = int(match.group(2))
                sampler = match.group(3)
                cfg_scale = float(match.group(4))
                seed = int(match.group(5))
                divider_match = re.match('^(.*)\nNegative prompt: (.*)$', prompt)
                if divider_match:
                    prompt = divider_match.group(1)
                    negative = divider_match.group(2)
                print('Detected saved image gen data, applying to UI')
                try:
                    self._config.set('prompt', prompt)
                    self._config.set('negative_prompt', negative)
                    self._config.set('sampling_steps', steps)
                    self._config.set('sampling_method', sampler)
                    self._config.set('guidance_scale', cfg_scale)
                    self._config.set('seed', seed)
                except (TypeError, RuntimeError) as err:
                    print(f'Failed to load image gen data from metadata: {err}')
            else:
                print("Warning: image parameters do not match expected patterns, cannot be used. " + \
                      f"parameters:{param_str}")
        self._qimage = pil_image_to_qimage(image)
        self._qimage.convertTo(QImage.Format_RGB888)
        if self._qimage.isNull():
            self._qimage = None
            raise RuntimeError(f"'{image}' is not a valid image file.")
