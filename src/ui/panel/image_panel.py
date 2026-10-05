"""Displays the image panel with zoom controls and input hints."""
from typing import Optional

from PySide6.QtCore import Qt, SignalInstance
from PySide6.QtGui import QResizeEvent, QAction, QPalette
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QSlider, QPushButton, \
    QSizePolicy, QApplication, QGridLayout

from src.config.application_config import AppConfig
from src.image.layers.image_stack import ImageStack
from src.ui.image_viewer import ImageViewer
from src.ui.layout.draggable_divider import DraggableDivider
from src.ui.layout.draggable_tabs.tab_box import TabBox
from src.ui.widget.image_graphics_view import MIN_IMAGE_ZOOM, MAX_IMAGE_ZOOM
from src.ui.widget.ruler import Ruler, RulerHighlight

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.image_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


SCALE_SLIDER_LABEL = _tr('Scale:')
SCALE_RESET_BUTTON_LABEL = _tr('Reset View')
SCALE_RESET_BUTTON_TOOLTIP = _tr('Restore default image zoom and offset')
SCALE_ZOOM_BUTTON_LABEL = _tr('Zoom in')
SCALE_ZOOM_BUTTON_TOOLTIP = _tr('Zoom in on the area selected for image generation')

MENU_ACTION_SHOW_HINTS = _tr('Show tool control hints')
MENU_ACTION_HIDE_HINTS = _tr('Hide tool control hints')
MENU_ACTION_HIDE_RULERS = _tr('Hide rulers')
MENU_ACTION_RULER_HIGHLIGHTS = _tr('Highlight generation area and selection')

MIN_WIDTH_SHOWING_SCALE_SLIDER = 600
MIN_WIDTH_SHOWING_HINT_TEXT = 900
MAIN_CONTENT_STRETCH = 100


class ImagePanel(QWidget):
    """Displays the image panel with zoom controls and input hints."""

    def __init__(self, image_stack: ImageStack, include_tab_boxes: bool = False, include_zoom_controls: bool = True,
                 use_keybindings=True, include_rulers: bool = False) -> None:
        super().__init__()
        self._image_stack = image_stack
        self._showing_image_gen_controls = True
        if include_tab_boxes:
            self._outer_layout = QHBoxLayout(self)
            self.setContentsMargins(0, 0, 0, 0)
            self._outer_layout.setContentsMargins(0, 0, 0, 0)
            self._outer_layout.setSpacing(2)
            self._left_tab_box: Optional[TabBox] = TabBox(Qt.Orientation.Vertical, True, parent=self)
            self._outer_layout.addWidget(self._left_tab_box, stretch=1)
            self._left_divider = DraggableDivider()
            self._outer_layout.addWidget(self._left_divider)
            self._inner_content = QWidget(self)
            self._layout = QVBoxLayout(self._inner_content)
            self._outer_layout.addWidget(self._inner_content, stretch=MAIN_CONTENT_STRETCH)
            self._right_divider = DraggableDivider()
            self._outer_layout.addWidget(self._right_divider)
            self._right_tab_box: Optional[TabBox] = TabBox(Qt.Orientation.Vertical, False, parent=self)
            self._outer_layout.addWidget(self._right_tab_box, stretch=1)

            def _show_or_hide_left_divider(_=None) -> None:
                assert self._left_tab_box is not None
                self._left_divider.setVisible(self._left_tab_box.count > 0 and self._left_tab_box.is_open)
            for signal in (self._left_tab_box.box_toggled, self._left_tab_box.tab_added,
                           self._left_tab_box.tab_removed):
                signal.connect(_show_or_hide_left_divider)
            _show_or_hide_left_divider()

            def _show_or_hide_right_divider(_=None) -> None:
                assert self._right_tab_box is not None
                self._right_divider.setVisible(self._right_tab_box.count > 0 and self._right_tab_box.is_open)
            for signal in (self._right_tab_box.box_toggled, self._right_tab_box.tab_added,
                           self._right_tab_box.tab_removed):
                signal.connect(_show_or_hide_right_divider)
            _show_or_hide_right_divider()

        else:
            self._layout = QVBoxLayout(self)
            self._left_tab_box = None
            self._right_tab_box = None

        self._image_viewer = ImageViewer(None, image_stack, use_keybindings)
        self._horizontal_ruler: Optional[Ruler] = None
        self._vertical_ruler: Optional[Ruler] = None
        self._ruler_corner: Optional[QWidget] = None
        if include_rulers:
            self._layout.addWidget(self._build_ruler_grid(), stretch=255)
        else:
            self._layout.addWidget(self._image_viewer, stretch=255)
        self._control_bar = QWidget(self)
        self._control_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)

        # Show/hide control hints:
        def _show_hints() -> None:
            AppConfig().set(AppConfig.SHOW_TOOL_CONTROL_HINTS, True)
        self._show_hint_action = QAction()
        self._show_hint_action.setText(MENU_ACTION_SHOW_HINTS)
        self._show_hint_action.triggered.connect(_show_hints)

        def _hide_hints() -> None:
            AppConfig().set(AppConfig.SHOW_TOOL_CONTROL_HINTS, False)
        self._hide_hint_action = QAction()
        self._hide_hint_action.setText(MENU_ACTION_HIDE_HINTS)
        self._hide_hint_action.triggered.connect(_hide_hints)

        AppConfig().connect(self, AppConfig.SHOW_TOOL_CONTROL_HINTS, self._show_control_hint_config_slot)
        self._control_bar.addAction(self._hide_hint_action if AppConfig().get(AppConfig.SHOW_TOOL_CONTROL_HINTS)
                                    else self._show_hint_action)
        self._layout.addWidget(self._control_bar, stretch=1)

        if include_zoom_controls:
            self._control_layout: Optional[QHBoxLayout] = QHBoxLayout(self._control_bar)
            self._control_hint_label: Optional[QLabel] = QLabel('')
            assert self._control_layout is not None
            assert self._control_hint_label is not None
            self._control_layout.addWidget(self._control_hint_label)
            self._control_layout.addSpacing(25)
            self._scale_reset_button: Optional[QPushButton] = QPushButton()

            def toggle_scale():
                """Toggle between default zoom and zooming in on the image generation area."""
                assert self._scale_reset_button is not None
                if self._image_viewer.is_at_default_view and not self._image_viewer.follow_generation_area:
                    self._image_viewer.follow_generation_area = True
                    self._scale_reset_button.setVisible(True)
                    self._scale_reset_button.setText(SCALE_RESET_BUTTON_LABEL)
                    self._scale_reset_button.setToolTip(SCALE_RESET_BUTTON_TOOLTIP)
                else:
                    self._scale_reset_button.setVisible(self._showing_image_gen_controls)
                    self._image_viewer.follow_generation_area = False
                    self._image_viewer.reset_scale()
                    self._scale_reset_button.setText(SCALE_ZOOM_BUTTON_LABEL)
                    self._scale_reset_button.setToolTip(SCALE_ZOOM_BUTTON_TOOLTIP)

            self._scale_reset_button.setText(SCALE_ZOOM_BUTTON_LABEL)
            self._scale_reset_button.setToolTip(SCALE_ZOOM_BUTTON_TOOLTIP)
            assert isinstance(self._scale_reset_button.clicked, SignalInstance)
            self._scale_reset_button.clicked.connect(toggle_scale)
            # Zoom slider:
            self._control_layout.addWidget(QLabel(SCALE_SLIDER_LABEL))
            image_scale_slider: Optional[QSlider] = QSlider(Qt.Orientation.Horizontal)
            assert image_scale_slider is not None
            self._image_scale_slider = image_scale_slider
            self._control_layout.addWidget(image_scale_slider)
            image_scale_slider.setRange(round(MIN_IMAGE_ZOOM * 100), round(MAX_IMAGE_ZOOM * 100))
            image_scale_slider.setSingleStep(10)
            image_scale_slider.setValue(int(self._image_viewer.scene_scale * 100))
            image_scale_box = QDoubleSpinBox()
            self._control_layout.addWidget(image_scale_box)
            image_scale_box.setRange(MIN_IMAGE_ZOOM, MAX_IMAGE_ZOOM)
            image_scale_box.setSingleStep(0.1)
            image_scale_box.setValue(self._image_viewer.scene_scale)
            self._control_layout.addWidget(self._scale_reset_button)

            scale_signals = [
                self._image_viewer.scale_changed,
                image_scale_slider.valueChanged,
                image_scale_box.valueChanged
            ]

            def on_scale_change(new_scale: float | int) -> None:
                """Synchronize slider, spin box, panel scale, and zoom button text:"""
                assert self._scale_reset_button is not None
                if isinstance(new_scale, int):
                    float_scale = new_scale / 100
                    int_scale = new_scale
                else:
                    float_scale = new_scale
                    int_scale = int(float_scale * 100)
                for scale_signal in scale_signals:
                    scale_signal.disconnect(on_scale_change)
                if image_scale_box.value() != float_scale:
                    image_scale_box.setValue(float_scale)
                if image_scale_slider.value() != int_scale:
                    image_scale_slider.setValue(int_scale)
                if self._image_viewer.scene_scale != float_scale:
                    self._image_viewer.scene_scale = float_scale
                for scale_signal in scale_signals:
                    scale_signal.connect(on_scale_change)
                if self._image_viewer.is_at_default_view and not self._image_viewer.follow_generation_area:
                    self._scale_reset_button.setVisible(self._showing_image_gen_controls)
                    self._scale_reset_button.setText(SCALE_ZOOM_BUTTON_LABEL)
                    self._scale_reset_button.setToolTip(SCALE_ZOOM_BUTTON_TOOLTIP)
                else:
                    self._scale_reset_button.setVisible(True)
                    self._scale_reset_button.setText(SCALE_RESET_BUTTON_LABEL)
                    self._scale_reset_button.setToolTip(SCALE_RESET_BUTTON_TOOLTIP)

            for signal in scale_signals:
                signal.connect(on_scale_change)
        else:
            self._control_layout = None
            self._control_hint_label = None
            self._control_bar = None
            self._image_scale_slider = None
            self._scale_reset_button = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _build_ruler_grid(self) -> QWidget:
        """Returns a widget holding the image viewer, with rulers above it and to its left."""
        grid_widget = QWidget(self)
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        self._horizontal_ruler = Ruler(self._image_viewer, Qt.Orientation.Horizontal, grid_widget)
        self._vertical_ruler = Ruler(self._image_viewer, Qt.Orientation.Vertical, grid_widget)
        self._ruler_corner = QWidget(grid_widget)
        self._ruler_corner.setFixedSize(self._vertical_ruler.thickness, self._horizontal_ruler.thickness)

        def _resize_corner(thickness: int) -> None:
            assert self._ruler_corner is not None
            self._ruler_corner.setFixedSize(thickness, thickness)
        self._horizontal_ruler.thickness_changed.connect(_resize_corner)
        self._ruler_corner.setBackgroundRole(QPalette.ColorRole.Button)
        self._ruler_corner.setAutoFillBackground(True)
        grid.addWidget(self._ruler_corner, 0, 0)
        grid.addWidget(self._horizontal_ruler, 0, 1)
        grid.addWidget(self._vertical_ruler, 1, 0)
        grid.addWidget(self._image_viewer, 1, 1)

        def _hide_rulers() -> None:
            AppConfig().set(AppConfig.SHOW_RULERS, False)
        hide_action = QAction(MENU_ACTION_HIDE_RULERS, grid_widget)
        hide_action.triggered.connect(_hide_rulers)
        highlight_action = QAction(MENU_ACTION_RULER_HIGHLIGHTS, grid_widget)
        highlight_action.setCheckable(True)
        highlight_action.setChecked(AppConfig().get(AppConfig.SHOW_RULER_HIGHLIGHTS))

        def _set_highlights_shown(shown: bool) -> None:
            AppConfig().set(AppConfig.SHOW_RULER_HIGHLIGHTS, shown)
        highlight_action.toggled.connect(_set_highlights_shown)
        for ruler_widget in (self._horizontal_ruler, self._vertical_ruler, self._ruler_corner):
            ruler_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
            ruler_widget.addActions([hide_action, highlight_action])

        def _update_highlight_action(shown: bool) -> None:
            highlight_action.setChecked(shown)
            self._update_ruler_highlights()
        AppConfig().connect(self, AppConfig.SHOW_RULER_HIGHLIGHTS, _update_highlight_action)
        AppConfig().connect(self, AppConfig.SHOW_RULERS, self._update_ruler_visibility)
        AppConfig().connect(self, AppConfig.SELECTION_COLOR, self._update_ruler_highlights)
        AppConfig().connect(self, AppConfig.RULER_GENERATION_AREA_COLOR, self._update_ruler_highlights)
        self._image_stack.generation_area_bounds_changed.connect(self._update_ruler_highlights)
        selection_layer = self._image_stack.selection_layer
        selection_layer.content_changed.connect(self._update_ruler_highlights)
        selection_layer.visibility_changed.connect(self._update_ruler_highlights)
        self._update_ruler_visibility(AppConfig().get(AppConfig.SHOW_RULERS))
        self._update_ruler_highlights()
        return grid_widget

    @property
    def rulers(self) -> tuple[Optional[Ruler], Optional[Ruler]]:
        """Returns the (horizontal, vertical) rulers, or Nones if this panel has no rulers."""
        return self._horizontal_ruler, self._vertical_ruler

    def _update_ruler_visibility(self, visible: bool) -> None:
        for ruler_widget in (self._horizontal_ruler, self._vertical_ruler, self._ruler_corner):
            if ruler_widget is not None:
                ruler_widget.setVisible(visible)

    def _update_ruler_highlights(self, *_) -> None:
        """Shades the generation area and the selection's bounds on the rulers, if enabled."""
        if self._horizontal_ruler is None or self._vertical_ruler is None:
            return
        horizontal: list[RulerHighlight] = []
        vertical: list[RulerHighlight] = []
        if AppConfig().get(AppConfig.SHOW_RULER_HIGHLIGHTS):
            if self._showing_image_gen_controls:
                area = self._image_stack.generation_area
                color = AppConfig().get_color(AppConfig.RULER_GENERATION_AREA_COLOR, Qt.GlobalColor.blue)
                horizontal.append(RulerHighlight(area.x(), area.x() + area.width(), color))
                vertical.append(RulerHighlight(area.y(), area.y() + area.height(), color))
            selection_layer = self._image_stack.selection_layer
            outline = selection_layer.outline
            if selection_layer.visible and len(outline) > 0:
                bounds = outline[0].boundingRect()
                for polygon in outline[1:]:
                    bounds = bounds.united(polygon.boundingRect())
                color = AppConfig().get_color(AppConfig.SELECTION_COLOR, Qt.GlobalColor.red)
                horizontal.append(RulerHighlight(bounds.left(), bounds.right(), color))
                vertical.append(RulerHighlight(bounds.top(), bounds.bottom(), color))
        self._horizontal_ruler.set_highlights(horizontal)
        self._vertical_ruler.set_highlights(vertical)

    def set_image_generation_controls_visible(self, visible: bool) -> None:
        """Sets whether controls related to image generation will be shown."""
        if visible == self._showing_image_gen_controls:
            return
        self._showing_image_gen_controls = visible
        if self._scale_reset_button is not None:
            self._scale_reset_button.setVisible(visible or not self._image_viewer.is_at_default_view)
        self._image_viewer.set_generation_area_visible(visible)
        self._update_ruler_highlights()

    @property
    def vertical_layout(self) -> QVBoxLayout:
        """Access the panel's main vertical layout."""
        return self._layout

    def setEnabled(self, enabled: bool) -> None:
        """Override setEnabled to ensure it does not apply to tab bars."""
        self._image_viewer.setEnabled(enabled)
        self._control_bar.setEnabled(enabled)

    @property
    def image_viewer(self) -> ImageViewer:
        """Returns the wrapped ImageViewer widget."""
        return self._image_viewer

    def set_control_hint(self, hint_text: str) -> None:
        """Add a message below the image viewer hinting at controls."""
        if isinstance(self._control_hint_label, QLabel):
            self._control_hint_label.setText(hint_text)

    def resizeEvent(self, event: Optional[QResizeEvent]) -> None:
        """Hide non-essential UI elements if there's not enough space."""
        self._update_widget_visibility()

    @property
    def left_tab_box(self) -> Optional[TabBox]:
        """Returns the left tab box, if used."""
        return self._left_tab_box

    @property
    def right_tab_box(self) -> Optional[TabBox]:
        """Returns the right tab box, if used."""
        return self._right_tab_box

    def _show_control_hint_config_slot(self, show_hints: bool):
        if self._control_bar is not None:
            if show_hints:
                self._control_bar.removeAction(self._show_hint_action)
                self._control_bar.addAction(self._hide_hint_action)
            else:
                self._control_bar.removeAction(self._hide_hint_action)
                self._control_bar.addAction(self._show_hint_action)
            self._update_widget_visibility()

    def _update_widget_visibility(self) -> None:
        if self._control_hint_label is not None:
            self._control_hint_label.setVisible(AppConfig().get(AppConfig.SHOW_TOOL_CONTROL_HINTS)
                                                and self.width() > MIN_WIDTH_SHOWING_HINT_TEXT)
        if self._image_scale_slider is not None:
            self._image_scale_slider.setVisible(self.width() > MIN_WIDTH_SHOWING_SCALE_SLIDER)
