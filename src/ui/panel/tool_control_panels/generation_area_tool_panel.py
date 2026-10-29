"""Generation area tool control panel: the shared `GeometryBlock`, labeled size presets, and a read-only line naming
the resolution the generator receives.

The panel is a view over `ImageStack.generation_area`. It sets the area when the user changes a field or picks a
preset, and follows the area whenever it changes.

- Position and size: the geometry block, with its ratio lock. A finished drag or typed W or H records the size in
  `Cache.RECENT_GENERATION_AREA_SIZES`, as resizing on the canvas does.
- Size presets:
  - Fit: Full image, Square, and Previous, which does what the previous frame key does.
  - Recent: `RECENT_FRAME_COUNT` fixed slots. A size keeps its slot while it stays recent, and empty slots show
    disabled, so the row keeps its shape.
  - Custom: a field that takes "768" or "640x480" (`parse_size`), and shows a hint in the signal color when Enter is
    pressed on anything else.
- Sent to generator: the resolution and resolution rule, which the generation panel owns, with an Edit button that
  emits `edit_resolution_requested`. It shows only while `set_resolution_shown` says a Stable Diffusion panel is
  loaded.

The panel is a `src.ui.layout.panel_fit.FitContent`, planned in the space the Tools panel gives it:
- Side: one column. The geometry block takes one row where that fits across. Presets keep a label column where the
  Fit buttons fit beside it, and otherwise put each label over its row. Buttons that don't fit in one row go in a
  two-column grid.
- Strip: Position and size, Size presets and Sent to generator are columns. A short strip puts the geometry block on
  one row, and section headers are optional.
- Recent and Custom are optional, then Sent to generator: a plan without room for them moves them to
  `overflow_content`, which the Tools panel shows in its More popover.
"""
from typing import Optional

from PySide6.QtCore import QEvent, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QWidget

from src.config.cache import Cache
from src.config.key_config import KeyConfig
from src.controller.generation_area_controller import apply_generation_area_frame, record_generation_area_size
from src.image.layers.image_stack import ImageStack
from src.ui.button_weight import ButtonWeight, set_button_weight
from src.ui.ink_style import signal_color
from src.ui.input_fields.geometry_block import HEIGHT, WIDTH, X, Y, GeometryBlock
from src.ui.layout.panel_fit import REQUIRED, FitItem, FitPlanner, Orientation, Placement
from src.ui.panel.tool_control_panels.fit_tool_panel import FitToolPanel
from src.ui.widget.panel_section import PanelSection
from src.undo_stack import UndoStack
from src.util.generation_area_utils import full_image_frame, square_frame, recent_frames, parse_size, size_to_str, \
    previous_frame

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.tool_control_panel.generation_area_tool_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


POSITION_SECTION_TITLE = _tr('Position and size')
PRESETS_SECTION_TITLE = _tr('Size presets')
GENERATOR_SECTION_TITLE = _tr('Sent to generator')
FIT_LABEL = _tr('Fit')
RECENT_LABEL = _tr('Recent')
CUSTOM_LABEL = _tr('Custom')
FRAME_LABEL_FULL_IMAGE = _tr('Full image')
FRAME_LABEL_SQUARE = _tr('Square')
FRAME_LABEL_PREVIOUS = _tr('Previous')
FRAME_TOOLTIP_FULL_IMAGE = _tr('Resize the generation area to cover the entire image.')
FRAME_TOOLTIP_SQUARE = _tr('Resize the generation area to the largest square that fits in the image.')
FRAME_TOOLTIP_PREVIOUS = _tr('Resize the generation area to the last size it had ({key}).')
FRAME_TOOLTIP_RECENT = _tr('Resize the generation area to a recently used size.')
FRAME_TOOLTIP_EMPTY = _tr('Sizes you use appear here.')
EMPTY_SLOT_TEXT = _tr('-')
CUSTOM_FRAME_PLACEHOLDER = _tr('768 or 640x480')
CUSTOM_FRAME_TOOLTIP = _tr('Type a size like 768 or 640x480 and press Enter to resize the generation area.')
CUSTOM_FRAME_HINT = _tr('Not a size: try 768 or 640x480')
RESOLUTION_LINE = _tr('Generates at {width} x {height}')
RESOLUTION_SUMMARY = _tr('{resolution}, {rule}')
EDIT_RESOLUTION_TEXT = _tr('Edit')
EDIT_RESOLUTION_TOOLTIP = _tr('Change the resolution and resolution rule in the Image generation panel.')

UNDO_GESTURE = 'GenerationAreaToolPanel.drag'
RECENT_FRAME_COUNT = 4
GRID_COLUMNS = 2
SECTION_SPACING = 10
ROW_SPACING = 4

# The planned items, in placement order:
GEOMETRY_ITEM = FitItem(REQUIRED, 2)
PRESETS_ITEM = FitItem(REQUIRED, 2)
RECENT_ITEM = FitItem(1, 2)
GENERATOR_ITEM = FitItem(2)
HEADERS_ITEM = FitItem(3)
# Forms of the geometry item. ROOMY takes more of the cross axis: one row in a side panel, two in a strip.
ROOMY = 0
TIGHT = 1
# Forms of the presets item:
LABEL_COLUMN = 0
LABELS_ABOVE = 1
# Forms of the recent item:
SLOTS_IN_ROW = 0
SLOTS_IN_GRID = 1


class GenerationAreaToolPanel(FitToolPanel):
    """Generation area tool control panel.

    Without a host that calls `set_fit_space`, the panel plans for its own size when resized.
    """

    edit_resolution_requested = Signal()
    _area_shown = Signal()

    def __init__(self, image_stack: ImageStack, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image_stack = image_stack
        # The area the panel last set, while its change signal is being handled:
        self._applying_area: Optional[QRect] = None
        self._resolution_shown = False

        # Position and size:
        self._geometry = GeometryBlock(parent=self)
        self._geometry.valueChanged.connect(self._geometry_changed)
        for name in (X, Y, WIDTH, HEIGHT):
            field = self._geometry.field(name)
            field.dragStarted.connect(self._drag_started)
            field.dragFinished.connect(self._drag_finished)
        for name in (WIDTH, HEIGHT):
            field = self._geometry.field(name)
            field.dragFinished.connect(self._record_area_size)
            field.entryCommitted.connect(self._record_area_size)
        self._position_section = PanelSection(POSITION_SECTION_TITLE, self._geometry, parent=self)
        self._position_section.bind_summary(self._geometry.summary_text, self._area_shown,
                                            self._geometry.valueChanged)

        # Size presets:
        self._fit_label = QLabel(FIT_LABEL, self)
        self._full_image_button = self._frame_button(FRAME_LABEL_FULL_IMAGE, FRAME_TOOLTIP_FULL_IMAGE)
        self._full_image_button.clicked.connect(lambda: self._apply_frame(
            full_image_frame(image_stack.size, image_stack.max_generation_area_size)))
        self._square_button = self._frame_button(FRAME_LABEL_SQUARE, FRAME_TOOLTIP_SQUARE)
        self._square_button.clicked.connect(lambda: self._apply_frame(
            square_frame(image_stack.size, image_stack.max_generation_area_size)))
        self._previous_button = self._frame_button(FRAME_LABEL_PREVIOUS, FRAME_TOOLTIP_PREVIOUS.format(
            key=KeyConfig().get(KeyConfig.PREVIOUS_GENERATION_FRAME_KEY)))
        self._previous_button.clicked.connect(self._apply_previous_frame)
        self._fit_row = QWidget(self)
        self._fit_layout = self._row_grid(self._fit_row)

        self._recent_label = QLabel(RECENT_LABEL, self)
        self._recent_buttons: list[QPushButton] = []
        self._recent_sizes: list[Optional[QSize]] = [None] * RECENT_FRAME_COUNT
        for index in range(RECENT_FRAME_COUNT):
            button = self._frame_button(EMPTY_SLOT_TEXT, FRAME_TOOLTIP_RECENT)
            button.clicked.connect(lambda _checked=False, slot=index: self._apply_recent_frame(slot))
            self._recent_buttons.append(button)
        self._recent_row = QWidget(self)
        self._recent_layout = self._row_grid(self._recent_row)
        self._custom_label = QLabel(CUSTOM_LABEL, self)
        self._custom_input = QLineEdit(self)
        self._custom_input.setPlaceholderText(CUSTOM_FRAME_PLACEHOLDER)
        self._custom_input.setToolTip(CUSTOM_FRAME_TOOLTIP)
        self._custom_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._custom_input.returnPressed.connect(self._apply_custom_frame)
        self._custom_input.textEdited.connect(lambda _text: self._set_custom_invalid(False))
        self._custom_label.setBuddy(self._custom_input)
        self._custom_hint = QLabel(CUSTOM_FRAME_HINT, self)
        self._custom_hint.setVisible(False)
        # Recent and Custom, which move to the More popover together:
        self._recent_box = QWidget(self)
        self._recent_box_layout = self._row_grid(self._recent_box)
        self._presets_body = QWidget(self)
        self._presets_layout = self._row_grid(self._presets_body)
        self._presets_section = PanelSection(PRESETS_SECTION_TITLE, self._presets_body, parent=self)

        # Sent to generator:
        # Two unwrapped lines: a grid sizes a wrapped label for its cell's full width, wider than the capped section.
        self._resolution_label = QLabel(self)
        self._rule_label = QLabel(self)
        for label in (self._resolution_label, self._rule_label):
            label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        self._edit_button = QPushButton(EDIT_RESOLUTION_TEXT, self)
        self._edit_button.setToolTip(EDIT_RESOLUTION_TOOLTIP)
        set_button_weight(self._edit_button, ButtonWeight.FLAT)
        self._edit_button.clicked.connect(self.edit_resolution_requested)
        generator_body = QWidget(self)
        generator_layout = self._row_grid(generator_body)
        generator_layout.addWidget(self._resolution_label, 0, 0)
        generator_layout.addWidget(self._edit_button, 0, 1, 2, 1, Qt.AlignmentFlag.AlignTop)
        generator_layout.addWidget(self._rule_label, 1, 0)
        generator_layout.setColumnStretch(0, 1)
        self._generator_section = PanelSection(GENERATOR_SECTION_TITLE, generator_body, parent=self)
        self._generator_section.bind_summary(self.resolution_summary, self._area_shown)

        self._sections = (self._position_section, self._presets_section, self._generator_section)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(SECTION_SPACING)

        self._update_custom_hint_color()
        self._show_area(image_stack.generation_area)
        self._update_resolution_line()
        image_stack.generation_area_bounds_changed.connect(self._area_changed)
        image_stack.size_changed.connect(self._image_size_changed)
        cache = Cache()
        cache.connect(self, Cache.RECENT_GENERATION_AREA_SIZES, self._update_frames)
        cache.connect(self, Cache.GENERATION_SIZE, self._update_resolution_line)
        cache.connect(self, Cache.GENERATION_RESOLUTION_RULE, self._update_resolution_line)

        self._planner = FitPlanner([GEOMETRY_ITEM, PRESETS_ITEM, RECENT_ITEM, GENERATOR_ITEM, HEADERS_ITEM],
                                   self._apply_fit, self._measure_fit)
        self._apply_fit(Orientation.SIDE, (TIGHT, LABEL_COLUMN, SLOTS_IN_GRID, 0, 0))

    def _frame_button(self, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text, self)
        button.setToolTip(tooltip)
        button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        return button

    def _row_grid(self, widget: QWidget) -> QGridLayout:
        layout = self._body_grid(widget)
        layout.setSpacing(ROW_SPACING)
        return layout

    # -----------------------------------------------------------------------------------------------------------------
    # Access
    # -----------------------------------------------------------------------------------------------------------------

    @property
    def geometry_block(self) -> GeometryBlock:
        """The X, Y, W and H fields."""
        return self._geometry

    @property
    def full_image_button(self) -> QPushButton:
        """The Fit row's Full image button."""
        return self._full_image_button

    @property
    def square_button(self) -> QPushButton:
        """The Fit row's Square button."""
        return self._square_button

    @property
    def previous_button(self) -> QPushButton:
        """The Fit row's Previous button."""
        return self._previous_button

    @property
    def recent_buttons(self) -> list[QPushButton]:
        """The Recent row's slots, in order."""
        return list(self._recent_buttons)

    @property
    def custom_input(self) -> QLineEdit:
        """The Custom size field."""
        return self._custom_input

    @property
    def custom_hint(self) -> QLabel:
        """The hint under the Custom field, shown after Enter on text that isn't a size."""
        return self._custom_hint

    @property
    def generator_section(self) -> PanelSection:
        """The Sent to generator section."""
        return self._generator_section

    @property
    def resolution_label(self) -> QLabel:
        """The read-only resolution line."""
        return self._resolution_label

    @property
    def rule_label(self) -> QLabel:
        """The read-only resolution rule line."""
        return self._rule_label

    @property
    def edit_resolution_button(self) -> QPushButton:
        """The button that asks to open the Image generation panel."""
        return self._edit_button

    def set_resolution_shown(self, shown: bool) -> None:
        """Shows or hides the Sent to generator section. It shows only while a Stable Diffusion panel owns the
        resolution."""
        if shown != self._resolution_shown:
            self._resolution_shown = shown
            self._generator_section.setVisible(shown)
            self._refit()

    def resolution_shown(self) -> bool:
        """Returns whether the panel offers the Sent to generator section."""
        return self._resolution_shown

    # -----------------------------------------------------------------------------------------------------------------
    # Generation area
    # -----------------------------------------------------------------------------------------------------------------

    def _show_area(self, area: QRect) -> None:
        """Sets the fields and their limits from the area, and updates the presets that depend on its size."""
        image_stack = self._image_stack
        min_size = image_stack.min_generation_area_size
        max_size = image_stack.max_generation_area_size.boundedTo(image_stack.size)
        geometry = self._geometry
        geometry.set_limits(X, 0, max(0, image_stack.width - area.width()))
        geometry.set_limits(Y, 0, max(0, image_stack.height - area.height()))
        geometry.set_limits(WIDTH, min(min_size.width(), max_size.width()), max_size.width())
        geometry.set_limits(HEIGHT, min(min_size.height(), max_size.height()), max_size.height())
        geometry.set_values(**{X: area.x(), Y: area.y(), WIDTH: area.width(), HEIGHT: area.height()})
        self._update_frames()
        self._area_shown.emit()

    def _area_changed(self, area: QRect) -> None:
        if self._applying_area is not None and area == self._applying_area:
            # The fields already hold this area. Setting them again would recapture the ratio lock's ratio from
            # rounded values. Only the position limits depend on the new size:
            geometry = self._geometry
            geometry.set_limits(X, 0, max(0, self._image_stack.width - area.width()))
            geometry.set_limits(Y, 0, max(0, self._image_stack.height - area.height()))
            self._update_frames()
            self._area_shown.emit()
            return
        self._show_area(area)

    def _image_size_changed(self, size: QSize) -> None:
        self._geometry.set_image_size(size)
        self._show_area(self._image_stack.generation_area)

    def _geometry_changed(self, _name: str, _value: int | float) -> None:
        """Sets the area from all four fields, which already hold the value the ratio lock gives a linked field."""
        geometry = self._geometry
        area = QRect(int(geometry.value(X)), int(geometry.value(Y)), int(geometry.value(WIDTH)),
                     int(geometry.value(HEIGHT)))
        if area == self._image_stack.generation_area:
            return
        self._applying_area = area
        try:
            self._image_stack.generation_area = area
        finally:
            self._applying_area = None

    @staticmethod
    def _drag_started() -> None:
        UndoStack().begin_gesture(UNDO_GESTURE)

    @staticmethod
    def _drag_finished() -> None:
        UndoStack().end_gesture()

    def _record_area_size(self) -> None:
        record_generation_area_size(self._image_stack.generation_area.size())

    # -----------------------------------------------------------------------------------------------------------------
    # Presets
    # -----------------------------------------------------------------------------------------------------------------

    def _apply_frame(self, size: QSize) -> None:
        apply_generation_area_frame(self._image_stack, size)

    def _apply_previous_frame(self) -> None:
        size = previous_frame(Cache().get(Cache.RECENT_GENERATION_AREA_SIZES),
                              self._image_stack.generation_area.size())
        if size is not None:
            self._apply_frame(size)

    def _apply_recent_frame(self, slot: int) -> None:
        size = self._recent_sizes[slot]
        if size is not None:
            self._apply_frame(size)

    def _apply_custom_frame(self) -> None:
        text = self._custom_input.text()
        if text.strip() == '':
            self._set_custom_invalid(False)
            return
        size = parse_size(text)
        if size is None:
            self._set_custom_invalid(True)
            return
        self._set_custom_invalid(False)
        self._custom_input.clear()
        self._apply_frame(size)

    def custom_invalid(self) -> bool:
        """Returns whether the Custom field's hint marks its text as not a size."""
        return bool(self._custom_hint.property('invalid'))

    def _set_custom_invalid(self, invalid: bool) -> None:
        if invalid == self.custom_invalid():
            return
        self._custom_hint.setProperty('invalid', invalid)
        self._custom_hint.setVisible(invalid)
        self._update_custom_hint_color()
        self._refit()

    def _update_custom_hint_color(self) -> None:
        """Draws the hint, and the Custom field's text while it is invalid, in the signal color."""
        signal = signal_color()
        if signal is None:
            signal = QColor(Qt.GlobalColor.red)
        hint_palette = QPalette(self.palette())
        hint_palette.setColor(QPalette.ColorRole.WindowText, signal)
        self._custom_hint.setPalette(hint_palette)
        field_palette = QPalette(self.palette())
        if self.custom_invalid():
            field_palette.setColor(QPalette.ColorRole.Text, signal)
        self._custom_input.setPalette(field_palette)

    def _update_frames(self, *_args) -> None:
        """Fills the Recent slots and enables Previous.

        A size that is still recent keeps its slot. New sizes fill the empty slots in order, newest first.
        """
        recent = Cache().get(Cache.RECENT_GENERATION_AREA_SIZES)
        sizes = recent_frames(recent, self._image_stack.size, self._image_stack.max_generation_area_size,
                              RECENT_FRAME_COUNT)
        slots = [size if size is not None and size in sizes else None for size in self._recent_sizes]
        unplaced = [size for size in sizes if size not in slots]
        for index, size in enumerate(slots):
            if size is None and len(unplaced) > 0:
                slots[index] = unplaced.pop(0)
        self._recent_sizes = slots
        for button, size in zip(self._recent_buttons, slots):
            button.setText(EMPTY_SLOT_TEXT if size is None else size_to_str(size))
            button.setToolTip(FRAME_TOOLTIP_EMPTY if size is None else FRAME_TOOLTIP_RECENT)
            button.setEnabled(size is not None)
        self._previous_button.setEnabled(previous_frame(recent, self._image_stack.generation_area.size()) is not None)

    # -----------------------------------------------------------------------------------------------------------------
    # Resolution
    # -----------------------------------------------------------------------------------------------------------------

    @staticmethod
    def _resolution_text() -> str:
        size = Cache().get(Cache.GENERATION_SIZE)
        return RESOLUTION_LINE.format(width=size.width(), height=size.height())

    @staticmethod
    def _rule_text() -> str:
        cache = Cache()
        return cache.get_option_display(cache.get(Cache.GENERATION_RESOLUTION_RULE))

    def resolution_summary(self) -> str:
        """Returns the resolution and rule on one line, as "Generates at 768 x 768, Match area"."""
        return RESOLUTION_SUMMARY.format(resolution=self._resolution_text(), rule=self._rule_text())

    def _update_resolution_line(self, *_args) -> None:
        self._resolution_label.setText(self._resolution_text())
        self._rule_label.setText(self._rule_text())
        self._area_shown.emit()

    def changeEvent(self, event: Optional[QEvent]) -> None:  # pylint: disable=invalid-name
        """Redraws the Custom hint in the new signal color after a palette change."""
        super().changeEvent(event)
        if event is not None and event.type() == QEvent.Type.PaletteChange:
            self._update_custom_hint_color()

    # -----------------------------------------------------------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------------------------------------------------------

    def _apply_fit(self, orientation: Orientation, placement: Placement) -> None:
        geometry_form, presets_form, recent, generator, headers = placement
        self._orientation = orientation
        strip = orientation == Orientation.STRIP
        # ROOMY is one row in a side panel, where width is the cross axis, and two rows in a strip:
        self._geometry.set_horizontal((geometry_form == ROOMY) != strip)
        show_headers = not strip or headers is not None
        for section in self._sections:
            section.set_header_visible(show_headers)
        self._arrange_presets(presets_form == LABEL_COLUMN, recent)
        self._arrange_sections(strip, generator is not None)

    def _arrange_presets(self, label_column: bool, recent_form: Optional[int]) -> None:
        """Lays out the Fit row, then Recent and Custom, beside a shared label column or each under its label. Recent
        and Custom go to the overflow when the plan leaves them out, and the Recent slots there take the grid."""
        self._arrange_buttons(self._fit_layout, (self._full_image_button, self._square_button,
                                                 self._previous_button), label_column)
        self._arrange_buttons(self._recent_layout, tuple(self._recent_buttons), recent_form == SLOTS_IN_ROW)
        labels = (self._fit_label, self._recent_label, self._custom_label)
        # The Fit row and the Recent box are separate grids, so the label column gets one width in both:
        label_width = max(label.sizeHint().width() for label in labels) if label_column else 0
        for label in labels:
            label.setMinimumWidth(label_width)

        box = self._recent_box_layout
        self._clear(box, (self._recent_label, self._recent_row, self._custom_label, self._custom_input,
                          self._custom_hint))
        rows = ((self._recent_label, self._recent_row), (self._custom_label, self._custom_input))
        row = 0
        for label, content in rows:
            if label_column:
                box.addWidget(label, row, 0)
                box.addWidget(content, row, 1)
            else:
                box.addWidget(label, row, 0, 1, 2)
                box.addWidget(content, row + 1, 0, 1, 2)
                row += 1
            row += 1
        box.addWidget(self._custom_hint, row, 1 if label_column else 0, 1, 1 if label_column else 2)
        box.setColumnStretch(1, 1)

        layout = self._presets_layout
        self._clear(layout, (self._fit_label, self._fit_row, self._recent_box))
        if label_column:
            layout.addWidget(self._fit_label, 0, 0)
            layout.addWidget(self._fit_row, 0, 1)
        else:
            layout.addWidget(self._fit_label, 0, 0, 1, 2)
            layout.addWidget(self._fit_row, 1, 0, 1, 2)
        layout.setColumnStretch(1, 1)
        if recent_form is not None:
            self._overflow_layout.removeWidget(self._recent_box)
            layout.addWidget(self._recent_box, 2, 0, 1, 2)
        else:
            self._overflow_layout.addWidget(self._recent_box)
        # Moving between the section and the overflow reparents the box, which hides it:
        self._recent_box.show()

    @staticmethod
    def _arrange_buttons(layout: QGridLayout, buttons: tuple[QPushButton, ...], one_row: bool) -> None:
        """Puts buttons in one row, or in a grid of `GRID_COLUMNS`, with equal columns."""
        FitToolPanel._clear(layout, buttons)
        columns = len(buttons) if one_row else GRID_COLUMNS
        for index, button in enumerate(buttons):
            layout.addWidget(button, index // columns, index % columns)
        for column in range(columns):
            layout.setColumnStretch(column, 1)

    def _arrange_sections(self, strip: bool, generator_placed: bool) -> None:
        """Places the sections in strip columns or one side column, with spare room after them. The Sent to generator
        section goes to the overflow when the plan leaves it out while it is shown."""
        grid = self._grid
        self._clear(grid, self._sections)
        generator_in_panel = generator_placed or not self._resolution_shown
        if generator_in_panel:
            self._overflow_layout.removeWidget(self._generator_section)
        else:
            self._overflow_layout.addWidget(self._generator_section)
        shown = [self._position_section, self._presets_section]
        if generator_in_panel:
            shown.append(self._generator_section)
        top = Qt.AlignmentFlag.AlignTop
        for index, section in enumerate(shown):
            if strip:
                grid.addWidget(section, 0, index, top)
            else:
                grid.addWidget(section, index, 0, top)
        if strip:
            grid.setRowStretch(1, 1)
            used_columns = len(shown)
        else:
            grid.setRowStretch(len(shown), 1)
            used_columns = 1
        for column in range(used_columns):
            grid.setColumnStretch(column, 1)
        grid.setColumnStretch(used_columns, 0)
        # Moving between the panel and the overflow reparents the section, which hides it:
        self._generator_section.setVisible(self._resolution_shown)
        for section in self._sections:
            self._cap_width(section)
