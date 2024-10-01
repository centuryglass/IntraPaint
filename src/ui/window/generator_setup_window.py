"""Preview, configure, and activate different image generators."""
from typing import List, Optional

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QMouseEvent, QImage, QFont, QResizeEvent, QIcon
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QApplication, QLabel, QPushButton, QTextBrowser

from src.controller.image_generation.image_generator import ImageGenerator
from src.ui.layout.bordered_widget import BorderedWidget
from src.ui.layout.divider import Divider
from src.ui.layout.draggable_divider import DraggableDivider
from src.ui.widget.image_widget import ImageWidget
from src.util.shared_constants import APP_ICON_PATH

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.window.generator_setup_window'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


GEN_SETUP_WINDOW_TITLE = _tr('Image Generator Selection')
GEN_SETUP_ACTIVATE_BUTTON_TEXT = _tr('Activate')
GEN_STATUS_HEADER = _tr('<h2>Status:</h2>')
ACTIVE_STATUS_TEXT = _tr('Generator is active.')
AVAILABLE_STATUS_TEXT = _tr('Generator is available.')
GEN_LIST_HEADER = _tr('<h1>Generator Options:</h1>')
PREVIEW_IMAGE_TITLE = _tr('<u>Preview: {generator_name}</u>')

SCROLL_CONTENT_MARGIN = 25


class GeneratorSetupWindow(QWidget):
    """Preview, configure, and activate different image generators."""

    activate_signal = Signal(ImageGenerator)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(GEN_SETUP_WINDOW_TITLE)
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self._layout = QHBoxLayout(self)
        self._option_list = BorderedWidget()
        self._option_list_layout = QVBoxLayout(self._option_list)
        self._option_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._option_list_layout.addWidget(QLabel(GEN_LIST_HEADER))
        self._option_spacer = QWidget(self)
        self._option_list_layout.addWidget(self._option_spacer, stretch=10)
        self._layout.addWidget(self._option_list, stretch=10)
        self._layout.addWidget(DraggableDivider())
        self._detail_panel = QWidget(self)
        self._detail_panel_layout = QVBoxLayout(self._detail_panel)
        self._detail_panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignVCenter)
        self._layout.addWidget(self._detail_panel, stretch=50)

        self._title_layout = QHBoxLayout()
        self._title_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignHCenter)
        self._preview_image = ImageWidget(QImage())
        self._preview_title = QLabel('', parent=self)
        self._preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._option_list_layout.addWidget(Divider(Qt.Orientation.Horizontal))
        self._option_list_layout.addWidget(self._preview_title)
        self._option_list_layout.addWidget(self._preview_image, stretch=5)
        self._option_list_layout.addSpacing(20)
        self._title = QLabel()
        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._title_layout.addWidget(self._title, stretch=2)
        self._detail_panel_layout.addLayout(self._title_layout)

        def _setup_rich_text_section():
            text_widget = QTextBrowser()
            text_widget.setOpenExternalLinks(True)
            text_widget.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            return text_widget

        self._description = _setup_rich_text_section()
        self._detail_panel_layout.addWidget(self._description, stretch=20)

        self._detail_panel_layout.addWidget(DraggableDivider())

        self._setup = _setup_rich_text_section()
        self._detail_panel_layout.addWidget(self._setup, stretch=20)
        self._detail_panel_layout.addWidget(DraggableDivider())

        self._status = _setup_rich_text_section()
        self._detail_panel_layout.addWidget(self._status, stretch=1)

        self._activate_button = QPushButton()
        self._activate_button.setText(GEN_SETUP_ACTIVATE_BUTTON_TEXT)
        self._detail_panel_layout.addWidget(self._activate_button)
        self._activate_button.clicked.connect(lambda _unused_param: self.activate_signal.emit(self._selected_generator))

        self._generators: List[ImageGenerator] = []
        self._generator_list_widgets: List[_GeneratorWidget] = []
        self._selected_generator: Optional[ImageGenerator] = None

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Make sure text doesn't need horizontal scrolling"""
        inner_width = self._detail_panel.width() - SCROLL_CONTENT_MARGIN
        for scroll_widget in (self._description, self._setup, self._status):
            scroll_widget.setMaximumWidth(inner_width)

    def _update_status_text(self, status_text: str) -> None:
        self._status.setHtml(self._status.toPlainText() + f'<p>{status_text}</p>')

    def add_generator(self, generator: ImageGenerator) -> None:
        """Add a new generator to the list"""
        assert generator not in self._generators
        self._generators.append(generator)
        widget = _GeneratorWidget(generator)
        self._generator_list_widgets.append(widget)
        layout_index = self._option_list_layout.indexOf(self._option_spacer)
        self._option_list_layout.insertWidget(layout_index, widget)

    def select_generator(self, generator: ImageGenerator) -> None:
        """Select a generator in the list, showing details"""
        if self._selected_generator is not None:
            self._selected_generator.status_signal.disconnect(self._update_status_text)
        self._selected_generator = generator
        self._title.setText(f'<h1>{generator.get_display_name()}</h1>')
        self._status.setText(GEN_STATUS_HEADER)
        generator.status_signal.connect(self._update_status_text)
        selected_widget = None
        for generator_widget in self._generator_list_widgets:
            generator_widget.set_selected(generator_widget.generator == generator)
            if generator_widget.generator == generator:
                selected_widget = generator_widget
        assert selected_widget is not None
        self._description.setText(generator.get_description())
        self._preview_image.image = generator.get_preview_image()
        preview_text = PREVIEW_IMAGE_TITLE.format(generator_name=generator.get_display_name())
        self._preview_title.setText(preview_text)
        self._setup.setText(generator.get_setup_text())
        self._activate_button.setEnabled(not selected_widget.active)
        if selected_widget.active:
            if ACTIVE_STATUS_TEXT not in self._status.toPlainText():
                self._update_status_text(ACTIVE_STATUS_TEXT)
        elif generator.is_available():
            self._update_status_text(AVAILABLE_STATUS_TEXT)

    def mark_active_generator(self, generator: ImageGenerator) -> None:
        """Set which generator the window should show as active."""
        for generator_widget in self._generator_list_widgets:
            generator_widget.set_active(generator_widget.generator == generator)
        self.select_generator(generator)


class _GeneratorWidget(QPushButton):

    def __init__(self, generator: ImageGenerator):
        super().__init__(generator.get_display_name())
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self._generator = generator
        self._active = False
        self._selected = False

    @property
    def active(self) -> bool:
        """Whether this widget's generator is the one currently in use."""
        return self._active

    @property
    def generator(self) -> ImageGenerator:
        """Returns the widget's image generator."""
        return self._generator

    def _window(self) -> 'GeneratorSetupWindow':
        list_widget = self.parent()
        assert isinstance(list_widget, BorderedWidget)
        window = list_widget.parent()
        assert isinstance(window, GeneratorSetupWindow)
        return window

    def _update_text_formatting(self) -> None:
        font = self.font()
        font.setWeight(QFont.Weight.Bold if self._active else QFont.Weight.Normal)
        font.setUnderline(self._selected)
        self.setFont(font)

    def set_selected(self, is_selected: bool) -> None:
        """Makes this widget's generator the active one within the window"""
        if is_selected == self._selected:
            return
        self._selected = is_selected
        self._update_text_formatting()
        if is_selected:
            self._window().select_generator(self._generator)

    def set_active(self, is_active: bool) -> None:
        """Marks this generator as the one currently used by IntraPaint"""
        if is_active == self._active:
            return
        self._active = is_active
        self._update_text_formatting()

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Selects this item's generator to show details"""
        self.set_selected(True)
