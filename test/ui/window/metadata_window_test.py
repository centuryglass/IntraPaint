"""Tests the metadata window: edits made through its widgets change the `ImageMetadata`, and the editor buttons."""
import sys

from PIL import ExifTags
from PIL.ExifTags import IFD
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.image.image_metadata import ImageMetadata
from src.ui.window.metadata_window import MetadataWindow, save_format_note
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

PARAMETERS = ('a cat\nNegative prompt: blur\nSteps: 20, Sampler: Euler a, CFG scale: 7, Seed: 5, Size: 512x768, '
              'Version: v1.9, Lora hashes: "a: 1, b: 2"')


class MetadataWindowTest(IntraPaintTestCase):
    """Builds the window over an `ImageMetadata` with A1111 parameters."""

    def setUp(self) -> None:
        super().setUp()
        self.metadata = ImageMetadata({'parameters': PARAMETERS, 'other': 'value'})
        self.window = MetadataWindow(self.metadata)

    def _row(self, field: str) -> int:
        return self.window._field_rows.index(field)

    def test_prompt_edit_changes_only_the_prompt(self) -> None:
        """Editing the prompt box rewrites the prompt and leaves every other field's text as it was."""
        self.window._prompt_box.setValue('a dog')
        self.assertEqual(PARAMETERS.replace('a cat', 'a dog'), self.metadata.text['parameters'])

    def test_field_table_edit(self) -> None:
        """Editing a value cell changes that field, including an unmapped one."""
        self.window._field_table.item(self._row('Version'), 1).setText('v2')
        params = self.metadata.a1111_parameters()
        assert params is not None
        self.assertEqual('v2', params.get('Version'))
        self.assertEqual('a: 1, b: 2', params.get('Lora hashes'))

    def test_add_and_remove_field(self) -> None:
        """Add field appends a field, and Remove field deletes the selected one."""
        self.window._add_field()
        params = self.metadata.a1111_parameters()
        assert params is not None
        self.assertIsNotNone(params.get('New field'))
        self.window._field_table.setCurrentCell(self._row('Version'), 0)
        self.window._remove_field()
        params = self.metadata.a1111_parameters()
        assert params is not None
        self.assertIsNone(params.get('Version'))

    def test_apply_and_update_field(self) -> None:
        """Per-field Apply writes the editor setting, Update writes the saved value."""
        self.window._apply_fields(('Steps',))
        self.assertEqual(20, Cache().get(Cache.SAMPLING_STEPS))
        Cache().set(Cache.SAMPLING_STEPS, 31)
        self.window.refresh()
        steps_status = self.window._field_table.item(self._row('Steps'), 3)
        self.assertEqual('Differs', steps_status.text())
        self.window._update_fields(('Steps',))
        params = self.metadata.a1111_parameters()
        assert params is not None
        self.assertEqual('31', params.get('Steps'))
        self.assertEqual('Same', self.window._field_table.item(self._row('Steps'), 3).text())

    def test_update_all_keeps_unmapped_fields(self) -> None:
        """Update all replaces mapped fields and keeps the rest."""
        Cache().set(Cache.SEED, 99)
        self.window._update_all()
        params = self.metadata.a1111_parameters()
        assert params is not None
        self.assertEqual('99', params.get('Seed'))
        self.assertEqual('v1.9', params.get('Version'))
        self.assertEqual('a: 1, b: 2', params.get('Lora hashes'))

    def test_apply_all_reports_rejected_field(self) -> None:
        """A value the editor can't take is reported and not applied, and the other fields still apply."""
        self.metadata.set_parameters(PARAMETERS.replace('Steps: 20', 'Steps: many'))
        self.window.refresh()
        before = Cache().get(Cache.SAMPLING_STEPS)
        self.window._apply_all()
        self.assertEqual(before, Cache().get(Cache.SAMPLING_STEPS))
        self.assertIn('many', self.window._status_label.text())
        self.assertEqual(5, Cache().get(Cache.SEED))

    def test_raw_text_edit(self) -> None:
        """The raw text box edits the saved parameters string."""
        self.window._raw_toggle.setChecked(True)
        self.window._raw_box.setValue('raw text')
        self.assertEqual('raw text', self.metadata.parameters)

    def test_copy(self) -> None:
        """Copy puts the parameters text on the clipboard."""
        self.window._copy_parameters()
        self.assertEqual(PARAMETERS, QApplication.clipboard().text())

    def test_hidden_editor_buttons(self) -> None:
        """Without editor buttons, no Apply or Update button is visible."""
        window = MetadataWindow(self.metadata, show_editor_buttons=False)
        window.show()
        self.assertFalse(window._apply_all_button.isVisible())
        self.assertFalse(window._update_all_button.isVisible())

    def test_text_entries(self) -> None:
        """Text entries can be added, edited, renamed and removed."""
        self.window._add_text_entry()
        self.assertIn('new_entry', self.metadata.text)
        self.window._text_value_box.setValue('hello')
        self.assertEqual('hello', self.metadata.text['new_entry'])
        row = self.window._text_keys.index('new_entry')
        self.window._text_table.item(row, 0).setText('renamed')
        self.assertEqual('hello', self.metadata.text['renamed'])
        self.assertNotIn('new_entry', self.metadata.text)
        self.window._text_table.selectRow(self.window._text_keys.index('renamed'))
        self.window._remove_text_entry()
        self.assertNotIn('renamed', self.metadata.text)

    def test_exif_edit_and_location_removal(self) -> None:
        """Text tags are editable, other tags removable, and Remove location data clears the GPS IFD."""
        self.metadata.set_exif_text(None, ExifTags.Base.Artist, 'someone')
        self.metadata._set_tag(IFD.GPSInfo, ExifTags.GPS.GPSLatitudeRef, 'N')  # pylint: disable=protected-access
        self.window.refresh()
        artist_row = [entry.tag for entry in self.window._exif_rows].index(ExifTags.Base.Artist)
        self.window._exif_table.item(artist_row, 2).setText('another')
        self.assertEqual('another', self.metadata.exif[ExifTags.Base.Artist])
        self.assertTrue(self.window._remove_location_button.isEnabled())
        self.window._remove_location()
        self.assertNotIn(IFD.GPSInfo, [entry.ifd for entry in self.metadata.exif_entries()])
        self.assertFalse(self.window._remove_location_button.isEnabled())

    def test_other_views(self) -> None:
        """ComfyUI JSON appears as a pretty-printed view and a node list; plain text entries don't."""
        self.metadata.text['prompt'] = '{"3": {"class_type": "KSampler", "inputs": {"seed": 1}}}'
        self.window.refresh()
        names = [self.window._other_selector.itemText(i) for i in range(self.window._other_selector.count())]
        self.assertEqual(['ComfyUI: prompt', 'ComfyUI: nodes'], names)
        self.window._other_selector.setCurrentIndex(1)
        self.assertIn('KSampler', self.window._other_view.toPlainText())

    def test_remove_all_and_set_metadata(self) -> None:
        """Remove all metadata empties the model, and set_metadata switches to another image's."""
        edits: list[bool] = []
        self.window.metadata_edited.connect(lambda: edits.append(True))
        self.window._remove_all()
        self.assertTrue(self.metadata.is_empty)
        self.assertGreater(len(edits), 0)
        other = ImageMetadata({'parameters': PARAMETERS})
        self.window.set_metadata(other)
        self.assertEqual('a cat', self.window._prompt_box.value())

    def test_save_note(self) -> None:
        """The note names what each kind of save keeps."""
        self.assertIn('every text entry', save_format_note('a.png'))
        self.assertIn('only the generation parameters', save_format_note('a.gif'))
        self.assertIn('image description', save_format_note('a.jpg'))
        self.assertIn('keep no metadata', save_format_note('a.bmp'))
        self.assertIn('Formats that keep metadata', save_format_note(''))
