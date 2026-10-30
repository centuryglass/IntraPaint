"""Checks each dock panel, and the Tools panel with each tool active, at every sweep size it can be docked at.

A scene is captured at each `SWEEP_WIDTHS` by `SWEEP_HEIGHTS` size in each of its orientations, skipping sizes below its
minimum size hint. Every problem `find_layout_problems` or `find_arrangement_problems` reports there counts, by kind
(the text before the colon), except `HINT_KINDS`.

`KNOWN_PROBLEMS` lists the kinds each scene is known to have and the open issue that tracks each. A scene fails when it
shows a kind it doesn't list, or when a listed kind no longer appears, so a fix removes its entry. Run
`scripts/capture_ui.py --sheet --only <scene>` to see where each kind appears.

Each scene in `SWEEP_SCENE_NAMES` is its own test, so no test runs long enough to reach `faulthandler_timeout` in
pytest.ini.
"""
import sys

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from test.base_test_case import IntraPaintTestCase
from test.ui.panel_capture import (SWEEP_HEIGHTS, SWEEP_WIDTHS, PanelHost, PanelScene, find_arrangement_problems,
                                   find_layout_problems, is_hint, mock_app_controller, panel_scenes, tools_panel_scenes)

app = QApplication.instance() or QApplication(sys.argv)

ISSUES = 'https://github.com/centuryglass/IntraPaint/issues/'

_OVERLAP_CLIPPED_SQUEEZED = ('overlap', 'clipped', 'squeezed')


def _each(kinds: tuple[str, ...], *issues: int) -> dict[str, tuple[int, ...]]:
    return {kind: issues for kind in kinds}


# Scene name -> {problem kind: the open issues that track it}:
KNOWN_PROBLEMS: dict[str, dict[str, tuple[int, ...]]] = {
    'tools_panel_fill_tool': _each(('clipped', 'squeezed'), 426),
}


def sweep_scenes(controller) -> list[PanelScene]:
    """Returns the scenes to sweep: every panel scene without fixed sizes, and every Tools panel scene.

    Standalone tool control scenes and the plain Tools panel scene are left out, since a Tools panel scene shows the
    same controls where users see them.
    """
    return [scene for scene in panel_scenes(controller)
            if scene.fixed_sizes is None and not scene.name.endswith('_controls') and scene.name != 'tool_panel'] \
        + tools_panel_scenes(controller)


# Every sweep scene's name, in `sweep_scenes` order. Test names come from this list, since building the scenes needs an
# AppController. `test_scene_names_match_sweep_scenes` fails when a panel or tool is added or removed without updating it.
SWEEP_SCENE_NAMES = (
    'layer_panel',
    'color_panel',
    'navigation_panel',
    'sd_webui_panel',
    'sd_comfyui_panel',
    'glid_panel',
    'test_generator_panel',
    'controlnet_webui_panel',
    'controlnet_comfyui_panel',
    'tools_panel_my_paint_brush_tool',
    'tools_panel_draw_tool',
    'tools_panel_eraser_tool',
    'tools_panel_fill_tool',
    'tools_panel_filter_tool',
    'tools_panel_smudge_tool',
    'tools_panel_clone_stamp_tool',
    'tools_panel_eyedropper_tool',
    'tools_panel_text_tool',
    'tools_panel_shape_tool',
    'tools_panel_layer_transform_tool',
    'tools_panel_free_selection_tool',
    'tools_panel_selection_brush_tool',
    'tools_panel_shape_selection_tool',
    'tools_panel_magic_wand_tool',
    'tools_panel_generation_area_tool',
)


class PanelSweepTest(IntraPaintTestCase):
    """Sweeps every panel of a mock-mode AppController across the sweep grid, one scene per test.

    `_add_scene_tests` adds a `test_<scene name>` method for each of `SWEEP_SCENE_NAMES`.
    """

    def setUp(self) -> None:
        super().setUp()
        self.controller = mock_app_controller()

    def test_scene_names_match_sweep_scenes(self) -> None:
        """SWEEP_SCENE_NAMES lists every sweep scene, in order."""
        self.assertEqual(SWEEP_SCENE_NAMES, tuple(scene.name for scene in sweep_scenes(self.controller)),
                         'update SWEEP_SCENE_NAMES to match sweep_scenes')

    def check_scene(self, scene_name: str) -> None:
        """Asserts that a sweep scene shows exactly the problem kinds KNOWN_PROBLEMS lists for it."""
        scene = next(scene for scene in sweep_scenes(self.controller) if scene.name == scene_name)
        panel = scene.build(self.controller)
        self.assertIsNotNone(panel, f'{scene_name} built no panel')
        assert panel is not None
        with scene.context():
            examples: dict[str, str] = {}
            host = PanelHost(panel)
            try:
                for orientation in scene.orientations(panel):
                    for height in SWEEP_HEIGHTS:
                        for width in SWEEP_WIDTHS:
                            host.capture(QSize(width, height), orientation)
                            minimum = panel.minimumSizeHint()
                            if width < minimum.width() or height < minimum.height():
                                continue
                            for problem in find_layout_problems(panel) + find_arrangement_problems(panel):
                                if is_hint(problem):
                                    continue
                                place = orientation.value if orientation is not None else 'undocked'
                                where = f'{place} {width}x{height}'
                                examples.setdefault(problem.split(':', 1)[0], f'{where}: {problem}')
            finally:
                host.release()
        known = KNOWN_PROBLEMS.get(scene_name, {})
        new = {kind: example for kind, example in examples.items() if kind not in known}
        fixed = {kind: [f'{ISSUES}{issue}' for issue in issues] for kind, issues in known.items()
                 if kind not in examples}
        self.assertEqual({}, new, f'{scene_name} has problems KNOWN_PROBLEMS does not list')
        self.assertEqual({}, fixed, f'{scene_name} no longer has these problems: remove them from KNOWN_PROBLEMS')


def _add_scene_tests() -> None:
    for scene_name in SWEEP_SCENE_NAMES:
        def test(self: PanelSweepTest, name: str = scene_name) -> None:
            self.check_scene(name)
        test.__name__ = f'test_{scene_name}'
        test.__doc__ = f'{scene_name} shows exactly the problem kinds KNOWN_PROBLEMS lists for it.'
        setattr(PanelSweepTest, test.__name__, test)


_add_scene_tests()
