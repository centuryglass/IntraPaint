"""Edits the base value of one libmypaint setting at a time on the active MyPaint brush.

Edits go straight to the `MyPaintBrush` and are not saved. Loading another brush file replaces them, so the owner calls
`refresh` after each load.

Size, color and the eraser flag are left out. The tool panel's Size field, the color pair and the eraser tool own them.
"""
from typing import Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QSizePolicy, QVBoxLayout, QWidget

from src.image.mypaint.mypaint_brush import BrushSetting, MyPaintBrush
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.panel_fit import FIELD_MAX_WIDTH

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.mypaint_brush_dynamics'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SETTING_LABEL = _tr('Setting')
VALUE_LABEL = _tr('Base value')
DEFAULT_SETTING = 'opaque'

QWIDGETSIZE_MAX = 16777215

# Settings that other controls own:
_EXCLUDED_SETTINGS = ('color_h', 'color_s', 'color_v', 'radius_logarithmic', 'eraser')


def editable_settings() -> list[BrushSetting]:
    """Returns the libmypaint settings this widget offers, in libmypaint's order."""
    # pylint: disable=protected-access
    return [setting for setting in MyPaintBrush._setting_info
            if setting.cname not in _EXCLUDED_SETTINGS and setting.name != '']


class _DescriptionLabel(QLabel):
    """A word-wrapped label whose minimum height fits its whole text at its current width.

    The height comes from the font metrics, since QLabel's own wrapped hints are cached and guessed at another width.
    A resize or new text re-measures it.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._measured_height = -1

    def setText(self, text: str) -> None:  # pylint: disable=invalid-name
        """Changes the text and re-measures the height."""
        super().setText(text)
        self._remeasure()

    def hasHeightForWidth(self) -> bool:  # pylint: disable=invalid-name
        """Returns false, so layouts use the height measured at the label's own width.

        A grid computes height for width at a spanned cell's full width, which a capped section never gets.
        """
        return False

    def heightForWidth(self, width: int) -> int:  # pylint: disable=invalid-name
        """Returns the height of the wrapped text at a width."""
        if self.text() == '':
            return 0
        margins = self.contentsMargins()
        text_width = max(width - margins.left() - margins.right() - 2 * self.margin(), 1)
        bounds = self.fontMetrics().boundingRect(QRect(0, 0, text_width, QWIDGETSIZE_MAX),
                                                 int(Qt.TextFlag.TextWordWrap), self.text())
        return bounds.height() + margins.top() + margins.bottom() + 2 * self.margin()

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns no width, and the wrapped text's height at the current width."""
        return QSize(0, self.heightForWidth(self.width()))

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the minimum size."""
        return self.minimumSizeHint()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Re-measures the height at the new width."""
        super().resizeEvent(event)
        self._remeasure()

    def _remeasure(self) -> None:
        height = self.minimumSizeHint().height()
        if height != self._measured_height:
            self._measured_height = height
            self.updateGeometry()


class BrushDynamicsWidget(QWidget):
    """A setting picker, the picked setting's description, and a field for its base value."""

    def __init__(self, brush: MyPaintBrush, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._brush = brush
        self._settings = editable_settings()
        self._setting_combo = QComboBox(self)
        self._setting_combo.setAccessibleName(SETTING_LABEL)
        self._setting_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self._setting_combo.setMinimumContentsLength(8)
        for setting in self._settings:
            self._setting_combo.addItem(setting.name, setting.id)
        self._description = _DescriptionLabel(self)
        self._description.setForegroundRole(self._description.palette().ColorRole.PlaceholderText)
        self._field = SliderField(VALUE_LABEL, 0.0, 0.0, 1.0, step=0.01, parent=self)
        # The description wraps to whatever width the section gets, and the inputs stop at the field cap:
        for field in (self._setting_combo, self._field):
            field.setMaximumWidth(FIELD_MAX_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._setting_combo)
        layout.addWidget(self._description)
        layout.addWidget(self._field)
        self._setting_combo.currentIndexChanged.connect(lambda _: self._show_setting())
        self._field.valueChanged.connect(self._apply_value)
        default_index = self._setting_combo.findText(DEFAULT_SETTING, Qt.MatchFlag.MatchFixedString)
        if default_index >= 0:
            self._setting_combo.setCurrentIndex(default_index)
        self._show_setting()

    @property
    def setting_combo(self) -> QComboBox:
        """The setting picker."""
        return self._setting_combo

    @property
    def description_label(self) -> QLabel:
        """The picked setting's description."""
        return self._description

    def description_for(self, index: int) -> str:
        """Returns the description of the setting at a picker index."""
        setting_id = self._setting_combo.itemData(index)
        return next((setting.tooltip for setting in self._settings if setting.id == setting_id), '')

    @property
    def value_field(self) -> SliderField:
        """The field for the picked setting's base value."""
        return self._field

    @property
    def current_setting(self) -> Optional[BrushSetting]:
        """The picked setting, or None if the brush library has none to offer."""
        setting_id = self._setting_combo.currentData()
        return next((setting for setting in self._settings if setting.id == setting_id), None)

    def summary(self) -> str:
        """Returns the picked setting's name and value, for a collapsed section header."""
        setting = self.current_setting
        if setting is None:
            return ''
        return f'{setting.name} {self._field.value_text()}'

    def refresh(self) -> None:
        """Re-reads the picked setting from the brush, after the brush loaded a file."""
        self._show_setting()

    def _show_setting(self) -> None:
        setting = self.current_setting
        self._field.setEnabled(setting is not None)
        if setting is None:
            return
        self._description.setText(setting.tooltip)
        self._field.blockSignals(True)
        try:
            self._field.set_range(setting.min_value, setting.max_value)
            self._field.set_value(self._brush.get_value(setting.id))
        finally:
            self._field.blockSignals(False)
        self._field.update()

    def _apply_value(self, value: int | float) -> None:
        setting = self.current_setting
        if setting is not None and self._brush.get_value(setting.id) != value:
            self._brush.set_value(setting.id, float(value))
