"""Tests the layout checks `hidden with room`, `misplaced leftover` and `misaligned` from `find_arrangement_problems`,
on small synthetic widget trees."""
import sys
from typing import Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from src.ui.layout.dock_panel import DockPanel, PanelLayout
from src.ui.layout.panel_fit import REQUIRED, Orientation
from test.base_test_case import IntraPaintTestCase
from test.ui.panel_capture import (ALIGN_TOLERANCE, LEFTOVER_SLACK, find_arrangement_problems, misaligned_edges)

app = QApplication.instance() or QApplication(sys.argv)

PANEL_SIZE = QSize(400, 300)


def _kind(problems: list[str], kind: str) -> list[str]:
    return [problem for problem in problems if problem.startswith(kind + ':')]


class SizedPanel(DockPanel):
    """A required control, a control with a large and a small form, and an optional control after it."""

    def build(self, ui: PanelLayout) -> None:
        self.required = QPushButton('required')
        self.shrinking = QWidget()
        self.shrinking.setFixedHeight(120)
        self.later = QPushButton('later')
        self.later.setFixedHeight(30)
        section = ui.section('Controls')
        section.add(self.required, REQUIRED)
        section.add(self.shrinking, 1, (lambda: self.shrinking.setFixedHeight(120),
                                        lambda: self.shrinking.setFixedHeight(20)))
        section.add(self.later, 2)


class PanelCaptureTest(IntraPaintTestCase):
    """Tests the checks one at a time."""

    @staticmethod
    def _root(*rects: QRect, size: QSize = PANEL_SIZE) -> QWidget:
        root = QWidget()
        root.resize(size)
        for i, rect in enumerate(rects):
            button = QPushButton(f'b{i}', root)
            button.setGeometry(rect)
        return root

    # misplaced leftover

    def test_content_at_the_origin_has_no_misplaced_leftover(self) -> None:
        """Content at the top left corner, with its spare space after it, is fine."""
        root = self._root(QRect(0, 0, 100, 30), QRect(0, 40, 100, 30))
        self.assertEqual([], _kind(find_arrangement_problems(root), 'misplaced leftover'))

    def test_leftover_slack_boundary(self) -> None:
        """Content LEFTOVER_SLACK px from the top and left is fine, and one more px is misplaced."""
        inside = self._root(QRect(LEFTOVER_SLACK, LEFTOVER_SLACK, 100, 30))
        self.assertEqual([], _kind(find_arrangement_problems(inside), 'misplaced leftover'))
        outside = self._root(QRect(LEFTOVER_SLACK + 1, LEFTOVER_SLACK + 1, 100, 30))
        self.assertEqual(2, len(_kind(find_arrangement_problems(outside), 'misplaced leftover')))

    def test_centered_content_has_misplaced_leftover(self) -> None:
        """Spare space split around content is misplaced."""
        root = self._root(QRect(150, 120, 100, 30))
        problems = _kind(find_arrangement_problems(root), 'misplaced leftover')
        self.assertEqual(2, len(problems))

    def test_leading_edge_follows_layout_direction(self) -> None:
        """In a right-to-left panel, content at the right edge is fine and content at the left edge is misplaced."""
        root = self._root(QRect(300, 0, 100, 30))
        root.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.assertEqual([], _kind(find_arrangement_problems(root), 'misplaced leftover'))
        root = self._root(QRect(0, 0, 100, 30))
        root.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.assertEqual(1, len(_kind(find_arrangement_problems(root), 'misplaced leftover')))

    # misaligned

    def _column_problems(self, offset: int, second_width: int = 100) -> list[str]:
        root = self._root(QRect(0, 0, 100, 30), QRect(offset, 40, second_width, 30))
        return _kind(find_arrangement_problems(root), 'misaligned')

    def test_aligned_neighbors_are_fine(self) -> None:
        """Neighbors with the same left edge don't report."""
        self.assertEqual([], self._column_problems(0))

    def test_near_miss_in_a_column(self) -> None:
        """Left edges 1 px apart, and ALIGN_TOLERANCE px apart, are misaligned."""
        self.assertEqual(1, len(self._column_problems(1)))
        self.assertEqual(1, len(self._column_problems(ALIGN_TOLERANCE)))

    def test_distant_edges_are_deliberate(self) -> None:
        """Left edges more than ALIGN_TOLERANCE px apart are not reported."""
        self.assertEqual([], self._column_problems(ALIGN_TOLERANCE + 1))

    def test_near_miss_in_a_row(self) -> None:
        """Top edges of neighbors in a row are compared the same way."""
        for offset, count in ((0, 0), (1, 1), (ALIGN_TOLERANCE, 1), (ALIGN_TOLERANCE + 1, 0)):
            with self.subTest(offset=offset):
                root = self._root(QRect(0, 0, 100, 30), QRect(120, offset, 100, 30))
                self.assertEqual(count, len(_kind(find_arrangement_problems(root), 'misaligned')))

    def test_centered_neighbors_are_not_misaligned(self) -> None:
        """A narrower item centered on a wider neighbor isn't a near miss."""
        self.assertEqual([], self._column_problems(2, 96))

    def test_only_nearest_neighbors_are_compared(self) -> None:
        """Content with another item between it and a nearly aligned one isn't their neighbor."""
        root = self._root(QRect(0, 0, 100, 30), QRect(0, 40, 100, 30), QRect(4, 80, 100, 30))
        problems = _kind(find_arrangement_problems(root), 'misaligned')
        self.assertEqual(1, len(problems), problems)
        self.assertIn('b1', problems[0])
        self.assertIn('b2', problems[0])

    def test_misaligned_edges_mark_both_compared_edges(self) -> None:
        """The overlay gets one line per compared edge, along the left edges for a column."""
        root = self._root(QRect(0, 0, 100, 30), QRect(3, 40, 100, 30))
        lines = misaligned_edges(root)
        self.assertEqual(2, len(lines))
        self.assertEqual({0, 3}, {line.x1() for line in lines})
        self.assertTrue(all(line.x1() == line.x2() for line in lines))

    # hidden with room

    def _sized_panel(self, height: int) -> SizedPanel:
        panel = SizedPanel()
        panel.resize(PANEL_SIZE.width(), height)
        panel.set_host_facts(Orientation.SIDE, QSize(PANEL_SIZE.width(), height))
        return panel

    def _hidden_with_room(self, panel: DockPanel) -> list[str]:
        return _kind(find_arrangement_problems(panel), 'hidden with room')

    def test_item_left_out_by_a_greedy_large_form_is_hidden_with_room(self) -> None:
        """Where the planner gives the earlier control its large form and leaves the later one in More, though the
        earlier control's small form leaves room for both, the later one is reported. Where the later one is shown, or
        doesn't fit in any form, nothing is."""
        reported, shown, squeezed = [], [], []
        for height in range(120, 420, 4):
            panel = self._sized_panel(height)
            problems = self._hidden_with_room(panel)
            if panel.later not in panel.overflow_widgets:
                self.assertEqual([], problems, height)
                shown.append(height)
            elif problems:
                self.assertIn('later', problems[0])
                self.assertIn('in More', problems[0])
                reported.append(height)
            else:
                squeezed.append(height)
        self.assertGreater(len(reported), 0)
        self.assertGreater(len(shown), 0)
        self.assertGreater(len(squeezed), 0)

    def test_checking_leaves_the_panel_as_it_was(self) -> None:
        """Measuring a trial placement doesn't change what the panel shows."""
        height = next(h for h in range(120, 420, 4) if self._hidden_with_room(self._sized_panel(h)))
        panel = self._sized_panel(height)
        before = (list(panel.overflow_widgets), panel.shrinking.height(), panel.later.isVisible(), panel.measure())
        self.assertTrue(self._hidden_with_room(panel))
        after = (list(panel.overflow_widgets), panel.shrinking.height(), panel.later.isVisible(), panel.measure())
        self.assertEqual(before, after)

    def test_panel_with_nothing_left_out_has_no_hidden_control(self) -> None:
        """A roomy panel shows everything, and a squeezed one that can't fit even the smallest form reports nothing."""
        self.assertEqual([], self._hidden_with_room(self._sized_panel(900)))
        squeezed = self._sized_panel(60)
        self.assertIn(squeezed.later, squeezed.overflow_widgets)
        self.assertEqual([], self._hidden_with_room(squeezed))

    def test_unplanned_panel_reports_nothing(self) -> None:
        """A panel that was never told its size has no placement to check."""
        self.assertEqual([], self._hidden_with_room(SizedPanel()))
