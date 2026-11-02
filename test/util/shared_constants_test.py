"""Test that the startup-time constants module stays free of translated strings."""
import subprocess
import sys

from test.base_test_case import IntraPaintTestCase

_SCRIPT = '''
import sys
import src.util.shared_constants
print(','.join(sorted(m for m, v in sys.modules.items()
                      if m.startswith('src') and m != 'src.util.translation' and hasattr(v, 'TR_ID'))))
'''


class TestSharedConstants(IntraPaintTestCase):
    """Test that the startup-time constants module stays free of translated strings."""

    def test_import_loads_no_translated_modules(self) -> None:
        """`IntraPaint.py` imports shared_constants before the translator is installed, so it can't load a module
        that calls `_tr` at import time."""
        result = subprocess.run([sys.executable, '-c', _SCRIPT], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), '')
