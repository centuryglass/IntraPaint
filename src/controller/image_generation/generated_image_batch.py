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


def generation_area_size_image(image: QImage) -> QImage:
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

    `option_images` holds the reference images first, then the generated options or `loading_image` placeholders
    from `first_generated_index` on. Index 0 is the no-op choice: the original content on a fresh batch, and the
    canvas content at the time of re-opening on a re-opened one (`set_current_image`). A re-opened batch keeps the
    generation-time content as `original_image`, at index 1, and choosing it writes it back like a generated option.
    Like generated options, the original is a composite of the visible layers, so choosing it bakes other visible
    layers' content inside the area into the target layer. `edit_mode` is the untranslated value `Cache.EDIT_MODE` holds. `mask_image` is the generator's paste
    mask when one is given, and the selection mask otherwise. `change_bounds` is relative to the generation area, or
    None when the whole area changed.
    """

    def __init__(self, image_stack: ImageStack, paste_mask: Optional[QImage] = None) -> None:
        self.option_images: list[QImage] = [image_stack.qimage_generation_area_content()]
        self._has_current_image = False
        # Inpainting results as patches over the image sent to the backend, by option index. See `make_result_patch`:
        self.patches: dict[int, QImage] = {}
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

    @property
    def original_image(self) -> QImage:
        """The content of the generation area when the batch started."""
        return self.option_images[self.reference_count - 1]

    @property
    def current_image(self) -> Optional[QImage]:
        """The canvas content captured when the batch was re-opened, or None on a fresh batch."""
        return self.option_images[0] if self._has_current_image else None

    @property
    def reference_count(self) -> int:
        """The number of leading entries of `option_images` that are not generated options."""
        return 2 if self._has_current_image else 1

    @property
    def first_generated_index(self) -> int:
        """The index in `option_images` of the first generated option or placeholder."""
        return self.reference_count

    def set_current_image(self, image: Optional[QImage]) -> None:
        """Sets the canvas content offered as the no-op choice, replacing any earlier one.

        The original stays put. None, or an image equal to the original, leaves the batch without a current-content
        entry. Indices of generated options, and their patches, shift with the entry.
        """
        if image is not None and image == self.original_image:
            image = None
        if image is None:
            if self._has_current_image:
                del self.option_images[0]
                self._has_current_image = False
                self.patches = {i - 1: patch for i, patch in self.patches.items()}
        elif self._has_current_image:
            self.option_images[0] = image
        else:
            self.option_images.insert(0, image)
            self._has_current_image = True
            self.patches = {i + 1: patch for i, patch in self.patches.items()}

    def edit_image(self, option_index: int) -> QImage:
        """Returns what applying option `option_index` draws, at the resolution it is applied at: the option's patch
        if it has one, and the option image otherwise."""
        patch = self.patches.get(option_index)
        if patch is not None:
            return generation_area_size_image(patch)
        return generation_area_size_image(self.option_images[option_index])

    def full_image(self, option_index: int) -> QImage:
        """Returns option `option_index` at the largest resolution available, as saved to a file."""
        return full_size_image(self.option_images[option_index])

    def has_results(self) -> bool:
        """Returns whether at least one generated image has replaced its loading placeholder."""
        return any(image is not self.loading_image for image in self.option_images[self.first_generated_index:])

    def discard_placeholders(self) -> list[int]:
        """Removes loading placeholders from `option_images`, returning the indices of the images that remain."""
        kept = [i for i, image in enumerate(self.option_images)
                if i < self.reference_count or image is not self.loading_image]
        self.option_images = [self.option_images[i] for i in kept]
        self.patches = {new: self.patches[old] for new, old in enumerate(kept) if old in self.patches}
        return kept
