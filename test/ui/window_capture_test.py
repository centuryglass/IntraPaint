"""Checks that every secondary window scene in `test/ui/window_capture.py` builds and renders at each of its sizes, so
`scripts/capture_ui.py --windows` keeps working as the windows change."""
import sys

from PySide6.QtWidgets import QApplication

from test.base_test_case import IntraPaintTestCase
from test.ui.panel_capture import mock_app_controller
from test.ui.window_capture import capture_window, release_window, window_scenes

app = QApplication.instance() or QApplication(sys.argv)


class WindowCaptureTest(IntraPaintTestCase):
    """Builds and renders every window scene for a mock-mode AppController."""

    def setUp(self) -> None:
        super().setUp()
        self.controller = mock_app_controller()

    def test_every_window_scene_renders(self) -> None:
        """Each scene builds a window that renders a non-empty image at every size it lists."""
        scenes = window_scenes(self.controller)
        self.assertGreater(len(scenes), 0)
        for scene in scenes:
            with self.subTest(window=scene.name), scene.context():
                window = scene.build(self.controller)
                try:
                    for size_name, size in scene.sizes(window).items():
                        image = capture_window(window, size)
                        self.assertFalse(image.isNull(), size_name)
                        self.assertGreater(image.width(), 0, size_name)
                finally:
                    release_window(window)
