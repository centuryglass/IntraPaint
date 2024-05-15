"""Panel used to display the edited image and associated controls. """
from PyQt5.QtWidgets import QWidget, QSpinBox, QLabel, QVBoxLayout, QHBoxLayout, QSlider, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QPen

from ui.image_viewer import ImageViewer
from ui.config_control_setup import connected_textedit
from ui.util.contrast_color import contrast_color
from ui.widget.param_slider import ParamSlider
from ui.widget.collapsible_box import CollapsibleBox
from data_model.config import Config

class ImagePanel(QWidget):
    """Holds the image viewer, provides inputs for selecting an editing area and saving/loading images."""


    image_toggled = pyqtSignal(bool)


    def __init__(self, config, edited_image):
        """Initializes the panel layout.

        Parameters
        ----------
        config : data_model.config.Config
            Shared application configuration object.
        edited_image : data_model.edited_image.EditedImage
            Image being edited
        """
        super().__init__()

        edited_image.size_changed.connect(lambda newSize: self.reload_scale_bounds())
        self._edited_image = edited_image
        self._config = config
        self._show_sliders = None
        self._slider_count = 0
        self._minimized = False
        self._border_size = 4
        self._image_box_layout = None

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._image_box = CollapsibleBox('Full Image',
                parent=self,
                scrolling=False,
                orientation=Qt.Orientation.Horizontal)
        self._image_box.toggled().connect(self.image_toggled.emit)
        self._image_box.set_expanded_size_policy(QSizePolicy.Ignored)

        self._image_viewer = ImageViewer(edited_image)

        self._controlbar = QWidget()
        controlbar_layout = QHBoxLayout(self._controlbar)
        controlbar_layout.addWidget(QLabel(self, text='Image Path:'))
        self._file_text_box = connected_textedit(self, config, Config.LAST_FILE_PATH)
        controlbar_layout.addWidget(self._file_text_box, stretch=255)

        # wire x/y coordinate boxes to set selection coordinates:
        controlbar_layout.addWidget(QLabel(self, text='X:'))
        self._x_coord_box = QSpinBox(self)
        controlbar_layout.addWidget(self._x_coord_box)
        self._x_coord_box.setRange(0, 0)
        self._x_coord_box.setToolTip('Selected X coordinate')
        def set_x(value):
            if edited_image.has_image():
                last_selected = edited_image.get_selection_bounds()
                last_selected.moveLeft(min(value, edited_image.width() - last_selected.width()))
                edited_image.set_selection_bounds(last_selected)
        self._x_coord_box.valueChanged.connect(set_x)

        controlbar_layout.addWidget(QLabel(self, text='Y:'))
        self._y_coord_box = QSpinBox(self)
        controlbar_layout.addWidget(self._y_coord_box)
        self._y_coord_box.setRange(0, 0)
        self._y_coord_box.setToolTip('Selected Y coordinate')
        def set_y(value):
            if edited_image.has_image():
                last_selected = edited_image.get_selection_bounds()
                last_selected.moveTop(min(value, edited_image.height() - last_selected.height()))
                edited_image.set_selection_bounds(last_selected)
        self._y_coord_box.valueChanged.connect(set_y)

        # Selection size controls:
        controlbar_layout.addWidget(QLabel(self, text='W:'))
        self._widthbox = QSpinBox(self)
        controlbar_layout.addWidget(self._widthbox)

        controlbar_layout.addWidget(QLabel(self, text='H:'))
        self._heightbox = QSpinBox(self)
        controlbar_layout.addWidget(self._heightbox)

        edit_size = config.get(Config.EDIT_SIZE)
        min_edit_size = config.get(Config.MIN_EDIT_SIZE)
        max_edit_size = config.get(Config.MAX_EDIT_SIZE)
        for size_control, type_name, min_size, max_size, size in [
                (self._widthbox, 'width', min_edit_size.width(), max_edit_size.width(), edit_size.width()),
                (self._heightbox, 'height', min_edit_size.height(), max_edit_size.height(), edit_size.height())]:
            size_control.setToolTip(f'Selected area {type_name}')
            size_control.setRange(min_size, max_size)
            size_control.setSingleStep(min_size)
            size_control.setValue(size)

        def set_w():
            value = self._widthbox.value()
            if edited_image.has_image():
                selection = edited_image.get_selection_bounds()
                selection.setWidth(value)
                edited_image.set_selection_bounds(selection)
        self._widthbox.editingFinished.connect(set_w)

        def set_h():
            value = self._heightbox.value()
            if edited_image.has_image():
                selection = edited_image.get_selection_bounds()
                selection.setHeight(value)
                edited_image.set_selection_bounds(selection)
        self._heightbox.editingFinished.connect(set_h)

        # Update coordinate controls automatically when the selection changes:
        def set_coords(bounds):
            self._x_coord_box.setValue(bounds.left())
            self._y_coord_box.setValue(bounds.top())
            self._widthbox.setValue(bounds.width())
            self._heightbox.setValue(bounds.height())
            if edited_image.has_image():
                self._x_coord_box.setMaximum(edited_image.width() - bounds.width())
                self._y_coord_box.setMaximum(edited_image.height() - bounds.height())
        edited_image.selection_changed.connect(set_coords)
        self.setLayout(self._layout)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self._init_image_box_layout()
        self.show_sliders(False)


    def set_orientation(self, orientation):
        """Sets the panel to a vertical or horizontal Qt.Orientation."""
        prev_image_box = self._image_box
        if self._image_box is not None:
            self._layout.removeWidget(self._image_box)
        self._image_box = CollapsibleBox('Full Image',
                parent=self,
                scrolling=False,
                orientation=orientation)
        self._init_image_box_layout()
        self._image_box.toggled().connect(self.image_toggled.emit)
        self._layout.insertWidget(self._slider_count, self._image_box)
        if prev_image_box is not None:
            prev_image_box.setParent(None)
            prev_image_box = None


    def add_slider(self, slider):
        """Adds a QSlider or ParamSlider control widget to the panel."""
        assert isinstance(slider, (ParamSlider, QSlider))
        self._layout.insertWidget(self._slider_count, slider, stretch=1)
        self._slider_count += 1
        self.show_sliders(self._show_sliders)


    def sliders_showing(self):
        """Returns whether sliders added with add_slider are visible."""
        return self._show_sliders


    def show_sliders(self, show_sliders):
        """Shows or hides all sliders added with add_slider."""
        self._show_sliders = show_sliders
        if show_sliders:
            for i in range(self._slider_count):
                self._layout.setStretch(i, 1)
            for slider in (self._layout.itemAt(i).widget() for i in range(self._slider_count)):
                slider.setVisible(True)
                slider.setEnabled(True)
                slider.setMaximumWidth(slider.sizeHint().width())
        else:
            for i in range(self._slider_count):
                self._layout.setStretch(i, 0)
            for slider in (self._layout.itemAt(i).widget() for i in range(self._slider_count)):
                slider.setEnabled(False)
                slider.setVisible(False)
                slider.setMaximumWidth(0)
        self._image_box.show_button_bar(True)


    def reload_scale_bounds(self):
        """Recalculate image scaling bounds based on image size and edit size limits."""
        max_edit_size = self._edited_image.get_max_selection_size()
        if not self._edited_image.has_image():
            self._widthbox.setMaximum(max_edit_size.width())
            self._heightbox.setMaximum(max_edit_size.height())
        else:
            image_size = self._edited_image.size()
            for spinbox, max_edit_dim in [
                    (self._widthbox, max_edit_size.width()),
                    (self._heightbox, max_edit_size.height())]:
                spinbox.setMaximum(max_edit_dim)
            selection_size = self._edited_image.get_selection_bounds().size()
            self._x_coord_box.setMaximum(image_size.width() - selection_size.width())
            self._y_coord_box.setMaximum(image_size.height() - selection_size.height())


    def paintEvent(self, unused_event):
        """Draws a border around the panel."""
        painter = QPainter(self)
        painter.setPen(QPen(contrast_color(self), self._border_size/2, Qt.SolidLine,
                    Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)


    def _init_image_box_layout(self):
        self._image_box_layout = QVBoxLayout()
        self._image_box_layout.addWidget(self._image_viewer, stretch=255)
        self._image_box_layout.addWidget(self._controlbar)
        self._image_box.set_content_layout(self._image_box_layout)
        self._layout.addWidget(self._image_box, stretch=255)
        self._image_box.set_content_layout(self._image_box_layout)
