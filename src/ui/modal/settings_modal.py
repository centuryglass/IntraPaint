"""The settings window (Edit > Settings): a category sidebar, a search field, and a page of sections per category.

- The controller fills it from `Config` objects with `load_from_config`, and generators add and remove their own
  categories. Controls are standalone: edits collect in a dict that `changes_saved` emits when Save is clicked, and
  nothing reaches a config before then.
- Each config subcategory is a `PanelSection` with a "Restore defaults" button. `create_setting_control` picks the
  control for each value.
- The search field hides rows whose label and description don't match, and sidebar categories left with no rows.
"""
import logging
import os
from typing import Any, Optional

from PySide6.QtCore import QSize, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, \
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from src.config.config import Config
from src.ui.input_fields.check_box import CheckBox
from src.ui.input_fields.line_edit import LineEdit
from src.ui.input_fields.setting_fields import ColorSettingField, DirectorySettingField, KeybindingField, \
    SizeSettingField
from src.ui.layout.label_column_layout import LabelColumnLayout, normalize_row_label
from src.ui.modal.dialog_footer import DialogFooter
from src.ui.modal.settings_controls import create_setting_control
from src.ui.widget.panel_section import PanelSection
from src.util.parameter import DynamicFieldWidget
from src.util.shared_constants import APP_ICON_PATH

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.settings_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


WINDOW_TITLE = _tr('Settings')
CONFIG_PATH_LABEL = _tr('Settings file locations')
CONFIG_PATH_TOOLTIP = _tr('IntraPaint saves its settings to these files. This section is only for reference, their'
                          ' locations cannot be changed here.')
SAVE_BUTTON_LABEL = _tr('Save')
SEARCH_PLACEHOLDER = _tr('Search settings')
NO_RESULTS_TEXT = _tr('No settings match the search.')
RESTORE_DEFAULTS_LABEL = _tr('Restore defaults')
RESTORE_DEFAULTS_TOOLTIP = _tr('Set every setting in this section back to its default value. Nothing changes until'
                               ' you click Save.')
OPEN_FOLDER_LABEL = _tr('Open folder')
OPEN_FOLDER_TOOLTIP = _tr('Show the folder containing this file')
FILE_CATEGORY = QApplication.translate('config.application_config', 'Files')

MIN_SIZE = QSize(660, 400)
SIDEBAR_MIN_WIDTH = 150
SIDEBAR_MAX_WIDTH = 220
PAGE_MARGIN = 8
# The widest a combo box, number field or segmented control is laid out:
SETTING_FIELD_MAX_WIDTH = 320
SECTION_SPACING = 6

logger = logging.getLogger(__name__)


class _Row:
    """One searchable row of a section: its control (or file path widget) and the text a search matches."""

    def __init__(self, key: str, label: str, tooltip: str, control: QWidget, config: Optional[Config]) -> None:
        self.key = key
        self.label = label
        self.tooltip = tooltip
        self.control = control
        self.config = config

    def matches(self, search: str) -> bool:
        """Returns whether the lowercase search text appears in the label or description."""
        return search in self.label.lower() or search in self.tooltip.lower()


class _Section:
    """A `PanelSection` and the rows in its form."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.rows: list[_Row] = []
        self.labels: list[QLabel] = []
        self.form_widget = QWidget()
        self.form = LabelColumnLayout(self.form_widget)
        self.panel = PanelSection(title, self.form_widget)
        self.restore_button: Optional[QPushButton] = None


class _Page:
    """The scrolling page for one category."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.sections: dict[str, _Section] = {}
        body = QWidget()
        self.layout = QVBoxLayout(body)
        self.layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        self.layout.setSpacing(SECTION_SPACING)
        self.layout.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setWidget(body)

    def align_labels(self) -> None:
        """Gives every row label on the page the width of the widest, so fields start at one x across sections."""
        labels = [label for section in self.sections.values() for label in section.labels]
        for label in labels:
            label.setMinimumWidth(0)
        width = max((label.sizeHint().width() for label in labels), default=0)
        for label in labels:
            label.setMinimumWidth(width)

    def rows(self) -> list[_Row]:
        """Returns every row on the page."""
        return [row for section in self.sections.values() for row in section.rows]


class SettingsModal(QDialog):
    """Edits application settings, and the settings that generators add while they are active."""

    changes_saved = Signal(dict)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(MIN_SIZE)

        self._pages: dict[str, _Page] = {}
        self._inputs: dict[str, DynamicFieldWidget] = {}
        self._input_sections: dict[str, tuple[str, str]] = {}
        self._changes: dict[str, Any] = {}
        self._config_paths: list[str] = []

        layout = QVBoxLayout(self)
        self._search = QLineEdit(self)
        self._search.setPlaceholderText(SEARCH_PLACEHOLDER)
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        content = QHBoxLayout()
        self._sidebar = QListWidget(self)
        self._sidebar.setMinimumWidth(SIDEBAR_MIN_WIDTH)
        self._sidebar.setMaximumWidth(SIDEBAR_MAX_WIDTH)
        self._sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._sidebar.currentRowChanged.connect(self._sidebar_row_changed)
        content.addWidget(self._sidebar)
        self._stack = QStackedWidget(self)
        self._no_results = QLabel(NO_RESULTS_TEXT, self)
        self._no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack.addWidget(self._no_results)
        content.addWidget(self._stack, stretch=1)
        layout.addLayout(content, stretch=1)

        self._footer = DialogFooter(SAVE_BUTTON_LABEL, self)
        self._footer.accepted.connect(self._save)
        self._footer.rejected.connect(self.hide)
        layout.addWidget(self._footer)

    # -----------------------------------------------------------------------------------------------------------------
    # Filling the window
    # -----------------------------------------------------------------------------------------------------------------

    def load_from_config(self, config: Config, categories: Optional[list[str]] = None) -> None:
        """Load settings from a Config object, or from a subset of Config object categories."""
        if categories is None:
            categories = config.get_categories()
        for category in categories:
            subcategories = config.get_subcategories(category)
            for subcategory in [None, *subcategories]:
                keys = [key for key in config.get_category_keys(category)
                        if config.get_subcategory(key) == subcategory]
                for key in keys:
                    if key in self._inputs:
                        continue
                    try:
                        control = create_setting_control(config, key)
                    except RuntimeError:
                        continue
                    self._connect_control(control, key)
                    self._add_setting(key, category, subcategory if subcategory is not None else category, control,
                                      config.get_label(key), config.get_tooltip(key), config)
        config_path = config.json_path
        if config_path is not None and config_path not in self._config_paths:
            self._config_paths.append(config_path)
            self._add_file_row(config_path)

    def add_custom_control(self, control_widget: DynamicFieldWidget, config: Config, key: str) -> None:
        """Adds a non-standard control to the window, replacing any control already shown for the key."""
        assert hasattr(control_widget, 'valueChanged')
        category = config.get_category(key)
        subcategory = config.get_subcategory(key)
        if key in self._inputs:
            self.remove_entry(config, key, category)
        control_widget.setValue(config.get(key))
        control_widget.setToolTip(config.get_tooltip(key))
        self._connect_control(control_widget, key)
        self._add_setting(key, category, subcategory if subcategory is not None else category, control_widget,
                          config.get_label(key), config.get_tooltip(key), config)

    def remove_entry(self, config: Config, key: str, category: Optional[str] = None) -> None:
        """Remove a single item from the modal"""
        if category is None:
            category = config.get_category(key)
        if category not in self._pages or key not in self._inputs:
            return
        page = self._pages[category]
        self._inputs.pop(key)
        self._changes.pop(key, None)
        section_title, _ = self._input_sections.pop(key)
        section = page.sections.get(section_title)
        if section is None:
            return
        for row in [row for row in section.rows if row.key == key]:
            section.rows.remove(row)
            section.labels = [label for label in section.labels if label.buddy() is not row.control]
            section.form.removeRow(row.control)
        if not section.rows:
            page.layout.removeWidget(section.panel)
            section.panel.deleteLater()
            del page.sections[section_title]
        page.align_labels()
        self._apply_filter(self._search.text())

    def remove_category(self, config: Config, category: str) -> None:
        """Remove a category from the modal"""
        page = self._pages.get(category)
        if page is None:
            return
        for key in config.get_category_keys(category):
            self.remove_entry(config, key, category)
        if page.sections:
            return
        del self._pages[category]
        self._stack.removeWidget(page.scroll)
        page.scroll.deleteLater()
        for row in range(self._sidebar.count()):
            if self._sidebar.item(row).text() == category:
                self._sidebar.takeItem(row)
                break
        self._apply_filter(self._search.text())

    def _connect_control(self, control: QWidget, key: str) -> None:
        assert hasattr(control, 'valueChanged')
        if isinstance(control, CheckBox):
            control.setText('')  # The row label names a check box.

        def _add_change(new_value: Any, name=key) -> None:
            self._changes[name] = new_value

        control.valueChanged.connect(_add_change)  # type: ignore[attr-defined]

    def _page(self, category: str) -> _Page:
        if category not in self._pages:
            page = _Page(category)
            self._pages[category] = page
            self._stack.addWidget(page.scroll)
            self._sidebar.addItem(category)
            if self._sidebar.currentRow() < 0:
                self._sidebar.setCurrentRow(0)
        return self._pages[category]

    def _section(self, page: _Page, title: str) -> _Section:
        if title not in page.sections:
            section = _Section(title)
            button = QPushButton(RESTORE_DEFAULTS_LABEL)
            button.setFlat(True)
            button.setToolTip(RESTORE_DEFAULTS_TOOLTIP)
            button.clicked.connect(lambda _checked=False, s=section: self._restore_defaults(s))
            section.restore_button = button
            section.panel.add_header_widget(button)
            page.sections[title] = section
            page.layout.insertWidget(page.layout.count() - 1, section.panel)
        return page.sections[title]

    def _add_setting(self, key: str, category: str, section_title: str, control: QWidget, label_text: str,
                     tooltip: str, config: Optional[Config]) -> None:
        page = self._page(category)
        section = self._section(page, section_title)
        if not isinstance(control, (CheckBox, ColorSettingField, DirectorySettingField, KeybindingField,
                                    SizeSettingField)):
            control.setMaximumWidth(SETTING_FIELD_MAX_WIDTH)
        label = section.form.add_row(label_text, control)
        label.setToolTip(tooltip)
        section.labels.append(label)
        page.align_labels()
        section.rows.append(_Row(key, normalize_row_label(label_text), tooltip, control, config))
        self._inputs[key] = control  # type: ignore[assignment]
        self._input_sections[key] = (section_title, category)
        self._apply_filter(self._search.text())

    def _add_file_row(self, path: str) -> None:
        page = self._page(FILE_CATEGORY)
        section = self._section(page, CONFIG_PATH_LABEL)
        if section.restore_button is not None:
            section.restore_button.hide()
            section.restore_button.deleteLater()
            section.restore_button = None
        field = LineEdit()
        field.setValue(path)
        field.setReadOnly(True)
        open_button = QPushButton(OPEN_FOLDER_LABEL)
        open_button.setToolTip(OPEN_FOLDER_TOOLTIP)
        open_button.clicked.connect(
            lambda _checked=False, folder=os.path.dirname(os.path.abspath(path)):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(field, stretch=1)
        row_layout.addWidget(open_button)
        row_widget.setToolTip(CONFIG_PATH_TOOLTIP)
        file_name = os.path.basename(path)
        section.labels.append(section.form.add_row(file_name, row_widget))
        page.align_labels()
        section.rows.append(_Row('', file_name, CONFIG_PATH_TOOLTIP + ' ' + path, row_widget, None))
        self._apply_filter(self._search.text())

    # -----------------------------------------------------------------------------------------------------------------
    # Showing, saving and refreshing
    # -----------------------------------------------------------------------------------------------------------------

    def show_modal(self, category: Optional[str] = None) -> None:
        """Shows the settings modal, on the page named `category` if it exists."""
        if category is not None and category in self._pages:
            self._search.clear()
            self._select_category(category)
        self.exec()

    def categories(self) -> list[str]:
        """Returns the names of the categories shown in the sidebar, in order."""
        return [self._sidebar.item(row).text() for row in range(self._sidebar.count())]

    def select_category(self, category: str) -> None:
        """Shows the page for `category` if it exists and has rows matching the search."""
        self._select_category(category)

    def set_tooltip(self, setting_name: str, tooltip: str) -> None:
        """Sets tooltip text for a setting, shown when the mouse hovers over its control."""
        if setting_name not in self._inputs:
            raise ValueError(f'{setting_name} not defined')
        self._inputs[setting_name].setToolTip(tooltip)

    def update_settings(self, settings: dict) -> None:
        """Sets all setting control widgets to match current settings values, and forgets their pending changes."""
        for key, new_value in settings.items():
            if key not in self._inputs:
                continue
            widget = self._inputs[key]
            try:
                self._set_control_value(widget, new_value)
            except (ValueError, TypeError) as err:
                logger.error(f'Failed to initialize "{key}"="{new_value}: {err}')
            self._changes.pop(key, None)

    @staticmethod
    def _set_control_value(widget: QWidget, new_value: Any) -> None:
        assert hasattr(widget, 'setValue')
        if isinstance(widget, (LineEdit, QLineEdit)) or hasattr(widget, 'currentData'):
            widget.setValue(str(new_value))  # type: ignore[attr-defined]
        elif isinstance(widget, CheckBox):
            widget.setValue(bool(new_value))
        elif new_value is None:
            widget.setValue(0)  # type: ignore[attr-defined]
        else:
            widget.setValue(new_value)  # type: ignore[attr-defined]

    def _save(self) -> None:
        self.changes_saved.emit(dict(self._changes))
        self.hide()

    def _restore_defaults(self, section: _Section) -> None:
        """Sets the controls in a section to their config defaults. The changes apply on Save."""
        for row in section.rows:
            if row.config is None or row.key == '':
                continue
            default = row.config.get_default(row.key)
            if default is None:
                continue
            try:
                self._set_control_value(row.control, default)
            except (ValueError, TypeError) as err:
                logger.error(f'Failed to restore default for "{row.key}": {err}')

    # -----------------------------------------------------------------------------------------------------------------
    # Categories and search
    # -----------------------------------------------------------------------------------------------------------------

    def _select_category(self, category: str) -> None:
        for row in range(self._sidebar.count()):
            if self._sidebar.item(row).text() == category and not self._sidebar.item(row).isHidden():
                self._sidebar.setCurrentRow(row)
                return

    def _sidebar_row_changed(self, row: int) -> None:
        item = self._sidebar.item(row) if row >= 0 else None
        if item is None or item.text() not in self._pages:
            self._stack.setCurrentWidget(self._no_results)
        else:
            self._stack.setCurrentWidget(self._pages[item.text()].scroll)

    def _apply_filter(self, text: str) -> None:
        """Shows only the rows matching the search text, and only the sections and categories that still have any."""
        search = text.strip().lower()
        any_shown = False
        for category, page in self._pages.items():
            page_shown = False
            for section in page.sections.values():
                section_match = search != '' and search in section.title.lower()
                section_shown = False
                for row in section.rows:
                    visible = search == '' or section_match or row.matches(search)
                    section.form.setRowVisible(row.control, visible)
                    section_shown = section_shown or visible
                section.panel.setVisible(section_shown)
                page_shown = page_shown or section_shown
            for row in range(self._sidebar.count()):
                item = self._sidebar.item(row)
                if item.text() == category:
                    item.setHidden(not page_shown)
            any_shown = any_shown or page_shown
        current = self._sidebar.currentItem()
        if current is None or current.isHidden():
            for row in range(self._sidebar.count()):
                if not self._sidebar.item(row).isHidden():
                    self._sidebar.setCurrentRow(row)
                    break
            else:
                self._sidebar.setCurrentRow(-1)
                self._stack.setCurrentWidget(self._no_results)
        self._no_results.setVisible(not any_shown)
