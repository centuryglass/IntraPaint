"""Tests open_image_file."""
from unittest.mock import patch

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFileDialog, QWidget

from src.ui.modal.modal_utils import open_image_file, save_filters, load_filters, _filter_extensions, \
    SAVE_IMAGE_MODE, IMAGE_FORMATS_DESCRIPTION
from src.util.visual.image_format_utils import IMAGE_WRITE_FORMATS, IMAGE_READ_FORMATS, image_format_groups
from test.base_test_case import IntraPaintTestCase


class OpenImageFileTest(IntraPaintTestCase):
    """Tests the file dialog's size cap."""

    def test_dialog_capped_to_parent_window_screen(self) -> None:
        """The dialog's maximum size comes from the screen of the parent's top-level window."""
        window = QWidget()
        child = QWidget(window)
        cap = QSize(640, 480)
        with patch('src.ui.modal.modal_utils.get_screen_size', return_value=cap) as get_size, \
                patch.object(QFileDialog, 'exec', return_value=0), \
                patch.object(QFileDialog, 'setMaximumSize') as set_maximum:
            self.assertIsNone(open_image_file(child))
        self.assertEqual(get_size.call_count, 1)
        self.assertIs(get_size.call_args.args[0], window)
        set_maximum.assert_called_once_with(cap)
        get_size.reset_mock()


class FormatFilterTest(IntraPaintTestCase):
    """Tests the per-format type filters and how `open_image_file` uses them."""

    def test_every_write_extension_in_one_save_entry(self) -> None:
        """Each writable extension appears in exactly one Save As entry."""
        listed = [ext for entry in save_filters() for ext in _filter_extensions(entry)]
        self.assertEqual(sorted(listed), sorted({ext.lower() for ext in IMAGE_WRITE_FORMATS}))

    def test_every_read_extension_in_one_open_entry(self) -> None:
        """Each readable extension appears in exactly one entry after "All supported"."""
        filters = load_filters()
        self.assertTrue(filters[0].startswith(IMAGE_FORMATS_DESCRIPTION))
        listed = [ext for entry in filters[1:] for ext in _filter_extensions(entry)]
        self.assertEqual(sorted(listed), sorted({ext.lower() for ext in IMAGE_READ_FORMATS}))
        self.assertEqual(sorted(listed), sorted(_filter_extensions(filters[0])))

    def test_layer_filters_leave_out_ora(self) -> None:
        """Open Images as Layers offers no OpenRaster entry."""
        listed = [ext for entry in load_filters(layers=True) for ext in _filter_extensions(entry)]
        self.assertNotIn('ora', listed)
        self.assertIn('png', listed)

    def test_save_order(self) -> None:
        """Top-tier formats come first in the decided order, then the rest sorted by label."""
        groups = image_format_groups(IMAGE_WRITE_FORMATS)
        top = ['ora', 'png', 'jpg', 'webp', 'avif', 'gif', 'apng', 'tiff', 'bmp']
        available = [ext for ext in top if ext.upper() in IMAGE_WRITE_FORMATS]
        self.assertEqual(available, [group.extensions[0] for group in groups[:len(available)]])
        rest = [group.label.casefold() for group in groups[len(available):]]
        self.assertEqual(sorted(rest), rest)

    def test_unclaimed_extension_gets_own_entry(self) -> None:
        """An extension no group claims is listed on its own."""
        groups = image_format_groups({'PNG', 'ZZZ'})
        self.assertEqual([('png',), ('zzz',)], [group.extensions for group in groups])
        self.assertIn('ZZZ', groups[1].label)

    def _save_dialog_state(self, selected_file: str) -> tuple[str, str, str]:
        """Returns the selected filter and default suffix a save dialog opens with, and the suffix after choosing PNG."""
        state: list[tuple[str, str, str]] = []

        def _record(dialog: QFileDialog) -> int:
            opened_filter, opened_suffix = dialog.selectedNameFilter(), dialog.defaultSuffix()
            dialog.filterSelected.emit(save_filters()[1])
            state.append((opened_filter, opened_suffix, dialog.defaultSuffix()))
            return 0

        parent = QWidget()  # tearDown deletes it, and the dialog with it.
        with patch.object(QFileDialog, 'exec', new=_record):
            open_image_file(parent, SAVE_IMAGE_MODE, selected_file)
        return state[0]

    def test_save_selects_entry_for_file_extension(self) -> None:
        """A save dialog starts on the entry listing the suggested file's extension, and appends its first one."""
        selected, suffix, changed_suffix = self._save_dialog_state('picture.jpeg')
        self.assertTrue(selected.startswith('JPEG'))
        self.assertEqual('jpg', suffix)
        self.assertEqual('png', changed_suffix)

    def test_save_defaults_to_first_entry(self) -> None:
        """With no matching file, a save dialog starts on ORA."""
        selected, suffix, _ = self._save_dialog_state('')
        self.assertEqual(save_filters()[0], selected)
        self.assertEqual('ora', suffix)
