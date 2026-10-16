"""The X, Y, W and H fields shared by the text, layer transform and generation area panels, with optional scale and
angle rows and a ratio lock.

`GeometryBlock` is a view: it holds field values and the lock, and tells its owner what the user changed. It touches no
config or tool state. The owner connects `valueChanged`, calls `set_value` when the model changes, and registers the
step keys with `bind_step_keys`.

- Fields are two columns of `NumberField`s. X and Y share a row, W and H share a row with the lock between them, and
  the X/Y row keeps an empty slot of the lock's width so the columns line up.
- Each field fills over a "scrub range" (X and Y from minus one image width to two, W and H from 0 to two) but accepts
  any typed value within its limits.
- The lock keeps W:H, and Scale X:Scale Y, at the ratio they had when the lock engaged or when the owner last set a
  value. Holding the fixed-aspect modifier engages it temporarily without changing the stored setting.
"""
from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QAbstractButton, QApplication, QGridLayout, QSizePolicy, QWidget

from src.ui.input_fields.number_field import FIELD_HEIGHT, NumberField
from src.ui.ink_style import ink_colors
from src.util.shared_constants import FLOAT_MAX, FLOAT_MIN, MIN_NONZERO

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.input_fields.geometry_block'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


X_LABEL = _tr('X')
Y_LABEL = _tr('Y')
WIDTH_LABEL = _tr('W')
HEIGHT_LABEL = _tr('H')
SCALE_X_LABEL = _tr('Scale X')
SCALE_Y_LABEL = _tr('Scale Y')
ANGLE_LABEL = _tr('Angle')
X_TOOLTIP = _tr('Horizontal position')
Y_TOOLTIP = _tr('Vertical position')
WIDTH_TOOLTIP = _tr('Width')
HEIGHT_TOOLTIP = _tr('Height')
SCALE_X_TOOLTIP = _tr('Horizontal scale')
SCALE_Y_TOOLTIP = _tr('Vertical scale')
ANGLE_TOOLTIP = _tr('Rotation angle')
LOCK_TOOLTIP = _tr('Lock the width:height ratio')
LOCK_TEMPORARY_TOOLTIP = _tr('Lock the width:height ratio ({modifier} locks it temporarily)')
STEP_KEYS_TOOLTIP = _tr('{description}\nKeys: {decrease} / {increase}')
PIXEL_SUFFIX = _tr(' px')
DEGREE_SUFFIX = _tr(' deg')
SCALE_SUFFIX = _tr('x')

# Field names, which `valueChanged` reports and `set_value` accepts:
X = 'x'
Y = 'y'
WIDTH = 'w'
HEIGHT = 'h'
SCALE_X = 'scale_x'
SCALE_Y = 'scale_y'
ANGLE = 'angle'
FIELD_NAMES = (X, Y, WIDTH, HEIGHT, SCALE_X, SCALE_Y, ANGLE)

DEFAULT_IMAGE_SIZE = QSize(512, 512)
SCALE_STEP = 0.05
SCALE_SCRUB_MAX = 4.0
ANGLE_SCRUB_RANGE = 360.0
FLOAT_PIXEL_STEP = 0.01
GRID_SPACING = 6
LOCK_WIDTH = FIELD_HEIGHT
LOCK_LINK_SIZE = 7.0


class _GeometryField(NumberField):
    """A `NumberField` that fills over a scrub range but accepts values outside it, up to its limits."""

    def __init__(self, *args, scrub_range: tuple[float, float], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._scrub_range = scrub_range

    def set_scrub_range(self, minimum: float, maximum: float) -> None:
        """Sets the values the fill shows as empty and full."""
        self._scrub_range = (minimum, maximum)
        self.update()

    def _fill_fraction(self) -> Optional[float]:
        low, high = self._scrub_range
        return min(max((self._value - low) / (high - low), 0.0), 1.0)

    def _scrub_delta(self, delta_x: int) -> int | float:
        low, high = self._scrub_range
        return delta_x / max(self.width(), 1) * (high - low)


class RatioLockButton(QAbstractButton):
    """An icon toggle drawn as two chain links. Checked means locked. Temporary means a held modifier locks it for now:
    the button shows a dotted outline and is not drawn checked, since releasing the modifier undoes it."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._temporary = False
        self.setCheckable(True)
        self.setFixedSize(LOCK_WIDTH, FIELD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def temporary(self) -> bool:
        """Returns whether the lock is on only while a modifier is held."""
        return self._temporary

    def set_temporary(self, temporary: bool) -> None:
        """Shows or hides the temporary-lock outline."""
        if temporary != self._temporary:
            self._temporary = temporary
            self.update()

    def sizeHint(self) -> QSize:
        """Returns the button's fixed size."""
        return QSize(LOCK_WIDTH, FIELD_HEIGHT)

    def paintEvent(self, _event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the links over a filled background when checked, or a dotted outline when temporarily locked."""
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        palette = self.palette()
        colors = ink_colors()
        accent = colors.accent_hover if colors is not None else palette.color(group, QPalette.ColorRole.Highlight)
        text = palette.color(group, QPalette.ColorRole.Text)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(self.rect()).adjusted(2.5, 2.5, -2.5, -2.5)
        if self.isChecked():
            fill = accent if self.isEnabled() else palette.color(group, QPalette.ColorRole.Mid)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(box, 4, 4)
        elif self._temporary:
            pen = QPen(accent, 1.5, Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box, 4, 4)
        elif self.underMouse() and self.isEnabled():
            painter.setPen(QPen(palette.color(group, QPalette.ColorRole.Mid), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(box, 4, 4)
        painter.setPen(QPen(palette.color(group, QPalette.ColorRole.HighlightedText) if self.isChecked() else text,
                            1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        center = QPointF(self.width() / 2, self.height() / 2)
        link = QRectF(0, 0, LOCK_LINK_SIZE * 1.6, LOCK_LINK_SIZE)
        offset = LOCK_LINK_SIZE * 0.55
        for direction in (-1, 1):
            link.moveCenter(center + QPointF(direction * offset, 0))
            painter.drawRoundedRect(link, LOCK_LINK_SIZE / 2, LOCK_LINK_SIZE / 2)
        painter.end()


class GeometryBlock(QWidget):
    """X, Y, W and H fields with a ratio lock, plus optional Scale X, Scale Y and Angle rows.

    Parameters
    ----------
    show_scale: bool
        Adds a Scale X / Scale Y row, which the ratio lock also links.
    show_angle: bool
        Adds an Angle row.
    integer: bool
        Whole-number fields for position and size. Otherwise they take fractional pixels.
    parent: Optional[QWidget]
        Optional parent widget.
    """

    valueChanged = Signal(str, object)
    ratioLockToggled = Signal(bool)

    def __init__(self, show_scale: bool = False, show_angle: bool = False, integer: bool = True,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._integer = integer
        self._image_size = DEFAULT_IMAGE_SIZE
        self._horizontal = False
        self._temporary_lock = False
        self._ratios: dict[str, float] = {}
        self._key_steps: dict[str, int | float] = {}
        self._fields: dict[str, NumberField] = {}
        self._lock = RatioLockButton(self)
        self._lock.setToolTip(LOCK_TOOLTIP)
        self._lock.toggled.connect(self._lock_toggled)
        self._spacer = QWidget(self)
        self._spacer.setFixedSize(LOCK_WIDTH, FIELD_HEIGHT)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(GRID_SPACING)
        pixel_step = 1 if integer else FLOAT_PIXEL_STEP
        pixel_min = 1 if integer else MIN_NONZERO
        pixel_limit = None if integer else FLOAT_MIN
        limit_max = None if integer else FLOAT_MAX
        zero: int | float = 0 if integer else 0.0
        self._add_field(X, X_LABEL, X_TOOLTIP, zero, pixel_limit, limit_max, pixel_step, PIXEL_SUFFIX)
        self._add_field(Y, Y_LABEL, Y_TOOLTIP, zero, pixel_limit, limit_max, pixel_step, PIXEL_SUFFIX)
        self._add_field(WIDTH, WIDTH_LABEL, WIDTH_TOOLTIP, pixel_min, pixel_min, limit_max, pixel_step, PIXEL_SUFFIX)
        self._add_field(HEIGHT, HEIGHT_LABEL, HEIGHT_TOOLTIP, pixel_min, pixel_min, limit_max, pixel_step,
                        PIXEL_SUFFIX)
        self._show_scale = show_scale
        self._show_angle = show_angle
        if show_scale:
            self._add_field(SCALE_X, SCALE_X_LABEL, SCALE_X_TOOLTIP, 1.0, FLOAT_MIN, FLOAT_MAX, SCALE_STEP,
                            SCALE_SUFFIX, decimals=2)
            self._add_field(SCALE_Y, SCALE_Y_LABEL, SCALE_Y_TOOLTIP, 1.0, FLOAT_MIN, FLOAT_MAX, SCALE_STEP,
                            SCALE_SUFFIX, decimals=2)
        if show_angle:
            self._add_field(ANGLE, ANGLE_LABEL, ANGLE_TOOLTIP, 0.0, FLOAT_MIN, FLOAT_MAX, 1.0, DEGREE_SUFFIX,
                            decimals=2)
        self._key_steps = {name: field.step() for name, field in self._fields.items()}
        self.set_image_size(DEFAULT_IMAGE_SIZE)
        self._arrange()

    def _make_field(self, *args, **kwargs) -> NumberField:
        """Creates one field. Gallery renders override this to draw fields without text."""
        return _GeometryField(*args, **kwargs)

    def _add_field(self, name: str, label: str, tooltip: str, value: int | float, minimum: int | float,
                   maximum: Optional[int | float], step: int | float, suffix: str, decimals: Optional[int] = None
                   ) -> None:
        field = self._make_field(label, value, minimum, maximum, step=step, suffix=suffix, decimals=decimals,
                                 scrub_range=(0.0, 1.0), parent=self)
        field.setToolTip(tooltip)
        field.valueChanged.connect(lambda new_value, field_name=name: self._field_changed(field_name, new_value))
        self._fields[name] = field

    # -----------------------------------------------------------------------------------------------------------------
    # Values
    # -----------------------------------------------------------------------------------------------------------------

    def field(self, name: str) -> NumberField:
        """Returns one field widget by name, for tests and for owners that need its signals."""
        return self._fields[name]

    def has_field(self, name: str) -> bool:
        """Returns whether the block shows a field of this name."""
        return name in self._fields

    def value(self, name: str) -> int | float:
        """Returns one field's value."""
        return self._fields[name].value()

    def set_value(self, name: str, value: int | float) -> None:
        """Sets one field's value from the model, without emitting `valueChanged`. The lock's ratio follows it."""
        field = self._fields[name]
        was_blocked = field.blockSignals(True)
        try:
            field.set_value(value)
        finally:
            field.blockSignals(was_blocked)
        self._capture_ratios()

    def set_values(self, **values: int | float) -> None:
        """Sets several fields from the model at once, then captures the lock's ratio."""
        for name, value in values.items():
            self.set_value(name, value)

    def set_limits(self, name: str, minimum: Optional[int | float], maximum: Optional[int | float]) -> None:
        """Sets the smallest and largest value a field accepts, where None means no limit."""
        field = self._fields[name]
        was_blocked = field.blockSignals(True)
        try:
            field.set_range(minimum, maximum)
        finally:
            field.blockSignals(was_blocked)

    def set_image_size(self, size: QSize) -> None:
        """Sets the image size the position and size fills are scaled to."""
        self._image_size = size
        width, height = max(size.width(), 1), max(size.height(), 1)
        self._set_scrub_range(X, -width, 2 * width)
        self._set_scrub_range(Y, -height, 2 * height)
        self._set_scrub_range(WIDTH, 0, 2 * width)
        self._set_scrub_range(HEIGHT, 0, 2 * height)
        self._set_scrub_range(SCALE_X, 0, SCALE_SCRUB_MAX)
        self._set_scrub_range(SCALE_Y, 0, SCALE_SCRUB_MAX)
        self._set_scrub_range(ANGLE, -ANGLE_SCRUB_RANGE / 2, ANGLE_SCRUB_RANGE / 2)

    def _set_scrub_range(self, name: str, minimum: float, maximum: float) -> None:
        field = self._fields.get(name)
        if isinstance(field, _GeometryField):
            field.set_scrub_range(minimum, maximum)

    def summary_text(self) -> str:
        """Returns the position and size as "128, 64 - 512 x 384", for a collapsed section's summary."""
        return f'{self._plain(X)}, {self._plain(Y)} - {self._plain(WIDTH)} x {self._plain(HEIGHT)}'

    def _plain(self, name: str) -> str:
        return self._fields[name].value_text().removesuffix(PIXEL_SUFFIX)

    # -----------------------------------------------------------------------------------------------------------------
    # Ratio lock
    # -----------------------------------------------------------------------------------------------------------------

    def ratio_locked(self) -> bool:
        """Returns the stored lock setting, which a held modifier does not change."""
        return self._lock.isChecked()

    def set_ratio_locked(self, locked: bool) -> None:
        """Sets the stored lock setting. Emits `ratioLockToggled` if it changed."""
        self._lock.setChecked(locked)

    def temporary_lock(self) -> bool:
        """Returns whether a held modifier is locking the ratio for now."""
        return self._temporary_lock

    def set_temporary_lock(self, held: bool) -> None:
        """Locks the ratio while a modifier is held, without changing the stored setting."""
        if held == self._temporary_lock:
            return
        self._temporary_lock = held
        if self.effective_ratio_locked():
            self._capture_ratios()
        self._lock.set_temporary(held and not self._lock.isChecked())

    def effective_ratio_locked(self) -> bool:
        """Returns whether edits currently keep the ratio, from either the stored setting or a held modifier."""
        return self._lock.isChecked() or self._temporary_lock

    def lock_button(self) -> RatioLockButton:
        """Returns the lock toggle."""
        return self._lock

    def _lock_toggled(self, locked: bool) -> None:
        self._lock.set_temporary(self._temporary_lock and not locked)
        if locked:
            self._capture_ratios()
        self.ratioLockToggled.emit(locked)

    def _capture_ratios(self) -> None:
        """Records the ratios the lock keeps, from the current values."""
        pairs = ((WIDTH, HEIGHT), (SCALE_X, SCALE_Y))
        for first, second in pairs:
            if first in self._fields and self.value(first) != 0:
                self._ratios[first] = self.value(second) / self.value(first)

    def _field_changed(self, name: str, value: int | float) -> None:
        """Passes a user edit on, first updating the field the lock links to it."""
        partners = {WIDTH: HEIGHT, HEIGHT: WIDTH, SCALE_X: SCALE_Y, SCALE_Y: SCALE_X}
        partner = partners.get(name)
        updated_partner: Optional[int | float] = None
        if partner is not None and self.effective_ratio_locked() and partner in self._fields:
            first = name if name in (WIDTH, SCALE_X) else partner
            ratio = self._ratios.get(first)
            if ratio is not None and ratio != 0:
                updated_partner = value * ratio if name == first else value / ratio
                partner_field = self._fields[partner]
                was_blocked = partner_field.blockSignals(True)
                try:
                    partner_field.set_value(updated_partner)
                finally:
                    partner_field.blockSignals(was_blocked)
                updated_partner = partner_field.value()
        self.valueChanged.emit(name, value)
        if partner is not None and updated_partner is not None:
            self.valueChanged.emit(partner, updated_partner)

    # -----------------------------------------------------------------------------------------------------------------
    # Step keys
    # -----------------------------------------------------------------------------------------------------------------

    def key_step(self, name: str) -> int | float:
        """Returns how far one step-key press moves a field, before the speed modifier's multiplier."""
        return self._key_steps[name]

    def step_field(self, name: str, steps: int | float) -> None:
        """Moves a field by `steps` key steps, as a step-key press does. Emits `valueChanged` like a typed edit."""
        field = self._fields[name]
        field.set_value(field.value() + steps * self._key_steps[name])

    def set_step_key_tooltip(self, name: str, decrease_key: str, increase_key: str) -> None:
        """Adds the keys that step a field to its tooltip."""
        field = self._fields[name]
        description = self._base_tooltip(name)
        field.setToolTip(STEP_KEYS_TOOLTIP.format(description=description, decrease=decrease_key,
                                                  increase=increase_key))

    def _base_tooltip(self, name: str) -> str:
        return {X: X_TOOLTIP, Y: Y_TOOLTIP, WIDTH: WIDTH_TOOLTIP, HEIGHT: HEIGHT_TOOLTIP, SCALE_X: SCALE_X_TOOLTIP,
                SCALE_Y: SCALE_Y_TOOLTIP, ANGLE: ANGLE_TOOLTIP}[name]

    # -----------------------------------------------------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------------------------------------------------

    def horizontal(self) -> bool:
        """Returns whether the position row and size row sit side by side on one line."""
        return self._horizontal

    def set_horizontal(self, horizontal: bool) -> None:
        """Puts the position row and size row side by side on one line, for a short strip."""
        if horizontal != self._horizontal:
            self._horizontal = horizontal
            self._arrange()

    def _arrange(self) -> None:
        while self._grid.count() > 0:
            self._grid.takeAt(0)
        for column in range(self._grid.columnCount() + 1):
            self._grid.setColumnStretch(column, 0)
        grid = self._grid
        if self._horizontal:
            grid.addWidget(self._fields[X], 0, 0)
            grid.addWidget(self._fields[Y], 0, 1)
            grid.addWidget(self._fields[WIDTH], 0, 2)
            grid.addWidget(self._lock, 0, 3)
            grid.addWidget(self._fields[HEIGHT], 0, 4)
            self._spacer.hide()
            for column in (0, 1, 2, 4):
                grid.setColumnStretch(column, 1)
            next_row = 1
        else:
            grid.addWidget(self._fields[X], 0, 0)
            grid.addWidget(self._spacer, 0, 1)
            grid.addWidget(self._fields[Y], 0, 2)
            grid.addWidget(self._fields[WIDTH], 1, 0)
            grid.addWidget(self._lock, 1, 1)
            grid.addWidget(self._fields[HEIGHT], 1, 2)
            self._spacer.show()
            for column in (0, 2):
                grid.setColumnStretch(column, 1)
            next_row = 2
        if self._show_scale:
            grid.addWidget(self._fields[SCALE_X], next_row, 0)
            grid.addWidget(self._fields[SCALE_Y], next_row, 2 if not self._horizontal else 1)
            next_row += 1
        if self._show_angle:
            grid.addWidget(self._fields[ANGLE], next_row, 0)
        self.updateGeometry()


def bind_step_keys(block: GeometryBlock, hotkey_filter, key_config, predicate: Callable[[], bool]) -> None:
    """Binds the step keys to a block's fields and lists them in the tooltips.

    Every user gets one direction: Move Left/Right step X, Move Up/Down step Y, Pan Left/Right step W, Pan Up/Down step
    H, and the rotate keys step the angle, each with the speed modifier's multiplier. `predicate` says whether the
    owning panel should react, usually whether it is visible and enabled.

    Parameters
    ----------
    block: GeometryBlock
        The block to bind.
    hotkey_filter: HotkeyFilter
        The application's key filter.
    key_config: type[KeyConfig]
        `KeyConfig`, whose key constants exist only after its first construction.
    predicate: Callable[[], bool]
        Whether a key press should step the field.
    """
    bindings = {
        'x': (key_config.MOVE_LEFT, key_config.MOVE_RIGHT),
        'y': (key_config.MOVE_UP, key_config.MOVE_DOWN),
        'w': (key_config.PAN_LEFT, key_config.PAN_RIGHT),
        'h': (key_config.PAN_DOWN, key_config.PAN_UP),
        'angle': (key_config.ROTATE_CCW_KEY, key_config.ROTATE_CW_KEY),
    }
    for name, (decrease_key, increase_key) in bindings.items():
        if not block.has_field(name):
            continue
        for key, sign in ((decrease_key, -1), (increase_key, 1)):
            def _binding(multiplier: int, field_name=name, direction=sign) -> bool:
                if not predicate():
                    return False
                block.step_field(field_name, direction * multiplier)
                return True

            hotkey_filter.register_speed_modified_keybinding(f'_GeometryBlock_{id(block)}_{name}_{key}', _binding, key)
        block.set_step_key_tooltip(name, key_config().get(decrease_key), key_config().get(increase_key))
    modifier = key_config().get(key_config.FIXED_ASPECT_MODIFIER)
    block.lock_button().setToolTip(LOCK_TEMPORARY_TOOLTIP.format(modifier=modifier))

    def _modifiers_changed(modifiers: Qt.KeyboardModifier) -> None:
        block.set_temporary_lock(block.isVisible() and key_config.modifier_held(key_config.FIXED_ASPECT_MODIFIER,
                                                                                held_modifiers=modifiers))

    hotkey_filter.modifiers_changed.connect(_modifiers_changed)
