"""Control panel widget for testing and debugging."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton

from src.config.cache import Cache
from src.ui.layout.bordered_widget import BorderedWidget


class TestControlPanel(BorderedWidget):
    """Control panel widget for testing and debugging."""

    generate_signal = Signal()

    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(QLabel('TODO: as needed, add items here for manual testing.'))
        self._generate_button = QPushButton()
        self._generate_button.setText('Generate')
        self._generate_button.clicked.connect(self.generate_signal.emit)
        gen_size_input = Cache().get_control_widget(Cache.GENERATION_SIZE)
        self._layout.addWidget(gen_size_input, stretch=1)
        self._mode_box = Cache().get_control_widget(Cache.EDIT_MODE)
        self._layout.addWidget(self._mode_box)
        self._layout.addWidget(self._generate_button)
