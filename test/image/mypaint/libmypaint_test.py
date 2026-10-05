"""Tests the ctypes declarations for libmypaint functions."""
from ctypes import c_void_p

from src.image.mypaint.libmypaint import libmypaint
from test.base_test_case import IntraPaintTestCase


class LibMyPaintDeclarationTest(IntraPaintTestCase):
    """Tests that pointer arguments are declared, so ctypes passes them at full width."""

    def test_brush_unref_takes_full_width_pointer(self) -> None:
        """mypaint_brush_unref receives the whole brush pointer, not one masked to 32 bits as an undeclared int."""
        self.assertEqual(libmypaint.mypaint_brush_unref.argtypes, [c_void_p])
        self.assertIsNone(libmypaint.mypaint_brush_unref.restype)
