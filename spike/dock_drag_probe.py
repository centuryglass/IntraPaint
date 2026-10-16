"""Synthetic-event drag probe for #55: which custom title widgets let QDockWidget start a drag.

Run: QT_QPA_PLATFORM=xcb xvfb-run -a python spike/dock_drag_probe.py (offscreen also works).
Synthetic events only; confirm with a real mouse in dock_widget_manual.py.
"""
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import *
app=QApplication([])
def make(kind):
    if kind=='plain_fixedH': w=QWidget(); w.setFixedHeight(20)
    elif kind=='plain_minsize': w=QWidget(); w.setMinimumSize(60,20)
    elif kind=='plain_layout': w=QWidget(); l=QVBoxLayout(w); l.setContentsMargins(0,0,0,0); l.addSpacing(20)
    elif kind=='qframe': w=QFrame(); w.setFixedHeight(20)
    elif kind=='label_empty': w=QLabel(''); w.setFixedHeight(20)
    elif kind=='label_text': w=QLabel('x'); 
    return w
for kind in ('plain_fixedH','plain_minsize','plain_layout','qframe','label_empty','label_text'):
    w=QMainWindow(); w.setCentralWidget(QLabel('c')); w.resize(1000,700)
    d=QDockWidget('t',w); d.setWidget(QLabel('body')); tw=make(kind); d.setTitleBarWidget(tw)
    w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,d); w.show(); app.processEvents()
    pos=QPoint(min(10,tw.width()-1),min(5,tw.height()-1))
    QTest.mousePress(tw,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,pos)
    for i in range(1,8):
        QTest.mouseMove(tw,pos+QPoint(-i*30,i*10)); app.processEvents()
    QTest.mouseRelease(tw,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,pos+QPoint(-210,70)); app.processEvents()
    print(f'{kind:14} size={tw.size().toTuple()} floating={d.isFloating()}')
    w.close()
