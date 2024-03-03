from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from ui.widget.collapsible_box import CollapsibleBox
from ui.widget.label_wrapper import LabelWrapper
from ui.widget.param_slider import ParamSlider
from ui.modal.modal_utils import openImageFile
import pprint

class ControlnetPanel(CollapsibleBox):

    def __init__(self, config, controlTypes, moduleDetail, title = "ControlNet"):
        super().__init__(title=title, startClosed=(len(config.get('controlnetArgs')) == 0), maxSizeFraction=0.3, maxSizePx=300)

        initialControlState = config.get('controlnetArgs')

        # Build layout:
        layout = QVBoxLayout()
        self.setContentLayout(layout)

        # Basic checkboxes:
        checkboxRow = QHBoxLayout()
        layout.addLayout(checkboxRow)
        enabledCheck = QCheckBox()
        enabledCheck.setText('Enable ControlNet')
        checkboxRow.addWidget(enabledCheck)

        vramCheck = QCheckBox()
        vramCheck.setText('Low VRAM')
        checkboxRow.addWidget(vramCheck)

        pxPerfectCheck = QCheckBox()
        pxPerfectCheck.setText('Pixel Perfect')
        checkboxRow.addWidget(pxPerfectCheck)
        
        
        # Control image row:
        useSelection = 'image' in initialControlState and initialControlState['image'] == 'SELECTION'
        imageRow = QHBoxLayout()
        layout.addLayout(imageRow)

        loadImageButton = QPushButton()
        loadImageButton.setText('Set Control Image')
        loadImageButton.setEnabled(not useSelection)
        imageRow.addWidget(loadImageButton, stretch=10)

        imagePathEdit = QLineEdit('' if useSelection  or 'image' not in initialControlState else initialControlState['image'])
        imagePathEdit.setEnabled(not useSelection)
        imageRow.addWidget(imagePathEdit, stretch=80)

        reuseImageCheck = QCheckBox()
        reuseImageCheck.setText('Selection as Control')
        imageRow.addWidget(reuseImageCheck, stretch=10)
        reuseImageCheck.setChecked(useSelection)

        # Mode-selection row:
        selectionRow = QHBoxLayout()
        layout.addLayout(selectionRow)
        controlTypeBox = QComboBox(self)
        for control in controlTypes:
            controlTypeBox.addItem(control)
        controlTypeBox.setCurrentIndex(controlTypeBox.findText("All"))
        selectionRow.addWidget(LabelWrapper(controlTypeBox, 'Control Type'))
        
        moduleBox = QComboBox(self)
        selectionRow.addWidget(LabelWrapper(moduleBox, 'Control Module'))

        modelBox = QComboBox(self)
        selectionRow.addWidget(LabelWrapper(modelBox, 'Control Model'))


        # Dynamic options section:
        optionsBox = CollapsibleBox("Options", maxSizeFraction=0.2, maxSizePx=200)
        optionsLayout = QVBoxLayout()
        optionsBox.setContentLayout(optionsLayout)
        layout.addWidget(optionsBox)
        self.moduleOptions = {}
        optionsBox.setEnabled(not useSelection)


        # Update controlNet selection in config:
        def writeStateToConfig():
            if not enabledCheck.isChecked():
                config.set('controlnetArgs', {})
                return
            controlnet = {
                'module':  moduleBox.currentText(),
                'model': modelBox.currentText(),
                'low_vram': vramCheck.isChecked(),
                'pixel_perfect': pxPerfectCheck.isChecked(),
                #NOTE: Values below need to be adjusted by API before sending:
            }
            if reuseImageCheck.isChecked():
                controlnet['image'] = 'SELECTION'
            else:
                controlnet['image'] = imagePathEdit.text()
            for key in self.moduleOptions:
                controlnet[key] = self.moduleOptions[key]
            config.set('controlnetArgs', controlnet)


        # connect components above to writeStateToConfig:
        for checkbox in [vramCheck, pxPerfectCheck]:
            checkbox.stateChanged.connect(writeStateToConfig)
        imagePathEdit.textChanged.connect(writeStateToConfig)

        def toggleControlImage():
            if reuseImageCheck.isChecked():
                imagePathEdit.setText('')
                imagePathEdit.setEnabled(False)
                loadImageButton.setEnabled(False)
            else:
                imagePathEdit.setEnabled(True)
                loadImageButton.setEnabled(True)
            writeStateToConfig()
        reuseImageCheck.stateChanged.connect(toggleControlImage)

        def loadImage():
            file, fileSelected = openImageFile(self)
            if file and fileSelected:
                imagePathEdit.setText(file)
                writeStateToConfig()
        loadImageButton.clicked.connect(loadImage)


        #on model change, update config:
        def handleModelChange():
            writeStateToConfig()
        modelBox.currentIndexChanged.connect(handleModelChange)

        def handleModuleChange(selection):
            if selection not in moduleDetail['module_detail']:
                for option in moduleDetail['module_list']:
                    if selection.startswith(option):
                        selection = option
                        break
            if selection not in moduleDetail['module_detail']:
                print(f"Warning: invalid selection {selection} not found")
                return
            details = moduleDetail['module_detail'][selection]
            self.moduleOptions = {}
            while optionsLayout.count() > 0:
                row = optionsLayout.itemAt(0)
                while row.layout().count() > 0:
                    item = row.layout().itemAt(0)
                    row.layout().removeItem(item)
                    if item.widget():
                        item.widget().deleteLater()
                optionsLayout.removeItem(row)
                row.layout().deleteLater()
            if selection != "none":
                sliders = [
                    {
                        'display': 'Control Weight',
                        'name': 'weight',
                        'value': 1.0,
                        'min': 0.0,
                        'max': 2.0,
                        'step': 0.1
                    },
                    {
                        'display': 'Starting Control Step',
                        'name': 'guidance_start',
                        'value': 0.0,
                        'min': 0.0,
                        'max': 1.0,
                        'step': 0.1
                    },
                    {
                        'display': 'Ending Control Step',
                        'name': 'guidance_end',
                        'value': 1.0,
                        'min': 0.0,
                        'max': 1.0,
                        'step': 0.1
                    },
                ]
                if 'sliders' in details:
                    for sliderParams in details['sliders']:
                        if sliderParams is None:
                            continue
                        sliders.append(sliderParams)
                sliderRow = QHBoxLayout()
                for sliderParams in sliders:
                    if sliderParams is None:
                        continue
                    key = sliderParams['name']
                    title = sliderParams['display'] if 'display' in sliderParams else key
                    value = sliderParams['value']
                    minVal = sliderParams['min']
                    maxVal = sliderParams['max']
                    if key == title:
                        if 'Resolution' in key:
                            key = 'processor_res'
                        elif 'threshold_a' not in self.moduleOptions:
                            key = 'threshold_a'
                        elif 'threshold_b' not in self.moduleOptions:
                            key = 'threshold_b'
                    step = 1 if 'step' not in sliderParams else sliderParams['step']
                    floatMode = any(x != int(x) for x in [value, minVal, maxVal, step])
                    if floatMode:
                        value = float(value)
                        minVal = float(minVal)
                        maxVal = float(maxVal)
                        step = float(step)
                    else:
                        value = int(value)
                        minVal = int(minVal)
                        maxVal = int(maxVal)
                        step = int(step)

                    # Mini implementation of the Config interface so we can reuse ParamSlider:
                    panel = self
                    class Config():
                        def __init__(self):
                            self._connected = {}
                            self.data = {
                                'min': minVal,
                                'max': maxVal,
                                'step': step
                            }
                            self.data[key] = value
                        def get(self, key):
                            return self.data[key]

                        def connect(self, toConnect, key, onChange):
                            if not key in self._connected:
                                self._connected[key] = {}
                            self._connected[key][toConnect] = onChange

                        def set(self, keyName, newValue):
                            if newValue != panel.moduleOptions[keyName]:
                                panel.moduleOptions[keyName] = newValue
                                self.data[keyName] = newValue
                                for callback in self._connected[keyName].values():
                                    callback(newValue)
                                try:
                                    writeStateToConfig()
                                except RecursionError:
                                    pp = pprint.PrettyPrinter(indent=2)
                                    pp.pprint(self.data)


                    config = Config()
                    self.moduleOptions[key] = value
                    slider = ParamSlider(self, title, config, key, 'min', 'max', 'step')
                    if sliderRow.count() > 1:
                        optionsLayout.addLayout(sliderRow)
                        sliderRow = QHBoxLayout()
                    sliderRow.addWidget(slider)
                if sliderRow.count() > 0:
                    optionsLayout.addLayout(sliderRow)
            optionsBox.refreshLayout()
            self.refreshLayout()
            writeStateToConfig()
        moduleChangeHandler = lambda: handleModuleChange(moduleBox.currentText())
        moduleBox.currentIndexChanged.connect(moduleChangeHandler)

        # Setup control types, update other boxes on change:
        def loadControlType(typename):
            modelBox.currentIndexChanged.disconnect(handleModelChange)
            while modelBox.count() > 0:
                modelBox.removeItem(0)
            for model in controlTypes[typename]['model_list']:
                modelBox.addItem(model)
            defaultModel = controlTypes[typename]['default_model']
            if defaultModel != 'none':
                modelBox.setCurrentIndex(modelBox.findText(defaultModel))
            else:
                modelBox.setCurrentIndex(0)
            modelBox.currentIndexChanged.connect(handleModelChange)

            moduleBox.currentIndexChanged.disconnect(moduleChangeHandler)
            while moduleBox.count() > 0:
                moduleBox.removeItem(0)
            for module in controlTypes[typename]['module_list']:
                moduleBox.addItem(module)
            defaultModule = controlTypes[typename]['default_option']
            moduleBox.currentIndexChanged.connect(moduleChangeHandler)
            if defaultModule != 'none':
                moduleBox.setCurrentIndex(moduleBox.findText(defaultModule))
            else:
                moduleBox.setCurrentIndex(0)
        loadControlType('All')
        controlTypeBox.currentIndexChanged.connect(lambda: loadControlType(controlTypeBox.currentText()))

        # Restore previous state on start:
        if 'module' in initialControlState:
            module = moduleBox.findText(initialControlState['module'])
            if module is not None:
                moduleBox.setCurrentIndex(module)
        if 'model' in initialControlState:
            model = modelBox.findText(initialControlState['model'])
            if model is not None:
                modelBox.setCurrentIndex(model)
        if 'low_vram' in initialControlState:
            vramCheck.setChecked(initialControlState['low_vram'])
        if 'pixel_perfect' in initialControlState:
            vramCheck.setChecked(initialControlState['pixel_perfect'])

        # Setup "Enabled" control:
        def setEnabled(isChecked):
            if enabledCheck.isChecked() != isChecked:
                enabledCheck.setChecked(isChecked)
            for widget in [controlTypeBox, moduleBox, modelBox, optionsBox]:
                widget.setEnabled(isChecked)
            writeStateToConfig()
        setEnabled(len(initialControlState) > 0)
        enabledCheck.stateChanged.connect(setEnabled) 
        self.showButtonBar(True)




