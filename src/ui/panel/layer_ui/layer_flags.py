"""The lock, alpha lock and isolate flags a layer can have, and the two widgets that toggle them.

- `LayerFlag` describes one flag: which layers have it, how to read and set it, the signals that announce a change, and
  whether it can be toggled now. `LAYER_FLAGS` lists them in display order.
- `LayerFlagButton` is the selected-layer header's checkable toggle, drawn in the style's checked state. It follows the
  layer `set_layer` gives it.
- `LayerStateIcon` is a list row's icon for one flag of one layer. It shows only while the flag is on, and as a faint
  slot while its row is hovered, so a click there turns the flag on.
"""
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QSize, Qt, SignalInstance
from PySide6.QtGui import QIcon, QPainter, QPaintEvent
from PySide6.QtWidgets import QApplication, QSizePolicy, QToolButton, QWidget

from src.image.layers.image_layer import ImageLayer
from src.image.layers.layer import Layer
from src.image.layers.layer_group import LayerGroup
from src.util.shared_constants import PROJECT_DIR
from src.util.visual.palette_icon import palette_icon

# The QCoreApplication.translate context for strings in this file
TR_ID = 'ui.panel.layer_ui.layer_flags'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


LOCK_LABEL = _tr('Lock')
LOCK_TOOLTIP = _tr('Toggle layer lock')
ALPHA_LOCK_LABEL = _tr('Alpha lock')
ALPHA_LOCK_TOOLTIP = _tr('Toggle layer transparency lock')
ISOLATE_LABEL = _tr('Isolate')
ISOLATE_TOOLTIP = _tr('Toggle layer group isolation')
ISOLATION_FORCED_TOOLTIP = _tr('Layer groups below full opacity or outside Normal mode are always isolated')

ICON_PATH_LOCK = f'{PROJECT_DIR}/resources/icons/layer/lock_closed.svg'
ICON_PATH_ALPHA_LOCK = f'{PROJECT_DIR}/resources/icons/layer/alpha_lock_closed.svg'
ICON_PATH_ISOLATE = f'{PROJECT_DIR}/resources/icons/layer/isolate_on.svg'

STATE_ICON_SIZE = 16
STATE_ICON_MARGIN = 2
# Opacity of a state icon drawn as a hover slot, for a flag that is off:
SLOT_OPACITY = 0.3


def _editable(layer: Layer) -> bool:
    return not layer.locked and not layer.parent_locked


def _isolate_can_toggle(layer: Layer) -> bool:
    assert isinstance(layer, LayerGroup)
    return _editable(layer) and not layer.isolation_forced


def _isolate_tooltip(layer: Layer) -> str:
    assert isinstance(layer, LayerGroup)
    return ISOLATION_FORCED_TOOLTIP if layer.isolation_forced else ISOLATE_TOOLTIP


def _set_alpha_locked(layer: Layer, value: bool) -> None:
    assert isinstance(layer, ImageLayer)
    layer.alpha_locked = value


def _set_isolate(layer: Layer, value: bool) -> None:
    assert isinstance(layer, LayerGroup)
    layer.isolate = value


def _set_locked(layer: Layer, value: bool) -> None:
    layer.locked = value


@dataclass(frozen=True)
class LayerFlag:
    """One boolean layer property shown as a toggle."""
    label: str
    icon_path: str
    # Whether the icon loads in the signal color:
    signal_icon: bool
    applies: Callable[[Layer], bool]
    get: Callable[[Layer], bool]
    set: Callable[[Layer, bool], None]
    # The signals that announce a change to the value or to whether it can be toggled:
    signals: Callable[[Layer], list[SignalInstance]]
    can_toggle: Callable[[Layer], bool]
    tooltip: Callable[[Layer], str]


def _is_child(layer: Layer) -> bool:
    """Whether a layer is in a group, which every layer is except the root."""
    return layer.layer_parent is not None


LOCK_FLAG = LayerFlag(LOCK_LABEL, ICON_PATH_LOCK, True, _is_child, lambda layer: layer.locked, _set_locked,
                      lambda layer: [layer.lock_changed], lambda _layer: True, lambda _layer: LOCK_TOOLTIP)
ALPHA_LOCK_FLAG = LayerFlag(ALPHA_LOCK_LABEL, ICON_PATH_ALPHA_LOCK, False,
                            lambda layer: isinstance(layer, ImageLayer) and _is_child(layer),
                            lambda layer: isinstance(layer, ImageLayer) and layer.alpha_locked, _set_alpha_locked,
                            lambda layer: [layer.alpha_lock_changed, layer.lock_changed]
                            if isinstance(layer, ImageLayer) else [],
                            _editable, lambda _layer: ALPHA_LOCK_TOOLTIP)
ISOLATE_FLAG = LayerFlag(ISOLATE_LABEL, ICON_PATH_ISOLATE, False,
                         lambda layer: isinstance(layer, LayerGroup) and _is_child(layer),
                         lambda layer: isinstance(layer, LayerGroup) and layer.renders_isolated, _set_isolate,
                         lambda layer: [layer.isolate_changed, layer.lock_changed, layer.opacity_changed,
                                        layer.composition_mode_changed] if isinstance(layer, LayerGroup) else [],
                         _isolate_can_toggle, _isolate_tooltip)

# Display order, left to right:
LAYER_FLAGS = (ALPHA_LOCK_FLAG, ISOLATE_FLAG, LOCK_FLAG)


def _flag_icon(flag: LayerFlag) -> QIcon:
    return palette_icon(flag.icon_path, signal=flag.signal_icon)


class LayerFlagButton(QToolButton):
    """A checkable toggle for one flag of the layer it is given, hidden while that layer doesn't have the flag."""

    def __init__(self, flag: LayerFlag, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._flag = flag
        self._layer: Optional[Layer] = None
        self.setCheckable(True)
        self.setIcon(_flag_icon(flag))
        self.setText(flag.label)
        self.setAccessibleName(flag.label)
        self.set_labeled(False)
        self.clicked.connect(self._clicked_slot)
        self.hide()

    @property
    def flag(self) -> LayerFlag:
        """The flag the button toggles."""
        return self._flag

    def set_labeled(self, labeled: bool) -> None:
        """Shows the flag's name beside its icon, or the icon alone."""
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon if labeled
                                else Qt.ToolButtonStyle.ToolButtonIconOnly)

    def set_layer(self, layer: Optional[Layer]) -> None:
        """Follows a new layer, or none."""
        if self._layer is not None:
            for signal in self._flag.signals(self._layer):
                signal.disconnect(self.refresh)
        self._layer = layer if layer is not None and self._flag.applies(layer) else None
        if self._layer is not None:
            for signal in self._flag.signals(self._layer):
                signal.connect(self.refresh)
        self.setVisible(self._layer is not None)
        self.refresh()

    def refresh(self, *_args) -> None:
        """Shows the layer's current value, and whether it can change."""
        layer = self._layer
        if layer is None:
            return
        self.setChecked(self._flag.get(layer))
        self.setEnabled(self._flag.can_toggle(layer))
        self.setToolTip(self._flag.tooltip(layer))

    def _clicked_slot(self, checked: bool) -> None:
        if self._layer is not None and self._flag.can_toggle(self._layer):
            self._flag.set(self._layer, checked)
        self.refresh()


class LayerStateIcon(QToolButton):
    """Shows one flag of a list row's layer while it is on, and as a faint slot that turns it on while the row is
    hovered."""

    def __init__(self, flag: LayerFlag, layer: Layer, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._flag = flag
        self._layer = layer
        self._slot_shown = False
        self.setAutoRaise(True)
        self.setIcon(_flag_icon(flag))
        self.setIconSize(QSize(STATE_ICON_SIZE, STATE_ICON_SIZE))
        self.setFixedSize(STATE_ICON_SIZE + 2 * STATE_ICON_MARGIN, STATE_ICON_SIZE + 2 * STATE_ICON_MARGIN)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName(flag.label)
        for signal in flag.signals(layer):
            signal.connect(self.refresh)
        self.clicked.connect(self._clicked_slot)
        self.refresh()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the fixed icon slot size."""
        return QSize(STATE_ICON_SIZE + 2 * STATE_ICON_MARGIN, STATE_ICON_SIZE + 2 * STATE_ICON_MARGIN)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the fixed icon slot size, which is smaller than the style's tool button minimum."""
        return self.sizeHint()

    @property
    def flag(self) -> LayerFlag:
        """The flag the icon shows."""
        return self._flag

    @property
    def is_on(self) -> bool:
        """Whether the layer's flag is on, which shows the icon."""
        return self._flag.get(self._layer)

    @property
    def slot_shown(self) -> bool:
        """Whether the icon draws as a faint slot while the flag is off."""
        return self._slot_shown and not self.is_on and self._flag.can_toggle(self._layer)

    def set_slot_shown(self, shown: bool) -> None:
        """Shows or hides the faint slot drawn while the flag is off, for the row's hover state."""
        if shown != self._slot_shown:
            self._slot_shown = shown
            self.update()

    def refresh(self, *_args) -> None:
        """Shows the layer's current value, and whether it can change."""
        self.setEnabled(self._flag.can_toggle(self._layer))
        self.setToolTip(self._flag.tooltip(self._layer))
        self.update()

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the icon while the flag is on, a faint slot while the row is hovered, and nothing otherwise."""
        if self.is_on:
            super().paintEvent(event)
        elif self.slot_shown:
            painter = QPainter(self)
            painter.setOpacity(SLOT_OPACITY)
            icon_rect = self.rect().adjusted(STATE_ICON_MARGIN, STATE_ICON_MARGIN, -STATE_ICON_MARGIN,
                                             -STATE_ICON_MARGIN)
            self.icon().paint(painter, icon_rect)
            painter.end()

    def _clicked_slot(self) -> None:
        if not self._flag.can_toggle(self._layer):
            return
        if self.is_on or self._slot_shown:
            self._flag.set(self._layer, not self.is_on)
