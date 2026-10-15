"""Tests loading design discovery, the random pick, and each design's frames."""
import json
import os
import random
import sys
import tempfile

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtWidgets import QApplication

from src.ui.loading.diffusion_ring import DiffusionRing, signal_level
from src.ui.loading.halftone_press import HalftonePress
from src.ui.loading.loading_design import LoadingDesign
from src.ui.loading.loading_designs import load_loading_designs, pick_design, DEFAULT_SPRITE_DURATION_MS
from src.ui.loading.sprite_sheet_design import SpriteSheetDesign
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)

GOLDEN_DIR = 'test/resources/test_images/loading'
GOLDEN_SIZE = 144
GOLDEN_PHASE = 0.3


def save_image(path: str, width: int, height: int, color: QColor | Qt.GlobalColor = Qt.GlobalColor.red) -> None:
    """Saves a solid image, creating its folder."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(color)
    assert image.save(path)


def save_json(path: str, data: object) -> None:
    """Saves data as a JSON file."""
    with open(path, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file)


def render_design(design: LoadingDesign, phase: float, dark: bool) -> QImage:
    """Renders one design frame on a transparent GOLDEN_SIZE square."""
    image = QImage(GOLDEN_SIZE, GOLDEN_SIZE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    design.paint(painter, design.fit(QRectF(image.rect())), phase, dark)
    painter.end()
    return image


class LoadDesignsTest(IntraPaintTestCase):
    """Tests finding designs and their variants on disk."""

    def setUp(self) -> None:
        super().setUp()
        self._temp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.resource_dir = self._temp_dir.name

    def tearDown(self) -> None:
        self._temp_dir.cleanup()
        super().tearDown()

    def test_shipped_designs(self) -> None:
        """The committed resources load as the starting variants, after the procedural design."""
        designs = load_loading_designs()
        self.assertEqual([design.label for design in designs],
                         ['Halftone Press', 'Diffusion Ring: color_wheel', 'Pixel Orbit: ember'])
        pixel_orbit = designs[2]
        assert isinstance(pixel_orbit, SpriteSheetDesign)
        self.assertEqual(pixel_orbit.frame_count, 32)

    def test_missing_folder_leaves_procedural_designs(self) -> None:
        """Without the resource folder, the procedural designs are still available."""
        with self.assertLogs('src.ui.loading.loading_designs', 'WARNING'):
            designs = load_loading_designs(os.path.join(self.resource_dir, 'missing'))
        self.assertEqual([design.label for design in designs], ['Halftone Press'])

    def test_sprite_sheet_defaults(self) -> None:
        """A sheet without options plays every 72px cell, with the default duration."""
        save_image(os.path.join(self.resource_dir, 'pixel_orbit', 'flame.png'), 216, 144)
        design = load_loading_designs(self.resource_dir)[1]
        assert isinstance(design, SpriteSheetDesign)
        self.assertEqual((design.name, design.variant), ('Pixel Orbit', 'flame'))
        self.assertEqual(design.frame_count, 6)
        self.assertEqual(design.duration_ms, DEFAULT_SPRITE_DURATION_MS)
        self.assertEqual(design.native_size, 72)

    def test_new_folder_is_new_sprite_sheet_design(self) -> None:
        """Any folder other than diffusion_ring is a sprite-sheet design named after the folder, and a sidecar file
        overrides the defaults."""
        sheet_path = os.path.join(self.resource_dir, 'paint_drip', 'v1.png')
        save_image(sheet_path, 96, 64)
        save_json(sheet_path.replace('.png', '.json'), {'frame_size': 32, 'frame_count': 5, 'duration_ms': 1000})
        design = load_loading_designs(self.resource_dir)[1]
        assert isinstance(design, SpriteSheetDesign)
        self.assertEqual(design.label, 'Paint Drip: v1')
        self.assertEqual((design.frame_count, design.duration_ms, design.native_size), (5, 1000, 32))

    def test_diffusion_ring_variants(self) -> None:
        """Each image in diffusion_ring is a clean ring variant, with an optional duration."""
        ring_path = os.path.join(self.resource_dir, 'diffusion_ring', 'small.png')
        save_image(ring_path, 36, 36)
        save_json(ring_path.replace('.png', '.json'), {'duration_ms': 3000})
        design = load_loading_designs(self.resource_dir)[1]
        assert isinstance(design, DiffusionRing)
        self.assertEqual((design.variant, design.duration_ms, design.native_size), ('small', 3000, 36))

    def test_invalid_files_are_skipped(self) -> None:
        """Files that can't be used are logged and skipped, and other files in the folder are ignored."""
        save_image(os.path.join(self.resource_dir, 'pixel_orbit', 'uneven.png'), 100, 72)
        save_image(os.path.join(self.resource_dir, 'diffusion_ring', 'wide.png'), 72, 36)
        bad_option_path = os.path.join(self.resource_dir, 'pixel_orbit', 'bad_option.png')
        save_image(bad_option_path, 72, 72)
        save_json(bad_option_path.replace('.png', '.json'), {'frame_size': 'large'})
        too_many_path = os.path.join(self.resource_dir, 'pixel_orbit', 'too_many.png')
        save_image(too_many_path, 72, 72)
        save_json(too_many_path.replace('.png', '.json'), {'frame_count': 2})
        with open(os.path.join(self.resource_dir, 'pixel_orbit', 'notes.txt'), 'w', encoding='utf-8') as notes:
            notes.write('not an image')
        with self.assertLogs('src.ui.loading.loading_designs', 'WARNING') as logs:
            designs = load_loading_designs(self.resource_dir)
        self.assertEqual([design.label for design in designs], ['Halftone Press'])
        self.assertEqual(len(logs.records), 4)


class PickDesignTest(IntraPaintTestCase):
    """Tests the random pick."""

    def test_never_repeats(self) -> None:
        """With more than one design, no design is picked twice in a row, and every design gets picked."""
        designs = [HalftonePress() for _ in range(3)]
        rng = random.Random(1)
        previous = None
        picked = set()
        for _ in range(300):
            design = pick_design(designs, previous, rng)
            self.assertIsNot(design, previous)
            picked.add(id(design))
            previous = design
        self.assertEqual(len(picked), 3)

    def test_single_design_repeats(self) -> None:
        """With one design, it is picked every time."""
        design = HalftonePress()
        self.assertIs(pick_design([design], design), design)

    def test_no_designs(self) -> None:
        """Picking from nothing raises."""
        with self.assertRaises(ValueError):
            pick_design([], None)


class DesignFrameTest(IntraPaintTestCase):
    """Tests the shipped designs' frames and sizing."""

    def setUp(self) -> None:
        super().setUp()
        self.designs = {design.name: design for design in load_loading_designs()}

    def test_fit_scales_bitmaps_by_whole_numbers(self) -> None:
        """Bitmap designs fit at a whole multiple of their native size, on whole pixels."""
        pixel_orbit = self.designs['Pixel Orbit']
        self.assertEqual(pixel_orbit.fit(QRectF(0.5, 0, 250, 300)), QRectF(18, 42, 216, 216))
        self.assertEqual(pixel_orbit.fit(QRectF(0, 0, 50, 50)), QRectF(0, 0, 50, 50))
        self.assertEqual(self.designs['Halftone Press'].fit(QRectF(0, 0, 250, 300)), QRectF(0, 25, 250, 250))

    def test_sprite_frame_index(self) -> None:
        """Phase maps evenly onto frames, read along rows."""
        pixel_orbit = self.designs['Pixel Orbit']
        assert isinstance(pixel_orbit, SpriteSheetDesign)
        self.assertEqual(pixel_orbit.frame_index(0.0), 0)
        self.assertEqual(pixel_orbit.frame_index(9 / 32), 9)
        self.assertEqual(pixel_orbit.frame_index(0.9999), 31)
        self.assertEqual(pixel_orbit.frame_index(1.0), 0)
        self.assertEqual(pixel_orbit.frame_rect(9), QRect(72, 72, 72, 72))

    def test_diffusion_ring_rests_on_clean_image(self) -> None:
        """At the rest phase, the frame is the clean image. At phase 0, it is noise inside the ring's alpha."""
        ring = self.designs['Diffusion Ring']
        assert isinstance(ring, DiffusionRing)
        self.assertEqual(signal_level(0.0), 0.0)
        self.assertEqual(signal_level(ring.rest_phase), 1.0)
        clean = QImage('resources/loading/diffusion_ring/color_wheel.png').convertToFormat(QImage.Format.Format_ARGB32)
        self.assert_images_equal(ring.frame(ring.rest_phase), clean)
        noisy = ring.frame(0.0)
        self.assertNotEqual(noisy, clean)
        for x, y in ((0, 0), (36, 36), (36, 2)):
            self.assertEqual(noisy.pixelColor(x, y).alpha() == 0, clean.pixelColor(x, y).alpha() == 0)

    def test_design_goldens(self) -> None:
        """Each shipped design draws the same frame as its golden image, on both themes when it depends on them."""
        cases = (('Halftone Press', 'halftone_press', (True, False)),
                 ('Diffusion Ring', 'diffusion_ring', (True,)),
                 ('Pixel Orbit', 'pixel_orbit', (True,)))
        for name, file_name, themes in cases:
            for dark in themes:
                with self.subTest(design=name, dark=dark):
                    theme_suffix = ('_dark' if dark else '_light') if len(themes) > 1 else ''
                    self.assert_image_matches_golden(render_design(self.designs[name], GOLDEN_PHASE, dark),
                                                     f'{GOLDEN_DIR}/{file_name}{theme_suffix}.png')
