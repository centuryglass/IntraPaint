"""Tests ReactiveLayoutWidget's mode switching at size thresholds, and its visibility limits."""
import sys

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QWidget

from src.ui.layout.reactive_layout_widget import ReactiveLayoutWidget
from src.util.shared_constants import INT_MAX
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

NARROW_MAX = QSize(199, INT_MAX)
WIDE_MIN = QSize(200, 0)


class ReactiveLayoutWidgetTest(IntraPaintTestCase):
    """Resizes a shown ReactiveLayoutWidget across its mode thresholds."""

    def setUp(self) -> None:
        super().setUp()
        self.widget = ReactiveLayoutWidget()
        self.widget.resize(100, 100)
        self.widget.show()
        self.activations: list[str] = []

    def tearDown(self) -> None:
        self.widget.close()
        super().tearDown()

    def _setup_fn(self, name: str):
        return lambda: self.activations.append(name)

    def _add_narrow_and_wide(self) -> None:
        self.widget.add_layout_mode('narrow', self._setup_fn('narrow'), None, NARROW_MAX)
        self.widget.add_layout_mode('wide', self._setup_fn('wide'), WIDE_MIN, None)

    def test_adding_a_mode_activates_it_when_in_range(self) -> None:
        """A mode whose range holds the current size activates as soon as it is added."""
        self._add_narrow_and_wide()
        self.assertEqual(self.activations, ['narrow'])

    def test_mode_switches_at_threshold(self) -> None:
        """Both range ends are inclusive: 199 wide is narrow, 200 wide is wide."""
        self._add_narrow_and_wide()
        self.widget.resize(199, 100)
        self.assertEqual(self.activations, ['narrow'])
        self.widget.resize(200, 100)
        self.assertEqual(self.activations, ['narrow', 'wide'])
        self.widget.resize(199, 100)
        self.assertEqual(self.activations, ['narrow', 'wide', 'narrow'])

    def test_resizing_within_a_mode_does_not_rerun_setup(self) -> None:
        """Setup runs once per mode change, not on every resize."""
        self._add_narrow_and_wide()
        for width in (120, 150, 190):
            self.widget.resize(width, 100)
        self.assertEqual(self.activations, ['narrow'])

    def test_default_mode_covers_gaps(self) -> None:
        """When no sized mode is in range, the default mode activates."""
        self.widget.add_layout_mode('small', self._setup_fn('small'), None, QSize(150, 150))
        self.widget.add_default_layout_mode(self._setup_fn('default'))
        self.widget.resize(300, 300)
        self.assertEqual(self.activations, ['small', 'default'])
        self.widget.resize(100, 100)
        self.assertEqual(self.activations, ['small', 'default', 'small'])

    def test_no_mode_in_range_keeps_last_mode(self) -> None:
        """Without a default mode, a size outside every range keeps the last mode and logs an error."""
        self.widget.add_layout_mode('small', self._setup_fn('small'), None, QSize(150, 150))
        with self.assertLogs('src.ui.layout.reactive_layout_widget', level='ERROR'):
            self.widget.resize(300, 300)
        self.assertEqual(self.activations, ['small'])

    def test_overlapping_corner_is_rejected(self) -> None:
        """A mode whose minimum falls inside an existing mode's range raises."""
        self.widget.add_layout_mode('narrow', self._setup_fn('narrow'), None, NARROW_MAX)
        with self.assertRaises(RuntimeError):
            self.widget.add_layout_mode('overlap', self._setup_fn('overlap'), QSize(150, 0), None)

    def test_mode_enclosing_another_is_rejected(self) -> None:
        """A mode whose range encloses an existing one overlaps it, though neither of its corners is inside."""
        self.widget.add_layout_mode('middle', self._setup_fn('middle'), QSize(300, 300), QSize(400, 400))
        with self.assertRaises(RuntimeError):
            self.widget.add_layout_mode('outer', self._setup_fn('outer'), QSize(200, 200), QSize(500, 500))

    def test_open_ended_mode_ignores_current_size_in_overlap_check(self) -> None:
        """An omitted bound defaults to the widest range, never to the widget's current size."""
        self.widget.resize(300, 300)
        self.widget.add_layout_mode('wide', self._setup_fn('wide'), WIDE_MIN, None)
        self.widget.add_layout_mode('narrow', self._setup_fn('narrow'), None, NARROW_MAX)
        self.assertEqual(self.activations, ['wide'])

    def test_visibility_limit(self) -> None:
        """A limited child shows only when both dimensions reach its limit."""
        child = QWidget(self.widget)
        self.widget.add_visibility_limit(child, QSize(150, 150))
        self.widget.resize(149, 300)
        self.assertTrue(child.isHidden())
        self.widget.resize(300, 149)
        self.assertTrue(child.isHidden())
        self.widget.resize(150, 150)
        self.assertFalse(child.isHidden())

    def test_visibility_limit_skips_non_descendants(self) -> None:
        """A limited widget moved out of the widget keeps its own visibility."""
        child = QWidget(self.widget)
        self.widget.add_visibility_limit(child, QSize(150, 150))
        child.setParent(None)
        child.show()
        self.widget.resize(100, 100)
        self.assertFalse(child.isHidden())
        child.close()

    def test_show_rechecks_limits(self) -> None:
        """Showing the widget applies limits that changed while it was hidden."""
        self.widget.hide()
        child = QWidget(self.widget)
        child.show()
        self.widget.add_visibility_limit(child, QSize(150, 150))
        self.widget.show()
        self.assertTrue(child.isHidden())
