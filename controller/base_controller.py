"""
BaseController coordinates primary application functionality across all operation modes. Each image generation and
editing method supported by IntraPaint should have its own BaseController subclass.
"""
import os
import sys
from PIL import Image, ImageFilter, UnidentifiedImageError
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from data_model.config import Config
from data_model.edited_image import EditedImage
from data_model.canvas.mask_canvas import MaskCanvas
from data_model.canvas.sketch_canvas import SketchCanvas

from ui.window.main_window import MainWindow
from ui.modal.new_image_modal import NewImageModal
from ui.modal.resize_canvas_modal import ResizeCanvasModal
from ui.modal.image_scale_modal import ImageScaleModal
from ui.modal.modal_utils import show_error_dialog, request_confirmation, open_image_file
from ui.util.screen_size import screen_size

from controller.spacenav_manager import SpacenavManager

# Optional spacenav support:
try:
    import spacenav
except ImportError as spacenav_err:
    print(f'spaceMouse support not enabled: {spacenav_err}')
    spacenav = None

class BaseInpaintController():
    """
    Shared base class for managing impainting. 

    At a bare minimum, subclasses will need to implement self._inpaint.
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
        self._config = Config()
        self._adjust_config_defaults()
        self._config.apply_args(args)

        self._edited_image = EditedImage(self._config, args.init_image)
        self._window = None
        self._nav_manager = None
        self._worker = None

        initial_selection_size = self._edited_image.get_selection_bounds().size()
        self._mask_canvas = MaskCanvas(self._config, initial_selection_size)

        if self._config.get('use_mypaint_canvas'):
            try:
                from data_model.canvas.brushlib_canvas import BrushlibCanvas
                self._sketch_canvas = BrushlibCanvas(self._config, initial_selection_size)
            except ImportError as err: # fallback to old implementation:
                print(f"Brushlib import failed: {err}")
                self._sketch_canvas = SketchCanvas(self._config, initial_selection_size)
        else:
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
        """ 
        Function to override initialize a SettingsModal with implementation-specific settings. 
        Return
        ------
        bool
            Whether settings were initialized. This will always be False unless overridden.
        """
        return False


    def refresh_settings(self, settings_modal):
        """
        Unimplemented function used to update a SettingsModal to reflect any changes.  This should only be called in
        a child class instance that previously returned true after init_settings was called.

        Parameters
        ----------
        settings_modal : SettingsModal
        """
        raise NotImplementedError('refresh_settings not implemented!')


    def update_settings(self, changed_settings):
        """
        Unimplemented function used to apply changed settings from a SettingsModal.  This should only be called in
        a child class instance that previously returned true after init_settings was called.

        Parameters
        ----------
        changed_settings : dict
            Set of changes loaded from a SettingsModal.
        """
        raise NotImplementedError('update_settings not implemented!')


    def window_init(self):
        """Initialize and show the main application window."""
        self._window = MainWindow(self._config, self._edited_image, self._mask_canvas, self._sketch_canvas, self)
        size = screen_size(self._window)
        self._window.setGeometry(0, 0, size.width(), size.height())
        self._window.setMaximumHeight(size.height())
        self._window.setMaximumWidth(size.width())
        self.fix_styles()
        self._window.show()


    def fix_styles(self):
        """Update application styling based on theme configuration, UI configuration, and available theme modules."""
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
                xml_file = theme[len('qt_material_'):]
                apply_stylesheet(self._app, theme=xml_file)
        except ModuleNotFoundError:
            print('Failed to load theme ' + self._config.get('style'))
        font = self._app.font()
        font.setPointSize(self._config.get('font_point_size'))
        self._app.setFont(font)


    def start_app(self):
        """Start the application after performing any additional required setup steps."""
        self.window_init()

        # Configure support for spacemouse panning, if relevant:
        self._nav_manager = SpacenavManager(self._window, self._edited_image)
        self._nav_manager.start_thread()

        self._app.exec_()
        sys.exit()


    # File IO handling:
    def new_image(self):
        """Open a new image creation modal."""
        default_size = self._config.get('edit_size')
        image_modal = NewImageModal(default_size.width(), default_size.height())
        image_size = image_modal.show_image_modal()
        if image_size and ((not self._edited_image.has_image()) or \
                request_confirmation(self._window, "Create new image?", "This will discard all unsaved changes.")):
            new_image = Image.new('RGB', (image_size.width(), image_size.height()), color = 'white')
            self._edited_image.set_image(new_image)


    def save_image(self):
        """Open a save dialog, and save the edited image to disk."""
        if not self._edited_image.has_image():
            show_error_dialog(self._window, "Save failed", "Open an image first before trying to save.")
            return
        file, file_selected = open_image_file(self._window, mode='save',
                selected_file = self._config.get("last_file_path"))
        try:
            if file and file_selected:
                self._edited_image.save_image(file)
                self._config.set("last_file_path", file)
        except Exception as err:
            show_error_dialog(self._window, "Save failed", str(err))
            print(f"Saving image failed: {err}")
            raise err


    def load_image(self):
        """Open a loading dialog, then load the selected image for editing."""
        file, file_selected = open_image_file(self._window)
        if file and file_selected:
            try:
                self._edited_image.set_image(file)
                self._config.set("last_file_path", file)
            except UnidentifiedImageError as err:
                show_error_dialog(self._window, "Open failed", err)


    def reload_image(self):
        """Reload the edited image from disk after getting confirmation from a confirmation dialog."""
        file_path = self._config.get("last_file_path")
        if file_path == "":
            show_error_dialog(self._window, "Reload failed", "Enter an image path or click 'Open Image' first.")
            return
        if not os.path.isfile(file_path):
            show_error_dialog(self._window, "Reload failed", f"Image path '{file_path}' is not a valid file.")
            return
        if (not self._edited_image.has_image()) or \
                request_confirmation(self._window, "Reload image?", "This will discard all unsaved changes."):
            self._edited_image.set_image(file_path)


    def resize_canvas(self):
        """Crop or extend the edited image without scaling its contents based on user input into a popup modal."""
        if not self._edited_image.has_image():
            show_error_dialog(self._window, "Unable to resize",
                    "Load or create an image first before trying to resize.")
            return
        resize_modal = ResizeCanvasModal(self._edited_image.get_qimage())
        new_size, offset = resize_modal.showResizeModal()
        if new_size is None:
            return
        new_image = Image.new('RGB', (new_size.width(), new_size.height()), color = 'white')
        new_image.paste(self._edited_image.get_pil_image(), (offset.x(), offset.y()))
        self._edited_image.set_image(new_image)
        if offset.x() > 0 or offset.y() > 0:
            self._edited_image.set_selection_bounds(self._edited_image.get_selection_bounds().translated(offset))


    def scale_image(self):
        """Scale the edited image based on user input into a popup modal."""
        if not self._edited_image.has_image():
            show_error_dialog(self._window, "Unable to scale", "Load or create an image first before trying to scale.")
            return
        width = self._edited_image.width()
        height = self._edited_image.height()
        scale_modal = ImageScaleModal(width, height, self._config)
        new_size = scale_modal.show_image_modal()
        if new_size is not None:
            self._scale(new_size)


    def _scale(self, new_size): # Override to allow alternate or external upscalers:
        width = self._edited_image.width()
        height = self._edited_image.height()
        if new_size is None or (new_size.width() == width and new_size.height() == height):
            return
        image = self._edited_image.get_pil_image()
        scale_mode = None
        if (new_size.width() <= width and new_size.height() <= height): #downscaling
            scale_mode = self._config.get('downscale_mode')
        else:
            scale_mode = self._config.get('upscale_mode')
        scaled_image = image.resize((new_size.width(), new_size.height()), scale_mode)
        self._edited_image.set_image(scaled_image)


    def _start_thread(self, thread_worker, loading_text=None):
        if self._thread is not None:
            raise RuntimeError('Tried to start a new async operation while the previous one is still running')
        self._window.set_is_loading(True, loading_text)
        self._thread = QThread()
        self._worker = thread_worker
        self._worker.moveToThread(self._thread)
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
    def _inpaint(self, selection, mask, save_image, status_signal):
        """
        Unimplemented method for handling image inpainting.

        Parameters
        ----------
        selection : PIL Image, optional
            Image selection to edit
        mask : PIL Image, optional
            Mask marking edited image region.
        save_image : function (PIL Image, int)
            Function used to return each image response and its index.
        status_signal : pyqtSignal
            Signal to emit when status updates are available.
        """
        raise NotImplementedError('_inpaint method not implemented.')


    def _apply_status_update(self, status_dict):
        """Optional unimplemented method for handling image editing status updates."""
        return


    def start_and_manage_inpainting(self):
        """Start inpainting/image editing based on the current state of the UI.
        """
        if not self._edited_image.has_image():
            show_error_dialog(self._window, "Failed", "Load an image for editing before trying to start inpainting.")
            return
        if self._thread is not None:
            show_error_dialog(self._window, "Failed",
                    "Existing inpainting operation not yet finished, wait a little longer.")
            return
        upscale_mode = self._config.get('upscale_mode')
        downscale_mode = self._config.get('downscale_mode')
        def resize_image(pil_image, width, height):
            """Resize a PIL image using the appropriate scaling mode:"""
            if width == pil_image.width and height == pil_image.height:
                return pil_image
            if width > pil_image.width or height > pil_image.height:
                return pil_image.resize((width, height), upscale_mode)
            return pil_image.resize((width, height), downscale_mode)

        selection = self._edited_image.get_selection_content()

        # If sketch mode was used, write the sketch onto the image selection:
        inpaint_image = selection.copy()
        inpaint_mask = self._mask_canvas.get_pil_image()
        sketch_image = self._sketch_canvas.get_pil_image()
        sketch_image = resize_image(sketch_image, inpaint_image.width, inpaint_image.height).convert('RGBA')
        if self._sketch_canvas.has_sketch():
            inpaint_image = inpaint_image.convert('RGBA')
            inpaint_image = Image.alpha_composite(inpaint_image, sketch_image).convert('RGB')
        keep_sketch = self._sketch_canvas.has_sketch()

        # If necessary, scale image and mask to match the edit size. Keep the unscaled version so it can be used for
        # compositing if "keep sketch" is checked.
        unscaled_inpaint_image = inpaint_image.copy()

        edit_size = self._config.get('edit_size')
        if inpaint_image.width != edit_size.width() or inpaint_image.height != edit_size.height():
            inpaint_image = resize_image(inpaint_image, edit_size.width(), edit_size.height())
        if inpaint_mask.width != edit_size.width() or inpaint_mask.height != edit_size.height():
            inpaint_mask = resize_image(inpaint_mask, edit_size.width(), edit_size.height())

        def do_inpaint(img, mask, save, status_signal):
            self._inpaint(img, mask, save, status_signal)
        config = self._config
        class InpaintThreadWorker(QObject):
            """Handles inpainting witin its own thread."""
            finished = pyqtSignal()
            image_ready = pyqtSignal(Image.Image, int)
            status_signal = pyqtSignal(dict)
            error_signal = pyqtSignal(Exception)

            def run(self):
                """Start the inpainting thread."""
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
            if ((config.get('edit_mode') == 'Inpaint')):
                def point_fn(p):
                    return 255 if p < 1 else 0
                mask_alpha = inpaint_mask.convert('L').point(point_fn).filter(ImageFilter.GaussianBlur())
                img = resize_image(img, selection.width, selection.height)
                mask_alpha = resize_image(mask_alpha, selection.width, selection.height)
                img = Image.composite(unscaled_inpaint_image if keep_sketch else selection, img, mask_alpha)
            self._window.load_sample_preview(img, idx)
        worker.image_ready.connect(load_sample_preview)
        self._window.set_sample_selector_visible(True)
        self._start_thread(worker)


    def select_and_apply_sample(self, sample_image):
        """Apply an AI-generated image change to the edited image.

        Parameters
        ----------
        sample_image : PIL Image
            Image data to be inserted into the EditedImage selection bounds.
        """
        source_selection = self._edited_image.get_selection_content()
        sketch_image = self._sketch_canvas.get_pil_image().resize((source_selection.width, source_selection.height),
                self._config.get('downscale_mode')).convert('RGBA')
        source_selection = Image.alpha_composite(source_selection.convert('RGBA'), sketch_image).convert('RGB')
        self._edited_image.set_selection_content(source_selection)
        self._sketch_canvas.clear()
        if sample_image is not None and isinstance(sample_image, Image.Image):
            self._edited_image.set_selection_content(sample_image)
