"""Provides various functions that act on an ImageStack.  Includes only functions that the ImageStack itself does not
   need to access, which don't access any protected internal data."""
from typing import Optional

from PIL import Image
from PySide6.QtCore import QSize, QPoint, QRectF, QRect
from PySide6.QtGui import QTransform, QColor, QPolygonF, QPainterPath
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack, ERROR_TITLE_CROP_FAILED, ERROR_MESSAGE_CROP_FAILED_NO_SELECTION, \
    ERROR_TITLE_IMAGE_SCALE_FAILED, ERROR_MESSAGE_CROP_FAILED_NO_OVERLAP, ACTION_NAME_CROP_LAYER_TO_SELECTION, \
    ERROR_MESSAGE_CROP_FAILED_MULTI, ERROR_MESSAGE_CROP_FAILED_FULLY_CONTAINED, WARNING_MESSAGE_CROP_DELETED_LAYERS, \
    WARNING_TITLE_CROP_DELETED_LAYERS
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.layer_resize_mode import LayerResizeMode
from src.image.layers.text_layer import TextLayer
from src.image.layers.transform_layer import TransformLayer
from src.ui.modal.modal_utils import show_error_dialog, show_warning_dialog
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_content_bounds
from src.util.visual.pil_image_utils import pil_image_scaling

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.layers.image_stack_utils'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


def resize_image_stack_to_content(image_stack: ImageStack) -> None:
    """Resizes the image to match image content."""
    full_bounds = image_stack.merged_layer_bounds
    image_stack.resize_canvas(full_bounds.size(), -full_bounds.x(), -full_bounds.y(), LayerResizeMode.RESIZE_NONE,
                              False)


def crop_image_stack_to_bounds(image_stack: ImageStack, bounds: QRect) -> None:
    """Crops the image stack to an arbitrary bounding rectangle."""
    image_stack.resize_canvas(bounds.size(), -bounds.x(), -bounds.y(), LayerResizeMode.RESIZE_NONE, crop_layers=True)


def crop_image_stack_to_selection(image_stack: ImageStack) -> None:
    """Crops the image stack to match its selection bounds"""
    selection_layer = image_stack.selection_layer
    np_selection = selection_layer.image_bits_readonly
    selection_pos = selection_layer.position
    selection_bounds = image_content_bounds(np_selection).translated(selection_pos.x(), selection_pos.y())
    if selection_bounds.isEmpty():
        show_error_dialog(None, ERROR_TITLE_CROP_FAILED, ERROR_MESSAGE_CROP_FAILED_NO_SELECTION)
        return
    crop_image_stack_to_bounds(image_stack, selection_bounds)


def crop_image_stack_to_gen_area(image_stack: ImageStack) -> None:
    """Crops the image stack to the generation area."""
    gen_area_bounds = image_stack.generation_area
    crop_image_stack_to_bounds(image_stack, gen_area_bounds)


def crop_layer_to_selection(image_stack: ImageStack, layer: Optional[Layer] = None) -> None:
    """Crop a layer to perfectly fit selected content within that layer, using the active layer if no specific layer
    is provided."""
    if layer is None:
        layer = image_stack.active_layer
    if not image_stack.validate_layer_showing_errors(layer, allow_layer_stack=True):
        return
    if image_stack.selection_layer.is_empty():
        show_error_dialog(None, ERROR_TITLE_CROP_FAILED, ERROR_MESSAGE_CROP_FAILED_NO_OVERLAP)
        return
    if isinstance(layer, LayerGroup):
        all_layers = layer.recursive_child_layers
    else:
        all_layers = [layer]
    text_layers = [crop_layer for crop_layer in all_layers if isinstance(crop_layer, TextLayer)]
    if len(text_layers) > 0:
        text_layer_names = [text_layer.name for text_layer in text_layers]
        if not TextLayer.confirm_or_cancel_render_to_image(text_layer_names,
                                                           ACTION_NAME_CROP_LAYER_TO_SELECTION):
            return
    with UndoStack().combining_actions('image_stack_utils.crop_layer_to_selection'):
        no_overlap_count = 0
        no_content_cropped_count = 0
        crop_success_count = 0
        to_delete = []
        deleted_layer_names = []
        if len(text_layers) > 0:
            replacements: dict[int, Layer] = {}
            for i, updated_layer in enumerate(all_layers):
                if isinstance(updated_layer, TextLayer):
                    replacements[i] = image_stack.replace_text_layer_with_image(updated_layer)
            for i, image_layer in replacements.items():
                all_layers[i] = image_layer
        for cropped_layer in all_layers:
            if not isinstance(cropped_layer, ImageLayer):
                assert isinstance(cropped_layer, LayerGroup)
                continue
            layer_mask = image_stack.get_layer_selection_mask(cropped_layer)
            content_bounds = image_content_bounds(layer_mask)
            layer_bounds = cropped_layer.bounds
            if content_bounds == layer_bounds:
                no_content_cropped_count += 1
                continue
            if content_bounds.isEmpty():
                if len(all_layers) > 1:
                    to_delete.append(cropped_layer)
                else:
                    no_overlap_count += 1
                continue
            cropped_layer.crop_to_bounds(content_bounds, False)
            crop_success_count += 1
        for deleted_layer in to_delete:
            deleted_layer_names.append(deleted_layer.name)
            image_stack.remove_layer(deleted_layer)
            crop_success_count += 1
        if crop_success_count == 0:
            if no_overlap_count > 0 and no_content_cropped_count > 0:
                show_error_dialog(None, ERROR_TITLE_CROP_FAILED, ERROR_MESSAGE_CROP_FAILED_MULTI)
            elif no_overlap_count > 0:
                show_error_dialog(None, ERROR_TITLE_CROP_FAILED, ERROR_MESSAGE_CROP_FAILED_NO_OVERLAP)
            else:
                assert no_content_cropped_count > 0
                show_error_dialog(None, ERROR_TITLE_CROP_FAILED, ERROR_MESSAGE_CROP_FAILED_FULLY_CONTAINED)
            if not layer_bounds.intersects(content_bounds):
                return
        if len(deleted_layer_names) > 0:
            warning_message = WARNING_MESSAGE_CROP_DELETED_LAYERS.format(
                layer_names=' '.join((f'<li>{name}</li>' for name in deleted_layer_names)))
            show_warning_dialog(None, WARNING_TITLE_CROP_DELETED_LAYERS, warning_message,
                                AppConfig.WARN_WHEN_CROP_DELETES_LAYERS)


def scale_all_layers(image_stack: ImageStack, width: int, height: int,
                     image_scale_mode: Optional[Image.Resampling] = None) -> None:
    """Scale all layer content by applying PIL scaling or adjusting layer transformations."""
    initial_size = image_stack.size
    if width == initial_size.width() and height == initial_size.height():
        return
    if width <= 0 or height <= 0:
        raise ValueError(f'size must be greater than zero, got {width}x{height}')
    x_scale = width / initial_size.width()
    y_scale = height / initial_size.height()

    if not image_stack.confirm_no_locked_layers(ERROR_TITLE_IMAGE_SCALE_FAILED):
        return

    scale_transform = QTransform.fromScale(x_scale, y_scale)
    action_id = 'image_stack_utils.scale_all_layers'
    with UndoStack().combining_actions(action_id) and image_stack.batching_content_updates():
        for layer in image_stack.all_layers():
            if not isinstance(layer, TransformLayer):
                continue
            if isinstance(layer, ImageLayer) and image_scale_mode is not None:
                image = layer.image
                if image.size() == initial_size:
                    new_size = QSize(width, height)
                else:
                    new_size = QSize(round(image.width() * x_scale), round(image.height() * y_scale))
                layer.image = pil_image_scaling(image, new_size, image_scale_mode)
            else:
                layer.transform = layer.transform * scale_transform
        new_size = QSize(width, height)

        def _final_size_update(size=new_size) -> None:
            image_stack.size = size

        def _revert(size=initial_size) -> None:
            image_stack.size = size

        UndoStack().commit_action(_final_size_update, _revert, action_id)


def image_stack_color_at_point(image_stack: ImageStack, image_point: QPoint) -> QColor:
    """Gets the combined color of visible saved layers at a single point, or QColor(0, 0, 0) if out of bounds."""
    image_bounds = image_stack.bounds
    if image_bounds.contains(image_point):
        return image_stack.qimage(True).pixelColor(image_point)
    content_bounds = image_stack.merged_layer_bounds
    adjusted_point = image_point - content_bounds.topLeft()
    if not content_bounds.contains(adjusted_point):
        return QColor(0, 0, 0)
    return image_stack.qimage(False).pixelColor(adjusted_point)


def top_layer_at_point(image_stack: ImageStack, image_coordinates: QPoint) -> Optional[ImageLayer | TextLayer]:
    """Return the topmost image or text layer that contains non-transparent pixels at the given coordinates, or the
       topmost with transparent pixels if none are non-transparent at that point."""
    all_layers = [layer for layer in image_stack.layer_stack.recursive_child_layers
                  if isinstance(layer, (ImageLayer, TextLayer))]
    top_transparent: Optional[ImageLayer | TextLayer] = None
    for layer in all_layers:
        layer_point = layer.map_from_image(image_coordinates)
        if not layer.bounds.contains(layer_point):
            continue
        layer_image = layer.get_qimage()
        pixel_color = layer_image.pixelColor(layer_point)
        if pixel_color.alpha() > 0:
            return layer
        elif top_transparent is None or (top_transparent.locked or top_transparent.parent_locked
                                         or not top_transparent.visible):
            top_transparent = layer
    return top_transparent


def image_stack_outline_path(image_stack: ImageStack) -> QPainterPath:
    """Gets the outline of all layers in an image stack."""
    polygon = QPolygonF()
    all_layers = [layer for layer in image_stack.all_layers() if not isinstance(layer, LayerGroup)]
    for layer in all_layers:
        layer_bounds = QRectF(layer.bounds)
        if isinstance(layer, TransformLayer):
            transformed_bounds_polygon = layer.transform.map(layer_bounds)
            polygon = polygon.united(transformed_bounds_polygon)
        else:
            polygon = polygon.united(layer_bounds)
    path = QPainterPath()
    path.addPolygon(polygon)
    return path
