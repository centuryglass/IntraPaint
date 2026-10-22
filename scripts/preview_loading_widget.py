"""Opens a window that previews the loading indicator with any of its designs.

Drop-downs choose the design and its variant from everything `load_loading_designs` finds, including new sprite
sheets added under `resources/loading/`. The Diffusion Ring's variants are its images: "(procedural)" cycles through
all of them as the app does, and a name pins that one image. The other controls set the message, the theme backdrop, play and pause, and
scrub to any phase. "Export GIF" writes one loop of the current design and options as an infinitely looping GIF at
the preview's current resolution.

Usage: python scripts/preview_loading_widget.py
"""
import os
import sys
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# pylint: disable=wrong-import-position
from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPalette, QShowEvent
from PySide6.QtWidgets import QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, \
    QSlider, QVBoxLayout, QWidget

from src.ui.loading.diffusion_ring import DiffusionRing
from src.ui.loading.loading_design import LoadingDesign
from src.ui.loading.loading_designs import load_loading_designs
from src.ui.widget.loading_widget import LoadingWidget

BACKDROPS = {'Dark': QColor('#1e2128'), 'Light': QColor('#eef0f3')}
SLIDER_STEPS = 1000
SYNC_INTERVAL_MS = 30
# One GIF frame's duration in milliseconds. A multiple of 10 keeps the loop length exact, since GIF delays are stored
# in hundredths of a second.
FRAME_MS = 30


class LoadingPreviewWindow(QWidget):
    """Shows a LoadingWidget over a plain backdrop, with controls for its design, message, theme and phase."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle('Loading indicator preview')
        self.resize(640, 720)
        self._designs = load_loading_designs()
        self._design_names = list(dict.fromkeys(design.name for design in self._designs))

        self._design_box = QComboBox()
        self._design_box.addItems(self._design_names)
        self._variant_box = QComboBox()
        self._random_button = QPushButton('Random')
        self._theme_box = QComboBox()
        self._theme_box.addItems(list(BACKDROPS))
        self._play_button = QPushButton('Pause')
        self._message_field = QLineEdit('Loading...')
        self._phase_slider = QSlider(Qt.Orientation.Horizontal)
        self._phase_slider.setRange(0, SLIDER_STEPS)
        self._export_button = QPushButton('Export GIF')

        self._backdrop = QWidget()
        self._backdrop.setAutoFillBackground(True)
        self._loading_widget = LoadingWidget(self._backdrop, self._message_field.text(), self._designs)
        backdrop_layout = QVBoxLayout(self._backdrop)
        backdrop_layout.addWidget(self._loading_widget)

        choice_row = QHBoxLayout()
        for label, widget in (('Design', self._design_box), ('Variant', self._variant_box)):
            choice_row.addWidget(QLabel(label))
            choice_row.addWidget(widget, stretch=1)
        choice_row.addWidget(self._random_button)
        control_row = QHBoxLayout()
        control_row.addWidget(QLabel('Theme'))
        control_row.addWidget(self._theme_box)
        control_row.addWidget(QLabel('Message'))
        control_row.addWidget(self._message_field, stretch=1)
        control_row.addWidget(self._play_button)
        control_row.addWidget(self._export_button)
        phase_row = QHBoxLayout()
        phase_row.addWidget(QLabel('Phase'))
        phase_row.addWidget(self._phase_slider)
        layout = QVBoxLayout(self)
        layout.addLayout(choice_row)
        layout.addLayout(control_row)
        layout.addLayout(phase_row)
        layout.addWidget(self._backdrop, stretch=1)

        self._design_box.currentTextChanged.connect(self._design_name_changed)
        self._variant_box.currentIndexChanged.connect(self._variant_changed)
        self._random_button.clicked.connect(self._random_design)
        self._theme_box.currentTextChanged.connect(self._apply_theme)
        self._play_button.clicked.connect(self._toggle_play)
        self._export_button.clicked.connect(self._export_gif)
        self._message_field.textChanged.connect(self._message_changed)
        self._phase_slider.valueChanged.connect(self._scrub)
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._sync_controls)
        self._sync_timer.start(SYNC_INTERVAL_MS)
        self._apply_theme(self._theme_box.currentText())

    def showEvent(self, event: Optional[QShowEvent]) -> None:
        """Shows the design the loading widget picked when it was shown."""
        super().showEvent(event)
        self._sync_controls()

    def _variants(self, name: str) -> list[tuple[str, LoadingDesign, Optional[int]]]:
        """Returns a (label, design, fixed image index) entry for each choice in the variant drop-down."""
        entries: list[tuple[str, LoadingDesign, Optional[int]]] = []
        for design in self._designs:
            if design.name != name:
                continue
            if isinstance(design, DiffusionRing):
                entries.append(('(procedural)', design, None))
                entries.extend((image_name, design, index) for index, image_name in enumerate(design.image_names))
            else:
                entries.append((design.variant or '(procedural)', design, None))
        return entries

    @staticmethod
    def _entry_index(entries: list[tuple[str, LoadingDesign, Optional[int]]], design: LoadingDesign) -> int:
        fixed = design.fixed_image if isinstance(design, DiffusionRing) else None
        return next(i for i, (_, entry_design, index) in enumerate(entries) if entry_design is design
                    and index == fixed)

    def _sync_controls(self) -> None:
        """Matches the drop-downs, slider and play button to the widget's current design and phase."""
        design = self._loading_widget.design
        for widget in (self._design_box, self._variant_box, self._phase_slider):
            widget.blockSignals(True)
        if self._design_box.currentText() != design.name:
            self._design_box.setCurrentText(design.name)
            self._fill_variants(design.name)
        self._variant_box.setCurrentIndex(self._entry_index(self._variants(design.name), design))
        self._phase_slider.setValue(round(self._loading_widget.phase * SLIDER_STEPS))
        for widget in (self._design_box, self._variant_box, self._phase_slider):
            widget.blockSignals(False)
        self._play_button.setText('Play' if self._loading_widget.paused else 'Pause')

    def _fill_variants(self, name: str) -> None:
        self._variant_box.clear()
        self._variant_box.addItems([label for label, _, _ in self._variants(name)])

    def _design_name_changed(self, name: str) -> None:
        self._variant_box.blockSignals(True)
        self._fill_variants(name)
        self._variant_box.blockSignals(False)
        self._select_entry(self._variants(name)[0])

    def _variant_changed(self, index: int) -> None:
        variants = self._variants(self._design_box.currentText())
        if 0 <= index < len(variants):
            self._select_entry(variants[index])

    def _select_entry(self, entry: tuple[str, LoadingDesign, Optional[int]]) -> None:
        """Shows a drop-down entry, pinning a Diffusion Ring image when the entry names one."""
        _, design, fixed_image = entry
        if isinstance(design, DiffusionRing):
            design.fixed_image = fixed_image
        self._loading_widget.design = design

    def _random_design(self) -> None:
        self._loading_widget.start_new_design()
        self._sync_controls()

    def _apply_theme(self, theme: str) -> None:
        palette = self._backdrop.palette()
        palette.setColor(QPalette.ColorRole.Window, BACKDROPS[theme])
        self._backdrop.setPalette(palette)

    def _toggle_play(self) -> None:
        if self._loading_widget.paused:
            # Unpausing starts a new load with a random design, so restore the chosen one afterward.
            design = self._loading_widget.design
            self._loading_widget.paused = False
            self._loading_widget.design = design
        else:
            self._loading_widget.paused = True
        self._sync_controls()

    def _message_changed(self, message: str) -> None:
        paused = self._loading_widget.paused
        phase = self._loading_widget.phase
        design = self._loading_widget.design
        self._loading_widget.message = message
        self._loading_widget.design = design
        if paused:
            self._loading_widget.paused = True
            self._loading_widget.phase = phase

    def _scrub(self, value: int) -> None:
        self._loading_widget.paused = True
        self._loading_widget.phase = value / SLIDER_STEPS
        self._sync_controls()

    def _export_gif(self) -> None:
        """Writes one loop of the current design as an infinitely looping GIF at the preview's current resolution."""
        if self._loading_widget.width() <= 0 or self._loading_widget.height() <= 0:
            return
        design = self._loading_widget.design
        parts = [design.name, design.variant] if design.variant else [design.name]
        suggested_name = '_'.join(part.replace(' ', '_') for part in parts) + '.gif'
        path, _ = QFileDialog.getSaveFileName(self, 'Export GIF', suggested_name, 'GIF images (*.gif)')
        if not path:
            return
        if not path.lower().endswith('.gif'):
            path += '.gif'
        frame_count = max(1, round(design.duration_ms / FRAME_MS))
        saved_phase = self._loading_widget.phase
        saved_paused = self._loading_widget.paused
        try:
            frames = []
            for index in range(frame_count):
                self._loading_widget.phase = index / frame_count
                frame = self._backdrop.grab().toImage().convertToFormat(QImage.Format.Format_RGB888)
                pil_frame = Image.frombytes('RGB', (frame.width(), frame.height()), bytes(frame.bits()))
                frames.append(pil_frame)
            frames[0].save(path, save_all=True, append_images=frames[1:], duration=FRAME_MS, loop=0)
            print(f'Saved {path}')
        finally:
            self._loading_widget.paused = saved_paused
            self._loading_widget.phase = saved_phase


def main() -> None:
    """Opens the preview window."""
    app = QApplication.instance() or QApplication(sys.argv)
    window = LoadingPreviewWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
