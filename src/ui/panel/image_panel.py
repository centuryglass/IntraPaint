"""Displays the image panel with rulers, zoom controls and input hints."""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QPalette
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QApplication, QGridLayout

from src.config.application_config import AppConfig
from src.hotkey_filter import HotkeyFilter
from src.image.layers.image_stack import ImageStack
from src.ui.canvas_extras import CanvasExtraCategory
from src.ui.graphics_items.guide_line_item import GuideLineItem
from src.ui.image_viewer import ImageViewer
from src.ui.widget.canvas_bar import CanvasBar
from src.ui.widget.guide_handle_bar import GuideHandleBar, GuideHandleStrip
from src.ui.widget.ruler import Ruler, RulerHighlight
from src.ui.widget.ruler_guides import RulerGuides

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.image_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


MENU_ACTION_HIDE_RULERS = _tr('Hide rulers')
MENU_ACTION_RULER_HIGHLIGHTS = _tr('Highlight generation area and selection')
MENU_ACTION_LOCK_GUIDES = _tr('Lock guides')
MENU_ACTION_CLEAR_GUIDES = _tr('Clear guides')

# Ruler highlight lanes, counting out from the image:
GENERATION_AREA_RULER_LANE = 0
SELECTION_RULER_LANE = 1
RULER_HIGHLIGHT_LANES = 2


class ImagePanel(QWidget):
    """Displays the image panel with rulers, zoom controls and input hints.

    `navigation_window_requested` fires when the bar's navigation window button is clicked, which only shows with
    `include_navigation_button`.

    A panel with rulers owns a `RulerGuides` and draws its guide lines in the viewer. While the rulers are hidden, the
    guide lines stay and their handles move to `GuideHandleStrip`s over the viewer's top and left edges. Any guide
    outside the image is removed when the image size changes.
    """

    navigation_window_requested = Signal()

    def __init__(self, image_stack: ImageStack, hotkey_filter: HotkeyFilter, include_zoom_controls: bool = True,
                 use_keybindings=True,
                 include_rulers: bool = False, include_navigation_button: bool = False) -> None:
        super().__init__()
        self._image_stack = image_stack
        self._showing_image_gen_controls = True
        self._layout = QVBoxLayout(self)

        self._image_viewer = ImageViewer(None, image_stack, hotkey_filter, use_keybindings)
        self._horizontal_ruler: Optional[Ruler] = None
        self._vertical_ruler: Optional[Ruler] = None
        self._ruler_corner: Optional[QWidget] = None
        self._handle_strips: tuple[GuideHandleStrip, ...] = ()
        self._ruler_highlight_action: Optional[QAction] = None
        self._guides: Optional[RulerGuides] = None
        self._guide_items: dict[Qt.Orientation, list[GuideLineItem]] = {Qt.Orientation.Horizontal: [],
                                                                        Qt.Orientation.Vertical: []}
        self._ruler_menu_actions: list[QAction] = []
        if include_rulers:
            self._layout.addWidget(self._build_ruler_grid(), stretch=255)
        else:
            self._layout.addWidget(self._image_viewer, stretch=255)

        self._control_bar: Optional[CanvasBar] = None
        if include_zoom_controls:
            # The Rulers toggle already hides them, so its menu leaves out Hide rulers:
            ruler_actions = self._ruler_menu_actions[1:]
            self._control_bar = CanvasBar(self._image_viewer, include_rulers, include_navigation_button,
                                          ruler_actions, self)
            self._control_bar.navigation_requested.connect(self.navigation_window_requested)
            self._layout.addWidget(self._control_bar)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _build_ruler_grid(self) -> QWidget:
        """Returns a widget holding the image viewer, with rulers above it and to its left."""
        grid_widget = QWidget(self)
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        self._guides = RulerGuides()
        self._horizontal_ruler = Ruler(self._image_viewer, Qt.Orientation.Horizontal, grid_widget, self._guides)
        self._vertical_ruler = Ruler(self._image_viewer, Qt.Orientation.Vertical, grid_widget, self._guides)
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
        self._ruler_highlight_action = highlight_action
        highlight_action.setCheckable(True)
        highlight_action.setChecked(AppConfig().get(AppConfig.SHOW_RULER_HIGHLIGHTS))

        def _set_highlights_shown(shown: bool) -> None:
            AppConfig().set(AppConfig.SHOW_RULER_HIGHLIGHTS, shown)
        highlight_action.toggled.connect(_set_highlights_shown)
        lock_action = QAction(MENU_ACTION_LOCK_GUIDES, grid_widget)
        lock_action.setCheckable(True)
        guides = self._guides
        lock_action.toggled.connect(lambda locked: setattr(guides, 'locked', locked))
        guides.guides_changed.connect(lambda: lock_action.setChecked(guides.locked))
        clear_action = QAction(MENU_ACTION_CLEAR_GUIDES, grid_widget)
        clear_action.triggered.connect(guides.clear)
        self._ruler_menu_actions = [hide_action, highlight_action, lock_action, clear_action]
        for ruler in (self._horizontal_ruler, self._vertical_ruler):
            ruler.menu_actions = self._ruler_menu_actions
        self._ruler_corner.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self._ruler_corner.addActions(self._ruler_menu_actions)
        self._handle_strips = (
            GuideHandleStrip(self._image_viewer, Qt.Orientation.Horizontal, guides, grid_widget,
                             self._image_viewer.canvas_extras),
            GuideHandleStrip(self._image_viewer, Qt.Orientation.Vertical, guides, grid_widget,
                             self._image_viewer.canvas_extras))
        for strip in self._handle_strips:
            # Hide rulers and the highlight toggle don't apply while the rulers are hidden:
            strip.menu_actions = [lock_action, clear_action]
            strip.thickness = self._horizontal_ruler.thickness
            self._horizontal_ruler.thickness_changed.connect(lambda thickness, s=strip: setattr(s, 'thickness',
                                                                                                 thickness))
        guides.guides_changed.connect(self._update_guide_items)
        for handle_bar in self._guide_bars:
            handle_bar.guide_drag_changed.connect(self._update_guide_items)
        self._image_stack.size_changed.connect(guides.prune)
        self._image_stack.size_changed.connect(self._update_guide_items)

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
        for strip in self._handle_strips:
            strip.shown = not visible

    @property
    def guide_handle_strips(self) -> tuple[GuideHandleStrip, ...]:
        """Returns the (horizontal, vertical) strips that hold guide handles while the rulers are hidden, or an empty
        tuple if this panel has no rulers."""
        return self._handle_strips

    @property
    def _guide_bars(self) -> list[GuideHandleBar]:
        """Returns every widget that takes guide gestures."""
        rulers: list[GuideHandleBar] = [ruler for ruler in self.rulers if ruler is not None]
        return rulers + list(self._handle_strips)

    @property
    def guides(self) -> Optional[RulerGuides]:
        """Returns the guide model, or None if this panel has no rulers."""
        return self._guides

    def _displayed_guides(self) -> dict[Qt.Orientation, list[int]]:
        """Returns the coordinates of the guide lines to draw, with any guide gesture in progress applied: a moved
        guide at its new coordinate, a guide pending deletion left out, and a guide being created included."""
        assert self._guides is not None
        displayed = {orientation: self._guides.positions(orientation) for orientation in self._guide_items}
        for handle_bar in self._guide_bars:
            drag = handle_bar.guide_drag
            if drag is None:
                continue
            displayed[drag.orientation] = drag.applied_to(displayed[drag.orientation])
        return displayed

    def _update_guide_items(self, *_) -> None:
        """Makes the guide line items match the model and any guide gesture in progress."""
        if self._guides is None:
            return
        size = self._image_stack.size
        for orientation, coordinates in self._displayed_guides().items():
            items = self._guide_items[orientation]
            while len(items) > len(coordinates):
                item = items.pop()
                scene = item.scene()
                if scene is not None:
                    scene.removeItem(item)
            length = size.width() if orientation == Qt.Orientation.Horizontal else size.height()
            for index, coordinate in enumerate(coordinates):
                if index == len(items):
                    item = GuideLineItem(orientation)
                    self._image_viewer.canvas_extras.register(item, CanvasExtraCategory.GUIDES)
                    items.append(item)
                items[index].set_guide(coordinate, length)

    @property
    def guide_line_items(self) -> list[GuideLineItem]:
        """Returns the guide lines currently in the viewer's scene."""
        return [item for items in self._guide_items.values() for item in items]

    def _update_ruler_highlights(self, *_) -> None:
        """Shades the generation area and the selection's bounds on the rulers, if enabled."""
        if self._horizontal_ruler is None or self._vertical_ruler is None:
            return
        horizontal: list[RulerHighlight] = []
        vertical: list[RulerHighlight] = []
        show_highlights = AppConfig().get(AppConfig.SHOW_RULER_HIGHLIGHTS)
        for ruler in (self._horizontal_ruler, self._vertical_ruler):
            ruler.highlight_lanes = RULER_HIGHLIGHT_LANES if show_highlights else 0
        if show_highlights:
            if self._showing_image_gen_controls:
                area = self._image_stack.generation_area
                color = AppConfig().get_color(AppConfig.RULER_GENERATION_AREA_COLOR,
                                              self._horizontal_ruler.palette().color(QPalette.ColorRole.Highlight))
                horizontal.append(RulerHighlight(area.x(), area.x() + area.width(), color, GENERATION_AREA_RULER_LANE))
                vertical.append(RulerHighlight(area.y(), area.y() + area.height(), color, GENERATION_AREA_RULER_LANE))
            selection_layer = self._image_stack.selection_layer
            outline = selection_layer.outline
            if selection_layer.visible and len(outline) > 0:
                bounds = outline[0].boundingRect()
                for polygon in outline[1:]:
                    bounds = bounds.united(polygon.boundingRect())
                color = AppConfig().get_color(AppConfig.SELECTION_COLOR, Qt.GlobalColor.red)
                horizontal.append(RulerHighlight(bounds.left(), bounds.right(), color, SELECTION_RULER_LANE))
                vertical.append(RulerHighlight(bounds.top(), bounds.bottom(), color, SELECTION_RULER_LANE))
        self._horizontal_ruler.set_highlights(horizontal)
        self._vertical_ruler.set_highlights(vertical)

    def set_image_generation_controls_visible(self, visible: bool) -> None:
        """Sets whether controls related to image generation will be shown."""
        if visible == self._showing_image_gen_controls:
            return
        self._showing_image_gen_controls = visible
        self._image_viewer.set_generation_area_visible(visible)
        self._update_ruler_highlights()

    @property
    def vertical_layout(self) -> QVBoxLayout:
        """Access the panel's main vertical layout."""
        return self._layout

    def setEnabled(self, enabled: bool) -> None:
        """Override setEnabled to ensure it does not apply to tab bars."""
        self._image_viewer.setEnabled(enabled)
        if self._control_bar is not None:
            self._control_bar.setEnabled(enabled)

    @property
    def image_viewer(self) -> ImageViewer:
        """Returns the wrapped ImageViewer widget."""
        return self._image_viewer

    @property
    def control_bar(self) -> Optional[CanvasBar]:
        """Returns the bar under the viewer, or None if the panel has no zoom controls."""
        return self._control_bar

    def set_control_hint(self, hint_text: str) -> None:
        """Shows the active tool's control hints in the bar below the image viewer."""
        if self._control_bar is not None:
            self._control_bar.set_hint_text(hint_text)
