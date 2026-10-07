"""Snapshots of an ImageStack's full state, and a base test case that checks undo and redo restore them.

`StackState.capture` records everything an undoable ImageStack operation can change: canvas size, active layer, the
layer tree (each layer's object, properties, transform and pixels, and each group's isolate flag), the selection
layer, and the composite. `ImageStackOpTestCase.assert_undo_redo` applies an operation and checks that undo and redo
each restore the exact state on their side of it.
"""
import sys
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QTransform
from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.transform_layer import TransformLayer
from src.undo_stack import UndoStack
from src.util.visual.image_utils import image_data_as_numpy_8bit
from test.base_test_case import IntraPaintTestCase, assert_images_equal
from test.render_assertions import full_render

app = QApplication.instance() or QApplication(sys.argv)

CANVAS_SIZE = QSize(32, 24)
MIN_GEN_AREA = QSize(8, 8)
MAX_GEN_AREA = QSize(999, 999)


def noise_image(size: QSize, seed: int, min_alpha: int = 255) -> QImage:
    """Returns a premultiplied image of random colors, with random alpha no lower than min_alpha."""
    rng = np.random.default_rng(seed)
    alpha = rng.integers(min_alpha, 256, (size.height(), size.width()), dtype=np.uint16)
    color = rng.integers(0, 256, (size.height(), size.width(), 3), dtype=np.uint16)
    pixels = np.empty((size.height(), size.width(), 4), dtype=np.uint8)
    pixels[:, :, :3] = color * alpha[:, :, np.newaxis] // 255
    pixels[:, :, 3] = alpha
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    np.copyto(image_data_as_numpy_8bit(image), pixels)
    return image


def select_rect(image_stack: ImageStack, rect: QRect) -> None:
    """Replaces the selection with a canvas-space rectangle."""
    selection_layer = image_stack.selection_layer
    with selection_layer.borrow_image() as mask_image:
        assert mask_image is not None
        mask_image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(mask_image)
        painter.fillRect(rect.translated(-selection_layer.position), Qt.GlobalColor.red)
        painter.end()


def masked_to_rect(image: QImage, rect: QRect) -> QImage:
    """Returns a copy of image with everything outside rect cleared to transparent."""
    masked = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    mask = QImage(masked.size(), QImage.Format.Format_ARGB32_Premultiplied)
    mask.fill(Qt.GlobalColor.transparent)
    painter = QPainter(mask)
    painter.fillRect(rect, Qt.GlobalColor.black)
    painter.end()
    painter = QPainter(masked)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawImage(QPoint(), mask)
    painter.end()
    return masked


def _transform_values(transform: QTransform) -> tuple[float, ...]:
    return (transform.m11(), transform.m12(), transform.m13(), transform.m21(), transform.m22(), transform.m23(),
            transform.m31(), transform.m32(), transform.m33())


@dataclass
class LayerState:
    """One layer's properties and pixels, with its parent and position in the tree."""
    layer: Layer
    parent: Optional[Layer]
    properties: dict
    image: Optional[QImage]


@dataclass
class StackState:
    """Everything an undoable ImageStack operation can change."""
    size: QSize
    active_layer: Layer
    layers: list[LayerState]
    selection_image: QImage
    selection_transform: tuple[float, ...]
    composite: QImage

    @staticmethod
    def capture(image_stack: ImageStack) -> 'StackState':
        """Records the current state, flushing pending renders first."""
        image_stack.flush_render()
        layers = []
        for layer in image_stack.layer_stack.recursive_child_layers:
            properties = {
                'type': type(layer).__name__,
                'name': layer.name,
                'visible': layer.visible,
                'opacity': layer.opacity,
                'mode': layer.composition_mode,
                'locked': layer.locked,
                'z_value': layer.z_value,
            }
            image: Optional[QImage] = None
            if isinstance(layer, LayerGroup):
                properties['isolate'] = layer.isolate
                properties['children'] = [child.id for child in layer.child_layers]
            else:
                image = layer.image
            if isinstance(layer, TransformLayer):
                properties['transform'] = _transform_values(layer.transform)
            if isinstance(layer, ImageLayer):
                properties['alpha_locked'] = layer.alpha_locked
            layers.append(LayerState(layer, layer.layer_parent if isinstance(layer.layer_parent, Layer) else None,
                                     properties, image))
        selection_layer = image_stack.selection_layer
        return StackState(image_stack.size, image_stack.active_layer, layers, selection_layer.image,
                          _transform_values(selection_layer.transform), full_render(image_stack))

    def assert_matches(self, expected: 'StackState', label: str) -> None:
        """Asserts that this state matches another exactly."""
        assert self.size == expected.size, f'{label}: size {self.size} != {expected.size}'
        assert self.active_layer is expected.active_layer, \
            f'{label}: active layer {self.active_layer.name} != {expected.active_layer.name}'
        actual_tree = [(state.layer, state.parent) for state in self.layers]
        expected_tree = [(state.layer, state.parent) for state in expected.layers]
        assert actual_tree == expected_tree, (f'{label}: layer tree {[state.layer.name for state in self.layers]}'
                                              f' != {[state.layer.name for state in expected.layers]}')
        for actual, expected_layer in zip(self.layers, expected.layers):
            name = expected_layer.properties['name']
            assert actual.properties == expected_layer.properties, \
                f'{label}: layer {name} properties {actual.properties} != {expected_layer.properties}'
            if expected_layer.image is not None:
                assert actual.image is not None
                assert_images_equal(actual.image, expected_layer.image, f'{label}: layer {name} image')
        assert self.selection_transform == expected.selection_transform, f'{label}: selection transform'
        assert_images_equal(self.selection_image, expected.selection_image, f'{label}: selection')
        assert_images_equal(self.composite, expected.composite, f'{label}: composite')


class ImageStackOpTestCase(IntraPaintTestCase):
    """Builds a small ImageStack with no undo history, and checks operations against undo and redo."""

    def setUp(self) -> None:
        super().setUp()
        # Without time-based merging, each committed operation is its own undo step.
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 0.0)
        self.image_stack = ImageStack(CANVAS_SIZE, CANVAS_SIZE, MIN_GEN_AREA, MAX_GEN_AREA)

    def add_layer(self, name: str, seed: int, size: Optional[QSize] = None, offset: QPoint = QPoint(),
                  parent: Optional[LayerGroup] = None, min_alpha: int = 255) -> ImageLayer:
        """Adds a noise-filled layer at the bottom of parent, or of the layer stack."""
        parent = self.image_stack.layer_stack if parent is None else parent
        layer = self.image_stack.create_layer(name, noise_image(CANVAS_SIZE if size is None else size, seed,
                                                                min_alpha),
                                              layer_parent=parent, layer_index=parent.count)
        if not offset.isNull():
            layer.set_transform(QTransform.fromTranslate(offset.x(), offset.y()))
        return layer

    def add_group(self, name: str, parent: Optional[LayerGroup] = None) -> LayerGroup:
        """Adds an empty group at the bottom of parent, or of the layer stack."""
        parent = self.image_stack.layer_stack if parent is None else parent
        return self.image_stack.create_layer_group(name, parent, parent.count)

    def add_nested_layers(self) -> tuple[ImageLayer, LayerGroup, ImageLayer, ImageLayer, ImageLayer]:
        """Adds translucent layers [top, group [inner a, inner b], bottom], returned in that order."""
        top = self.add_layer('top', 1, QSize(12, 10), QPoint(2, 2), min_alpha=80)
        group = self.add_group('group')
        inner_a = self.add_layer('inner a', 2, QSize(14, 10), QPoint(6, 6), group, min_alpha=80)
        inner_b = self.add_layer('inner b', 3, QSize(14, 10), QPoint(10, 9), group, min_alpha=80)
        bottom = self.add_layer('bottom', 4, min_alpha=80)
        return top, group, inner_a, inner_b, bottom

    def capture(self) -> StackState:
        """Records the image stack's current state."""
        return StackState.capture(self.image_stack)

    def assert_undo_redo(self, operation: Callable[[], None]) -> tuple[StackState, StackState]:
        """Runs operation as one new undo step, then checks that undo and redo restore the state before and after it,
        twice over. Returns the before and after states."""
        UndoStack().clear()
        before = self.capture()
        operation()
        after = self.capture()
        self.assertEqual(1, UndoStack().undo_count(), 'operation should be one undo step')
        for cycle in range(2):
            UndoStack().undo()
            self.capture().assert_matches(before, f'undo {cycle + 1}')
            UndoStack().redo()
            self.capture().assert_matches(after, f'redo {cycle + 1}')
        return before, after
