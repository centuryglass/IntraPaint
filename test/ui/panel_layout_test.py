"""Pins each panel's layout problems at extreme sizes, so a change that adds or fixes one shows up in a snapshot diff.

Each snapshot in `test/resources/layout_snapshots/` lists, for every size a panel is captured at, the size and the
problems `find_layout_problems` reports. Run `scripts/capture_ui.py` to see the captures the snapshots describe.
"""
import sys

from PySide6.QtWidgets import QApplication

from test.base_test_case import IntraPaintTestCase
from test.ui.ui_capture import PanelHost, find_layout_problems, layout_report, mock_app_controller, panel_scenes

app = QApplication.instance() or QApplication(sys.argv)

SNAPSHOT_DIR = 'test/resources/layout_snapshots'


class PanelLayoutTest(IntraPaintTestCase):
    """Captures every panel of a mock-mode AppController at each of its sizes."""

    def setUp(self) -> None:
        super().setUp()
        self.controller = mock_app_controller()

    def test_panel_layouts_match_snapshots(self) -> None:
        """Each panel's sizes and layout problems match its snapshot."""
        for scene in panel_scenes(self.controller):
            panel = scene.build(self.controller)
            if panel is None:
                continue
            with self.subTest(panel=scene.name), scene.context():
                host = PanelHost(panel)
                try:
                    captures = {}
                    for size_case, size in scene.sizes(panel).items():
                        host.capture(size)
                        captures[size_case] = layout_report(size, find_layout_problems(panel))
                finally:
                    host.release()
                self.assert_json_matches_snapshot(captures, f'{SNAPSHOT_DIR}/{scene.name}.json')
