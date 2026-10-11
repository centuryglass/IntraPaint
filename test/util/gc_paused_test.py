import gc

from src.util.gc_paused import gc_paused
from test.base_test_case import IntraPaintTestCase


class _Cycle:
    """An object kept alive only by a reference to itself."""

    def __init__(self) -> None:
        self.cycle = self


class GcPausedTest(IntraPaintTestCase):

    def test_disables_collection_inside_block(self):
        self.assertTrue(gc.isenabled())
        with gc_paused():
            self.assertFalse(gc.isenabled())
        self.assertTrue(gc.isenabled())

    def test_reenables_collection_after_exception(self):
        with self.assertRaises(ValueError):
            with gc_paused():
                raise ValueError()
        self.assertTrue(gc.isenabled())

    def test_leaves_disabled_collection_disabled(self):
        gc.disable()
        try:
            with gc_paused():
                self.assertFalse(gc.isenabled())
            self.assertFalse(gc.isenabled())
        finally:
            gc.enable()

    def test_collects_unreachable_cycles_before_block(self):
        gc.disable()
        try:
            _Cycle()
            with gc_paused():
                self.assertEqual([], [obj for obj in gc.get_objects() if isinstance(obj, _Cycle)])
        finally:
            gc.enable()
