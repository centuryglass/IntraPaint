"""Tests the metadata window: edits made through its widgets change its working copy, Apply hands the copy back, and
the editor buttons read and write the editor's settings."""
import sys

from PIL import ExifTags, Image
from PIL.ExifTags import IFD
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from src.config.cache import Cache
from src.image.image_metadata import ImageMetadata
from src.ui.window.metadata_window import MetadataWindow, save_format_note, SOURCE_IPTC, SOURCE_XMP
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

PARAMETERS = ('a cat\nNegative prompt: blur\nSteps: 20, Sampler: Euler a, CFG scale: 7, Seed: 5, Size: 512x768, '
              'Version: v1.9, Lora hashes: "a: 1, b: 2"')


def _delete_removed_widgets() -> None:
    """Runs the deferred deletes of cell widgets a table replaced, as the event loop would between refreshes."""
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _iptc_dataset(dataset: int, value: bytes) -> bytes:
    return bytes([0x1C, 2, dataset]) + len(value).to_bytes(2, 'big') + value


class MetadataWindowTest(IntraPaintTestCase):
    """Builds the window over an `ImageMetadata` with A1111 parameters."""

    def setUp(self) -> None:
        super().setUp()
        self.source = ImageMetadata({'parameters': PARAMETERS, 'other': 'value'})
        self.window = MetadataWindow(self.source)
        self.applied: list[ImageMetadata] = []
        self.window.metadata_applied.connect(self.applied.append)

    @property
    def metadata(self) -> ImageMetadata:
        """The window's working copy."""
        return self.window._metadata

    def _row(self, field: str) -> int:
        return self.window._field_rows.index(field)

    def _all_row(self, name: str) -> int:
        return [row.name for row in self.window._metadata_rows].index(name)

    def test_edits_wait_for_apply(self) -> None:
        """Edits change the working copy only, until Apply changes hands a copy to the owner."""
        self.window._prompt_box.setValue('a dog')
        self.assertEqual(PARAMETERS, self.source.parameters)
        self.assertTrue(self.window.is_modified)
        self.assertTrue(self.window._footer.confirm_button.isEnabled())
        self.window.apply_changes()
        self.assertEqual(1, len(self.applied))
        self.assertEqual(PARAMETERS.replace('a cat', 'a dog'), self.applied[0].parameters)
        self.assertFalse(self.window.is_modified)

    def test_set_metadata_discards_edits(self) -> None:
        """Showing another image's metadata drops unapplied edits."""
        self.window._prompt_box.setValue('a dog')
        self.window.set_metadata(ImageMetadata({'parameters': PARAMETERS}))
        self.assertFalse(self.window.is_modified)
        self.assertEqual('a cat', self.window._prompt_box.value())
        self.assertFalse(self.window._footer.confirm_button.isEnabled())

    def test_close_discards_edits(self) -> None:
        """Closing without applying drops the edits, and an applied edit survives a close."""
        self.window._prompt_box.setValue('a dog')
        self.window.close()
        self.assertEqual(PARAMETERS, self.metadata.parameters)
        self.window._prompt_box.setValue('a bird')
        self.window.apply_changes()
        self.window.close()
        self.assertEqual(PARAMETERS.replace('a cat', 'a bird'), self.metadata.parameters)

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

    def test_field_value_box_edit(self) -> None:
        """The value box under the table shows and edits the selected field's full value."""
        self.window._field_table.selectRow(self._row('Lora hashes'))
        self.assertEqual('a: 1, b: 2', self.window._field_value_box.value())
        self.window._field_value_box.setValue('c: 3')
        params = self.metadata.a1111_parameters()
        assert params is not None
        self.assertEqual('c: 3', params.get('Lora hashes'))

    def test_refresh_after_rows_are_rebuilt(self) -> None:
        """Refreshing after the table replaced its row buttons doesn't touch the deleted buttons."""
        self.window._add_field()
        _delete_removed_widgets()
        self.window.refresh()
        _delete_removed_widgets()
        self.window._update_all()
        self.window.refresh()

    def test_update_all_on_empty_metadata_then_reopen(self) -> None:
        """Update all on an image with no metadata, then showing it again, refreshes without error."""
        window = MetadataWindow(ImageMetadata())
        window._update_all()
        _delete_removed_widgets()
        window.set_metadata(ImageMetadata())
        _delete_removed_widgets()
        window.refresh()

    def test_add_and_remove_field(self) -> None:
        """Add field appends a field, and Remove field deletes the selected one."""
        self.window._add_field()
        params = self.metadata.a1111_parameters()
        assert params is not None
        self.assertIsNotNone(params.get('New field'))
        self.window._field_table.selectRow(self._row('Version'))
        self.assertTrue(self.window._remove_field_button.isEnabled())
        self.window._remove_field()
        params = self.metadata.a1111_parameters()
        assert params is not None
        self.assertIsNone(params.get('Version'))

    def test_field_buttons_follow_what_a1111_can_read(self) -> None:
        """Add field needs a settings line, and Remove field needs a selection and leaves at least three fields."""
        window = MetadataWindow(ImageMetadata({'parameters': 'just a prompt'}))
        self.assertFalse(window._add_field_button.isEnabled())
        window._add_field()
        self.assertEqual('just a prompt', window._metadata.parameters)
        self.window._field_table.clearSelection()
        self.assertFalse(self.window._remove_field_button.isEnabled())
        short = MetadataWindow(ImageMetadata({'parameters': 'p\nSteps: 1, Sampler: Euler, Seed: 2'}))
        short._field_table.selectRow(0)
        self.assertFalse(short._remove_field_button.isEnabled())

    def test_apply_and_update_field(self) -> None:
        """Per-field Apply writes the editor setting, Update writes the saved value, and both disable once equal."""
        self.window._apply_fields(('Steps',))
        self.assertEqual(20, Cache().get(Cache.SAMPLING_STEPS))
        apply_button, update_button = self.window._row_buttons['Steps']
        self.assertFalse(apply_button.isEnabled())
        self.assertEqual('', self.window._field_table.item(self._row('Steps'), 2).text())
        Cache().set(Cache.SAMPLING_STEPS, 31)
        self.assertTrue(update_button.isEnabled())
        self.assertEqual('31', self.window._field_table.item(self._row('Steps'), 2).text())
        self.window._update_fields(('Steps',))
        params = self.metadata.a1111_parameters()
        assert params is not None
        self.assertEqual('31', params.get('Steps'))
        self.assertFalse(update_button.isEnabled())

    def test_string_seed_is_not_marked_different(self) -> None:
        """A seed the spinbox stored as a string matches the same saved seed."""
        Cache().set(Cache.SEED, '5')
        self.assertEqual('', self.window._field_table.item(self._row('Seed'), 2).text())
        self.assertFalse(self.window._row_buttons['Seed'][0].isEnabled())

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
        window = MetadataWindow(ImageMetadata({'parameters': PARAMETERS.replace('Steps: 20', 'Steps: many')}))
        before = Cache().get(Cache.SAMPLING_STEPS)
        window._apply_all()
        self.assertEqual(before, Cache().get(Cache.SAMPLING_STEPS))
        self.assertIn('many', window._status_label.text())
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
        """Without editor buttons, no Apply or Update button or editor column is visible."""
        window = MetadataWindow(self.source, show_editor_buttons=False)
        window.show()
        self.assertFalse(window._apply_all_button.isVisible())
        self.assertFalse(window._update_all_button.isVisible())
        self.assertTrue(window._field_table.isColumnHidden(2))
        self.assertEqual({}, window._row_buttons)

    def test_text_entries(self) -> None:
        """Text entries can be added, edited, renamed and removed on the All metadata tab."""
        self.window._add_text_entry()
        self.assertIn('new_entry', self.metadata.text)
        self.window._row_value_box.setValue('hello')
        self.assertEqual('hello', self.metadata.text['new_entry'])
        self.window._all_table.item(self._all_row('new_entry'), 1).setText('renamed')
        self.assertEqual('hello', self.metadata.text['renamed'])
        self.assertNotIn('new_entry', self.metadata.text)
        self.window._all_table.selectRow(self._all_row('renamed'))
        self.window._remove_row()
        self.assertNotIn('renamed', self.metadata.text)

    def test_exif_edit_and_location_removal(self) -> None:
        """Text tags are editable, other tags removable, and Remove location data clears the GPS IFD."""
        self.metadata.set_exif_text(None, ExifTags.Base.Artist, 'someone')
        self.metadata._set_tag(IFD.GPSInfo, ExifTags.GPS.GPSLatitudeRef, 'N')  # pylint: disable=protected-access
        self.window.refresh()
        self.window._all_table.item(self._all_row('Artist'), 2).setText('another')
        self.assertEqual('another', self.metadata.exif[ExifTags.Base.Artist])
        self.assertTrue(self.window._remove_location_button.isEnabled())
        self.window._remove_location()
        self.assertNotIn(IFD.GPSInfo, [entry.ifd for entry in self.metadata.exif_entries()])
        self.assertFalse(self.window._remove_location_button.isEnabled())

    def test_save_note_for_jpeg_data(self) -> None:
        """Only JPEG and .ora saves keep the comment and IPTC data, and an XMP packet kept as a PNG text entry counts as
        XMP."""
        metadata = ImageMetadata({'comment': 'a note', 'XML:com.adobe.xmp': '<x/>'},
                                 format_info={'photoshop': {0x0404: _iptc_dataset(25, b'tag')}})
        self.assertEqual('Saving as JPEG keeps all of this metadata.', save_format_note(metadata, 'a.jpg'))
        self.assertEqual('Saving as TIFF keeps: XMP. It drops: comment, IPTC.', save_format_note(metadata, 'a.tiff'))
        self.assertEqual('Saving as PNG keeps: comment, XMP. It drops: IPTC.', save_format_note(metadata, 'a.png'))
        self.assertEqual('Saving as ORA keeps all of this metadata.', save_format_note(metadata, 'a.ora'))

    def test_save_note_for_ora_keeps_jpeg_data(self) -> None:
        """An .ora save keeps a JPEG's EXIF tags, XMP packet and IPTC data."""
        exif = Image.Exif()
        exif[ExifTags.Base.Make] = 'Camera Co'
        metadata = ImageMetadata({'comment': 'a note'}, exif,
                                 {'xmp': b'<x/>', 'photoshop': {0x0404: _iptc_dataset(25, b'tag')}})
        self.assertEqual('Saving as ORA keeps all of this metadata.', save_format_note(metadata, 'a.ora'))

    def test_remove_location_covers_iptc_and_xmp(self) -> None:
        """Remove location data is available for IPTC and XMP place fields alone, and clears them."""
        iptc = _iptc_dataset(90, b'Anytown') + _iptc_dataset(25, b'tag')
        xmp = b'<x xmlns:ps="http://ns.adobe.com/photoshop/1.0/"><ps:Country>USA</ps:Country></x>'
        window = MetadataWindow(ImageMetadata(format_info={'photoshop': {0x0404: iptc}, 'xmp': xmp}))
        self.assertTrue(window._remove_location_button.isEnabled())
        window._remove_location()
        self.assertFalse(window._remove_location_button.isEnabled())
        self.assertEqual([(SOURCE_IPTC, 'Keywords', 'tag')],
                         [(row.source, row.name, row.value) for row in window._metadata_rows
                          if row.source == SOURCE_IPTC])
        self.assertNotIn('Country', window._metadata.xmp or '')

    def test_iptc_and_xmp_rows_are_read_only(self) -> None:
        """IPTC datasets and the XMP packet are listed, and can't be edited or removed."""
        iptc = _iptc_dataset(90, b'Anytown') + _iptc_dataset(101, b'United States')
        window = MetadataWindow(ImageMetadata(format_info={'photoshop': {0x0404: iptc}, 'xmp': b'<x:xmpmeta/>'}))
        sources = [(row.source, row.name, row.value) for row in window._metadata_rows]
        self.assertIn((SOURCE_IPTC, 'City', 'Anytown'), sources)
        self.assertIn((SOURCE_XMP, 'XMP packet', '<x:xmpmeta/>'), sources)
        window._all_table.selectRow(0)
        self.assertFalse(window._remove_row_button.isEnabled())
        self.assertTrue(window._row_value_box.isReadOnly())

    def test_remove_buttons_need_a_target(self) -> None:
        """Remove needs a selected row, and Remove all metadata needs metadata."""
        self.assertFalse(self.window._remove_row_button.isEnabled())
        self.assertTrue(self.window._remove_all_button.isEnabled())
        window = MetadataWindow(ImageMetadata(format_info={'dpi': (72, 72)}))
        self.assertFalse(window._remove_all_button.isEnabled())

    def test_other_views(self) -> None:
        """ComfyUI JSON appears as a pretty-printed view and a node list; plain text entries don't."""
        self.metadata.text['prompt'] = '{"3": {"class_type": "KSampler", "inputs": {"seed": 1}}}'
        self.window.refresh()
        names = [self.window._other_selector.itemText(i) for i in range(self.window._other_selector.count())]
        self.assertEqual(['ComfyUI: prompt', 'ComfyUI: nodes'], names)
        self.window._other_selector.setCurrentIndex(1)
        self.assertIn('KSampler', self.window._other_view.toPlainText())

    def test_remove_all(self) -> None:
        """Remove all metadata empties the working copy and disables itself."""
        self.window._remove_all()
        self.assertFalse(self.metadata.has_removable_data)
        self.assertFalse(self.window._remove_all_button.isEnabled())
        self.assertTrue(self.window.is_modified)

    def test_save_note(self) -> None:
        """The note names what a save to each format keeps and drops of this image's metadata."""
        metadata = ImageMetadata({'parameters': PARAMETERS, 'other': 'value'}, format_info={'xmp': b'<x/>'})
        metadata.set_exif_text(None, ExifTags.Base.Artist, 'someone')
        self.assertEqual('Saving as PNG keeps all of this metadata.', save_format_note(metadata, 'a.png'))
        self.assertEqual('Saving as JPEG keeps: generation parameters, EXIF tags, XMP. It drops: text entries (other).',
                         save_format_note(metadata, 'a.jpg'))
        self.assertEqual('Saving as WEBP keeps: generation parameters, EXIF tags, XMP. It drops: text entries (other).',
                         save_format_note(metadata, 'a.webp'))
        self.assertIn('It drops: text entries (other), EXIF tags, XMP', save_format_note(metadata, 'a.gif'))
        self.assertIn('It drops: text entries (other), XMP', save_format_note(metadata, 'a.jp2'))
        self.assertIn('keep no metadata', save_format_note(metadata, 'a.bmp'))
        self.assertIn('hasn\'t been saved', save_format_note(metadata, ''))
        self.assertEqual('This image has no metadata to save.', save_format_note(ImageMetadata(), 'a.png'))
        self.assertEqual('Saving as PNG keeps all of this metadata.',
                         save_format_note(ImageMetadata({'parameters': PARAMETERS}), 'a.png'))
