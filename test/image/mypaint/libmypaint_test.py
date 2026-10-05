"""Tests libmypaint loading: which library wins, and how the brush setting table is read from it."""
import os
from unittest.mock import patch, MagicMock

from src.config.application_config import AppConfig
from src.image.mypaint import libmypaint as libmypaint_module
from src.image.mypaint.libmypaint import load_libmypaint, BUNDLED_LIBRARY_DIR
from src.image.mypaint.mypaint_brush import MyPaintBrush
from test.base_test_case import IntraPaintTestCase


class LoadLibmypaintTest(IntraPaintTestCase):
    """load_libmypaint tries the bundled build, then the configured directory, then the system library."""

    def test_bundled_library_dir_exists(self) -> None:
        """The running platform's bundled build is checked in."""
        self.assertTrue(os.path.isdir(BUNDLED_LIBRARY_DIR), BUNDLED_LIBRARY_DIR)

    def test_bundled_library_loads_before_system_library(self) -> None:
        """A system libmypaint is never loaded when the bundled one loads."""
        with patch.object(libmypaint_module, 'find_library', return_value='libmypaint-system.so') as find_mock, \
                patch.object(libmypaint_module, 'CDLL') as system_cdll_mock:
            load_libmypaint()
        find_mock.assert_not_called()
        system_cdll_mock.assert_not_called()

    def test_falls_back_to_config_dir_then_system_library(self) -> None:
        """Each directory is tried in order, and the system library loads only when both fail."""
        AppConfig().set(AppConfig.LIBMYPAINT_LIBRARY_DIR, '/configured/libmypaint/dir')
        tried_dirs: list[str] = []

        def _fail_to_load(library_dir: str) -> None:
            tried_dirs.append(library_dir)
            raise OSError('missing')

        system_lib = MagicMock()
        with patch.object(libmypaint_module, '_load_from_dir', side_effect=_fail_to_load), \
                patch.object(libmypaint_module, 'find_library', return_value='libmypaint-system.so'), \
                patch.object(libmypaint_module, 'CDLL', return_value=system_lib) as system_cdll_mock:
            self.assertIs(load_libmypaint(), system_lib)
        self.assertEqual(tried_dirs, [BUNDLED_LIBRARY_DIR, '/configured/libmypaint/dir'])
        system_cdll_mock.assert_called_once_with('libmypaint-system.so')

    def test_error_names_every_attempt(self) -> None:
        """When nothing loads, the ImportError says what was tried."""
        AppConfig().set(AppConfig.LIBMYPAINT_LIBRARY_DIR, '/configured/libmypaint/dir')
        with patch.object(libmypaint_module, '_load_from_dir', side_effect=OSError('missing')), \
                patch.object(libmypaint_module, 'find_library', return_value=None):
            with self.assertRaises(ImportError) as context:
                load_libmypaint()
        message = str(context.exception)
        self.assertIn(BUNDLED_LIBRARY_DIR, message)
        self.assertIn('/configured/libmypaint/dir', message)
        self.assertIn('no system mypaint library found', message)


class BrushSettingTableTest(IntraPaintTestCase):
    """MyPaintBrush's setting constants come from the loaded library's own setting ids."""

    def test_setting_constants_match_library_ids(self) -> None:
        """Every loaded setting is registered under its own name, with its library id."""
        settings = MyPaintBrush._setting_info  # pylint: disable=protected-access
        self.assertEqual([setting.id for setting in settings], list(range(len(settings))))
        for setting in settings:
            self.assertEqual(getattr(MyPaintBrush, setting.cname.upper()), setting.id, setting.cname)

    def test_every_declared_setting_is_loaded(self) -> None:
        """The bundled build has every setting MyPaintBrush declares, so none are left out of the table."""
        declared = {name for name in MyPaintBrush.__annotations__ if name.isupper()}
        loaded = {setting.cname.upper() for setting in MyPaintBrush._setting_info}  # pylint: disable=protected-access
        self.assertEqual(declared, loaded)
