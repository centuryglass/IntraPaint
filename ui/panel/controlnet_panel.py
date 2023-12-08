from PyQt5.QtWidgets import *
from ui.widget.collapsible_box import CollapsibleBox

class ControlnetPanel(CollapsibleBox)

    def __init__(self, config, controlTypes, moduleDetail, title = "ControlNet"):
        super().__init__(title=title)
        # Build layout:
        layout = QVBoxLayout()
        self.setContentLayout(layout)

        enabledCheck = QCheckBox()
        #TODO: add label
        layout.addWidget(0, enabledCheck)
        
        
        controlTypeBox = QComboBox(self)
        #TODO: add label
        for control in controlTypes:
            controlTypeBox.addItem(control)
        controlTypeBox.setCurrentIndex(controlTypeBox.findText("All"))
        layout.addWidget(controlTypeBox)
        
        #TODO: add label
        moduleBox = QComboBox(self)
        layout.addWidget(moduleBox)

        #TODO: add label
        modelBox = QComboBox(self)
        layout.addWidget(modelBox)

        optionsBox = CollapsibleBox("Options")
        optionsLayout = QVBoxLayout()
        optionsBox.setContentLayout(optionsLayout)
        layout.addWidget(optionsBox)
        optionList = {}

        #TODO: define writeStateToConfig:

        # Setup "Enabled" control:
        def setEnabled(isChecked):
            controlTypeBox.setEnabled(isChecked)
            moduleBox.setEnabled(isChecked)
            modelBox.setEnabled(isChecked)
            # TODO: writeStateToConfig
                
        enabledCheck.stateChanged.connect(setEnabled) 
        enabledCheck.setChecked(False)

        # Setup control types, update other boxes on change:
        def loadControlType(typename):
            while moduleBox.count() > 0:
                moduleBox.removeItem(0)
            for module in controlTypes[typename]['module_list']:
                moduleBox.addItem(module)
            defaultModule = controlTypes[typename]['default_option']
            if defaultModule != 'none':
                moduleBox.setCurrentIndex(moduleBox.findText(defaultModule))

            while modelBox.count() > 0:
                modelBox.removeItem(0)
            for model in controlTypes[typename]['model_list']:
                modelBox.addItem(model)
            defaultModel = controlTypes[typename]['default_model']
            if defaultModel != 'none':
                modelBox.setCurrentIndex(modelBox.findText(defaultModel))
        loadControlType('All')
        controlTypeBox.currentIndexChanged.connect(lambda: loadControlType(controlTypeBox.currentText()))


        #TODO: on model change, writeStateToConfig

        #TODO: on module change:
        # clear optionList, optionsBox
        # Iterate through moduleDetail[selection]:
        #   create widget
        #   save default to OptionList
        #   add onchange updating optionList, calling writeStateToConfig
        # writeStateToConfig()




