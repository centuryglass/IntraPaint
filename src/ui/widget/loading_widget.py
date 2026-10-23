"""
Animated widget used to indicate a loading state.
"""
from typing import Optional

from PySide6.QtCore import Qt, QRectF, Property, QPropertyAnimation, QPointF
from PySide6.QtGui import QPainter, QColor, QShowEvent, QHideEvent, QPaintEvent, QResizeEvent, QPalette, \
    QRadialGradient
from PySide6.QtWidgets import QWidget

from src.config.application_config import AppConfig
from src.ui.loading.loading_design import LoadingDesign, MESSAGE_ZONE
from src.ui.loading.loading_designs import default_loading_designs, pick_design

# Behind the message, as a fraction of the indicator's side.
SCRIM_RADIUS = 0.31
SCRIM_DARK = QColor(12, 14, 18)
SCRIM_LIGHT = QColor(246, 247, 249)
TEXT_DARK = QColor('#f5f3ee')
TEXT_LIGHT = QColor('#16181e')
# Message line height as a fraction of the message zone's height. Messages wrap, so up to about three lines fit.
LINE_HEIGHT_FRACTION = 0.25


class LoadingWidget(QWidget):
    """Show an animated loading indicator, with an optional message.

    Each time the animation starts, from hidden or paused, the widget picks a random design from its design list,
    never repeating the previous one. A design is told each time its loop restarts. With
    `AppConfig.STATIC_LOADING_INDICATOR` set, a load holds the design's rest frame instead of animating, and message
    changes keep that frame.
    """

    def __init__(self, parent: Optional[QWidget] = None, message: str = '',
                 designs: Optional[list[LoadingDesign] | tuple[LoadingDesign, ...]] = None) -> None:
        """Initializes the widget, optionally with a parent widget, an initial loading message, and the designs to
        pick from. By default, it picks from every design `default_loading_designs` finds."""
        super().__init__(parent=parent)
        # Drawn over the window, so it must not block clicks or the cancel shortcut:
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._message = message
        self._phase = 0.0
        self._font_pixel_size = 1
        self._update_font_size()
        self._designs = tuple(designs) if designs is not None else default_loading_designs()
        self._design = self._designs[0]
        # noinspection PyTypeChecker
        self._anim = QPropertyAnimation(self, b'phase', self)
        self._anim.setLoopCount(-1)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(self._design.duration_ms)

    @property
    def designs(self) -> tuple[LoadingDesign, ...]:
        """Returns every design the widget picks from."""
        return self._designs

    @property
    def design(self) -> LoadingDesign:
        """Returns the design currently shown."""
        return self._design

    @design.setter
    def design(self, design: LoadingDesign) -> None:
        """Switches to a design, keeping the animation's running or paused state."""
        self._design = design
        if self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()
            self._anim.setDuration(design.duration_ms)
            self._anim.start()
        else:
            self._anim.setDuration(design.duration_ms)
            if self.paused:
                self.phase = design.rest_phase
        self.update()

    def start_new_design(self) -> None:
        """Picks a new random design and plays it from the start, or holds its rest frame if the indicator is
        static."""
        self._anim.stop()
        self.design = pick_design(self._designs, self._design)
        self._design.next_loop()
        if AppConfig().get(AppConfig.STATIC_LOADING_INDICATOR):
            self.phase = self._design.rest_phase
        else:
            self._anim.start()

    @property
    def paused(self) -> bool:
        """Whether the loading animation is currently paused."""
        return self._anim.state() == QPropertyAnimation.State.Paused

    @paused.setter
    def paused(self, should_pause: bool) -> None:
        """Pausing holds the design's rest frame. Unpausing starts a new load, with a new design."""
        if should_pause == self.paused:
            return
        if should_pause:
            if self._anim.state() == QPropertyAnimation.State.Stopped:
                self._anim.start()
            self._anim.pause()
            self.phase = self._design.rest_phase
        else:
            self.start_new_design()

    @property
    def visible(self) -> bool:
        """Exposes isVisible() as a property."""
        return self.isVisible()

    @property
    def message(self) -> str:
        """Returns the current loading message."""
        return self._message

    @message.setter
    def message(self, message: str) -> None:
        """Sets the loading message displayed, resuming the animation if paused."""
        self._message = message
        self.paused = False
        self.update()

    def phase_getter(self) -> float:
        """Returns the current position in the design's loop, from 0.0 to 1.0."""
        return self._phase

    def phase_setter(self, phase: float) -> None:
        """Sets the current position in the design's loop. Values outside 0.0 to 1.0 wrap."""
        phase %= 1.0
        if phase < self._phase and self._anim.state() == QPropertyAnimation.State.Running:
            self._design.next_loop()
        self._phase = phase
        self.update()

    # noinspection PyTypeChecker
    phase = Property(float, phase_getter, phase_setter)

    def showEvent(self, unused_event: Optional[QShowEvent]) -> None:
        """Starts the animation with a new design when the widget is shown."""
        self.start_new_design()

    def hideEvent(self, unused_event: Optional[QHideEvent]) -> None:
        """Stops the animation when the widget is hidden."""
        self._anim.stop()

    def resizeEvent(self, unused_event: Optional[QResizeEvent]) -> None:
        """Rescales the message text to the new bounds. The size depends only on the bounds, so it stays fixed as the
        message changes."""
        self._update_font_size()

    def _update_font_size(self) -> None:
        side = min(self.width(), self.height())
        self._font_pixel_size = max(1, round(side * MESSAGE_ZONE[1] * LINE_HEIGHT_FRACTION))

    def _is_dark(self) -> bool:
        return self.palette().color(QPalette.ColorRole.Window).lightness() < 128

    def paintEvent(self, unused_event: Optional[QPaintEvent]) -> None:
        """Draws a soft scrim, the current design frame, and the message over both."""
        side = min(self.width(), self.height())
        if side <= 0:
            return
        dark = self._is_dark()
        center = QPointF(self.width() / 2, self.height() / 2)
        bounds = QRectF(center.x() - side / 2, center.y() - side / 2, side, side)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        scrim_color = QColor(SCRIM_DARK if dark else SCRIM_LIGHT)
        gradient = QRadialGradient(center, side * SCRIM_RADIUS)
        for stop, alpha in ((0.0, 0.74), (0.78, 0.6), (1.0, 0.0)):
            scrim_color.setAlphaF(alpha)
            gradient.setColorAt(stop, scrim_color)
        painter.fillRect(bounds, gradient)

        self._design.paint(painter, self._design.fit(bounds), self._phase, dark)

        zone_width, zone_height = MESSAGE_ZONE
        text_bounds = QRectF(center.x() - side * zone_width / 2, center.y() - side * zone_height / 2,
                             side * zone_width, side * zone_height).toRect()
        font = painter.font()
        font.setPixelSize(self._font_pixel_size)
        painter.setFont(font)
        painter.setPen(TEXT_DARK if dark else TEXT_LIGHT)
        painter.drawText(text_bounds, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._message)
        painter.end()
