"""Fails on `QLayout.itemAt` and `QGridLayout.itemAtPosition` calls, which can corrupt the heap.

The wrapper those calls return stays registered at the item's address. If the item's widget is deleted or unparented
while the layout lives on, Qt frees the item without PySide knowing, and the stale wrapper corrupts the heap. Use
`src.util.layout.layout_contents`, `QLayout.indexOf`, or `takeAt` instead.
"""
import ast
from pathlib import Path

from test.base_test_case import IntraPaintTestCase

ROOT = Path(__file__).resolve().parent.parent
CHECKED_DIRS = ('src', 'test')
BANNED_METHODS = ('itemAt', 'itemAtPosition')

# Receivers that are not layouts. `QListWidget.itemAt(QPoint)` returns a model item, and is safe.
ALLOWED_CALLS = {
    ('src/ui/panel/mypaint_brush_panel.py', 'self.itemAt'),
    ('src/ui/panel/mypaint_brush_panel.py', 'self._grid.itemAt'),
}


class LayoutItemCallsTest(IntraPaintTestCase):
    """Keeps layout item wrapper calls out of the codebase."""

    def test_no_layout_item_calls(self) -> None:
        """No source or test file calls `itemAt` or `itemAtPosition` on a layout."""
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
        self.assertEqual([], found, 'Use layout_contents, QLayout.indexOf or takeAt instead of itemAt/itemAtPosition')
