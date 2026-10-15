"""Finds every available loading design, and picks one at random for each load.

Asset-backed variants are found by scanning `LOADING_RESOURCE_DIR`, so adding a variant means adding a file there.
`resources/loading/README.md` describes the folder layout and file formats.
"""
import json
import logging
import os
import random
from functools import cache
from typing import Optional, Any

from PySide6.QtGui import QImage

from src.ui.loading.diffusion_ring import DiffusionRing, DEFAULT_DURATION_MS as DIFFUSION_DURATION_MS
from src.ui.loading.halftone_press import HalftonePress
from src.ui.loading.loading_design import LoadingDesign
from src.ui.loading.sprite_sheet_design import SpriteSheetDesign
from src.util.shared_constants import PROJECT_DIR

logger = logging.getLogger(__name__)

LOADING_RESOURCE_DIR = f'{PROJECT_DIR}/resources/loading'
DIFFUSION_RING_DIR = 'diffusion_ring'
DEFAULT_FRAME_SIZE = 72
DEFAULT_SPRITE_DURATION_MS = 2400

KEY_FRAME_SIZE = 'frame_size'
KEY_FRAME_COUNT = 'frame_count'
KEY_DURATION_MS = 'duration_ms'


def _read_options(image_path: str) -> dict[str, Any]:
    """Returns the options in an image's optional JSON sidecar file, or an empty dict when there is none."""
    json_path = f'{os.path.splitext(image_path)[0]}.json'
    if not os.path.isfile(json_path):
        return {}
    with open(json_path, encoding='utf-8') as json_file:
        options = json.load(json_file)
    if not isinstance(options, dict):
        raise ValueError(f'{json_path} must hold a JSON object')
    return options


def _int_option(options: dict[str, Any], key: str, default: Optional[int]) -> Optional[int]:
    value = options.get(key, default)
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
        raise ValueError(f'"{key}" must be a positive integer, got {value!r}')
    return value


def _load_design(folder_name: str, image_path: str) -> LoadingDesign:
    """Loads one asset-backed design variant, raising ValueError if the file or its options are invalid."""
    image = QImage(image_path)
    if image.isNull():
        raise ValueError('not a readable image')
    options = _read_options(image_path)
    variant = os.path.splitext(os.path.basename(image_path))[0]
    if folder_name == DIFFUSION_RING_DIR:
        duration_ms = _int_option(options, KEY_DURATION_MS, DIFFUSION_DURATION_MS)
        assert duration_ms is not None
        return DiffusionRing(image, variant, duration_ms)
    frame_size = _int_option(options, KEY_FRAME_SIZE, DEFAULT_FRAME_SIZE)
    duration_ms = _int_option(options, KEY_DURATION_MS, DEFAULT_SPRITE_DURATION_MS)
    assert frame_size is not None and duration_ms is not None
    name = folder_name.replace('_', ' ').title()
    return SpriteSheetDesign(name, variant, image, frame_size, _int_option(options, KEY_FRAME_COUNT, None),
                             duration_ms)


def load_loading_designs(resource_dir: str = LOADING_RESOURCE_DIR) -> list[LoadingDesign]:
    """Returns the procedural designs, then one design for each valid asset under resource_dir.

    Each subfolder of resource_dir is one design and each PNG in it is one variant. Invalid files are logged and
    skipped.
    """
    designs: list[LoadingDesign] = [HalftonePress()]
    if not os.path.isdir(resource_dir):
        logger.warning(f'Loading design folder {resource_dir} not found, using procedural designs only')
        return designs
    for folder_name in sorted(os.listdir(resource_dir)):
        folder_path = os.path.join(resource_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        for file_name in sorted(os.listdir(folder_path)):
            if not file_name.lower().endswith('.png'):
                continue
            image_path = os.path.join(folder_path, file_name)
            try:
                designs.append(_load_design(folder_name, image_path))
            except (ValueError, OSError) as err:
                logger.warning(f'Skipping loading design {image_path}: {err}')
    return designs


@cache
def default_loading_designs() -> tuple[LoadingDesign, ...]:
    """Returns the designs under LOADING_RESOURCE_DIR, loaded once per run."""
    return tuple(load_loading_designs())


def pick_design(designs: list[LoadingDesign] | tuple[LoadingDesign, ...], previous: Optional[LoadingDesign],
                rng: Optional[random.Random] = None) -> LoadingDesign:
    """Returns a random design other than previous, unless previous is the only design."""
    if len(designs) == 0:
        raise ValueError('No loading designs to pick from')
    options = [design for design in designs if design is not previous] or list(designs)
    return rng.choice(options) if rng is not None else random.choice(options)
