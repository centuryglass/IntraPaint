"""Control panel widget for testing and debugging."""
from typing import List

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton, QWidget

from src.config.cache import Cache
from src.ui.panel.generators.generator_panel import GeneratorPanel
from src.ui.widget.rotating_toolbar_button import RotatingToolbarButton
from src.util.shared_constants import BUTTON_TEXT_GENERATE, BUTTON_TOOLTIP_GENERATE


class TestControlPanel(GeneratorPanel):
    """Control panel widget for testing and debugging."""

    generate_signal = Signal()

    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(QLabel('TODO: as needed, add items here for manual testing.'))
        self._generate_button = QPushButton()
        self._generate_button.setText('Generate')
        self._generate_button.clicked.connect(self.generate_signal.emit)
        self._generate_button.hide()
        gen_size_input = Cache().get_control_widget(Cache.GENERATION_SIZE)
        self._layout.addWidget(gen_size_input, stretch=1)
        self._mode_box = Cache().get_control_widget(Cache.EDIT_MODE)
        self._layout.addWidget(self._mode_box)
        self._layout.addWidget(self._generate_button)
        self._toolbar_generate_button = RotatingToolbarButton(BUTTON_TEXT_GENERATE)
        self._toolbar_generate_button.setToolTip(BUTTON_TOOLTIP_GENERATE)
        self._toolbar_generate_button.clicked.connect(self.generate_signal)
        self._toolbar_generate_button.setVisible(False)

    def get_tab_bar_widgets(self) -> List[QWidget]:
        """Returns the toolbar generate button as the only toolbar widget."""
        return [self._toolbar_generate_button]
