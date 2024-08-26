<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en_US">
  <context>
    <name>config.config</name>
    <message>
      <location filename="../../src/config/config.py" line="36"/>
      <source>Config definition file not found at {definition_path}</source>
      <translation>Config definition file not found at {definition_path}</translation>
    </message>
    <message>
      <location filename="../../src/config/config.py" line="37"/>
      <source>Config value definition for {key} had invalid data type {value_type}</source>
      <translation>Config value definition for {key} had invalid data type {value_type}</translation>
    </message>
    <message>
      <location filename="../../src/config/config.py" line="38"/>
      <source>Loading {key} failed: {err}</source>
      <translation>Loading {key} failed: {err}</translation>
    </message>
    <message>
      <location filename="../../src/config/config.py" line="39"/>
      <source>Reading JSON config definitions failed: {err}</source>
      <translation>Reading JSON config definitions failed: {err}</translation>
    </message>
    <message>
      <location filename="../../src/config/config.py" line="40"/>
      <source>Reading JSON config values failed: {err}</source>
      <translation>Reading JSON config values failed: {err}</translation>
    </message>
    <message>
      <location filename="../../src/config/config.py" line="41"/>
      <source>Tried to access unknown config value "{key}"</source>
      <translation>Tried to access unknown config value "{key}"</translation>
    </message>
    <message>
      <location filename="../../src/config/config.py" line="42"/>
      <source>Tried to get key code "{key}", found "{code_string}"</source>
      <translation>Tried to get key code "{key}", found "{code_string}"</translation>
    </message>
    <message>
      <location filename="../../src/config/config.py" line="43"/>
      <source>Tried to add duplicate config entry for key "{key}"</source>
      <translation>Tried to add duplicate config entry for key "{key}"</translation>
    </message>
  </context>
  <context>
    <name>config.config_entry</name>
    <message>
      <location filename="../../src/config/config_entry.py" line="24"/>
      <source>Tried to set "{key}.{inner_key}" to value "{value}", but {key} is type "{type_name}"</source>
      <translation>Tried to set "{key}.{inner_key}" to value "{value}", but {key} is type "{type_name}"</translation>
    </message>
    <message>
      <location filename="../../src/config/config_entry.py" line="26"/>
      <source>Tried to read {key}.{inner_key} from type {type_name}</source>
      <translation>Tried to read {key}.{inner_key} from type {type_name}</translation>
    </message>
    <message>
      <location filename="../../src/config/config_entry.py" line="27"/>
      <source>Config value "{key}" does not have an associated options list</source>
      <translation>Config value "{key}" does not have an associated options list</translation>
    </message>
    <message>
      <location filename="../../src/config/config_entry.py" line="28"/>
      <source>unexpected type:</source>
      <translation>unexpected type:</translation>
    </message>
    <message>
      <location filename="../../src/config/config_entry.py" line="29"/>
      <source>{key}: missing value</source>
      <translation>{key}: missing value</translation>
    </message>
  </context>
  <context>
    <name>config.key_config</name>
    <message>
      <location filename="../../src/config/key_config.py" line="27"/>
      <source>Warning</source>
      <translation>Warning</translation>
    </message>
    <message>
      <location filename="../../src/config/key_config.py" line="28"/>
      <source>Errors found in configurable key bindings:
</source>
      <translation>Errors found in configurable key bindings:
</translation>
    </message>
    <message>
      <location filename="../../src/config/key_config.py" line="29"/>
      <source>Invalid key for speed_modifier option: found {speed_modifier}, expected {modifiers}</source>
      <translation>Invalid key for speed_modifier option: found {speed_modifier}, expected {modifiers}</translation>
    </message>
    <message>
      <location filename="../../src/config/key_config.py" line="30"/>
      <source>"{key_binding_name}" should be a modifier key (Ctrl, Alt, Shift), found "{key_value}"</source>
      <translation>"{key_binding_name}" should be a modifier key (Ctrl, Alt, Shift), found "{key_value}"</translation>
    </message>
    <message>
      <location filename="../../src/config/key_config.py" line="31"/>
      <source>"{key_binding_name}" assigned unexpected modifier key "{key_value}", this may cause problems</source>
      <translation>"{key_binding_name}" assigned unexpected modifier key "{key_value}", this may cause problems</translation>
    </message>
    <message>
      <location filename="../../src/config/key_config.py" line="33"/>
      <source>"{key_binding_name}" value "{key_value}" is not a recognized key</source>
      <translation>"{key_binding_name}" value "{key_value}" is not a recognized key</translation>
    </message>
    <message>
      <location filename="../../src/config/key_config.py" line="34"/>
      <source>"{key_binding_name}" is set to {key_value}, but {speed_modifier} is the speed modifier key. This will cause {key_str} to always operate at 10x speed.</source>
      <translation>"{key_binding_name}" is set to {key_value}, but {speed_modifier} is the speed modifier key. This will cause {key_str} to always operate at 10x speed.</translation>
    </message>
    <message>
      <location filename="../../src/config/key_config.py" line="37"/>
      <source>{key_binding_name} is not set</source>
      <translation>{key_binding_name} is not set</translation>
    </message>
    <message>
      <location filename="../../src/config/key_config.py" line="38"/>
      <source>Key "{key_str}" is shared between options {key_names}, some keys may not work.</source>
      <translation>Key "{key_str}" is shared between options {key_names}, some keys may not work.</translation>
    </message>
    <message>
      <location filename="../../src/config/key_config.py" line="39"/>
      <source>{key_binding_name} (with speed modifier)</source>
      <translation>{key_binding_name} (with speed modifier)</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="3"/>
      <source>Key Speed Modifier:</source>
      <translation>Key Speed Modifier:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="5"/>
      <source>If this key is held, movement/zoom/pan/scroll/etc. operations will go faster. (avoid changing, Shift and Ctrl are the only other working options and those cause various conflicts.)</source>
      <translation>If this key is held, movement/zoom/pan/scroll/etc. operations will go faster. (avoid changing, Shift and Ctrl are the only other working options and those cause various conflicts.)</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="11"/>
      <source>Line Drawing Modifier:</source>
      <translation>Line Drawing Modifier:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="13"/>
      <source>When held, drawing tools will draw a line from the last point.</source>
      <translation>When held, drawing tools will draw a line from the last point.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="19"/>
      <source>Fixed Angle Modifier:</source>
      <translation>Fixed Angle Modifier:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="21"/>
      <source>When held, drawing tools will be constrained to a fixed angle.</source>
      <translation>When held, drawing tools will be constrained to a fixed angle.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="27"/>
      <source>Pan View Modifier:</source>
      <translation>Pan View Modifier:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="29"/>
      <source>When held, click and drag to pan the image view</source>
      <translation>When held, click and drag to pan the image view</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="35"/>
      <source>Fixed Aspect Ratio Modifier:</source>
      <translation>Fixed Aspect Ratio Modifier:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="37"/>
      <source>When held, shape and transform tools will keep a fixed aspect ratio.</source>
      <translation>When held, shape and transform tools will keep a fixed aspect ratio.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="43"/>
      <source>Color Picker Override Modifier:</source>
      <translation>Color Picker Override Modifier:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="45"/>
      <source>When held, temporarily switch from the brush or fill tool to the color picker.</source>
      <translation>When held, temporarily switch from the brush or fill tool to the color picker.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="51"/>
      <source>Zoom in:</source>
      <translation>Zoom in:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="53"/>
      <source>Zoom in on image content</source>
      <translation>Zoom in on image content</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="59"/>
      <source>Zoom out:</source>
      <translation>Zoom out:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="61"/>
      <source>Zoom out on image content</source>
      <translation>Zoom out on image content</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="67"/>
      <source>Toggle zoom:</source>
      <translation>Toggle zoom:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="69"/>
      <source>Switch between close-up and zoomed out views</source>
      <translation>Switch between close-up and zoomed out views</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="75"/>
      <source>Pan left:</source>
      <translation>Pan left:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="77"/>
      <source>Scroll the image view left</source>
      <translation>Scroll the image view left</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="83"/>
      <source>Pan right:</source>
      <translation>Pan right:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="85"/>
      <source>Scroll the image view right</source>
      <translation>Scroll the image view right</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="91"/>
      <source>Pan up:</source>
      <translation>Pan up:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="93"/>
      <source>Scroll the image view up</source>
      <translation>Scroll the image view up</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="99"/>
      <source>Pan down:</source>
      <translation>Pan down:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="101"/>
      <source>Scroll the image view down</source>
      <translation>Scroll the image view down</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="107"/>
      <source>Move left:</source>
      <translation>Move left:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="109"/>
      <source>Move the image generation area left</source>
      <translation>Move the image generation area left</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="115"/>
      <source>Move right:</source>
      <translation>Move right:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="117"/>
      <source>Move the image generation area right</source>
      <translation>Move the image generation area right</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="123"/>
      <source>Move up:</source>
      <translation>Move up:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="125"/>
      <source>Move the image generation area up</source>
      <translation>Move the image generation area up</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="131"/>
      <source>Move down:</source>
      <translation>Move down:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="133"/>
      <source>Move the image generation area down</source>
      <translation>Move the image generation area down</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="139"/>
      <source>Increase brush size:</source>
      <translation>Increase brush size:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="141"/>
      <source>Increase the size of the active brush</source>
      <translation>Increase the size of the active brush</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="147"/>
      <source>Decrease brush size:</source>
      <translation>Decrease brush size:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="141"/>
      <source>Increase the size of the active brush</source>
      <translation>Increase the size of the active brush</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="155"/>
      <source>Switch to the brush tool:</source>
      <translation>Switch to the brush tool:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="157"/>
      <source>Activate the brush tool to paint into the image.</source>
      <translation>Activate the brush tool to paint into the image.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="163"/>
      <source>Switch to the draw tool:</source>
      <translation>Switch to the draw tool:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="165"/>
      <source>Activate the draw tool to draw into the image.</source>
      <translation>Activate the draw tool to draw into the image.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="171"/>
      <source>Switch to the color picker tool:</source>
      <translation>Switch to the color picker tool:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="173"/>
      <source>Activate the color picker tool to change the brush color.</source>
      <translation>Activate the color picker tool to change the brush color.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="179"/>
      <source>Switch to the layer transformation tool:</source>
      <translation>Switch to the layer transformation tool:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="181"/>
      <source>Activate the layer transformation tool to move, scale, or rotate layers.</source>
      <translation>Activate the layer transformation tool to move, scale, or rotate layers.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="187"/>
      <source>Switch to the selection tool:</source>
      <translation>Switch to the selection tool:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="189"/>
      <source>Activate the selection tool to mark areas for editing.</source>
      <translation>Activate the selection tool to mark areas for editing.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="195"/>
      <source>Switch to the area selection tool:</source>
      <translation>Switch to the area selection tool:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="197"/>
      <source>Activate the area selection tool to mark areas for editing.</source>
      <translation>Activate the area selection tool to mark areas for editing.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="203"/>
      <source>Switch to the shape selection tool:</source>
      <translation>Switch to the shape selection tool:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="205"/>
      <source>Activate the shape selection tool to mark areas for editing.</source>
      <translation>Activate the shape selection tool to mark areas for editing.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="211"/>
      <source>Switch to the fill tool:</source>
      <translation>Switch to the fill tool:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="213"/>
      <source>Activate the fill tool to fill areas with solid colors.</source>
      <translation>Activate the fill tool to fill areas with solid colors.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="219"/>
      <source>Switch to the text tool:</source>
      <translation>Switch to the text tool:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="221"/>
      <source>Activate the text tool.</source>
      <translation>Activate the text tool.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="227"/>
      <source>Switch to the image generation area selection tool:</source>
      <translation>Switch to the image generation area selection tool:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="229"/>
      <source>Activate the generation area tool to pick an image area for AI image generation.</source>
      <translation>Activate the generation area tool to pick an image area for AI image generation.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="235"/>
      <source>Rotate layer counter-clockwise:</source>
      <translation>Rotate layer counter-clockwise:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="237"/>
      <source>Rotates the layer when the layer transformation tool is active</source>
      <translation>Rotates the layer when the layer transformation tool is active</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="243"/>
      <source>Rotate layer clockwise:</source>
      <translation>Rotate layer clockwise:</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="237"/>
      <source>Rotates the layer when the layer transformation tool is active</source>
      <translation>Rotates the layer when the layer transformation tool is active</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="251"/>
      <source>Tool action hotkey</source>
      <translation>Tool action hotkey</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="253"/>
      <source>Performs some context-specific action based on the active tool.</source>
      <translation>Performs some context-specific action based on the active tool.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="259"/>
      <source>New Image</source>
      <translation>New Image</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="261"/>
      <source>Open a new image for editing.</source>
      <translation>Open a new image for editing.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="267"/>
      <source>Save</source>
      <translation>Save</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="269"/>
      <source>Save current image as .png or .ora.</source>
      <translation>Save current image as .png or .ora.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="275"/>
      <source>Save as</source>
      <translation>Save as</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="277"/>
      <source>Save current image as .png or .inpt at a new file path.</source>
      <translation>Save current image as .png or .inpt at a new file path.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="283"/>
      <source>Load Image</source>
      <translation>Load Image</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="285"/>
      <source>Open an image file for editing.</source>
      <translation>Open an image file for editing.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="291"/>
      <source>Open as Layers</source>
      <translation>Open as Layers</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="293"/>
      <source>Open images as new layers.</source>
      <translation>Open images as new layers.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="299"/>
      <source>Reload</source>
      <translation>Reload</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="301"/>
      <source>Reload the image from its file.</source>
      <translation>Reload the image from its file.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="307"/>
      <source>Quit</source>
      <translation>Quit</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="309"/>
      <source>Closes the application.</source>
      <translation>Closes the application.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="315"/>
      <source>Undo</source>
      <translation>Undo</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="317"/>
      <source>Undo the last action taken</source>
      <translation>Undo the last action taken</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="323"/>
      <source>Redo</source>
      <translation>Redo</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="325"/>
      <source>Re-apply the last action reversed with undo.</source>
      <translation>Re-apply the last action reversed with undo.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="331"/>
      <source>Cut</source>
      <translation>Cut</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="333"/>
      <source>Remove selected image content in the active layer.</source>
      <translation>Remove selected image content in the active layer.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="339"/>
      <source>Copy</source>
      <translation>Copy</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="341"/>
      <source>Copy selected image content in the active layer.</source>
      <translation>Copy selected image content in the active layer.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="347"/>
      <source>Paste</source>
      <translation>Paste</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="349"/>
      <source>Insert copied image data into a new layer.</source>
      <translation>Insert copied image data into a new layer.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="355"/>
      <source>Clear</source>
      <translation>Clear</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="357"/>
      <source>Delete selected image content in the active layer.</source>
      <translation>Delete selected image content in the active layer.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="363"/>
      <source>Resize canvas</source>
      <translation>Resize canvas</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="365"/>
      <source>Change the image size without scaling layers.</source>
      <translation>Change the image size without scaling layers.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="371"/>
      <source>Scale image</source>
      <translation>Scale image</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="373"/>
      <source>Scale image content to a new size.</source>
      <translation>Scale image content to a new size.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="379"/>
      <source>Resize image to content</source>
      <translation>Resize image to content</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="381"/>
      <source>Resize the image to fit all layers</source>
      <translation>Resize the image to fit all layers</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="387"/>
      <source>Update metadata</source>
      <translation>Update metadata</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="389"/>
      <source>Update image metadata that will be saved with the file.</source>
      <translation>Update image metadata that will be saved with the file.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="395"/>
      <source>Generate</source>
      <translation>Generate</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="397"/>
      <source>Start AI image generation.</source>
      <translation>Start AI image generation.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="403"/>
      <source>Select All</source>
      <translation>Select All</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="405"/>
      <source>Select the entire image</source>
      <translation>Select the entire image</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="411"/>
      <source>Deselect All</source>
      <translation>Deselect All</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="413"/>
      <source>Clear the selection</source>
      <translation>Clear the selection</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="419"/>
      <source>Invert selection</source>
      <translation>Invert selection</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="421"/>
      <source>Swap selected and unselected areas</source>
      <translation>Swap selected and unselected areas</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="427"/>
      <source>Select layer content</source>
      <translation>Select layer content</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="429"/>
      <source>Select all non-transparent pixels in the active layer</source>
      <translation>Select all non-transparent pixels in the active layer</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="435"/>
      <source>Expand selection</source>
      <translation>Expand selection</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="437"/>
      <source>Expand the selection bounds</source>
      <translation>Expand the selection bounds</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="443"/>
      <source>Shrink selection</source>
      <translation>Shrink selection</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="445"/>
      <source>Shrink the selection bounds</source>
      <translation>Shrink the selection bounds</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="451"/>
      <source>New layer</source>
      <translation>New layer</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="453"/>
      <source>Create a new layer above the active layer.</source>
      <translation>Create a new layer above the active layer.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="459"/>
      <source>New layer group</source>
      <translation>New layer group</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="461"/>
      <source>Create a new layer group above the active layer.</source>
      <translation>Create a new layer group above the active layer.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="467"/>
      <source>Copy layer</source>
      <translation>Copy layer</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="469"/>
      <source>Create a copy of the active layer.</source>
      <translation>Create a copy of the active layer.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="475"/>
      <source>Delete layer</source>
      <translation>Delete layer</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="477"/>
      <source>Delete the active layer.</source>
      <translation>Delete the active layer.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="483"/>
      <source>Select previous layer</source>
      <translation>Select previous layer</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="485"/>
      <source>Switch to the next layer up.</source>
      <translation>Switch to the next layer up.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="491"/>
      <source>Select next layer</source>
      <translation>Select next layer</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="493"/>
      <source>Switch to the next layer down.</source>
      <translation>Switch to the next layer down.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="499"/>
      <source>Move layer up</source>
      <translation>Move layer up</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="501"/>
      <source>Move the active layer up</source>
      <translation>Move the active layer up</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="507"/>
      <source>Move layer down</source>
      <translation>Move layer down</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="509"/>
      <source>Move the active layer down</source>
      <translation>Move the active layer down</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="515"/>
      <source>Move layer to top</source>
      <translation>Move layer to top</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="517"/>
      <source>Move the active layer above all others</source>
      <translation>Move the active layer above all others</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="523"/>
      <source>Merge layer down</source>
      <translation>Merge layer down</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="525"/>
      <source>Merge the active layer with the one below it</source>
      <translation>Merge the active layer with the one below it</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="531"/>
      <source>Layer to image size</source>
      <translation>Layer to image size</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="533"/>
      <source>Expand or crop the active layer to match the image bounds.</source>
      <translation>Expand or crop the active layer to match the image bounds.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="539"/>
      <source>Crop layer to contents</source>
      <translation>Crop layer to contents</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="541"/>
      <source>Crop transparent borders in the active layer.</source>
      <translation>Crop transparent borders in the active layer.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="547"/>
      <source>Mirror layer horizontally</source>
      <translation>Mirror layer horizontally</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="549"/>
      <source>Flip layer content horizontally</source>
      <translation>Flip layer content horizontally</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="554"/>
      <source>Mirror layer vertically</source>
      <translation>Mirror layer vertically</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="556"/>
      <source>Flip layer content vertically</source>
      <translation>Flip layer content vertically</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="561"/>
      <source>Rotate layer 90° CW</source>
      <translation>Rotate layer 90° CW</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="563"/>
      <source>Rotate the active layer 90 degrees clockwise.</source>
      <translation>Rotate the active layer 90 degrees clockwise.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="568"/>
      <source>Rotate layer 90° CCW</source>
      <translation>Rotate layer 90° CCW</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="570"/>
      <source>Rotate the active layer 90 degrees counter-clockwise.</source>
      <translation>Rotate the active layer 90 degrees counter-clockwise.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="576"/>
      <source>Show layer window</source>
      <translation>Show layer window</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="578"/>
      <source>Open the image layer panel in a new window.</source>
      <translation>Open the image layer panel in a new window.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="584"/>
      <source>Settings</source>
      <translation>Settings</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="586"/>
      <source>Open the application settings window.</source>
      <translation>Open the application settings window.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="592"/>
      <source>LCM Mode</source>
      <translation>LCM Mode</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="594"/>
      <source>Apply appropriate settings for the LCM LORA.</source>
      <translation>Apply appropriate settings for the LCM LORA.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="600"/>
      <source>Show Image Window</source>
      <translation>Show Image Window</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="602"/>
      <source>Open a new window showing the edited image.</source>
      <translation>Open a new window showing the edited image.</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="608"/>
      <source>Select Image Generator</source>
      <translation>Select Image Generator</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="610"/>
      <source>Selects an AI image generator</source>
      <translation>Selects an AI image generator</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="616"/>
      <source>RGBA Color Balance</source>
      <translation>RGBA Color Balance</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="618"/>
      <source>Adjust RGBA color channels</source>
      <translation>Adjust RGBA color channels</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="624"/>
      <source>Brightness/Contrast</source>
      <translation>Brightness/Contrast</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="626"/>
      <source>Adjust image brightness/contrast</source>
      <translation>Adjust image brightness/contrast</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="632"/>
      <source>Blur</source>
      <translation>Blur</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="634"/>
      <source>Image blurring</source>
      <translation>Image blurring</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="640"/>
      <source>Sharpen</source>
      <translation>Sharpen</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="642"/>
      <source>Sharpen image details</source>
      <translation>Sharpen image details</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="648"/>
      <source>Posterize</source>
      <translation>Posterize</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="650"/>
      <source>Simplify layer color palette</source>
      <translation>Simplify layer color palette</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="656"/>
      <source>View saved prompt styles</source>
      <translation>View saved prompt styles</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="658"/>
      <source>Access saved stable-diffusion prompt styles</source>
      <translation>Access saved stable-diffusion prompt styles</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="664"/>
      <source>View Lora models</source>
      <translation>View Lora models</translation>
    </message>
    <message>
      <location filename="../config/key_config_definitions.json" line="666"/>
      <source>Access available Lora models.</source>
      <translation>Access available Lora models.</translation>
    </message>
  </context>
  <context>
    <name>controller.app_controller</name>
    <message>
      <location filename="../../src/controller/app_controller.py" line="84"/>
      <source>File</source>
      <translation>File</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="85"/>
      <source>Edit</source>
      <translation>Edit</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="86"/>
      <source>Image</source>
      <translation>Image</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="87"/>
      <source>Selection</source>
      <translation>Selection</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="88"/>
      <source>Layers</source>
      <translation>Layers</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="89"/>
      <source>Tools</source>
      <translation>Tools</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="90"/>
      <source>Filters</source>
      <translation>Filters</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="92"/>
      <source>Move</source>
      <translation>Move</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="93"/>
      <source>Select</source>
      <translation>Select</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="94"/>
      <source>Transform</source>
      <translation>Transform</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="96"/>
      <source>Loading image generator failed</source>
      <translation>Loading image generator failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="97"/>
      <source>Unable to load the {generator_name} image generator</source>
      <translation>Unable to load the {generator_name} image generator</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="98"/>
      <source>Quit now?</source>
      <translation>Quit now?</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="99"/>
      <source>All unsaved changes will be lost.</source>
      <translation>All unsaved changes will be lost.</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="100"/>
      <source>Create new image?</source>
      <translation>Create new image?</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="108"/>
      <location filename="../../src/controller/app_controller.py" line="101"/>
      <source>This will discard all unsaved changes.</source>
      <translation>This will discard all unsaved changes.</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="113"/>
      <location filename="../../src/controller/app_controller.py" line="102"/>
      <source>Save failed</source>
      <translation>Save failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="103"/>
      <source>Open failed</source>
      <translation>Open failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="104"/>
      <source>Reload failed</source>
      <translation>Reload failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="105"/>
      <source>Image path "{file_path}" is not a valid image file.</source>
      <translation>Image path "{file_path}" is not a valid image file.</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="106"/>
      <source>Enter an image path or click "Open Image" first.</source>
      <translation>Enter an image path or click "Open Image" first.</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="107"/>
      <source>Reload image?</source>
      <translation>Reload image?</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="109"/>
      <source>Metadata updated</source>
      <translation>Metadata updated</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="110"/>
      <source>On save, current image generation parameters will be stored within the image</source>
      <translation>On save, current image generation parameters will be stored within the image</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="111"/>
      <source>Resize failed</source>
      <translation>Resize failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="112"/>
      <source>Inpainting failure</source>
      <translation>Inpainting failure</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="114"/>
      <source>Failed</source>
      <translation>Failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="115"/>
      <source>Existing image generation operation not yet finished, wait a little longer.</source>
      <translation>Existing image generation operation not yet finished, wait a little longer.</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="116"/>
      <source>Settings not supported in this mode.</source>
      <translation>Settings not supported in this mode.</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="117"/>
      <source>Failed to open settings</source>
      <translation>Failed to open settings</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="118"/>
      <source>Opening layers failed</source>
      <translation>Opening layers failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="119"/>
      <source>Could not open the following images: </source>
      <translation>Could not open the following images: </translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="121"/>
      <source>Save image generation metadata?</source>
      <translation>Save image generation metadata?</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="122"/>
      <source>No image metadata is cached, would you like to save image generation parameters to this image?</source>
      <translation>No image metadata is cached, would you like to save image generation parameters to this image?</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="124"/>
      <source>Update image generation metadata?</source>
      <translation>Update image generation metadata?</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="125"/>
      <source>Image generation parameters have changed, would you like this image to be saved with the most recent values?</source>
      <translation>Image generation parameters have changed, would you like this image to be saved with the most recent values?</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="129"/>
      <source>Image saved without layer data</source>
      <translation>Image saved without layer data</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="130"/>
      <source>To save layer data, images must be saved in .ora format.</source>
      <translation>To save layer data, images must be saved in .ora format.</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="132"/>
      <source>Image saved without full transparency</source>
      <translation>Image saved without full transparency</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="133"/>
      <source>To preserve transparency, save using one of the following file formats: {alpha_formats}</source>
      <translation>To preserve transparency, save using one of the following file formats: {alpha_formats}</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="136"/>
      <source>Image saved without image generation metadata</source>
      <translation>Image saved without image generation metadata</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="137"/>
      <source>To preserve image generation metadata, save using one of the following file formats: {metadata_formats}</source>
      <translation>To preserve image generation metadata, save using one of the following file formats: {metadata_formats}</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="140"/>
      <source>Image saved in a write-only format</source>
      <translation>Image saved in a write-only format</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="141"/>
      <source>IntraPaint can write images in the {file_format} format, but cannot load them. Use another file format if you want to be able to load this image in IntraPaint again.</source>
      <translation>IntraPaint can write images in the {file_format} format, but cannot load them. Use another file format if you want to be able to load this image in IntraPaint again.</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="144"/>
      <source>Image saved in a format that changes size</source>
      <translation>Image saved in a format that changes size</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="145"/>
      <source>The image is {width_px}x{height_px}, but the {file_format} format saves all images at {saved_width_px}x{saved_height_px} resolution. Use another file format if you want to preserve the original image size.</source>
      <translation>The image is {width_px}x{height_px}, but the {file_format} format saves all images at {saved_width_px}x{saved_height_px} resolution. Use another file format if you want to preserve the original image size.</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="149"/>
      <source>Image saved without color</source>
      <translation>Image saved without color</translation>
    </message>
    <message>
      <location filename="../../src/controller/app_controller.py" line="150"/>
      <source>The {file_format} format saves the image without color. Use another format if you want to preserve image colors.</source>
      <translation>The {file_format} format saves the image without color. Use another format if you want to preserve image colors.</translation>
    </message>
  </context>
  <context>
    <name>controller.image_generation.glid3_webservice_generator</name>
    <message>
      <location filename="../../src/controller/image_generation/glid3_webservice_generator.py" line="33"/>
      <source>GLID-3-XL image generation server</source>
      <translation>GLID-3-XL image generation server</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/glid3_webservice_generator.py" line="34"/>
      <source>&lt;h2&gt;GLID-3-XL server setup&lt;/h2&gt;&lt;p&gt;NOTE: Because GLID-3-XL is mainly a historical curiosity at this point, few steps have been taken to simplify the setup process. As the software involved becomes increasingly outdated, further steps may be necessary to get this generator to work.&lt;/p&gt;&lt;p&gt;The original preferred way to use this mode relied on a Google Colab notebook, found &lt;a href="https://colab.research.google.com/github/centuryglass/IntraPaint/blob/colab-refactor/colabFiles/IntraPaint_colab_server.ipynb"&gt;here&lt;/a&gt;. This approach is discouraged by Google and no longer seems to work using the free tier of Google Colab. It may or may not work on the paid tier, or if additional steps are taken to replace the ngrok service used to handle external connections. Steps for running the server on your own machine are as follows:&lt;ol&gt;&lt;li&gt;Make sure the server system has a NVIDIA GPU with at least 8GB of VRAM. Other GPUsor slightly less memory may work, but are not tested.&lt;/li&gt;&lt;li&gt;Install required dependencies:&lt;/li&gt;&lt;ol&gt;&lt;li&gt;&lt;a href="https://www.python.org/"&gt;Python3&lt;/a&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://git-scm.com/"&gt;Git&lt;/a&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://developer.nvidia.com/cuda-toolkit"&gt;CUDA&lt;/a&gt; (if using a NVIDIA graphics card)&lt;/li&gt;&lt;li&gt;&lt;a href="https://www.anaconda.com/download/"&gt;Anaconda&lt;/a&gt;&lt;/li&gt;&lt;/ol&gt;&lt;li&gt;Depending on your system, you may need to take extra steps to add Python, Git, and Anaconda to your system path, or perform other configuration steps. Refer to the sites linked above for full documentation.&lt;/li&gt;&lt;li&gt;In a terminal window, run `&lt;code&gt;conda create -n intrapaint-server&lt;/code&gt;`, then `&lt;code&gt;conda activate intrapaint-server&lt;/code&gt;` to prepare to install additional dependencies.&lt;/li&gt;&lt;li&gt;Next run `&lt;code&gt;git clone https://github.com/centuryglass/IntraPaint.git&lt;/code&gt;` to download the full IntraPaint repository, then change directory to the new IntraPaint folder that this creates.&lt;/li&gt;&lt;li&gt;Within the the terminal in the IntraPaint directory with the `intrapaint-server`environment active, install the appropriate versions of torch and torchvision found &lt;a href="https://pytorch.org/get-started/locally/"&gt;here&lt;/a&gt;.&lt;li&gt;Run `&lt;code&gt;conda install pip&lt;/code&gt;` to make sure the environment has its own copy of the python package manager.&lt;/li&gt;&lt;li&gt;Run `&lt;code&gt;pip install -r requirements-glid.txt&lt;/code&gt;` to install additional dependencies.&lt;/li&gt;&lt;li&gt;Run the following Git commands to add two other required dependencies:&lt;li&gt;&lt;ol&gt;&lt;li&gt;`&lt;code&gt;git clone https://github.com/CompVis/taming-transformers.git&lt;/code&gt;`&lt;/li&gt;&lt;li&gt;`&lt;code&gt;git clone https://github.com/CompVis/latent-diffusion.git&lt;/code&gt;`&lt;/li&gt;&lt;li&gt;Download one or more GLID-3-XL inpainting models, and place them in the IntraPaint/models/ directory. These are the main options available:&lt;li&gt;&lt;ol&gt;&lt;li&gt;&lt;a href="https://dall-3.com/models/glid-3-xl/"&gt;inpaint.pt&lt;/a&gt;, the original GLID-3-XL inpainting model&lt;/li&gt;&lt;li&gt;&lt;a href="https://huggingface.co/laion/ongo/resolve/main/ongo.pt&gt;ongo.pt&lt;/a&gt;, trained by LAION on paintings from the Wikiart dataset&lt;/li&gt;&lt;li&gt;&lt;a href="https://huggingface.co/laion/erlich/resolve/main/model/ema_0.9999_120000.pt"&gt;erlich.pt&lt;/a&gt;, trained on the LAION large logo dataset&lt;/li&gt;&lt;/ol&gt;&lt;li&gt;Start the server by running &lt;code&gt;python IntraPaint_server.py&lt;/code&gt;. If you are using a model other than the default inpaint.pt, instead run `&lt;code&gt;python Intrapaint_server.py --model_path models/model.pt&lt;/code&gt;`, replacing "model.pt" with the file name of whatever model you are using.&lt;/li&gt;&lt;li&gt;If the setup was successful, something like "* Running on http://192.168.0.XXX:5555" will be printed in the console  after a short delay. You can now activate this generator, entering that URL when prompted.</source>
      <translation>&lt;h2&gt;GLID-3-XL server setup&lt;/h2&gt;&lt;p&gt;NOTE: Because GLID-3-XL is mainly a historical curiosity at this point, few steps have been taken to simplify the setup process. As the software involved becomes increasingly outdated, further steps may be necessary to get this generator to work.&lt;/p&gt;&lt;p&gt;The original preferred way to use this mode relied on a Google Colab notebook, found &lt;a href="https://colab.research.google.com/github/centuryglass/IntraPaint/blob/colab-refactor/colabFiles/IntraPaint_colab_server.ipynb"&gt;here&lt;/a&gt;. This approach is discouraged by Google and no longer seems to work using the free tier of Google Colab. It may or may not work on the paid tier, or if additional steps are taken to replace the ngrok service used to handle external connections. Steps for running the server on your own machine are as follows:&lt;ol&gt;&lt;li&gt;Make sure the server system has a NVIDIA GPU with at least 8GB of VRAM. Other GPUsor slightly less memory may work, but are not tested.&lt;/li&gt;&lt;li&gt;Install required dependencies:&lt;/li&gt;&lt;ol&gt;&lt;li&gt;&lt;a href="https://www.python.org/"&gt;Python3&lt;/a&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://git-scm.com/"&gt;Git&lt;/a&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://developer.nvidia.com/cuda-toolkit"&gt;CUDA&lt;/a&gt; (if using a NVIDIA graphics card)&lt;/li&gt;&lt;li&gt;&lt;a href="https://www.anaconda.com/download/"&gt;Anaconda&lt;/a&gt;&lt;/li&gt;&lt;/ol&gt;&lt;li&gt;Depending on your system, you may need to take extra steps to add Python, Git, and Anaconda to your system path, or perform other configuration steps. Refer to the sites linked above for full documentation.&lt;/li&gt;&lt;li&gt;In a terminal window, run `&lt;code&gt;conda create -n intrapaint-server&lt;/code&gt;`, then `&lt;code&gt;conda activate intrapaint-server&lt;/code&gt;` to prepare to install additional dependencies.&lt;/li&gt;&lt;li&gt;Next run `&lt;code&gt;git clone https://github.com/centuryglass/IntraPaint.git&lt;/code&gt;` to download the full IntraPaint repository, then change directory to the new IntraPaint folder that this creates.&lt;/li&gt;&lt;li&gt;Within the the terminal in the IntraPaint directory with the `intrapaint-server`environment active, install the appropriate versions of torch and torchvision found &lt;a href="https://pytorch.org/get-started/locally/"&gt;here&lt;/a&gt;.&lt;li&gt;Run `&lt;code&gt;conda install pip&lt;/code&gt;` to make sure the environment has its own copy of the python package manager.&lt;/li&gt;&lt;li&gt;Run `&lt;code&gt;pip install -r requirements-glid.txt&lt;/code&gt;` to install additional dependencies.&lt;/li&gt;&lt;li&gt;Run the following Git commands to add two other required dependencies:&lt;li&gt;&lt;ol&gt;&lt;li&gt;`&lt;code&gt;git clone https://github.com/CompVis/taming-transformers.git&lt;/code&gt;`&lt;/li&gt;&lt;li&gt;`&lt;code&gt;git clone https://github.com/CompVis/latent-diffusion.git&lt;/code&gt;`&lt;/li&gt;&lt;li&gt;Download one or more GLID-3-XL inpainting models, and place them in the IntraPaint/models/ directory. These are the main options available:&lt;li&gt;&lt;ol&gt;&lt;li&gt;&lt;a href="https://dall-3.com/models/glid-3-xl/"&gt;inpaint.pt&lt;/a&gt;, the original GLID-3-XL inpainting model&lt;/li&gt;&lt;li&gt;&lt;a href="https://huggingface.co/laion/ongo/resolve/main/ongo.pt&gt;ongo.pt&lt;/a&gt;, trained by LAION on paintings from the Wikiart dataset&lt;/li&gt;&lt;li&gt;&lt;a href="https://huggingface.co/laion/erlich/resolve/main/model/ema_0.9999_120000.pt"&gt;erlich.pt&lt;/a&gt;, trained on the LAION large logo dataset&lt;/li&gt;&lt;/ol&gt;&lt;li&gt;Start the server by running &lt;code&gt;python IntraPaint_server.py&lt;/code&gt;. If you are using a model other than the default inpaint.pt, instead run `&lt;code&gt;python Intrapaint_server.py --model_path models/model.pt&lt;/code&gt;`, replacing "model.pt" with the file name of whatever model you are using.&lt;/li&gt;&lt;li&gt;If the setup was successful, something like "* Running on http://192.168.0.XXX:5555" will be printed in the console  after a short delay. You can now activate this generator, entering that URL when prompted.</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/glid3_webservice_generator.py" line="92"/>
      <source>&lt;h2&gt;Colab server setup&lt;/h2&gt;&lt;p&gt;This is the easier way to set up this mode. It does not require a powerful GPU, but it does require an internet connection and a Google account.&lt;/p&gt;&lt;ol&gt;&lt;li&gt;You'll need a free ngrok account to handle the connection between IntraPaint and the Colab Notebook, sign up for that at &lt;a&gt;https://ngrok.com&lt;/a&gt;&lt;/li&gt;&lt;li&gt;Once you sign up for an ngrok account, log in to their site, find your ngrok AuthToken on &lt;a href="https://dashboard.ngrok.com/get-started/your-authtoken"&gt;this page. Copy it, and save it somewhere safe (e.g. a password manager).&lt;/li&gt;&lt;li&gt;Open the &lt;a href="https://colab.research.google.com/github/centuryglass/IntraPaint/blob/colab-refactor/colabFiles/IntraPaint_colab_server.ipynb"&gt;IntraPaint Server notebook&lt;/a&gt; in Google Colab.&lt;/li&gt;&lt;li&gt;Click "connect" in the upper right, after making sure that the dropdown to the right of the connect button is set to "GPU". If you don't pay for Google Colab there is a chance that a GPU server won't be available, and you'll have to try again later.&lt;/li&gt;&lt;li&gt;By default, the server uses Google Drive to save configuration info to simplify theprocess of starting it again later.  If you don't want to do this, scroll down through the notebook, find where it says "use_google_drive=True", and change it to "use_google_drive=False"&lt;/li&gt;&lt;li&gt;If you have an extra 10GB of space free in Google Drive, you can scroll down, find the line that says "save_missing_models_to_drive=False", and change False to True, and it will start up much more quickly in the future.&lt;/li&gt;&lt;li&gt;Under the "Runtime" menu, select "Run All".  You'll see a popup warning you thatthe notebook is not from Google. Click "Run anyway".&lt;/li&gt;&lt;li&gt;If you chose to use Google Drive, another popup will appear asking you to grantpermission to access Google Drive. Click "Connect to Google Drive", and follow on-screen instructions to allow it to read and write files.&lt;/li&gt;&lt;li&gt;Below the first section of code on the page, a dialog asking you to enter your ngrok AuthToken will appear.  Paste in the auth token you saved earlier, and press enter. If you are using Google Drive, you won't need to do this again the next time you start the server.&lt;/li&gt;&lt;li&gt;Scroll down, and the server URL you need should be printed at the end of all log entries after a few minutes.&lt;/li&gt;&lt;/ol&gt;</source>
      <translation>&lt;h2&gt;Colab server setup&lt;/h2&gt;&lt;p&gt;This is the easier way to set up this mode. It does not require a powerful GPU, but it does require an internet connection and a Google account.&lt;/p&gt;&lt;ol&gt;&lt;li&gt;You'll need a free ngrok account to handle the connection between IntraPaint and the Colab Notebook, sign up for that at &lt;a&gt;https://ngrok.com&lt;/a&gt;&lt;/li&gt;&lt;li&gt;Once you sign up for an ngrok account, log in to their site, find your ngrok AuthToken on &lt;a href="https://dashboard.ngrok.com/get-started/your-authtoken"&gt;this page. Copy it, and save it somewhere safe (e.g. a password manager).&lt;/li&gt;&lt;li&gt;Open the &lt;a href="https://colab.research.google.com/github/centuryglass/IntraPaint/blob/colab-refactor/colabFiles/IntraPaint_colab_server.ipynb"&gt;IntraPaint Server notebook&lt;/a&gt; in Google Colab.&lt;/li&gt;&lt;li&gt;Click "connect" in the upper right, after making sure that the dropdown to the right of the connect button is set to "GPU". If you don't pay for Google Colab there is a chance that a GPU server won't be available, and you'll have to try again later.&lt;/li&gt;&lt;li&gt;By default, the server uses Google Drive to save configuration info to simplify theprocess of starting it again later.  If you don't want to do this, scroll down through the notebook, find where it says "use_google_drive=True", and change it to "use_google_drive=False"&lt;/li&gt;&lt;li&gt;If you have an extra 10GB of space free in Google Drive, you can scroll down, find the line that says "save_missing_models_to_drive=False", and change False to True, and it will start up much more quickly in the future.&lt;/li&gt;&lt;li&gt;Under the "Runtime" menu, select "Run All".  You'll see a popup warning you thatthe notebook is not from Google. Click "Run anyway".&lt;/li&gt;&lt;li&gt;If you chose to use Google Drive, another popup will appear asking you to grantpermission to access Google Drive. Click "Connect to Google Drive", and follow on-screen instructions to allow it to read and write files.&lt;/li&gt;&lt;li&gt;Below the first section of code on the page, a dialog asking you to enter your ngrok AuthToken will appear.  Paste in the auth token you saved earlier, and press enter. If you are using Google Drive, you won't need to do this again the next time you start the server.&lt;/li&gt;&lt;li&gt;Scroll down, and the server URL you need should be printed at the end of all log entries after a few minutes.&lt;/li&gt;&lt;/ol&gt;</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/glid3_webservice_generator.py" line="127"/>
      <source>No GLID-3-XL server address was provided.</source>
      <translation>No GLID-3-XL server address was provided.</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/glid3_webservice_generator.py" line="128"/>
      <source>Could not find a valid GLID-3-XL server at "{server_address}"</source>
      <translation>Could not find a valid GLID-3-XL server at "{server_address}"</translation>
    </message>
  </context>
  <context>
    <name>controller.image_generation.glid3_xl_generator</name>
    <message>
      <location filename="../../src/controller/image_generation/glid3_xl_generator.py" line="46"/>
      <source>GLID-3-XL image generation</source>
      <translation>GLID-3-XL image generation</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/glid3_xl_generator.py" line="47"/>
      <source>&lt;h1&gt;GLID-3-XL&lt;/h1&gt;&lt;p&gt;GLID-3-XL was the best inpainting model available until August 2022, and the first model supported by IntraPaint. IntraPaint continues to support it for the sake of preserving historically interesting image generation models.&lt;h2&gt;Generator capabilities and limits:&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;Requires approximately 8GB of VRAM.&lt;/li&gt;&lt;li&gt;Inpainting is supported at an ideal resolution of 256x256, with limited support for other resolutions.&lt;/li&gt;&lt;li&gt;Supports positive and negative prompting with variable guidance strength&lt;/li&gt;&lt;li&gt;Capable of generating images in batches, with max batch size dependent on available VRAM.&lt;/li&gt;&lt;li&gt;Some stylistic flexibility, but limited ability to understand complex prompts.&lt;/ul&gt;</source>
      <translation>&lt;h1&gt;GLID-3-XL&lt;/h1&gt;&lt;p&gt;GLID-3-XL was the best inpainting model available until August 2022, and the first model supported by IntraPaint. IntraPaint continues to support it for the sake of preserving historically interesting image generation models.&lt;h2&gt;Generator capabilities and limits:&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;Requires approximately 8GB of VRAM.&lt;/li&gt;&lt;li&gt;Inpainting is supported at an ideal resolution of 256x256, with limited support for other resolutions.&lt;/li&gt;&lt;li&gt;Supports positive and negative prompting with variable guidance strength&lt;/li&gt;&lt;li&gt;Capable of generating images in batches, with max batch size dependent on available VRAM.&lt;/li&gt;&lt;li&gt;Some stylistic flexibility, but limited ability to understand complex prompts.&lt;/ul&gt;</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/glid3_xl_generator.py" line="62"/>
      <source>&lt;h2&gt;GLID-3-XL server setup&lt;/h2&gt;&lt;p&gt;NOTE: Because GLID-3-XL is mainly a historical curiosity at this point, few steps have been taken to simplify the setup process. As the software involved becomes increasingly outdated, further steps may be necessary to get this generator to work. Currently, completing the following steps should allow IntraPaint to run GLID-3-XL:&lt;/p&gt;&lt;ol&gt;&lt;li&gt;Make sure your computer has a NVIDIA GPU with at least 8GB of VRAM. Other GPUsor slightly less memory may work, but are not tested.&lt;/li&gt;&lt;li&gt;If you are using the pre-built version of IntraPaint, you will need to switch to the Git version. Here's how you do that:&lt;/li&gt;&lt;ol&gt;&lt;li&gt;Ensure that all of the following are installed:&lt;/li&gt;&lt;ol&gt;&lt;li&gt;&lt;a href="https://www.python.org/"&gt;Python3&lt;/a&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://git-scm.com/"&gt;Git&lt;/a&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://developer.nvidia.com/cuda-toolkit"&gt;CUDA&lt;/a&gt; (if using a NVIDIA graphics card)&lt;/li&gt;&lt;li&gt;&lt;a href="https://www.anaconda.com/download/"&gt;Anaconda&lt;/a&gt;&lt;/li&gt;&lt;/ol&gt;&lt;li&gt;Depending on your system, you may need to take extra steps to add Python, Git, and Anaconda to your system path, or perform other configuration steps. Refer to the sites linked above for full documentation.&lt;/li&gt;&lt;li&gt;In a terminal window, run &lt;code&gt;git clone https://github.com/centuryglass/IntraPaint.git&lt;/code&gt; to download the full IntraPaint repository, then change directory to the new IntraPaint folder that this creates.&lt;/li&gt;&lt;/ol&gt;&lt;li&gt;In a terminal window, run `&lt;code&gt;conda create -n intrapaint-glid&lt;/code&gt;`, then `&lt;code&gt;conda activate intrapaint-glid&lt;/code&gt;` to prepare to install additional dependencies.&lt;/li&gt;&lt;li&gt;Within the the terminal in the IntraPaint directory with the `intrapaint-glid`environment active, install the appropriate versions of torch and torchvision found &lt;a href="https://pytorch.org/get-started/locally/"&gt;here&lt;/a&gt;.&lt;li&gt;Run `&lt;code&gt;conda install pip&lt;/code&gt;` to make sure the environment has its own copy of the python package manager.&lt;/li&gt;&lt;li&gt;Run `&lt;code&gt;pip install -r requirements.txt&lt;/code&gt;` to install primary IntraPaint requirements within the anaconda environment.&lt;/li&gt;&lt;li&gt;Run `&lt;code&gt;pip install -r requirements-glid.txt&lt;/code&gt;` to install additional dependencies for GLID-3-XL.&lt;/li&gt;&lt;li&gt;Run the following Git commands to add two other required dependencies:&lt;li&gt;&lt;ol&gt;&lt;li&gt;`&lt;code&gt;git clone https://github.com/CompVis/taming-transformers.git&lt;/code&gt;`&lt;/li&gt;&lt;li&gt;`&lt;code&gt;git clone https://github.com/CompVis/latent-diffusion.git&lt;/code&gt;`&lt;/li&gt;&lt;li&gt;Download one or more GLID-3-XL inpainting models, and place them in the IntraPaint/models/ directory. These are the main options available:&lt;li&gt;&lt;ol&gt;&lt;li&gt;&lt;a href="https://dall-3.com/models/glid-3-xl/"&gt;inpaint.pt&lt;/a&gt;, the original GLID-3-XL inpainting model&lt;/li&gt;&lt;li&gt;&lt;a href="https://huggingface.co/laion/ongo/resolve/main/ongo.pt&gt;ongo.pt&lt;/a&gt;, trained by LAION on paintings from the Wikiart dataset&lt;/li&gt;&lt;li&gt;&lt;a href="https://huggingface.co/laion/erlich/resolve/main/model/ema_0.9999_120000.pt"&gt;erlich.pt&lt;/a&gt;, trained on the LAION large logo dataset&lt;/li&gt;&lt;/ol&gt;&lt;li&gt;Start IntraPaint by running `&lt;code&gt;python IntraPaint.py&lt;/code&gt;`. If you are using a model other than the default inpaint.pt, instead run `&lt;code&gt;python Intrapaint_server.py  --model_path models/model.pt&lt;/code&gt;`, replacing "model.pt" with the file name of whatever model you are using.&lt;/li&gt;&lt;li&gt;If all steps were performed correctly, you should be able to activate this generator without any errors.&lt;/li&gt;</source>
      <translation>&lt;h2&gt;GLID-3-XL server setup&lt;/h2&gt;&lt;p&gt;NOTE: Because GLID-3-XL is mainly a historical curiosity at this point, few steps have been taken to simplify the setup process. As the software involved becomes increasingly outdated, further steps may be necessary to get this generator to work. Currently, completing the following steps should allow IntraPaint to run GLID-3-XL:&lt;/p&gt;&lt;ol&gt;&lt;li&gt;Make sure your computer has a NVIDIA GPU with at least 8GB of VRAM. Other GPUsor slightly less memory may work, but are not tested.&lt;/li&gt;&lt;li&gt;If you are using the pre-built version of IntraPaint, you will need to switch to the Git version. Here's how you do that:&lt;/li&gt;&lt;ol&gt;&lt;li&gt;Ensure that all of the following are installed:&lt;/li&gt;&lt;ol&gt;&lt;li&gt;&lt;a href="https://www.python.org/"&gt;Python3&lt;/a&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://git-scm.com/"&gt;Git&lt;/a&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://developer.nvidia.com/cuda-toolkit"&gt;CUDA&lt;/a&gt; (if using a NVIDIA graphics card)&lt;/li&gt;&lt;li&gt;&lt;a href="https://www.anaconda.com/download/"&gt;Anaconda&lt;/a&gt;&lt;/li&gt;&lt;/ol&gt;&lt;li&gt;Depending on your system, you may need to take extra steps to add Python, Git, and Anaconda to your system path, or perform other configuration steps. Refer to the sites linked above for full documentation.&lt;/li&gt;&lt;li&gt;In a terminal window, run &lt;code&gt;git clone https://github.com/centuryglass/IntraPaint.git&lt;/code&gt; to download the full IntraPaint repository, then change directory to the new IntraPaint folder that this creates.&lt;/li&gt;&lt;/ol&gt;&lt;li&gt;In a terminal window, run `&lt;code&gt;conda create -n intrapaint-glid&lt;/code&gt;`, then `&lt;code&gt;conda activate intrapaint-glid&lt;/code&gt;` to prepare to install additional dependencies.&lt;/li&gt;&lt;li&gt;Within the the terminal in the IntraPaint directory with the `intrapaint-glid`environment active, install the appropriate versions of torch and torchvision found &lt;a href="https://pytorch.org/get-started/locally/"&gt;here&lt;/a&gt;.&lt;li&gt;Run `&lt;code&gt;conda install pip&lt;/code&gt;` to make sure the environment has its own copy of the python package manager.&lt;/li&gt;&lt;li&gt;Run `&lt;code&gt;pip install -r requirements.txt&lt;/code&gt;` to install primary IntraPaint requirements within the anaconda environment.&lt;/li&gt;&lt;li&gt;Run `&lt;code&gt;pip install -r requirements-glid.txt&lt;/code&gt;` to install additional dependencies for GLID-3-XL.&lt;/li&gt;&lt;li&gt;Run the following Git commands to add two other required dependencies:&lt;li&gt;&lt;ol&gt;&lt;li&gt;`&lt;code&gt;git clone https://github.com/CompVis/taming-transformers.git&lt;/code&gt;`&lt;/li&gt;&lt;li&gt;`&lt;code&gt;git clone https://github.com/CompVis/latent-diffusion.git&lt;/code&gt;`&lt;/li&gt;&lt;li&gt;Download one or more GLID-3-XL inpainting models, and place them in the IntraPaint/models/ directory. These are the main options available:&lt;li&gt;&lt;ol&gt;&lt;li&gt;&lt;a href="https://dall-3.com/models/glid-3-xl/"&gt;inpaint.pt&lt;/a&gt;, the original GLID-3-XL inpainting model&lt;/li&gt;&lt;li&gt;&lt;a href="https://huggingface.co/laion/ongo/resolve/main/ongo.pt&gt;ongo.pt&lt;/a&gt;, trained by LAION on paintings from the Wikiart dataset&lt;/li&gt;&lt;li&gt;&lt;a href="https://huggingface.co/laion/erlich/resolve/main/model/ema_0.9999_120000.pt"&gt;erlich.pt&lt;/a&gt;, trained on the LAION large logo dataset&lt;/li&gt;&lt;/ol&gt;&lt;li&gt;Start IntraPaint by running `&lt;code&gt;python IntraPaint.py&lt;/code&gt;`. If you are using a model other than the default inpaint.pt, instead run `&lt;code&gt;python Intrapaint_server.py  --model_path models/model.pt&lt;/code&gt;`, replacing "model.pt" with the file name of whatever model you are using.&lt;/li&gt;&lt;li&gt;If all steps were performed correctly, you should be able to activate this generator without any errors.&lt;/li&gt;</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/glid3_xl_generator.py" line="116"/>
      <source>Required dependencies are missing: &lt;code&gt;{dependency_list}&lt;/code&gt;</source>
      <translation>Required dependencies are missing: &lt;code&gt;{dependency_list}&lt;/code&gt;</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/glid3_xl_generator.py" line="117"/>
      <source>Not enough VRAM for the GLID-3-XL generator: {mem_free} free memory found, expected at least {min_vram}</source>
      <translation>Not enough VRAM for the GLID-3-XL generator: {mem_free} free memory found, expected at least {min_vram}</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/glid3_xl_generator.py" line="119"/>
      <source>{model_name} model file expected at "{model_path}" is missing</source>
      <translation>{model_name} model file expected at "{model_path}" is missing</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/glid3_xl_generator.py" line="123"/>
      <source>Missing required {repo_name} repository, please run `git clone {repo_url}` within the IntraPaint directory.</source>
      <translation>Missing required {repo_name} repository, please run `git clone {repo_url}` within the IntraPaint directory.</translation>
    </message>
  </context>
  <context>
    <name>controller.image_generation.image_generator</name>
    <message>
      <location filename="../../src/controller/image_generation/image_generator.py" line="31"/>
      <source>Inpainting failure</source>
      <translation>Inpainting failure</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/image_generator.py" line="32"/>
      <source>Save failed</source>
      <translation>Save failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/image_generator.py" line="33"/>
      <source>Failed</source>
      <translation>Failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/image_generator.py" line="34"/>
      <source>Existing image generation operation not yet finished, wait a little longer.</source>
      <translation>Existing image generation operation not yet finished, wait a little longer.</translation>
    </message>
  </context>
  <context>
    <name>controller.image_generation.null_generator</name>
    <message>
      <location filename="../../src/controller/image_generation/null_generator.py" line="19"/>
      <source>No image generator</source>
      <translation>No image generator</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/null_generator.py" line="20"/>
      <source>&lt;p&gt;IntraPaint does not need an image generator to function.  If you don't want to set up an image generator, you can still use it like any other image editor.</source>
      <translation>&lt;p&gt;IntraPaint does not need an image generator to function.  If you don't want to set up an image generator, you can still use it like any other image editor.</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/null_generator.py" line="22"/>
      <source>This option has no setup requirements.</source>
      <translation>This option has no setup requirements.</translation>
    </message>
  </context>
  <context>
    <name>controller.image_generation.sd_webui_generator</name>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="45"/>
      <source>Tools</source>
      <translation>Tools</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="47"/>
      <source>Stable-Diffusion WebUI API</source>
      <translation>Stable-Diffusion WebUI API</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="48"/>
      <source>&lt;h2&gt;Stable-Diffusion: via WebUI API&lt;/h2&gt;&lt;p&gt;Released in August 2022, Stable-Diffusion remains the most versatile and useful free image generation model.&lt;/p&gt;&lt;h2&gt;Generator capabilities and limits:&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;Requires only 4GB of VRAM, or 8GB if using an SDXL model.&lt;/li&gt;&lt;li&gt;Tuned for an ideal resolution of 512x512 (1024x1024 for SDXL).&lt;/li&gt;&lt;li&gt;A huge variety of fine-tuned variant models are available.&lt;/li&gt;&lt;li&gt;The magnitude of changes made to existing images can be precisely controlled by varying denoising strength.&lt;/li&gt;&lt;li&gt;Supports LORAs, miniature extension models adding support for new styles and subjects.&lt;/li&gt;&lt;li&gt;Supports positive and negative prompting, where (parentheses) draw additional attention to prompt sections, and [square brackets] reduce attention.&lt;/li&gt;&lt;li&gt;Supports ControlNet modules, allowing image generation to be guided by arbitrary constraints like depth maps, existing image lines, and more.&lt;/li&gt;&lt;/ul&gt;&lt;h3&gt;Stable-Diffusion WebUI:&lt;/h3&gt;&lt;p&gt;The Stable-Diffusion WebUI is one of the first interfaces created for using Stable-Diffusion. This IntraPaint generator offloads image generation to that system through a network connection.  The WebUI instance can be run on the same computer as IntraPaint, or remotely on a separate server.&lt;/p&gt;</source>
      <translation>&lt;h2&gt;Stable-Diffusion: via WebUI API&lt;/h2&gt;&lt;p&gt;Released in August 2022, Stable-Diffusion remains the most versatile and useful free image generation model.&lt;/p&gt;&lt;h2&gt;Generator capabilities and limits:&lt;/h2&gt;&lt;ul&gt;&lt;li&gt;Requires only 4GB of VRAM, or 8GB if using an SDXL model.&lt;/li&gt;&lt;li&gt;Tuned for an ideal resolution of 512x512 (1024x1024 for SDXL).&lt;/li&gt;&lt;li&gt;A huge variety of fine-tuned variant models are available.&lt;/li&gt;&lt;li&gt;The magnitude of changes made to existing images can be precisely controlled by varying denoising strength.&lt;/li&gt;&lt;li&gt;Supports LORAs, miniature extension models adding support for new styles and subjects.&lt;/li&gt;&lt;li&gt;Supports positive and negative prompting, where (parentheses) draw additional attention to prompt sections, and [square brackets] reduce attention.&lt;/li&gt;&lt;li&gt;Supports ControlNet modules, allowing image generation to be guided by arbitrary constraints like depth maps, existing image lines, and more.&lt;/li&gt;&lt;/ul&gt;&lt;h3&gt;Stable-Diffusion WebUI:&lt;/h3&gt;&lt;p&gt;The Stable-Diffusion WebUI is one of the first interfaces created for using Stable-Diffusion. This IntraPaint generator offloads image generation to that system through a network connection.  The WebUI instance can be run on the same computer as IntraPaint, or remotely on a separate server.&lt;/p&gt;</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="71"/>
      <source>&lt;h2&gt;Installing the WebUI&lt;/h2&gt;&lt;p&gt;The &lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge"&gt;Forge WebUI&lt;/a&gt; is the recommended version, but the original &lt;a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui"&gt;Stable-Diffusion WebUI&lt;/a&gt; also works. Pick one of those, and follow instructions at the link to install it.&lt;/p&gt;&lt;p&gt;Once the WebUI is installed, open the "webui-user.bat" file in its main folder (or "webui-user.sh" on Linux and MacOS). Where it says "set COMMANDLINE_ARGS", add &lt;nobr&gt;--api&lt;/nobr&gt;, save changes, and run the webui-user script. Once the WebUI starts successfully, you should be able to activate this IntraPaint generator.&lt;/p&gt;</source>
      <translation>&lt;h2&gt;Installing the WebUI&lt;/h2&gt;&lt;p&gt;The &lt;a href="https://github.com/lllyasviel/stable-diffusion-webui-forge"&gt;Forge WebUI&lt;/a&gt; is the recommended version, but the original &lt;a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui"&gt;Stable-Diffusion WebUI&lt;/a&gt; also works. Pick one of those, and follow instructions at the link to install it.&lt;/p&gt;&lt;p&gt;Once the WebUI is installed, open the "webui-user.bat" file in its main folder (or "webui-user.sh" on Linux and MacOS). Where it says "set COMMANDLINE_ARGS", add &lt;nobr&gt;--api&lt;/nobr&gt;, save changes, and run the webui-user script. Once the WebUI starts successfully, you should be able to activate this IntraPaint generator.&lt;/p&gt;</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="85"/>
      <source>Not authenticated</source>
      <translation>Not authenticated</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="86"/>
      <source>Open or create an image first.</source>
      <translation>Open or create an image first.</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="87"/>
      <source>Existing operation still in progress</source>
      <translation>Existing operation still in progress</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="88"/>
      <source>Interrogate failure</source>
      <translation>Interrogate failure</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="89"/>
      <source>Running CLIP interrogate</source>
      <translation>Running CLIP interrogate</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="90"/>
      <source>Inpainting UI</source>
      <translation>Inpainting UI</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="91"/>
      <source>Enter server URL:</source>
      <translation>Enter server URL:</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="92"/>
      <source>Server connection failed, enter a new URL or click "OK" to retry</source>
      <translation>Server connection failed, enter a new URL or click "OK" to retry</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="94"/>
      <source>Upscale failure</source>
      <translation>Upscale failure</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="98"/>
      <source>Updating prompt styles failed</source>
      <translation>Updating prompt styles failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="100"/>
      <source>Image generation failed</source>
      <translation>Image generation failed</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="101"/>
      <source>Nothing was selected in the image generation area. Either use the selection tool to mark part of the image generation area for inpainting, move the image generation area to cover selected content, or switch to another image generation mode.</source>
      <translation>Nothing was selected in the image generation area. Either use the selection tool to mark part of the image generation area for inpainting, move the image generation area to cover selected content, or switch to another image generation mode.</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="105"/>
      <source>ControlNet</source>
      <translation>ControlNet</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="106"/>
      <source>ControlNet Unit {unit_number}</source>
      <translation>ControlNet Unit {unit_number}</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/sd_webui_generator.py" line="107"/>
      <source>Login cancelled.</source>
      <translation>Login cancelled.</translation>
    </message>
  </context>
  <context>
    <name>controller.image_generation.test_generator</name>
    <message>
      <location filename="../../src/controller/image_generation/test_generator.py" line="29"/>
      <source>Test/development image generator</source>
      <translation>Test/development image generator</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/test_generator.py" line="30"/>
      <source>Mock image generator, for testing and development</source>
      <translation>Mock image generator, for testing and development</translation>
    </message>
    <message>
      <location filename="../../src/controller/image_generation/test_generator.py" line="31"/>
      <source>No setup required.</source>
      <translation>No setup required.</translation>
    </message>
  </context>
  <context>
    <name>controller.tool_controller</name>
    <message>
      <location filename="../../src/controller/tool_controller.py" line="41"/>
      <source>Failed to load libmypaint brush library files</source>
      <translation>Failed to load libmypaint brush library files</translation>
    </message>
    <message>
      <location filename="../../src/controller/tool_controller.py" line="42"/>
      <source>The brush tool will not be available unless this is fixed.</source>
      <translation>The brush tool will not be available unless this is fixed.</translation>
    </message>
  </context>
  <context>
    <name>excepthook</name>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="134"/>
      <source>Bug Detected</source>
      <translation>Bug Detected</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="135"/>
      <source>&lt;big&gt;&lt;b&gt;A programming error has been detected during the execution of this program.&lt;/b&gt;&lt;/big&gt;</source>
      <translation>&lt;big&gt;&lt;b&gt;A programming error has been detected during the execution of this program.&lt;/b&gt;&lt;/big&gt;</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="138"/>
      <source>It probably isn't fatal, but should be reported to the developers nonetheless.</source>
      <translation>It probably isn't fatal, but should be reported to the developers nonetheless.</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="142"/>
      <source>Report Bug...</source>
      <translation>Report Bug...</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="146"/>
      <source>Copy Traceback...</source>
      <translation>Copy Traceback...</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="151"/>
      <source>

Please remember to include the traceback from the Details expander.</source>
      <translation>

Please remember to include the traceback from the Details expander.</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="170"/>
      <source>Traceback Copied</source>
      <translation>Traceback Copied</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="171"/>
      <source>The traceback has now been copied to the clipboard.</source>
      <translation>The traceback has now been copied to the clipboard.</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="236"/>
      <source>SMTP Failure</source>
      <translation>SMTP Failure</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="237"/>
      <source>An error was encountered while attempting to send your bug report. Please submit it manually.</source>
      <translation>An error was encountered while attempting to send your bug report. Please submit it manually.</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="241"/>
      <source>Bug Reported</source>
      <translation>Bug Reported</translation>
    </message>
    <message>
      <location filename="../../src/util/qtexcepthook.py" line="242"/>
      <source>Your bug report was successfully sent.</source>
      <translation>Your bug report was successfully sent.</translation>
    </message>
  </context>
  <context>
    <name>image.composite_mode</name>
    <message>
      <location filename="../../src/image/composite_mode.py" line="24"/>
      <source>Normal</source>
      <translation>Normal</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="25"/>
      <source>Multiply</source>
      <translation>Multiply</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="26"/>
      <source>Screen</source>
      <translation>Screen</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="27"/>
      <source>Overlay</source>
      <translation>Overlay</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="28"/>
      <source>Darken</source>
      <translation>Darken</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="29"/>
      <source>Lighten</source>
      <translation>Lighten</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="30"/>
      <source>Color Dodge</source>
      <translation>Color Dodge</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="31"/>
      <source>Color Burn</source>
      <translation>Color Burn</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="32"/>
      <source>Hard Light</source>
      <translation>Hard Light</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="33"/>
      <source>Soft Light</source>
      <translation>Soft Light</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="34"/>
      <source>Difference</source>
      <translation>Difference</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="35"/>
      <source>Color</source>
      <translation>Color</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="36"/>
      <source>Luminosity</source>
      <translation>Luminosity</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="37"/>
      <source>Hue</source>
      <translation>Hue</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="38"/>
      <source>Saturation</source>
      <translation>Saturation</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="39"/>
      <source>Plus</source>
      <translation>Plus</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="40"/>
      <source>Destination In</source>
      <translation>Destination In</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="41"/>
      <source>Destination Out</source>
      <translation>Destination Out</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="42"/>
      <source>Source Atop</source>
      <translation>Source Atop</translation>
    </message>
    <message>
      <location filename="../../src/image/composite_mode.py" line="43"/>
      <source>Destination Atop</source>
      <translation>Destination Atop</translation>
    </message>
  </context>
  <context>
    <name>image.filter.blur</name>
    <message>
      <location filename="../../src/image/filter/blur.py" line="21"/>
      <source>Simple</source>
      <translation>Simple</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/blur.py" line="22"/>
      <source>Box</source>
      <translation>Box</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/blur.py" line="23"/>
      <source>Gaussian</source>
      <translation>Gaussian</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/blur.py" line="25"/>
      <source>Blur</source>
      <translation>Blur</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/blur.py" line="26"/>
      <source>Blur the image</source>
      <translation>Blur the image</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/blur.py" line="28"/>
      <source>Blurring mode</source>
      <translation>Blurring mode</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/blur.py" line="29"/>
      <source>Image blurring algorithm</source>
      <translation>Image blurring algorithm</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/blur.py" line="31"/>
      <source>Radius</source>
      <translation>Radius</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/blur.py" line="32"/>
      <source>Pixel blur radius (no effect in simple mode).</source>
      <translation>Pixel blur radius (no effect in simple mode).</translation>
    </message>
  </context>
  <context>
    <name>image.filter.brightness_contrast</name>
    <message>
      <location filename="../../src/image/filter/brightness_contrast.py" line="21"/>
      <source>Brightness/Contrast</source>
      <translation>Brightness/Contrast</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/brightness_contrast.py" line="22"/>
      <source>Adjust image brightness and contrast.</source>
      <translation>Adjust image brightness and contrast.</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/brightness_contrast.py" line="24"/>
      <source>Brightness:</source>
      <translation>Brightness:</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/brightness_contrast.py" line="25"/>
      <source>Contrast</source>
      <translation>Contrast</translation>
    </message>
  </context>
  <context>
    <name>image.filter.filter</name>
    <message>
      <location filename="../../src/image/filter/filter.py" line="31"/>
      <source>Apply image filter</source>
      <translation>Apply image filter</translation>
    </message>
  </context>
  <context>
    <name>image.filter.posterize</name>
    <message>
      <location filename="../../src/image/filter/posterize.py" line="23"/>
      <source>Posterize</source>
      <translation>Posterize</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/posterize.py" line="24"/>
      <source>Reduce color range by reducing image color bit count.</source>
      <translation>Reduce color range by reducing image color bit count.</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/posterize.py" line="25"/>
      <source>Bit Count:</source>
      <translation>Bit Count:</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/posterize.py" line="26"/>
      <source>Image color bits to preserve (1-8)</source>
      <translation>Image color bits to preserve (1-8)</translation>
    </message>
  </context>
  <context>
    <name>image.filter.rgb_color_balance</name>
    <message>
      <location filename="../../src/image/filter/rgb_color_balance.py" line="22"/>
      <source>RGBA Color Balance</source>
      <translation>RGBA Color Balance</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/rgb_color_balance.py" line="23"/>
      <source>Adjust color balance</source>
      <translation>Adjust color balance</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/rgb_color_balance.py" line="25"/>
      <source>Red</source>
      <translation>Red</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/rgb_color_balance.py" line="26"/>
      <source>Green</source>
      <translation>Green</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/rgb_color_balance.py" line="27"/>
      <source>Blue</source>
      <translation>Blue</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/rgb_color_balance.py" line="28"/>
      <source>Alpha</source>
      <translation>Alpha</translation>
    </message>
  </context>
  <context>
    <name>image.filter.sharpen</name>
    <message>
      <location filename="../../src/image/filter/sharpen.py" line="23"/>
      <source>Sharpen</source>
      <translation>Sharpen</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/sharpen.py" line="24"/>
      <source>Sharpen the image</source>
      <translation>Sharpen the image</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/sharpen.py" line="26"/>
      <source>Factor</source>
      <translation>Factor</translation>
    </message>
    <message>
      <location filename="../../src/image/filter/sharpen.py" line="27"/>
      <source>Sharpness factor (1.0: no change)</source>
      <translation>Sharpness factor (1.0: no change)</translation>
    </message>
  </context>
  <context>
    <name>image.layers.image_layer</name>
    <message>
      <location filename="../../src/image/layers/image_layer.py" line="27"/>
      <source>Layer cropping failed</source>
      <translation>Layer cropping failed</translation>
    </message>
    <message>
      <location filename="../../src/image/layers/image_layer.py" line="28"/>
      <source>Layer has no image content.</source>
      <translation>Layer has no image content.</translation>
    </message>
    <message>
      <location filename="../../src/image/layers/image_layer.py" line="29"/>
      <source>Layer is already cropped to fit image content.</source>
      <translation>Layer is already cropped to fit image content.</translation>
    </message>
  </context>
  <context>
    <name>image.layers.image_stack</name>
    <message>
      <location filename="../../src/image/layers/image_stack.py" line="38"/>
      <source>new image</source>
      <translation>new image</translation>
    </message>
    <message>
      <location filename="../../src/image/layers/image_stack.py" line="39"/>
      <source>merge layers</source>
      <translation>merge layers</translation>
    </message>
    <message>
      <location filename="../../src/image/layers/image_stack.py" line="40"/>
      <source>resize layer to image</source>
      <translation>resize layer to image</translation>
    </message>
    <message>
      <location filename="../../src/image/layers/image_stack.py" line="41"/>
      <source>cut/clear selection</source>
      <translation>cut/clear selection</translation>
    </message>
  </context>
  <context>
    <name>image.layers.text_layer</name>
    <message>
      <location filename="../../src/image/layers/text_layer.py" line="25"/>
      <source>Convert text layer to image?</source>
      <translation>Convert text layer to image?</translation>
    </message>
    <message>
      <location filename="../../src/image/layers/text_layer.py" line="26"/>
      <source>Attempted action: &lt;b&gt;{action_name}&lt;/b&gt;. To complete this action, layer "{layer_name}" must be converted to an image layer, and you will no longer be able to edit it with the text tool. Continue?</source>
      <translation>Attempted action: &lt;b&gt;{action_name}&lt;/b&gt;. To complete this action, layer "{layer_name}" must be converted to an image layer, and you will no longer be able to edit it with the text tool. Continue?</translation>
    </message>
    <message>
      <location filename="../../src/image/layers/text_layer.py" line="30"/>
      <source>Convert text layers to image?</source>
      <translation>Convert text layers to image?</translation>
    </message>
    <message>
      <location filename="../../src/image/layers/text_layer.py" line="31"/>
      <source>Attempted action: &lt;b&gt;{action_name}&lt;/b&gt;. To complete this action,{num_text_layers} text layers must be converted to image layers, and you will no longer be able to edit them with the text tool. Continue?</source>
      <translation>Attempted action: &lt;b&gt;{action_name}&lt;/b&gt;. To complete this action,{num_text_layers} text layers must be converted to image layers, and you will no longer be able to edit them with the text tool. Continue?</translation>
    </message>
  </context>
  <context>
    <name>tools.base_tool</name>
    <message>
      <location filename="../../src/tools/base_tool.py" line="27"/>
      <source>{modifier_or_modifiers}+LMB/MMB and drag:pan view - </source>
      <translation>{modifier_or_modifiers}+LMB/MMB and drag:pan view - </translation>
    </message>
    <message>
      <location filename="../../src/tools/base_tool.py" line="28"/>
      <source>Scroll wheel:zoom</source>
      <translation>Scroll wheel:zoom</translation>
    </message>
    <message>
      <location filename="../../src/tools/base_tool.py" line="29"/>
      <source>{modifier_or_modifiers}: Fixed aspect ratio</source>
      <translation>{modifier_or_modifiers}: Fixed aspect ratio</translation>
    </message>
  </context>
  <context>
    <name>tools.brush_tool</name>
    <message>
      <location filename="../../src/tools/brush_tool.py" line="31"/>
      <source>Brush</source>
      <translation>Brush</translation>
    </message>
    <message>
      <location filename="../../src/tools/brush_tool.py" line="32"/>
      <source>Paint into the image</source>
      <translation>Paint into the image</translation>
    </message>
    <message>
      <location filename="../../src/tools/brush_tool.py" line="33"/>
      <source>LMB:draw - RMB:1px draw - </source>
      <translation>LMB:draw - RMB:1px draw - </translation>
    </message>
  </context>
  <context>
    <name>tools.canvas_tool</name>
    <message>
      <location filename="../../src/tools/canvas_tool.py" line="35"/>
      <source>{modifier_or_modifiers}+click: line mode - </source>
      <translation>{modifier_or_modifiers}+click: line mode - </translation>
    </message>
    <message>
      <location filename="../../src/tools/canvas_tool.py" line="36"/>
      <source>{modifier_or_modifiers}: fixed angle - </source>
      <translation>{modifier_or_modifiers}: fixed angle - </translation>
    </message>
  </context>
  <context>
    <name>tools.draw_tool</name>
    <message>
      <location filename="../../src/tools/draw_tool.py" line="31"/>
      <source>Draw</source>
      <translation>Draw</translation>
    </message>
    <message>
      <location filename="../../src/tools/draw_tool.py" line="32"/>
      <source>Draw into the image</source>
      <translation>Draw into the image</translation>
    </message>
    <message>
      <location filename="../../src/tools/draw_tool.py" line="33"/>
      <source>LMB:draw - RMB:1px draw - </source>
      <translation>LMB:draw - RMB:1px draw - </translation>
    </message>
  </context>
  <context>
    <name>tools.eyedropper_tool</name>
    <message>
      <location filename="../../src/tools/eyedropper_tool.py" line="28"/>
      <source>Color Picker</source>
      <translation>Color Picker</translation>
    </message>
    <message>
      <location filename="../../src/tools/eyedropper_tool.py" line="29"/>
      <source>Select a brush color</source>
      <translation>Select a brush color</translation>
    </message>
    <message>
      <location filename="../../src/tools/eyedropper_tool.py" line="30"/>
      <source>LMB:pick color - </source>
      <translation>LMB:pick color - </translation>
    </message>
  </context>
  <context>
    <name>tools.fill_tool</name>
    <message>
      <location filename="../../src/tools/fill_tool.py" line="31"/>
      <source>Color fill</source>
      <translation>Color fill</translation>
    </message>
    <message>
      <location filename="../../src/tools/fill_tool.py" line="32"/>
      <source>Fill areas with solid colors</source>
      <translation>Fill areas with solid colors</translation>
    </message>
    <message>
      <location filename="../../src/tools/fill_tool.py" line="33"/>
      <source>LMB:fill - </source>
      <translation>LMB:fill - </translation>
    </message>
    <message>
      <location filename="../../src/tools/fill_tool.py" line="34"/>
      <source>Set fill color</source>
      <translation>Set fill color</translation>
    </message>
  </context>
  <context>
    <name>tools.generation_area_tool</name>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="29"/>
      <source>Select Image Generation Area</source>
      <translation>Select Image Generation Area</translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="30"/>
      <source>Select an image region for AI image generation</source>
      <translation>Select an image region for AI image generation</translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="31"/>
      <source>Full image as generation area</source>
      <translation>Full image as generation area</translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="32"/>
      <source>Send the entire image during image generation.</source>
      <translation>Send the entire image during image generation.</translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="33"/>
      <source>LMB:move area - RMB:resize area - </source>
      <translation>LMB:move area - RMB:resize area - </translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="35"/>
      <source>X:</source>
      <translation>X:</translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="36"/>
      <source>Y:</source>
      <translation>Y:</translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="37"/>
      <source>W:</source>
      <translation>W:</translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="38"/>
      <source>H:</source>
      <translation>H:</translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="39"/>
      <source>Set the left edge position of the image generation area.</source>
      <translation>Set the left edge position of the image generation area.</translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="42"/>
      <location filename="../../src/tools/generation_area_tool.py" line="40"/>
      <source>Set the top edge position of the image generation area.</source>
      <translation>Set the top edge position of the image generation area.</translation>
    </message>
    <message>
      <location filename="../../src/tools/generation_area_tool.py" line="41"/>
      <source>Set the width of the image generation area.</source>
      <translation>Set the width of the image generation area.</translation>
    </message>
  </context>
  <context>
    <name>tools.layer_transform_tool</name>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="39"/>
      <source>X:</source>
      <translation>X:</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="40"/>
      <source>Y:</source>
      <translation>Y:</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="41"/>
      <source>X-Scale:</source>
      <translation>X-Scale:</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="42"/>
      <source>Y-Scale:</source>
      <translation>Y-Scale:</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="43"/>
      <source>W:</source>
      <translation>W:</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="44"/>
      <source>H:</source>
      <translation>H:</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="45"/>
      <source>Angle:</source>
      <translation>Angle:</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="47"/>
      <source>Transform Layers</source>
      <translation>Transform Layers</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="48"/>
      <source>Move, scale, or rotate the active layer.</source>
      <translation>Move, scale, or rotate the active layer.</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="49"/>
      <source>Keep aspect ratio</source>
      <translation>Keep aspect ratio</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="50"/>
      <source>Reset</source>
      <translation>Reset</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="51"/>
      <source>Clear</source>
      <translation>Clear</translation>
    </message>
    <message>
      <location filename="../../src/tools/layer_transform_tool.py" line="52"/>
      <source>LMB+drag:move layer - </source>
      <translation>LMB+drag:move layer - </translation>
    </message>
  </context>
  <context>
    <name>tools.selection_fill_tool</name>
    <message>
      <location filename="../../src/tools/selection_fill_tool.py" line="31"/>
      <source>Selection fill</source>
      <translation>Selection fill</translation>
    </message>
    <message>
      <location filename="../../src/tools/selection_fill_tool.py" line="32"/>
      <source>Select areas with solid colors</source>
      <translation>Select areas with solid colors</translation>
    </message>
    <message>
      <location filename="../../src/tools/selection_fill_tool.py" line="33"/>
      <source>LMB:select - RMB:deselect - </source>
      <translation>LMB:select - RMB:deselect - </translation>
    </message>
  </context>
  <context>
    <name>tools.selection_tool</name>
    <message>
      <location filename="../../src/tools/selection_tool.py" line="27"/>
      <source>Selection</source>
      <translation>Selection</translation>
    </message>
    <message>
      <location filename="../../src/tools/selection_tool.py" line="28"/>
      <source>Select areas for editing or inpainting.</source>
      <translation>Select areas for editing or inpainting.</translation>
    </message>
    <message>
      <location filename="../../src/tools/selection_tool.py" line="29"/>
      <source>LMB:select - RMB:1px select - </source>
      <translation>LMB:select - RMB:1px select - </translation>
    </message>
  </context>
  <context>
    <name>tools.shape_selection_tool</name>
    <message>
      <location filename="../../src/tools/shape_selection_tool.py" line="29"/>
      <source>Rectangle/Ellipse selection</source>
      <translation>Rectangle/Ellipse selection</translation>
    </message>
    <message>
      <location filename="../../src/tools/shape_selection_tool.py" line="30"/>
      <source>Select or de-select rectangles or ellipses</source>
      <translation>Select or de-select rectangles or ellipses</translation>
    </message>
    <message>
      <location filename="../../src/tools/shape_selection_tool.py" line="31"/>
      <source>LMB+drag:select - RMB+drag:deselect - </source>
      <translation>LMB+drag:select - RMB+drag:deselect - </translation>
    </message>
  </context>
  <context>
    <name>tools.text_tool</name>
    <message>
      <location filename="../../src/tools/text_tool.py" line="36"/>
      <source>Text</source>
      <translation>Text</translation>
    </message>
    <message>
      <location filename="../../src/tools/text_tool.py" line="37"/>
      <source>Add text to a text layer</source>
      <translation>Add text to a text layer</translation>
    </message>
    <message>
      <location filename="../../src/tools/text_tool.py" line="38"/>
      <source>LMB:select text layer - LMB+drag:create new layer - </source>
      <translation>LMB:select text layer - LMB+drag:create new layer - </translation>
    </message>
  </context>
  <context>
    <name>ui.generated_image_selector</name>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="43"/>
      <source>Zoom to changes</source>
      <translation>Zoom to changes</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="44"/>
      <source>Show selection</source>
      <translation>Show selection</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="45"/>
      <source>Inpaint</source>
      <translation>Inpaint</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="46"/>
      <source>Cancel</source>
      <translation>Cancel</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="47"/>
      <source>This will discard all generated images.</source>
      <translation>This will discard all generated images.</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="48"/>
      <source>Previous</source>
      <translation>Previous</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="49"/>
      <source>Toggle zoom</source>
      <translation>Toggle zoom</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="50"/>
      <source>Next</source>
      <translation>Next</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="52"/>
      <source>Original image content</source>
      <translation>Original image content</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="53"/>
      <source>Loading...</source>
      <translation>Loading...</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="55"/>
      <source>Select from generated image options.</source>
      <translation>Select from generated image options.</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="60"/>
      <source>Ctrl+LMB or MMB and drag: pan view, mouse wheel: zoom, Esc: discard all options</source>
      <translation>Ctrl+LMB or MMB and drag: pan view, mouse wheel: zoom, Esc: discard all options</translation>
    </message>
    <message>
      <location filename="../../src/ui/generated_image_selector.py" line="61"/>
      <source>Ctrl+LMB or MMB and drag: pan view, mouse wheel: zoom, Enter: select option, Esc: return to full view</source>
      <translation>Ctrl+LMB or MMB and drag: pan view, mouse wheel: zoom, Enter: select option, Esc: return to full view</translation>
    </message>
  </context>
  <context>
    <name>ui.graphics_items.click_and_drag_selection</name>
    <message>
      <location filename="../../src/ui/graphics_items/click_and_drag_selection.py" line="25"/>
      <source>Rectangle</source>
      <translation>Rectangle</translation>
    </message>
    <message>
      <location filename="../../src/ui/graphics_items/click_and_drag_selection.py" line="26"/>
      <source>Ellipse</source>
      <translation>Ellipse</translation>
    </message>
  </context>
  <context>
    <name>ui.input_fields.size_field</name>
    <message>
      <location filename="../../src/ui/input_fields/size_field.py" line="19"/>
      <source>W:</source>
      <translation>W:</translation>
    </message>
    <message>
      <location filename="../../src/ui/input_fields/size_field.py" line="20"/>
      <source>H:</source>
      <translation>H:</translation>
    </message>
  </context>
  <context>
    <name>ui.modal.image_filter_modal</name>
    <message>
      <location filename="../../src/ui/modal/image_filter_modal.py" line="22"/>
      <source>Change selected areas only</source>
      <translation>Change selected areas only</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_filter_modal.py" line="23"/>
      <source>Change active layer only</source>
      <translation>Change active layer only</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_filter_modal.py" line="24"/>
      <source>Cancel</source>
      <translation>Cancel</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_filter_modal.py" line="25"/>
      <source>Apply</source>
      <translation>Apply</translation>
    </message>
  </context>
  <context>
    <name>ui.modal.image_scale_modal</name>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="36"/>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="24"/>
      <source>Scale image</source>
      <translation>Scale image</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="25"/>
      <source>Width:</source>
      <translation>Width:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="26"/>
      <source>New image width in pixels</source>
      <translation>New image width in pixels</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="27"/>
      <source>Height:</source>
      <translation>Height:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="28"/>
      <source>New image height in pixels</source>
      <translation>New image height in pixels</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="29"/>
      <source>Width scale:</source>
      <translation>Width scale:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="30"/>
      <source>New image width (as multiplier)</source>
      <translation>New image width (as multiplier)</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="31"/>
      <source>Height scale:</source>
      <translation>Height scale:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="32"/>
      <source>New image height (as multiplier)</source>
      <translation>New image height (as multiplier)</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="33"/>
      <source>Upscale Method:</source>
      <translation>Upscale Method:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="34"/>
      <source>Use ControlNet Tiles</source>
      <translation>Use ControlNet Tiles</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="35"/>
      <source>ControlNet Downsample:</source>
      <translation>ControlNet Downsample:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/image_scale_modal.py" line="37"/>
      <source>Cancel</source>
      <translation>Cancel</translation>
    </message>
  </context>
  <context>
    <name>ui.modal.login_modal</name>
    <message>
      <location filename="../../src/ui/modal/login_modal.py" line="21"/>
      <source>Enter image generation server credentials:</source>
      <translation>Enter image generation server credentials:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/login_modal.py" line="22"/>
      <source>Username:</source>
      <translation>Username:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/login_modal.py" line="23"/>
      <source>Password:</source>
      <translation>Password:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/login_modal.py" line="24"/>
      <source>Log In</source>
      <translation>Log In</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/login_modal.py" line="25"/>
      <source>Cancel</source>
      <translation>Cancel</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/login_modal.py" line="27"/>
      <source>Username and password cannot be empty.</source>
      <translation>Username and password cannot be empty.</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/login_modal.py" line="28"/>
      <source>Unknown error, try again.</source>
      <translation>Unknown error, try again.</translation>
    </message>
  </context>
  <context>
    <name>ui.modal.modal_utils</name>
    <message>
      <location filename="../../src/ui/modal/modal_utils.py" line="28"/>
      <source>Open Image</source>
      <translation>Open Image</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/modal_utils.py" line="29"/>
      <source>Open Images as Layers</source>
      <translation>Open Images as Layers</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/modal_utils.py" line="30"/>
      <source>Save Image</source>
      <translation>Save Image</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/modal_utils.py" line="31"/>
      <source>Open failed</source>
      <translation>Open failed</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/modal_utils.py" line="33"/>
      <source>Images and IntraPaint projects</source>
      <translation>Images and IntraPaint projects</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/modal_utils.py" line="34"/>
      <source>Images</source>
      <translation>Images</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/modal_utils.py" line="36"/>
      <source>Don't show this again</source>
      <translation>Don't show this again</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/modal_utils.py" line="37"/>
      <source>Remember my choice</source>
      <translation>Remember my choice</translation>
    </message>
  </context>
  <context>
    <name>ui.modal.new_image_modal</name>
    <message>
      <location filename="../../src/ui/modal/new_image_modal.py" line="19"/>
      <source>Create new image</source>
      <translation>Create new image</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/new_image_modal.py" line="20"/>
      <source>Width:</source>
      <translation>Width:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/new_image_modal.py" line="21"/>
      <source>New image width in pixels</source>
      <translation>New image width in pixels</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/new_image_modal.py" line="22"/>
      <source>Height:</source>
      <translation>Height:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/new_image_modal.py" line="23"/>
      <source>New image height in pixels</source>
      <translation>New image height in pixels</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/new_image_modal.py" line="24"/>
      <source>Create</source>
      <translation>Create</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/new_image_modal.py" line="25"/>
      <source>Cancel</source>
      <translation>Cancel</translation>
    </message>
  </context>
  <context>
    <name>ui.modal.resize_canvas_modal</name>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="33"/>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="20"/>
      <source>Resize image canvas</source>
      <translation>Resize image canvas</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="21"/>
      <source>Width:</source>
      <translation>Width:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="22"/>
      <source>New image width in pixels</source>
      <translation>New image width in pixels</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="23"/>
      <source>Height:</source>
      <translation>Height:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="24"/>
      <source>New image height in pixels</source>
      <translation>New image height in pixels</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="25"/>
      <source>X Offset:</source>
      <translation>X Offset:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="26"/>
      <source>Distance in pixels from the left edge of the resized canvas to the left edge of the current image content</source>
      <translation>Distance in pixels from the left edge of the resized canvas to the left edge of the current image content</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="28"/>
      <source>Y Offset:</source>
      <translation>Y Offset:</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="29"/>
      <source>Distance in pixels from the top edge of the resized canvas to the top edge of the current image content</source>
      <translation>Distance in pixels from the top edge of the resized canvas to the top edge of the current image content</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="31"/>
      <source>Center</source>
      <translation>Center</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/resize_canvas_modal.py" line="32"/>
      <source>Cancel</source>
      <translation>Cancel</translation>
    </message>
  </context>
  <context>
    <name>ui.modal.settings_modal</name>
    <message>
      <location filename="../../src/ui/modal/settings_modal.py" line="34"/>
      <source>Cancel</source>
      <translation>Cancel</translation>
    </message>
    <message>
      <location filename="../../src/ui/modal/settings_modal.py" line="35"/>
      <source>Save</source>
      <translation>Save</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.controlnet_panel</name>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="32"/>
      <source>ControlNet</source>
      <translation>ControlNet</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="33"/>
      <source>ControlNet Unit {unit_number}</source>
      <translation>ControlNet Unit {unit_number}</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="34"/>
      <source>Enable ControlNet Unit</source>
      <translation>Enable ControlNet Unit</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="35"/>
      <source>Low VRAM</source>
      <translation>Low VRAM</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="36"/>
      <source>Pixel Perfect</source>
      <translation>Pixel Perfect</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="37"/>
      <source>Control Image:</source>
      <translation>Control Image:</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="38"/>
      <source>Set Control Image</source>
      <translation>Set Control Image</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="39"/>
      <source>Generation Area as Control</source>
      <translation>Generation Area as Control</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="40"/>
      <source>Control Type</source>
      <translation>Control Type</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="41"/>
      <source>Control Module</source>
      <translation>Control Module</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="42"/>
      <source>Control Model</source>
      <translation>Control Model</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="43"/>
      <source>Options</source>
      <translation>Options</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="44"/>
      <source>Control Weight</source>
      <translation>Control Weight</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="45"/>
      <source>Starting Control Step</source>
      <translation>Starting Control Step</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/controlnet_panel.py" line="46"/>
      <source>Ending Control Step</source>
      <translation>Ending Control Step</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.generators.sd_webui_panel</name>
    <message>
      <location filename="../../src/ui/panel/generators/sd_webui_panel.py" line="26"/>
      <source>Interrogate</source>
      <translation>Interrogate</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/generators/sd_webui_panel.py" line="27"/>
      <source>Attempt to generate a prompt that describes the current image generation area</source>
      <translation>Attempt to generate a prompt that describes the current image generation area</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.image_panel</name>
    <message>
      <location filename="../../src/ui/panel/image_panel.py" line="24"/>
      <source>Scale:</source>
      <translation>Scale:</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/image_panel.py" line="25"/>
      <source>Reset View</source>
      <translation>Reset View</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/image_panel.py" line="26"/>
      <source>Restore default image zoom and offset</source>
      <translation>Restore default image zoom and offset</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/image_panel.py" line="27"/>
      <source>Zoom in</source>
      <translation>Zoom in</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/image_panel.py" line="28"/>
      <source>Zoom in on the area selected for image generation</source>
      <translation>Zoom in on the area selected for image generation</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/image_panel.py" line="30"/>
      <source>Show tool control hints</source>
      <translation>Show tool control hints</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/image_panel.py" line="31"/>
      <source>Hide tool control hints</source>
      <translation>Hide tool control hints</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.layer.image_layer_widget</name>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="42"/>
      <source>Move up</source>
      <translation>Move up</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="43"/>
      <source>Move down</source>
      <translation>Move down</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="44"/>
      <source>Copy</source>
      <translation>Copy</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="45"/>
      <source>Delete</source>
      <translation>Delete</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="46"/>
      <source>Merge down</source>
      <translation>Merge down</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="47"/>
      <source>Clear selected</source>
      <translation>Clear selected</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="48"/>
      <source>Copy selected to new layer</source>
      <translation>Copy selected to new layer</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="49"/>
      <source>Layer to image size</source>
      <translation>Layer to image size</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="50"/>
      <source>Crop layer to content</source>
      <translation>Crop layer to content</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="51"/>
      <source>Clear selection</source>
      <translation>Clear selection</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="52"/>
      <source>Select all in active layer</source>
      <translation>Select all in active layer</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="53"/>
      <source>Invert selection</source>
      <translation>Invert selection</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="54"/>
      <source>Mirror vertically</source>
      <translation>Mirror vertically</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="55"/>
      <source>Mirror horizontally</source>
      <translation>Mirror horizontally</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_widget.py" line="56"/>
      <source>{src_layer_name} copied content</source>
      <translation>{src_layer_name} copied content</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.layer.layer_alpha_lock_button</name>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_alpha_lock_button.py" line="20"/>
      <source>Toggle layer transparency lock</source>
      <translation>Toggle layer transparency lock</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.layer.layer_lock_button</name>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_lock_button.py" line="19"/>
      <source>Toggle layer lock</source>
      <translation>Toggle layer lock</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.layer.layer_visibility_button</name>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_visibility_button.py" line="20"/>
      <source>Toggle layer visibility</source>
      <translation>Toggle layer visibility</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.layer_ui.layer_panel</name>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_panel.py" line="30"/>
      <source>Image Layers</source>
      <translation>Image Layers</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_panel.py" line="31"/>
      <source>Create a new layer above the current active layer.</source>
      <translation>Create a new layer above the current active layer.</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_panel.py" line="32"/>
      <source>Delete the active layer.</source>
      <translation>Delete the active layer.</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_panel.py" line="33"/>
      <source>Move the active layer up.</source>
      <translation>Move the active layer up.</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_panel.py" line="34"/>
      <source>Move the active layer down.</source>
      <translation>Move the active layer down.</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_panel.py" line="35"/>
      <source>Merge the active layer with the one below it.</source>
      <translation>Merge the active layer with the one below it.</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_panel.py" line="36"/>
      <source>Merge Down</source>
      <translation>Merge Down</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_panel.py" line="37"/>
      <source>Opacity:</source>
      <translation>Opacity:</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/layer_ui/layer_panel.py" line="38"/>
      <source>Layer mode:</source>
      <translation>Layer mode:</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.mypaint_brush_panel</name>
    <message>
      <location filename="../../src/ui/panel/mypaint_brush_panel.py" line="28"/>
      <source>favorites</source>
      <translation>favorites</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.tool_control_panels.brush_control_panel</name>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/brush_control_panel.py" line="25"/>
      <source>Paint selection only</source>
      <translation>Paint selection only</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.tool_control_panels.canvas_selection_panel</name>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/canvas_selection_panel.py" line="27"/>
      <source>Size:</source>
      <translation>Size:</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/canvas_selection_panel.py" line="28"/>
      <source>Draw</source>
      <translation>Draw</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/canvas_selection_panel.py" line="29"/>
      <source>Erase</source>
      <translation>Erase</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/canvas_selection_panel.py" line="30"/>
      <source>Clear</source>
      <translation>Clear</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/canvas_selection_panel.py" line="31"/>
      <source>Fill</source>
      <translation>Fill</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.tool_control_panels.draw_tool_panel</name>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/draw_tool_panel.py" line="27"/>
      <source>Draw in selection only</source>
      <translation>Draw in selection only</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.tool_control_panels.fill_selection_panel</name>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/fill_selection_panel.py" line="24"/>
      <source>Fill selection holes</source>
      <translation>Fill selection holes</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/fill_selection_panel.py" line="25"/>
      <source>Fill based on selection shape only.</source>
      <translation>Fill based on selection shape only.</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.tool_control_panels.selection_panel</name>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py" line="21"/>
      <source>Select All</source>
      <translation>Select All</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py" line="22"/>
      <source>Clear</source>
      <translation>Clear</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py" line="23"/>
      <source>Select All ({select_all_shortcut})</source>
      <translation>Select All ({select_all_shortcut})</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/selection_panel.py" line="24"/>
      <source>Clear ({clear_shortcut})</source>
      <translation>Clear ({clear_shortcut})</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.tool_control_panels.text_panel</name>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="31"/>
      <source>Font:</source>
      <translation>Font:</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="32"/>
      <source>Font Size:</source>
      <translation>Font Size:</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="33"/>
      <source>Enter Text:</source>
      <translation>Enter Text:</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="34"/>
      <source>Stretch</source>
      <translation>Stretch</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="35"/>
      <source>Text Color</source>
      <translation>Text Color</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="36"/>
      <source>Background Color</source>
      <translation>Background Color</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="37"/>
      <source>Update width and height to fit the current text exactly.</source>
      <translation>Update width and height to fit the current text exactly.</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="38"/>
      <source>Change the font size to the largest size that will fit in the text bounds.</source>
      <translation>Change the font size to the largest size that will fit in the text bounds.</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="39"/>
      <source>Set text color</source>
      <translation>Set text color</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="40"/>
      <source>Set text background color</source>
      <translation>Set text background color</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="42"/>
      <source>Alignment:</source>
      <translation>Alignment:</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="43"/>
      <source>Left</source>
      <translation>Left</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="44"/>
      <source>Center</source>
      <translation>Center</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="45"/>
      <source>Right</source>
      <translation>Right</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="47"/>
      <source>Pixels</source>
      <translation>Pixels</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="48"/>
      <source>Point</source>
      <translation>Point</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="50"/>
      <source>Text Style:</source>
      <translation>Text Style:</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="51"/>
      <source>Bold</source>
      <translation>Bold</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="52"/>
      <source>Italic</source>
      <translation>Italic</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="53"/>
      <source>Overline</source>
      <translation>Overline</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="54"/>
      <source>Strikeout</source>
      <translation>Strikeout</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="55"/>
      <source>Underline</source>
      <translation>Underline</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="56"/>
      <source>Fixed Pitch</source>
      <translation>Fixed Pitch</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="57"/>
      <source>Kerning</source>
      <translation>Kerning</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="58"/>
      <source>Fill Background</source>
      <translation>Fill Background</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="59"/>
      <source>Resize Font to Bounds</source>
      <translation>Resize Font to Bounds</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_control_panels/text_tool_panel.py" line="60"/>
      <source>Resize Bounds to Text</source>
      <translation>Resize Bounds to Text</translation>
    </message>
  </context>
  <context>
    <name>ui.panel.tool_panel</name>
    <message>
      <location filename="../../src/ui/panel/tool_panel.py" line="31"/>
      <source>Tools</source>
      <translation>Tools</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_panel.py" line="32"/>
      <source>Generate</source>
      <translation>Generate</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_panel.py" line="33"/>
      <source>Layers</source>
      <translation>Layers</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_panel.py" line="34"/>
      <source>Color</source>
      <translation>Color</translation>
    </message>
    <message>
      <location filename="../../src/ui/panel/tool_panel.py" line="35"/>
      <source>Navigation</source>
      <translation>Navigation</translation>
    </message>
  </context>
  <context>
    <name>ui.widget.brush_color_button</name>
    <message>
      <location filename="../../src/ui/widget/brush_color_button.py" line="20"/>
      <source>Color</source>
      <translation>Color</translation>
    </message>
    <message>
      <location filename="../../src/ui/widget/brush_color_button.py" line="21"/>
      <source>Select paint color</source>
      <translation>Select paint color</translation>
    </message>
  </context>
  <context>
    <name>ui.widget.color_picker</name>
    <message>
      <location filename="../../src/ui/widget/color_picker.py" line="17"/>
      <source>Basic Palette</source>
      <translation>Basic Palette</translation>
    </message>
    <message>
      <location filename="../../src/ui/widget/color_picker.py" line="18"/>
      <source>Custom Palette</source>
      <translation>Custom Palette</translation>
    </message>
    <message>
      <location filename="../../src/ui/widget/color_picker.py" line="19"/>
      <source>Spectrum</source>
      <translation>Spectrum</translation>
    </message>
    <message>
      <location filename="../../src/ui/widget/color_picker.py" line="20"/>
      <source>Palette</source>
      <translation>Palette</translation>
    </message>
    <message>
      <location filename="../../src/ui/widget/color_picker.py" line="21"/>
      <source>Color Component</source>
      <translation>Color Component</translation>
    </message>
  </context>
  <context>
    <name>ui.window.extra_network_window</name>
    <message>
      <location filename="../../src/ui/window/extra_network_window.py" line="29"/>
      <source>Lora Models</source>
      <translation>Lora Models</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/extra_network_window.py" line="31"/>
      <source>Add to prompt</source>
      <translation>Add to prompt</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/extra_network_window.py" line="32"/>
      <source>Remove from prompt</source>
      <translation>Remove from prompt</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/extra_network_window.py" line="33"/>
      <source>Close</source>
      <translation>Close</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/extra_network_window.py" line="34"/>
      <source>LORA</source>
      <translation>LORA</translation>
    </message>
  </context>
  <context>
    <name>ui.window.generator_setup_window</name>
    <message>
      <location filename="../../src/ui/window/generator_setup_window.py" line="24"/>
      <source>Image Generator Selection</source>
      <translation>Image Generator Selection</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/generator_setup_window.py" line="25"/>
      <source>Activate</source>
      <translation>Activate</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/generator_setup_window.py" line="26"/>
      <source>&lt;h2&gt;Status:&lt;/h2&gt;</source>
      <translation>&lt;h2&gt;Status:&lt;/h2&gt;</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/generator_setup_window.py" line="27"/>
      <source>Generator is active.</source>
      <translation>Generator is active.</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/generator_setup_window.py" line="28"/>
      <source>Generator is available.</source>
      <translation>Generator is available.</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/generator_setup_window.py" line="29"/>
      <source>&lt;h1&gt;Generator Options:&lt;/h1&gt;</source>
      <translation>&lt;h1&gt;Generator Options:&lt;/h1&gt;</translation>
    </message>
  </context>
  <context>
    <name>ui.window.main_window</name>
    <message>
      <location filename="../../src/ui/window/main_window.py" line="43"/>
      <source>Image Generation</source>
      <translation>Image Generation</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/main_window.py" line="44"/>
      <source>Tools</source>
      <translation>Tools</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/main_window.py" line="45"/>
      <source>Move up</source>
      <translation>Move up</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/main_window.py" line="46"/>
      <source>Move down</source>
      <translation>Move down</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/main_window.py" line="47"/>
      <source>Move left</source>
      <translation>Move left</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/main_window.py" line="48"/>
      <source>Move right</source>
      <translation>Move right</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/main_window.py" line="49"/>
      <source>Move all tabs here</source>
      <translation>Move all tabs here</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/main_window.py" line="52"/>
      <source>Loading...</source>
      <translation>Loading...</translation>
    </message>
  </context>
  <context>
    <name>ui.window.prompt_style_window</name>
    <message>
      <location filename="../../src/ui/window/prompt_style_window.py" line="28"/>
      <source>Name:</source>
      <translation>Name:</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/prompt_style_window.py" line="29"/>
      <source>Prompt:</source>
      <translation>Prompt:</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/prompt_style_window.py" line="30"/>
      <source>Negative:</source>
      <translation>Negative:</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/prompt_style_window.py" line="31"/>
      <source>Add to prompt</source>
      <translation>Add to prompt</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/prompt_style_window.py" line="32"/>
      <source>Replace prompt</source>
      <translation>Replace prompt</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/prompt_style_window.py" line="33"/>
      <source>Save changes</source>
      <translation>Save changes</translation>
    </message>
    <message>
      <location filename="../../src/ui/window/prompt_style_window.py" line="34"/>
      <source>Close</source>
      <translation>Close</translation>
    </message>
  </context>
  <context>
    <name>util.shared_constants</name>
    <message>
      <location filename="../../src/util/shared_constants.py" line="35"/>
      <source>Inpaint</source>
      <translation>Inpaint</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="36"/>
      <source>Text to Image</source>
      <translation>Text to Image</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="37"/>
      <source>Image to Image</source>
      <translation>Image to Image</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="43"/>
      <source>Generate</source>
      <translation>Generate</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="44"/>
      <source>W:</source>
      <translation>W:</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="45"/>
      <source>H:</source>
      <translation>H:</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="46"/>
      <source>X:</source>
      <translation>X:</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="47"/>
      <source>Y:</source>
      <translation>Y:</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="49"/>
      <source>Width:</source>
      <translation>Width:</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="50"/>
      <source>Height:</source>
      <translation>Height:</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="51"/>
      <source>Color:</source>
      <translation>Color:</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="52"/>
      <source>Size:</source>
      <translation>Size:</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="53"/>
      <source>Scale:</source>
      <translation>Scale:</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="54"/>
      <source>Padding:</source>
      <translation>Padding:</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="55"/>
      <source>Zoom In</source>
      <translation>Zoom In</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="56"/>
      <source>Reset Zoom</source>
      <translation>Reset Zoom</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="62"/>
      <source>Bilinear</source>
      <translation>Bilinear</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="63"/>
      <source>Nearest</source>
      <translation>Nearest</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="64"/>
      <source>Hamming</source>
      <translation>Hamming</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="65"/>
      <source>Bicubic</source>
      <translation>Bicubic</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="66"/>
      <source>Lanczos</source>
      <translation>Lanczos</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="67"/>
      <source>Box</source>
      <translation>Box</translation>
    </message>
    <message>
      <location filename="../../src/util/shared_constants.py" line="70"/>
      <source>{modifier_or_modifiers}:pick color - </source>
      <translation>{modifier_or_modifiers}:pick color - </translation>
    </message>
  </context>
  <context>
    <name>config.a1111_config</name>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="3"/>
      <source>Stable-Diffusion Model:</source>
      <translation>Stable-Diffusion Model:</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="5"/>
      <source>Active image generation model</source>
      <translation>Active image generation model</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="10"/>
      <source>Only keep one model on GPU/TPU</source>
      <translation>Only keep one model on GPU/TPU</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="12"/>
      <source>If selected, checkpoints after the first are cached in RAM instead</source>
      <translation>If selected, checkpoints after the first are cached in RAM instead</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="16"/>
      <source>Max checkpoints loaded:</source>
      <translation>Max checkpoints loaded:</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="18"/>
      <source>Number of image generation models to keep in memory.</source>
      <translation>Number of image generation models to keep in memory.</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="27"/>
      <source>Stable-Diffusion VAE model:</source>
      <translation>Stable-Diffusion VAE model:</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="29"/>
      <source>VAE model used for final image data creation.</source>
      <translation>VAE model used for final image data creation.</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="34"/>
      <source>Stable-Diffusion VAE models cached:</source>
      <translation>Stable-Diffusion VAE models cached:</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="36"/>
      <source>Number of VAE models to keep in memory.</source>
      <translation>Number of VAE models to keep in memory.</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="45"/>
      <source>CLIP skip:</source>
      <translation>CLIP skip:</translation>
    </message>
    <message>
      <location filename="../config/a1111_setting_definitions.json" line="47"/>
      <source>Number of final image generation steps taken without prompt guidance.</source>
      <translation>Number of final image generation steps taken without prompt guidance.</translation>
    </message>
  </context>
  <context>
    <name>config.application_config</name>
    <message>
      <location filename="../config/application_config_definitions.json" line="3"/>
      <source>Style:</source>
      <translation>Style:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="5"/>
      <source>Qt style to use for the user interface</source>
      <translation>Qt style to use for the user interface</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="12"/>
      <source>Theme:</source>
      <translation>Theme:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="14"/>
      <source>Theme to use for the user interface (may require restart)</source>
      <translation>Theme to use for the user interface (may require restart)</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="21"/>
      <source>Font size:</source>
      <translation>Font size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="23"/>
      <source>Font point size to use for user interface text (may require restart)</source>
      <translation>Font point size to use for user interface text (may require restart)</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="29"/>
      <source>Tab font size:</source>
      <translation>Tab font size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="31"/>
      <source>Font point size to use for user interface tab labels (may require restart)</source>
      <translation>Font point size to use for user interface tab labels (may require restart)</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="37"/>
      <source>Show active tool control hints:</source>
      <translation>Show active tool control hints:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="39"/>
      <source>Show control hints for the active tool below the image.</source>
      <translation>Show control hints for the active tool below the image.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="45"/>
      <source>Animate outlines and selections:</source>
      <translation>Animate outlines and selections:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="47"/>
      <source>Enable or disable animated outlines (may require restart)</source>
      <translation>Enable or disable animated outlines (may require restart)</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="53"/>
      <source>Selection overlay color:</source>
      <translation>Selection overlay color:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="55"/>
      <source>Overlay color used to highlight selected image areas</source>
      <translation>Overlay color used to highlight selected image areas</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="61"/>
      <source>Show selections in generated image options:</source>
      <translation>Show selections in generated image options:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="63"/>
      <source>Draw the selection borders when choosing inpainted image options.</source>
      <translation>Draw the selection borders when choosing inpainted image options.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="69"/>
      <source>Show generated images zoomed to changes:</source>
      <translation>Show generated images zoomed to changes:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="71"/>
      <source>When zooming in on individual inpainting options, focus the change region.</source>
      <translation>When zooming in on individual inpainting options, focus the change region.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="77"/>
      <source>Show generated image options at original size</source>
      <translation>Show generated image options at original size</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="79"/>
      <source>When the selected image size doesn't match the image generation resolution, preview options using the generated size.</source>
      <translation>When the selected image size doesn't match the image generation resolution, preview options using the generated size.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="85"/>
      <source>OpenGL acceleration:</source>
      <translation>OpenGL acceleration:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="87"/>
      <source>Use OpenGL to accelerate image rendering.  Currently somewhat buggy, breaks several layer rendering modes.</source>
      <translation>Use OpenGL to accelerate image rendering.  Currently somewhat buggy, breaks several layer rendering modes.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="93"/>
      <source>Tool tab bar:</source>
      <translation>Tool tab bar:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="95"/>
      <source>Toolbar where the tool tab is placed by default (TOP|BOTTOM|LEFT|RIGHT|LOWER or empty)</source>
      <translation>Toolbar where the tool tab is placed by default (TOP|BOTTOM|LEFT|RIGHT|LOWER or empty)</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="101"/>
      <source>Image generation tab bar:</source>
      <translation>Image generation tab bar:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="103"/>
      <source>Toolbar where the image generation tab is placed by default (TOP|BOTTOM|LEFT|RIGHT|LOWER or empty)</source>
      <translation>Toolbar where the image generation tab is placed by default (TOP|BOTTOM|LEFT|RIGHT|LOWER or empty)</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="109"/>
      <source>ControlNet tab bar:</source>
      <translation>ControlNet tab bar:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="111"/>
      <source>Toolbar where the ControlNet tab is placed by default (TOP|BOTTOM|LEFT|RIGHT|LOWER or empty)</source>
      <translation>Toolbar where the ControlNet tab is placed by default (TOP|BOTTOM|LEFT|RIGHT|LOWER or empty)</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="117"/>
      <source>Default image size:</source>
      <translation>Default image size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="119"/>
      <source>Default size when creating new images</source>
      <translation>Default size when creating new images</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="125"/>
      <source>Editing size:</source>
      <translation>Editing size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="127"/>
      <source>Current/initial size in pixels of the area selected for editing</source>
      <translation>Current/initial size in pixels of the area selected for editing</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="133"/>
      <source>Maximum editing size:</source>
      <translation>Maximum editing size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="135"/>
      <source>Maximum size in pixels of the area selected for editing</source>
      <translation>Maximum size in pixels of the area selected for editing</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="141"/>
      <source>Minimum editing size:</source>
      <translation>Minimum editing size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="143"/>
      <source>Minimum size in pixels of the area selected for editing</source>
      <translation>Minimum size in pixels of the area selected for editing</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="149"/>
      <source>Generation size:</source>
      <translation>Generation size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="151"/>
      <source>Current/initial size in pixels used for AI image generation</source>
      <translation>Current/initial size in pixels used for AI image generation</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="157"/>
      <source>Maximum generation size:</source>
      <translation>Maximum generation size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="159"/>
      <source>Maximum size in pixels allowed for AI image generation</source>
      <translation>Maximum size in pixels allowed for AI image generation</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="165"/>
      <source>Minimum generation size:</source>
      <translation>Minimum generation size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="167"/>
      <source>Minimum size in pixels allowed for AI image generation</source>
      <translation>Minimum size in pixels allowed for AI image generation</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="173"/>
      <source>Selection brush size:</source>
      <translation>Selection brush size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="175"/>
      <source>Current/initial brush size (in pixels) for the selection tool.</source>
      <translation>Current/initial brush size (in pixels) for the selection tool.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="186"/>
      <source>Brush size:</source>
      <translation>Brush size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="188"/>
      <source>Current/initial brush size (in pixels) for the drawing/painting tool.</source>
      <translation>Current/initial brush size (in pixels) for the drawing/painting tool.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="199"/>
      <source>Selected MyPaint brush:</source>
      <translation>Selected MyPaint brush:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="201"/>
      <source>Currently selected MyPaint brush file.</source>
      <translation>Currently selected MyPaint brush file.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="207"/>
      <source>Favorite MyPaint brushes:</source>
      <translation>Favorite MyPaint brushes:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="209"/>
      <source>Brushes to list in the 'Favorites' tab of the brush selection window</source>
      <translation>Brushes to list in the 'Favorites' tab of the brush selection window</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="215"/>
      <source>Maximum undo count:</source>
      <translation>Maximum undo count:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="217"/>
      <source>Number of actions that can be reversed using the 'undo' option.</source>
      <translation>Number of actions that can be reversed using the 'undo' option.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="223"/>
      <source>Undo merge interval (seconds):</source>
      <translation>Undo merge interval (seconds):</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="225"/>
      <source>Similar actions will be combined in the undo history if the time between them is less than this.</source>
      <translation>Similar actions will be combined in the undo history if the time between them is less than this.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="231"/>
      <source>'Speed modifier' key multiplier:</source>
      <translation>'Speed modifier' key multiplier:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="233"/>
      <source>Controls how much faster changes happen when the 'speed_modifier' key is held down</source>
      <translation>Controls how much faster changes happen when the 'speed_modifier' key is held down</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="239"/>
      <source>Prompt:</source>
      <translation>Prompt:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="241"/>
      <source>Description that generated images should match.</source>
      <translation>Description that generated images should match.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="247"/>
      <source>Negative prompt:</source>
      <translation>Negative prompt:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="249"/>
      <source>Description that generated images should not match.</source>
      <translation>Description that generated images should not match.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="255"/>
      <source>Guidance scale:</source>
      <translation>Guidance scale:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="257"/>
      <source>Controls how strongly the prompt and negative prompt are applied. Higher values are more consistent but may be less creative.  Overly high or low values may cause image distortion.</source>
      <translation>Controls how strongly the prompt and negative prompt are applied. Higher values are more consistent but may be less creative.  Overly high or low values may cause image distortion.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="268"/>
      <source>Batch size:</source>
      <translation>Batch size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="270"/>
      <source>Number of image options to simultaneously create in a single image editing operation. Increasing this value too much may result in errors or slowdown if GPU memory limits are reached.</source>
      <translation>Number of image options to simultaneously create in a single image editing operation. Increasing this value too much may result in errors or slowdown if GPU memory limits are reached.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="281"/>
      <source>Batch count:</source>
      <translation>Batch count:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="283"/>
      <source>Number of image batches to create in a single image editing operation. Increasing this value doesn't require additional memory, but it slows down image editing more than increasing the batch size does.</source>
      <translation>Number of image batches to create in a single image editing operation. Increasing this value doesn't require additional memory, but it slows down image editing more than increasing the batch size does.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="294"/>
      <source>Edit mode:</source>
      <translation>Edit mode:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="296"/>
      <source>Stable-Diffusion image editing mode. 'Text to Image' completely replaces the selected image section with new content, 'Image to Image' creates altered versions of the image selection, and 'Inpaint' works like 'Image to Image' except that it only affects areas selected by the mask tool</source>
      <translation>Stable-Diffusion image editing mode. 'Text to Image' completely replaces the selected image section with new content, 'Image to Image' creates altered versions of the image selection, and 'Inpaint' works like 'Image to Image' except that it only affects areas selected by the mask tool</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="307"/>
      <source>Masked content:</source>
      <translation>Masked content:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="309"/>
      <source>Determines what should be used to fill the masked area before inpainting. 'fill' replaces it with a solid color, 'original' keeps it as-is, 'latent noise' replaces it with random data, and 'latent nothing' clears it. Unless you're inpainting with a denoising strength &gt;0.8, 'original' will almost always be the best option</source>
      <translation>Determines what should be used to fill the masked area before inpainting. 'fill' replaces it with a solid color, 'original' keeps it as-is, 'latent noise' replaces it with random data, and 'latent nothing' clears it. Unless you're inpainting with a denoising strength &gt;0.8, 'original' will almost always be the best option</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="321"/>
      <source>Image interrogation model:</source>
      <translation>Image interrogation model:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="323"/>
      <source>Model used when auto-generating appropriate prompts using the 'interrogate' button. Supported values will vary based on what extensions you've installed into the stable-generation-webui, but 'clip' should always be accepted.</source>
      <translation>Model used when auto-generating appropriate prompts using the 'interrogate' button. Supported values will vary based on what extensions you've installed into the stable-generation-webui, but 'clip' should always be accepted.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="329"/>
      <source>Sampling steps:</source>
      <translation>Sampling steps:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="331"/>
      <source>Number of diffusion operations to perform when generating image data. Higher values take longer, but often produce more detailed and accurate results. Different stable-diffusion models and samplers have different requirements, but in most cates setting this higher than 30 has only minimal benefits</source>
      <translation>Number of diffusion operations to perform when generating image data. Higher values take longer, but often produce more detailed and accurate results. Different stable-diffusion models and samplers have different requirements, but in most cates setting this higher than 30 has only minimal benefits</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="342"/>
      <source>Denoising strength:</source>
      <translation>Denoising strength:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="344"/>
      <source>Controls how dramatically inpainting and image-to-image operations will change the initial image data. At 0.0, the image will be completely unedited, at 1.0 the image will be completely different</source>
      <translation>Controls how dramatically inpainting and image-to-image operations will change the initial image data. At 0.0, the image will be completely unedited, at 1.0 the image will be completely different</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="355"/>
      <source>Sampling method:</source>
      <translation>Sampling method:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="357"/>
      <source>Mathematical technique used to transform image data during the generation process. 'Euler a' works well in most cases, but certain models or extensions might perform better with other options.</source>
      <translation>Mathematical technique used to transform image data during the generation process. 'Euler a' works well in most cases, but certain models or extensions might perform better with other options.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="364"/>
      <source>Upscale method:</source>
      <translation>Upscale method:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="366"/>
      <source>Method to use when increasing image resolution. Available options will be loaded from the stable-diffusion-webui on launch.</source>
      <translation>Method to use when increasing image resolution. Available options will be loaded from the stable-diffusion-webui on launch.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="373"/>
      <source>ControlNet tiled upscaling</source>
      <translation>ControlNet tiled upscaling</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="375"/>
      <source>Whether to use the ControlNet tile model to improve image upscaling. When enabled and supported, all other image generation options will influence upscaling results. To use this, the ControlNet extension needs to be installed in the stable-diffusion-webui, and the controlnet tile model needs to be downloaded to the correct folder.</source>
      <translation>Whether to use the ControlNet tile model to improve image upscaling. When enabled and supported, all other image generation options will influence upscaling results. To use this, the ControlNet extension needs to be installed in the stable-diffusion-webui, and the controlnet tile model needs to be downloaded to the correct folder.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="381"/>
      <source>ControlNet tiled upscaling model:</source>
      <translation>ControlNet tiled upscaling model:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="383"/>
      <source>ControlNet model to use for tiled upscaling, in the 'filename [hash]' format used by the webui. This only needs to change if a newer model is available if using a stable diffusion model not based on stable-diffusion 1.5.</source>
      <translation>ControlNet model to use for tiled upscaling, in the 'filename [hash]' format used by the webui. This only needs to change if a newer model is available if using a stable diffusion model not based on stable-diffusion 1.5.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="389"/>
      <source>Tile downsample rate:</source>
      <translation>Tile downsample rate:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="391"/>
      <source>Adjusts how strongly the ControlNet tile model preserves the original image data, higher values result in fewer changes.</source>
      <translation>Adjusts how strongly the ControlNet tile model preserves the original image data, higher values result in fewer changes.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="402"/>
      <source>Mask blur:</source>
      <translation>Mask blur:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="404"/>
      <source>Pixel radius to blur in the inpainting mask to smoothly combine edited and original image content.</source>
      <translation>Pixel radius to blur in the inpainting mask to smoothly combine edited and original image content.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="415"/>
      <source>Seed:</source>
      <translation>Seed:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="417"/>
      <source>Number used to control pseudo-random aspects of image generation, in most cases using the same seed with the same settings and inputs will always produce the same results. If set to -1, a different random seed will be used for each image generation. </source>
      <translation>Number used to control pseudo-random aspects of image generation, in most cases using the same seed with the same settings and inputs will always produce the same results. If set to -1, a different random seed will be used for each image generation. </translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="428"/>
      <source>Inpaint Full Resolution</source>
      <translation>Inpaint Full Resolution</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="430"/>
      <source>If true, inpaint the masked area at higher resolution by ignoring the unmasked area. This can increase image quality by sacrificing awareness of additional image content.</source>
      <translation>If true, inpaint the masked area at higher resolution by ignoring the unmasked area. This can increase image quality by sacrificing awareness of additional image content.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="436"/>
      <source>Padding:</source>
      <translation>Padding:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="438"/>
      <source>Pixel radius outside of the masked area to include when inpainting when the 'Inpaint Full Resolution' option is enabled. Higher values increase contextual awareness while decreasing overall level of detail.</source>
      <translation>Pixel radius outside of the masked area to include when inpainting when the 'Inpaint Full Resolution' option is enabled. Higher values increase contextual awareness while decreasing overall level of detail.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="449"/>
      <source>Restore faces</source>
      <translation>Restore faces</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="451"/>
      <source>Use a face restoration model to correct image data after stable-diffusion runs. In most cases you'll probably get better results without it.</source>
      <translation>Use a face restoration model to correct image data after stable-diffusion runs. In most cases you'll probably get better results without it.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="457"/>
      <source>Tiling</source>
      <translation>Tiling</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="459"/>
      <source>Generate tiling images that can be seamlessly repeated.</source>
      <translation>Generate tiling images that can be seamlessly repeated.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="465"/>
      <source>ControlNet Settings (first layer)</source>
      <translation>ControlNet Settings (first layer)</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="467"/>
      <source>First layer ControlNet extension settings.</source>
      <translation>First layer ControlNet extension settings.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="473"/>
      <source>ControlNet Settings (second layer)</source>
      <translation>ControlNet Settings (second layer)</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="475"/>
      <source>Second layer ControlNet extension settings.</source>
      <translation>Second layer ControlNet extension settings.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="481"/>
      <source>ControlNet Settings (third layer)</source>
      <translation>ControlNet Settings (third layer)</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="475"/>
      <source>Second layer ControlNet extension settings.</source>
      <translation>Second layer ControlNet extension settings.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="492"/>
      <source>Detail reference count (cutn):</source>
      <translation>Detail reference count (cutn):</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="494"/>
      <source>Determines how many random cutouts from the input image are used to guide image generation. Higher values can introduce more detail and variation, but may also introduce more noise and irrelevant information.</source>
      <translation>Determines how many random cutouts from the input image are used to guide image generation. Higher values can introduce more detail and variation, but may also introduce more noise and irrelevant information.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="500"/>
      <source>Skip steps:</source>
      <translation>Skip steps:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="502"/>
      <source>Number of diffusion steps to skip. Higher values will result in faster image generation with decreased detail and accuracy.</source>
      <translation>Number of diffusion steps to skip. Higher values will result in faster image generation with decreased detail and accuracy.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="513"/>
      <source>Upscale mode:</source>
      <translation>Upscale mode:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="515"/>
      <source>Upscaling mode used when the inpainting resolution doesn't match the image generation area size.</source>
      <translation>Upscaling mode used when the inpainting resolution doesn't match the image generation area size.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="522"/>
      <source>Downscale mode:</source>
      <translation>Downscale mode:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="524"/>
      <source>Downscaling mode used when the inpainting resolution doesn't match the image generation area size.</source>
      <translation>Downscaling mode used when the inpainting resolution doesn't match the image generation area size.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="531"/>
      <source>Enable global error handler:</source>
      <translation>Enable global error handler:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="533"/>
      <source>Attempt to catch and report global application errors instead of crashing. Disabling this makes it easier to debug certain errors.</source>
      <translation>Attempt to catch and report global application errors instead of crashing. Disabling this makes it easier to debug certain errors.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="539"/>
      <source>Warn about keybinding issues:</source>
      <translation>Warn about keybinding issues:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="541"/>
      <source>Show an alert when keybinding issues are found on startup.</source>
      <translation>Show an alert when keybinding issues are found on startup.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="547"/>
      <source>Warn when saving without layers:</source>
      <translation>Warn when saving without layers:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="549"/>
      <source>Show a warning popup when saving a multi-layer image in a format that discards layer data.</source>
      <translation>Show a warning popup when saving a multi-layer image in a format that discards layer data.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="555"/>
      <source>Warn when saving without transparency:</source>
      <translation>Warn when saving without transparency:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="557"/>
      <source>Show a warning popup when saving an image with transparency in a format that doesn't support it.</source>
      <translation>Show a warning popup when saving an image with transparency in a format that doesn't support it.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="563"/>
      <source>Warn when saving without metadata:</source>
      <translation>Warn when saving without metadata:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="565"/>
      <source>Show a warning popup when saving an image in a format that discards metadata.</source>
      <translation>Show a warning popup when saving an image in a format that discards metadata.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="571"/>
      <source>Warn when saving in a format that cannot be loaded:</source>
      <translation>Warn when saving in a format that cannot be loaded:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="573"/>
      <source>Show a warning popup when saving an image in a format that can't be loaded.</source>
      <translation>Show a warning popup when saving an image in a format that can't be loaded.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="579"/>
      <source>Warn when saving in a format that changes image size:</source>
      <translation>Warn when saving in a format that changes image size:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="581"/>
      <source>Show a warning popup when saving an image in a format requires a specific resolution.</source>
      <translation>Show a warning popup when saving an image in a format requires a specific resolution.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="587"/>
      <source>Warn when saving in a format that removes color:</source>
      <translation>Warn when saving in a format that removes color:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="589"/>
      <source>Show a warning popup when saving an image in a format that does not support color.</source>
      <translation>Show a warning popup when saving an image in a format that does not support color.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="595"/>
      <source>Warn when loading libmypaint fails:</source>
      <translation>Warn when loading libmypaint fails:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="597"/>
      <source>Show a warning popup when the brush tool cannot be used because of missing libraries.</source>
      <translation>Show a warning popup when the brush tool cannot be used because of missing libraries.</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="603"/>
      <source>Always save metadata:</source>
      <translation>Always save metadata:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="605"/>
      <source>Always save metadata when no previous metadata exists(confirm), never do that(cancel), or ask every time(always_ask).</source>
      <translation>Always save metadata when no previous metadata exists(confirm), never do that(cancel), or ask every time(always_ask).</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="611"/>
      <source>Always update metadata:</source>
      <translation>Always update metadata:</translation>
    </message>
    <message>
      <location filename="../config/application_config_definitions.json" line="613"/>
      <source>Always update metadata when images are saved(confirm), never do that(cancel), or ask every time(always_ask).</source>
      <translation>Always update metadata when images are saved(confirm), never do that(cancel), or ask every time(always_ask).</translation>
    </message>
  </context>
  <context>
    <name>config.cache</name>
    <message>
      <location filename="../config/cache_value_definitions.json" line="2"/>
      <source>styles</source>
      <translation>styles</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="5"/>
      <source>Saved style prompts loaded from the webui</source>
      <translation>Saved style prompts loaded from the webui</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="11"/>
      <source>ControlNet version:</source>
      <translation>ControlNet version:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="13"/>
      <source>ControlNet extension version loaded from the webui</source>
      <translation>ControlNet extension version loaded from the webui</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="19"/>
      <source>ControlNet control types:</source>
      <translation>ControlNet control types:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="21"/>
      <source>ControlNet control type definitions loaded from the webui</source>
      <translation>ControlNet control type definitions loaded from the webui</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="27"/>
      <source>ControlNet modules:</source>
      <translation>ControlNet modules:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="29"/>
      <source>ControlNet module definitions loaded from the webui</source>
      <translation>ControlNet module definitions loaded from the webui</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="35"/>
      <source>ControlNet models:</source>
      <translation>ControlNet models:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="37"/>
      <source>ControlNet model definitions loaded from the webui</source>
      <translation>ControlNet model definitions loaded from the webui</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="43"/>
      <source>LoRA models:</source>
      <translation>LoRA models:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="45"/>
      <source>LoRA model definitions loaded from the webui</source>
      <translation>LoRA model definitions loaded from the webui</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="51"/>
      <source>Last seed:</source>
      <translation>Last seed:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="53"/>
      <source>Last seed used for image generation</source>
      <translation>Last seed used for image generation</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="59"/>
      <source>Last file path:</source>
      <translation>Last file path:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="61"/>
      <source>Last image file loaded</source>
      <translation>Last image file loaded</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="67"/>
      <source>Last brush color:</source>
      <translation>Last brush color:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="67"/>
      <source>Last brush color</source>
      <translation>Last brush color</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="75"/>
      <source>Background color:</source>
      <translation>Background color:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="77"/>
      <source>Last background color (text tool)</source>
      <translation>Last background color (text tool)</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="83"/>
      <source>Text tool parameters:</source>
      <translation>Text tool parameters:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="85"/>
      <source>Last text tool font and settings</source>
      <translation>Last text tool font and settings</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="91"/>
      <source>Last active tool:</source>
      <translation>Last active tool:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="93"/>
      <source>Label of the last active tool, to restore after restart</source>
      <translation>Label of the last active tool, to restore after restart</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="99"/>
      <source>Color threshold:</source>
      <translation>Color threshold:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="101"/>
      <source>Sets how closely colors need to match the clicked color to be selected. 0.0 only changes exact matching colors, higher values are more permissive.</source>
      <translation>Sets how closely colors need to match the clicked color to be selected. 0.0 only changes exact matching colors, higher values are more permissive.</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="112"/>
      <source>Sample Merged:</source>
      <translation>Sample Merged:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="114"/>
      <source>If checked, fill based on the entire image contents, not just the current layer</source>
      <translation>If checked, fill based on the entire image contents, not just the current layer</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="120"/>
      <source>Paint selection only:</source>
      <translation>Paint selection only:</translation>
    </message>
    <message>
      <location filename="../config/cache_value_definitions.json" line="122"/>
      <source>If checked, only paint within the selection bounds</source>
      <translation>If checked, only paint within the selection bounds</translation>
    </message>
  </context>
</TS>
