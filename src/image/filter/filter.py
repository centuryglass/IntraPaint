"""Generic interface for image filtering functions. Handles the process of opening modal windows to apply the filter
and provides the information needed to add the function as a menu action."""
from typing import Callable, List

from PyQt5.QtGui import QImage

from src.image.layer_stack import LayerStack
from src.ui.modal.image_filter_modal import ImageFilterModal
from src.util.parameter import Parameter


class ImageFilter:
    """Interface for image filtering functions exposed through a modal UI."""

    def get_filter_modal(self, layer_stack: LayerStack) -> ImageFilterModal:
        """Creates and returns a modal widget that can apply the filter to the edited image."""
        return ImageFilterModal(self.get_modal_title(),
                                self.get_modal_description(),
                                self.get_parameters(),
                                self.get_filter(),
                                layer_stack)

    def get_modal_title(self) -> str:
        """Return the modal's title string."""
        raise NotImplementedError()

    def get_modal_description(self) -> str:
        """Returns the modal's description string."""
        raise NotImplementedError()

    def get_config_key(self) -> str:
        """Returns the KeyConfig key used to load menu item info and keybindings."""
        raise NotImplementedError()

    def get_filter(self) -> Callable[[...], QImage]:
        """Returns the filter's image variable filtering function."""
        raise NotImplementedError()

    def get_parameters(self) -> List[Parameter]:
        """Returns definitions for the non-image parameters passed to the filtering function."""
        return []