"""Tests for the rounded, shadowed menus and tooltips InkStyle draws in translucent top-level windows."""
import sys

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QPushButton, QToolTip

from src.ui.ink_style import InkStyle, POPUP_SHADOW_OFFSET
from src.ui.theme import apply_rounded_popups
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


def _render(widget: QLabel | QMenu) -> QImage:
    image = QImage(widget.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    widget.render(image)
    return image


def _menu() -> QMenu:
    menu = QMenu()
    menu.addAction('Open')
    menu.addAction('Save')
    menu.ensurePolished()
    return menu


class PopupStyleTest(IntraPaintTestCase):
    """Menus and tooltips draw a panel inside a transparent margin that holds the shadow."""

    def tearDown(self) -> None:
        apply_rounded_popups(True)
        QToolTip.hideText()
        super().tearDown()

    def _assert_rounded_popup_image(self, image: QImage) -> None:
        window_color = QApplication.palette().color(QPalette.ColorRole.Window)
        shadow_color = QApplication.palette().color(QPalette.ColorRole.Shadow)
        # Square corners would cover the top-left pixel, and the rounded panel's corner leaves it clear:
        self.assertEqual(0, image.pixelColor(0, 0).alpha())
        # The shadow shows below and right of the panel, and nothing is drawn at the other two corners of the window:
        self.assertEqual(0, image.pixelColor(image.width() - 1, 0).alpha())
        self.assertEqual(0, image.pixelColor(0, image.height() - 1).alpha())
        for edge_pixel in ((image.width() // 2, image.height() - 1), (image.width() - 1, image.height() // 2)):
            self.assertEqual(255, image.pixelColor(*edge_pixel).alpha())
            self.assertEqual(shadow_color.name(), image.pixelColor(*edge_pixel).name())
        center = image.pixelColor((image.width() - POPUP_SHADOW_OFFSET) // 2,
                                  (image.height() - POPUP_SHADOW_OFFSET) // 2)
        self.assertEqual(window_color.name(), center.name())

    def test_menu_is_translucent_with_shadow_margin(self) -> None:
        self.assertIsInstance(QApplication.style(), InkStyle)
        menu = _menu()
        self.assertTrue(menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertTrue(menu.windowFlags() & Qt.WindowType.FramelessWindowHint)
        margins = menu.contentsMargins()
        self.assertEqual((0, 0, POPUP_SHADOW_OFFSET, POPUP_SHADOW_OFFSET),
                         (margins.left(), margins.top(), margins.right(), margins.bottom()))
        menu.resize(menu.sizeHint())
        self._assert_rounded_popup_image(_render(menu))

    def test_tooltip_is_translucent_with_shadow_margin(self) -> None:
        anchor = QPushButton('anchor')
        anchor.show()
        QToolTip.showText(QPoint(10, 10), 'A tooltip', anchor)
        tips = [widget for widget in QApplication.topLevelWidgets()
                if widget.metaObject().className() == 'QTipLabel' and widget.isVisible()]
        self.assertEqual(1, len(tips))
        self.assertTrue(tips[0].testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self._assert_rounded_popup_image(_render(tips[0]))

    def test_option_off_draws_square_opaque_popups(self) -> None:
        apply_rounded_popups(False)
        menu = _menu()
        self.assertFalse(menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertEqual(0, menu.contentsMargins().right())
        menu.resize(menu.sizeHint())
        image = _render(menu)
        self.assertEqual(255, image.pixelColor(0, 0).alpha())
        self.assertEqual(255, image.pixelColor(image.width() - 1, image.height() - 1).alpha())
