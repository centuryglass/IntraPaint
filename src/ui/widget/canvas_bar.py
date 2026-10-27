"""The bar under the canvas: the active tool's control hints on the left, view controls on the right.

- Hints are "keycap + verb" pairs split from a tool's `get_input_hint()` text. As many as fit show in one line, then a
  "?" button that lists every pair in a popover.
- The view controls are an optional Rulers toggle and navigation window button, the zoom field with its - and +
  buttons, and Reset view.
- The bar plans with `plan_fit` on its own width, which is the canvas column's. As it narrows, hint pairs move into
  "?" first, then Reset view's label gives way to its glyph, then Rulers and the navigation button move into the "..."
  popover.
- The bar's minimum size is its smallest plan, so what it shows never widens the window.
"""
import math
import re
from functools import partial
from typing import Optional

from PySide6.QtCore import QEvent, QSize, Qt, Signal, SignalInstance
from PySide6.QtGui import QAction, QIcon, QResizeEvent
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout,
                               QWidget)

from src.config.application_config import AppConfig
from src.config.key_config import KeyConfig
from src.ui.button_weight import ButtonWeight, set_button_weight
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.slider_field import SliderField
from src.ui.layout.panel_fit import FitItem, FitPlanner, Orientation, Placement, fresh_minimum_size
from src.ui.widget.image_graphics_view import MIN_IMAGE_ZOOM, MAX_IMAGE_ZOOM, ZOOM_FACTOR
from src.ui.widget.panel_header import BUTTON_SIZE, GlyphButton, PanelPopover
from src.ui.widget.shortcut_tooltip import set_shortcut_tooltip
from src.util.shared_constants import PROJECT_DIR

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.canvas_bar'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


ZOOM_FIELD_LABEL = _tr('Zoom')
ZOOM_IN_TOOLTIP = _tr('Zoom in')
ZOOM_OUT_TOOLTIP = _tr('Zoom out')
RESET_VIEW_LABEL = _tr('Reset view')
RESET_VIEW_TOOLTIP = _tr('Restore default image zoom and offset')
RULERS_LABEL = _tr('Rulers')
RULERS_TOOLTIP = _tr('Show rulers')
RULERS_DESCRIPTION = _tr('Right-click for ruler highlight options')
NAVIGATION_TOOLTIP = _tr('Navigation window')
HINTS_TOOLTIP = _tr('Controls for this tool')
MORE_TOOLTIP = _tr('More view options')
RULER_HIGHLIGHTS_LABEL = _tr('Highlight generation area and selection')
HINTS_LABEL = _tr('Tool control hints')
MENU_ACTION_SHOW_HINTS = _tr('Show tool control hints')
MENU_ACTION_HIDE_HINTS = _tr('Hide tool control hints')

ICON_PATH_NAVIGATION = f'{PROJECT_DIR}/resources/icons/tabs/navigation.svg'

BAR_HEIGHT = 32
BAR_MARGIN = 8
BAR_SPACING = 6
HINT_SPACING = 12
ZOOM_FIELD_WIDTH = 120
ICON_SIZE = 18

# Separators between the "keycap + verb" pairs in `BaseTool.get_input_hint` text:
HINT_SEPARATOR = re.compile(r'<br\s*/?>|</br>| - ')

# Rulers and the navigation button: in the bar, or left out into "...". Placed first, so they leave the bar last.
TOGGLES_ITEM = 0
# Reset view's label: shown, or left out for its glyph.
LABELS_ITEM = 1
# Hint pairs: form n leaves the last n pairs to "?", and leaving the item out leaves all of them.
HINTS_ITEM = 2


def split_hint_pairs(hint_text: str) -> list[str]:
    """Returns the rich text "keycap + verb" pairs in a tool's input hint, in order."""
    return [pair.strip() for pair in HINT_SEPARATOR.split(hint_text) if pair.strip() != '']


def _set_app_config(key: str, value: bool) -> None:
    AppConfig().set(key, value)


class ZoomField(SliderField):
    """A slider field for the view scale, shown as a percentage, with a fill and steps that follow the scale
    logarithmically, so each step and each pixel dragged zooms by the same factor."""

    def __init__(self, value: float, parent: Optional[QWidget] = None) -> None:
        super().__init__(ZOOM_FIELD_LABEL, value, MIN_IMAGE_ZOOM, MAX_IMAGE_ZOOM, parent=parent, step=0.001,
                         suffix='%', display_scale=100.0, decimals=0)

    def _fill_fraction(self) -> Optional[float]:
        assert self._minimum is not None and self._maximum is not None
        return math.log(self._value / self._minimum) / math.log(self._maximum / self._minimum)

    def _scrub_delta(self, delta_x: int) -> int | float:
        assert self._minimum is not None and self._maximum is not None
        ratio = self._maximum / self._minimum
        return self._press_value * (ratio ** (delta_x / max(self.width(), 1)) - 1)

    def _step_by(self, amount: int | float) -> None:
        """Zooms by `ZOOM_FACTOR` for each step in `amount`."""
        self.set_value(self._value * ZOOM_FACTOR ** (amount / self.step()))


class CanvasBar(QWidget):
    """Shows control hints and view controls under an image viewer, planning what fits in its width.

    Parameters
    ----------
    image_viewer: ImageViewer
        The viewer the zoom and reset controls act on.
    include_rulers: bool
        Whether to show the Rulers toggle, which follows `AppConfig.SHOW_RULERS`.
    include_navigation: bool
        Whether to show the navigation window button, which emits `navigation_requested`.
    ruler_actions: Optional[list[QAction]]
        Actions for the Rulers toggle's context menu.
    """

    navigation_requested = Signal()

    def __init__(self, image_viewer: ImageViewer, include_rulers: bool = False, include_navigation: bool = False,
                 ruler_actions: Optional[list[QAction]] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image_viewer = image_viewer
        self._hint_pairs: list[str] = []
        self._base_size = QSize(0, BAR_HEIGHT)
        self._planning = False
        self._syncing_zoom = False
        self._popover: Optional[PanelPopover] = None
        self.setFixedHeight(BAR_HEIGHT)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

        self._show_hint_action = QAction(MENU_ACTION_SHOW_HINTS, self)
        self._show_hint_action.triggered.connect(partial(_set_app_config, AppConfig.SHOW_TOOL_CONTROL_HINTS, True))
        self._hide_hint_action = QAction(MENU_ACTION_HIDE_HINTS, self)
        self._hide_hint_action.triggered.connect(partial(_set_app_config, AppConfig.SHOW_TOOL_CONTROL_HINTS, False))

        # The bar has no layout, so its row's minimum size never reaches the window:
        self._row = QWidget(self)
        row_layout = QHBoxLayout(self._row)
        row_layout.setContentsMargins(BAR_MARGIN, 0, BAR_MARGIN, 0)
        row_layout.setSpacing(BAR_SPACING)

        self._hint_layout = QHBoxLayout()
        self._hint_layout.setContentsMargins(0, 0, 0, 0)
        self._hint_layout.setSpacing(HINT_SPACING)
        self._hint_labels: list[QLabel] = []
        row_layout.addLayout(self._hint_layout)
        self._hint_button = self._tool_button('?', HINTS_TOOLTIP)
        self._hint_button.clicked.connect(self._show_hint_popover)
        row_layout.addWidget(self._hint_button)
        row_layout.addStretch(1)

        self._rulers_button: Optional[QPushButton] = None
        if include_rulers:
            self._rulers_button = QPushButton(RULERS_LABEL)
            self._rulers_button.setCheckable(True)
            self._rulers_button.setChecked(AppConfig().get(AppConfig.SHOW_RULERS))
            set_button_weight(self._rulers_button, ButtonWeight.FLAT)
            set_shortcut_tooltip(self._rulers_button, RULERS_TOOLTIP, KeyConfig.TOGGLE_RULERS_SHORTCUT,
                                 RULERS_DESCRIPTION)
            assert isinstance(self._rulers_button.toggled, SignalInstance)
            self._rulers_button.toggled.connect(partial(_set_app_config, AppConfig.SHOW_RULERS))
            self._rulers_button.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
            self._rulers_button.addActions(ruler_actions if ruler_actions is not None else [])
            AppConfig().connect(self, AppConfig.SHOW_RULERS, self._rulers_button.setChecked)
            row_layout.addWidget(self._rulers_button)

        self._navigation_button: Optional[QToolButton] = None
        if include_navigation:
            self._navigation_button = QToolButton()
            self._navigation_button.setIcon(QIcon(ICON_PATH_NAVIGATION))
            self._navigation_button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
            self._navigation_button.setAutoRaise(True)
            self._navigation_button.setAccessibleName(NAVIGATION_TOOLTIP)
            set_shortcut_tooltip(self._navigation_button, NAVIGATION_TOOLTIP, KeyConfig.NAVIGATION_WINDOW_SHORTCUT)
            self._navigation_button.clicked.connect(self.navigation_requested)
            row_layout.addWidget(self._navigation_button)

        self._zoom_out_button = self._tool_button('−', ZOOM_OUT_TOOLTIP, KeyConfig.ZOOM_OUT)
        self._zoom_out_button.setAutoRaise(False)
        self._zoom_out_button.clicked.connect(self._zoom_out)
        row_layout.addWidget(self._zoom_out_button)
        self._zoom_field = ZoomField(image_viewer.scene_scale)
        self._zoom_field.setFixedWidth(ZOOM_FIELD_WIDTH)
        self._zoom_field.valueChanged.connect(self._zoom_field_changed)
        row_layout.addWidget(self._zoom_field)
        self._zoom_in_button = self._tool_button('+', ZOOM_IN_TOOLTIP, KeyConfig.ZOOM_IN)
        self._zoom_in_button.setAutoRaise(False)
        self._zoom_in_button.clicked.connect(self._zoom_in)
        row_layout.addWidget(self._zoom_in_button)

        self._reset_button = QPushButton(RESET_VIEW_LABEL)
        self._reset_button.setToolTip(RESET_VIEW_TOOLTIP)
        self._reset_glyph = GlyphButton(GlyphButton.RESET, RESET_VIEW_LABEL)
        self._reset_glyph.setToolTip(RESET_VIEW_TOOLTIP)
        self._reset_glyph.setAutoRaise(False)
        for button in (self._reset_button, self._reset_glyph):
            assert isinstance(button.clicked, SignalInstance)
            button.clicked.connect(self._reset_view)
            row_layout.addWidget(button)

        self._more_button = GlyphButton(GlyphButton.MORE, MORE_TOOLTIP)
        self._more_button.clicked.connect(self._show_more_popover)
        row_layout.addWidget(self._more_button)

        self._planner = FitPlanner(self._fit_items(), self._apply_fit, self._measure_fit)
        image_viewer.scale_changed.connect(self._view_changed)
        image_viewer.offset_changed.connect(self._view_changed)
        AppConfig().connect(self, AppConfig.SHOW_TOOL_CONTROL_HINTS, self._hints_shown_changed)
        self._hints_shown_changed(AppConfig().get(AppConfig.SHOW_TOOL_CONTROL_HINTS))
        self._view_changed()

    def _tool_button(self, text: str, tooltip: str, config_key: Optional[str] = None) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setAutoRaise(True)
        button.setFixedSize(BUTTON_SIZE, BUTTON_SIZE)
        button.setAccessibleName(tooltip)
        if config_key is None:
            button.setToolTip(tooltip)
        else:
            set_shortcut_tooltip(button, tooltip, config_key)
        return button

    # -----------------------------------------------------------------------------------------------------------------
    # Content
    # -----------------------------------------------------------------------------------------------------------------

    @property
    def zoom_field(self) -> ZoomField:
        """Returns the field showing and setting the view scale."""
        return self._zoom_field

    @property
    def reset_buttons(self) -> tuple[QPushButton, GlyphButton]:
        """Returns Reset view's labeled and glyph forms."""
        return self._reset_button, self._reset_glyph

    @property
    def hint_pairs(self) -> list[str]:
        """Returns every hint pair, shown or not."""
        return list(self._hint_pairs)

    def shown_hint_count(self) -> int:
        """Returns how many hint pairs the bar shows."""
        return sum(1 for label in self._hint_labels if not label.isHidden())

    def set_hint_text(self, hint_text: str) -> None:
        """Replaces the hints with the pairs in a tool's `get_input_hint()` text."""
        self._hint_pairs = split_hint_pairs(hint_text)
        while len(self._hint_labels) > len(self._hint_pairs):
            label = self._hint_labels.pop()
            self._hint_layout.removeWidget(label)
            label.deleteLater()
        while len(self._hint_labels) < len(self._hint_pairs):
            label = QLabel()
            label.setTextFormat(Qt.TextFormat.RichText)
            self._hint_labels.append(label)
            self._hint_layout.addWidget(label)
        for label, pair in zip(self._hint_labels, self._hint_pairs):
            label.setText(pair)
        self._content_changed()

    def _hints_shown_changed(self, shown: bool) -> None:
        self.removeAction(self._show_hint_action if shown else self._hide_hint_action)
        self.addAction(self._hide_hint_action if shown else self._show_hint_action)
        self._content_changed()

    def _fit_items(self) -> list[FitItem]:
        return [FitItem(1), FitItem(2), FitItem(3, max(1, len(self._hint_pairs)))]

    def _content_changed(self) -> None:
        """Measures the smallest plan again and plans for the current size."""
        if self._planner.items[HINTS_ITEM].form_count != max(1, len(self._hint_pairs)):
            self._planner = FitPlanner(self._fit_items(), self._apply_fit, self._measure_fit)
        self._plan(force=True)

    # -----------------------------------------------------------------------------------------------------------------
    # View controls
    # -----------------------------------------------------------------------------------------------------------------

    def _view_changed(self, *_) -> None:
        """Shows the view's scale, and enables Reset view while the view isn't at its default."""
        self._syncing_zoom = True
        try:
            self._zoom_field.set_value(self._image_viewer.scene_scale)
        finally:
            self._syncing_zoom = False
        at_default = self._image_viewer.is_at_default_view and not self._image_viewer.follow_generation_area
        for button in (self._reset_button, self._reset_glyph):
            button.setEnabled(not at_default)

    def _zoom_field_changed(self, scale: float) -> None:
        if not self._syncing_zoom:
            self._image_viewer.scene_scale = scale

    def _zoom_in(self) -> None:
        self._image_viewer.zoom_in()

    def _zoom_out(self) -> None:
        self._image_viewer.zoom_out()

    def _reset_view(self) -> None:
        self._image_viewer.follow_generation_area = False
        self._image_viewer.reset_scale()
        self._view_changed()

    # -----------------------------------------------------------------------------------------------------------------
    # Popovers
    # -----------------------------------------------------------------------------------------------------------------

    def _open_popover(self, content: QWidget, anchor: QWidget, align_left: bool) -> None:
        if self._popover is None:
            self._popover = PanelPopover(self)
        self._popover.set_content(content)
        self._popover.popup_below(anchor, align_left)

    def _show_hint_popover(self) -> None:
        """Lists every hint pair."""
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        for pair in self._hint_pairs:
            label = QLabel(pair)
            label.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(label)
        self._open_popover(content, self._hint_button, True)

    def more_popover_content(self) -> QWidget:
        """Returns a new widget with the view options that don't fit in the bar, plus the hints toggle."""
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        config = AppConfig()
        options = [(HINTS_LABEL, AppConfig.SHOW_TOOL_CONTROL_HINTS)]
        if self._rulers_button is not None:
            options = [(RULERS_LABEL, AppConfig.SHOW_RULERS),
                       (RULER_HIGHLIGHTS_LABEL, AppConfig.SHOW_RULER_HIGHLIGHTS), *options]
        for label, key in options:
            check_box = QCheckBox(label, content)
            check_box.setChecked(config.get(key))
            check_box.toggled.connect(partial(_set_app_config, key))
            layout.addWidget(check_box)
        if self._navigation_button is not None:
            navigation_button = QPushButton(QIcon(ICON_PATH_NAVIGATION), NAVIGATION_TOOLTIP, content)
            set_button_weight(navigation_button, ButtonWeight.FLAT)
            set_shortcut_tooltip(navigation_button, NAVIGATION_TOOLTIP, KeyConfig.NAVIGATION_WINDOW_SHORTCUT)
            assert isinstance(navigation_button.clicked, SignalInstance)
            navigation_button.clicked.connect(self._navigation_from_popover)
            layout.addWidget(navigation_button)
        return content

    def _show_more_popover(self) -> None:
        self._open_popover(self.more_popover_content(), self._more_button, False)

    def _navigation_from_popover(self) -> None:
        if self._popover is not None:
            self._popover.hide()
        self.navigation_requested.emit()

    # -----------------------------------------------------------------------------------------------------------------
    # Fit planning
    # -----------------------------------------------------------------------------------------------------------------

    def _apply_fit(self, _orientation: Orientation, placement: Placement) -> None:
        """Arranges the bar for a placement. Each item shows only while the items that leave after it are shown, so
        the bar gives up hints, then labels, then toggles, and never shows an earlier one again as room frees up."""
        toggles_shown = placement[TOGGLES_ITEM] is not None
        labels_shown = toggles_shown and placement[LABELS_ITEM] is not None
        hints_on = AppConfig().get(AppConfig.SHOW_TOOL_CONTROL_HINTS)
        hint_form = placement[HINTS_ITEM]
        shown_hints = 0 if hint_form is None or not hints_on or not labels_shown \
            else len(self._hint_pairs) - hint_form
        for index, label in enumerate(self._hint_labels):
            label.setVisible(index < shown_hints)
        self._hint_button.setVisible(hints_on and shown_hints < len(self._hint_pairs))
        for toggle in (self._rulers_button, self._navigation_button):
            if toggle is not None:
                toggle.setVisible(toggles_shown)
        self._more_button.setVisible(not toggles_shown and (self._rulers_button is not None
                                                            or self._navigation_button is not None))
        self._reset_button.setVisible(labels_shown)
        self._reset_glyph.setVisible(not labels_shown)

    def _measure_fit(self) -> QSize:
        # fresh_minimum_size invalidates only the row's own layout, and the hint layout caches the labels it held:
        self._hint_layout.invalidate()
        return fresh_minimum_size(self._row)

    def _plan(self, force: bool = False) -> None:
        """Plans for the bar's width. With `force`, measures the smallest plan first, since the content changed."""
        if self._planning:
            return
        self._planning = True
        try:
            if force:
                base_size = self._planner.base_size(Orientation.STRIP)
                if base_size != self._base_size:
                    self._base_size = base_size
                    self.updateGeometry()
            self._planner.update(Orientation.STRIP, self.size(), force)
            self._row.layout().activate()
        finally:
            self._planning = False

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the smallest plan's width, at the bar's height."""
        return QSize(self._base_size.width(), BAR_HEIGHT)

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the smallest plan's width, at the bar's height."""
        return self.sizeHint()

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:  # pylint: disable=invalid-name
        """Plans for the new width."""
        super().resizeEvent(event)
        self._row.setGeometry(self.rect())
        self._plan()

    def changeEvent(self, event: QEvent) -> None:  # pylint: disable=invalid-name
        """Plans again when the font or style changes the controls' sizes."""
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._plan(force=True)
