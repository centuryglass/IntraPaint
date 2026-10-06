"""Three gradient sliders with spin boxes that edit a color in RGB, HSV or OKLCH.

A combo box switches the color model. Each slider's track shows the color the slider would produce at each position,
holding the other two components. OKLCH tracks leave out-of-gamut positions blank, and an out-of-gamut OKLCH choice
keeps its lightness and hue at the largest chroma that fits sRGB (see `color_math.oklch_to_srgb_in_gamut`).

The block keeps its own components, so dragging saturation or chroma to zero keeps the hue. Slider drags emit
`color_changed`; slider releases, arrow keys and spin box edits also emit `color_committed`. The block leaves alpha
unchanged.
"""
import colorsys
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QGridLayout, QLabel, QDoubleSpinBox, QApplication, QComboBox, QSizePolicy

from src.config.cache import Cache
from src.ui.widget.color_picker.gradient_slider import GradientSlider
from src.util.visual import color_math

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.color_picker.color_slider_block'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MODE_RGB = 'RGB'
MODE_HSV = 'HSV'
MODE_OKLCH = 'OKLCH'
MODES = (MODE_RGB, MODE_HSV, MODE_OKLCH)

MODE_TOOLTIP = _tr('Color model for the sliders')
OUT_OF_GAMUT_TOOLTIP = _tr('Gray parts of the track are colors sRGB cannot show.')
MODE_LABELS = {
    MODE_RGB: _tr('RGB'),
    MODE_HSV: _tr('HSV'),
    MODE_OKLCH: _tr('OKLCH'),
}

GRADIENT_SAMPLES = 64

# Below this OKLCH chroma, HSV saturation or HSV value the hue is undefined, so the block keeps its current hue.
ACHROMATIC_THRESHOLD = 1e-4


@dataclass(frozen=True)
class _Channel:
    label: str
    tooltip: str
    maximum: float
    decimals: int
    step: float


CHANNELS: dict[str, tuple[_Channel, _Channel, _Channel]] = {
    MODE_RGB: (
        _Channel(_tr('R'), _tr('Red'), 255.0, 0, 1.0),
        _Channel(_tr('G'), _tr('Green'), 255.0, 0, 1.0),
        _Channel(_tr('B'), _tr('Blue'), 255.0, 0, 1.0),
    ),
    MODE_HSV: (
        _Channel(_tr('H'), _tr('Hue, in degrees'), 360.0, 0, 1.0),
        _Channel(_tr('S'), _tr('Saturation, in percent'), 100.0, 0, 1.0),
        _Channel(_tr('V'), _tr('Value, in percent'), 100.0, 0, 1.0),
    ),
    MODE_OKLCH: (
        _Channel(_tr('L'), _tr('Perceptual lightness, in percent'), 100.0, 1, 0.5),
        _Channel(_tr('C'), _tr('Chroma: 0 is gray, and the most saturated sRGB colors reach about 0.32'), 0.37, 3,
                 0.005),
        _Channel(_tr('H'), _tr('Perceptual hue, in degrees'), 360.0, 1, 1.0),
    ),
}


def components_to_srgb(mode: str, components: np.ndarray) -> np.ndarray:
    """Converts component arrays with shape (..., 3) in a mode's display units to sRGB, 0.0-1.0.

    OKLCH colors outside sRGB come back with channels outside 0.0-1.0; use `color_math.oklch_to_srgb_in_gamut` to
    map them instead.
    """
    components = np.asarray(components, dtype=np.float64)
    if mode == MODE_RGB:
        return components / 255.0
    if mode == MODE_HSV:
        return _hsv_to_rgb(components[..., 0], components[..., 1] / 100.0, components[..., 2] / 100.0)
    assert mode == MODE_OKLCH, f'unexpected mode {mode}'
    return color_math.oklch_to_srgb(np.stack((components[..., 0] / 100.0, components[..., 1], components[..., 2]),
                                             axis=-1))


def _hsv_to_rgb(hue: np.ndarray, saturation: np.ndarray, value: np.ndarray) -> np.ndarray:
    """Vectorized `colorsys.hsv_to_rgb`, with hue in degrees."""
    sector = (np.asarray(hue) % 360.0) / 60.0
    index = np.floor(sector).astype(int) % 6
    fraction = sector - np.floor(sector)
    p = value * (1.0 - saturation)
    q = value * (1.0 - saturation * fraction)
    t = value * (1.0 - saturation * (1.0 - fraction))
    red = np.choose(index, [value, q, p, p, t, value])
    green = np.choose(index, [t, value, value, q, p, p])
    blue = np.choose(index, [p, p, t, value, value, q])
    return np.stack((red, green, blue), axis=-1)


class ColorSliderBlock(QWidget):
    """Three gradient sliders with spin boxes that edit a color in RGB, HSV or OKLCH."""

    color_changed = Signal(QColor)
    color_committed = Signal(QColor)

    def __init__(self, parent: Optional[QWidget] = None, save_mode: bool = True) -> None:
        """Creates the block, reading and saving its mode in `Cache.COLOR_SLIDER_MODE` if `save_mode` is true."""
        super().__init__(parent)
        # Cache key attributes exist only once the Cache singleton is constructed, so this can't be a default argument.
        self._mode_key: Optional[str] = Cache.COLOR_SLIDER_MODE if save_mode else None
        mode = Cache().get(self._mode_key) if self._mode_key is not None else MODE_RGB
        self._mode = mode if mode in MODES else MODE_RGB
        self._color = QColor(Qt.GlobalColor.black)
        self._components = np.zeros(3)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._mode_box = QComboBox(self)
        self._mode_box.setToolTip(MODE_TOOLTIP)
        for option in MODES:
            self._mode_box.addItem(MODE_LABELS[option], option)
        self._mode_box.setCurrentIndex(MODES.index(self._mode))
        self._mode_box.currentIndexChanged.connect(lambda index: self.set_mode(MODES[index]))
        layout.addWidget(self._mode_box, 0, 0, 1, 3, Qt.AlignmentFlag.AlignLeft)

        self._labels: list[QLabel] = []
        self._sliders: list[GradientSlider] = []
        self._spin_boxes: list[QDoubleSpinBox] = []
        for index in range(3):
            label = QLabel(self)
            spin_box = QDoubleSpinBox(self)
            spin_box.setKeyboardTracking(False)
            spin_box.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            spin_box.valueChanged.connect(lambda value, i=index: self._spin_box_changed(i, value))
            label.setBuddy(spin_box)
            layout.addWidget(label, index + 1, 0)
            layout.addWidget(spin_box, index + 1, 2)
            self._labels.append(label)
            self._spin_boxes.append(spin_box)
        layout.setColumnStretch(1, 1)
        self._build_sliders()
        self._update_components_from_color()
        self._update_widgets()

    @property
    def sliders(self) -> tuple[GradientSlider, ...]:
        """The three component sliders, in channel order."""
        return tuple(self._sliders)

    @property
    def spin_boxes(self) -> tuple[QDoubleSpinBox, ...]:
        """The three component spin boxes, in channel order."""
        return tuple(self._spin_boxes)

    def mode(self) -> str:
        """Returns the color model: MODE_RGB, MODE_HSV or MODE_OKLCH."""
        return self._mode

    def set_mode(self, mode: str) -> None:
        """Switches the color model, keeping the color, and saves it as the default if the block saves its mode."""
        assert mode in MODES, f'unexpected mode {mode}'
        if mode == self._mode:
            return
        self._mode = mode
        self._mode_box.blockSignals(True)
        self._mode_box.setCurrentIndex(MODES.index(mode))
        self._mode_box.blockSignals(False)
        if self._mode_key is not None:
            Cache().set(self._mode_key, mode)
        self._components = np.zeros(3)
        self._build_sliders()
        self._update_components_from_color()
        self._update_widgets()

    def components(self) -> tuple[float, float, float]:
        """Returns the components in the current mode's display units."""
        return float(self._components[0]), float(self._components[1]), float(self._components[2])

    def selected_color(self) -> QColor:
        """Returns the selected color."""
        return QColor(self._color)

    def set_color(self, color: QColor) -> None:
        """Sets the selected color without emitting signals.

        A color that matches the current components keeps them, so 8-bit rounding and gamut mapping never move the
        sliders.
        """
        color = color.toRgb()
        if color.rgb() != self._components_color().rgb():
            self._color = color
            self._update_components_from_color()
        self._color = color
        self._update_widgets()

    def _build_sliders(self) -> None:
        layout = self.layout()
        assert isinstance(layout, QGridLayout)
        for slider in self._sliders:
            layout.removeWidget(slider)
            slider.hide()
            slider.deleteLater()
        self._sliders = []
        for index, channel in enumerate(CHANNELS[self._mode]):
            slider = GradientSlider(0.0, channel.maximum, self, step=channel.step)
            slider.setToolTip(f'{channel.tooltip}\n{OUT_OF_GAMUT_TOOLTIP}' if self._mode == MODE_OKLCH
                              else channel.tooltip)
            slider.value_changed.connect(lambda value, i=index: self._set_component(i, value, False))
            slider.value_committed.connect(lambda _: self.color_committed.emit(self.selected_color()))
            layout.addWidget(slider, index + 1, 1)
            self._sliders.append(slider)

            self._labels[index].setText(channel.label)
            self._labels[index].setToolTip(channel.tooltip)
            spin_box = self._spin_boxes[index]
            spin_box.blockSignals(True)
            spin_box.setDecimals(channel.decimals)
            spin_box.setRange(0.0, channel.maximum)
            spin_box.setSingleStep(channel.step)
            spin_box.setToolTip(channel.tooltip)
            spin_box.blockSignals(False)

    def _components_color(self) -> QColor:
        """Returns the color the current components select, gamut-mapped, with the current alpha."""
        if self._mode == MODE_OKLCH:
            lightness, chroma, hue = self._components
            rgb = color_math.oklch_to_srgb_in_gamut((lightness / 100.0, chroma, hue))
        else:
            rgb = np.clip(components_to_srgb(self._mode, self._components), 0.0, 1.0)
        red, green, blue = (int(round(channel * 255)) for channel in rgb)
        return QColor(red, green, blue, self._color.alpha())

    def _update_components_from_color(self) -> None:
        red, green, blue = self._color.redF(), self._color.greenF(), self._color.blueF()
        last_hue = self._components[0] if self._mode == MODE_HSV else self._components[2]
        if self._mode == MODE_RGB:
            self._components = np.array((self._color.red(), self._color.green(), self._color.blue()), dtype=np.float64)
        elif self._mode == MODE_HSV:
            last_saturation = self._components[1]
            hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
            if value < ACHROMATIC_THRESHOLD:
                hue, saturation = last_hue / 360.0, last_saturation / 100.0
            elif saturation < ACHROMATIC_THRESHOLD:
                hue = last_hue / 360.0
            self._components = np.array((hue * 360.0, saturation * 100.0, value * 100.0))
        else:
            lightness, chroma, hue = color_math.srgb_to_oklch((red, green, blue))
            if chroma < ACHROMATIC_THRESHOLD:
                hue = last_hue
            self._components = np.array((lightness * 100.0, chroma, hue))
        maxima = [channel.maximum for channel in CHANNELS[self._mode]]
        self._components = np.clip(self._components, 0.0, maxima)

    def _update_widgets(self) -> None:
        for index in range(3):
            self._sliders[index].set_value(self._components[index])
            spin_box = self._spin_boxes[index]
            spin_box.blockSignals(True)
            spin_box.setValue(self._components[index])
            spin_box.blockSignals(False)
            self._sliders[index].set_gradient(self._gradient(index))

    def _gradient(self, index: int) -> np.ndarray:
        """Returns RGBA samples across one channel's range, holding the other components."""
        components = np.tile(self._components, (GRADIENT_SAMPLES, 1))
        components[:, index] = np.linspace(0.0, CHANNELS[self._mode][index].maximum, GRADIENT_SAMPLES)
        rgb = components_to_srgb(self._mode, components)
        rgba = np.ones((GRADIENT_SAMPLES, 4))
        rgba[:, :3] = np.clip(rgb, 0.0, 1.0)
        rgba[:, 3] = color_math.is_in_srgb_gamut(rgb)
        return rgba

    def _set_component(self, index: int, value: float, commit: bool) -> None:
        self._components[index] = value
        last_color = self._color
        self._color = self._components_color()
        self._update_widgets()
        if self._color != last_color:
            self.color_changed.emit(self.selected_color())
        if commit:
            self.color_committed.emit(self.selected_color())

    def _spin_box_changed(self, index: int, value: float) -> None:
        if value != round(self._components[index], CHANNELS[self._mode][index].decimals):
            self._set_component(index, value, True)
