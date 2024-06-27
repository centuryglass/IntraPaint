"""Popup modal window that applies an arbitrary image filtering action."""
from typing import List, Callable, Optional, Dict

from PyQt5.QtCore import QPoint, QRect, QSize, Qt
from PyQt5.QtGui import QPainter, QImage
from PyQt5.QtWidgets import QDialog, QFormLayout, QLabel, QWidget, QCheckBox, QHBoxLayout, QPushButton

from src.image.layer_stack import LayerStack
from src.ui.widget.image_widget import ImageWidget
from src.undo_stack import commit_action
from src.util.image_utils import get_transparency_tile_pixmap
from src.util.parameter import Parameter

SELECTED_ONLY_LABEL = 'Change selected areas only'
ACTIVE_ONLY_LABEL = 'Change active layer only'
MIN_PREVIEW_SIZE = 450
CANCEL_BUTTON_TEXT = 'Cancel'
APPLY_BUTTON_TEXT = 'Apply'


class ImageFilterModal(QDialog):
    """Popup modal window that applies an arbitrary image filtering action."""

    def __init__(self, title: str, description: str, parameters: List[Parameter],
                 filter_action: Callable[[...], QImage], layer_stack: LayerStack) -> None:
        super().__init__()
        self.setModal(True)
        self._filter = filter_action
        self._layer_stack = layer_stack
        self._preview = ImageWidget(layer_stack.pixmap(), self)
        self._preview.setMinimumSize(QSize(MIN_PREVIEW_SIZE, MIN_PREVIEW_SIZE))
        self._layout = QFormLayout(self)
        self._params = parameters
        self._param_inputs: List[QWidget] = []

        self.setWindowTitle(title)
        self._layout.addWidget(QLabel(description))
        for param in parameters:
            field_widget = param.get_input_widget()
            self._param_inputs.append(field_widget)
            self._layout.addRow(param.name, field_widget)
            field_widget.valueChanged.connect(self._update_preview)

        self._selected_only_checkbox = QCheckBox()
        self._layout.addRow(self._selected_only_checkbox)
        self._selected_only_checkbox.setText(SELECTED_ONLY_LABEL)
        self._selected_only_checkbox.setChecked(layer_stack.selection_layer.empty is False)
        self._selected_only_checkbox.stateChanged.connect(self._update_preview)

        self._active_only_checkbox = QCheckBox()
        self._layout.addRow(self._active_only_checkbox)
        self._active_only_checkbox.setText(ACTIVE_ONLY_LABEL)
        self._active_only_checkbox.setChecked(True)
        self._active_only_checkbox.stateChanged.connect(self._update_preview)

        self._layout.addRow(self._preview)
        self._button_row = QWidget()
        button_layout = QHBoxLayout(self._button_row)
        self._cancel_button = QPushButton()
        self._cancel_button.setText(CANCEL_BUTTON_TEXT)
        self._cancel_button.clicked.connect(self.close)
        button_layout.addWidget(self._cancel_button)
        self._apply_button = QPushButton()
        self._apply_button.setText(APPLY_BUTTON_TEXT)
        self._apply_button.clicked.connect(self._apply_change)
        button_layout.addWidget(self._apply_button)
        self._layout.addWidget(self._button_row)
        self._update_preview()

    def _get_filtered_image(self, image: QImage, selection: Optional[QImage], selection_offset: QPoint) -> QImage:
        arg_list = [image]
        for input_widget in self._param_inputs:
            arg_list.append(input_widget.value())
        filtered_image = self._filter(*arg_list)
        if selection is None:
            return filtered_image
        painter = QPainter(filtered_image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(QRect(QPoint(), image.size()), selection, QRect(selection_offset, image.size()))
        painter.end()
        final_image = image.copy()
        painter = QPainter(final_image)
        painter.drawImage(QRect(0, 0, image.width(), image.height()), filtered_image)
        return final_image

    def _get_layer_images(self, changed_only: bool) -> Dict[int, QImage]:
        images: Dict[int, QImage] = {}
        bounds = self._layer_stack.merged_layer_geometry
        if self._selected_only_checkbox.isChecked():
            selection_layer = self._layer_stack.selection_layer
            selection: Optional[QImage] = QImage(bounds.size(), QImage.Format_ARGB32_Premultiplied)
            selection.fill(Qt.GlobalColor.transparent)
            painter = QPainter(selection)
            painter.drawPixmap(QRect(-bounds.topLeft(), selection_layer.size), selection_layer.pixmap)
            painter.end()
        else:
            selection = None
        for i in reversed(range(self._layer_stack.count)):
            layer = self._layer_stack.get_layer_by_index(i)
            if not layer.visible:
                continue
            offset = layer.position - bounds.topLeft()
            if not self._active_only_checkbox.isChecked() or layer.id == self._layer_stack.active_layer_id:
                images[layer.id] = self._get_filtered_image(layer.qimage, selection, offset)
            elif not changed_only:
                images[layer.id] = layer.qimage
        return images

    def _update_preview(self, _ = None) -> None:
        layer_images = self._get_layer_images(False)
        bounds = self._layer_stack.merged_layer_geometry
        preview_image = QImage(bounds.size(), QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(preview_image)
        transparency_pattern = get_transparency_tile_pixmap()
        painter.drawTiledPixmap(0, 0, preview_image.width(), preview_image.height(), transparency_pattern)
        for i in reversed(range(self._layer_stack.count)):
            layer = self._layer_stack.get_layer_by_index(i)
            if not layer.visible:
                continue
            assert layer.id in layer_images
            offset = layer.position - bounds.topLeft()
            painter.setOpacity(layer.opacity)
            painter.setCompositionMode(layer.composition_mode)
            painter.drawImage(QRect(offset, layer.size), layer_images[layer.id])
        painter.end()
        self._preview.image = preview_image

    def _apply_change(self) -> None:
        """Apply the filter to the active layer or layer stack, then close the modal."""
        layer_images = self._get_layer_images(True)
        source_images: Dict[int, QImage] = {}
        for layer_id in layer_images.keys():
            layer = self._layer_stack.get_layer_by_id(layer_id)
            source_images[layer_id] = layer.qimage

        def _apply_filters(img_dict=layer_images):
            for updated_id, image in img_dict.items():
                updated_layer = self._layer_stack.get_layer_by_id(updated_id)
                updated_layer.qimage = image

        def _undo_filters(img_dict=source_images):
            for updated_id, image in img_dict.items():
                updated_layer = self._layer_stack.get_layer_by_id(updated_id)
                updated_layer.qimage = image

        commit_action(_apply_filters, _undo_filters)
        self.close()


