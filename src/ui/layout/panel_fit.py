"""Orientation and fit planning for panels: what a panel shows, and in which form, from the space its host reports.

A panel never measures the window. Its host reports an `Orientation` and the size the panel fills, and the panel shows
as much as fits there. Thresholds live in this module, so DPI normalization (issue #13) changes them in one place.
`doc/agents/panel_layout.md` lists what a planned layout has to do.

- Orientation comes from the space a panel fills: a panel taller than wide is a side panel, a wide one is a strip,
  with `HYSTERESIS` on the switch, so a tall panel in a bottom dock still lays out as a side panel. The dock area
  still sets unmigrated panels' orientation (`orientation_for_dock`), until the last one moves to `DockPanel`.
- Side panels are a tall column that scrolls vertically. Strip panels are a wide row that scrolls horizontally. The
  scroll axis is the long one, and the other is the cross axis.
- Content is a list of `FitItem`s, each with a priority and one or more forms, largest first. `plan_fit` picks a form
  for each item, or leaves an optional item out:
  - `REQUIRED` items are always shown, in their largest form that fits on the cross axis. They may scroll.
  - Optional items take their largest form that fits on both axes, or are left out. Lower priorities are placed
    first, and ties go in declaration order.
  - A form fits on an axis if it doesn't make the content overflow the available size there, or overflow further than
    it already does. An optional item that adds nothing along the scroll axis still shows while required content
    scrolls.
- `plan_fit` keeps the current placement until a better one fits with `HYSTERESIS` pixels to spare, so dragging a
  separator across a boundary doesn't flicker. A current placement that no longer fits doesn't hold, since forms of
  one item can differ in shape.
- `plan_orientation` plans both orientations. The one whose content fits better wins; ties go to the orientation the
  size suggests, so a square-ish panel keeps its orientation until the other axis is longer by more than `HYSTERESIS`
  pixels. Switching needs `HYSTERESIS` pixels to spare too.
- `plan_fit` is pure. A `measure` callback returns a placement's minimum size. `FitPlanner` binds it to widgets, and
  `fresh_minimum_size` measures widgets without waiting on the event loop.
"""
import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Protocol, Sequence, TypeVar, runtime_checkable
from weakref import WeakMethod

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QApplication, QSizePolicy, QWidget


class Orientation(Enum):
    """Whether a panel is a tall column or a wide row."""
    SIDE = 'side'
    STRIP = 'strip'


HYSTERESIS = 6

STRIP_SECTION_MIN_WIDTH = 240
STRIP_SECTION_MAX_WIDTH = 300

# The widest an input field is laid out, unless set_field_width_cap gives it its own cap:
FIELD_MAX_WIDTH = STRIP_SECTION_MAX_WIDTH
FIELD_WIDTH_CAP_PROPERTY = 'field_width_cap'
_UNCAPPED = -1


def set_field_width_cap(field: QWidget, cap: Optional[int]) -> None:
    """Gives an input field its own width cap in place of FIELD_MAX_WIDTH, or lets it stretch with None.

    The cap is what layout checks hold the field to (`find_arrangement_problems` in `test/ui/panel_capture.py`). It
    doesn't resize the field: its maximum width and size policy do that.
    """
    field.setProperty(FIELD_WIDTH_CAP_PROPERTY, _UNCAPPED if cap is None else cap)


def field_width_cap(field: QWidget) -> Optional[int]:
    """Returns the widest a field should be laid out: its `set_field_width_cap` cap, or FIELD_MAX_WIDTH, or None if it
    may stretch."""
    cap = field.property(FIELD_WIDTH_CAP_PROPERTY)
    if cap is None:
        return FIELD_MAX_WIDTH
    return None if cap == _UNCAPPED else int(cap)

# The priority of items that are always shown:
REQUIRED = 0

# One entry per item: the index of the form it takes, or None for an optional item that is left out.
Placement = tuple[Optional[int], ...]


@dataclass(frozen=True)
class FitItem:
    """One part of a panel's content: a priority, and how many forms it has, largest first.

    Raises ValueError for a negative priority or a form count below 1.
    """
    priority: int = REQUIRED
    form_count: int = 1

    def __post_init__(self) -> None:
        if self.priority < REQUIRED:
            raise ValueError(f'Invalid priority {self.priority}')
        if self.form_count < 1:
            raise ValueError(f'Invalid form count {self.form_count}')

    @property
    def required(self) -> bool:
        """Whether the item is always shown."""
        return self.priority == REQUIRED


def orientation_for_size(size: QSize, current: Optional[Orientation] = None) -> Orientation:
    """Returns the orientation a panel of `size` arranges its content in: side when it is taller than wide, strip
    otherwise, with `HYSTERESIS` on the switch.

    `current` is the orientation in use, if any. It holds while the other axis is longer by at most `HYSTERESIS`
    pixels, so resizing through a square size doesn't switch back and forth. A square size is a strip.
    """
    taller_by = size.height() - size.width()
    if current == Orientation.SIDE:
        return Orientation.SIDE if taller_by >= -HYSTERESIS else Orientation.STRIP
    if current == Orientation.STRIP:
        return Orientation.SIDE if taller_by > HYSTERESIS else Orientation.STRIP
    return Orientation.SIDE if taller_by > 0 else Orientation.STRIP


def orientation_for_dock(area: Qt.DockWidgetArea, floating: bool, size: QSize,
                         current: Optional[Orientation] = None) -> Orientation:
    """Returns the orientation an unmigrated dock's content arranges in: from the area when docked, from the size
    when floating.

    Left and right areas are side panels, top and bottom are strips. Migrated `DockPanel` content plans from its
    size alone (`orientation_for_size`), so this area rule only matters until the last panel with a `set_orientation`
    layout moves to `DockPanel`, and then it is removed.
    """
    if floating:
        return orientation_for_size(size, current)
    if area in (Qt.DockWidgetArea.LeftDockWidgetArea, Qt.DockWidgetArea.RightDockWidgetArea):
        return Orientation.SIDE
    return Orientation.STRIP


def cross_extent(size: QSize, orientation: Orientation) -> int:
    """Returns a size's extent on the cross axis: width for side panels, height for strips."""
    return size.width() if orientation == Orientation.SIDE else size.height()


def scroll_extent(size: QSize, orientation: Orientation) -> int:
    """Returns a size's extent on the scroll axis: height for side panels, width for strips."""
    return size.height() if orientation == Orientation.SIDE else size.width()


def base_placement(items: Sequence[FitItem]) -> Placement:
    """Returns the placement with required items in their smallest forms and optional items left out."""
    return tuple(item.form_count - 1 if item.required else None for item in items)


def _rank(items: Sequence[FitItem], placement: Placement) -> tuple[int, ...]:
    """Orders placements: lower is better, comparing items in fill order, larger forms before smaller ones and any
    form before none."""
    return tuple(item.form_count if placement[i] is None else placement[i]
                 for i, item in sorted(enumerate(items), key=lambda entry: (entry[1].priority, entry[0])))


def _left_out(items: Sequence[FitItem], placement: Placement) -> tuple[bool, ...]:
    """Orders placements by which optional items they show, in fill order, ignoring their forms."""
    return tuple(placement[i] is None
                 for i, item in sorted(enumerate(items), key=lambda entry: (entry[1].priority, entry[0]))
                 if not item.required)


def _fits_axis(need: int, before: int, available: int) -> bool:
    return need <= max(available, before)


def _greedy(items: Sequence[FitItem], available: QSize, orientation: Orientation,
            measure: Callable[[Placement], QSize]) -> Placement:
    placement = list(base_placement(items))
    before = measure(tuple(placement))
    for index in sorted(range(len(items)), key=lambda i: (items[i].priority, i)):
        item = items[index]
        # A required item already holds its smallest form:
        forms = range(item.form_count - 1) if item.required else range(item.form_count)
        for form in forms:
            trial = list(placement)
            trial[index] = form
            need = measure(tuple(trial))
            fits = _fits_axis(cross_extent(need, orientation), cross_extent(before, orientation),
                              cross_extent(available, orientation))
            if fits and not item.required:
                fits = _fits_axis(scroll_extent(need, orientation), scroll_extent(before, orientation),
                                  scroll_extent(available, orientation))
            if fits:
                placement = trial
                before = need
                break
    return tuple(placement)


def plan_fit(items: Sequence[FitItem], available: QSize, orientation: Orientation,
             measure: Callable[[Placement], QSize], current: Optional[Placement] = None) -> Placement:
    """Returns the placement for content in an available size, following the rules in this module's docstring.

    `measure` returns the minimum size of the content arranged for a placement. `current` is the placement in use, if
    any. A better placement replaces it only once it fits in `available` shrunk by `HYSTERESIS` on both axes, unless
    `current` no longer fits: it is larger across than the best fit, or its optional items overflow the scroll axis.
    """
    cache: dict[Placement, QSize] = {}

    def _measure(placement: Placement) -> QSize:
        if placement not in cache:
            cache[placement] = measure(placement)
        return cache[placement]

    planned = _greedy(items, available, orientation, _measure)
    if current is None or len(current) != len(items) or _rank(items, planned) >= _rank(items, current):
        return planned
    roomy = _greedy(items, QSize(available.width() - HYSTERESIS, available.height() - HYSTERESIS), orientation,
                    _measure)
    if _rank(items, roomy) < _rank(items, current):
        return roomy
    # The current placement holds only while it still fits as `_greedy` judges it: across within the best fit, and
    # with its optional items adding no overflow along the scroll axis.
    need = _measure(current)
    required_need = _measure(tuple(form if item.required else None for item, form in zip(items, current)))
    if not _fits_axis(cross_extent(need, orientation), cross_extent(_measure(planned), orientation),
                      cross_extent(available, orientation)) \
            or not _fits_axis(scroll_extent(need, orientation), scroll_extent(required_need, orientation),
                              scroll_extent(available, orientation)):
        return planned
    return current


def _invalidate_sizes(widget: QWidget) -> None:
    widget.updateGeometry()
    policy = widget.sizePolicy()
    ignored = QSizePolicy.Policy.Ignored
    if (policy.horizontalPolicy() == ignored and policy.verticalPolicy() == ignored) \
            or widget.minimumSize() == widget.maximumSize():
        return
    for child in widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
        if not child.isHidden() and not child.isWindow():
            _invalidate_sizes(child)
    layout = widget.layout()
    if layout is not None:
        layout.invalidate()


def _overflows(need: QSize, available: QSize) -> bool:
    return need.width() > available.width() or need.height() > available.height()


def plan_orientation(items: Sequence[FitItem], available: QSize,
                     measure: Callable[[Orientation, Placement], QSize],
                     current: Optional[tuple[Orientation, Placement]] = None) -> tuple[Orientation, Placement]:
    """Returns the orientation and placement for content in an available size, planning each orientation with
    `plan_fit`.

    - The orientation whose content doesn't overflow the available size wins, then the one that shows more optional
      items, in fill order, then the one the size's shape suggests, then the one with larger forms. Form sizes come
      last because forms differ between orientations, so a strip's larger buttons say nothing about which orientation
      suits the space.
    - The shape suggestion comes from `orientation_for_size` with the current orientation as its hysteresis anchor, so
      a square-ish panel keeps its arrangement until the other axis is longer by more than `HYSTERESIS` pixels.
    - `current` is the orientation and placement in use, if any. Another orientation replaces it only once it also
      wins in `available` shrunk by `HYSTERESIS` on both axes.
    """
    guess = orientation_for_size(available, current[0] if current is not None else None)

    def _plan(orientation: Orientation, size: QSize) -> tuple[tuple, Placement]:
        in_use = current[1] if current is not None and current[0] == orientation else None
        placement = plan_fit(items, size, orientation, lambda p: measure(orientation, p), in_use)
        score = (_overflows(measure(orientation, placement), size), _left_out(items, placement),
                 orientation != guess, _rank(items, placement))
        return score, placement

    plans = {guess: _plan(guess, available)}
    overflows, left_out = plans[guess][0][:2]
    # Nothing beats the suggested orientation when it fits and leaves nothing out, so the other needs no plan:
    if not overflows and not any(left_out) and (current is None or current[0] == guess):
        return guess, plans[guess][1]
    other = Orientation.STRIP if guess == Orientation.SIDE else Orientation.SIDE
    plans[other] = _plan(other, available)
    best = min(plans, key=lambda orientation: plans[orientation][0])
    if current is None or best == current[0]:
        return best, plans[best][1]
    roomy_score, _ = _plan(best, QSize(available.width() - HYSTERESIS, available.height() - HYSTERESIS))
    if roomy_score < plans[current[0]][0]:
        return best, plans[best][1]
    return current[0], plans[current[0]][1]


def fresh_minimum_size(root: QWidget) -> QSize:
    """Returns root's minimum size after clearing the cached sizes under it.

    Qt recomputes a parent layout's sizes only once a posted layout request runs, so without this a change made since
    the last event loop pass doesn't count. Nothing inside a hidden widget, a fixed-size widget or one whose size policy
    ignores its hints on both axes changes its parent's minimum, so their subtrees are skipped.
    """
    _invalidate_sizes(root)
    hint = root.minimumSizeHint()
    # A shown window's layout sets the window's minimum size to its last hint:
    return hint if root.isWindow() else hint.expandedTo(root.minimumSize())


_Result = TypeVar('_Result')


def _held_weakly(callback: Callable[..., _Result]) -> Callable[..., _Result]:
    """Returns a bound method as a callable that holds its object weakly, and any other callable unchanged."""
    if not inspect.ismethod(callback):
        return callback
    method_ref = WeakMethod(callback)

    def _call(*args):
        method = method_ref()
        assert method is not None, 'A FitPlanner outlived the object its callbacks belong to'
        return method(*args)
    return _call


class FitPlanner:
    """Plans one content's placement with `plan_fit`, applies it, and remembers it for hysteresis.

    Callbacks that are bound methods are held weakly, since the content usually owns its planner. A reference cycle
    leaves a parentless widget to the cyclic garbage collector, which can delete it in C++ during an unrelated Qt call
    (see `src.util.gc_paused`). A lambda that captures the content still makes a cycle.

    - `apply(orientation, placement)` arranges the content's widgets for a placement. Planning applies trial placements
      in any order, so `apply` must leave no trace of earlier ones.
    - `measure()` returns the arranged content's minimum size, usually through `fresh_minimum_size`.
    - `prepare(orientation)` runs before the trials in each orientation planned, and once more if needed before the
      result is applied. `finish(orientation)` runs after the result is applied. Neither runs when `update` skips
      planning.
    - Keyboard focus survives planning, though trials may hide or move the focused widget.
    """

    def __init__(self, items: Sequence[FitItem], apply: Callable[[Orientation, Placement], None],
                 measure: Callable[[], QSize], prepare: Optional[Callable[[Orientation], None]] = None,
                 finish: Optional[Callable[[Orientation], None]] = None) -> None:
        self._items = tuple(items)
        self._apply = _held_weakly(apply)
        self._measure = _held_weakly(measure)
        self._prepare = None if prepare is None else _held_weakly(prepare)
        self._finish = None if finish is None else _held_weakly(finish)
        self._placement: Optional[Placement] = None
        self._orientation: Optional[Orientation] = None
        # The orientation the latest update asked for, or None when planning picked it:
        self._requested: Optional[Orientation] = None
        self._available: Optional[QSize] = None
        self._applied = False

    @property
    def items(self) -> tuple[FitItem, ...]:
        """The items planned for."""
        return self._items

    @property
    def placement(self) -> Optional[Placement]:
        """The placement from the latest update, or None before the first one."""
        return self._placement

    @property
    def available(self) -> Optional[QSize]:
        """The available size being planned for, or from the latest update, or None before the first one."""
        return self._available

    def update(self, orientation: Optional[Orientation], available: QSize, force: bool = False) -> bool:
        """Plans for an orientation and available size and applies the result, returning whether the placement or
        orientation changed. Skips planning when neither input changed, unless `force` is set.

        With `orientation` None, `plan_orientation` picks the orientation from the available size and the content's
        fit.
        """
        if self._applied and not force and orientation == self._requested and available == self._available:
            return False
        focus = QApplication.focusWidget()
        self._requested = orientation
        self._available = QSize(available)
        prepared: list[Orientation] = []

        def _measure(planned_orientation: Orientation, placement: Placement) -> QSize:
            if self._prepare is not None and prepared[-1:] != [planned_orientation]:
                self._prepare(planned_orientation)
                prepared.append(planned_orientation)
            self._apply(planned_orientation, placement)
            return self._measure()

        in_use = None if self._placement is None or self._orientation is None else (self._orientation,
                                                                                     self._placement)
        if orientation is None:
            orientation, placement = plan_orientation(self._items, available, _measure, in_use)
        else:
            fixed = orientation
            current = self._placement if orientation == self._orientation else None
            placement = plan_fit(self._items, available, fixed, lambda p: _measure(fixed, p), current)
        if self._prepare is not None and prepared[-1:] != [orientation]:
            self._prepare(orientation)
        self._apply(orientation, placement)
        changed = placement != self._placement or orientation != self._orientation
        self._placement = placement
        self._orientation = orientation
        self._applied = True
        if self._finish is not None:
            self._finish(orientation)
        if focus is not None and QApplication.focusWidget() is not focus and focus.isVisible():
            focus.setFocus()
        return changed

    def measure_placement(self, placement: Placement) -> QSize:
        """Returns the content's minimum size arranged for a placement in the current orientation, then arranges the
        content as it was. Planning state is untouched. Returns the current size before the first update."""
        if self._orientation is None or self._placement is None:
            return self._measure()
        orientation = self._orientation
        if self._prepare is not None:
            self._prepare(orientation)
        self._apply(orientation, placement)
        size = self._measure()
        if self._prepare is not None:
            self._prepare(orientation)
        self._apply(orientation, self._placement)
        if self._finish is not None:
            self._finish(orientation)
        return size

    def base_size(self, orientation: Orientation) -> QSize:
        """Returns the content's minimum size with only required items, in their smallest forms. The content keeps
        that arrangement until the next `update`, which then plans even with unchanged inputs."""
        self._apply(orientation, base_placement(self._items))
        self._applied = False
        return self._measure()


@runtime_checkable
class FitContent(Protocol):
    """Content that plans its own layout in the space a parent panel gives it.

    The parent plans first, measuring the content at `fit_base_size`, then passes the space left over to
    `set_fit_space`. Optional controls the content leaves out go in `overflow_content`.
    """

    def fit_base_size(self, orientation: Orientation) -> QSize:
        """Returns the minimum size with only required items, in their smallest forms, and keeps that arrangement
        until the next `set_fit_space`."""

    def set_fit_space(self, orientation: Orientation, size: QSize) -> None:
        """Plans for the space the parent gives the content."""

    def overflow_content(self) -> QWidget:
        """Returns a widget holding the controls the latest plan left out, which the parent shows in its More
        popover. It is empty, with no visible children, while every control fits."""
