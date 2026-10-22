# Panel layout

What a panel layout has to do, and where its look comes from. `src/ui/layout/panel_fit.py` and
`src/ui/layout/dock_panel.py` describe the planner that places content.

## Where the look comes from

- **The design is the spec.** Build each panel as the "IntraPaint Panel Redesign" review shows it (linked from #301).
  Its mock-ups are drawn at sample sizes, not layout classes.
- **Between and beyond the mock-ups, keep the nearest mock-up's arrangement.** The fit planner adapts it with
  priorities, forms and More. Don't invent a new arrangement, and don't build a general mechanism to choose one.
- **The maintainer revises layouts after a panel lands,** by reading its sweep sheets. A revision is a change to that
  panel's own code. Where it isn't obvious from the code, a comment says what it does.
- **Look is judged by eye.** No test enforces alignment, spacing or how spare space is spread. The sweep checks report
  those as hints (see "How layouts are checked").

## Invariants

These hold at every size, whatever the design shows.

- **Nothing is cut off while there is room for it.** No control is clipped, squeezed below its minimum size, overlapped,
  scrolled out of view, or moved to the More popover while the panel has room to show it. Scrolling and More are for
  content that doesn't fit at all.
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
