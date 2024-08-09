"""Opens a color picker to set the brush color."""
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QPushButton, QColorDialog, QApplication

from src.config.cache import Cache


# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.brush_color_button'


def _tr(*args):
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, *args)


COLOR_BUTTON_LABEL = _tr('Color')
COLOR_BUTTON_TOOLTIP = _tr('Select paint color')


class BrushColorButton(QPushButton):
    """Opens a color picker to set the brush color."""

    def __init__(self):
        super().__init__()
        self._color = QColor()
        self._icon = QPixmap(QSize(64, 64))
        cache = Cache()
        cache.connect(self, Cache.LAST_BRUSH_COLOR, self._update_color)
        self._update_color(cache.get(Cache.LAST_BRUSH_COLOR))
        self.clicked.connect(self.select_color)
        self.setText(COLOR_BUTTON_LABEL)
        self.setToolTip(COLOR_BUTTON_TOOLTIP)

    def _update_color(self, color_str: str) -> None:
        self._color = QColor(color_str)
        self._icon.fill(self._color)
        self.setIcon(QIcon(self._icon))
        self.update()

    def select_color(self) -> None:
        """Open the color picker, then apply the selection through the cache."""
        color_dialog = QColorDialog()
        color_dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        color_dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        selection = color_dialog.getColor(self._color)
        if selection != self._color:
            Cache().set(Cache.LAST_BRUSH_COLOR, selection.name())
