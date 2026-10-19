# Panel layout rules

What a correct panel layout is, independent of how one is produced. `src/ui/layout/panel_fit.py` and
`src/ui/layout/dock_panel.py` describe the planner. This file describes the result it is judged against. A layout is
correct when it follows these rules at every size the sweep covers, not only at the size a mock-up was drawn at.

## Scope

- **The rules govern content inside a panel:** sections, controls, previews and lists. The user decides the size of
  each dock and panel. Nothing here sizes or places a dock.
- **"Room" is space inside the panel being laid out.** Space in a neighboring dock doesn't count.

## The rules

Highest precedence first. When two rules conflict, the higher one wins.

1. **Nothing is cut off while there is room for it.** No control is clipped, squeezed below its minimum size,
   scrolled out of view, or moved to the More popover while the panel has room to show it, in any of its forms.
   Scrolling and More are for content that doesn't fit at all.
2. **Content that can use space gets the spare space.** Some content makes good use of nearly any size: multi-line
   text fields, the font list, the MyPaint brush grid, the layer list, the navigation view and the brush previews.
   - Spare space in a panel goes to this growable content, up to its maximum, before any of it is spread over other
     content.
   - Its maximums are much larger than other content's, but finite.
   - Optional controls are placed first. Growable content takes what remains, never space an optional control needs
     under rule 1.
   - With several growable items, each gets a share by its weight until it reaches its maximum.
3. **Leftover space sits after the content.** When nothing can use more space, the spare space collects below the
   content and toward its trailing edge (right, or left in right-to-left languages).
   - Content isn't stretched or spread out to fill it.
   - Content is arranged so its overall shape follows the panel's. When one part needs far more height than the rest,
     such as the brush grid beside a few fields, the rest stacks or wraps beside it. A row aligned to the tallest part
     strands the space under the others.
4. **Neighbors align.** Sections and controls line up with their neighbors on both axes.
   - Leading edges (top, and left in left-to-right languages) take precedence over trailing edges.
   - A stretchable control may stretch to reach a neighbor's edge, by less than twice its natural size.
   - Rule 3 wins over this one: an arrangement that aligns everything in one row but strands a large empty area is
     worse than one with fewer aligned edges.
5. **Order and position change only for a reason.** Any rule above is reason enough to move or reorder content.
   - Between arrangements that differ only in order or position, the current one stays.
   - `HYSTERESIS` delays a switch at a boundary by at most that many pixels so a dragged separator doesn't flicker. It
     never keeps a worse arrangement beyond that.
   - Content that must keep an order declares it as an override (see "Exceptions"), such as Size first in the stroke
     block.

## Arrangement

- **Sections pack into the panel like a grid.** Sections flow into as many columns or rows as fit, and the orientation
  is the direction they prefer to flow, so a large, square panel can use both axes.
- **"Best" means fewest rule violations, compared in precedence order.** Ties go to rule 5. The planner tries the
  declared order first and reorders only when that order breaks a higher rule. It doesn't search every possible
  packing, which would make arrangements jump while a separator is dragged.

## Exceptions

- **Any rule can be overridden where following it gives a distinctly worse result.** These rules are incomplete, and
  some arrangements look wrong despite following them.
- **An override is a declaration on the content,** such as a width cap (`set_field_width_cap`), a fixed order or a
  stretch limit, with a comment that says why.
- **A sweep problem an override causes on purpose is recorded as intentional,** not as a known bug.
  `KNOWN_PROBLEMS` in `test/ui/panel_sweep_test.py` records only bugs, each with the open issue that tracks it.

## Also binding

These hold alongside the five rules and outrank none of them.

- **Nothing is removed.** Content that doesn't fit moves to More. Decorative content, such as a preview, hides.
- **Re-planning keeps widgets.** Widget objects, their state and keyboard focus survive any re-arrangement.
- **A panel's minimum size doesn't depend on history.** The same size gives the same minimum size hint, whatever the
  panel showed before.
- **Things that belong together stay together.** A label stays with its field, and the More button stays beside the
  content it belongs to.
- **Parents plan first.** A child gets the space its parent leaves it, and a child's content size never feeds back into
  the space its host reports.
- **No pixel thresholds in panel code.** Panels measure whether content fits, so the result holds at any font size or
  DPI.
- **Shared parts look the same everywhere.** Switching tools doesn't move the parts tools share, such as the header,
  unless a rule above requires it at that size.
- **The window fits 1024x600** with its first-run panels open.

## Definitions

- **Natural size:** a widget's size hint.
- **Stretchable:** input fields (combo boxes, number and slider fields, text fields, segmented controls). Buttons,
  icon buttons and check boxes keep their natural size. Previews keep their aspect ratio.
- **Growable:** content that rule 2 lists, with a weight and a maximum size.
- **Neighbors:** two items that share a row or column band with nothing between them.

## How the rules are checked

`test/ui/panel_sweep_test.py` sweeps every panel across a grid of dock sizes. `find_layout_problems` and
`find_arrangement_problems` in `test/ui/panel_capture.py` report each problem by kind.

| Rule | Checked by |
| --- | --- |
| 1 | `clipped`, `squeezed`, `overlap`, `cramped` |
| 2 | Not yet checked |
| 3 | `empty band` |
| 4 | Not yet checked |
| 5 | Not checked |

- **The `stretched` check conflicts with rule 4.** It holds each field to a fixed cap, `FIELD_MAX_WIDTH` or its own
  `set_field_width_cap`, while rule 4 lets a field stretch relative to its natural size to align. A field stretched to
  align can fail it.
- **The planner can't express rules 2 and 4 yet.** A `FitItem` has a priority and a form count only. Spare space goes
  wherever the panel's stretch factors put it, and the stretch `DockPanel.__init__` adds after the sections takes it
  ahead of any growable content.
