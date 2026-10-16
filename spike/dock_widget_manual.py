"""Interactive companion to dock_widget_spike.py for #55: a window to poke at by hand.

Run: python spike/dock_widget_manual.py
The window stays open until closed. Every dock event is printed in the log panel on the right.

Things to try:
  1. Drag each "title bar" variant (right area, upper group) out into the canvas and back. "bare widget" is
     expected to fail if the synthetic-event result holds with a real mouse.
  2. Drag the tabs of the "tabs" group apart and together; check the North tab bar and icons.
  3. Float a dock, then dock it into each zone. Try dropping on the bottom area to see whether two rows form.
  4. Save state, rearrange, Restore state. Then "Add late dock", Restore state again.
  5. Shrink the window below 1024x600 and Restore state with a layout saved while the window was large.
  6. On Windows and Linux, check focus, stacking and re-docking of floating docks.
"""
import sys

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import (QApplication, QDockWidget, QHBoxLayout, QLabel, QMainWindow, QPlainTextEdit,
                               QPushButton, QStyle, QTabWidget, QVBoxLayout, QWidget)

STATE_VERSION = 1
AREAS = {'Top': Qt.DockWidgetArea.TopDockWidgetArea, 'Left': Qt.DockWidgetArea.LeftDockWidgetArea,
         'Right': Qt.DockWidgetArea.RightDockWidgetArea, 'Bottom': Qt.DockWidgetArea.BottomDockWidgetArea}


class SpikeWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName('main')
        self.setDockNestingEnabled(True)
        self.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)
        for corner, area in ((Qt.Corner.TopLeftCorner, 'Top'), (Qt.Corner.TopRightCorner, 'Top'),
                             (Qt.Corner.BottomLeftCorner, 'Bottom'), (Qt.Corner.BottomRightCorner, 'Bottom')):
            self.setCorner(corner, AREAS[area])
        self.resize(1200, 800)
        self._saved: QByteArray | None = None
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.setCentralWidget(self._build_central())
        self._late_count = 0
        self._build_docks()

    def _build_central(self) -> QWidget:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel('Canvas stand-in. Drag docks around me.'))
        row = QHBoxLayout()
        for text, handler in (('Save state', self._save), ('Restore state', self._restore),
                              ('Add late dock', self._add_late), ('Float all', self._float_all),
                              ('Dock all', self._dock_all)):
            button = QPushButton(text)
            button.clicked.connect(handler)
            row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(self.log)
        return central

    def _say(self, text: str) -> None:
        self.log.appendPlainText(text)
        print(text, flush=True)

    def _make(self, name: str, area: str, title_widget: QWidget | None = None, body: str = '') -> QDockWidget:
        dock = QDockWidget(name, self)
        dock.setObjectName(name)
        dock.setWindowIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        label = QLabel(body or name)
        label.setMinimumSize(120, 80)
        dock.setWidget(label)
        if title_widget is not None:
            dock.setTitleBarWidget(title_widget)
        dock.dockLocationChanged.connect(lambda a, n=name: self._say(f'{n}: dockLocationChanged -> {a.name}'))
        dock.topLevelChanged.connect(lambda floating, n=name: self._say(f'{n}: topLevelChanged floating={floating}'))
        dock.visibilityChanged.connect(lambda visible, n=name: self._say(f'{n}: visibilityChanged {visible}'))
        self.addDockWidget(AREAS[area], dock)
        return dock

    def _build_docks(self) -> None:
        bare = QWidget()
        bare.setFixedHeight(20)
        with_layout = QWidget()
        spacing = QVBoxLayout(with_layout)
        spacing.setContentsMargins(0, 0, 0, 0)
        spacing.addSpacing(20)
        with_label = QLabel('custom title (label)')
        self._make('bare widget title', 'Right', bare, 'Title bar hidden via a bare QWidget')
        second = self._make('layout widget title', 'Right', with_layout, 'Title bar hidden via QWidget + layout')
        third = self._make('label title', 'Right', with_label, 'Title bar replaced by a QLabel')
        self.splitDockWidget(self.findChild(QDockWidget, 'bare widget title'), second, Qt.Orientation.Vertical)
        self.splitDockWidget(second, third, Qt.Orientation.Vertical)
        self._make('top', 'Top')
        self._make('left', 'Left')
        tabs = [self._make(n, 'Left') for n in ('tabs A', 'tabs B', 'tabs C')]
        for first, other in zip(tabs, tabs[1:]):
            self.tabifyDockWidget(first, other)
        lower = self._make('bottom lower', 'Bottom')
        upper = self._make('bottom upper', 'Bottom')
        self.splitDockWidget(upper, lower, Qt.Orientation.Vertical)

    def _save(self) -> None:
        self._saved = self.saveState(STATE_VERSION)
        self._say(f'saved state: {self._saved.size()} bytes, window {self.width()}x{self.height()}')

    def _restore(self) -> None:
        if self._saved is None:
            self._say('nothing saved yet')
            return
        self._say(f'restoreState -> {self.restoreState(self._saved, STATE_VERSION)} '
                  f'(window {self.width()}x{self.height()})')

    def _add_late(self) -> None:
        self._late_count += 1
        dock = self._make(f'late {self._late_count}', 'Bottom')
        self._say(f'{dock.objectName()} added to Bottom after any restore; use Restore state to re-place it')

    def _float_all(self) -> None:
        for dock in self.findChildren(QDockWidget):
            dock.setFloating(True)

    def _dock_all(self) -> None:
        for dock in self.findChildren(QDockWidget):
            dock.setFloating(False)


app = QApplication.instance() or QApplication(sys.argv)
window = SpikeWindow()
window.show()
sys.exit(app.exec())
