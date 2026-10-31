"""Renders a comparison sheet of the current and draft icons: argv = out_png, svg paths..."""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt, QRect
app = QApplication(['x', '-platform', 'offscreen'])
out, paths = sys.argv[1], sys.argv[2:]
sizes = [128, 48, 32, 24]
others = ['brush', 'selection', 'layer_transform', 'zoom']
colw, rowh = 150, 150
sheet = QPixmap(colw * len(paths), 40 + rowh + 60 + 4 * 40)
sheet.fill(QColor('#d0d0d0'))
p = QPainter(sheet)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
for c, path in enumerate(paths):
    x0 = c * colw
    p.setPen(Qt.GlobalColor.black)
    p.drawText(QRect(x0, 5, colw, 30), Qt.AlignmentFlag.AlignCenter, path.split('/')[-1].replace('.svg', ''))
    p.drawPixmap(x0 + 11, 40, QIcon(path).pixmap(128, 128))
    x = x0 + 11
    for s in sizes[1:]:
        p.drawPixmap(x, 40 + rowh + (48 - s), QIcon(path).pixmap(s, s))
        x += s + 8
    # In context: a row of 32px tool buttons with this icon in the middle.
    y = 40 + rowh + 60
    for dark in (False, True):
        p.fillRect(x0 + 4, y - 4, colw - 8, 40, QColor('#2b2b2b' if dark else '#f0f0f0'))
        icons = [f'resources/icons/tools/{others[0]}_icon.svg', f'resources/icons/tools/{others[1]}_icon.svg',
                 path, f'resources/icons/tools/{others[3]}_icon.svg']
        for i, ip in enumerate(icons):
            p.drawPixmap(x0 + 8 + i * 35, y, QIcon(ip).pixmap(32, 32))
        y += 44
p.end()
sheet.save(out)
