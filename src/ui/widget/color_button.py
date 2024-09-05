"""Opens a color picker to set a cached color, setting the brush color by default."""
from typing import Optional

from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QPushButton, QColorDialog, QApplication

from src.config.config_from_key import get_config_from_key
from src.util.image_utils import get_color_icon

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.brush_color_button'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


COLOR_BUTTON_LABEL = _tr('Color')
COLOR_BUTTON_TOOLTIP = _tr('Select paint color')


class ColorButton(QPushButton):
    """Opens a color picker to set the brush color."""

    def __init__(self, config_key: Optional[str] = 'last_brush_color'):
        super().__init__()
        self._color = QColor()
        self._icon = QPixmap()
        self._config_key = config_key
        if config_key is not None:
            config = get_config_from_key(config_key)
            config.connect(self, config_key, self._update_color)
            self._update_color(config.get(config_key))
        self.clicked.connect(self.select_color)
        self.setText(COLOR_BUTTON_LABEL)
        self.setToolTip(COLOR_BUTTON_TOOLTIP)

    def disconnect_config(self) -> None:
        """Disconnects this color button from its config value."""
        if self._config_key is not None:
            config = get_config_from_key(self._config_key)
            config.disconnect(self, self._config_key)
            self._config_key = None

    def _update_color(self, color: str | QColor) -> None:
        if isinstance(color, str):
            color = QColor(color) if QColor.isValidColor(color) else self._color
        if color != self._color:
            self._color = color
            self._icon = get_color_icon(color)
            self.setIcon(QIcon(self._icon))
            if self._config_key is not None:
                config = get_config_from_key(self._config_key)
                config.set(self._config_key, color.name(QColor.NameFormat.HexArgb))
            self.update()

    def select_color(self) -> None:
        """Open the color picker, then apply the selection if connected to config."""
        color_dialog = QColorDialog()
        color_dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        color_dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        selection = color_dialog.getColor(self._color)
        if selection != self._color:
            if self._config_key is not None:
                config = get_config_from_key(self._config_key)
                config.set(self._config_key, selection.name(QColor.NameFormat.HexArgb))
            else:
                self._color = selection

    @property
    def color(self) -> QColor:
        """Returns the current selected color."""
        return QColor(self._color)

    @color.setter
    def color(self, new_color: QColor) -> None:
        self._update_color(new_color)
