"""Tests SettingsModal and the controls it chooses for config values."""
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.ui.input_fields.setting_fields import ColorSettingField, DirectorySettingField, KeybindingField, \
    OptionSegmentsField, SizeSettingField, split_key_text
from src.ui.modal.settings_modal import SettingsModal
from test.base_test_case import IntraPaintTestCase


class SettingsModalTest(IntraPaintTestCase):
    """Tests categories, search, control types, restoring defaults and saving."""

    def setUp(self) -> None:
        super().setUp()
        self.parent = QWidget()
        self.modal = SettingsModal(self.parent)
        self.config = AppConfig()
        self.modal.load_from_config(self.config)

    def tearDown(self) -> None:
        self.modal.deleteLater()
        self.parent.deleteLater()
        super().tearDown()

    def test_categories_match_config(self) -> None:
        """Every config category with a control gets a sidebar entry, in definition order."""
        categories = self.modal.categories()
        self.assertIn('Interface', categories)
        self.assertIn('Alerts', categories)
        self.assertEqual(len(categories), len(set(categories)))

    def test_control_types(self) -> None:
        """Colors, paths, options and sizes get their dedicated controls."""
        inputs = self.modal._inputs  # pylint: disable=protected-access
        self.assertIsInstance(inputs[AppConfig.SELECTION_COLOR], ColorSettingField)
        self.assertFalse(inputs[AppConfig.SELECTION_COLOR].is_theme_default())
        ruler = inputs[AppConfig.RULER_GENERATION_AREA_COLOR]
        self.assertIsInstance(ruler, ColorSettingField)
        self.assertTrue(ruler.is_theme_default())
        self.assertIsInstance(inputs[AppConfig.ADDED_FONT_DIR], DirectorySettingField)
        self.assertIsInstance(inputs[AppConfig.ALWAYS_INIT_METADATA_ON_SAVE], OptionSegmentsField)
        self.assertIsInstance(inputs[AppConfig.MAX_IMAGE_SIZE], SizeSettingField)

    def test_metadata_options_show_labels(self) -> None:
        """The metadata options show Ask / Always / Never but store the raw option values."""
        control = self.modal._inputs[AppConfig.ALWAYS_INIT_METADATA_ON_SAVE]  # pylint: disable=protected-access
        assert isinstance(control, OptionSegmentsField)
        self.assertEqual([segment.label for segment in control.segments], ['Ask', 'Always', 'Never'])
        self.assertEqual([segment.value for segment in control.segments], ['always_ask', 'confirm', 'cancel'])

    def test_changes_collect_until_save(self) -> None:
        """Edits don't touch the config; Save emits them."""
        control = self.modal._inputs[AppConfig.SELECTION_COLOR]  # pylint: disable=protected-access
        assert isinstance(control, ColorSettingField)
        original = self.config.get(AppConfig.SELECTION_COLOR)
        control.setValue('#ff112233')
        self.assertEqual(self.config.get(AppConfig.SELECTION_COLOR), original)
        saved: list[dict] = []
        self.modal.changes_saved.connect(saved.append)
        self.modal._footer.confirm_button.click()  # pylint: disable=protected-access
        self.assertEqual(saved, [{AppConfig.SELECTION_COLOR: '#ff112233'}])

    def test_update_settings_clears_changes(self) -> None:
        """Refreshing the window from the config discards pending changes."""
        inputs = self.modal._inputs  # pylint: disable=protected-access
        control = inputs[AppConfig.ADDED_FONT_DIR]
        assert isinstance(control, DirectorySettingField)
        control.setValue('/tmp/fonts')
        self.modal.update_settings({AppConfig.ADDED_FONT_DIR: ''})
        self.assertEqual(control.value(), '')
        self.assertEqual(self.modal._changes, {})  # pylint: disable=protected-access

    def test_restore_defaults(self) -> None:
        """A section's Restore defaults button sets its controls back to the config defaults."""
        control = self.modal._inputs[AppConfig.ADDED_FONT_DIR]  # pylint: disable=protected-access
        assert isinstance(control, DirectorySettingField)
        control.setValue('/tmp/fonts')
        section = self.modal._pages['Files'].sections['Files']  # pylint: disable=protected-access
        assert section.restore_button is not None
        section.restore_button.click()
        self.assertEqual(control.value(), self.config.get_default(AppConfig.ADDED_FONT_DIR))

    def test_search_filters_rows_and_categories(self) -> None:
        """Search hides rows and categories without a match, and clearing it restores them."""
        self.modal._search.setText('font directory')  # pylint: disable=protected-access
        self.assertEqual(self.modal.categories().count('Files'), 1)
        sidebar = self.modal._sidebar  # pylint: disable=protected-access
        visible = [sidebar.item(i).text() for i in range(sidebar.count()) if not sidebar.item(i).isHidden()]
        self.assertEqual(visible, ['Files'])
        self.modal._search.setText('no such setting anywhere')  # pylint: disable=protected-access
        self.assertTrue(all(sidebar.item(i).isHidden() for i in range(sidebar.count())))
        self.modal._search.clear()  # pylint: disable=protected-access
        self.assertFalse(any(sidebar.item(i).isHidden() for i in range(sidebar.count())))

    def test_remove_category(self) -> None:
        """Removing a category removes its page, sidebar entry and inputs."""
        self.modal.remove_category(self.config, 'Alerts')
        self.assertNotIn('Alerts', self.modal.categories())
        self.assertNotIn(AppConfig.WARN_BEFORE_RGB_SAVE, self.modal._inputs)  # pylint: disable=protected-access

    def test_files_page_lists_settings_file(self) -> None:
        """The Files page lists the config file read-only."""
        rows = self.modal._pages['Files'].rows()  # pylint: disable=protected-access
        self.assertTrue(any(row.key == '' for row in rows))

    def test_keybindings_show_keycaps(self) -> None:
        """Key sequence settings show a badge per key."""
        self.modal.load_from_config(KeyConfig())
        key = KeyConfig().get_keys()[0]
        control = self.modal._inputs[key]  # pylint: disable=protected-access
        assert isinstance(control, KeybindingField)
        control.setValue('Ctrl+Shift+Z')
        self.assertEqual(control.badge_texts(), ['Ctrl', 'Shift', 'Z'])

    def test_size_field_round_trip(self) -> None:
        """A size setting reports the QSize it was given."""
        control = self.modal._inputs[AppConfig.DEFAULT_IMAGE_SIZE]  # pylint: disable=protected-access
        assert isinstance(control, SizeSettingField)
        control.setValue(QSize(640, 480))
        self.assertEqual(control.value(), QSize(640, 480))

    def test_split_key_text(self) -> None:
        """Key text splits into key names, keeping a plus key whole."""
        self.assertEqual(split_key_text('Ctrl+Shift+Z'), ['Ctrl', 'Shift', 'Z'])
        self.assertEqual(split_key_text('Ctrl++'), ['Ctrl', '+'])
        self.assertEqual(split_key_text(''), [])
