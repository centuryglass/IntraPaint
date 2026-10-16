"""A form layout where every row shares one label column, for the non-numeric rows of a panel.

Numeric rows use `NumberField` or `SliderField`, which carry their own label. This layout is for rows such as a
combo box, a text field or a check box group.
"""
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QWidget


def normalize_row_label(text: str) -> str:
    """Returns a row label without surrounding whitespace or a trailing colon.

    Row labels are sentence case ("Sampling method") and carry no units. Units go in the field's value ("512 px").
    """
    return text.strip().removesuffix(':').removesuffix('：').rstrip()


class LabelColumnLayout(QFormLayout):
    """Lays out rows of a label and a field, with all labels left-aligned in one column and fields filling the rest."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

    def add_row(self, label_text: str, field: QWidget) -> QLabel:
        """Adds a row and returns its label, which is the field's buddy so mnemonic keys and screen readers work."""
        label = QLabel(normalize_row_label(label_text))
        label.setBuddy(field)
        self.addRow(label, field)
        return label
