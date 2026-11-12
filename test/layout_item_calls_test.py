"""Fails on layout calls that make PySide wrap layout items, which can corrupt the heap.

A layout item wrapper stays registered at the item's address. If the item's widget moves to another layout, is
unparented or is deleted while the layout lives on, Qt frees the item without PySide knowing, and the stale wrapper
corrupts the heap. `QLayout.itemAt` and `QGridLayout.itemAtPosition` return such a wrapper: use
`src.util.layout.layout_contents`, `QLayout.indexOf`, or `takeAt` instead. `addLayout`, `insertLayout` and
`addChildLayout` wrap every item already in the child layout: use `src.util.layout.add_layout`, which only accepts an
empty child.
"""
import ast
from pathlib import Path

from test.base_test_case import IntraPaintTestCase

ROOT = Path(__file__).resolve().parent.parent
CHECKED_DIRS = ('src', 'test', 'scripts')
BANNED_METHODS = ('itemAt', 'itemAtPosition', 'addLayout', 'insertLayout', 'addChildLayout')

ALLOWED_CALLS = {
    # Receivers that are not layouts. `QListWidget.itemAt(QPoint)` returns a model item, and is safe.
    ('src/ui/panel/mypaint_brush_grid.py', 'self.itemAt'),
    ('src/ui/panel/mypaint_brush_panel.py', 'self._grid.itemAt'),
    # The one checked caller:
    ('src/util/layout.py', 'parent.addLayout'),
    # Pins the PySide behavior add_layout works around:
    ('test/util/layout_test.py', 'self.outer.addLayout'),
}


class LayoutItemCallsTest(IntraPaintTestCase):
    """Keeps layout item wrapper calls out of the codebase."""

    def test_no_layout_item_calls(self) -> None:
        """No source, test or script file calls a layout method that wraps layout items."""
        found = []
        for directory in CHECKED_DIRS:
            for path in sorted((ROOT / directory).rglob('*.py')):
                relative = path.relative_to(ROOT).as_posix()
                tree = ast.parse(path.read_text(encoding='utf-8'), filename=relative)
                for node in ast.walk(tree):
                    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                            and node.func.attr in BANNED_METHODS):
                        receiver = ast.unparse(node.func)
                        if (relative, receiver) not in ALLOWED_CALLS:
                            found.append(f'{relative}:{node.lineno}: {receiver}()')
        self.assertEqual([], found, 'Use layout_contents, QLayout.indexOf or takeAt instead of itemAt/itemAtPosition,'
                                    ' and add_layout instead of addLayout/insertLayout/addChildLayout')
