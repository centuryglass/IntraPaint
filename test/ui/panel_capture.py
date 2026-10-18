"""Captures IntraPaint's panels at extreme sizes and across a grid of dock sizes, and lists their layout problems.

`panel_layout_test.py` compares these captures with committed snapshots, `panel_sweep_test.py` checks them across
the sweep grid, and `scripts/capture_ui.py` saves them as images and sweep sheets for review. All three go through the
same functions, so a screenshot shows what a test checked.

- Panel captures resize each panel inside a plain host widget, which lets them go below the panel's minimum size the
  way a squeezed dock or divider can. `find_layout_problems` lists overlapping, clipped and squeezed child widgets,
  and `find_arrangement_problems` lists stretched fields, empty bands and cramped panels. Their results depend on
  font metrics, which the bundled theme font fixes.
- A panel that takes a dock orientation is captured with a side and a strip preference, as a left or right dock and a
  top or bottom dock would tell it. `PanelHost.capture` passes it on.
- `SWEEP_WIDTHS` and `SWEEP_HEIGHTS` are a grid of dock sizes between the extremes, for sweep sheets.
"""
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Callable, Optional, TYPE_CHECKING
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt
from PySide6 import QtGui
from PySide6.QtGui import QImage, QTextDocumentFragment
from PySide6.QtWidgets import (QAbstractButton, QAbstractScrollArea, QAbstractSpinBox, QApplication, QComboBox,
                               QDockWidget, QFrame, QGroupBox, QLabel, QLayout, QMainWindow, QSizePolicy, QTabBar,
                               QWidget)

from src.ui.input_fields.number_field import NumberField
from src.ui.input_fields.segmented_control import SegmentedControl
from src.ui.layout.dock_panel import DockPanel
from src.ui.layout.panel_fit import STRIP_SECTION_MAX_WIDTH, FitContent, Orientation

if TYPE_CHECKING:
    from src.controller.app_controller import AppController

SIZE_CASES = ('preferred', 'minimum', 'wide', 'tall', 'narrow', 'short')
FALLBACK_SIZE = QSize(400, 300)
WIDE_MIN_WIDTH = 1600
TALL_MIN_HEIGHT = 1200
MAX_SETTLE_PASSES = 8


def panel_size(case: str, widget: QWidget) -> QSize:
    """Returns the size a panel is captured at for one of SIZE_CASES.

    - preferred, minimum: the panel's size hint and minimum size hint.
    - wide, tall: the preferred size stretched to at least WIDE_MIN_WIDTH wide or TALL_MIN_HEIGHT tall.
    - narrow, short: the preferred size with its width or height cut to half the minimum, below what the panel asks
      for.
    """
    preferred = widget.sizeHint()
    if not preferred.isValid() or preferred.isEmpty():
        preferred = FALLBACK_SIZE
    minimum = widget.minimumSizeHint().expandedTo(QSize(1, 1))
    if case == 'preferred':
        return preferred
    if case == 'minimum':
        return minimum.expandedTo(QSize(1, 1))
    if case == 'wide':
        return QSize(max(preferred.width() * 3, WIDE_MIN_WIDTH), preferred.height())
    if case == 'tall':
        return QSize(preferred.width(), max(preferred.height() * 3, TALL_MIN_HEIGHT))
    if case == 'narrow':
        return QSize(max(minimum.width() // 2, 1), preferred.height())
    if case == 'short':
        return QSize(preferred.width(), max(minimum.height() // 2, 1))
    raise ValueError(f'Unknown size case {case}, expected one of {SIZE_CASES}')


def _settle_layouts(root: QWidget) -> None:
    """Activates every layout under root, parents first, and delivers posted layout requests, so geometry is final.

    Qt applies some size hint changes, such as a dock panel switching size class, only when a posted
    `QEvent.LayoutRequest` runs, which the running app's event loop does. Each pass activates the layouts and delivers
    the requests it posted, until a pass changes no geometry (at most MAX_SETTLE_PASSES).
    """
    for _ in range(MAX_SETTLE_PASSES):
        before = _geometries(root)
        for widget in [root, *root.findChildren(QWidget)]:
            layout = widget.layout()
            if layout is not None and widget.isVisibleTo(root):
                layout.activate()
        QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
        if _geometries(root) == before:
            return


def _geometries(root: QWidget) -> list[QRect]:
    return [widget.geometry() for widget in root.findChildren(QWidget)]


def host_orientations(panel: QWidget) -> tuple[Optional[Orientation], ...]:
    """Returns the orientations to capture a panel with: side and strip for a panel `tell_orientation` can tell, or only
    None for any other."""
    if isinstance(panel, (DockPanel, FitContent)) or hasattr(panel, 'set_orientation'):
        return Orientation.SIDE, Orientation.STRIP
    return (None,)


def tell_orientation(panel: QWidget, orientation: Orientation, size: QSize) -> None:
    """Tells a panel its orientation the way its host does, with the size it fills.

    - A `DockPanel` gets `set_host_facts`, as from `PanelDock`.
    - `FitContent` gets `set_fit_space`, as from the Tools panel.
    - Other content gets `set_orientation` with the matching `Qt.Orientation`.
    """
    if isinstance(panel, DockPanel):
        panel.set_host_facts(orientation, size)
    elif isinstance(panel, FitContent):
        panel.set_fit_space(orientation, size)
    elif hasattr(panel, 'set_orientation'):
        panel.set_orientation(Qt.Orientation.Vertical if orientation == Orientation.SIDE else Qt.Orientation.Horizontal)


class PanelHost(QWidget):
    """A plain parent that sets a panel's geometry directly, so the panel can be sized below its minimum.

    Fit planning keeps a placement until a better one fits with `HYSTERESIS` to spare, so a capture within that margin
    of a planning boundary depends on the size captured before it.
    """

    def __init__(self, panel: QWidget) -> None:
        super().__init__()
        self.panel = panel
        self._old_parent = panel.parentWidget()
        self._panel_was_visible = panel.isVisible()
        panel.setParent(self)
        panel.show()

    def capture(self, size: QSize, orientation: Optional[Orientation] = None) -> QImage:
        """Resizes the panel, tells it the orientation if one is given, settles its layouts and returns a render of
        it."""
        self.resize(size)
        if orientation is not None:
            tell_orientation(self.panel, orientation, size)
        self.panel.setGeometry(QRect(QPoint(), size))
        self.show()
        _settle_layouts(self.panel)
        return self.panel.grab().toImage()

    def release(self) -> None:
        """Hides the host and returns the panel to its original parent, or makes it a hidden window if it had none.

        The panel keeps the last orientation it was told.
        """
        self.hide()
        self.panel.setParent(self._old_parent)
        self.panel.setVisible(self._panel_was_visible and self._old_parent is not None)


def _widget_label(widget: QWidget) -> str:
    """Returns a short identifier for a widget: its object name, or its class name and any short text it shows."""
    if widget.objectName() != '' and not widget.objectName().startswith('qt_'):
        return widget.objectName()
    label = type(widget).__name__
    text = ''
    if isinstance(widget, (QLabel, QAbstractButton)):
        text = widget.text()
    elif isinstance(widget, QGroupBox):
        text = widget.title()
    if QtGui.Qt.mightBeRichText(text):
        text = QTextDocumentFragment.fromHtml(text).toPlainText()
    text = text.replace('&', '').replace('\n', ' ').strip()
    if text != '':
        label += f" '{text[:24]}'"
    return label


def widget_path(widget: QWidget, root: QWidget) -> str:
    """Returns a widget's path from root, naming each step with _widget_label and a sibling index where labels repeat."""
    steps = []
    while widget is not root and widget is not None:
        parent = widget.parentWidget()
        label = _widget_label(widget)
        if parent is not None:
            same_label = [child for child in parent.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
                          if _widget_label(child) == label]
            if len(same_label) > 1:
                label += f'[{same_label.index(widget)}]'
        steps.append(label)
        widget = parent
    return '/'.join(reversed(steps))


def _is_scroll_viewport(widget: QWidget) -> bool:
    parent = widget.parentWidget()
    return isinstance(parent, QAbstractScrollArea) and parent.viewport() is widget


def _is_qt_internal(widget: QWidget, root: QWidget) -> bool:
    """Returns whether a widget is, or is inside, a part Qt builds into a composite widget, like a spin box's line edit.

    A scroll area's viewport is the exception: it holds IntraPaint's own content.
    """
    while widget is not None and widget is not root:
        if widget.objectName().startswith('qt_') and not _is_scroll_viewport(widget):
            return True
        widget = widget.parentWidget()
    return False


def _is_parked(widget: QWidget, root: QWidget) -> bool:
    """Returns whether a widget is, or is inside, a dock or tab bar that a `QMainWindow` keeps outside itself.

    Qt moves the docks behind a tab, and spare dock tab bars, out of the window instead of hiding them.
    """
    while widget is not None and widget is not root:
        parent = widget.parentWidget()
        if isinstance(parent, QMainWindow) and isinstance(widget, (QDockWidget, QTabBar)) \
                and not widget.geometry().intersects(parent.rect()):
            return True
        widget = parent
    return False


def _rect_in(widget: QWidget, root: QWidget) -> QRect:
    return QRect(widget.mapTo(root, QPoint()), widget.size())


def _visible_rect(widget: QWidget, root: QWidget) -> QRect:
    """Returns the part of a widget its ancestors up to root don't clip, or up to a scroll area viewport if nearer.

    Content under a scroll area viewport is meant to extend past it, so clipping is only measured below the viewport.
    """
    visible = _rect_in(widget, root)
    ancestor = widget.parentWidget()
    while ancestor is not None and not _is_scroll_viewport(ancestor):
        visible = visible.intersected(_rect_in(ancestor, root))
        if ancestor is root:
            break
        ancestor = ancestor.parentWidget()
    return visible


def _checked_widgets(root: QWidget) -> list[QWidget]:
    """Returns the visible widgets under root that the layout checks look at."""
    return [widget for widget in root.findChildren(QWidget)
            if widget.isVisibleTo(root) and not widget.isWindow() and not _is_qt_internal(widget, root)
            and not _is_parked(widget, root)]


def layout_widget_rects(root: QWidget) -> list[QRect]:
    """Returns the rectangle in root of every visible widget under it that `find_layout_problems` checks."""
    return [_rect_in(widget, root) for widget in _checked_widgets(root)]


def _layout_widgets(layout: QLayout) -> list[QWidget]:
    """Returns the widgets a layout and its nested layouts manage, in layout order.

    Finds them with `QLayout.indexOf`, never `itemAt`. A Python wrapper from `itemAt` outlives its item when Qt deletes
    the item along with its widget, and shiboken frees the item again when the layout's wrapper goes, which corrupts
    the heap.
    """
    parent = layout.parentWidget()
    if parent is None:
        return []
    children = parent.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)

    def _in_order(current: QLayout) -> list[QWidget]:
        entries: list[tuple[int, list[QWidget]]] = []
        for child in children:
            index = current.indexOf(child)
            if index >= 0:
                entries.append((index, [child]))
        for nested in current.findChildren(QLayout, options=Qt.FindChildOption.FindDirectChildrenOnly):
            index = current.indexOf(nested)
            if index >= 0:
                entries.append((index, _in_order(nested)))
        return [widget for _, widgets in sorted(entries, key=lambda entry: entry[0]) for widget in widgets]
    return _in_order(layout)


def _ignores_size(widget: QWidget, orientation: Qt.Orientation) -> bool:
    policy = widget.sizePolicy()
    value = policy.horizontalPolicy() if orientation == Qt.Orientation.Horizontal else policy.verticalPolicy()
    return value == QSizePolicy.Policy.Ignored


def find_layout_problems(root: QWidget) -> list[str]:
    """Lists visible widgets under root that overlap, are clipped, or are smaller than their minimum size hint.

    - overlap: two widgets in the same layout whose rectangles intersect.
    - clipped: a widget partly cut off by an ancestor, measured as described in _visible_rect.
    - squeezed: a widget narrower or shorter than its minimum size hint, unless its size policy ignores hints in that
      direction.

    Parts Qt builds into composite widgets are left out, as _is_qt_internal describes, and so are widgets a main
    window parks outside itself, as _is_parked describes.
    """
    problems = []
    widgets = _checked_widgets(root)
    for widget in [root, *widgets]:
        layout = widget.layout()
        if layout is None:
            continue
        managed = [child for child in _layout_widgets(layout)
                   if child.isVisibleTo(root) and not _is_qt_internal(child, root) and not _is_parked(child, root)]
        for i, first in enumerate(managed):
            for second in managed[i + 1:]:
                overlap = first.geometry().intersected(second.geometry())
                if not overlap.isEmpty():
                    problems.append(f'overlap: {widget_path(first, root)} and {widget_path(second, root)} '
                                    f'share {overlap.width()}x{overlap.height()}')
    for widget in widgets:
        path = widget_path(widget, root)
        full = _rect_in(widget, root)
        visible = _visible_rect(widget, root)
        if visible != full and not full.isEmpty():
            problems.append(f'clipped: {path} shows {visible.width()}x{visible.height()} of '
                            f'{full.width()}x{full.height()}')
        minimum = widget.minimumSizeHint()
        if not minimum.isValid():
            continue
        too_narrow = widget.width() < minimum.width() and not _ignores_size(widget, Qt.Orientation.Horizontal)
        too_short = widget.height() < minimum.height() and not _ignores_size(widget, Qt.Orientation.Vertical)
        if too_narrow or too_short:
            problems.append(f'squeezed: {path} is {widget.width()}x{widget.height()}, minimum '
                            f'{minimum.width()}x{minimum.height()}')
    return problems


# Input fields wider than this are stretched: a field column keeps the width of a strip section.
FIELD_MAX_WIDTH = STRIP_SECTION_MAX_WIDTH
FIELD_TYPES = (QComboBox, QAbstractSpinBox, NumberField, SegmentedControl)
# Empty space wider than this between parts of a panel's content strands the part after it:
EMPTY_BAND_LIMIT = 48
# A panel whose content scrolls while using less than this share of the other axis should arrange differently:
CRAMPED_SHARE = 0.5


def _is_framed_scroll_area(widget: QWidget) -> bool:
    return isinstance(widget, QAbstractScrollArea) and widget.frameShape() != QFrame.Shape.NoFrame


def _content_rects(root: QWidget) -> list[tuple[QWidget, QRect]]:
    """Returns the visible part, inside root, of each widget that shows content: leaf widgets, input fields and framed
    scroll areas, each counted whole."""
    widgets = _checked_widgets(root)
    checked = set(widgets)
    content = []
    for widget in widgets:
        ancestor = widget.parentWidget()
        inside_whole = False
        while ancestor is not None and ancestor is not root:
            if isinstance(ancestor, FIELD_TYPES) or _is_framed_scroll_area(ancestor):
                inside_whole = True
                break
            ancestor = ancestor.parentWidget()
        if inside_whole:
            continue
        whole = isinstance(widget, FIELD_TYPES) or _is_framed_scroll_area(widget)
        if whole or not any(child in checked for child in widget.findChildren(QWidget)):
            visible = _visible_rect(widget, root).intersected(root.rect())
            if not visible.isEmpty():
                content.append((widget, visible))
    return content


def _empty_bands(spans: list[tuple[int, int, QWidget]]) -> list[tuple[int, QWidget, QWidget]]:
    """Returns each gap wider than EMPTY_BAND_LIMIT between spans along one axis, as its width and the widgets that
    end before it and start after it."""
    bands = []
    end: Optional[int] = None
    last: Optional[QWidget] = None
    for start, stop, widget in sorted(spans, key=lambda span: (span[0], span[1])):
        if end is not None and last is not None and start - end > EMPTY_BAND_LIMIT:
            bands.append((start - end, last, widget))
        if end is None or stop > end:
            end, last = stop, widget
    return bands


def find_arrangement_problems(root: QWidget) -> list[str]:
    """Lists ways a panel's content is arranged badly for its size, though nothing overlaps or is clipped.

    - stretched: an input field wider than FIELD_MAX_WIDTH.
    - empty band: a gap of more than EMPTY_BAND_LIMIT pixels that crosses the whole panel, with content on both sides.
      A tall band separates rows, and a wide band separates columns.
    - cramped: a `DockPanel` whose content scrolls, while it uses less than CRAMPED_SHARE of the other axis.

    Content is what `_content_rects` returns.
    """
    problems = []
    for widget in _checked_widgets(root):
        if isinstance(widget, FIELD_TYPES) and widget.width() > FIELD_MAX_WIDTH:
            problems.append(f'stretched: {widget_path(widget, root)} is {widget.width()} wide, cap {FIELD_MAX_WIDTH}')
    content = _content_rects(root)
    for gap, before, after in _empty_bands([(rect.top(), rect.bottom() + 1, widget) for widget, rect in content]):
        problems.append(f'empty band: {gap} px tall between {widget_path(before, root)} and {widget_path(after, root)}')
    for gap, before, after in _empty_bands([(rect.left(), rect.right() + 1, widget) for widget, rect in content]):
        problems.append(f'empty band: {gap} px wide between {widget_path(before, root)} and {widget_path(after, root)}')
    if isinstance(root, DockPanel) and root.content_scrolls and len(content) > 0:
        used = QRect()
        for _, rect in content:
            used = used.united(rect)
        if root.orientation == Orientation.SIDE and used.width() < root.width() * CRAMPED_SHARE:
            problems.append(f'cramped: scrolls vertically using {used.width()} of {root.width()} width')
        elif root.orientation == Orientation.STRIP and used.height() < root.height() * CRAMPED_SHARE:
            problems.append(f'cramped: scrolls horizontally using {used.height()} of {root.height()} height')
    return problems


def layout_report(size: QSize, problems: list[str]) -> dict:
    """Returns the JSON-compatible record of one panel capture."""
    return {'size': [size.width(), size.height()], 'problems': problems}


# Dock sizes for sweep sheets, from a squeezed dock to a wide strip or a tall side panel:
SWEEP_WIDTHS = (160, 240, 360, 540, 800, 1200)
SWEEP_HEIGHTS = (100, 160, 240, 360, 540, 800)

# Common screen sizes the main window is captured at, along with its minimum size:
WINDOW_SIZES = {'small': QSize(800, 600), 'hd': QSize(1280, 720), 'full_hd': QSize(1920, 1080),
                'ultrawide': QSize(3440, 1440), 'portrait': QSize(1080, 1920)}
# MainWindow shrinks itself to the screen, and the offscreen platform's screen is smaller than most of WINDOW_SIZES:
_LARGE_SCREEN = QSize(8192, 8192)


def _large_screen() -> AbstractContextManager:
    return patch('src.ui.window.main_window.get_screen_size', return_value=_LARGE_SCREEN)


@dataclass(frozen=True)
class PanelScene:
    """A panel to capture: its snapshot name, and a function that returns the panel from a mock-mode AppController.

    A scene with `fixed_sizes` is captured at its minimum size and those sizes, and other scenes at SIZE_CASES. Captures
    run inside the context manager `context` returns.

    A scene without `fixed_sizes` is captured in each of its panel's `host_orientations`. Strip captures reuse the
    sizes measured before the first capture, so a strip is also captured tall and narrow.
    """
    name: str
    build: Callable[['AppController'], Optional[QWidget]]
    fixed_sizes: Optional[dict[str, QSize]] = None
    context: Callable[[], AbstractContextManager] = nullcontext

    def sizes(self, panel: QWidget) -> dict[str, QSize]:
        """Returns the sizes to capture the panel at, by size case name."""
        if self.fixed_sizes is not None:
            return {'minimum': panel_size('minimum', panel), **self.fixed_sizes}
        return {case: panel_size(case, panel) for case in SIZE_CASES}

    def orientations(self, panel: QWidget) -> tuple[Optional[Orientation], ...]:
        """Returns the orientations to capture the panel with, or only None for a panel no dock tells."""
        return (None,) if self.fixed_sizes is not None else host_orientations(panel)

    def captures(self, panel: QWidget) -> dict[str, tuple[QSize, Optional[Orientation]]]:
        """Returns each capture's size and orientation by capture name: the size case, prefixed with `strip_` for a
        strip capture.

        Tells the panel its first orientation before measuring, since a panel keeps the orientation it was last told.
        """
        orientations = self.orientations(panel)
        if orientations[0] is not None:
            tell_orientation(panel, orientations[0], panel.size())
            _settle_layouts(panel)
        sizes = self.sizes(panel)
        return {(f'strip_{case}' if orientation == Orientation.STRIP else case): (size, orientation)
                for orientation in orientations for case, size in sizes.items()}


def _snake_case(name: str) -> str:
    return ''.join(f'_{char.lower()}' if char.isupper() and i > 0 else char.lower() for i, char in enumerate(name))


def _tool_control_scenes(controller: 'AppController') -> list[PanelScene]:
    # pylint: disable=protected-access
    scenes = []
    for tool in controller._tool_controller.tools:
        if tool.get_control_panel() is not None:
            scenes.append(PanelScene(_snake_case(type(tool).__name__) + '_controls',
                                     lambda _controller, panel_tool=tool: panel_tool.get_control_panel()))
    return scenes


def _show_tool(controller: 'AppController', tool) -> QWidget:
    # pylint: disable=protected-access
    controller._tool_controller.active_tool = tool
    return controller._tool_panel


def tools_panel_scenes(controller: 'AppController') -> list[PanelScene]:
    """Returns a scene for the Tools panel with each tool that has a control panel active, for sweep sheets.

    Each scene makes its tool the active tool when built.
    """
    # pylint: disable=protected-access
    return [PanelScene('tools_panel_' + _snake_case(type(tool).__name__),
                       lambda c, panel_tool=tool: _show_tool(c, panel_tool))
            for tool in controller._tool_controller.tools if tool.get_control_panel() is not None]


def panel_scenes(controller: 'AppController') -> list[PanelScene]:
    """Returns every panel scene for a mock-mode AppController, in capture order.

    Later scenes take their panels out of the main window while they're captured, so the main window comes first.
    """
    # pylint: disable=import-outside-toplevel,protected-access
    from src.ui.panel.generators.stable_diffusion_panel import StableDiffusionPanel
    # Panels that show the controller's ImageStack are the controller's own: a discarded copy would leave the stack
    # connected to deleted graphics items.
    return [
        PanelScene('main_window', lambda c: c._window, WINDOW_SIZES, _large_screen),
        PanelScene('tool_panel', lambda c: c._tool_panel),
        PanelScene('layer_panel', lambda c: c._window.layers_dock.content),
        PanelScene('color_panel', lambda c: c._tool_panel_color_picker),
        PanelScene('navigation_panel', lambda c: c._tool_panel_navigation_panel),
        PanelScene('sd_webui_panel', lambda _c: StableDiffusionPanel(True, True)),
        PanelScene('sd_comfyui_panel', lambda _c: StableDiffusionPanel(False, False)),
        *_tool_control_scenes(controller),
    ]


def mock_app_controller() -> 'AppController':
    """Restores config option lists with restore_option_lists, then returns a new AppController in mock mode."""
    # pylint: disable=import-outside-toplevel
    from src.controller.app_controller import AppController
    from src.util.arg_parser import build_arg_parser
    restore_option_lists()
    args = build_arg_parser(include_edit_params=False).parse_args([])
    args.mode = 'mock'
    args.server_url = ''
    args.fast_ngrok_connection = False
    return AppController(args)


def restore_option_lists() -> None:
    """Restores every AppConfig and Cache option list to its definition, so combo boxes hold all their options.

    IntraPaintTestCase's config reset trims option lists to the default value alone.
    """
    # pylint: disable=import-outside-toplevel
    from src.config.application_config import AppConfig
    from src.config.cache import Cache
    for config in (AppConfig(), Cache()):
        for key in config.get_keys():
            config.restore_default_options(key)
