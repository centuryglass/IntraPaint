"""Maps animation frames to layers: one top-level layer per frame, with the first frame at the bottom of the stack.

A frame's display time is stored in its layer name as a GIMP-style "(120ms)" tag, so it survives saving to .ora and
can be changed by renaming the layer. Only the first frame's layer starts out visible, so the canvas shows the first
frame.
"""
from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer_group import LayerGroup
from src.util.visual.image_format_utils import ImageFrame

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'image.animation'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


FRAME_LAYER_NAME = _tr('Frame {frame_number}')

# Not translated: animation saving reads frame durations back out of layer names.
FRAME_DURATION_TAG = ' ({duration_ms}ms)'


def frame_layer_name(frame_number: int, duration_ms: Optional[int], name_prefix: str = '') -> str:
    """Returns the layer name for a frame, numbered from 1, with its duration tag if it has a duration."""
    name = name_prefix + FRAME_LAYER_NAME.format(frame_number=frame_number)
    if duration_ms is not None:
        name += FRAME_DURATION_TAG.format(duration_ms=duration_ms)
    return name


def load_frames_as_image(image_stack: ImageStack, frames: list[ImageFrame]) -> None:
    """Replaces the edited image with one layer per frame, sizing the canvas to fit the largest frame."""
    assert len(frames) > 0
    layer_stack = LayerGroup('')
    canvas_size = QSize()
    for frame_number, frame in enumerate(frames, start=1):
        layer = ImageLayer(frame.image, frame_layer_name(frame_number, frame.duration_ms))
        layer.set_visible(frame_number == 1)
        layer_stack.insert_layer(layer, 0)
        canvas_size = canvas_size.expandedTo(frame.image.size())
    first_frame_layer = layer_stack.get_layer_by_index(layer_stack.count - 1)
    image_stack.load_layer_stack(layer_stack, canvas_size, first_frame_layer)


def add_frame_layers(image_stack: ImageStack, frames: list[ImageFrame], name_prefix: str = '') -> None:
    """Adds one layer per frame above the active layer, prefixing each layer name with name_prefix."""
    previous_layer: Optional[ImageLayer] = None
    for frame_number, frame in enumerate(frames, start=1):
        name = frame_layer_name(frame_number, frame.duration_ms, name_prefix)
        if previous_layer is None:
            layer = image_stack.create_layer(name, frame.image)
        else:
            parent = previous_layer.layer_parent
            assert isinstance(parent, LayerGroup)
            layer = image_stack.create_layer(name, frame.image, parent, parent.get_layer_index(previous_layer))
        layer.set_visible(frame_number == 1)
        previous_layer = layer
