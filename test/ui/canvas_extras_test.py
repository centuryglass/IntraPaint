"""Tests that CanvasExtras hides marker categories without changing their items' own visibility, and that ImageViewer
and the editing tools register their markers in the expected categories and stacking order."""
import sys

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QApplication, QGraphicsItem, QGraphicsRectItem, QGraphicsScene

from src.image.layers.image_stack import ImageStack
from src.tools.free_selection_tool import FreeSelectionTool
from src.tools.generation_area_tool import GenerationAreaTool
from src.tools.layer_transform_tool import LayerTransformTool
from src.tools.text_tool import TextTool
from src.ui.canvas_extras import CanvasExtras, CanvasExtraCategory
from src.ui.graphics_items.context_pin_item import ContextPinItem
from src.ui.image_viewer import ImageViewer
from test.base_test_case import IntraPaintTestCase
from test.tools.tool_test_case import ToolTestCase

app = QApplication.instance() or QApplication(sys.argv)

# pylint: disable=protected-access


class CanvasExtrasTest(IntraPaintTestCase):
    """Tests showing and hiding categories in a plain scene."""

    def setUp(self) -> None:
        super().setUp()
        self.scene = QGraphicsScene()
        self.extras = CanvasExtras(self.scene)

    def tearDown(self) -> None:
        self.scene.clear()
        super().tearDown()

    def _add_item(self, category: CanvasExtraCategory, visible: bool = True) -> QGraphicsRectItem:
        item = QGraphicsRectItem(0, 0, 10, 10)
        item.setVisible(visible)
        self.scene.addItem(item)
        self.extras.register(item, category)
        return item

    def test_register_keeps_item_state(self) -> None:
        """A registered item stays in the scene with its own visibility, position and z-value."""
        item = QGraphicsRectItem(0, 0, 10, 10)
        item.setPos(5, 7)
        item.setZValue(3)
        hidden_item = QGraphicsRectItem(0, 0, 10, 10)
        hidden_item.setVisible(False)
        self.scene.addItem(item)
        self.extras.register(item, CanvasExtraCategory.SELECTION)
        self.extras.register(hidden_item, CanvasExtraCategory.SELECTION)
        self.assertIs(item.scene(), self.scene)
        self.assertIs(hidden_item.scene(), self.scene)
        self.assertTrue(item.isVisible())
        self.assertFalse(hidden_item.isVisible())
        self.assertEqual(item.scenePos(), QPointF(5, 7))
        self.assertEqual(item.zValue(), 3)

    def test_hiding_category_hides_only_its_items(self) -> None:
        """Hiding a category hides its items and leaves other categories alone."""
        selection_item = self._add_item(CanvasExtraCategory.SELECTION)
        tool_item = self._add_item(CanvasExtraCategory.TOOL)
        self.extras.set_shown(CanvasExtraCategory.SELECTION, False)
        self.assertFalse(self.extras.is_shown(CanvasExtraCategory.SELECTION))
        self.assertFalse(selection_item.isVisible())
        self.assertTrue(tool_item.isVisible())

    def test_showing_category_restores_each_item_visibility(self) -> None:
        """Showing a category again shows each item as its owner last set it, including changes made while hidden."""
        shown_item = self._add_item(CanvasExtraCategory.GENERATION_AREA)
        hidden_item = self._add_item(CanvasExtraCategory.GENERATION_AREA, visible=False)
        shown_while_hidden = self._add_item(CanvasExtraCategory.GENERATION_AREA, visible=False)
        hidden_while_hidden = self._add_item(CanvasExtraCategory.GENERATION_AREA)
        self.extras.set_shown(CanvasExtraCategory.GENERATION_AREA, False)
        shown_while_hidden.setVisible(True)
        hidden_while_hidden.setVisible(False)
        self.assertFalse(shown_while_hidden.isVisible())
        self.extras.set_shown(CanvasExtraCategory.GENERATION_AREA, True)
        self.assertTrue(shown_item.isVisible())
        self.assertFalse(hidden_item.isVisible())
        self.assertTrue(shown_while_hidden.isVisible())
        self.assertFalse(hidden_while_hidden.isVisible())

    def test_removed_item_leaves_its_container(self) -> None:
        """Removing a registered item from the scene also removes it from its category's container."""
        item = self._add_item(CanvasExtraCategory.CANVAS)
        container = self.extras.container(CanvasExtraCategory.CANVAS)
        self.scene.removeItem(item)
        self.assertIsNone(item.parentItem())
        self.assertNotIn(item, container.childItems())


class ImageViewerCanvasExtrasTest(IntraPaintTestCase):
    """Tests the categories and stacking order of ImageViewer's own markers."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(QSize(64, 64), QSize(64, 64), QSize(8, 8), QSize(64, 64))
        image = QImage(64, 64, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(Qt.GlobalColor.red))
        self.image_stack.create_layer(image_data=image)
        self.image_stack.generation_area = QRect(8, 8, 32, 32)
        self.image_stack.selection_layer.set_context_pins([QPoint(4, 4)])
        self.viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        self.extras = self.viewer.canvas_extras

    def _category_of(self, item: QGraphicsItem) -> CanvasExtraCategory:
        for category in CanvasExtraCategory:
            if item.parentItem() is self.extras.container(category):
                return category
        raise AssertionError(f'{type(item).__name__} is not a registered canvas extra')

    def test_markers_registered_by_category(self) -> None:
        """Each of the viewer's markers is registered under its category, and the pixel outline under none."""
        viewer = self.viewer
        expected = {
            CanvasExtraCategory.SELECTION: [viewer._selection_poly_outline],
            CanvasExtraCategory.CANVAS: [viewer._image_outline, viewer._image_border, viewer._active_layer_outline],
            CanvasExtraCategory.GENERATION_AREA: [viewer._generation_area_outline,
                                                  viewer._generation_area_selection_outline,
                                                  viewer._generation_area_border, viewer.manual_resolution_label,
                                                  *viewer._context_pin_items],
        }
        for category, items in expected.items():
            for item in items:
                with self.subTest(item=type(item).__name__, category=category):
                    self.assertEqual(self._category_of(item), category)
        self.assertIsNone(viewer._pixel_outline.parentItem())

    def test_replaced_context_pins_leave_container(self) -> None:
        """Replacing the context pins leaves only the new pin markers in the generation area category."""
        self.image_stack.selection_layer.set_context_pins([QPoint(10, 10), QPoint(20, 20)])
        container = self.extras.container(CanvasExtraCategory.GENERATION_AREA)
        pins = [child for child in container.childItems() if isinstance(child, ContextPinItem)]
        self.assertCountEqual(pins, self.viewer._context_pin_items)
        self.assertEqual(len(pins), 2)

    def test_stacking_order(self) -> None:
        """Markers draw above the layers, in the order the viewer has always drawn them."""
        viewer = self.viewer
        self.viewer.set_viewport_highlight(QRectF(0, 0, 32, 32))
        scene = viewer.scene()
        assert scene is not None
        bottom_to_top = scene.items(Qt.SortOrder.AscendingOrder)
        layer_stack_item = viewer._layer_items[self.image_stack.layer_stack.id]
        expected_order = [layer_stack_item, viewer._image_outline, viewer._image_border,
                          viewer._active_layer_outline, viewer._pixel_outline, viewer._viewport_highlight,
                          viewer._selection_poly_outline, viewer.manual_resolution_label,
                          viewer._generation_area_outline, viewer._context_pin_items[0]]
        indices = [bottom_to_top.index(item) for item in expected_order]
        self.assertEqual(indices, sorted(indices))

    def test_generation_area_stays_enabled_while_hidden(self) -> None:
        """Hiding the generation area category leaves the generation area enabled, so following it keeps working."""
        self.viewer.follow_generation_area = True
        self.extras.set_shown(CanvasExtraCategory.GENERATION_AREA, False)
        self.assertFalse(self.viewer._generation_area_outline.isVisible())
        self.assertTrue(self.viewer.follow_generation_area)
        self.viewer.set_generation_area_visible(False)
        self.assertFalse(self.viewer.follow_generation_area)

    def test_hidden_outline_stops_animating(self) -> None:
        """An animated outline stops its animation timer while its category is hidden, and resumes when shown."""
        outline = self.viewer._generation_area_outline
        outline.animated = True
        self.assertTrue(outline._animation_timer.isActive())
        self.extras.set_shown(CanvasExtraCategory.GENERATION_AREA, False)
        self.assertFalse(outline._animation_timer.isActive())
        self.extras.set_shown(CanvasExtraCategory.GENERATION_AREA, True)
        self.assertTrue(outline._animation_timer.isActive())


class ToolCanvasExtrasTest(ToolTestCase):
    """Tests that tools register the markers they create as tool extras, above every other category."""

    def test_tool_markers_registered(self) -> None:
        """Tool-created handles and outlines are registered in the tool category."""
        tool_container = self.image_viewer.canvas_extras.container(CanvasExtraCategory.TOOL)
        generation_area_tool = GenerationAreaTool(self.image_stack, self.image_viewer)
        transform_tool = LayerTransformTool(self.image_stack, self.image_viewer)
        text_tool = TextTool(self.image_stack, self.image_viewer)
        free_selection_tool = FreeSelectionTool(self.image_stack, self.image_viewer)
        items = [*generation_area_tool._handles.values(), transform_tool._transform_outline,
                 text_tool._placement_outline, free_selection_tool._path_item, free_selection_tool._preview_line]
        for item in items:
            with self.subTest(item=type(item).__name__):
                self.assertIs(item.parentItem(), tool_container)

    def test_tool_category_above_other_categories(self) -> None:
        """The tool category draws above every other category."""
        extras = self.image_viewer.canvas_extras
        tool_z = extras.container(CanvasExtraCategory.TOOL).zValue()
        for category in CanvasExtraCategory:
            if category != CanvasExtraCategory.TOOL:
                with self.subTest(category=category):
                    self.assertLess(extras.container(category).zValue(), tool_z)
