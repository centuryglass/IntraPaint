"""
Base implementation of the primary image editing window. On its own, provides an appropriate interface for GLID3-XL
inpainting modes.  Other editing modes should provide subclasses with implementation-specific controls.
"""
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPainter, QPen, QIcon, QPixmap
from PyQt5.QtCore import Qt, QObject, QThread, QRect, QPoint, QSize, pyqtSignal
import PyQt5.QtGui as QtGui
from PIL import Image, ImageFilter
import sys, os, glob, math

from ui.modal.modal_utils import show_error_dialog, request_confirmation
from ui.modal.settings_modal import SettingsModal
from ui.panel.mask_panel import MaskPanel
from ui.panel.image_panel import ImagePanel
from ui.sample_selector import SampleSelector
from ui.config_control_setup import *
from ui.widget.draggable_arrow import DraggableArrow
from ui.widget.loading_widget import LoadingWidget
from ui.util.contrast_color import contrast_color
from ui.util.screen_size import screen_size
from data_model.canvas.filled_canvas import FilledMaskCanvas

class MainWindow(QMainWindow):
    """Main user interface for inpainting."""

    def __init__(self, config, edited_image, mask, sketch, controller):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon('resources/icon.png'))

        # Initialize UI/editing data model:
        self._controller = controller
        self._config = config
        self._edited_image = edited_image
        self._mask = mask
        self._sketch = sketch
        self._dragging_divider = False
        self._timelapse_path = None
        self._sample_selector = None
        self._layout_mode = 'horizontal'
        self._sliders_enabled = True

        # Create components, build layout:
        self._layout = QVBoxLayout()
        self._main_page_widget = QWidget(self);
        self._main_page_widget.setLayout(self._layout)
        self._main_tab_widget = None
        self._main_widget = self._main_page_widget
        self._central_widget = QStackedWidget(self);
        self._central_widget.addWidget(self._main_widget)
        self.setCentralWidget(self._central_widget)
        self._central_widget.setCurrentWidget(self._main_widget)

        # Loading widget (for interrogate):
        self._is_loading = False
        self._loading_widget = LoadingWidget()
        self._loading_widget.setParent(self)
        self._loading_widget.setGeometry(self.frameGeometry())
        self._loading_widget.hide()

        # Image/Mask editing layout:
        self._image_panel = ImagePanel(self._config, self._edited_image, controller)
        self._mask_panel = MaskPanel(self._config, self._mask, self._sketch, self._edited_image)


        self.installEventFilter(self._mask_panel)
        self._divider = DraggableArrow()
        self._scale_handler = None
        self._image_layout = None
        self._setup_correct_layout()
        self._image_panel.image_toggled.connect(lambda s: self._on_image_panel_toggle(s))

        # Set up menu:
        self._menu = self.menuBar()

        def add_action(name, shortcut, on_trigger, menu):
            action = QAction(name, self)
            if shortcut is not None:
                action.setShortcut(shortcut)
            action.triggered.connect(on_trigger)
            menu.addAction(action)

        # File:
        file_menu = self._menu.addMenu("File")
        def if_not_selecting(fn):
            if not self.is_sample_selector_visible():
                fn()
        add_action("New Image", "Ctrl+N", lambda: if_not_selecting(lambda: controller.new_image()), file_menu)
        add_action("Save", "Ctrl+S", lambda: controller.save_image(), file_menu)
        add_action("Load", "Ctrl+O", lambda: if_not_selecting(lambda: controller.load_image()), file_menu)
        add_action("Reload", "F5", lambda: if_not_selecting(lambda: controller.reload_image()), file_menu)
        def try_quit():
            if (not self._edited_image.has_image()) or request_confirmation(self, "Quit now?",
                    "All unsaved changes will be lost."):
                self.close()
        add_action("Quit", "Ctrl+Q", try_quit, file_menu)

        # Edit:
        edit_menu = self._menu.addMenu("Edit")
        add_action("Undo", "Ctrl+Z", lambda: if_not_selecting(lambda: self._mask_panel.undo()), edit_menu)
        add_action("Redo", "Ctrl+Shift+Z", lambda: if_not_selecting(lambda: self._mask_panel.redo()), edit_menu)
        add_action("Generate", "F4", lambda: if_not_selecting(lambda: controller.start_and_manage_inpainting()),
                edit_menu)


        # Image:
        image_menu = self._menu.addMenu("Image")
        add_action("Resize canvas", "F2", lambda: if_not_selecting(lambda: controller.resize_canvas()), image_menu)
        add_action("Scale image", "F3", lambda: if_not_selecting(lambda: controller.scale_image()), image_menu)
        def update_metadata():
            self._edited_image.update_metadata()
            message_box = QMessageBox(self)
            message_box.setWindowTitle("Metadata updated")
            message_box.setText("On save, current image generation paremeters will be stored within the image")
            message_box.setStandardButtons(QMessageBox.Ok)
            message_box.exec()
        add_action("Update image metadata", None, update_metadata, image_menu)

        # Tools:
        tool_menu = self._menu.addMenu("Tools")
        def sketch_mode_toggle():
            try: 
                self._mask_panel.toggle_draw_mode()
            except Exception:
                pass # Other mode is disabled, just do nothing
        add_action("Toggle mask/sketch editing mode", "F6", lambda: if_not_selecting(sketch_mode_toggle), tool_menu)
        def mask_tool_toggle():
            self._mask_panel.swap_draw_tool()
        add_action("Toggle pen/eraser tool", "F7", lambda: if_not_selecting(mask_tool_toggle), tool_menu)
        def clear_both():
            mask.clear()
            sketch.clear()
            self._mask_panel.update()
        add_action("Clear mask and sketch", "F8", lambda: if_not_selecting(clear_both), tool_menu)
        def brush_size_change(offset):
            size = self._mask_panel.get_brush_size()
            self._mask_panel.set_brush_size(size + offset)
        add_action("Increase brush size", "Ctrl+]", lambda: if_not_selecting(lambda: brush_size_change(1)), tool_menu)
        add_action("Decrease brush size", "Ctrl+[", lambda: if_not_selecting(lambda: brush_size_change(-1)), tool_menu)

        if hasattr(self._mask_panel, '_open_brush_picker'):
            try:
                from data_model.canvas.brushlib import Brushlib
                from ui.widget.brush_picker import BrushPicker
                add_action("Open brush menu", None, lambda: self._mask_panel._open_brush_picker(), tool_menu)
                def load_brush():
                    isPyinstallerBundle = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
                    options = QFileDialog.Option.DontUseNativeDialog if isPyinstallerBundle else None
                    file, fileSelected = QFileDialog.getOpenFileName(self, 'Open Brush File', options)
                    if fileSelected:
                        Brushlib.load_brush(file)
                add_action("Load MyPaint Brush (.myb)", None, load_brush, tool_menu)
            except ImportError as err:
                print(f"Skipping brush selection init, brushlib loading failed: {err}")

        self._settings = SettingsModal(self)
        if (controller.init_settings(self._settings)):
            self._settings.changes_saved.connect(lambda changes: controller.update_settings(changes))
            def show_settings():
                controller.refresh_settings(self._settings)
                frame = self.frameGeometry()
                frame.setX(frame.x() + (frame.width() // 8))
                frame.setY(frame.y() + (frame.height() // 8))
                frame.setWidth(math.floor(self.width() * 0.75))
                frame.setHeight(math.floor(self.height() * 0.75))
                self._settings.setGeometry(frame)
                self._settings.show_modal()
            add_action("Settings", "F9", lambda: if_not_selecting(show_settings), tool_menu)

        # TODO: the following are specific to the A1111 stable-diffusion api and should move to 
        #       stable_diffusion_controller:
        if hasattr(controller, '_webservice') and 'LCM' in config.get_options('samplingMethod'):
            try:
                loras = [l['name'] for l in controller._webservice.get_loras()]
                if 'lcm-lora-sdv1-5' in loras:
                    def setLcmMode():
                        loraKey= '<lora:lcm-lora-sdv1-5:1>'
                        prompt = config.get("prompt")
                        if loraKey not in prompt:
                            config.set("prompt", f"{prompt} {loraKey}")
                        config.set('cfgScale', 1.5)
                        config.set('samplingSteps', 8)
                        config.set('samplingMethod', 'LCM')
                        config.set('seed', -1)
                        if config.get('batchSize') < 5:
                            config.set('batchSize', 5)
                        if self._edited_image.has_image():
                            imageSize = self._edited_image.size()
                            if imageSize.width() < 1200 and imageSize.height() < 1200:
                                config.set('editSize', imageSize)
                            else:
                                size = QSize(min(imageSize.width(), 1024), min(imageSize.height(), 1024))
                                config.set('editSize', size)
                    add_action("LCM Mode", "F10", setLcmMode, tool_menu)
            except:
                print('Failed to check loras for lcm lora')

        # Build config + control layout (varying based on implementation): 
        self._build_control_layout(controller)

    def should_use_wide_layout(self):
        return self.height() <= (self.width() * 1.2)

    def should_use_tabbed_layout(self):
        main_display_size = screen_size(self)
        required_height = 0

        # Calculate max heights, taking into account possible expanded panels:
        def get_required_height(item):
            height = 0
            if hasattr(item, 'expanded_size'):
                height = max(height, item.expanded_size().height())
            if hasattr(item, 'sizeHint'):
                height = max(height, item.sizeHint().height())
            inner_height = 0
            if item.layout() is not None and isinstance(item.layout(), QVBoxLayout):
                for inner_item in (item.layout().itemAt(i) for i in range(item.layout().count())):
                    inner_height += get_required_height(inner_item)
                height = max(height, inner_height)
            return height

        for item in (self.layout().itemAt(i) for i in range(self.layout().count())):
            required_height += get_required_height(item)
        if required_height == 0 and self._main_tab_widget is not None:
            for item in (self._main_tab_widget.widget(i) for i in range(self._main_tab_widget.count())):
                required_height += get_required_height(item)
        return required_height > (main_display_size.height() * 0.9)


    def _clear_editing_layout(self):
        if self._image_layout is not None:
            for widget in [self._image_panel, self._divider, self._mask_panel]:
                self._image_layout.removeWidget(widget)
            self.layout().removeItem(self._image_layout)
            self._image_layout = None
            if self._scale_handler is not None:
                self._divider.dragged.disconnect(self._scale_handler)
                self._scale_handler = None

    def set_image_sliders_enabled(self, slidersEnabled):
        self._sliders_enabled = slidersEnabled
        if not slidersEnabled and self._image_panel.sliders_showing():
            self._image_panel.show_sliders(False)
        elif slidersEnabled and not self._image_panel.sliders_showing() and self.should_use_wide_layout():
            self._image_panel.show_sliders(True)

    def _setup_wide_layout(self):
        if self._image_layout is not None:
            self._clear_editing_layout()
        image_layout = QHBoxLayout()
        self._divider.set_horizontal_mode()
        self._image_layout = image_layout
        def scaleWidgets(pos):
            x = pos.x()
            imgWeight = int(x / self.width() * 300)
            maskWeight = 300 - imgWeight
            self._image_layout.setStretch(0, imgWeight)
            self._image_layout.setStretch(2, maskWeight)
            self.update()
        self._scale_handler = scaleWidgets
        self._divider.dragged.connect(self._scale_handler)

        image_layout.addWidget(self._image_panel, stretch=255)
        image_layout.addWidget(self._divider, stretch=5)
        image_layout.addWidget(self._mask_panel, stretch=100)
        self._layout.insertLayout(0, image_layout, stretch=255)
        self._image_panel.show_sliders(True and self._sliders_enabled)
        self._image_panel.set_orientation(Qt.Orientation.Horizontal)
        self.update()

    def _setup_tall_layout(self):
        if self._image_layout is not None:
            self._clear_editing_layout()
        image_layout = QVBoxLayout()
        self._image_layout = image_layout
        self._divider.set_vertical_mode()
        def scale_widgets(pos):
            y = pos.y()
            img_weight = int(y / self.height() * 300)
            mask_wight = 300 - img_weight
            self._image_layout.setStretch(0, img_weight)
            self._image_layout.setStretch(2, mask_wight)
            self.update()
        self._scale_handler = scale_widgets
        self._divider.dragged.connect(self._scale_handler)

        image_layout.addWidget(self._image_panel, stretch=255)
        image_layout.addWidget(self._divider, stretch=5)
        image_layout.addWidget(self._mask_panel, stretch=100)
        self.layout().insertLayout(0, image_layout, stretch=255)
        self._image_layout = image_layout
        self._image_panel.show_sliders(False)
        self._image_panel.set_orientation(Qt.Orientation.Vertical)
        self.update()

    #def _setupTabbedLayout(self):



    def _setup_correct_layout(self):
        if self.should_use_wide_layout():
            if isinstance(self._image_layout, QVBoxLayout) or self._image_layout is None: 
                self._setup_wide_layout()
        elif isinstance(self._image_layout, QHBoxLayout) or self._image_layout is None:
                self._setup_tall_layout()

    def _create_scale_mode_selector(self, parent, config_key): 
        scale_mode_list = QComboBox(parent)
        filter_types = [
            ('Bilinear', Image.BILINEAR),
            ('Nearest', Image.NEAREST),
            ('Hamming', Image.HAMMING),
            ('Bicubic', Image.BICUBIC),
            ('Lanczos', Image.LANCZOS),
            ('Box', Image.BOX)
        ]
        for name, image_filter in filter_types:
            scale_mode_list.addItem(name, image_filter)
        scale_mode_list.setCurrentIndex(scale_mode_list.findData(self._config.get(config_key)))
        def set_scale_mode(modeIndex):
            mode = scale_mode_list.itemData(modeIndex)
            if mode:
                self._config.set(config_key, mode)
        scale_mode_list.currentIndexChanged.connect(set_scale_mode)
        return scale_mode_list


    def _build_control_layout(self, controller):
        inpaint_panel = QWidget(self)
        text_prompt_textbox = connected_textedit(inpaint_panel, self._config, 'prompt')
        negative_prompt_textbox = connected_textedit(inpaint_panel, self._config, 'negativePrompt')

        batch_size_spinbox = connected_spinbox(inpaint_panel, self._config, 'batchSize', max_key='maxBatchSize')
        batch_size_spinbox.setRange(1, batch_size_spinbox.maximum())
        batch_size_spinbox.setToolTip("Inpainting images generated per batch")

        batch_count_spinbox = connected_spinbox(inpaint_panel, self._config, 'batchCount', max_key='maxBatchCount')
        batch_count_spinbox.setRange(1, batch_count_spinbox.maximum())
        batch_count_spinbox.setToolTip("Number of inpainting image batches to generate")

        inpaint_button = QPushButton();
        inpaint_button.setText("Start inpainting")
        inpaint_button.clicked.connect(lambda: controller.start_and_manage_inpainting())

        more_options_bar = QHBoxLayout()
        guidance_scale_spinbox = connected_spinbox(inpaint_panel, self._config, 'guidanceScale',
                max_key='maxGuidanceScale', step_size_key='guidanceScaleStep')
        guidance_scale_spinbox.setValue(self._config.get('guidanceScale'))
        guidance_scale_spinbox.setRange(1.0, self._config.get('maxGuidanceScale'))
        guidance_scale_spinbox.setToolTip("Scales how strongly the prompt and negative are considered. Higher values "
                + "are usually more precise, but have less variation.")

        skip_steps_checkbox = connected_spinbox(inpaint_panel, self._config, 'skipSteps', max_key='maxSkipSteps')
        skip_steps_checkbox.setToolTip("Sets how many diffusion steps to skip. Higher values generate faster and "
                + "produce simpler images.")

        enable_scale_checkbox = connected_checkbox(inpaint_panel, self._config, 'inpaintFullRes')
        enable_scale_checkbox.setText("Scale edited areas")
        enable_scale_checkbox.setToolTip("Enabling scaling allows for larger sample areas and better results at small "
                + "scales, but increases the time required to generate images for small areas.")
        def update_scale():
            if self._edited_image.has_image():
                self._image_panel.reload_scale_bounds()
        enable_scale_checkbox.stateChanged.connect(update_scale)

        upscale_mode_label = QLabel(inpaint_panel)
        upscale_mode_label.setText("Upscaling mode:")
        upscale_mode_list = self._create_scale_mode_selector(inpaint_panel, 'upscaleMode')
        upscale_mode_list.setToolTip("Image scaling mode used when increasing image scale");
        downscale_mode_label = QLabel(inpaint_panel)
        downscale_mode_label.setText("Downscaling mode:")
        downscale_mode_list = self._create_scale_mode_selector(inpaint_panel, 'downscaleMode')
        downscale_mode_list.setToolTip("Image scaling mode used when decreasing image scale");
        
        more_options_bar.addWidget(QLabel(inpaint_panel, text="Guidance scale:"), stretch=0)
        more_options_bar.addWidget(guidance_scale_spinbox, stretch=20)
        more_options_bar.addWidget(QLabel(inpaint_panel, text="Skip timesteps:"), stretch=0)
        more_options_bar.addWidget(skip_steps_checkbox, stretch=20)
        more_options_bar.addWidget(enable_scale_checkbox, stretch=10)
        more_options_bar.addWidget(upscale_mode_label, stretch=0)
        more_options_bar.addWidget(upscale_mode_list, stretch=10)
        more_options_bar.addWidget(downscale_mode_label, stretch=0)
        more_options_bar.addWidget(downscale_mode_list, stretch=10)

        zoom_button = QPushButton(); 
        zoom_button.setText("Zoom")
        zoom_button.setToolTip("Save frame, zoom out 15%, set mask to new blank area")
        zoom_button.clicked.connect(lambda: controller.zoomOut())
        more_options_bar.addWidget(zoom_button, stretch=5)

        # Build layout with labels:
        layout = QGridLayout()
        layout.addWidget(QLabel(inpaint_panel, text="Prompt:"), 1, 1, 1, 1)
        layout.addWidget(text_prompt_textbox, 1, 2, 1, 1)
        layout.addWidget(QLabel(inpaint_panel, text="Negative:"), 2, 1, 1, 1)
        layout.addWidget(negative_prompt_textbox, 2, 2, 1, 1)
        layout.addWidget(QLabel(inpaint_panel, text="Batch size:"), 1, 3, 1, 1)
        layout.addWidget(batch_size_spinbox, 1, 4, 1, 1)
        layout.addWidget(QLabel(inpaint_panel, text="Batch count:"), 2, 3, 1, 1)
        layout.addWidget(batch_count_spinbox, 2, 4, 1, 1)
        layout.addWidget(inpaint_button, 2, 5, 1, 1)
        layout.setColumnStretch(2, 255) # Maximize prompt input

        layout.addLayout(more_options_bar, 3, 1, 1, 4)
        inpaint_panel.setLayout(layout)
        self.layout().addWidget(inpaint_panel, stretch=20)
        self.resizeEvent(None)

    def is_sample_selector_visible(self):
        return hasattr(self, '_sample_selector') and self._central_widget.currentWidget() == self._sample_selector

    def set_sample_selector_visible(self, visible):
        is_visible = self.is_sample_selector_visible()
        if (visible == is_visible):
            return
        if visible:
            mask = self._mask if (self._config.get('editMode') == 'Inpaint') else FilledMaskCanvas(self._config)
            self._sample_selector = SampleSelector(
                    self._config,
                    self._edited_image,
                    mask,
                    self._sketch,
                    lambda: self.set_sample_selector_visible(False),
                    lambda img: self._controller.select_and_apply_sample(img))
            self._central_widget.addWidget(self._sample_selector)
            self._central_widget.setCurrentWidget(self._sample_selector)
            self.installEventFilter(self._sample_selector)
        else:
            self.removeEventFilter(self._sample_selector)
            self._central_widget.setCurrentWidget(self._main_widget)
            self._central_widget.removeWidget(self._sample_selector)
            del self._sample_selector
            self._sample_selector = None

    def load_sample_preview(self, image, idx):
        if self._sample_selector is None:
            print(f"Tried to load sample {idx} after sampleSelector was closed")
        else:
            self._sample_selector.load_sample_image(image, idx)

    def layout(self):
        return self._layout

    def set_is_loading(self, is_loading, message=None):
        if self._sample_selector is not None:
            self._sample_selector.set_is_loading(is_loading, message)
        else:
            if is_loading:
                self._loading_widget.show()
                if message:
                    self._loading_widget.set_message(message)
                else:
                    self._loading_widget.set_message("Loading...")
            else:
                self._loading_widget.hide()
            self._is_loading = is_loading
            self.update()

    def set_loading_message(self, message):
        if self._sample_selector is not None:
            self._sample_selector.set_loading_message(message)

    def resizeEvent(self, event):
        self.should_use_tabbed_layout()
        self._setup_correct_layout()
        if hasattr(self, '_loading_widget'):
            loading_widget_size = int(self.height() / 8)
            loading_bounds = QRect(self.width() // 2 - loading_widget_size // 2, loading_widget_size * 3,
                    loading_widget_size, loading_widget_size)
            self._loading_widget.setGeometry(loading_bounds)

    def mousePressEvent(self, event):
        if not self._is_loading:
            super().mousePressEvent(event)

    def _on_image_panel_toggle(self, image_showing):
        if image_showing:
            self._image_layout.setStretch(0, 255)
            self._image_layout.setStretch(2, 100)
        else:
            self._image_layout.setStretch(0, 1)
            self._image_layout.setStretch(2, 255)
        self._divider.set_hidden(not image_showing)
        self.update()
