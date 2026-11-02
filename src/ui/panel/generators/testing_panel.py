"""Control panel for the test generator (`--mode mock`), which exists for developers and for mock-mode captures.

It holds the edit mode selector and the generation resolution, so the generation panel's kit pieces can be exercised
without a Stable Diffusion backend.
"""
from typing import Optional

from PySide6.QtWidgets import QApplication, QSizePolicy

from src.config.application_config import AppConfig
from src.config.cache import Cache
from src.ui.input_fields.segmented_control import Segment, SegmentedControl
from src.ui.input_fields.size_field import SizeField
from src.ui.layout.dock_panel import PanelLayout
from src.ui.layout.label_column_layout import normalize_row_label
from src.ui.layout.panel_fit import FIELD_MAX_WIDTH, REQUIRED
from src.ui.panel.generators.generator_panel import GenerateFooterPanel
from src.ui.panel.generators.stable_diffusion_panel import HonestSizeHints, LabeledRows
from src.util.shared_constants import EDIT_MODE_IMG2IMG, EDIT_MODE_INPAINT, EDIT_MODE_TXT2IMG
from src.ui.input_fields.field_factory import create_control_widget

# The `QCoreApplication.translate` context for strings in this file
TR_ID = 'ui.panel.generators.testing_panel'


def _tr(key: str, disambiguation: Optional[str] = None, n: int = -1) -> str:
    """Helper to make `QCoreApplication.translate` more concise."""
    return QApplication.translate(TR_ID, key, disambiguation, n)


PANEL_TITLE = _tr('Test generator')
BACKEND_DESCRIPTION = _tr('--mode mock')

SEGMENT_INPAINT = _tr('Inpaint')
SEGMENT_IMG2IMG = _tr('Img2img')
SEGMENT_TXT2IMG = _tr('Txt2img')


# `build` runs in the `DockPanel` constructor, so the controls it creates are attributes defined outside `__init__`:
# pylint: disable=attribute-defined-outside-init
class TestControlPanel(GenerateFooterPanel):
    """Control panel widget for testing and debugging."""

    __test__ = False  # Not a pytest class, despite the name.

    def __init__(self) -> None:
        super().__init__(PANEL_TITLE)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.header.set_description(BACKEND_DESCRIPTION)
        self.header.reset_button.hide()

    def build(self, ui: PanelLayout) -> None:
        """Declares the edit mode and resolution controls."""
        cache = Cache()
        section = ui.section(PANEL_TITLE)
        section.widget.set_header_visible(False)
        self._edit_mode_control = SegmentedControl([Segment(EDIT_MODE_INPAINT, SEGMENT_INPAINT),
                                                    Segment(EDIT_MODE_IMG2IMG, SEGMENT_IMG2IMG),
                                                    Segment(EDIT_MODE_TXT2IMG, SEGMENT_TXT2IMG)],
                                                   combo_fallback=True)
        self._edit_mode_control.setToolTip(cache.get_tooltip(Cache.EDIT_MODE))
        self._edit_mode_control.set_value(cache.get(Cache.EDIT_MODE))
        self._edit_mode_control.valueChanged.connect(lambda mode: cache.set(Cache.EDIT_MODE, mode))
        cache.connect(self._edit_mode_control, Cache.EDIT_MODE,
                      lambda mode, *_: self._edit_mode_control.set_value(mode))
        section.add(self._edit_mode_control, REQUIRED)

        self._gen_resolution_input = create_control_widget(cache, Cache.GENERATION_SIZE)
        if isinstance(self._gen_resolution_input, SizeField):
            self._gen_resolution_input.maximum = AppConfig().get(AppConfig.MAX_IMAGE_SIZE).expandedTo(
                self._gen_resolution_input.value())
        holder = HonestSizeHints(self._gen_resolution_input)
        holder.setMaximumWidth(FIELD_MAX_WIDTH)
        section.add(LabeledRows([(normalize_row_label(cache.get_label(Cache.GENERATION_SIZE)), holder)]), REQUIRED)
