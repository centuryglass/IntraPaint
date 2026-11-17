"""Tests LayerTransformToolPanel: the fields it always shows, the ratio lock and its temporary form, the buttons, and
the arrangements fit planning picks."""
import sys

from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QApplication

from src.image.layers.image_stack import ImageStack
from src.ui.button_weight import ButtonWeight, button_weight
from src.ui.input_fields.geometry_block import FIELD_NAMES, HEIGHT, SCALE_X, SCALE_Y, WIDTH
from src.ui.layout.panel_fit import Orientation
from src.ui.panel.tool_control_panels.layer_transform_tool_panel import LayerTransformToolPanel
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

IMAGE_SIZE = QSize(512, 512)


class LayerTransformToolPanelTest(IntraPaintTestCase):
    """Tests LayerTransformToolPanel."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE, IMAGE_SIZE)
        self.panel = LayerTransformToolPanel(self.image_stack)
        self.lock_changes: list[bool] = []
        self.panel.preserve_aspect_ratio_changed.connect(self.lock_changes.append)

    def _arrange(self, orientation: Orientation, size: QSize) -> None:
        self.panel.set_fit_space(orientation, size)
        self.panel.resize(size)
        layout = self.panel.layout()
        assert layout is not None
        layout.activate()

    def test_every_field_shows_at_every_size(self) -> None:
        """Position, size, scale and angle show in every orientation, however small the space."""
        block = self.panel.geometry_block
        for orientation in Orientation:
            for size in (QSize(1, 1), QSize(200, 120), QSize(400, 300), QSize(1600, 1200)):
                self._arrange(orientation, size)
                for name in FIELD_NAMES:
                    self.assertFalse(block.field(name).isHidden(), f'{name} at {orientation} {size}')

    def test_temporary_lock_leaves_setting_unchanged(self) -> None:
        """Holding the fixed-aspect modifier locks the ratio for the tool without changing the stored setting."""
        block = self.panel.geometry_block
        block.set_temporary_lock(True)
        self.assertFalse(self.panel.preserve_aspect_ratio)
        self.assertFalse(block.lock_button().isChecked())
        self.assertTrue(block.lock_button().temporary())
        block.set_temporary_lock(False)
        self.assertFalse(self.panel.preserve_aspect_ratio)
        self.assertEqual(self.lock_changes, [True, False])

    def test_stored_lock_reports_through_temporary_release(self) -> None:
        """Releasing the modifier while the stored lock is on leaves the ratio locked."""
        block = self.panel.geometry_block
        block.set_ratio_locked(True)
        block.set_temporary_lock(True)
        block.set_temporary_lock(False)
        self.assertTrue(self.panel.preserve_aspect_ratio)
        self.assertEqual(self.lock_changes, [True, True, True])

    def test_lock_links_size_and_scale(self) -> None:
        """With the ratio locked, changing W changes H, and changing Scale X changes Scale Y, in proportion."""
        self.panel.layer_width = 200.0
        self.panel.layer_height = 100.0
        self.panel.geometry_block.set_ratio_locked(True)
        heights: list[float] = []
        self.panel.height_changed.connect(heights.append)
        self.panel.geometry_block.field(WIDTH).set_value(400.0)
        self.assertAlmostEqual(self.panel.layer_height, 200.0)
        self.assertEqual(heights, [200.0])
        self.panel.geometry_block.field(SCALE_X).set_value(2.0)
        self.assertAlmostEqual(self.panel.y_scale, 2.0)

    def test_setting_fields_emits_nothing(self) -> None:
        """Values the tool sets back don't emit change signals."""
        changes: list[float] = []
        for signal in (self.panel.x_changed, self.panel.width_changed, self.panel.height_changed,
                       self.panel.y_scale_changed, self.panel.angle_changed):
            signal.connect(changes.append)
        self.panel.x_position = 12.5
        self.panel.layer_width = 300.0
        self.panel.layer_height = 30.0
        self.panel.y_scale = 1.5
        self.panel.rotation = 45.0
        self.assertEqual(changes, [])
        self.assertEqual((self.panel.x_position, self.panel.layer_width, self.panel.y_scale, self.panel.rotation),
                         (12.5, 300.0, 1.5, 45.0))
        self.assertEqual(self.panel.geometry_block.value(HEIGHT), 30.0)
        self.assertEqual(self.panel.geometry_block.value(SCALE_Y), 1.5)

    def test_buttons(self) -> None:
        """Revert and Clear transform have tooltips, emit their signals, and Clear transform is a danger button."""
        emitted: list[str] = []
        self.panel.reset_signal.connect(lambda: emitted.append('revert'))
        self.panel.clear_signal.connect(lambda: emitted.append('clear'))
        self.panel.revert_button.click()
        self.panel.clear_button.click()
        self.assertEqual(emitted, ['revert', 'clear'])
        for button in (self.panel.revert_button, self.panel.clear_button):
            self.assertNotEqual(button.toolTip(), '')
        self.assertEqual(button_weight(self.panel.clear_button), ButtonWeight.DANGER)
        self.assertEqual(button_weight(self.panel.revert_button), ButtonWeight.STANDARD)

    def test_preview_shows_where_it_fits(self) -> None:
        """The preview hides in a short side panel and a short strip, and shows where there is room."""
        side_base = self.panel.fit_base_size(Orientation.SIDE)
        self._arrange(Orientation.SIDE, side_base)
        self.assertTrue(self.panel.preview.isHidden())
        self._arrange(Orientation.SIDE, QSize(side_base.width(), 1000))
        self.assertFalse(self.panel.preview.isHidden())
        self._arrange(Orientation.STRIP, QSize(1600, 400))
        self.assertFalse(self.panel.preview.isHidden())
        self._arrange(Orientation.STRIP, QSize(side_base.width(), 1000))
        self.assertTrue(self.panel.preview.isHidden())

    def test_short_strip_moves_buttons_beside_fields(self) -> None:
        """A strip puts the buttons under the fields when its height holds both, and beside them otherwise."""
        block = self.panel.geometry_block
        self._arrange(Orientation.STRIP, QSize(1600, 600))
        self.assertGreater(self._revert_position().y(), block.geometry().bottom())
        self._arrange(Orientation.STRIP, QSize(1600, block.minimumSizeHint().height()))
        self.assertGreater(self._revert_position().x(), block.geometry().right())

    def _revert_position(self) -> QPoint:
        button = self.panel.revert_button
        return button.mapTo(self.panel, button.rect().topLeft())
