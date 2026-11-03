"""Popup modal window used for creating a new image at an arbitrary size.

The size sits in a `GeometryBlock` with an aspect lock, above a list of size presets that fill it in. The background
color is a row of swatches, where the custom swatch opens the color dialog.
"""
from typing import Optional, cast

from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, Qt
from PySide6.QtWidgets import QApplication, QButtonGroup, QDialog, QHBoxLayout, QPushButton, QToolButton, QVBoxLayout, \
    QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.input_fields import geometry_block
from src.ui.input_fields.geometry_block import GeometryBlock
from src.ui.modal.color_dialog import ColorDialog
from src.ui.modal.dialog_footer import DialogFooter
from src.ui.widget.panel_section import PanelSection
from src.util.shared_constants import APP_ICON_PATH
from src.util.visual.image_utils import get_color_icon

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.modal.new_image_modal'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


CREATE_IMAGE_TITLE = _tr('Create new image')
CREATE_BUTTON_TEXT = _tr('Create')
SIZE_SECTION_TITLE = _tr('Size')
PRESETS_SECTION_TITLE = _tr('Size presets')
BACKGROUND_SECTION_TITLE = _tr('Background')

PRESET_DEFAULT = _tr('Default image size ({width} x {height})')
PRESET_DEFAULT_TOOLTIP = _tr('Use the default image size from the application settings.')
PRESET_GENERATION_RESOLUTION = _tr('Generation resolution ({width} x {height})')
PRESET_GENERATION_RESOLUTION_TOOLTIP = _tr('Use the size that images are generated at.')
PRESET_GENERATION_AREA = _tr('Generation area ({width} x {height})')
PRESET_GENERATION_AREA_TOOLTIP = _tr('Use the size of the current image generation area.')
PRESET_CLIPBOARD = _tr('Clipboard image ({width} x {height})')
PRESET_CLIPBOARD_TOOLTIP = _tr('Use the size of the image on the clipboard.')

BACKGROUND_COLOR_OPTION_TRANSPARENT = _tr('Transparent')
BACKGROUND_COLOR_OPTION_WHITE = _tr('White')
BACKGROUND_COLOR_OPTION_BLACK = _tr('Black')
BACKGROUND_COLOR_OPTION_CUSTOM = _tr('Custom color...')

MIN_PX_VALUE = 1
SWATCH_SIZE = 28
CUSTOM_DEFAULT_COLOR = QColor('#ff808080')


class NewImageModal(QDialog):
    """Popup modal window used for creating a new image at an arbitrary size.

    `generation_area_size` and `clipboard_size` add size presets when the caller has them.
    """

    def __init__(self, default_width: int, default_height: int, generation_area_size: Optional[QSize] = None,
                 clipboard_size: Optional[QSize] = None) -> None:
        super().__init__()
        self.setWindowIcon(QIcon(APP_ICON_PATH))
        self.setModal(True)
        self.setWindowTitle(CREATE_IMAGE_TITLE)
        self._create = False

        max_size = cast(QSize, AppConfig().get(AppConfig.MAX_IMAGE_SIZE))
        self._geometry = GeometryBlock(show_position=False, parent=self)
        self._geometry.set_limits(geometry_block.WIDTH, MIN_PX_VALUE, max_size.width())
        self._geometry.set_limits(geometry_block.HEIGHT, MIN_PX_VALUE, max_size.height())
        self._geometry.set_values(w=default_width, h=default_height)

        # Size presets, skipping any that repeat an earlier size:
        presets: list[tuple[str, str, QSize]] = [
            (PRESET_DEFAULT, PRESET_DEFAULT_TOOLTIP, QSize(default_width, default_height)),
            (PRESET_GENERATION_RESOLUTION, PRESET_GENERATION_RESOLUTION_TOOLTIP,
             cast(QSize, Cache().get(Cache.GENERATION_SIZE)))]
        if generation_area_size is not None:
            presets.append((PRESET_GENERATION_AREA, PRESET_GENERATION_AREA_TOOLTIP, generation_area_size))
        if clipboard_size is not None:
            presets.append((PRESET_CLIPBOARD, PRESET_CLIPBOARD_TOOLTIP, clipboard_size))
        self._preset_buttons: list[QPushButton] = []
        preset_body = QWidget(self)
        preset_layout = QVBoxLayout(preset_body)
        preset_layout.setContentsMargins(0, 0, 0, 0)
        seen: list[QSize] = []
        for label, tooltip, size in presets:
            size = QSize(min(max(size.width(), MIN_PX_VALUE), max_size.width()),
                         min(max(size.height(), MIN_PX_VALUE), max_size.height()))
            if size in seen:
                continue
            seen.append(size)
            button = QPushButton(label.format(width=size.width(), height=size.height()), preset_body)
            button.setToolTip(tooltip)
            button.setAutoDefault(False)
            button.clicked.connect(lambda _=False, preset=size: self._apply_preset(preset))
            preset_layout.addWidget(button)
            self._preset_buttons.append(button)

        # Background swatches:
        self._color = Cache().get_color(Cache.NEW_IMAGE_BACKGROUND_COLOR, Qt.GlobalColor.white)
        self._custom_color = QColor(CUSTOM_DEFAULT_COLOR)
        swatch_body = QWidget(self)
        swatch_layout = QHBoxLayout(swatch_body)
        swatch_layout.setContentsMargins(0, 0, 0, 0)
        self._swatch_group = QButtonGroup(self)
        self._swatch_group.setExclusive(True)
        self._swatches: dict[str, QToolButton] = {}
        for name, label in ((BACKGROUND_COLOR_OPTION_TRANSPARENT, BACKGROUND_COLOR_OPTION_TRANSPARENT),
                            (BACKGROUND_COLOR_OPTION_WHITE, BACKGROUND_COLOR_OPTION_WHITE),
                            (BACKGROUND_COLOR_OPTION_BLACK, BACKGROUND_COLOR_OPTION_BLACK),
                            (BACKGROUND_COLOR_OPTION_CUSTOM, BACKGROUND_COLOR_OPTION_CUSTOM)):
            button = QToolButton(swatch_body)
            button.setCheckable(True)
            button.setToolTip(label)
            button.setAutoRaise(False)
            button.setIconSize(QSize(SWATCH_SIZE, SWATCH_SIZE))
            self._swatch_group.addButton(button)
            swatch_layout.addWidget(button)
            self._swatches[name] = button
        swatch_layout.addStretch(1)
        self._swatches[BACKGROUND_COLOR_OPTION_TRANSPARENT].setIcon(get_color_icon(Qt.GlobalColor.transparent))
        self._swatches[BACKGROUND_COLOR_OPTION_WHITE].setIcon(get_color_icon(Qt.GlobalColor.white))
        self._swatches[BACKGROUND_COLOR_OPTION_BLACK].setIcon(get_color_icon(Qt.GlobalColor.black))
        self._selected_swatch = BACKGROUND_COLOR_OPTION_WHITE
        self._select_swatch_for_color(self._color)
        for name, button in self._swatches.items():
            button.clicked.connect(lambda _=False, swatch=name: self._swatch_clicked(swatch))

        self._footer = DialogFooter(CREATE_BUTTON_TEXT, self)
        self._footer.accepted.connect(self._confirm)
        self._footer.rejected.connect(self._cancel)
        self._create_button = self._footer.confirm_button
        self._cancel_button = self._footer.cancel_button

        self._layout = QVBoxLayout(self)
        self._layout.addWidget(PanelSection(SIZE_SECTION_TITLE, self._geometry))
        if len(self._preset_buttons) > 1:
            self._layout.addWidget(PanelSection(PRESETS_SECTION_TITLE, preset_body))
        else:
            preset_body.setVisible(False)
        self._layout.addWidget(PanelSection(BACKGROUND_SECTION_TITLE, swatch_body))
        self._layout.addStretch(1)
        self._layout.addWidget(self._footer)

    def _apply_preset(self, size: QSize) -> None:
        self._geometry.set_values(w=size.width(), h=size.height())

    def _select_swatch_for_color(self, color: QColor) -> None:
        if color == Qt.GlobalColor.transparent:
            name = BACKGROUND_COLOR_OPTION_TRANSPARENT
        elif color == Qt.GlobalColor.white:
            name = BACKGROUND_COLOR_OPTION_WHITE
        elif color == Qt.GlobalColor.black:
            name = BACKGROUND_COLOR_OPTION_BLACK
        else:
            name = BACKGROUND_COLOR_OPTION_CUSTOM
            self._custom_color = QColor(color)
            self._update_custom_swatch()
        self._selected_swatch = name
        self._swatches[name].setChecked(True)

    def _update_custom_swatch(self) -> None:
        self._swatches[BACKGROUND_COLOR_OPTION_CUSTOM].setIcon(get_color_icon(self._custom_color))

    def _swatch_clicked(self, name: str) -> None:
        if name == BACKGROUND_COLOR_OPTION_CUSTOM:
            selection = ColorDialog.show_color_dialog(self._custom_color)
            if selection is None:
                self._swatches[self._selected_swatch].setChecked(True)
                return
            self._custom_color = selection
            self._update_custom_swatch()
        self._selected_swatch = name
        self._swatches[name].setChecked(True)

    def background_color(self) -> QColor:
        """Returns the color of the selected background swatch."""
        if self._selected_swatch == BACKGROUND_COLOR_OPTION_TRANSPARENT:
            return QColor(Qt.GlobalColor.transparent)
        if self._selected_swatch == BACKGROUND_COLOR_OPTION_WHITE:
            return QColor(Qt.GlobalColor.white)
        if self._selected_swatch == BACKGROUND_COLOR_OPTION_BLACK:
            return QColor(Qt.GlobalColor.black)
        return QColor(self._custom_color)

    def _confirm(self) -> None:
        self._create = True
        Cache().set_color(Cache.NEW_IMAGE_BACKGROUND_COLOR, self.background_color())
        self.hide()

    def _cancel(self) -> None:
        self._create = False
        self.hide()

    def new_size(self) -> QSize:
        """Returns the size entered in the size fields."""
        return QSize(int(self._geometry.value(geometry_block.WIDTH)), int(self._geometry.value(geometry_block.HEIGHT)))

    def show_image_modal(self) -> Optional[QSize]:
        """Shows the modal, then returns the user-entered size when closed."""
        self.exec()
        return self.new_size() if self._create else None
