"""Opens a color picker to set the brush color."""
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QColor, QIcon, QPixmap
from PyQt5.QtWidgets import QPushButton, QColorDialog

from src.config.cache import Cache

COLOR_BUTTON_LABEL = 'Color'


class BrushColorButton(QPushButton):
    """Opens a color picker to set the brush color."""

    def __init__(self):
        super().__init__()
        self._color = QColor()
        self._icon = QPixmap(QSize(64, 64))
        cache = Cache.instance()
        cache.connect(self, Cache.LAST_BRUSH_COLOR, self._update_color)
        self._update_color(cache.get(Cache.LAST_BRUSH_COLOR))
        self.clicked.connect(self.select_color)
        self.setText(COLOR_BUTTON_LABEL)

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
            Cache.instance().set(Cache.LAST_BRUSH_COLOR, selection)
