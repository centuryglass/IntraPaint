"""Tests LayerPanel, its selected-layer header and its layer rows against changes to the layer stack.

Each structural test checks every row with `assert_panel_matches_stack`: one row per layer, in stack order, indented
by depth, shown only under expanded groups, and laid out without overlap or squeezing.
"""
import re
import sys
from typing import Callable
from unittest.mock import patch

from PySide6 import QtTest
from PySide6.QtCore import QSize, QEvent, Qt, QPoint, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QApplication, QComboBox, QMenu, QPushButton, QToolButton, QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.image.composite_mode import CompositeMode
from src.image.layers.image_layer import ImageLayer
from src.image.layers.image_stack import ImageStack
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.image.layers.text_layer import TextLayer
from src.ui.layout.panel_fit import Orientation
from src.ui.panel.layer_ui.blend_mode_combo_box import COMPOSITING_HEADING, COMPOSITING_MODES, MODE_FAMILIES
from src.ui.panel.layer_ui.layer_flags import ALPHA_LOCK_FLAG, ISOLATE_FLAG, LOCK_FLAG, LayerFlag, LayerFlagButton
from src.ui.panel.layer_ui.layer_list import DROP_ABOVE_LABEL, DROP_BELOW_LABEL, DROP_INTO_LABEL, LayerList
from src.ui.panel.layer_ui.layer_menu import MENU_OPTION_MOVE_UP, MENU_OPTION_MOVE_DOWN, MENU_OPTION_DELETE, \
    MENU_OPTION_MERGE_DOWN, MENU_OPTION_RENAME, MENU_OPTION_CROP_TO_SELECTION, MENU_OPTION_MIRROR_HORIZONTAL, \
    MENU_OPTION_MIRROR_VERTICAL, MENU_OPTION_DUPLICATE, MENU_OPTION_MOVE_TO_TOP, MENU_OPTION_MERGE_GROUP, \
    MENU_OPTION_MERGE_ALL_VISIBLE, MENU_OPTION_FLATTEN, MENU_OPTION_CLEAR_SELECTED, MENU_OPTION_COPY_SELECTED, \
    MENU_OPTION_SELECT_CONTENT, MENU_OPTION_LAYER_TO_IMAGE_SIZE, MENU_OPTION_CROP_TO_CONTENT, \
    MENU_OPTION_ROTATE_CW, MENU_OPTION_ROTATE_CCW, SUBMENU_CROP_AND_RESIZE, SUBMENU_MIRROR_AND_ROTATE
from src.ui.panel.layer_ui.layer_panel import LayerPanel, ADD_BUTTON_TITLE, MERGE_DOWN_BUTTON_TITLE, \
    DELETE_BUTTON_TITLE, DUPLICATE_BUTTON_TITLE, SELECT_NEXT_LABEL, SELECT_PREVIOUS_LABEL, SHOW_WINDOW_LABEL
from src.ui.panel.layer_ui.layer_row import (INDENT, LARGE_THUMBNAIL_SIZE, MEDIUM_THUMBNAIL_SIZE,
                                             SMALL_THUMBNAIL_SIZE, LayerRow, layer_meta_text, refused_drop_color,
                                             selection_stripe_color)
from src.ui.panel.layer_ui.layer_visibility_button import LayerVisibilityButton
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(64, 64)
PANEL_SIZE = QSize(400, 1200)


def flush_layouts() -> None:
    """Applies pending layout changes. This dispatches already-posted layout requests and never waits."""
    QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)


class _DragEvent:
    """Stands in for the drag move and drop events Qt sends while a row is dragged over the list."""

    def __init__(self, source: LayerRow, position: QPointF) -> None:
        self._source = source
        self._position = position

    def source(self) -> LayerRow:
        """Returns the dragged row."""
        return self._source

    def position(self) -> QPointF:
        """Returns the pointer position in the list's content."""
        return self._position

    def accept(self) -> None:
        """Accepts the event."""

    def ignore(self) -> None:
        """Ignores the event."""


def expected_rows(layer_list: LayerList, group: LayerGroup, depth: int, shown: bool) -> list[tuple[Layer, int, bool]]:
    """Returns the layers under a group in display order, with each one's depth and whether its row should show."""
    result: list[tuple[Layer, int, bool]] = []
    for child in group.child_layers:
        result.append((child, depth, shown))
        if isinstance(child, LayerGroup):
            result += expected_rows(layer_list, child, depth + 1, shown and layer_list.is_expanded(child))
    return result


class LayerPanelTest(IntraPaintTestCase):
    """Drives LayerPanel through layer stack changes, panel controls and row input."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE)
        root = self.image_stack.layer_stack
        # Layer order, top to bottom: group [inner_top, nested [nested_child], inner_bottom], bottom
        self.bottom = self.image_stack.create_layer('bottom', layer_parent=root, layer_index=0)
        self.group = self.image_stack.create_layer_group('group', layer_parent=root, layer_index=0)
        self.inner_bottom = self.image_stack.create_layer('inner_bottom', layer_parent=self.group, layer_index=0)
        self.nested = self.image_stack.create_layer_group('nested', layer_parent=self.group, layer_index=0)
        self.nested_child = self.image_stack.create_layer('nested_child', layer_parent=self.nested, layer_index=0)
        self.inner_top = self.image_stack.create_layer('inner_top', layer_parent=self.group, layer_index=0)
        self.image_stack.active_layer = self.bottom
        UndoStack().clear()
        self.panel = LayerPanel(self.image_stack)
        self.panel.resize(PANEL_SIZE)
        self.panel.show()
        flush_layouts()

    def tearDown(self) -> None:
        self.panel.close()
        super().tearDown()

    def row(self, layer: Layer) -> LayerRow:
        """Returns the row showing a layer."""
        return self.panel.layer_list.row_for(layer)

    def assert_panel_matches_stack(self) -> None:
        """Checks every row against the layer stack, after applying pending layout changes."""
        flush_layouts()
        layer_list = self.panel.layer_list
        expected = expected_rows(layer_list, self.image_stack.layer_stack, 0, True)
        rows = layer_list.rows
        self.assertEqual([layer.name for layer, _, _ in expected], [row.layer.name for row in rows], 'row order')
        # Rows of removed layers are hidden until their deferred deletion:
        for row in layer_list.findChildren(LayerRow):
            if row not in rows:
                self.assertTrue(row.isHidden(), f'{row.layer.name}: removed row shown')
        last_bottom = layer_list.image_strip.geometry().bottom()
        for (layer, depth, shown), row in zip(expected, rows):
            self.assertIs(row.layer, layer)
            self.assertEqual(row.depth, depth, f'{layer.name}: depth')
            self.assertEqual(row.isVisible(), shown, f'{layer.name}: visibility')
            if shown:
                self.assertGreater(row.y(), last_bottom, f'{layer.name}: overlaps the row above it')
                self.assertGreaterEqual(row.height(), row.minimumSizeHint().height(), f'{layer.name}: height')
                last_bottom = row.geometry().bottom()

    def assert_change_tracked_with_undo(self, change: Callable[[], None]) -> None:
        """Checks the panel after a change, its undo, and its redo."""
        change()
        self.assert_panel_matches_stack()
        UndoStack().undo()
        self.assert_panel_matches_stack()
        UndoStack().redo()
        self.assert_panel_matches_stack()

    # Action bar:

    def test_button_tooltips_show_key_bindings(self) -> None:
        """Each layer button's tooltip has a title, a description and a keycap for each key of its binding."""
        for button, key, title in ((self.panel._add_button, KeyConfig.NEW_LAYER_SHORTCUT, ADD_BUTTON_TITLE),
                                   (self.panel._merge_down_button, KeyConfig.MERGE_LAYER_DOWN_SHORTCUT,
                                    MERGE_DOWN_BUTTON_TITLE),
                                   (self.panel._delete_button, KeyConfig.DELETE_LAYER_SHORTCUT,
                                    DELETE_BUTTON_TITLE)):
            tooltip = button.toolTip()
            key_count = len(re.split(r'\+(?=.)', KeyConfig().get(key)))
            self.assertIn(f'<b>{title}</b>', tooltip)
            self.assertEqual(tooltip.count('<img'), key_count, tooltip)

    def test_delete_button_is_right_of_the_other_buttons(self) -> None:
        """The delete button sits alone at the bar's right end, with the other buttons clustered at the left."""
        panel = self.panel
        others = (panel._add_button, panel._add_group_button, panel._move_up_button, panel._move_down_button,
                  panel._merge_down_button)
        lefts = [button.geometry().left() for button in others]
        self.assertEqual(sorted(lefts), lefts, 'buttons are in order')
        cluster_right = others[-1].geometry().right()
        delete_geometry = panel._delete_button.geometry()
        self.assertGreater(delete_geometry.left(), cluster_right + 20)
        self.assertEqual(panel._button_bar.width(), delete_geometry.right() + 1)

    # Rows and the layer stack:

    def test_initial_tree_matches_stack(self) -> None:
        """The panel starts with a row for every layer, in stack order and indented by depth."""
        self.assert_panel_matches_stack()

    def test_add_layers_tracked_with_undo(self) -> None:
        """New layers and groups appear at their index in their group, including mid-group inserts."""
        self.assert_change_tracked_with_undo(lambda: self.image_stack.create_layer('new', layer_parent=self.group,
                                                                                   layer_index=1))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.create_layer_group('new_group',
                                                                                         layer_parent=self.nested,
                                                                                         layer_index=0))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.create_layer('new_top'))

    def test_remove_layers_tracked_with_undo(self) -> None:
        """Removed layers and groups disappear, and undo restores them in place."""
        self.assert_change_tracked_with_undo(lambda: self.image_stack.remove_layer(self.inner_top))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.remove_layer(self.nested))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.remove_layer(self.group))

    def test_removing_groups_logs_no_warnings(self) -> None:
        """Removing a group also signals the removal of its children, which the panel expects."""
        with self.assertNoLogs('src.ui.panel.layer_ui', level='WARNING'):
            self.image_stack.remove_layer(self.group)
            UndoStack().undo()

    def test_move_layers_tracked_with_undo(self) -> None:
        """Layers moved within, into and out of groups move to the matching row."""
        root = self.image_stack.layer_stack
        self.assert_change_tracked_with_undo(lambda: self.image_stack.move_layer(self.inner_top, self.group, 2))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.move_layer(self.bottom, self.nested, 0))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.move_layer(self.nested_child, root, 0))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.move_layer(self.nested, root, 2))

    def test_move_by_offset_through_nested_groups(self) -> None:
        """Moving a layer up one step at a time passes it into and out of each group without breaking the list."""
        self.image_stack.create_layer_group('empty', layer_parent=self.nested, layer_index=1)
        root = self.image_stack.layer_stack
        move_count = 0
        while root.get_layer_index(self.bottom) != 0:
            self.image_stack.move_layer_by_offset(-1, self.bottom)
            move_count += 1
            self.assertLess(move_count, 20)
            self.assert_panel_matches_stack()
        for _ in range(move_count):
            UndoStack().undo()
            self.assert_panel_matches_stack()
        self.assertEqual(root.get_layer_index(self.bottom), 1)

    def test_move_into_last_nested_group(self) -> None:
        """Moving a layer into a nested group at the end of its parent group indents it under both."""
        self.image_stack.move_layer(self.inner_bottom, self.image_stack.layer_stack, 0)
        self.assert_panel_matches_stack()
        self.image_stack.move_layer_by_offset(-1, self.bottom)
        self.assert_panel_matches_stack()
        self.image_stack.move_layer_by_offset(-1, self.bottom)
        self.assertEqual(self.bottom.layer_parent, self.nested)
        self.assertEqual(self.row(self.bottom).depth, 2)
        self.assert_panel_matches_stack()

    def test_merge_and_flatten_tracked_with_undo(self) -> None:
        """Merging or flattening a group replaces its row, and undo brings back the group's children."""
        self.assert_change_tracked_with_undo(lambda: self.image_stack.merge_group(self.nested))
        self.assert_change_tracked_with_undo(lambda: self.image_stack.flatten_layer(self.group))
        self.assert_change_tracked_with_undo(self.image_stack.merge_all_visible)

    # Groups:

    def test_collapse_and_expand_nested_groups(self) -> None:
        """Collapsing a group hides all its descendants, and expanding it restores each nested group's own state."""
        layer_list = self.panel.layer_list
        layer_list.set_expanded(self.nested, False)
        self.assert_panel_matches_stack()
        layer_list.set_expanded(self.group, False)
        self.assert_panel_matches_stack()
        self.assertFalse(self.row(self.inner_top).isVisible())
        layer_list.set_expanded(self.group, True)
        self.assert_panel_matches_stack()
        self.assertFalse(layer_list.is_expanded(self.nested))
        self.assertFalse(self.row(self.nested_child).isVisible())

    def test_collapsed_group_moves_rows_up(self) -> None:
        """Collapsing a group moves the rows below it up to just under the group's row, and expanding moves them back."""
        expanded_y = self.row(self.bottom).y()
        self.panel.layer_list.set_expanded(self.group, False)
        flush_layouts()
        self.assertEqual(self.row(self.bottom).y(), self.row(self.group).geometry().bottom() + 1)
        self.panel.layer_list.set_expanded(self.group, True)
        flush_layouts()
        self.assertEqual(self.row(self.bottom).y(), expanded_y)

    def test_disclosure_button_collapses_group(self) -> None:
        """The group's triangle collapses and expands it, and only group rows have one."""
        button = self.row(self.group).disclosure_button
        assert button is not None
        button.click()
        self.assertFalse(self.panel.layer_list.is_expanded(self.group))
        self.assert_panel_matches_stack()
        button.click()
        self.assertTrue(self.panel.layer_list.is_expanded(self.group))
        self.assert_panel_matches_stack()
        self.assertIsNone(self.row(self.bottom).disclosure_button)

    def test_adding_to_collapsed_group(self) -> None:
        """Adding a layer to a collapsed group expands the groups above it, so the new layer is shown."""
        self.panel.layer_list.set_expanded(self.nested, False)
        self.panel.layer_list.set_expanded(self.group, False)
        new_layer = self.image_stack.create_layer('new', layer_parent=self.nested, layer_index=0)
        self.assert_panel_matches_stack()
        self.assertTrue(self.row(new_layer).isVisible())

    def test_locking_group_collapses_it(self) -> None:
        """Locking a group collapses it and its nested groups."""
        self.group.locked = True
        self.assertFalse(self.panel.layer_list.is_expanded(self.group))
        self.assertFalse(self.panel.layer_list.is_expanded(self.nested))
        self.assert_panel_matches_stack()

    # Row anatomy:

    def test_eye_column_is_the_same_for_every_type(self) -> None:
        """Every row's eye, and the image strip's, sits at the same x, whatever the layer's type or depth."""
        self.image_stack.create_text_layer(layer_parent=self.nested, layer_index=0)
        flush_layouts()
        rows = self.panel.layer_list.rows
        self.assertTrue(any(isinstance(row.layer, TextLayer) for row in rows))
        eye_xs = {row.eye_button.mapTo(self.panel, QPoint()).x() for row in rows}
        eye_xs.add(self.panel.layer_list.image_strip.eye_button.mapTo(self.panel, QPoint()).x())
        self.assertEqual(len(eye_xs), 1, eye_xs)

    def test_thumbnails_indent_by_depth(self) -> None:
        """Each level of nesting moves a row's thumbnail right by one indent step, and draws one guide line."""
        flush_layouts()
        for layer in (self.bottom, self.group, self.inner_top, self.nested, self.nested_child):
            row = self.row(layer)
            x = row.thumbnail.mapTo(self.panel, QPoint()).x()
            self.assertEqual(x - self.row(self.bottom).thumbnail.mapTo(self.panel, QPoint()).x(), row.depth * INDENT,
                             layer.name)
            self.assertEqual(len(row.guide_line_xs()), row.depth, layer.name)

    def test_state_icons_show_only_when_on(self) -> None:
        """A row's state icons are drawn only while their flag is on, or as slots while the row is hovered."""
        row = self.row(self.inner_top)
        icons = {icon.flag: icon for icon in row.state_icons}
        self.assertEqual(set(icons), {LOCK_FLAG, ALPHA_LOCK_FLAG})
        self.assertEqual(set(icon.flag for icon in self.row(self.nested).state_icons), {LOCK_FLAG, ISOLATE_FLAG})
        self.assertFalse(any(icon.is_on or icon.slot_shown for icon in icons.values()))
        self.inner_top.alpha_locked = True
        self.assertTrue(icons[ALPHA_LOCK_FLAG].is_on)
        self.assertFalse(icons[LOCK_FLAG].is_on)
        QApplication.sendEvent(row, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
        self.assertTrue(icons[LOCK_FLAG].slot_shown)
        QApplication.sendEvent(row, QEvent(QEvent.Type.Leave))
        self.assertFalse(icons[LOCK_FLAG].slot_shown)

    def test_state_icons_toggle_from_the_row(self) -> None:
        """Clicking an on icon turns its flag off, and clicking a hovered slot turns it on."""
        row = self.row(self.inner_top)
        lock_icon = next(icon for icon in row.state_icons if icon.flag is LOCK_FLAG)
        lock_icon.click()
        self.assertFalse(self.inner_top.locked, 'an unhovered, hidden slot does nothing')
        QApplication.sendEvent(row, QEnterEvent(QPointF(5, 5), QPointF(5, 5), QPointF(5, 5)))
        lock_icon.click()
        self.assertTrue(self.inner_top.locked)
        QApplication.sendEvent(row, QEvent(QEvent.Type.Leave))
        lock_icon.click()
        self.assertFalse(self.inner_top.locked)
        UndoStack().undo()
        self.assertTrue(self.inner_top.locked)

    def test_name_is_left_aligned_and_ellipsized(self) -> None:
        """A long name ends in an ellipsis with the full name as the tooltip, and the row stays within the panel."""
        long_name = 'a layer with a name far too long to fit in any reasonable layer panel row at all'
        self.inner_top.name = long_name
        self.panel.resize(QSize(240, 600))
        flush_layouts()
        label = self.row(self.inner_top).name_label
        self.assertEqual(label.text(), long_name)
        self.assertNotEqual(label.shown_text(), long_name)
        self.assertTrue(label.shown_text().endswith('…'), label.shown_text())
        self.assertLessEqual(self.row(self.inner_top).geometry().right(), self.panel.width())

    def test_meta_line(self) -> None:
        """The meta line shows opacity below 100%, a mode other than Normal and a group's layer count."""
        self.assertEqual(layer_meta_text(self.bottom), '')
        self.bottom.opacity = 0.6
        self.bottom.composition_mode = CompositeMode.MULTIPLY
        self.assertEqual(self.row(self.bottom).meta_label.full_text, '60% · Multiply')
        self.assertEqual(self.row(self.group).meta_label.full_text, '3 layers')
        self.image_stack.remove_layer(self.inner_top)
        self.assertEqual(self.row(self.group).meta_label.full_text, '2 layers')
        self.assertEqual(self.row(self.nested).meta_label.full_text, '1 layer')

    def test_rows_keep_one_height(self) -> None:
        """Every row is as tall as every other, with or without meta text, so selection never shifts the list."""
        self.bottom.opacity = 0.5
        flush_layouts()
        self.assertEqual(len({row.height() for row in self.panel.layer_list.rows}), 1)

    # Image strip:

    def test_image_strip_replaces_root_row(self) -> None:
        """The root has no row: the image strip shows its eye, name and canvas size, and top-level rows aren't
        indented under it."""
        layer_list = self.panel.layer_list
        with self.assertRaises(KeyError):
            layer_list.row_for(self.image_stack.layer_stack)
        strip = layer_list.image_strip
        self.assertEqual(strip.size_text, '64 x 64')
        self.assertEqual(strip.name_label.text(), self.image_stack.layer_stack.name)
        self.assertEqual(self.row(self.group).depth, 0)

    def test_image_strip_selects_root(self) -> None:
        """Clicking the image strip makes the root active and highlights the strip."""
        strip = self.panel.layer_list.image_strip
        QtTest.QTest.mouseClick(strip, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(60, 5))
        self.assertIs(self.image_stack.active_layer, self.image_stack.layer_stack)
        self.assertTrue(strip.active)
        self.assertFalse(any(row.active for row in self.panel.layer_list.rows))

    def test_image_strip_eye_hides_everything(self) -> None:
        """The strip's eye toggles the root's visibility."""
        eye = self.panel.layer_list.image_strip.eye_button
        QtTest.QTest.mouseClick(eye, Qt.MouseButton.LeftButton)
        self.assertFalse(self.image_stack.layer_stack.visible)
        UndoStack().undo()
        self.assertTrue(self.image_stack.layer_stack.visible)

    def test_image_strip_menu(self) -> None:
        """The strip's menu holds rename, crop to selection and mirror."""
        menu = self.panel.layer_list.image_strip.build_menu()
        self.assertEqual([action.text() for action in menu.actions()],
                         [MENU_OPTION_RENAME, MENU_OPTION_CROP_TO_SELECTION, MENU_OPTION_MIRROR_HORIZONTAL,
                          MENU_OPTION_MIRROR_VERTICAL])

    def test_image_strip_canvas_size_follows_image(self) -> None:
        """The strip's size text follows canvas resizes."""
        self.image_stack.resize_canvas(QSize(80, 48), 0, 0)
        self.assertEqual(self.panel.layer_list.image_strip.size_text, '80 x 48')

    # Active layer:

    def test_active_layer_highlighted(self) -> None:
        """Exactly one row or the strip is highlighted, including when the active layer is nested."""
        for layer in (self.nested_child, self.group, self.image_stack.layer_stack, self.inner_bottom, self.bottom):
            self.image_stack.active_layer = layer
            self.assertEqual(self.panel.layer_list.image_strip.active, layer is self.image_stack.layer_stack)
            for row in self.panel.layer_list.rows:
                self.assertEqual(row.active, row.layer is layer, f'{row.layer.name} with {layer.name} active')

    def test_new_row_for_active_layer_is_highlighted(self) -> None:
        """A row created for the active layer starts highlighted, as when undo restores a deleted group."""
        self.image_stack.active_layer = self.nested_child
        self.image_stack.remove_layer(self.group)
        UndoStack().undo()
        self.assertEqual(self.image_stack.active_layer, self.nested_child)
        self.assertTrue(self.row(self.nested_child).active)

    def test_activation_keeps_row_size(self) -> None:
        """Highlighting a row doesn't change its size, so the list doesn't shift on click."""
        flush_layouts()
        row = self.row(self.inner_top)
        inactive_size = row.size()
        self.image_stack.active_layer = self.inner_top
        flush_layouts()
        self.assertEqual(row.size(), inactive_size)
        self.image_stack.active_layer = self.bottom
        flush_layouts()
        self.assertEqual(row.size(), inactive_size)

    def test_click_activates_layer(self) -> None:
        """Clicking a row makes its layer active."""
        row = self.row(self.nested_child)
        point = row.thumbnail.geometry().center()
        QtTest.QTest.mouseClick(row, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
        self.assertEqual(self.image_stack.active_layer, self.nested_child)
        self.assertTrue(row.active)

    def test_activating_layer_expands_parent_groups(self) -> None:
        """Activating a layer in a collapsed group expands every group above it."""
        self.panel.layer_list.set_expanded(self.nested, False)
        self.panel.layer_list.set_expanded(self.group, False)
        self.image_stack.active_layer = self.nested_child
        self.assertTrue(self.panel.layer_list.is_expanded(self.group))
        self.assertTrue(self.panel.layer_list.is_expanded(self.nested))
        self.assert_panel_matches_stack()

    def test_nested_selection_updates_rows_and_header(self) -> None:
        """Selecting nested layers in turn, from the stack or by clicking rows, moves the highlight and the header
        with it (issue #18)."""
        properties = self.panel.properties
        for layer in (self.nested_child, self.nested, self.inner_top, self.nested_child, self.bottom):
            row = self.row(layer)
            QtTest.QTest.mouseClick(row, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                                    row.thumbnail.geometry().center())
            self.assertIs(self.image_stack.active_layer, layer)
            self.assertEqual([row.layer for row in self.panel.layer_list.rows if row.active], [layer])
            self.assertIs(properties.layer, layer)
            self.assertEqual(properties.name_text, layer.name)
            self.assertIs(properties.thumbnail.layer, layer)
        self.image_stack.active_layer = self.nested_child
        self.nested_child.name = 'renamed'
        self.assertEqual(properties.name_text, 'renamed')

    # Selected-layer header:

    def test_opacity_field(self) -> None:
        """The opacity field sets the active layer's opacity in percent."""
        field = self.panel.properties.opacity_field
        self.assertEqual(field.value(), 100)
        self.assertEqual(field.value_text(), '100%')
        field.set_value(40)
        self.assertAlmostEqual(self.bottom.opacity, 0.4)

    def test_opacity_drag_is_one_undo_step(self) -> None:
        """Every change during one drag of the opacity field undoes together."""
        field = self.panel.properties.opacity_field
        field.dragStarted.emit()
        for value in (90, 70, 50):
            field.set_value(value)
        field.dragFinished.emit()
        self.assertAlmostEqual(self.bottom.opacity, 0.5)
        UndoStack().undo()
        self.assertEqual(self.bottom.opacity, 1.0)

    def test_opacity_field_follows_layer(self) -> None:
        """Opacity changes from outside the panel, such as undo, update the field."""
        self.bottom.opacity = 0.5
        self.assertEqual(self.panel.properties.opacity_field.value(), 50)
        UndoStack().undo()
        self.assertEqual(self.bottom.opacity, 1.0)
        self.assertEqual(self.panel.properties.opacity_field.value(), 100)

    def test_opacity_field_shows_active_layer(self) -> None:
        """Switching the active layer shows its opacity, without changing either layer."""
        self.inner_top.opacity = 0.25
        self.image_stack.active_layer = self.inner_top
        self.assertEqual(self.panel.properties.opacity_field.value(), 25)
        self.assertEqual(self.bottom.opacity, 1.0)
        self.assertEqual(self.inner_top.opacity, 0.25)

    def test_mode_controls(self) -> None:
        """The mode box sets the active layer's composition mode, and follows changes from outside the panel."""
        mode_box = self.panel.properties.mode_box
        mode_box.setCurrentIndex(mode_box.findText(CompositeMode.MULTIPLY))
        self.assertEqual(self.bottom.composition_mode, CompositeMode.MULTIPLY)
        UndoStack().undo()
        self.assertEqual(self.bottom.composition_mode, CompositeMode.NORMAL)
        self.assertEqual(mode_box.currentText(), CompositeMode.NORMAL)
        self.inner_top.composition_mode = CompositeMode.SCREEN
        self.image_stack.active_layer = self.inner_top
        self.assertEqual(mode_box.currentText(), CompositeMode.SCREEN)

    def test_mode_box_groups_families(self) -> None:
        """The mode box lists the same 20 modes in families split by separators, with the Porter-Duff modes last
        under their heading. Only modes can be chosen."""
        mode_box = self.panel.properties.mode_box
        modes = [mode_box.itemData(index) for index in range(mode_box.count())
                 if mode_box.itemData(index) is not None]
        self.assertEqual(sorted(modes), sorted(CompositeMode))
        families = [list(family) for family in MODE_FAMILIES] + [list(COMPOSITING_MODES)]
        self.assertEqual(modes, [mode for family in families for mode in family])
        model = mode_box.model()
        heading = mode_box.findText(COMPOSITING_HEADING)
        self.assertGreater(heading, 0)
        self.assertEqual(mode_box.itemData(heading + 1), COMPOSITING_MODES[0])
        for index in range(mode_box.count()):
            enabled = bool(model.flags(model.index(index, 0)) & Qt.ItemFlag.ItemIsEnabled)
            self.assertEqual(enabled, mode_box.itemData(index) is not None, mode_box.itemText(index))

    def test_mode_hover_previews_without_undo(self) -> None:
        """Highlighting a mode in the open popup shows it on the layer without an undo step, and closing the popup
        restores the layer's mode."""
        properties = self.panel.properties
        mode_box = properties.mode_box
        mode_box._popup_open = True
        mode_box.highlighted.emit(mode_box.findData(CompositeMode.SCREEN))
        self.assertEqual(self.bottom.composition_mode, CompositeMode.SCREEN)
        self.assertEqual(mode_box.mode(), CompositeMode.NORMAL)
        mode_box.highlighted.emit(mode_box.findData(CompositeMode.DIFFERENCE))
        self.assertEqual(self.bottom.composition_mode, CompositeMode.DIFFERENCE)
        mode_box.end_preview()
        self.assertEqual(self.bottom.composition_mode, CompositeMode.NORMAL)
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_mode_choice_after_preview_is_one_undo_step(self) -> None:
        """Choosing a mode while previewing applies it once, as a normal undoable change, in either signal order."""
        mode_box = self.panel.properties.mode_box
        for end_first in (False, True):
            mode_box._popup_open = True
            mode_box.highlighted.emit(mode_box.findData(CompositeMode.SCREEN))
            if end_first:
                mode_box.end_preview()
            mode_box.setCurrentIndex(mode_box.findData(CompositeMode.MULTIPLY))
            mode_box.end_preview()
            self.assertEqual(self.bottom.composition_mode, CompositeMode.MULTIPLY)
            self.assertEqual(UndoStack().undo_count(), 1)
            UndoStack().undo()
            self.assertEqual(self.bottom.composition_mode, CompositeMode.NORMAL)
            self.assertEqual(mode_box.mode(), CompositeMode.NORMAL)
            UndoStack().clear()

    def test_header_flags_follow_layer_type(self) -> None:
        """The header shows lock and alpha lock for image layers, lock and isolate for groups, and no toggle for the
        root."""
        def shown_flags() -> set[LayerFlag]:
            return {button.flag for button in self.panel.properties.flag_buttons if not button.isHidden()}
        self.assertEqual(shown_flags(), {LOCK_FLAG, ALPHA_LOCK_FLAG})
        self.image_stack.active_layer = self.nested
        self.assertEqual(shown_flags(), {LOCK_FLAG, ISOLATE_FLAG})
        self.image_stack.active_layer = self.image_stack.layer_stack
        self.assertEqual(shown_flags(), set())

    def _flag_button(self, flag: LayerFlag) -> LayerFlagButton:
        return next(button for button in self.panel.properties.flag_buttons if button.flag is flag)

    def test_header_flag_buttons_toggle_layer(self) -> None:
        """Each header toggle sets its flag on the active layer, and shows changes from outside it as checked."""
        for layer, flag, getter in ((self.inner_top, LOCK_FLAG, lambda: self.inner_top.locked),
                                    (self.inner_top, ALPHA_LOCK_FLAG, lambda: self.inner_top.alpha_locked),
                                    (self.nested, ISOLATE_FLAG, lambda: self.nested.isolate)):
            self.image_stack.active_layer = layer
            button = self._flag_button(flag)
            self.assertFalse(button.isChecked())
            button.click()
            self.assertTrue(getter(), flag.label)
            self.assertTrue(button.isChecked(), flag.label)
            UndoStack().undo()
            self.assertFalse(getter(), flag.label)
            self.assertFalse(button.isChecked(), flag.label)

    def test_lock_disables_alpha_lock_button(self) -> None:
        """A layer's own lock or a group lock disables its alpha lock toggles, until every lock is released."""
        self.image_stack.active_layer = self.nested_child
        button = self._flag_button(ALPHA_LOCK_FLAG)
        icon = next(icon for icon in self.row(self.nested_child).state_icons if icon.flag is ALPHA_LOCK_FLAG)
        self.nested_child.locked = True
        self.assertFalse(button.isEnabled())
        self.assertFalse(icon.isEnabled())
        self.group.locked = True
        self.nested_child.locked = False
        self.assertFalse(button.isEnabled())
        self.group.locked = False
        self.assertTrue(button.isEnabled())
        self.assertTrue(icon.isEnabled())

    def test_isolate_button_shows_forced_isolation(self) -> None:
        """Below full opacity or outside Normal mode, the isolate toggle shows checked and can't be toggled."""
        self.image_stack.active_layer = self.nested
        button = self._flag_button(ISOLATE_FLAG)
        icon = next(icon for icon in self.row(self.nested).state_icons if icon.flag is ISOLATE_FLAG)
        self.assertFalse(self.nested.isolate)
        for force, restore in ((lambda: self.nested.set_opacity(0.5), lambda: self.nested.set_opacity(1.0)),
                               (lambda: self.nested.set_composition_mode(CompositeMode.MULTIPLY),
                                lambda: self.nested.set_composition_mode(CompositeMode.NORMAL))):
            force()
            self.assertFalse(button.isEnabled())
            self.assertTrue(button.isChecked())
            self.assertTrue(icon.is_on)
            self.assertFalse(self.nested.isolate)
            restore()
            self.assertTrue(button.isEnabled())
            self.assertFalse(button.isChecked())
            self.assertFalse(icon.is_on)

    def test_locked_layer_disables_controls(self) -> None:
        """Locking the active layer or one of its groups disables the controls that would change it, and shows a
        banner naming the lock that offers to remove it."""
        properties = self.panel.properties
        controls: list[QWidget] = [properties.opacity_field, properties.mode_box, self.panel._delete_button,
                                   self.panel._merge_down_button]
        self.image_stack.active_layer = self.nested_child
        self.assertTrue(all(control.isEnabled() for control in controls))
        self.assertTrue(properties.banner.isHidden())
        self.nested_child.locked = True
        self.assertFalse(any(control.isEnabled() for control in controls))
        self.assertIn('"nested_child"', properties.banner.message())
        self.assertFalse(properties.banner.isHidden())
        self.assertTrue(self._flag_button(LOCK_FLAG).isEnabled())
        self.group.locked = True
        self.nested_child.locked = False
        self.assertFalse(any(control.isEnabled() for control in controls))
        self.assertIn('"group"', properties.banner.message())
        properties.banner.fix_button.click()
        self.assertFalse(self.group.locked)
        self.assertTrue(all(control.isEnabled() for control in controls))
        self.assertTrue(properties.banner.isHidden())

    def test_root_layer_controls(self) -> None:
        """The root group can't be moved, deleted or merged. Its mode and opacity both stay editable."""
        self.image_stack.active_layer = self.image_stack.layer_stack
        for control in (self.panel._delete_button, self.panel._merge_down_button, self.panel._move_up_button,
                        self.panel._move_down_button):
            self.assertFalse(control.isEnabled())
        self.assertTrue(self.panel.properties.opacity_field.isEnabled())
        self.assertTrue(self.panel.properties.mode_box.isEnabled())

    # Action bar buttons:

    def test_add_buttons(self) -> None:
        """The add buttons create a layer or group above the active layer."""
        self.image_stack.active_layer = self.inner_bottom
        self.panel._add_button.click()
        self.assertIsInstance(self.group.get_layer_by_index(2), ImageLayer)
        self.panel._add_group_button.click()
        self.assertIsInstance(self.group.get_layer_by_index(3), LayerGroup)
        self.assertEqual(self.group.get_layer_index(self.inner_bottom), 4)
        self.assert_panel_matches_stack()

    def test_delete_button(self) -> None:
        """The delete button removes the active layer."""
        self.image_stack.active_layer = self.inner_top
        self.panel._delete_button.click()
        self.assertFalse(self.group.contains(self.inner_top))
        self.assert_panel_matches_stack()

    def test_move_buttons(self) -> None:
        """The move buttons move the active layer up or down by one step."""
        self.image_stack.active_layer = self.inner_bottom
        self.panel._move_up_button.click()
        self.assertEqual(self.nested.get_layer_index(self.inner_bottom), 1)
        self.panel._move_down_button.click()
        self.panel._move_down_button.click()
        self.assertEqual(self.image_stack.layer_stack.get_layer_index(self.inner_bottom), 1)
        self.assert_panel_matches_stack()

    def test_merge_down_button(self) -> None:
        """The merge button merges the active layer into the layer below it."""
        upper = self.image_stack.create_layer('upper', layer_parent=self.image_stack.layer_stack, layer_index=1)
        self.image_stack.active_layer = upper
        self.panel._merge_down_button.click()
        self.assertFalse(self.image_stack.layer_stack.contains(upper))
        self.assertEqual(self.image_stack.layer_stack.count, 2)
        self.assert_panel_matches_stack()

    def test_header_counts_layers(self) -> None:
        """The panel header counts every layer under the root."""
        self.assertEqual(self.panel.header.description(), '6 layers')
        self.image_stack.remove_layer(self.group)
        self.assertEqual(self.panel.header.description(), '1 layer')

    # Eye buttons:

    def test_locked_layer_visibility_button_works(self) -> None:
        """Locking a layer or its group doesn't block its eye."""
        button = self.row(self.nested_child).eye_button
        self.assertTrue(button.isEnabled())
        self.nested_child.locked = True
        self.assertTrue(button.isEnabled())
        QtTest.QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertFalse(self.nested_child.visible)
        UndoStack().undo()
        self.assertTrue(self.nested_child.visible)
        self.group.locked = True
        QtTest.QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertFalse(self.nested_child.visible)
        UndoStack().undo()
        self.assertTrue(self.nested_child.visible)

    def test_visibility_button_in_hidden_group(self) -> None:
        """In a hidden group, a visible layer's eye shows the hidden-by-group icon and names the group. Clicking it
        toggles that layer alone."""
        button: LayerVisibilityButton = self.row(self.nested_child).eye_button
        visible_icon = button.icon().cacheKey()
        self.group.visible = False
        parent_hidden_icon = button.icon().cacheKey()
        self.assertNotEqual(parent_hidden_icon, visible_icon)
        self.assertIn('"group"', button.toolTip())
        QtTest.QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertEqual([self.nested_child.visible, self.group.visible, self.nested.visible, self.inner_top.visible],
                         [False, False, True, True])
        self.assertNotIn(button.icon().cacheKey(), (visible_icon, parent_hidden_icon))
        self.assertNotIn('"group"', button.toolTip())
        QtTest.QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        self.assertEqual([self.nested_child.visible, self.group.visible], [True, False])
        self.group.visible = True
        self.assertEqual(button.icon().cacheKey(), visible_icon)

    # Rename:

    def test_rename(self) -> None:
        """Editing a row's name renames the layer, and renaming the layer updates the row."""
        label = self.row(self.inner_top).name_label
        label.activate_input_mode()
        self.assertTrue(label.is_requesting_input())
        label._field.setText('renamed')
        label.apply_changes()
        self.assertEqual(self.inner_top.name, 'renamed')
        UndoStack().undo()
        self.assertEqual(label.text(), 'inner_top')

    def test_rename_escape_discards(self) -> None:
        """Escape ends editing and keeps the old name."""
        label = self.row(self.inner_top).name_label
        label.activate_input_mode()
        label._field.setText('renamed')
        QtTest.QTest.keyClick(label._field, Qt.Key.Key_Escape)
        self.assertFalse(label.is_requesting_input())
        self.assertEqual(self.inner_top.name, 'inner_top')

    def test_lock_blocks_rename(self) -> None:
        """A layer under a locked group can't be renamed, even after its own lock is released."""
        label = self.row(self.nested_child).name_label
        self.group.locked = True
        self.nested_child.locked = True
        self.nested_child.locked = False
        # Locking collapses the groups, and the label only enters input mode while shown:
        self.image_stack.active_layer = self.nested_child
        label.activate_input_mode()
        self.assertFalse(label.is_requesting_input())
        self.group.locked = False
        self.image_stack.active_layer = self.bottom
        self.image_stack.active_layer = self.nested_child
        label.activate_input_mode()
        self.assertTrue(label.is_requesting_input())

    # Context menu:

    def _menu_actions(self, layer: Layer) -> dict[str, bool]:
        """Returns the layer's context menu options, mapped to whether each is enabled."""
        menu = self.row(layer).build_menu()
        return {action.text(): action.isEnabled() for action in menu.actions()}

    def test_menu_move_options(self) -> None:
        """Move options are offered wherever a move would change something: anywhere but the ends of the stack."""
        top_actions = self._menu_actions(self.group)
        self.assertNotIn(MENU_OPTION_MOVE_UP, top_actions)
        self.assertIn(MENU_OPTION_MOVE_DOWN, top_actions)
        bottom_actions = self._menu_actions(self.bottom)
        self.assertIn(MENU_OPTION_MOVE_UP, bottom_actions)
        self.assertNotIn(MENU_OPTION_MOVE_DOWN, bottom_actions)
        for layer in (self.inner_top, self.inner_bottom, self.nested_child):
            actions = self._menu_actions(layer)
            self.assertIn(MENU_OPTION_MOVE_UP, actions, layer.name)
            self.assertIn(MENU_OPTION_MOVE_DOWN, actions, layer.name)

    def test_menu_merge_down_option(self) -> None:
        """Merge down is enabled only for a layer with an image layer below it."""
        self.assertTrue(self._menu_actions(self.inner_bottom)[MENU_OPTION_MERGE_DOWN])
        self.assertFalse(self._menu_actions(self.inner_top)[MENU_OPTION_MERGE_DOWN])
        self.assertFalse(self._menu_actions(self.bottom)[MENU_OPTION_MERGE_DOWN])

    def test_menu_locked_layer(self) -> None:
        """A locked layer's menu disables delete."""
        self.assertTrue(self._menu_actions(self.inner_top)[MENU_OPTION_DELETE])
        self.inner_top.locked = True
        self.assertFalse(self._menu_actions(self.inner_top)[MENU_OPTION_DELETE])

    # Fit forms:

    def test_side_panel_stacks_header_over_list(self) -> None:
        """A side panel puts the header above the list, and a strip puts it beside the list."""
        self.panel.plan_in(Orientation.SIDE, QSize(320, 600))
        flush_layouts()
        properties, layer_list = self.panel.properties, self.panel.layer_list
        self.assertLess(properties.geometry().bottom(), layer_list.y())
        # The strip is as large as the plan, since the labeled action bar is wider than the fixture's panel:
        self.panel.resize(900, 240)
        self.panel.plan_in(Orientation.STRIP, QSize(900, 240))
        flush_layouts()
        self.assertLess(properties.geometry().right(), layer_list.x())

    def test_large_form_where_it_fits(self) -> None:
        """A roomy panel labels the toggles and uses large thumbnails, and a narrow one drops both."""
        self.panel.plan_in(Orientation.SIDE, QSize(600, 900))
        flush_layouts()
        button = self._flag_button(LOCK_FLAG)
        self.assertEqual(button.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        large = self.row(self.bottom).thumbnail.width()
        self.panel.plan_in(Orientation.SIDE, QSize(170, 900))
        flush_layouts()
        self.assertEqual(button.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.assertLess(self.row(self.bottom).thumbnail.width(), large)

    def test_strip_columns_stay_at_the_left(self) -> None:
        """In a wide strip the header and the list sit side by side at the left edge, not spread across the width."""
        self.panel.resize(QSize(1600, 300))
        self.panel.plan_in(Orientation.STRIP, QSize(1600, 300))
        flush_layouts()
        properties, layer_list = self.panel.properties, self.panel.layer_list
        self.assertLess(properties.geometry().right(), layer_list.x())
        gap = layer_list.x() - properties.geometry().right()
        self.assertLessEqual(gap, 2 * self.panel.inset + 2)
        self.assertLess(layer_list.geometry().right(), self.panel.width() // 2)

    def test_mode_and_opacity_stack_before_the_mode_box_shrinks(self) -> None:
        """Mode and opacity share a row only while the mode box keeps room to read its name, and stack otherwise."""
        self.panel.plan_in(Orientation.SIDE, QSize(600, 900))
        flush_layouts()
        mode_box, opacity = self.panel.properties.mode_box, self.panel.properties.opacity_field
        self.assertEqual(mode_box.y(), opacity.y(), 'one row')
        min_width = mode_box.minimumSizeHint().width()
        for width in range(400, 150, -10):
            self.panel.plan_in(Orientation.SIDE, QSize(width, 900))
            flush_layouts()
            self.assertGreaterEqual(mode_box.width(), min_width, f'width {width}')

    def test_strip_leaves_room_to_read_layer_names(self) -> None:
        """A strip is only as narrow as the header and a list wide enough to read the start of a name, and a side
        panel's list has no such minimum."""
        layer_list = self.panel.layer_list
        self.panel.plan_in(Orientation.SIDE, QSize(600, 900))
        side_minimum = layer_list.minimumSizeHint().width()
        self.panel.plan_in(Orientation.STRIP, QSize(900, 300))
        self.assertGreater(layer_list.minimumSizeHint().width(), side_minimum)

    def test_smallest_panel_is_a_side_panel(self) -> None:
        """Shrunk to its minimum size, the panel is a side panel that scrolls down, not a strip scrolled past its layer
        list."""
        size = QSize(1, 1)
        for _ in range(4):
            self.panel.resize(size)
            flush_layouts()
            size = self.panel.minimumSizeHint().expandedTo(QSize(1, 1))
        self.assertEqual(self.panel.orientation, Orientation.SIDE)

    def test_list_minimum_covers_only_its_rows(self) -> None:
        """The list's minimum height leaves room for MIN_VISIBLE_ROWS rows, or every row if it has fewer, so a panel
        with one layer doesn't scroll while that layer fits."""
        layer_list = self.panel.layer_list
        self.assertLess(layer_list.minimumSizeHint().height(), layer_list.sizeHint().height())
        image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE)
        image_stack.create_layer()
        panel = LayerPanel(image_stack)
        panel.resize(QSize(270, 270))
        panel.show()
        flush_layouts()
        self.assertEqual(panel.layer_list.minimumSizeHint().height(), panel.layer_list.sizeHint().height())
        self.assertEqual(panel.orientation, Orientation.SIDE)
        self.assertFalse(panel.content_scrolls)
        panel.close()

    def test_floating_panel_leaves_its_header_to_the_title_bar(self) -> None:
        """A floating panel hides its header, whose name and layer count its title bar shows, and the title note
        follows the count."""
        header = self.panel.header
        self.assertEqual(self.panel.title_note, '6 layers')
        self.panel.host_floating_changed(True)
        flush_layouts()
        self.assertTrue(header.isHidden())
        self.image_stack.create_layer()
        self.assertEqual(self.panel.title_note, '7 layers')
        self.panel.host_floating_changed(False)
        flush_layouts()
        self.assertFalse(header.isHidden())
        self.assertEqual(header.description(), '7 layers')

    # Drag and drop:

    def _drop(self, moved_layer: Layer, target_layer: Layer, below: bool) -> None:
        """Drops a row onto the upper or lower half of another layer's row."""
        layer_list = self.panel.layer_list
        flush_layouts()
        target = self.row(target_layer)
        y_offset = target.height() * 3 // 4 if below else target.height() // 4
        event = _DragEvent(self.row(moved_layer), QPointF(target.width() / 2, target.y() + y_offset))
        layer_list.drag_move(event)
        layer_list.drop(event)

    def test_drop_into_nested_group(self) -> None:
        """Dropping a layer below a nested group's child moves it into that group."""
        self._drop(self.bottom, self.nested_child, below=True)
        self.assertEqual(self.nested.get_layer_index(self.bottom), 1)
        self.assert_panel_matches_stack()

    def test_drop_within_group(self) -> None:
        """Dropping a layer above a sibling moves it to the sibling's index."""
        self._drop(self.inner_bottom, self.inner_top, below=False)
        self.assertEqual(self.group.get_layer_index(self.inner_bottom), 0)
        self.assert_panel_matches_stack()

    def test_drop_below_expanded_group_enters_it(self) -> None:
        """Dropping on the lower half of an expanded group's row puts the layer at the top of the group."""
        self._drop(self.bottom, self.group, below=True)
        self.assertEqual(self.group.get_layer_index(self.bottom), 0)
        self.assert_panel_matches_stack()

    def test_drop_group_into_itself_ignored(self) -> None:
        """Dropping a group inside itself does nothing."""
        self._drop(self.group, self.nested_child, below=True)
        self.assertEqual(self.image_stack.layer_stack.get_layer_index(self.group), 0)
        self.assertEqual(UndoStack().undo_count(), 0)
        self.assert_panel_matches_stack()

    def test_drop_into_locked_group_ignored(self) -> None:
        """A locked group accepts no drops, and shows no insert marker."""
        self.nested.locked = True
        UndoStack().clear()
        self.panel.layer_list.set_expanded(self.nested, True)
        self._drop(self.bottom, self.nested_child, below=False)
        self.assertIs(self.bottom.layer_parent, self.image_stack.layer_stack)
        self.assertEqual(UndoStack().undo_count(), 0)

    def test_drop_marker_names_the_landing_spot(self) -> None:
        """The marker's label says whether the layer lands above, below or into the layer under the pointer."""
        layer_list = self.panel.layer_list
        flush_layouts()
        for target, below, expected in ((self.bottom, False, DROP_ABOVE_LABEL.format(name='bottom')),
                                        (self.inner_top, True, DROP_BELOW_LABEL.format(name='inner_top')),
                                        (self.group, True, DROP_INTO_LABEL.format(name='group'))):
            row = self.row(target)
            y_offset = row.height() * 3 // 4 if below else row.height() // 4
            layer_list.drag_move(_DragEvent(self.row(self.nested_child), QPointF(row.width() / 2, row.y() + y_offset)))
            self.assertEqual(layer_list.insert_marker_text, expected)
        layer_list.drag_move(_DragEvent(self.row(self.group), QPointF(5, 0)))
        self.assertEqual(layer_list.insert_marker_text, DROP_ABOVE_LABEL.format(name='group'))
        layer_list.drop(_DragEvent(self.row(self.group), QPointF(5, 0)))
        self.assertEqual(layer_list.insert_marker_text, '')

    def test_drop_into_group_outlines_its_rows(self) -> None:
        """A drop inside a group outlines the group's row and its visible rows in the selection stripe color, and the
        outline goes when the drag leaves."""
        layer_list = self.panel.layer_list
        layer_list.set_expanded(self.nested, False)
        flush_layouts()
        target = self.row(self.inner_top)
        layer_list.drag_move(_DragEvent(self.row(self.bottom), QPointF(5, target.y() + target.height() // 4)))
        stripe = selection_stripe_color(layer_list)
        outlined = {row.layer.name for row in layer_list.rows if row.drop_outline == stripe}
        self.assertEqual(outlined, {'group', 'inner_top', 'nested', 'inner_bottom'})
        layer_list.drag_move(_DragEvent(self.row(self.bottom), QPointF(5, self.row(self.bottom).y() + 1)))
        self.assertEqual([row for row in layer_list.rows if row.drop_outline is not None], [])

    def test_drop_into_locked_group_outlines_only_that_group(self) -> None:
        """A drop onto a locked group outlines its row in the refused-drop color, with no marker."""
        layer_list = self.panel.layer_list
        self.nested.locked = True
        layer_list.set_expanded(self.nested, True)
        flush_layouts()
        target = self.row(self.nested_child)
        layer_list.drag_move(_DragEvent(self.row(self.bottom), QPointF(5, target.y() + target.height() // 4)))
        outlined = {row.layer.name: row.drop_outline for row in layer_list.rows if row.drop_outline is not None}
        self.assertEqual(outlined, {'nested': refused_drop_color()})
        self.assertEqual(layer_list.insert_marker_text, '')

    # Right-click, menu groups and rename:

    def test_right_click_selects_the_row(self) -> None:
        """Right-pressing a row makes its layer active, so the menu acts on the active layer."""
        self.assertIs(self.image_stack.active_layer, self.bottom)
        strip = self.panel.layer_list.image_strip
        QtTest.QTest.mousePress(self.row(self.inner_top), Qt.MouseButton.RightButton)
        self.assertIs(self.image_stack.active_layer, self.inner_top)
        QtTest.QTest.mousePress(strip, Qt.MouseButton.RightButton)
        self.assertIs(self.image_stack.active_layer, self.image_stack.layer_stack)

    def test_menu_action_acts_on_the_clicked_layer(self) -> None:
        """After a right-press selects a row, choosing Duplicate from its menu duplicates that row's layer. The menu
        isn't opened, since `conftest.py` fails a test that opens one."""
        row = self.row(self.inner_top)
        QtTest.QTest.mousePress(row, Qt.MouseButton.RightButton)
        self.assertIs(self.image_stack.active_layer, self.inner_top)
        menu = row.build_menu()
        self.assertEqual(menu.title(), 'inner_top')
        next(action for action in menu.actions() if action.text() == MENU_OPTION_DUPLICATE).trigger()
        self.assertEqual(self.group.count, 4)
        self.assertEqual(self.group.get_layer_by_index(0).name, 'inner_top copy')

    def test_menu_groups_and_separators(self) -> None:
        """A layer's menu has its commands in groups: rename, move, duplicate, merge, selection, submenus, delete."""
        def _texts(menu: QMenu) -> list[str]:
            return ['-' if action.isSeparator() else action.text() for action in menu.actions()]

        menu = self.row(self.inner_top).build_menu()
        self.assertEqual(_texts(menu), [
            MENU_OPTION_RENAME, '-',
            MENU_OPTION_MOVE_UP, MENU_OPTION_MOVE_DOWN, MENU_OPTION_MOVE_TO_TOP, '-',
            MENU_OPTION_DUPLICATE, '-',
            MENU_OPTION_MERGE_DOWN, MENU_OPTION_MERGE_ALL_VISIBLE, MENU_OPTION_FLATTEN, '-',
            MENU_OPTION_CLEAR_SELECTED, MENU_OPTION_COPY_SELECTED, MENU_OPTION_SELECT_CONTENT, '-',
            SUBMENU_CROP_AND_RESIZE, SUBMENU_MIRROR_AND_ROTATE, '-',
            MENU_OPTION_DELETE])
        submenus = {action.text(): action.menu() for action in menu.actions() if action.menu() is not None}
        self.assertEqual(_texts(submenus[SUBMENU_CROP_AND_RESIZE]),
                         [MENU_OPTION_LAYER_TO_IMAGE_SIZE, MENU_OPTION_CROP_TO_CONTENT, MENU_OPTION_CROP_TO_SELECTION])
        self.assertEqual(_texts(submenus[SUBMENU_MIRROR_AND_ROTATE]),
                         [MENU_OPTION_MIRROR_HORIZONTAL, MENU_OPTION_MIRROR_VERTICAL, MENU_OPTION_ROTATE_CW,
                          MENU_OPTION_ROTATE_CCW])

    def test_menu_move_to_top(self) -> None:
        """Move to top is disabled for the top layer, and moves any other layer to the top of the stack."""
        self.assertFalse(self._menu_actions(self.group)[MENU_OPTION_MOVE_TO_TOP])
        self.assertTrue(self._menu_actions(self.nested_child)[MENU_OPTION_MOVE_TO_TOP])
        menu = self.row(self.nested_child).build_menu()
        next(action for action in menu.actions() if action.text() == MENU_OPTION_MOVE_TO_TOP).trigger()
        self.assertIs(self.image_stack.layer_stack.get_layer_by_index(0), self.nested_child)
        self.assert_panel_matches_stack()

    def test_menu_merge_group_only_for_groups(self) -> None:
        """Merge group is in a group's menu and not in a layer's menu."""
        self.assertIn(MENU_OPTION_MERGE_GROUP, self._menu_actions(self.group))
        self.assertNotIn(MENU_OPTION_MERGE_GROUP, self._menu_actions(self.inner_top))

    def test_menu_rotate_needs_a_transform_layer(self) -> None:
        """A group's rotate options are disabled, and rotating a layer from the menu rotates that layer."""
        def _rotate_actions(menu: QMenu) -> list:
            submenu = next(action.menu() for action in menu.actions() if action.text() == SUBMENU_MIRROR_AND_ROTATE)
            return [action for action in submenu.actions() if action.text() in (MENU_OPTION_ROTATE_CW,
                                                                                MENU_OPTION_ROTATE_CCW)]

        # The menus must outlive their actions:
        group_menu = self.row(self.group).build_menu()
        layer_menu = self.row(self.inner_top).build_menu()
        self.assertFalse(any(action.isEnabled() for action in _rotate_actions(group_menu)))
        clockwise = _rotate_actions(layer_menu)[0]
        self.assertTrue(clockwise.isEnabled())
        with patch.object(ImageLayer, 'rotate') as rotate:
            clockwise.trigger()
        rotate.assert_called_once_with(90)

    def test_menu_shows_key_hints(self) -> None:
        """Menu actions show their KeyConfig bindings."""
        menu = self.row(self.inner_top).build_menu()
        shortcuts = {action.text(): action.shortcut().toString() for action in menu.actions()}
        self.assertEqual(shortcuts[MENU_OPTION_RENAME], KeyConfig().get(KeyConfig.RENAME_LAYER_SHORTCUT))
        self.assertEqual(shortcuts[MENU_OPTION_DUPLICATE], KeyConfig().get(KeyConfig.COPY_LAYER_SHORTCUT))

    def test_rename_starts_in_a_collapsed_group(self) -> None:
        """Renaming the active layer opens the groups above its row and starts editing there."""
        self.image_stack.active_layer = self.nested_child
        self.panel.layer_list.set_expanded(self.nested, False)
        self.panel.layer_list.set_expanded(self.group, False)
        flush_layouts()
        self.assertTrue(self.row(self.nested_child).isHidden())
        self.panel.start_rename()
        flush_layouts()
        label = self.row(self.nested_child).name_label
        self.assertFalse(self.row(self.nested_child).isHidden())
        self.assertTrue(label.is_requesting_input())
        self.assertFalse(self.row(self.bottom).name_label.is_requesting_input())

    def test_rename_root_edits_the_image_strip(self) -> None:
        """Renaming with the root active edits the image strip's name."""
        self.image_stack.active_layer = self.image_stack.layer_stack
        self.panel.start_rename()
        self.assertTrue(self.panel.layer_list.image_strip.name_label.is_requesting_input())

    # Action bar:

    def _bar_button(self, title: str):
        return next(button for button in self.panel.findChildren(QToolButton)
                    if button.accessibleName() == title)

    def test_duplicate_button(self) -> None:
        """The action bar's Duplicate button duplicates the active layer."""
        self.image_stack.active_layer = self.inner_top
        self._bar_button(DUPLICATE_BUTTON_TITLE).click()
        self.assertEqual(self.group.get_layer_by_index(0).name, 'inner_top copy')

    def test_action_bar_forms(self) -> None:
        """The action bar shows text beside its icons where there is room, and bare icons in a narrow panel."""
        button = self._bar_button(DELETE_BUTTON_TITLE)
        self.panel.resize(700, 900)
        self.panel.plan_in(Orientation.SIDE, QSize(700, 900))
        flush_layouts()
        self.assertEqual(button.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.panel.resize(PANEL_SIZE)
        self.panel.plan_in(Orientation.SIDE, QSize(PANEL_SIZE.width() - 190, 900))
        flush_layouts()
        self.assertEqual(button.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonIconOnly)

    # Thumbnail size and the More popover:

    def test_thumbnail_size_choice_resizes_rows(self) -> None:
        """A fixed thumbnail size applies to every row at once, and to rows created later. Auto goes back to the
        fitted size."""
        sizes = {'Small': SMALL_THUMBNAIL_SIZE, 'Medium': MEDIUM_THUMBNAIL_SIZE, 'Large': LARGE_THUMBNAIL_SIZE}
        for choice, size in sizes.items():
            Cache().set(Cache.LAYER_THUMBNAIL_SIZE, choice)
            self.assertEqual({row.thumbnail.width() for row in self.panel.layer_list.rows}, {size}, choice)
        new_layer = self.image_stack.create_layer('new')
        self.assertEqual(self.row(new_layer).thumbnail.width(), LARGE_THUMBNAIL_SIZE)
        Cache().set(Cache.LAYER_THUMBNAIL_SIZE, 'Auto')
        self.panel.plan_in(Orientation.SIDE, QSize(170, 900))
        flush_layouts()
        self.assertEqual(self.row(self.bottom).thumbnail.width(), SMALL_THUMBNAIL_SIZE)

    def test_fixed_thumbnail_size_keeps_toggle_labels_fit_driven(self) -> None:
        """A fixed size doesn't change when the toggles get text labels."""
        Cache().set(Cache.LAYER_THUMBNAIL_SIZE, 'Small')
        button = self._flag_button(LOCK_FLAG)
        self.panel.plan_in(Orientation.SIDE, QSize(600, 900))
        flush_layouts()
        self.assertEqual(button.toolButtonStyle(), Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.assertEqual(self.row(self.bottom).thumbnail.width(), SMALL_THUMBNAIL_SIZE)

    def test_more_popover_sets_thumbnail_size(self) -> None:
        """The More popover's size choice is saved in the Cache, and the popover is always available."""
        content = self.panel.more_content()
        assert content is not None
        box = content.findChild(QComboBox)
        assert box is not None
        box.setCurrentIndex(box.findData('Medium'))
        box.activated.emit(box.currentIndex())
        self.assertEqual(Cache().get(Cache.LAYER_THUMBNAIL_SIZE), 'Medium')
        self.assertEqual(self.row(self.bottom).thumbnail.width(), MEDIUM_THUMBNAIL_SIZE)

    def test_more_popover_selects_neighbor_layers(self) -> None:
        """The popover's select buttons move the active layer, and the window button appears only with a callback."""
        content = self.panel.more_content()
        assert content is not None
        buttons = {button.text().split(' (')[0]: button for button in content.findChildren(QPushButton)}
        self.assertEqual(set(buttons), {SELECT_PREVIOUS_LABEL, SELECT_NEXT_LABEL})
        self.image_stack.active_layer = self.inner_bottom
        buttons[SELECT_PREVIOUS_LABEL].click()
        self.assertIsNot(self.image_stack.active_layer, self.inner_bottom)
        shown: list[bool] = []
        panel = LayerPanel(self.image_stack, show_window=lambda: shown.append(True))
        window_content = panel.more_content()
        assert window_content is not None
        window_button = next(button for button in window_content.findChildren(QPushButton)
                             if button.text().startswith(SHOW_WINDOW_LABEL))
        window_button.click()
        self.assertEqual(shown, [True])
        panel.close()
