"""
Panel used to display the edited image and associated controls.
"""
from PyQt5.QtWidgets import (QWidget, QSpinBox, QLineEdit, QPushButton, QLabel, QGridLayout, QSpacerItem,
        QFileDialog, QMessageBox, QVBoxLayout, QHBoxLayout, QSlider, QSizePolicy)
from PyQt5.QtCore import Qt, QPoint, QSize, QRect, QBuffer, pyqtSignal
from PyQt5.QtGui import QPainter, QPen
from PIL import Image
import os, sys

from ui.image_viewer import ImageViewer
from ui.config_control_setup import connected_textedit
from ui.util.contrast_color import contrast_color
from ui.widget.param_slider import ParamSlider
from ui.widget.collapsible_box import CollapsibleBox
from ui.widget.dual_toggle import DualToggle

class ImagePanel(QWidget):
    """
    Holds the image viewer, provides inputs for selecting an editing area and saving/loading images.
    """
    image_toggled = pyqtSignal(bool)


    def __init__(self, config, edited_image, controller):
        super().__init__()

        edited_image.size_changed.connect(lambda newSize: self.reload_scale_bounds())
        self._edited_image = edited_image
        self._config = config
        self._show_sliders = None
        self._slider_count = 0
        self._minimized = False
        self._border_size = 4

        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._image_box = CollapsibleBox("Full Image",
                parent=self,
                scrolling=False,
                orientation=Qt.Orientation.Horizontal)
        self._image_box.toggled().connect(lambda t: self.image_toggled.emit(t))
        self._image_box.set_expanded_size_policy(QSizePolicy.Ignored)
        self._image_box_layout = QVBoxLayout()
        self._image_box.set_content_layout(self._image_box_layout)
        self._layout.addWidget(self._image_box, stretch=255)


        self._image_viewer = ImageViewer(edited_image)
        self._image_box_layout.addWidget(self._image_viewer, stretch=255)

        controlbar_layout = QHBoxLayout()
        self._image_box_layout.addLayout(controlbar_layout)

        controlbar_layout.addWidget(QLabel(self, text="Image Path:"))
        self._file_text_box = connected_textedit(self, config, "last_file_path") 
        controlbar_layout.addWidget(self._file_text_box, stretch=255)

        # wire x/y coordinate boxes to set selection coordinates:
        controlbar_layout.addWidget(QLabel(self, text="X:"))
        self._x_coord_box = QSpinBox(self)
        controlbar_layout.addWidget(self._x_coord_box)
        self._x_coord_box.setRange(0, 0)
        self._x_coord_box.setToolTip("Selected X coordinate")
        def set_x(value):
            if edited_image.has_image():
                last_selected = edited_image.get_selection_bounds()
                last_selected.moveLeft(min(value, edited_image.width() - last_selected.width()))
                edited_image.set_selection_bounds(last_selected)
        self._x_coord_box.valueChanged.connect(set_x)

        controlbar_layout.addWidget(QLabel(self, text="Y:"))
        self._y_coord_box = QSpinBox(self)
        controlbar_layout.addWidget(self._y_coord_box)
        self._y_coord_box.setRange(0, 0)
        self._y_coord_box.setToolTip("Selected Y coordinate")
        def set_y(value):
            if edited_image.has_image():
                last_selected = edited_image.get_selection_bounds()
                last_selected.moveTop(min(value, edited_image.height() - last_selected.height()))
                edited_image.set_selection_bounds(last_selected)
        self._y_coord_box.valueChanged.connect(set_y)

        # Selection size controls:
        controlbar_layout.addWidget(QLabel(self, text="W:"))
        self._widthbox = QSpinBox(self)
        controlbar_layout.addWidget(self._widthbox)

        controlbar_layout.addWidget(QLabel(self, text="H:"))
        self._heightbox = QSpinBox(self)
        controlbar_layout.addWidget(self._heightbox)

        edit_size = config.get('edit_size')
        min_edit_size = config.get('min_edit_size')
        max_edit_size = config.get('max_edit_size')
        for size_control, type_name, min_size, max_size, size in [
                (self._widthbox, "width", min_edit_size.width(), max_edit_size.width(), edit_size.width()),
                (self._heightbox, "height", min_edit_size.height(), max_edit_size.height(), edit_size.height())]:
            size_control.setToolTip(f"Selected area {type_name}")
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
        self.show_sliders(False)

    def set_orientation(self, orientation):
        if self._image_box is not None:
            self._layout.removeWidget(self._image_box)
            self._image_box.setParent(None)
            self._image_box = None
        self._image_box = CollapsibleBox("Full Image",
                parent=self,
                scrolling=False,
                orientation=orientation)
        self._image_box.toggled().connect(lambda t: self.image_toggled.emit(t))
        self._image_box.set_content_layout(self._image_box_layout)
        self._layout.insertWidget(self._slider_count, self._image_box)

    def add_slider(self, slider):
        assert(isinstance(slider, ParamSlider) or isinstance(slider, QSlider))
        self._layout.insertWidget(self._slider_count, slider, stretch=1)
        self._slider_count += 1
        self.show_sliders(self._show_sliders)

    def sliders_showing(self):
        return self._show_sliders

    def show_sliders(self, show_sliders):
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
        max_edit_size = self._edited_image.get_max_selection_size()
        if not self._edited_image.has_image():
            self._widthbox.setMaximum(max_edit_size.width())
            self._heightbox.setMaximum(max_edit_size.height())
        else:
            image_size = self._edited_image.size()
            for spinbox, dim, max_edit_dim in [
                    (self._widthbox, image_size.width(), max_edit_size.width()),
                    (self._heightbox, image_size.height(), max_edit_size.height())]:
                spinbox.setMaximum(max_edit_dim)
            selection_size = self._edited_image.get_selection_bounds().size()
            self._x_coord_box.setMaximum(image_size.width() - selection_size.width())
            self._y_coord_box.setMaximum(image_size.height() - selection_size.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(contrast_color(self), self._border_size/2, Qt.SolidLine,
                    Qt.RoundCap, Qt.RoundJoin))
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
