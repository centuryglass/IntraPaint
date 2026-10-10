"""Tests the UndoStack module."""
import sys
import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from src.config.application_config import AppConfig
from src.undo_stack import UndoStack
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class UndoStackTest(IntraPaintTestCase):
    """Tests the UndoStack module."""

    def setUp(self) -> None:
        super().setUp()
        self.undo_stack = UndoStack()
        self.undo_stack.clear()
        self.value = 0

    def commit_value(self, new_value: int, action_type: str = 'test.set_value') -> None:
        """Commits an action that changes self.value, standing in for an edit to application state."""
        old_value = self.value

        def _apply(value=new_value) -> None:
            self.value = value

        def _revert(value=old_value) -> None:
            self.value = value

        self.undo_stack.commit_action(_apply, _revert, action_type)

    def test_commit_runs_and_records_action(self) -> None:
        """commit_action applies the change immediately and adds one undo entry."""
        self.commit_value(1)
        self.assertEqual(self.value, 1)
        self.assertEqual(self.undo_stack.undo_count(), 1)
        self.assertEqual(self.undo_stack.redo_count(), 0)

    def test_undo_and_redo(self) -> None:
        """Undo and redo walk the history in order and move entries between the two stacks."""
        self.commit_value(1)
        self.commit_value(2)
        self.undo_stack.undo()
        self.assertEqual((self.value, self.undo_stack.undo_count(), self.undo_stack.redo_count()), (1, 1, 1))
        self.undo_stack.undo()
        self.assertEqual((self.value, self.undo_stack.undo_count(), self.undo_stack.redo_count()), (0, 0, 2))
        self.undo_stack.redo()
        self.assertEqual((self.value, self.undo_stack.undo_count(), self.undo_stack.redo_count()), (1, 1, 1))
        self.undo_stack.redo()
        self.assertEqual((self.value, self.undo_stack.undo_count(), self.undo_stack.redo_count()), (2, 2, 0))

    def test_commit_clears_redo_history(self) -> None:
        """A new action after an undo discards the undone actions."""
        self.commit_value(1)
        self.commit_value(2)
        self.undo_stack.undo()
        self.commit_value(3)
        self.assertEqual(self.undo_stack.redo_count(), 0)
        self.undo_stack.undo()
        self.assertEqual(self.value, 1)

    def test_count_signals(self) -> None:
        """The count signals report each stack's new size."""
        undo_count_changed = MagicMock()
        redo_count_changed = MagicMock()
        self.undo_stack.undo_count_changed.connect(undo_count_changed)
        self.undo_stack.redo_count_changed.connect(redo_count_changed)
        try:
            self.commit_value(1)
            undo_count_changed.assert_called_with(1)
            self.undo_stack.undo()
            undo_count_changed.assert_called_with(0)
            redo_count_changed.assert_called_with(1)
        finally:
            self.undo_stack.undo_count_changed.disconnect(undo_count_changed)
            self.undo_stack.redo_count_changed.disconnect(redo_count_changed)

    def test_skip_initial_call(self) -> None:
        """With skip_initial_call, the action isn't run on commit, but is still undone and redone."""
        apply = MagicMock()
        revert = MagicMock()
        self.undo_stack.commit_action(apply, revert, 'test.skip', skip_initial_call=True)
        apply.assert_not_called()
        self.undo_stack.undo()
        revert.assert_called_once()
        self.undo_stack.redo()
        apply.assert_called_once()

    def test_combining_actions(self) -> None:
        """Actions committed inside combining_actions form one entry, undone in reverse order."""
        with self.undo_stack.combining_actions('test.group'):
            self.commit_value(1)
            self.commit_value(2)
            self.commit_value(3)
        self.assertEqual(self.undo_stack.undo_count(), 1)
        self.undo_stack.undo()
        self.assertEqual(self.value, 0)
        self.undo_stack.redo()
        self.assertEqual(self.value, 3)

    def test_empty_group_adds_nothing(self) -> None:
        """A combining_actions block with no commits leaves the history unchanged."""
        with self.undo_stack.combining_actions('test.group'):
            pass
        self.assertEqual(self.undo_stack.undo_count(), 0)

    def test_unrelated_commits_stay_separate(self) -> None:
        """Commits close together in time stay separate entries, whatever the merge interval."""
        AppConfig().set(AppConfig.UNDO_MERGE_INTERVAL, 60.0)
        self.commit_value(1, 'test.first_type')
        self.commit_value(2, 'test.second_type')
        self.assertEqual(self.undo_stack.undo_count(), 2)
        self.undo_stack.undo()
        self.assertEqual(self.value, 1)

    def test_nested_combining_actions_join_outer_group(self) -> None:
        """A group opened inside another group adds its commits to the outer entry."""
        with self.undo_stack.combining_actions('test.outer'):
            self.commit_value(1)
            with self.undo_stack.combining_actions('test.inner'):
                self.commit_value(2)
            self.commit_value(3)
        self.assertEqual(self.undo_stack.undo_count(), 1)
        self.undo_stack.undo()
        self.assertEqual(self.value, 0)
        self.undo_stack.redo()
        self.assertEqual(self.value, 3)

    def test_exception_in_nested_group_keeps_outer_group_open(self) -> None:
        """An exception caught inside an outer group leaves the outer group recording, then closing normally."""
        with self.undo_stack.combining_actions('test.outer'):
            self.commit_value(1)
            with self.assertRaises(ValueError):
                with self.undo_stack.combining_actions('test.inner'):
                    self.commit_value(2)
                    raise ValueError('simulated failure in an inner group')
            self.commit_value(3)
        self.assertEqual(self.undo_stack.undo_count(), 1)
        self.commit_value(4)
        self.assertEqual(self.undo_stack.undo_count(), 2)
        self.undo_stack.undo()
        self.undo_stack.undo()
        self.assertEqual(self.value, 0)

    def test_last_action_is_none_inside_group(self) -> None:
        """last_action doesn't expose the history entry from before an open group."""
        self.commit_value(1)
        with self.undo_stack.combining_actions('test.group'):
            with self.undo_stack.last_action('test.set_value') as prev_action:
                self.assertIsNone(prev_action)
        with self.undo_stack.last_action('test.set_value') as prev_action:
            self.assertIsNotNone(prev_action)

    def test_commit_inside_action_raises(self) -> None:
        """An action that commits another action is rejected rather than corrupting the history."""
        def _nested_commit() -> None:
            self.commit_value(2)

        with self.assertRaises(RuntimeError):
            self.undo_stack.commit_action(_nested_commit, lambda: None, 'test.nested')

    def test_exception_in_combined_actions_keeps_history_working(self) -> None:
        """An exception inside combining_actions still records the completed actions, and later ones as usual."""
        with self.assertRaises(ValueError):
            with self.undo_stack.combining_actions('test.failing_group'):
                self.commit_value(1)
                raise ValueError('simulated failure partway through a grouped edit')
        self.assertEqual(self.value, 1)
        self.assertEqual(self.undo_stack.undo_count(), 1)
        self.commit_value(2)
        self.assertEqual(self.undo_stack.undo_count(), 2)
        with self.undo_stack.combining_actions('test.next_group'):
            self.commit_value(3)
        self.assertEqual(self.undo_stack.undo_count(), 3)
        for expected_value in (2, 1, 0):
            self.undo_stack.undo()
            self.assertEqual(self.value, expected_value)

    def test_undo_in_progress(self) -> None:
        """undo_in_progress is True only while an undo action runs."""
        states_during_undo = []

        def _revert() -> None:
            states_during_undo.append(self.undo_stack.undo_in_progress)

        self.undo_stack.commit_action(lambda: None, _revert, 'test.undo_state')
        self.assertFalse(self.undo_stack.undo_in_progress)
        self.undo_stack.undo()
        self.assertEqual(states_during_undo, [True])
        self.assertFalse(self.undo_stack.undo_in_progress)

    def test_redo_in_progress(self) -> None:
        """redo_in_progress is True only while a redo action runs, and undo_in_progress stays False then."""
        states_during_redo = []

        def _apply() -> None:
            states_during_redo.append((self.undo_stack.undo_in_progress, self.undo_stack.redo_in_progress))

        self.undo_stack.commit_action(_apply, lambda: None, 'test.redo_state')
        self.undo_stack.undo()
        states_during_redo.clear()
        self.undo_stack.redo()
        self.assertEqual(states_during_redo, [(False, True)])
        self.assertFalse(self.undo_stack.redo_in_progress)

    def test_undo_with_empty_history_is_not_in_progress(self) -> None:
        """Undo with nothing to undo leaves undo_in_progress False."""
        self.undo_stack.undo()
        self.assertFalse(self.undo_stack.undo_in_progress)

    def test_failed_undo_is_not_in_progress(self) -> None:
        """An undo action that raises doesn't leave undo_in_progress stuck on."""
        def _failing_revert() -> None:
            raise ValueError('simulated failure while undoing')

        self.undo_stack.commit_action(lambda: None, _failing_revert, 'test.failing_undo')
        with self.assertRaises(ValueError):
            self.undo_stack.undo()
        self.assertFalse(self.undo_stack.undo_in_progress)

    def test_failed_redo_raises(self) -> None:
        """A redo action that raises propagates out of redo()."""
        calls = []

        def _apply() -> None:
            calls.append(1)
            if len(calls) > 1:
                raise ValueError('simulated failure while redoing')

        self.undo_stack.commit_action(_apply, lambda: None, 'test.failing_redo')
        self.undo_stack.undo()
        with self.assertRaises(ValueError):
            self.undo_stack.redo()
        self.assertFalse(self.undo_stack.redo_in_progress)

    def test_undo_limit_follows_config(self) -> None:
        """After clear(), the history holds at most AppConfig.MAX_UNDO entries, dropping the oldest."""
        AppConfig().set(AppConfig.MAX_UNDO, 3)
        self.undo_stack.clear()
        for value in range(1, 6):
            self.commit_value(value)
        self.assertEqual(self.undo_stack.undo_count(), 3)
        for _ in range(3):
            self.undo_stack.undo()
        self.assertEqual(self.value, 2)


if __name__ == '__main__':
    unittest.main()
