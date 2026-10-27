"""Tests LayerPanel, its selected-layer header and its layer rows against changes to the layer stack.

Each structural test checks every row with `assert_panel_matches_stack`: one row per layer, in stack order, indented
by depth, shown only under expanded groups, and laid out without overlap or squeezing.
"""
import re
import sys
from typing import Callable

from PySide6 import QtTest
from PySide6.QtCore import QSize, QEvent, Qt, QPoint, QPointF
from PySide6.QtGui import QEnterEvent
from PySide6.QtWidgets import QApplication, QWidget

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
from src.ui.panel.layer_ui.layer_list import LayerList
from src.ui.panel.layer_ui.layer_menu import MENU_OPTION_MOVE_UP, MENU_OPTION_MOVE_DOWN, MENU_OPTION_DELETE, \
    MENU_OPTION_MERGE_DOWN, MENU_OPTION_RENAME, MENU_OPTION_CROP_TO_SELECTION, MENU_OPTION_MIRROR_HORIZONTAL, \
    MENU_OPTION_MIRROR_VERTICAL
from src.ui.panel.layer_ui.layer_panel import LayerPanel, ADD_BUTTON_TITLE, MERGE_DOWN_BUTTON_TITLE, \
    DELETE_BUTTON_TITLE
from src.ui.panel.layer_ui.layer_row import INDENT, LayerRow, layer_meta_text
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
