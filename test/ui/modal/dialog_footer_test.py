"""Tests DialogFooter."""
from PySide6.QtWidgets import QPushButton

from src.ui.button_weight import ButtonWeight, button_weight
from src.ui.modal.dialog_footer import DialogFooter
from test.base_test_case import IntraPaintTestCase


class DialogFooterTest(IntraPaintTestCase):
    """Tests the shared footer's buttons and signals."""

    def test_confirm_is_primary_default_and_emits(self) -> None:
        """The confirm button is the primary default button, and the buttons emit accepted and rejected."""
        footer = DialogFooter('Resize canvas')
        results: list[str] = []
        footer.accepted.connect(lambda: results.append('accepted'))
        footer.rejected.connect(lambda: results.append('rejected'))
        self.assertEqual(footer.confirm_button.text(), 'Resize canvas')
        self.assertTrue(footer.confirm_button.isDefault())
        self.assertEqual(button_weight(footer.confirm_button), ButtonWeight.PRIMARY)
        footer.confirm_button.click()
        assert footer.cancel_button is not None
        footer.cancel_button.click()
        self.assertEqual(results, ['accepted', 'rejected'])

    def test_destructive_and_secondary_buttons(self) -> None:
        """A destructive confirm button uses the signal color, and secondary buttons come before the box."""
        footer = DialogFooter('Delete', cancel_text=None, destructive=True)
        self.assertIsNone(footer.cancel_button)
        self.assertEqual(button_weight(footer.confirm_button), ButtonWeight.DANGER)
        center = footer.add_secondary_button('Center')
        remove = footer.add_secondary_button('Remove', destructive=True)
        self.assertEqual(button_weight(remove), ButtonWeight.DANGER)
        self.assertFalse(center.autoDefault())
        layout = footer.layout()
        order = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertEqual([w for w in order if isinstance(w, QPushButton)], [center, remove])
        self.assertIs(order[0], center)
