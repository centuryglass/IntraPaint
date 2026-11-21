"""A small card of a brush tool's stroke settings that opens at the cursor on a right-click.

`QuickStrokeCard` is a plain child widget of the `ImageViewer`, not a popup window, so it can be placed at the cursor
on every platform and doesn't grab the mouse. Its fields are the Tools panel's (`build_stroke_fields`), so they write
the same `Cache` values and follow changes made anywhere. The owning tool decides when to open it and closes it on tool
changes. The card closes itself on Escape, a press outside it, the pointer leaving it, and a view or image change.

While shown, the card watches every application event (`eventFilter`), so that work is kept to a rectangle check. A
press on the canvas that closes the card is consumed, so it neither paints nor reopens the card.
"""
import os
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QMouseEvent, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.controller import color_controller
from src.ui.image_viewer import ImageViewer
from src.ui.input_fields.slider_field import SliderField
from src.ui.ink_style import POPUP_SHADOW_OFFSET
from src.ui.panel.mypaint_brush_panel import (FAV_CONFIG_KEY, MAX_FAVORITE_THUMBNAILS, THUMBNAIL_SIZE,
                                              BrushLibrary, active_brush_path, choose_brush)
from src.ui.panel.mypaint_brush_grid import brush_name
from src.ui.panel.tool_control_panels.stroke_block import StrokeKeys, build_stroke_fields
from src.ui.widget.color_pair_widget import ColorPairWidget
from src.ui.widget.color_picker.color_swatch_grid import SWATCH_SIZE, ColorSwatchGrid
from src.util.layout import add_layout

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.widget.quick_stroke_card'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


RECENT_COLORS_TOOLTIP = _tr('Recent colors: click to set the foreground color')

CARD_WIDTH = 220
CARD_MARGIN = 8
CARD_SPACING = 6
CARD_RADIUS = 4
# The card keeps this far from the viewer's edges:
EDGE_MARGIN = 8
# The card closes when the pointer is this far outside it with no button held:
CLOSE_MARGIN = 48
HEADER_ICON_SIZE = 16


class QuickStrokeCard(QFrame):
    """The stroke settings of one tool in a card, with a favorite brush row and a color row for tools that have them.

    `keys` picks the Size, Opacity and Hardness fields, and its `color_key` set adds the color row. With a `library`,
    the card adds a row of favorite brushes, which pick the brush `brush_config_key` names.

    `closed` is emitted whenever the card hides.
    """

    closed = Signal()

    def __init__(self, viewer: ImageViewer, keys: StrokeKeys, icon: QIcon, label: str,
                 library: Optional[BrushLibrary] = None, brush_config_key: str = Cache.MYPAINT_BRUSH) -> None:
        super().__init__(viewer)
        self._viewer = viewer
        self._library = library
        self._brush_config_key = brush_config_key
        self._filter_installed = False
        self.setAttribute(Qt.WidgetAttribute.WA_NoMousePropagation)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedWidth(CARD_WIDTH + POPUP_SHADOW_OFFSET)
        self.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(CARD_MARGIN, CARD_MARGIN, CARD_MARGIN + POPUP_SHADOW_OFFSET,
                                  CARD_MARGIN + POPUP_SHADOW_OFFSET)
        layout.setSpacing(CARD_SPACING)

        header = QHBoxLayout()
        header.setSpacing(CARD_SPACING)
        add_layout(layout, header)
        icon_label = QLabel(self)
        icon_label.setPixmap(icon.pixmap(QSize(HEADER_ICON_SIZE, HEADER_ICON_SIZE)))
        icon_label.setEnabled(False)
        title_label = QLabel(label, self)
        title_label.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        header.addWidget(icon_label)
        header.addWidget(title_label, stretch=1)

        self._fields = build_stroke_fields(self, keys)
        for field, _ in self._fields:
            layout.addWidget(field)
        self._size_field: SliderField = self._fields[0][0]

        self._favorites_row: Optional[QWidget] = None
        self._favorite_buttons: list[QToolButton] = []
        if library is not None:
            self._favorites_row = QWidget(self)
            row_layout = QHBoxLayout(self._favorites_row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(CARD_SPACING // 2)
            layout.addWidget(self._favorites_row)
            AppConfig().connect(self, FAV_CONFIG_KEY, lambda _: self._rebuild_favorites())
            Cache().connect(self, brush_config_key, lambda _: self._check_active_favorite())
            self._rebuild_favorites()

        self._color_pair: Optional[ColorPairWidget] = None
        self._swatches: Optional[ColorSwatchGrid] = None
        if keys.color_key is not None:
            color_row = QHBoxLayout()
            color_row.setSpacing(CARD_SPACING)
            add_layout(layout, color_row)
            self._color_pair = _CardColorPair(self)
            self._color_pair.dialog_requested.connect(self.close_card)
            self._swatches = ColorSwatchGrid(self)
            self._swatches.setToolTip(RECENT_COLORS_TOOLTIP)
            self._swatches.color_clicked.connect(self._swatch_clicked)
            swatch_width = CARD_WIDTH - 2 * CARD_MARGIN - self._color_pair.width() - CARD_SPACING
            self._swatch_columns = self._swatches.columns(swatch_width)
            self._swatches.setFixedWidth(swatch_width)
            color_row.addWidget(self._color_pair)
            color_row.addWidget(self._swatches, stretch=1, alignment=Qt.AlignmentFlag.AlignVCenter)
            Cache().connect(self, Cache.RECENT_COLORS, lambda _: self._update_swatches())
            self._update_swatches()

    @property
    def size_field(self) -> SliderField:
        """The Size field."""
        return self._size_field

    @property
    def fields(self) -> list[SliderField]:
        """The Size, Opacity and Hardness fields the card has, in display order."""
        return [field for field, _ in self._fields]

    @property
    def favorite_buttons(self) -> list[QToolButton]:
        """The favorite brush buttons, in display order. Empty for a card with no favorites row."""
        return list(self._favorite_buttons)

    @property
    def favorites_row(self) -> Optional[QWidget]:
        """The favorite brush row, or None for a card without one. It is hidden while there are no favorites."""
        return self._favorites_row

    @property
    def color_pair(self) -> Optional[ColorPairWidget]:
        """The foreground and background colors, or None for a card with no color row."""
        return self._color_pair

    @property
    def swatches(self) -> Optional[ColorSwatchGrid]:
        """The recent color swatches, or None for a card with no color row."""
        return self._swatches

    # -----------------------------------------------------------------------------------------------------------------
    # Opening and closing
    # -----------------------------------------------------------------------------------------------------------------

    def open_at(self, viewer_point: QPoint) -> None:
        """Shows the card with the middle of the Size field under a point in the viewer's coordinates.

        The card stays inside the viewer, so near an edge the pointer is no longer over the field.
        """
        layout = self.layout()
        assert layout is not None
        self.adjustSize()
        bounds = self._viewer.rect().adjusted(EDGE_MARGIN, EDGE_MARGIN, -EDGE_MARGIN, -EDGE_MARGIN)
        self.raise_()
        self.show()
        # A hidden widget's layout isn't placed, so the Size field's position is read once shown:
        layout.activate()
        target = viewer_point - self._size_field.geometry().center()
        self.move(max(bounds.left(), min(target.x(), bounds.right() - self.width() + 1)),
                  max(bounds.top(), min(target.y(), bounds.bottom() - self.height() + 1)))
        self.setFocus(Qt.FocusReason.PopupFocusReason)
        if not self._filter_installed:
            app = QApplication.instance()
            assert app is not None
            app.installEventFilter(self)
            self._filter_installed = True

    def close_card(self, *_args) -> None:
        """Hides the card, if it is shown."""
        if self.isVisible():
            self.hide()

    def hideEvent(self, event) -> None:  # pylint: disable=invalid-name
        """Stops watching application events, and emits `closed`."""
        super().hideEvent(event)
        if self._filter_installed:
            app = QApplication.instance()
            if app is not None:
                app.removeEventFilter(self)
            self._filter_installed = False
        self.closed.emit()

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:  # pylint: disable=invalid-name
        """Closes the card on Escape."""
        assert event is not None
        if event.key() == Qt.Key.Key_Escape:
            self.close_card()
            event.accept()
            return
        super().keyPressEvent(event)

    def _global_rect(self) -> QRect:
        return QRect(self.mapToGlobal(QPoint(0, 0)), self.size())

    def eventFilter(self, watched: Optional[QObject], event: Optional[QEvent]) -> bool:  # pylint: disable=invalid-name
        """Closes the card on a press outside it or the pointer moving away, and consumes a press on the canvas that
           closed it."""
        if event is None or not isinstance(event, QMouseEvent):
            return False
        match event.type():
            case QEvent.Type.MouseButtonPress | QEvent.Type.MouseButtonDblClick:
                if self._global_rect().contains(event.globalPosition().toPoint()):
                    return False
                self.close_card()
                return watched is self._viewer or watched is self._viewer.viewport()
            case QEvent.Type.MouseMove:
                if event.buttons() == Qt.MouseButton.NoButton and not self._global_rect().adjusted(
                        -CLOSE_MARGIN, -CLOSE_MARGIN, CLOSE_MARGIN, CLOSE_MARGIN).contains(
                        event.globalPosition().toPoint()):
                    self.close_card()
        return False

    def paintEvent(self, event: Optional[QPaintEvent]) -> None:  # pylint: disable=invalid-name
        """Draws the card's hard offset shadow, then its rounded body."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        body = self.rect().adjusted(0, 0, -POPUP_SHADOW_OFFSET - 1, -POPUP_SHADOW_OFFSET - 1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.color(QPalette.ColorRole.Shadow))
        painter.drawRoundedRect(body.translated(POPUP_SHADOW_OFFSET, POPUP_SHADOW_OFFSET), CARD_RADIUS, CARD_RADIUS)
        painter.setPen(palette.color(QPalette.ColorRole.WindowText))
        painter.setBrush(palette.color(QPalette.ColorRole.Window))
        painter.drawRoundedRect(body, CARD_RADIUS, CARD_RADIUS)
        painter.end()
        super().paintEvent(event)

    # -----------------------------------------------------------------------------------------------------------------
    # Favorites and colors
    # -----------------------------------------------------------------------------------------------------------------

    def _rebuild_favorites(self) -> None:
        assert self._favorites_row is not None and self._library is not None
        row_layout = self._favorites_row.layout()
        assert row_layout is not None
        while row_layout.count() > 0:
            item = row_layout.takeAt(0)
            widget = None if item is None else item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._favorite_buttons = []
        for path in self._library.favorite_paths()[:MAX_FAVORITE_THUMBNAILS]:
            button = QToolButton(self._favorites_row)
            button.setIcon(self._library.icon(path))
            button.setIconSize(QSize(THUMBNAIL_SIZE // 2, THUMBNAIL_SIZE // 2))
            button.setCheckable(True)
            button.setToolTip(brush_name(path))
            button.setAccessibleName(brush_name(path))
            button.setProperty('brush_path', path)
            button.clicked.connect(lambda _checked=False, chosen=path: self._favorite_clicked(chosen))
            row_layout.addWidget(button)
            self._favorite_buttons.append(button)
        self._favorites_row.setVisible(len(self._favorite_buttons) > 0)
        self._check_active_favorite()

    def _check_active_favorite(self) -> None:
        active = active_brush_path(self._brush_config_key)
        for button in self._favorite_buttons:
            path = button.property('brush_path')
            button.setChecked(active is not None and isinstance(path, str) and _same_file(path, active))

    def _favorite_clicked(self, brush_path: str) -> None:
        choose_brush(self._brush_config_key, brush_path)
        self.close_card()

    def _update_swatches(self) -> None:
        assert self._swatches is not None
        self._swatches.set_colors(color_controller.recent_colors()[:self._swatch_columns])
        self._swatches.setFixedHeight(SWATCH_SIZE)

    @staticmethod
    def _swatch_clicked(color: QColor) -> None:
        color_controller.set_foreground(color)


def _same_file(first: str, second: str) -> bool:
    return os.path.abspath(first) == os.path.abspath(second)


class _CardColorPair(ColorPairWidget):
    """The color pair, announcing that a color dialog is about to open so the card can close first."""

    dialog_requested = Signal()

    def select_foreground(self) -> None:
        """Closes the card, then opens the foreground color dialog."""
        self.dialog_requested.emit()
        super().select_foreground()

    def select_background(self) -> None:
        """Closes the card, then opens the background color dialog."""
        self.dialog_requested.emit()
        super().select_background()
