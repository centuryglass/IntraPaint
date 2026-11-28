"""Tests met_requirements, which reports which menu action requirements an image stack meets."""
from PySide6.QtCore import QSize

from src.controller.menu_requirements import met_requirements, SELECTION, UNLOCKED_LAYER, HAS_PREVIOUS_LAYER, \
    HAS_NEXT_LAYER, NOT_LAYER_STACK, NOT_FLAT, LAYER_GROUP, NOT_LAYER_GROUP, NOT_TEXT_LAYER, PAINTABLE_LAYER
from src.image.layers.image_stack import ImageStack
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase


class MetRequirementsTest(IntraPaintTestCase):
    """Each requirement is reported for a stack that meets it, and omitted for one that doesn't."""

    def setUp(self) -> None:
        super().setUp()
        size = QSize(64, 64)
        self.image_stack = ImageStack(size, size, size, size, UndoStack())
        root = self.image_stack.layer_stack
        self.lower = self.image_stack.create_layer('lower', layer_parent=root, layer_index=0)
        self.upper = self.image_stack.create_layer('upper', layer_parent=root, layer_index=0)
        self.image_stack.active_layer = self.lower

    def _assert_met(self, requirement: str, met: bool) -> None:
        self.assertEqual(requirement in met_requirements(self.image_stack), met)

    def test_selection(self) -> None:
        """SELECTION needs a non-empty selection."""
        self._assert_met(SELECTION, False)
        self.image_stack.selection_layer.select_all()
        self._assert_met(SELECTION, True)

    def test_unlocked_layer(self) -> None:
        """UNLOCKED_LAYER needs the active layer and its parents unlocked."""
        self._assert_met(UNLOCKED_LAYER, True)
        self.lower.locked = True
        self._assert_met(UNLOCKED_LAYER, False)
        self.lower.locked = False
        group = self.image_stack.create_layer_group('group', layer_parent=self.image_stack.layer_stack,
                                                    layer_index=0)
        child = self.image_stack.create_layer('child', layer_parent=group, layer_index=0)
        self.image_stack.active_layer = child
        self._assert_met(UNLOCKED_LAYER, True)
        group.locked = True
        self._assert_met(UNLOCKED_LAYER, False)

    def test_has_previous_layer(self) -> None:
        """HAS_PREVIOUS_LAYER needs a previous layer in list order other than the root stack."""
        self._assert_met(HAS_PREVIOUS_LAYER, True)
        self.image_stack.active_layer = self.upper
        self._assert_met(HAS_PREVIOUS_LAYER, False)
        self.image_stack.active_layer = self.image_stack.layer_stack
        self._assert_met(HAS_PREVIOUS_LAYER, False)

    def test_has_next_layer(self) -> None:
        """HAS_NEXT_LAYER needs a next layer in list order, which the root stack has while it holds any layers."""
        self.image_stack.active_layer = self.upper
        self._assert_met(HAS_NEXT_LAYER, True)
        root = self.image_stack.layer_stack
        self.image_stack.active_layer = root.child_layers[-1]
        self._assert_met(HAS_NEXT_LAYER, False)
        self.image_stack.active_layer = root
        self._assert_met(HAS_NEXT_LAYER, True)
        for layer in list(root.child_layers):
            self.image_stack.remove_layer(layer)
        self.image_stack.active_layer = root
        self._assert_met(HAS_NEXT_LAYER, False)

    def test_not_layer_stack(self) -> None:
        """NOT_LAYER_STACK needs an active layer other than the root stack."""
        self._assert_met(NOT_LAYER_STACK, True)
        self.image_stack.active_layer = self.image_stack.layer_stack
        self._assert_met(NOT_LAYER_STACK, False)

    def test_not_flat(self) -> None:
        """NOT_FLAT needs an active layer that flattening would change."""
        self._assert_met(NOT_FLAT, False)
        self.lower.opacity = 0.5
        self._assert_met(NOT_FLAT, True)

    def test_layer_group(self) -> None:
        """LAYER_GROUP and NOT_LAYER_GROUP follow whether the active layer is a group."""
        self._assert_met(LAYER_GROUP, False)
        self._assert_met(NOT_LAYER_GROUP, True)
        self.image_stack.active_layer = self.image_stack.create_layer_group()
        self._assert_met(LAYER_GROUP, True)
        self._assert_met(NOT_LAYER_GROUP, False)

    def test_not_text_layer(self) -> None:
        """NOT_TEXT_LAYER needs an active layer that isn't a text layer."""
        self._assert_met(NOT_TEXT_LAYER, True)
        self.image_stack.active_layer = self.image_stack.create_text_layer()
        self._assert_met(NOT_TEXT_LAYER, False)

    def test_paintable_layer(self) -> None:
        """PAINTABLE_LAYER needs an image layer or a non-destructive layer as the active layer."""
        self._assert_met(PAINTABLE_LAYER, True)
        self.image_stack.active_layer = self.image_stack.create_text_layer()
        self._assert_met(PAINTABLE_LAYER, True)
        self.image_stack.active_layer = self.image_stack.create_layer_group()
        self._assert_met(PAINTABLE_LAYER, False)
