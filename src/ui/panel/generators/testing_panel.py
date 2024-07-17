"""Control panel widget for testing and debugging."""
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal

from src.config.application_config import AppConfig
from src.ui.widget.bordered_widget import BorderedWidget


class TestControlPanel(BorderedWidget):
    """Control panel widget for testing and debugging."""

    generate_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(QLabel('TODO: as needed, add items here for manual testing.'))
        self._generate_button = QPushButton()
        self._generate_button.setText('Generate')
        self._generate_button.clicked.connect(self.generate_signal.emit)
        gen_size_input = AppConfig().get_control_widget(AppConfig.GENERATION_SIZE)
        self._layout.addWidget(gen_size_input, stretch=1)
        self._mode_box = AppConfig().get_control_widget(AppConfig.EDIT_MODE)
        self._layout.addWidget(self._mode_box)
        self._layout.addWidget(self._generate_button)
