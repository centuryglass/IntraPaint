"""
BaseController coordinates primary application functionality across all operation modes. Each image generation and
editing method supported by IntraPaint should have its own BaseController subclass.
"""

from PyQt5.QtWidgets import QApplication, QStyleFactory
from PyQt5.QtCore import Qt, QObject, QThread, QSize, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QPixmap
from PIL import Image, ImageFilter
import os, glob, sys, tempfile

from data_model.config import Config
from data_model.edited_image import EditedImage
from data_model.canvas.mask_canvas import MaskCanvas
from data_model.canvas.sketch_canvas import SketchCanvas

from ui.window.main_window import MainWindow
from ui.modal.new_image_modal import NewImageModal
from ui.modal.resize_canvas_modal import ResizeCanvasModal
from ui.modal.image_scale_modal import ImageScaleModal
from ui.modal.modal_utils import *
from ui.util.contrast_color import contrast_color
from ui.util.screen_size import screen_size


from controller.spacenav import SpacenavManager

# Optional spacenav support:
try:
    import spacenav, atexit
except ImportError as err:
    print(f'spaceMouse support not enabled: {err}')
    spacenav = None

class BaseInpaintController():
    """
    Shared base class for managing impainting. 

    Subclasses will need to override self._inpaint, and may also want to override self.startApp.
    """
    def __init__(self, args):
        self._app = QApplication(sys.argv)
        screen = self._app.primaryScreen()
        def screen_area(screen):
            if screen is None:
                return 0
            return screen.availableGeometry().width() * screen.availableGeometry().height()
        for s in self._app.screens():
            if screen_area(s) > screen_area(screen):
                screen = s
        size = screen.availableGeometry()

        self._config = Config()
        self._adjust_config_defaults()
        self._config.apply_args(args)

        self._edited_image = EditedImage(self._config, args.init_image)
        self._window = None

        initial_selection_size = self._edited_image.get_selection_bounds().size()
        self._mask_canvas = MaskCanvas(self._config, initial_selection_size)

        #self._sketch_canvas = SketchCanvas(self._config, initial_selection_size)
        try:
            from data_model.canvas.brushlib_canvas import BrushlibCanvas
            self._sketch_canvas = BrushlibCanvas(self._config, initial_selection_size)
        except ImportError as err: # fallback to old implementation:
            print(f"Brushlib import failed: {err}")
            self._sketch_canvas = SketchCanvas(self._config, initial_selection_size)

        # Connect mask/sketch size to image selection size:
        def resize_canvases(selection_bounds):
            size = selection_bounds.size()
            self._mask_canvas.resize(size)
            self._sketch_canvas.resize(size)
        self._edited_image.selection_changed.connect(resize_canvases)

        self._thread = None

    def _adjust_config_defaults(self):
        # no-op, override to adjust config before data initialization
        return

    def init_settings(self, settings_modal):
        """ Returns false if disabled, true if settings were initialized"""
        return False

    def refresh_settings(self, settings_modal):
        raise Exception('refresh_settings not implemented!')

    def update_settings(self, changed_settings):
        raise Exception('update_settings not implemented!')

    def window_init(self):
        self._window = MainWindow(self._config, self._edited_image, self._mask_canvas, self._sketch_canvas, self)
        size = screen_size(self._window)
        self._window.setGeometry(0, 0, size.width(), size.height())
        self._window.setMaximumHeight(size.height())
        self._window.setMaximumWidth(size.width())
        self.fix_styles()
        self._window.show()

    def fix_styles(self):
        try:
            self._app.setStyle(self._config.get('style'))
            theme = self._config.get('theme')
            if theme.startswith('qdarktheme_'):
                import qdarktheme
                if theme.endswith('_light'):
                    qdarktheme.setup_theme("light")
                elif theme.endswith('_auto'):
                    qdarktheme.setup_theme("auto")
                else:
                    qdarktheme.setup_theme()
            elif theme.startswith('qt_material_'):
                from qt_material import apply_stylesheet
                xmlFile = theme[len('qt_material_'):]
                apply_stylesheet(self._app, theme=xmlFile)
        except ModuleNotFoundError:
            print('Failed to load theme ' + self._config.get('style'))
        font = self._app.font()
        font.setPointSize(self._config.get('fontPointSize'))
        self._app.setFont(font)


    def start_app(self):
        self.window_init()

        # Configure support for spacemouse panning, if relevant:
        self._nav_manager = SpacenavManager(self._window, self._edited_image)
        self._nav_manager.start_thread()

        self._app.exec_()
        sys.exit()


    # File IO handling:
    def new_image(self):
        default_size = self._config.get('editSize')
        image_modal = NewImageModal(default_size.width(), default_size.height())
        image_size = image_modal.show_image_modal()
        if image_size and ((not self._edited_image.has_image()) or \
                request_confirmation(self._window, "Create new image?", "This will discard all unsaved changes.")):
            new_image = Image.new('RGB', (image_size.width(), image_size.height()), color = 'white')
            self._edited_image.set_image(new_image)


    def save_image(self):
        if not self._edited_image.has_image():
            show_error_dialog(self._window, "Save failed", "Open an image first before trying to save.")
            return
        file, file_selected = open_image_file(self._window, mode='save', selected_file = self._config.get("lastFilePath"))
        try:
            if file and file_selected:
                self._edited_image.save_image(file)
                self._config.set("lastFilePath", file)
        except Exception as err:
            show_error_dialog(self._window, "Save failed", str(err))
            print(f"Saving image failed: {err}")
            raise err

    def load_image(self):
        file, file_selected = open_image_file(self._window)
        if file and file_selected:
            try:
                self._edited_image.set_image(file)
                self._config.set("lastFilePath", file)
            except Exception as err:
                show_error_dialog(self._window, "Open failed", err)

    def reload_image(self):
        filePath = self._config.get("lastFilePath")
        if filePath == "":
            show_error_dialog(self._window, "Reload failed", f"Enter an image path or click 'Open Image' first.")
            return
        if not os.path.isfile(filePath):
            show_error_dialog(self._window, "Reload failed", f"Image path '{filePath}' is not a valid file.")
            return
        if (not self._edited_image.has_image()) or \
                request_confirmation(self._window, "Reload image?", "This will discard all unsaved changes."):
            self._edited_image.set_image(filePath)

    def resize_canvas(self):
        if not self._edited_image.has_image():
            show_error_dialog(self._window, "Unable to resize", "Load or create an image first before trying to resize.")
            return
        resize_modal = ResizeCanvasModal(self._edited_image.get_qimage())
        new_size, offset = resize_modal.showResizeModal();
        if new_size is None:
            return
        new_image = Image.new('RGB', (new_size.width(), new_size.height()), color = 'white')
        new_image.paste(self._edited_image.get_pil_image(), (offset.x(), offset.y()))
        self._edited_image.set_image(new_image)
        if offset.x() > 0 or offset.y() > 0:
            self._edited_image.set_selection_bounds(self._edited_image.get_selection_bounds().translated(offset))

    def scale_image(self):
        if not self._edited_image.has_image():
            show_error_dialog(self._window, "Unable to scale", "Load or create an image first before trying to scale.")
            return
        width = self._edited_image.width()
        height = self._edited_image.height()
        scale_modal = ImageScaleModal(width, height, self._config)
        newSize = scale_modal.show_image_modal()
        if newSize is not None:
            self._scale(newSize)

    def _scale(self, new_size): # Override to allow ML upscalers:
        width = self._edited_image.width()
        height = self._edited_image.height()
        if new_size is None or (new_size.width() == width and new_size.height() == height):
            return
        image = self._edited_image.get_pil_image()
        scale_mode = None
        if (new_size.width() <= width and new_size.height() <= height): #downscaling
            scale_mode = self._config.get('downscaleMode')
        else:
            scale_mode = self._config.get('upscaleMode')
        scaledImage = image.resize((new_size.width(), new_size.height()), scale_mode)
        self._edited_image.set_image(scaledImage)

    def _start_thread(self, threadWorker, loadingText=None):
        if self._thread is not None:
            raise Exception('Tried to start a new async operation while the previous one is still running')
        self._window.set_is_loading(True, loadingText)
        self._thread = QThread()
        self._worker = threadWorker
        self._worker.moveToThread(self._thread);
        def clear_worker():
            self._thread.quit()
            self._window.set_is_loading(False)
            self._worker.deleteLater()
            self._worker = None
        self._worker.finished.connect(clear_worker)
        self._thread.started.connect(self._worker.run)
        def clear_old_thread():
            self._thread.deleteLater()
            self._thread = None
        self._thread.finished.connect(clear_old_thread)
        self._thread.start()

    # Image generation handling:


    def _inpaint(self):
        raise Exception('BaseInpaintController should not be used directly, use a subclass.')

    def _apply_status_update(self, statusDict):
        return

    def start_and_manage_inpainting(self):
        if not self._edited_image.has_image():
            show_error_dialog(self._window, "Failed", "Load an image for editing before trying to start inpainting.")
            return
        if self._thread is not None:
            show_error_dialog(self._window, "Failed", "Existing inpainting operation not yet finished, wait a little longer.")
            return
        upscale_mode = self._config.get('upscaleMode')
        downscale_mode = self._config.get('downscaleMode')
        def resize_image(pilImage, width, height):
            """Resize a PIL image using the appropriate scaling mode:"""
            if width == pilImage.width and height == pilImage.height:
                return pilImage
            if width > pilImage.width or height > pilImage.height:
                return pilImage.resize((width, height), upscale_mode)
            return pilImage.resize((width, height), downscale_mode)

        selection = self._edited_image.get_selection_content()

        # If sketch mode was used, write the sketch onto the image selection:
        inpaint_image = selection.copy()
        inpaint_mask = self._mask_canvas.get_pil_image()
        sketch_image = self._sketch_canvas.get_pil_image()
        sketch_image = resize_image(sketch_image, inpaint_image.width, inpaint_image.height).convert('RGBA')
        if self._sketch_canvas._has_sketch: 
            inpaint_image = inpaint_image.convert('RGBA')
            inpaint_image = Image.alpha_composite(inpaint_image, sketch_image).convert('RGB')
        keep_sketch = self._sketch_canvas._has_sketch and self._config.get('saveSketchInResult')

        # If necessary, scale image and mask to match the edit size. Keep the unscaled version so it can be used for
        # compositing if "keep sketch" is checked.
        unscaled_inpaint_image = inpaint_image.copy()
        
        edit_size = self._config.get('editSize')
        if inpaint_image.width != edit_size.width() or inpaint_image.height != edit_size.height():
            inpaint_image = resize_image(inpaint_image, edit_size.width(), edit_size.height())
        if inpaint_mask.width != edit_size.width() or inpaint_mask.height != edit_size.height():
            inpaint_mask = resize_image(inpaint_mask, edit_size.width(), edit_size.height())

        do_inpaint = lambda img, mask, save, statusSignal: self._inpaint(img, mask, save, statusSignal)
        config = self._config
        class InpaintThreadWorker(QObject):
            finished = pyqtSignal()
            image_ready = pyqtSignal(Image.Image, int)
            status_signal = pyqtSignal(dict)
            error_signal = pyqtSignal(Exception)

            def __init__(self):
                super().__init__()

            def run(self):
                def send_image(img, idx):
                    self.image_ready.emit(img, idx)
                try:
                    do_inpaint(inpaint_image, inpaint_mask, send_image, self.status_signal)
                except Exception as err:
                    self.error_signal.emit(err)
                self.finished.emit()
        worker = InpaintThreadWorker()

        def handle_error(err):
            self._window.set_sample_selector_visible(False)
            show_error_dialog(self._window, "Inpainting failure", err)
        worker.error_signal.connect(handle_error)

        def update_status(status_dict):
            self._apply_status_update(status_dict)
        worker.status_signal.connect(update_status)

        def load_sample_preview(img, idx):
            if ((config.get('editMode') == 'Inpaint')) and (config.get('removeUnmaskedChanges') or img.width != selection.width or img.height != selection.height):
                point_fn = lambda p: 255 if p < 1 else 0
                if config.get('inpaintMasked') == 'Inpaint not masked':
                    point_fn = lambda p: 0 if p < 1 else 255
                mask_alpha = inpaint_mask.convert('L').point(point_fn).filter(ImageFilter.GaussianBlur())
                img = resize_image(img, selection.width, selection.height)
                mask_alpha = resize_image(mask_alpha, selection.width, selection.height)
                img = Image.composite(unscaled_inpaint_image if keep_sketch else selection, img, mask_alpha)
            self._window.load_sample_preview(img, idx)
        worker.image_ready.connect(load_sample_preview)
        self._window.set_sample_selector_visible(True)
        self._start_thread(worker)

    def select_and_apply_sample(self, sample_image):
        if self._config.get('saveSketchInResult'):
            source_selection = self._edited_image.get_selection_content()
            sketch_image = self._sketch_canvas.get_pil_image().resize((source_selection.width, source_selection.height),
                    self._config.get('downscaleMode')).convert('RGBA')
            source_selection = Image.alpha_composite(source_selection.convert('RGBA'), sketch_image).convert('RGB')
            self._edited_image.set_selection_content(source_selection)
            self._sketch_canvas.clear()
        if sample_image is not None and isinstance(sample_image, Image.Image):
            self._edited_image.set_selection_content(sample_image)
