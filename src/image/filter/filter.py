"""Generic interface for image filtering functions. Handles the process of opening modal windows to apply the filter
and provides the information needed to add the function as a menu action."""
from typing import Callable, List, Optional, Dict, Any

from PyQt5.QtCore import QRect, QPoint, Qt, QSize
from PyQt5.QtGui import QImage, QPainter

from src.image.layer_stack import LayerStack
from src.ui.modal.image_filter_modal import ImageFilterModal
from src.undo_stack import commit_action
from src.util.image_utils import get_transparency_tile_pixmap
from src.util.parameter import Parameter

MAX_PREVIEW_SIZE = 800


class ImageFilter:
    """Interface for image filtering functions exposed through a modal UI."""

    def __init__(self, layer_stack: LayerStack) -> None:
        self._layer_stack = layer_stack

    def get_filter_modal(self) -> ImageFilterModal:
        """Creates and returns a modal widget that can apply the filter to the edited image."""
        return ImageFilterModal(self.get_modal_title(),
                                self.get_modal_description(),
                                self.get_parameters(),
                                self.get_preview_image,
                                self.apply_filter,
                                self._layer_stack.selection_layer.empty is False)

    def get_modal_title(self) -> str:
        """Return the modal's title string."""
        raise NotImplementedError()

    def get_modal_description(self) -> str:
        """Returns the modal's description string."""
        raise NotImplementedError()

    def get_config_key(self) -> str:
        """Returns the KeyConfig key used to load menu item info and keybindings."""
        raise NotImplementedError()

    def get_filter(self) -> Callable[[...], QImage]:
        """Returns the filter's image variable filtering function."""
        raise NotImplementedError()

    def get_parameters(self) -> List[Parameter]:
        """Returns definitions for the non-image parameters passed to the filtering function."""
        return []

    def get_preview_image(self,
                          filter_param_values: List[Any],
                          filter_selection_only: bool,
                          filter_active_layer_only: bool) -> QImage:
        """
        Generate a preview of how the filter will be applied given a of parameters.
        Parameters
        ----------
            filter_param_values: list
                Parameter values to use, fitting the definitions the filter provides through get_parameters.
            filter_selection_only: bool
                If true, filters will only be applied to selected image content, and the preview will be cropped to
                the changed area.
            filter_active_layer_only: bool
                If true, filters will only be applied to the active layer, and the preview will be cropped to the active
                layer bounds.
        Returns
        -------
            QImage:
                The new preview image, possibly downscaled to avoid excess image processing.
        """
        scale = MAX_PREVIEW_SIZE / self._layer_stack.width
        layer_images = self._get_layer_images(filter_param_values, filter_selection_only, filter_active_layer_only,
                                              False, scale)
        bounds = self._bounds(scale)
        preview_image = QImage(bounds.size(), QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(preview_image)
        transparency_pattern = get_transparency_tile_pixmap()
        painter.drawTiledPixmap(0, 0, preview_image.width(), preview_image.height(), transparency_pattern)
        for i in reversed(range(self._layer_stack.count)):
            layer = self._layer_stack.get_layer_by_index(i)
            if not layer.visible:
                continue
            assert layer.id in layer_images
            position = QPoint(int(layer.position.x() * scale), int(layer.position.y() * scale))
            offset = position - bounds.topLeft()
            painter.setOpacity(layer.opacity)
            painter.setCompositionMode(layer.composition_mode)
            painter.drawImage(QRect(offset, layer_images[layer.id].size()), layer_images[layer.id])
        painter.end()

        crop_area = bounds.translated(-bounds.topLeft())

        def _map_to_preview(rect: QRect) -> None:
            rect.moveLeft(int(rect.x() * scale) - bounds.x())
            rect.moveTop(int(rect.y() * scale) - bounds.y())
            rect.setWidth(int(rect.width() * scale))
            rect.setHeight(int(rect.height() * scale))

        if filter_active_layer_only:
            active_layer = self._layer_stack.active_layer
            assert active_layer is not None
            layer_bounds = active_layer.geometry
            _map_to_preview(layer_bounds)
            crop_area = crop_area.intersected(layer_bounds)
        if filter_selection_only:
            selection_layer = self._layer_stack.selection_layer
            selection_bounds = selection_layer.get_content_bounds()
            if not selection_bounds.isEmpty():
                padding = max(selection_bounds.width(), selection_bounds.height()) // 10
                selection_bounds.adjust(-padding, -padding, padding, padding)
            _map_to_preview(selection_bounds)
            crop_area = crop_area.intersected(selection_bounds)

        if crop_area is not None and not crop_area.isEmpty() and crop_area.size() != bounds.size():
            preview_image = preview_image.copy(crop_area)
        return preview_image

    def apply_filter(self, filter_param_values: List[Any], filter_selection_only: bool,
                     filter_active_layer_only: bool) -> None:
        """
        Applies the filter to the layer stack.

        Parameters
        ----------
            filter_param_values: list
                Parameter values to use, fitting the definitions the filter provides through get_parameters.
            filter_selection_only: bool
                If true, filters will only be applied to selected image content.
            filter_active_layer_only: bool
                If true, filters will only be applied to the active layer instead of all visible layers.
        """
        layer_images = self._get_layer_images(filter_param_values, filter_selection_only, filter_active_layer_only,
                                              True)
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

    def _get_filtered_image(self,
                            image: QImage,
                            filter_param_values: List[Any],
                            selection: Optional[QImage],
                            selection_offset: QPoint) -> QImage:
        arg_list = [image]
        for arg in filter_param_values:
            arg_list.append(arg)
        filtered_image = self.get_filter()(*arg_list)
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

    def _bounds(self, scale = 1.0) -> QRect:
        bounds = self._layer_stack.merged_layer_geometry
        if scale != 1.0:
            bounds.setX(int(bounds.x() * scale))
            bounds.setY(int(bounds.y() * scale))
            bounds.setWidth(int(bounds.width() * scale))
            bounds.setHeight(int(bounds.height() * scale))
        return bounds

    def _get_layer_images(self,
                          filter_param_values: List[Any],
                          filter_selection_only: bool,
                          filter_active_layer_only: bool,
                          return_changed_layers_only: bool,
                          scale: float = 1.0) -> Dict[int, QImage]:
        images: Dict[int, QImage] = {}
        bounds = self._bounds(scale)
        if filter_selection_only:
            selection_layer = self._layer_stack.selection_layer
            selection: Optional[QImage] = QImage(bounds.size(), QImage.Format_ARGB32_Premultiplied)
            selection.fill(Qt.GlobalColor.transparent)
            painter = QPainter(selection)
            scaled_image_size = QSize(int(selection_layer.width * scale), int(selection_layer.height * scale))
            painter.drawPixmap(QRect(-bounds.topLeft(), bounds.size()), selection_layer.pixmap,
                               QRect(QPoint(), scaled_image_size))
            painter.end()
        else:
            selection = None
        for i in reversed(range(self._layer_stack.count)):
            layer = self._layer_stack.get_layer_by_index(i)
            if not layer.visible:
                continue
            position = QPoint(int(layer.position.x() * scale), int(layer.position.y() * scale))
            offset = position - bounds.topLeft()
            layer_image = layer.qimage
            if scale != 1.0:
                layer_image = layer_image.scaled(QSize(int(layer_image.width() * scale),
                                                       int(layer_image.height() * scale)))
            if not filter_active_layer_only or layer.id == self._layer_stack.active_layer_id:
                images[layer.id] = self._get_filtered_image(layer_image, filter_param_values, selection, offset)
            elif not return_changed_layers_only:
                images[layer.id] = layer_image
        return images
