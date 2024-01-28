from PyQt5.QtWidgets import *
from PyQt5.QtCore import pyqtSignal
from ui.widget.bordered_widget import BorderedWidget
from ui.widget.collapsible_box import CollapsibleBox
from ui.widget.big_int_spinbox import BigIntSpinbox
from ui.widget.label_wrapper import LabelWrapper


class SettingsModal(QDialog):
    """Manage remote settings."""

    changesSaved = pyqtSignal(dict)

    def __init__(self, parent):
        super().__init__(parent)
        self.setModal(True)

        self._panels = {}
        self._panelLayouts = {}
        self._inputs = {}
        self._changes = {}
        self._panelLayout = QVBoxLayout()

        layout = QVBoxLayout()
        self.setLayout(layout)

        panelWidget = BorderedWidget(self)
        panelWidget.setLayout(self._panelLayout)
        layout.addWidget(panelWidget, stretch=20)

        bottomPanel = BorderedWidget(self) 
        bottomPanelLayout = QHBoxLayout()
        bottomPanel.setLayout(bottomPanelLayout)
        bottomPanelLayout.addSpacing(300)

        cancelButton = QPushButton()
        cancelButton.setText("Cancel")
        cancelButton.clicked.connect(lambda: self.hide())
        bottomPanelLayout.addWidget(cancelButton, stretch=1)

        saveButton = QPushButton()
        saveButton.setText("Save")
        def onSave():
            self.changesSaved.emit(self._changes)
            self.hide()
        saveButton.clicked.connect(lambda: onSave())
        bottomPanelLayout.addWidget(saveButton, stretch=1)
        layout.addWidget(bottomPanel, stretch=1)

    def showModal(self):
        self.exec_()

    def setTooltip(self, settingName, tooltip):
        if settingName not in self._inputs:
            raise Exception(f"{settingName} not defined")
        self._inputs[settingName].setToolTip(tooltip)
        
    def _addChange(self, setting, newValue):
        self._changes[setting] = newValue

    def _addPanelIfMissing(self, panelName):
        if panelName not in self._panels:
            panel = CollapsibleBox(title=panelName)
            panelLayout = QVBoxLayout()
            panel.setContentLayout(panelLayout)
            self._panels[panelName] = panel
            self._panelLayouts[panelName] = panelLayout
            self._panelLayout.addWidget(panel)

    def _addSetting(self, settingName, panelName, widget, labelText):
        self._addPanelIfMissing(panelName)
        self._panelLayouts[panelName].addWidget(LabelWrapper(widget, labelText))
        self._inputs[settingName] = widget

    def updateSettings(self, settings):
        for key in settings:
            if key not in self._inputs:
                continue
            widget = self._inputs[key]
            if isinstance(widget, QLineEdit):
                widget.setText(settings[key])
            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(widget.findText(settings[key]))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(settings[key]))
            elif isinstance(widget, BigIntSpinbox):
                widget.setValue(int(settings[key]))
            elif isinstance(widget, QCheckBox):
                widget.setChecked(settings[key])
            if key in self._changes:
                del self._changes[key]

    def addTextSetting(self, settingName, panelName, initialValue, labelText):
        textBox = QLineEdit()
        textBox.setText(initialValue)
        textBox.textChanged.connect(lambda: self._addChange(settingName, textBox.text()))
        self._addSetting(settingName, panelName, textBox, labelText)

    def addComboBoxSetting(self, settingName, panelName, initialValue, options, labelText):
        comboBox = QComboBox()
        for option in options:
            if isinstance(option, dict):
                comboBox.addItem(option['text'])
            else:
                comboBox.addItem(option)
        def updateValue(selectedIndex):
            print(f"Set value {selectedIndex} for {settingName}")
            self._addChange(settingName, options[selectedIndex])
        comboBox.setCurrentIndex(options.index(initialValue))
        comboBox.currentIndexChanged.connect(updateValue)
        self._addSetting(settingName, panelName, comboBox, labelText)

    def addSpinBoxSetting(self, settingName, panelName, initialValue, minValue, maxValue, labelText):
        spinBox = QDoubleSpinBox() if type(initialValue) is float else BigIntSpinbox()
        spinBox.setRange(minValue, maxValue)
        spinBox.setValue(initialValue)
        spinBox.valueChanged.connect(lambda newValue: self._addChange(settingName, newValue))
        self._addSetting(settingName, panelName, spinBox, labelText)

        
    def addCheckBoxSetting(self, settingName, panelName, initialValue, labelText):
        checkBox = QCheckBox()
        checkBox.setChecked(initialValue)
        checkBox.stateChanged.connect(lambda isChecked: self._addChange(settingName, bool(isChecked)))
        self._addSetting(settingName, panelName, checkBox, labelText)
