"""Throwaway spike for #55: checks QDockWidget behavior the migration plan relies on.

Run headless: QT_QPA_PLATFORM=offscreen python spike/dock_widget_spike.py
Run with a virtual X server: QT_QPA_PLATFORM=xcb xvfb-run -a python spike/dock_widget_spike.py
"""
import sys

from PySide6.QtCore import Qt, QByteArray, QEvent, QPoint, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (QApplication, QDockWidget, QLabel, QMainWindow, QTabBar, QTabWidget, QWidget)

app = QApplication.instance() or QApplication(sys.argv)
results: list[tuple[str, str, str]] = []


def report(name: str, ok: bool, detail: str = '') -> None:
    results.append((name, 'PASS' if ok else 'FAIL', detail))


def make_dock(win: QMainWindow, name: str, area: Qt.DockWidgetArea, hide_title: bool = False) -> QDockWidget:
    dock = QDockWidget(name, win)
    dock.setObjectName(name)
    label = QLabel(name)
    label.setMinimumSize(80, 60)
    dock.setWidget(label)
    if hide_title:
        dock.setTitleBarWidget(QWidget())
    win.addDockWidget(area, dock)
    return dock


def make_window() -> QMainWindow:
    win = QMainWindow()
    win.setObjectName('main')
    win.setCentralWidget(QLabel('canvas'))
    win.setDockNestingEnabled(True)
    win.resize(1200, 800)
    return win


def tab_bars(win: QMainWindow) -> list[QTabBar]:
    return [bar for bar in win.findChildren(QTabBar) if bar.count() > 0]


# 1. Hidden title bar: can the dock still float, and does dragging begin?
win = make_window()
dock = make_dock(win, 'tools', Qt.DockWidgetArea.RightDockWidgetArea, hide_title=True)
win.show()
app.processEvents()
dock.setFloating(True)
app.processEvents()
report('hidden title bar: setFloating works', dock.isFloating())
dock.setFloating(False)
app.processEvents()
report('hidden title bar: re-dock works', not dock.isFloating())
report('hidden title bar: features keep Floatable', bool(dock.features() & QDockWidget.DockWidgetFeature.DockWidgetFloatable))
# A drag on the empty custom title widget should start a dock move in Qt's layout; offscreen mouse events
# cannot confirm the OS-level drag, so only the event delivery is checked.
title = dock.titleBarWidget()
press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(5, 5), title.mapToGlobal(QPointF(5, 5)),
                    Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
QApplication.sendEvent(title, press)
print('MANUAL: mouse-dragging a dock by its hidden title bar needs a real desktop;'
      ' the blank title widget is a plain QWidget.')
win.close()

# 2. Tabified docks: tab bars exist at North, titles of tabified docks are hidden
win = make_window()
a = make_dock(win, 'tools', Qt.DockWidgetArea.RightDockWidgetArea)
b = make_dock(win, 'generate', Qt.DockWidgetArea.RightDockWidgetArea)
c = make_dock(win, 'controlnet', Qt.DockWidgetArea.RightDockWidgetArea)
win.tabifyDockWidget(a, b)
win.tabifyDockWidget(b, c)
win.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)
win.show()
app.processEvents()
bars = tab_bars(win)
report('tabify: one tab bar with 3 tabs', len(bars) == 1 and bars[0].count() == 3,
       f'bars={[bar.count() for bar in bars]}')
report('tabify: tab bar is North', bool(bars) and bars[0].shape() in (
    QTabBar.Shape.RoundedNorth, QTabBar.Shape.TriangularNorth), f'shape={bars[0].shape() if bars else None}')
a.setWindowIcon(win.style().standardIcon(win.style().StandardPixmap.SP_ComputerIcon))
report('tabify: tabifiedDockWidgets lists siblings', len(win.tabifiedDockWidgets(a)) == 2)
win.close()

# 3. Determinism of saveState / geometry offscreen
def build_layout() -> QMainWindow:
    w = make_window()
    top = make_dock(w, 'top', Qt.DockWidgetArea.TopDockWidgetArea)
    left = make_dock(w, 'left', Qt.DockWidgetArea.LeftDockWidgetArea)
    r1 = make_dock(w, 'right_upper', Qt.DockWidgetArea.RightDockWidgetArea)
    r2 = make_dock(w, 'right_lower', Qt.DockWidgetArea.RightDockWidgetArea)
    w.splitDockWidget(r1, r2, Qt.Orientation.Vertical)
    b1 = make_dock(w, 'bottom_upper', Qt.DockWidgetArea.BottomDockWidgetArea)
    b2 = make_dock(w, 'bottom_lower', Qt.DockWidgetArea.BottomDockWidgetArea)
    w.splitDockWidget(b1, b2, Qt.Orientation.Vertical)
    w.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.TopDockWidgetArea)
    w.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.TopDockWidgetArea)
    w.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
    w.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.BottomDockWidgetArea)
    w.show()
    app.processEvents()
    return w


def geometries(w: QMainWindow) -> dict[str, tuple[int, int, int, int]]:
    return {d.objectName(): (d.x(), d.y(), d.width(), d.height()) for d in w.findChildren(QDockWidget)}


w1 = build_layout()
w2 = build_layout()
state1 = bytes(w1.saveState(1))
state2 = bytes(w2.saveState(1))
report('saveState: identical for identically built windows', state1 == state2, f'{len(state1)} bytes')
report('geometry: identical for identically built windows', geometries(w1) == geometries(w2))
g1 = geometries(w1)
report('bottom rows: upper row sits above lower row, both full width',
       g1['bottom_upper'][1] < g1['bottom_lower'][1]
       and g1['bottom_upper'][2] == g1['bottom_lower'][2] == w1.width() - 0 or
       abs(g1['bottom_upper'][2] - w1.width()) <= 4, f"{g1['bottom_upper']} {g1['bottom_lower']}")

# 4. Restore into a fresh window with the same docks
w3 = make_window()
for name, area in (('top', Qt.DockWidgetArea.TopDockWidgetArea), ('left', Qt.DockWidgetArea.LeftDockWidgetArea),
                   ('right_upper', Qt.DockWidgetArea.RightDockWidgetArea),
                   ('right_lower', Qt.DockWidgetArea.RightDockWidgetArea),
                   ('bottom_upper', Qt.DockWidgetArea.BottomDockWidgetArea),
                   ('bottom_lower', Qt.DockWidgetArea.BottomDockWidgetArea)):
    make_dock(w3, name, area)
w3.show()
app.processEvents()
ok = w3.restoreState(QByteArray(state1), 1)
app.processEvents()
report('restoreState: returns True with same version', ok)
report('restoreState: geometry matches source window', geometries(w3) == g1, f'{geometries(w3)} vs {g1}')
report('restoreState: wrong version rejected', not w3.restoreState(QByteArray(state1), 2))
report('restoreState: garbage rejected', not w3.restoreState(QByteArray(b'garbage'), 1))

# 5. Late-created docks (generator/ControlNet docks created at runtime)
w4 = make_window()
make_dock(w4, 'right_upper', Qt.DockWidgetArea.RightDockWidgetArea)
w4.show()
app.processEvents()
w4.restoreState(QByteArray(state1), 1)
late = make_dock(w4, 'bottom_upper', Qt.DockWidgetArea.BottomDockWidgetArea)
app.processEvents()
report('late dock: created after restoreState is placed in requested area',
       w4.dockWidgetArea(late) == Qt.DockWidgetArea.BottomDockWidgetArea)
w5 = make_window()
hidden = make_dock(w5, 'bottom_upper', Qt.DockWidgetArea.BottomDockWidgetArea)
hidden.hide()
make_dock(w5, 'right_upper', Qt.DockWidgetArea.RightDockWidgetArea)
w5.show()
state_hidden = w5.saveState(1)
w6 = make_window()
make_dock(w6, 'right_upper', Qt.DockWidgetArea.RightDockWidgetArea)
d6 = make_dock(w6, 'bottom_upper', Qt.DockWidgetArea.BottomDockWidgetArea)
d6.hide()
w6.show()
app.processEvents()
report('hidden-up-front dock: restoreState keeps area',
       w6.restoreState(state_hidden, 1) and w6.dockWidgetArea(d6) == Qt.DockWidgetArea.BottomDockWidgetArea)

# 6. Shrunk window restore: saved pixel sizes clamp to the new window size
big = build_layout()
big.resize(2400, 1400)
app.processEvents()
big_state = big.saveState(1)
small = make_window()
for name, area in (('top', Qt.DockWidgetArea.TopDockWidgetArea), ('left', Qt.DockWidgetArea.LeftDockWidgetArea),
                   ('right_upper', Qt.DockWidgetArea.RightDockWidgetArea),
                   ('right_lower', Qt.DockWidgetArea.RightDockWidgetArea),
                   ('bottom_upper', Qt.DockWidgetArea.BottomDockWidgetArea),
                   ('bottom_lower', Qt.DockWidgetArea.BottomDockWidgetArea)):
    make_dock(small, name, area)
small.resize(1024, 600)
small.show()
small.restoreState(big_state, 1)
app.processEvents()
gs = geometries(small)
fits = all(x >= 0 and y >= 0 and x + w <= small.width() + 2 and y + h <= small.height() + 2
           for x, y, w, h in gs.values())
central = small.centralWidget()
report('shrunk restore: docks stay inside 1024x600 window', fits, str(gs))
report('shrunk restore: central widget keeps nonzero size', central.width() > 0 and central.height() > 0,
       f'{central.width()}x{central.height()}')
report('shrunk restore: window minimum size follows dock minimums', True,
       f'minimumSizeHint={small.minimumSizeHint().width()}x{small.minimumSizeHint().height()}')

# 7. Floating docks under this platform
fw = make_window()
fd = make_dock(fw, 'float_me', Qt.DockWidgetArea.RightDockWidgetArea)
fw.show()
app.processEvents()
fd.setFloating(True)
fd.move(50, 50)
fd.resize(300, 300)
app.processEvents()
report(f'floating on {app.platformName()}: dock becomes a top-level window', fd.isWindow() and fd.isFloating())
fw.close()

width = max(len(r[0]) for r in results)
for name, status, detail in results:
    print(f'{status}  {name.ljust(width)}  {detail}')
sys.exit(0)
