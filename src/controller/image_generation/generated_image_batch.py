"""One batch of generated image options, with the generation context needed to apply or re-open them later.

Options are applied with the batch's own mask, generation area and edit mode, so changing the selection or edit
mode after generating doesn't change what an option inserts.
"""
from typing import Optional

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage

from src.config.cache import Cache
from src.image.layers.image_stack import ImageStack
from src.util.visual.pil_image_utils import pil_image_scaling


def edit_size_image(image: QImage) -> QImage:
    """Returns `image` at `Cache.EDIT_SIZE`, the resolution generated content is applied at."""
    return pil_image_scaling(image, Cache().get(Cache.EDIT_SIZE))


def full_size_image(image: QImage) -> QImage:
    """Returns the largest version of an option: `image` itself, or `image` scaled up to `Cache.GENERATION_SIZE` when it
    is at `Cache.EDIT_SIZE`."""
    if image.size() == Cache().get(Cache.EDIT_SIZE):
        return pil_image_scaling(image, Cache().get(Cache.GENERATION_SIZE))
    return image


class GeneratedImageBatch:
    """The options from one generation, captured against the image state at the time it started.

    `option_images[0]` is the original image content, and later entries are generated options or `loading_image`
    placeholders. `edit_mode` is the untranslated value `Cache.EDIT_MODE` holds. `mask_image` is the generator's paste
    mask when one is given, and the selection mask otherwise. `change_bounds` is relative to the generation area, or
    None when the whole area changed.
    """

    def __init__(self, image_stack: ImageStack, paste_mask: Optional[QImage] = None) -> None:
        self.option_images: list[QImage] = [image_stack.qimage_generation_area_content()]
        self.generation_area = image_stack.generation_area
        self.selection_polys = image_stack.selection_layer.outline
        self.mask_image = paste_mask if paste_mask is not None else image_stack.selection_layer.mask_image
        self.edit_mode = Cache().get(Cache.EDIT_MODE)
        change_bounds = image_stack.selection_layer.get_selection_gen_area(True)
        if change_bounds is None or change_bounds == self.generation_area:
            # The whole generation area changed, so "zoom to changes" has nothing smaller to zoom to.
            self.change_bounds: Optional[QRect] = None
        else:
            # Relative to the generation area, the coordinate space of the option images:
            self.change_bounds = change_bounds.translated(-self.generation_area.x(), -self.generation_area.y())

        # The selection screen draws the loading state over this blank stand-in:
        self.loading_image = QImage(self.generation_area.size(), QImage.Format.Format_ARGB32_Premultiplied)
        self.loading_image.fill(Qt.GlobalColor.black)

    def edit_image(self, option_index: int) -> QImage:
        """Returns option `option_index` at the resolution it is applied at."""
        return edit_size_image(self.option_images[option_index])

    def full_image(self, option_index: int) -> QImage:
        """Returns option `option_index` at the largest resolution available, as saved to a file."""
        return full_size_image(self.option_images[option_index])

    def has_results(self) -> bool:
        """Returns whether at least one generated image has replaced its loading placeholder."""
        return any(image is not self.loading_image for image in self.option_images[1:])

    def discard_placeholders(self) -> list[int]:
        """Removes loading placeholders from `option_images`, returning the indices of the images that remain."""
        kept = [i for i, image in enumerate(self.option_images) if image is not self.loading_image]
        self.option_images = [self.option_images[i] for i in kept]
        return kept
