"""Tests the pre-save loss dialog's details box."""
from PySide6.QtWidgets import QPlainTextEdit

from src.config.application_config import AppConfig
from src.ui.modal.save_loss_modal import SaveLoss, SaveLossModal
from src.ui.widget.panel_section import PanelSection
from test.base_test_case import IntraPaintTestCase


class SaveLossModalTest(IntraPaintTestCase):
    """The dialog lists details of a long loss in a collapsed, scrolling box."""

    def test_details_are_collapsed_and_scroll(self) -> None:
        """A loss with details gets a collapsed section holding a read-only box, capped in height."""
        details = '\n'.join(f'EXIF tags: Tag{i}' for i in range(200))
        modal = SaveLossModal(None, [SaveLoss('Title', 'Message', AppConfig.WARN_BEFORE_METADATA_LOSS, details)], False)
        sections = modal.findChildren(PanelSection)
        self.assertEqual(1, len(sections))
        self.assertFalse(sections[0].is_expanded())
        box = modal.findChild(QPlainTextEdit)
        assert box is not None
        self.assertTrue(box.isReadOnly())
        self.assertEqual(details, box.toPlainText())
        self.assertLess(box.maximumHeight(), box.fontMetrics().lineSpacing() * 20)

    def test_no_details_has_no_section(self) -> None:
        """A loss without details adds no section."""
        modal = SaveLossModal(None, [SaveLoss('Title', 'Message', AppConfig.WARN_BEFORE_LAYERLESS_SAVE)], False)
        self.assertEqual([], modal.findChildren(PanelSection))
