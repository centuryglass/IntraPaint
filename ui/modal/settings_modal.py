from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSignal
from ui.widget.bordered_widget import BorderedWidget
from ui.widget.collapsible_box import CollapsibleBox


class SettingsModal(QDialog):
    """Manage remote settings."""

    changesSaved = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__(parent)
        self.setModal(True)

        self._panels = {}
        self._panelLayouts = {}
        self._changes = {}
        self._panelLayout = QVBoxLayout()

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)

        self._panelWidget = BorderedWidget(self)
        self._panelWidget.setLayout(self._panelLayout)
        self._layout.addWidget(self._panelWidget, stretch=20)

        self._bottomPanel = BorderedWidget(self) 
        self._bottomPanelLayout = QHBoxLayout()
        self._bottomPanel.setLayout(self._bottomPanelLayout)
        self._bottomPanelLayout.addSpacing(300)

        self._cancelButton = QPushButton()
        self._cancelButton.setText("Cancel")
        self._cancelButton.clicked.connect(lambda: self.hide())
        self._bottomPanelLayout.addWidget(self._cancelButton, stretch=1)

        self._saveButton = QPushButton()
        self._saveButton.setText("Save")
        def onSave():
            self.changesSaved.emit(self._changes)
            self.hide()
        self._saveButton.clicked.connect(lambda: onSave())
        self._bottomPanelLayout.addWidget(self._saveButton, stretch=1)
        self._layout.addWidget(self._bottomPanel, stretch=1)

    def showModal(self):
        self.exec_()
        
    def _addChange(self, setting, newValue):
        self._changes[setting] = newValue

    def _addPanelIfMissing(self, panelName):
        if panelName not in self._panels:
            panel = CollapsibleBox(title=panelName, parent=self._panelWidget)
            panelLayout = QVBoxLayout()
            panel.setContentLayout(panelLayout)
            self._panels[panelName] = panel
            self._panelLayouts[panelName] = panelLayout
            self._panelLayout.addWidget(panel)

    def _getLabeledWrapper(self, settingWidget, labelText, panelName):
        settingContainer = QWidget(self._panels[panelName])
        settingLayout = QHBoxLayout()
        settingLayout.addWidget(QLabel(labelText))
        settingLayout.addWidget(settingWidget)
        settingContainer.setLayout(settingLayout)
        return settingContainer

    def addTextSetting(self, settingName, panelName, initialValue, labelText):
        self._addPanelIfMissing(panelName)
        textBox = QPlainTextEdit(self._panels[panelName])
        textBox.setPlainText(initialValue)
        textBox.textChanged.connect(lambda: self._addChange(settingName, textBox.toPlainText()))
        self._panelLayouts[panelName].addWidget(self._getLabeledWrapper(textBox, labelText, panelName))
        
