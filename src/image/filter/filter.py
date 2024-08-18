"""Generic interface for image filtering functions. Handles the process of opening modal windows to apply the filter
and provides the information needed to add the function as a menu action."""
from typing import Callable, List, Optional, Dict, Any

from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPainter, QTransform

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_stack import LayerStack
from src.image.layers.transform_layer import TransformLayer
from src.ui.modal.image_filter_modal import ImageFilterModal
from src.undo_stack import UndoStack
from src.util.application_state import APP_STATE_EDITING, AppStateTracker
from src.util.async_task import AsyncTask
from src.util.geometry_utils import adjusted_placement_in_bounds
from src.util.image_utils import get_transparency_tile_pixmap, image_content_bounds
from src.util.parameter import Parameter

MAX_PREVIEW_SIZE = 800
MIN_PREVIEW_SIZE = 200


class ImageFilter:
    """Interface for image filtering functions exposed through a modal UI."""

    def __init__(self, image_stack: ImageStack) -> None:
        self._image_stack = image_stack
        self._filter_selection_only = True
        self._filter_active_layer_only = True

    @property
    def selection_only(self) -> bool:
        """Controls whether the filter will only be applied to selected areas."""
        return self._filter_selection_only

    @selection_only.setter
    def selection_only(self, use_selection_only: bool) -> None:
        self._filter_selection_only = use_selection_only

    @property
    def active_layer_only(self) -> bool:
        """Controls whether the filter will only be applied to the active layer, or to all visible layers."""
        return self._filter_active_layer_only

    @active_layer_only.setter
    def active_layer_only(self, use_active_only: bool) -> None:
        self._filter_active_layer_only = use_active_only

    def is_local(self) -> bool:
        """Indicates whether the filter operates independently on each pixel (True) or takes neighboring pixels
        into account (False)."""
        return True

    def get_filter_modal(self) -> ImageFilterModal:
        """Creates and returns a modal widget that can apply the filter to the edited image."""
        self.selection_only = not self._image_stack.selection_layer.empty
        modal = ImageFilterModal(self.get_modal_title(),
                                 self.get_modal_description(),
                                 self.get_parameters(),
                                 self.get_preview_image,
                                 self.apply_filter,
                                 self.selection_only,
                                 self.active_layer_only)

        def _set_active_only(active_only: bool) -> None:
            self.active_layer_only = active_only

        modal.filter_active_only.connect(_set_active_only)

        def _set_selection_only(selection_only: bool) -> None:
            self.selection_only = selection_only

        modal.filter_selection_only.connect(_set_selection_only)
        return modal

    def get_modal_title(self) -> str:
        """Return the modal's title string."""
        raise NotImplementedError()

    def get_modal_description(self) -> str:
        """Returns the modal's description string."""
        raise NotImplementedError()

    def get_config_key(self) -> str:
        """Returns the KeyConfig key used to load menu item info and keybindings."""
        raise NotImplementedError()

    def get_filter(self) -> Callable[..., QImage]:
        """Returns the filter's image variable filtering function."""
        raise NotImplementedError()

    def get_parameters(self) -> List[Parameter]:
        """Returns definitions for the non-image parameters passed to the filtering function."""
        return []

    def _filter_layer_image(self, filter_param_values: List[Any], layer_id: int, layer_image: QImage) -> bool:
        """Apply any required filtering in-place to a layer image, returning whether changes were made."""
        layer = self._image_stack.get_layer_by_id(layer_id)
        assert layer is not None
        if self._filter_active_layer_only:
            active_layer = self._image_stack.active_layer
            if active_layer.id != layer_id and not (isinstance(active_layer, LayerStack)
                                                    and active_layer.contains_recursive(layer)):
                return False
        if self._filter_selection_only:
            if isinstance(layer, TransformLayer):
                layer_bounds = layer.transformed_bounds
            else:
                layer_bounds = layer.bounds
            selection_bounds = self._image_stack.selection_layer.map_rect_from_image(layer_bounds)
            if self._image_stack.selection_layer.is_empty(selection_bounds):
                return False
            layer_mask = self._image_stack.get_layer_mask(layer)
            if layer_mask.size() != layer_image.size():
                layer_mask = layer_mask.scaled(layer_image.width(), layer_image.height())
            if self.is_local():
                masked_bounds = image_content_bounds(layer_mask)
                if masked_bounds.size() == layer_image.size():
                    filtered_selection_image = self.get_filter()(layer_image, *filter_param_values)
                else:
                    filtered_section = layer_image.copy(masked_bounds)
                    cropped_filtered_image = self.get_filter()(filtered_section, *filter_param_values)
                    filtered_selection_image = layer_image.copy()
                    cropped_change_painter = QPainter(filtered_selection_image)
                    cropped_change_painter.drawImage(masked_bounds, cropped_filtered_image)
                    cropped_change_painter.end()
            else:
                filtered_selection_image = self.get_filter()(layer_image, *filter_param_values)
            # Clear areas where the filter may have altered image data outside the selection:
            filter_painter = QPainter(filtered_selection_image)
            filter_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            filter_painter.drawImage(QPoint(), layer_mask)

            # Fully replace the selected area with the filtered content:
            filtered_image = layer_image.copy()
            filter_painter = QPainter(filtered_image)
            filter_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            filter_painter.drawImage(QPoint(), layer_mask)
            filter_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            filter_painter.drawImage(QPoint(), filtered_selection_image)
            filter_painter.end()
        else:
            filtered_image = self.get_filter()(layer_image, *filter_param_values)
        painter = QPainter(layer_image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawImage(QPoint(), filtered_image)
        painter.end()
        return True

    def get_preview_image(self, filter_param_values: List[Any]) -> QImage:
        """
        Generate a preview of how the filter will be applied with given parameter values.
        Parameters
        ----------
            filter_param_values: list
                Parameter values to use, fitting the definitions the filter provides through get_parameters.
        Returns
        -------
            QImage:
                The new preview image, possibly downscaled to avoid excess image processing time.
        """
        bounds = self._image_stack.layer_stack.bounds
        if self._filter_selection_only:
            cropped_preview_bounds = self._image_stack.selection_layer.get_content_bounds()
            center = cropped_preview_bounds.center()
            cropped_preview_bounds.setWidth(max(int(cropped_preview_bounds.width() * 1.2), MIN_PREVIEW_SIZE))
            cropped_preview_bounds.setHeight(max(int(cropped_preview_bounds.height() * 1.2), MIN_PREVIEW_SIZE))
            cropped_preview_bounds.moveCenter(center)
            cropped_preview_bounds = adjusted_placement_in_bounds(cropped_preview_bounds, bounds)
            scale = min(MAX_PREVIEW_SIZE / cropped_preview_bounds.width(),
                        MAX_PREVIEW_SIZE / cropped_preview_bounds.height())
        else:
            cropped_preview_bounds = None
            scale = min(MAX_PREVIEW_SIZE / bounds.width(), MAX_PREVIEW_SIZE / bounds.height())
        scale = min(1.0, scale)

        preview_transform = QTransform.fromScale(scale, scale)
        bounds = preview_transform.mapRect(bounds)
        if cropped_preview_bounds is not None:
            cropped_preview_bounds = preview_transform.mapRect(cropped_preview_bounds)
        preview_image = QImage(bounds.size(), QImage.Format.Format_ARGB32_Premultiplied)
        background_painter = QPainter(preview_image)
        transparency_pattern = get_transparency_tile_pixmap()
        background_painter.drawTiledPixmap(0, 0, preview_image.width(), preview_image.height(), transparency_pattern)
        background_painter.end()

        def _adjust_layer_paint_params(layer_id: int, layer_image: QImage, _, painter: QPainter) -> Optional[QImage]:
            if scale != 1.0:
                layer_image = layer_image.scaled(int(layer_image.width() * scale), int(layer_image.height() * scale))
                painter.setTransform(preview_transform, True)
            self._filter_layer_image(filter_param_values, layer_id, layer_image)
            return layer_image if scale != 1.0 else None

        self._image_stack.render(preview_image, _adjust_layer_paint_params)
        if cropped_preview_bounds is not None:
            return preview_image.copy(cropped_preview_bounds)
        return preview_image

    def apply_filter(self, filter_param_values: List[Any]) -> None:
        """
        Applies the filter to the image stack, running filter operations in another thread to prevent hanging.

        Parameters
        ----------
            filter_param_values: list
                Parameter values to use, fitting the definitions the filter provides through get_parameters.
        """
        updated_layer_images: Dict[int, QImage] = {}

        def _filter_images() -> None:
            layer_images: Dict[int, QImage] = {}
            if self._filter_selection_only:
                selection_bounds = self._image_stack.selection_layer.get_content_bounds()
                selection_pos = self._image_stack.selection_layer.position
                selection_bounds.translate(-selection_pos.x(), -selection_pos.y())
            else:
                selection_bounds = None
            for layer in self._image_stack.image_layers:
                if selection_bounds is not None and not selection_bounds.intersects(layer.transformed_bounds):
                    continue
                layer_image = layer.image
                image_changed = self._filter_layer_image(filter_param_values, layer.id, layer_image)
                if image_changed:
                    layer_images[layer.id] = layer_image
            for layer_id, image in layer_images.items():
                updated_layer_images[layer_id] = image

        task = AsyncTask(_filter_images, True)

        def _finish() -> None:
            AppStateTracker.set_app_state(APP_STATE_EDITING)
            task.finish_signal.disconnect(_finish)
            if len(updated_layer_images) == 0:
                return
            source_images: Dict[int, QImage] = {}
            for layer_id in updated_layer_images:
                layer = self._image_stack.get_layer_by_id(layer_id)
                assert layer is not None
                source_images[layer_id] = layer.image

            def _apply_filters():
                for updated_id, image in updated_layer_images.items():
                    updated_layer = self._image_stack.get_layer_by_id(updated_id)
                    if isinstance(updated_layer, (ImageLayer, LayerStack)):
                        updated_layer.set_image(image)

            def _undo_filters():
                for updated_id, image in source_images.items():
                    updated_layer = self._image_stack.get_layer_by_id(updated_id)
                    if isinstance(updated_layer, (ImageLayer, LayerStack)):
                        updated_layer.set_image(image)

            UndoStack().commit_action(_apply_filters, _undo_filters, 'ImageFilter.apply_filters')

        task.finish_signal.connect(_finish)
        task.start()
