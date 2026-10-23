"""Tests ImageViewer's context pin markers, its drop routing, and what deleting a viewer releases."""
import sys

from PySide6.QtCore import QCoreApplication, QEvent, QMimeData, QObject, QPoint, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QDragEnterEvent, QImage, QPainter
from PySide6.QtWidgets import QApplication, QMainWindow
import shiboken6

from src.image.layers.image_stack import ImageStack
from src.ui.graphics_items.context_pin_item import marker_size_for_view, DEFAULT_MARKER_SIZE, MIN_MARKER_SIZE, \
    MAX_MARKER_SIZE, MARKER_REFERENCE_VIEW_SIDE
from src.ui.image_viewer import ImageViewer, color_under_overlay, IMAGE_BORDER_COLOR, IMAGE_BORDER_OPACITY
from src.ui.ink_style import ink_colors
from test.base_test_case import IntraPaintTestCase

app = QApplication.instance() or QApplication(sys.argv)


class ImageViewerContextPinTest(IntraPaintTestCase):
    """Tests that viewers draw one marker per context pin."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(QSize(64, 64), QSize(64, 64), QSize(8, 8), QSize(64, 64))
        self.selection_layer = self.image_stack.selection_layer

    @staticmethod
    def _marker_count(viewer: ImageViewer) -> int:
        return len(viewer._context_pin_items)  # pylint: disable=protected-access

    def test_viewer_created_after_pins_draws_them(self) -> None:
        """A viewer created while pins exist, like a navigation panel opened later, draws markers for them."""
        self.selection_layer.set_context_pins([QPoint(5, 5), QPoint(20, 40)])
        viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        self.assertEqual(self._marker_count(viewer), 2)

    def test_markers_follow_pin_changes(self) -> None:
        """Markers are added and removed as pins change."""
        viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        self.assertEqual(self._marker_count(viewer), 0)
        self.selection_layer.add_context_pin(QPoint(5, 5))
        self.assertEqual(self._marker_count(viewer), 1)
        self.selection_layer.clear_context_pins()
        self.assertEqual(self._marker_count(viewer), 0)

    def test_marker_size_follows_view_size(self) -> None:
        """Resizing the view rescales existing markers, within the size limits."""
        self.selection_layer.set_context_pins([QPoint(5, 5)])
        viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        viewer.resize(MARKER_REFERENCE_VIEW_SIDE * 2, MARKER_REFERENCE_VIEW_SIDE)
        viewer.resizeEvent(None)
        self.assertEqual(viewer.context_pin_marker_size, DEFAULT_MARKER_SIZE)
        viewer.resize(100, 100)
        viewer.resizeEvent(None)
        self.assertEqual(viewer.context_pin_marker_size, MIN_MARKER_SIZE)
        self.assertEqual(viewer._context_pin_items[0].marker_size, MIN_MARKER_SIZE)  # pylint: disable=protected-access


class ImageViewerSurroundTest(IntraPaintTestCase):
    """Tests that the area around the image takes the theme's canvas surround color."""

    def test_background_fills_with_canvas_surround(self) -> None:
        """Drawing the background fills the exposed area with the canvas surround color, before the image's tiles."""
        image_stack = ImageStack(QSize(64, 64), QSize(64, 64), QSize(8, 8), QSize(64, 64))
        viewer = ImageViewer(None, image_stack, use_keybindings=False)
        image = QImage(QSize(32, 32), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        viewer.drawBackground(painter, QRectF(0, 0, 32, 32))
        painter.end()
        surround = ink_colors().canvas_surround
        self.assertEqual(color_under_overlay(surround, QColor(IMAGE_BORDER_COLOR), IMAGE_BORDER_OPACITY).name(),
                         image.pixelColor(0, 0).name())

    def test_surround_shows_through_image_border_veil(self) -> None:
        """Drawing the image border veil over the filled background gives the theme's surround color."""
        surround = ink_colors().canvas_surround
        under = color_under_overlay(surround, QColor(IMAGE_BORDER_COLOR), IMAGE_BORDER_OPACITY)
        shown = QImage(QSize(1, 1), QImage.Format.Format_ARGB32_Premultiplied)
        shown.fill(under)
        painter = QPainter(shown)
        painter.setOpacity(IMAGE_BORDER_OPACITY)
        painter.fillRect(0, 0, 1, 1, QColor(IMAGE_BORDER_COLOR))
        painter.end()
        for channel in ('red', 'green', 'blue'):
            self.assertAlmostEqual(getattr(surround, channel)(), getattr(shown.pixelColor(0, 0), channel)(), delta=1)

    def test_color_under_overlay(self) -> None:
        """The overlay math inverts compositing, and clamps colors the overlay can't produce."""
        self.assertEqual('#3c3d41', color_under_overlay(QColor('#303134'), QColor('black'), 0.2).name())
        self.assertEqual('#303134', color_under_overlay(QColor('#303134'), QColor('black'), 0.0).name())
        self.assertEqual('#303134', color_under_overlay(QColor('#303134'), QColor('black'), 1.0).name())
        self.assertEqual('#000000', color_under_overlay(QColor('#000000'), QColor('#808080'), 0.5).name())
        self.assertEqual('#ffffff', color_under_overlay(QColor('#ffffff'), QColor('#808080'), 0.5).name())


class ImageViewerLifetimeTest(IntraPaintTestCase):
    """Tests that deleting a viewer releases its scene and its layers' connections, while the image stack lives on."""

    def test_delete_releases_scene_and_layer_items(self) -> None:
        """Deleting a viewer deletes its scene and disconnects its layer items, so layer changes don't reach them."""
        image_stack = ImageStack(QSize(64, 64), QSize(64, 64), QSize(8, 8), QSize(64, 64))
        layer = image_stack.create_layer()
        viewer = ImageViewer(None, image_stack, use_keybindings=False)
        scene = viewer.scene()
        layer_items = list(viewer._layer_items.values())  # pylint: disable=protected-access
        self.assertNotEqual(layer_items, [])
        viewer.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(shiboken6.isValid(scene))
        for layer_item in layer_items:
            self.assertEqual(layer_item._connections, [])  # pylint: disable=protected-access
        image = QImage(layer.size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0xff00ff00)
        layer.image = image


class MarkerSizeForViewTest(IntraPaintTestCase):
    """Tests marker_size_for_view's scaling and limits."""

    def test_scales_with_shorter_side(self) -> None:
        """The marker size scales with the view's shorter side."""
        self.assertEqual(marker_size_for_view(QSize(3000, MARKER_REFERENCE_VIEW_SIDE)), DEFAULT_MARKER_SIZE)
        self.assertEqual(marker_size_for_view(QSize(MARKER_REFERENCE_VIEW_SIDE * 3 // 2, 3000)),
                         DEFAULT_MARKER_SIZE * 3 // 2)

    def test_clamped(self) -> None:
        """Tiny and huge views stay within the marker size limits."""
        self.assertEqual(marker_size_for_view(QSize(10, 10)), MIN_MARKER_SIZE)
        self.assertEqual(marker_size_for_view(QSize(10000, 10000)), MAX_MARKER_SIZE)


DOCK_DRAG_MIME = 'application/x-qt-mainwindowdrag-window'
CLAIMED_DRAG_MIME = 'application/x-intrapaint-test-drop'


class _DragWatcher(QObject):
    """Installed on a top-level window to record whether a DragEnter reached it."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.window_saw_drag = False

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:  # pylint: disable=invalid-name
        """Records a DragEnter, and lets Qt's own drag handling run."""
        if event.type() == QEvent.Type.DragEnter:
            self.window_saw_drag = True
        return False


class _DropClaimingViewer(ImageViewer):
    """An image viewer that claims one sample drag format, as the canvas drop feature will."""

    def accepts_mime_data(self, mime_data: QMimeData) -> bool:
        """Returns whether the drag carries the claimed sample format."""
        return mime_data is not None and mime_data.hasFormat(CLAIMED_DRAG_MIME)


class ImageViewerDropRoutingTest(IntraPaintTestCase):
    """Tests that an image view claims only the drags it handles, passing Qt's dock drag up to
    the main window instead of letting its scene swallow it."""

    def setUp(self) -> None:
        super().setUp()
        self.image_stack = ImageStack(QSize(64, 64), QSize(64, 64), QSize(8, 8), QSize(64, 64))
        self.viewer = ImageViewer(None, self.image_stack, use_keybindings=False)
        self.window = QMainWindow()
        self.window.setCentralWidget(self.viewer)
        self.window.resize(300, 200)
        self.window.show()
        self.watcher = _DragWatcher(self.window)
        self.window.installEventFilter(self.watcher)

    def tearDown(self) -> None:
        self.window.hide()
        super().tearDown()

    @classmethod
    def _drag_enter(cls, viewer: ImageViewer, mime: QMimeData, action: Qt.DropAction) -> QDragEnterEvent:
        """Sends a DragEnter for `mime` to `viewer`'s viewport, as a drag over the canvas."""
        event = QDragEnterEvent(QPoint(50, 50), action, mime, Qt.MouseButton.LeftButton,
                                Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(viewer.viewport(), event)
        return event

    def test_dock_drag_passes_up_over_the_view(self) -> None:
        """A drag a view doesn't claim, like Qt's Wayland dock drag, is ignored at the viewport
        and reaches the window above the view, so a dock can drop over the canvas."""
        mime = QMimeData()
        mime.setData(DOCK_DRAG_MIME, b'')
        event = self._drag_enter(self.viewer, mime, Qt.DropAction.MoveAction)
        self.assertFalse(event.isAccepted())
        self.assertTrue(self.watcher.window_saw_drag)

    def test_claimed_drag_is_accepted_by_the_view(self) -> None:
        """A drag that `accepts_mime_data` claims is accepted at the view, which stops the
        drag's parent walk before it reaches the window."""
        claiming = _DropClaimingViewer(None, self.image_stack, use_keybindings=False)
        window = QMainWindow()
        window.setCentralWidget(claiming)
        window.resize(300, 200)
        window.show()
        self.addCleanup(window.hide)
        watcher = _DragWatcher(window)
        window.installEventFilter(watcher)
        mime = QMimeData()
        mime.setData(CLAIMED_DRAG_MIME, b'')
        event = self._drag_enter(claiming, mime, Qt.DropAction.CopyAction)
        self.assertTrue(event.isAccepted())
        self.assertEqual(event.dropAction(), Qt.DropAction.CopyAction)
        self.assertFalse(watcher.window_saw_drag)

    def test_accepts_mime_data_is_false_by_default(self) -> None:
        """The base view claims no drag formats, so every drag passes up the widget chain."""
        self.assertFalse(self.viewer.accepts_mime_data(QMimeData()))
