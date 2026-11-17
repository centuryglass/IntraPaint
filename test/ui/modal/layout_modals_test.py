"""Tests the saved panel layout dialogs' logic without opening them."""
from unittest.mock import patch

from src.ui.modal.layout_name_modal import LayoutNameModal, prompt_layout_name
from src.ui.modal.manage_layouts_modal import ManageLayoutsModal
from src.ui.window import saved_layouts
from test.base_test_case import IntraPaintTestCase

NAME_MODAL = 'src.ui.modal.layout_name_modal'
MANAGE_MODAL = 'src.ui.modal.manage_layouts_modal'


class LayoutModalsTest(IntraPaintTestCase):
    """Tests the name and manage dialogs."""

    def test_name_is_trimmed_and_empty_rejected(self) -> None:
        """Accepting trims the name, and a blank name sets no result."""
        modal = LayoutNameModal('title', 'Layout 1')
        modal._name_input.setText('   ')
        modal._accept_name()
        self.assertIsNone(modal.name)
        self.assertNotEqual(modal._status.text(), '')
        modal._name_input.setText('  Wide  ')
        modal._accept_name()
        self.assertEqual(modal.name, 'Wide')

    def test_prompt_confirms_overwrite(self) -> None:
        """An existing name is returned only when the overwrite is confirmed, otherwise the prompt repeats."""
        with patch(f'{NAME_MODAL}.LayoutNameModal') as modal_class, \
                patch(f'{NAME_MODAL}.confirm_overwrite', side_effect=[False, True]) as confirm:
            modal_class.return_value.exec.return_value = LayoutNameModal.DialogCode.Accepted
            modal_class.return_value.name = 'Wide'
            result = prompt_layout_name(None, 'title', 'Layout 1', {'Wide'})
        self.assertEqual(confirm.call_count, 2)
        self.assertEqual(result, 'Wide')

    def test_prompt_cancel_and_free_name(self) -> None:
        """Cancelling returns None, and a free name or the allowed existing name skips the confirmation."""
        with patch(f'{NAME_MODAL}.LayoutNameModal') as modal_class, \
                patch(f'{NAME_MODAL}.confirm_overwrite') as confirm:
            instance = modal_class.return_value
            instance.exec.return_value = 0
            self.assertIsNone(prompt_layout_name(None, 't', 'x', set()))
            instance.exec.return_value = LayoutNameModal.DialogCode.Accepted
            instance.name = 'New'
            self.assertEqual(prompt_layout_name(None, 't', 'x', {'Old'}), 'New')
            instance.name = 'Old'
            self.assertEqual(prompt_layout_name(None, 't', 'x', {'Old'}, allowed_existing='Old'), 'Old')
            confirm.assert_not_called()

    def test_manage_lists_renames_deletes_applies(self) -> None:
        """The manage dialog lists saved names and its actions change them."""
        saved_layouts.save_layout('b', 'state-b')
        saved_layouts.save_layout('A', 'state-a')
        applied: list[str] = []
        modal = ManageLayoutsModal(applied.append)
        self.assertEqual([modal._list.item(i).text() for i in range(modal._list.count())], ['A', 'b'])
        self.assertEqual(modal.selected_name(), 'A')

        # Reset the mocks after use: their recorded calls hold the modal, and a mock is always in a reference cycle.
        with patch(f'{MANAGE_MODAL}.prompt_layout_name', return_value='C') as prompt:
            modal.rename_selected()
            prompt.reset_mock()
        self.assertEqual(saved_layouts.layout_names(), ['b', 'C'])

        modal._list.setCurrentRow(0)
        with patch(f'{MANAGE_MODAL}.request_confirmation', return_value=False) as confirm:
            modal.delete_selected()
            confirm.reset_mock()
        self.assertEqual(saved_layouts.layout_names(), ['b', 'C'])
        with patch(f'{MANAGE_MODAL}.request_confirmation', return_value=True) as confirm:
            modal.delete_selected()
            confirm.reset_mock()
        self.assertEqual(saved_layouts.layout_names(), ['C'])

        modal.apply_selected()
        self.assertEqual(applied, ['C'])
