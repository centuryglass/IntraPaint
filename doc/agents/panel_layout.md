# Panel layout

What a panel layout has to do, and where its look comes from. `src/ui/layout/panel_fit.py` and
`src/ui/layout/dock_panel.py` describe the planner that places content.

## Where the look comes from

- **The code is the spec.** A panel's own code, its pinned layout snapshots and its sweep sheets define how it looks.
  A design mock-up is a draft that a panel's code can depart from, and is never updated to match the code.
- **The maintainer approves a new arrangement** by reading its sweep sheets. Each panel's arrangement lives in its own
  code, adapted to each size by the fit planner's priorities, forms and More. Don't build a general mechanism that
  picks between arrangements. Where an arrangement isn't obvious from the code, a comment says what it does.
- **Look is judged by eye.** No test enforces alignment, spacing or how spare space is spread. The sweep checks report
  those as hints (see "How layouts are checked").

## Shared conventions

Every panel builds from the same controls, so a habit learned in one panel carries to the next. Each owning module
describes its control.

- **Numbers use a slider-field** (`SliderField`, or `NumberField` for an unbounded value), which carries its own label
  and unit.
- **Groups are `PanelSection`s,** with a short header that collapses to a summary of the section's values. The
  most-used section comes first.
- **A short choice that changes often is a `SegmentedControl`** (2-5 options). A long list stays a combo box.
- **Push buttons take a `ButtonWeight`,** with at most one primary per panel. A destructive action uses the danger
  weight and sits apart from its neighbors. Every icon-only button has a tooltip naming its action and key.
- **Labels are sentence case, with no trailing colon and no unit** (`normalize_row_label`). Non-numeric rows share
  one label column (`LabelColumnLayout`).
- **A repeated group is one shared block** with the same order everywhere: `StrokeBlock` for brush-like tools,
  `GeometryBlock` for position and size fields, `SelectionModeBar` for selection tools.
- **A control leaves its panel only when it is rarely changed or duplicated elsewhere.** It moves to More, Settings or
  a menu, and nothing is removed (see "Invariants").

## Invariants

These hold at every size.

- **Nothing is cut off while there is room for it.** No control is clipped, squeezed below its minimum size, overlapped,
  scrolled out of view, or moved to the More popover while the panel has room to show it. Scrolling and More are for
  content that doesn't fit at all.
- **A dock stops shrinking a panel where its content would escape.** Once the planned content overflows a panel across
  its scroll axis, `DockPanel.minimumSizeHint` raises that axis to the extent the content needs, for as long as the
  orientation and scroll-axis size stay the same.
- **Nothing is removed.** Content that doesn't fit moves to More. Decorative content, such as a preview, hides. A
  collapsible section collapses to its summary, and its header opens the body in a popover.
- **Re-planning keeps widgets.** Widget objects, their state and keyboard focus survive any re-arrangement.
- **A panel's minimum size doesn't depend on history.** The same size gives the same minimum size hint, whatever the
  panel showed before.
- **Things that belong together stay together.** A label stays with its field, and the More button stays beside the
  content it belongs to.
- **Parents plan first.** A child gets the space its parent leaves it, and a child's content size never feeds back into
  the space its host reports.
- **No pixel thresholds in panel code.** Panels measure whether content fits, so the result holds at any font size or
  DPI.
- **The window fits 1024x600** with its first-run panels open.
- **The user decides dock and panel sizes.** Layout code places content inside a panel and never sizes or places a
  dock.

## How layouts are checked

`test/ui/panel_sweep_test.py` sweeps every panel across a grid of dock sizes. `find_layout_problems` and
`find_arrangement_problems` in `test/ui/panel_capture.py` report each problem by kind.

- **Problems fail the sweep** unless `KNOWN_PROBLEMS` lists them with the open issue that tracks them: `clipped`,
  `squeezed`, `overlap` and `hidden with room`.
- **Hints never fail a test:** every kind in `HINT_KINDS`. Sweep sheets caption them in amber. Change a layout for a
  hint only when the maintainer asks.
- The other invariants have no sweep check.
- **The sweep's host is a plain widget, not a dock.** `test/ui/window/docked_panel_resize_test.py` drags the separators
  around a panel docked in a `QMainWindow`, which is where a panel's size hints decide whether the dock overlaps its
  neighbors.
