"""Widgets the ControlNet panel shows in a strip: the unit list that stands in for its tabs, and the preprocessor
preview that sizes itself to a strip column."""
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage
from PySide6.QtWidgets import QAbstractItemView, QFrame, QListWidget, QListWidgetItem, QSizePolicy

from src.ui.widget.image_widget import ImageWidget

# The diameter of a unit's on/off dot:
DOT_SIZE = 8
# The largest a preprocessor preview is drawn, in both dimensions:
PREVIEW_IMAGE_SIZE = 300
# The smallest a preview shrinks to, as a fraction of its size at PREVIEW_IMAGE_SIZE:
PREVIEW_MIN_FRACTION = 1 / 3


class UnitList(QListWidget):
    """The strip's unit selector: one row per unit, with the same title, tooltip and dot as its tab.

    It is exactly as tall as its rows, and prefers the width of its longest title. Narrower than that, titles elide.
    """

    def __init__(self, count: int) -> None:
        super().__init__()
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setUniformItemSizes(True)
        self.setIconSize(QSize(DOT_SIZE, DOT_SIZE))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        # Rows sit on the panel's background, like the tabs they stand in for:
        self.viewport().setAutoFillBackground(False)
        for _ in range(count):
            self.addItem(QListWidgetItem())
        self.itemSelectionChanged.connect(self._keep_selection)

    def _keep_selection(self) -> None:
        """Selects the current row again after a Ctrl+click clears the selection, so one unit always shows as chosen."""
        current = self.currentItem()
        if current is not None and len(self.selectedItems()) == 0:
            current.setSelected(True)

    def set_row(self, row: int, title: str, tooltip: str, icon: QIcon) -> None:
        """Sets a unit's title, tooltip and on/off dot."""
        item = self.item(row)
        item.setText(title)
        item.setToolTip(tooltip)
        item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, tooltip)
        item.setIcon(icon)
        self.updateGeometry()

    def _rows_height(self) -> int:
        return sum(self.sizeHintForRow(row) for row in range(self.count())) + 2 * self.frameWidth()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the size that shows every row and its full title."""
        return QSize(self.sizeHintForColumn(0) + 2 * self.frameWidth(), self._rows_height())

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the size that shows every row, with titles elided down to the unit number."""
        metrics = self.fontMetrics()
        widest_title = max((metrics.horizontalAdvance(self.item(row).text()) for row in range(self.count())),
                           default=0)
        padding = self.sizeHintForColumn(0) - widest_title
        elided = metrics.horizontalAdvance(f'{self.count()} …')
        return QSize(padding + elided + 2 * self.frameWidth(), self._rows_height())


class PreviewImage(ImageWidget):
    """A preprocessor preview that prefers its image scaled down to fit `PREVIEW_IMAGE_SIZE`, and can shrink to
    `PREVIEW_MIN_FRACTION` of that, whatever the image's own size.

    With a size limit, as in a strip's column, it takes the largest size that fits the limit as both its preferred
    and minimum size, so nothing packs under it. A limit below its usual minimum leaves that minimum, so planning hides
    the preview instead of shrinking it further.
    """

    def __init__(self, image: QImage) -> None:
        super().__init__(image)
        self._size_limit: Optional[QSize] = None

    def set_size_limit(self, limit: Optional[QSize]) -> None:
        """Sets the size the preview fills, or None for no limit."""
        if limit != self._size_limit:
            self._size_limit = limit
            self.updateGeometry()

    def _scaled_size(self) -> QSize:
        size = super().sizeHint()
        if size.width() > PREVIEW_IMAGE_SIZE or size.height() > PREVIEW_IMAGE_SIZE:
            size = size.scaled(PREVIEW_IMAGE_SIZE, PREVIEW_IMAGE_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
        return size

    def _smallest_size(self) -> QSize:
        size = self._scaled_size()
        return QSize(round(size.width() * PREVIEW_MIN_FRACTION), round(size.height() * PREVIEW_MIN_FRACTION))

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns the image's size, scaled down to fit `PREVIEW_IMAGE_SIZE` and the size limit if larger."""
        size = self._scaled_size()
        limit = self._size_limit
        if limit is not None and (size.width() > limit.width() or size.height() > limit.height()):
            size = size.scaled(limit, Qt.AspectRatioMode.KeepAspectRatio).expandedTo(self._smallest_size())
        return size

    def minimumSizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Returns `PREVIEW_MIN_FRACTION` of the scaled size, or the size hint while there is a size limit."""
        return self._smallest_size() if self._size_limit is None else self.sizeHint()
