"""Checks the ctypes declarations in src/image/mypaint/libmypaint.py against the functions the code calls."""
import os
import re
import unittest

from src.image.mypaint.libmypaint import libmypaint
from test.base_test_case import PROJECT_ROOT

# Matches `libmypaint.mypaint_x(` and `lib.mypaint_x.` uses.
LIBMYPAINT_CALL = re.compile(r'\b(?:libmypaint|lib)\.(mypaint_\w+)')


def called_libmypaint_functions() -> set[str]:
    """Returns the name of every libmypaint function that code under src/ uses."""
    names: set[str] = set()
    for dir_path, _, file_names in os.walk(os.path.join(PROJECT_ROOT, 'src')):
        for file_name in file_names:
            if file_name.endswith('.py'):
                with open(os.path.join(dir_path, file_name), encoding='utf-8') as file:
                    names.update(LIBMYPAINT_CALL.findall(file.read()))
    return names


class LibMyPaintDeclarationTest(unittest.TestCase):
    """Without argtypes, ctypes passes a Python int as a 32-bit C int, so a pointer above 4 GiB loses its high bits.
       Whether that crashes depends on where the heap lands, so it can pass locally and segfault in CI."""

    def test_called_functions_declare_argtypes(self) -> None:
        """Every libmypaint function the code calls declares its argument types."""
        names = called_libmypaint_functions()
        self.assertIn('mypaint_brush_unref', names)
        # mypaint_tiled_surface_init only receives byref() and CFUNCTYPE arguments, which ctypes passes as pointers.
        undeclared = sorted(name for name in names - {'mypaint_tiled_surface_init'}
                            if getattr(libmypaint, name).argtypes is None)
        self.assertEqual(undeclared, [])


if __name__ == '__main__':
    unittest.main()
