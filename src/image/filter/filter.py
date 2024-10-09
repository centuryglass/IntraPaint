"""Generic interface for image filtering functions. Handles the process of opening modal windows to apply the filter
and provides the information needed to add the function as a menu action."""
import math
from typing import Callable, List, Optional, Dict, Any

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QImage, QPainter, QTransform, QIcon
from PySide6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.text_layer import TextLayer
from src.image.layers.transform_layer import TransformLayer
from src.ui.modal.image_filter_modal import ImageFilterModal
from src.undo_stack import UndoStack
from src.util.application_state import APP_STATE_EDITING, AppStateTracker
from src.util.async_task import AsyncTask
from src.util.parameter import Parameter
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.image_utils import get_transparency_tile_pixmap, image_content_bounds, image_data_as_numpy_8bit, \
    numpy_bounds_index

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.filter.filter'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


ACTION_NAME_FILTER = _tr('Apply image filter')


MAX_PREVIEW_SIZE = 800
MIN_PREVIEW_SIZE = 200
ICON_PATH_FILTER_GENERIC = f'{PROJECT_DIR}/resources/icons/tools/filter_icon.svg'


class ImageFilter:
    """Interface for image filtering functions exposed through a modal UI."""

    def __init__(self, image_stack: ImageStack, icon_path=ICON_PATH_FILTER_GENERIC) -> None:
        self._image_stack = image_stack
        self._filter_selection_only = True
        self._filter_active_layer_only = True
        self._icon = QIcon(icon_path)

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

    def radius(self, parameter_values: List[Any]) -> float:
        """Given a set of valid parameters, estimate how far each pixel's influence extends in the final image."""
        return 0.0

    def get_filter_modal(self) -> ImageFilterModal:
        """Creates and returns a modal widget that can apply the filter to the edited image."""
        self.selection_only = not self._image_stack.selection_layer.empty
        modal = ImageFilterModal(self.get_name(),
                                 self.get_modal_description(),
                                 self.get_parameters(),
                                 self.get_preview_image,
                                 self.apply_filter,
                                 self.selection_only,
                                 self.active_layer_only)

        def _set_active_only(active_only: bool) -> None:
            self.active_layer_only = active_only

        modal.filter_active_only.connect(_set_active_only)
        modal.setWindowIcon(self.get_icon())

        def _set_selection_only(selection_only: bool) -> None:
            self.selection_only = selection_only

        modal.filter_selection_only.connect(_set_selection_only)
        return modal

    def get_name(self) -> str:
        """Return the filter's name string."""
        raise NotImplementedError()

    def get_icon(self) -> QIcon:
        """Return the filter's icon."""
        return self._icon

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

    def validate_parameter_values(self, parameter_values: List[Any]) -> None:
        """Raise an exception if a set of parameter values is not valid for this filter."""
        parameters = self.get_parameters()
        if len(parameter_values) != len(parameters):
            raise ValueError(f'Expected {len(parameters)} parameters, got {len(parameter_values)}')
        for i, parameter in enumerate(parameters):
            parameter.validate(parameter_values[i])

    def _filter_layer_image(self, filter_param_values: List[Any], layer_id: int, layer_image: QImage) -> bool:
        """Apply any required filtering in-place to a layer image, returning whether changes were made."""
        layer = self._image_stack.get_layer_by_id(layer_id)
        assert layer is not None
        if isinstance(layer, LayerGroup):
            return False
        if self._filter_active_layer_only:
            active_layer = self._image_stack.active_layer
            if active_layer.id != layer_id and not (isinstance(active_layer, LayerGroup)
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
            masked_bounds = image_content_bounds(layer_mask)
            if not self.is_local():
                radius = math.ceil(self.radius(filter_param_values))
                masked_bounds.adjust(-radius, -radius, radius, radius)
                masked_bounds = masked_bounds.intersected(layer.bounds)
            if masked_bounds.size() == layer_image.size():
                filtered_selection_image = self.get_filter()(layer_image, *filter_param_values)
            else:
                filtered_section = layer_image.copy(masked_bounds)
                filtered_selection_image = self.get_filter()(filtered_section, *filter_param_values)
            # Copy filtered content into masked areas:

            np_mask = image_data_as_numpy_8bit(layer_mask)
            np_filtered = image_data_as_numpy_8bit(filtered_selection_image)
            np_final = image_data_as_numpy_8bit(layer_image)

            if masked_bounds != layer.bounds:
                np_mask = numpy_bounds_index(np_mask, masked_bounds)
                np_final = numpy_bounds_index(np_final, masked_bounds)
            selected = np_mask[:, :, 3] > 0
            np_final[selected, :] = np_filtered[selected, :]
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
        preview_bounds = QRect(bounds)
        if self.active_layer_only:
            active_layer = self._image_stack.active_layer
            if isinstance(active_layer, TransformLayer):
                active_bounds = active_layer.transformed_bounds
            else:
                active_bounds = active_layer.bounds
            preview_bounds = preview_bounds.intersected(active_bounds)
        if self._filter_selection_only:
            selection_bounds = self._image_stack.selection_layer.get_content_bounds()
            if not selection_bounds.isEmpty() and preview_bounds.contains(selection_bounds):
                preview_bounds = preview_bounds.intersected(selection_bounds)
        change_size = QSize(preview_bounds.size())
        preview_bounds.setX(max(bounds.x(), preview_bounds.x() - round(change_size.width() * 0.1)))
        preview_bounds.setWidth(min(bounds.x() + bounds.width() - preview_bounds.x(),
                                    round(change_size.width() * 1.2)))
        preview_bounds.setY(max(bounds.y(), preview_bounds.y() - round(change_size.height() * 0.1)))
        preview_bounds.setHeight(min(bounds.y() + bounds.height() - preview_bounds.y(),
                                     round(change_size.height() * 1.2)))
        if preview_bounds.isEmpty():
            return QImage()

        preview_transform = QTransform.fromTranslate(-preview_bounds.x(), -preview_bounds.y())
        preview_image = QImage(preview_bounds.size(), QImage.Format.Format_ARGB32_Premultiplied)
        background_painter = QPainter(preview_image)
        transparency_pattern = get_transparency_tile_pixmap()
        background_painter.drawTiledPixmap(0, 0, preview_image.width(), preview_image.height(), transparency_pattern)
        background_painter.end()

        def apply_filter(layer: Layer, layer_image: QImage) -> QImage:
            """Apply the filter to each layer image as an intermediate step."""
            self._filter_layer_image(filter_param_values, layer.id, layer_image)
            return layer_image

        self._image_stack.render(base_image=preview_image, transform=preview_transform, image_adjuster=apply_filter)
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

        changed_text_layers: List[TextLayer] = []
        changed_parent_group: Optional[LayerGroup] = None
        if self._filter_active_layer_only:
            active_layer = self._image_stack.active_layer
            if isinstance(active_layer, LayerGroup):
                changed_parent_group = active_layer
            elif isinstance(active_layer, TextLayer) and not active_layer.locked and not active_layer.parent_locked:
                changed_text_layers.append(active_layer)
        else:
            changed_parent_group = self._image_stack.layer_stack
        if changed_parent_group is not None:
            for child_layer in changed_parent_group.recursive_child_layers:
                if isinstance(child_layer, TextLayer) and not child_layer.locked and not child_layer.parent_locked:
                    changed_text_layers.append(child_layer)

        text_layer_names = [layer.name for layer in changed_text_layers]
        if len(changed_text_layers) > 0 and not TextLayer.confirm_or_cancel_render_to_image(text_layer_names,
                                                                                            ACTION_NAME_FILTER):
            return
        for text_layer in changed_text_layers:
            self._image_stack.replace_text_layer_with_image(text_layer)

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
                    if isinstance(updated_layer, (ImageLayer, LayerGroup)):
                        updated_layer.set_image(image)

            def _undo_filters():
                for updated_id, image in source_images.items():
                    updated_layer = self._image_stack.get_layer_by_id(updated_id)
                    if isinstance(updated_layer, (ImageLayer, LayerGroup)):
                        updated_layer.set_image(image)

            UndoStack().commit_action(_apply_filters, _undo_filters, 'ImageFilter.apply_filters')

        task.finish_signal.connect(_finish)
        task.start()
