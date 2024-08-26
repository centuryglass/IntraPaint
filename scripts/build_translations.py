"""Generate Qt translation files"""
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ElementTree, Element

TS_PATH = 'resources/translations/main.ts'

python_files = []

for root, _, files in os.walk('src'):
    for file in files:
        if file.endswith('.py'):
            python_files.append(os.path.join(root, file))

tr_id_pattern = r"TR_ID = '(.*)'"

translation_files = []

for file in python_files:
    with open(file, 'r') as py_file:
        file_text = py_file.read()
    match = re.search(tr_id_pattern, file_text)
    if match is None:
        continue
    tr_id = match.group(1)
    translation_files.append(file)
    try:
        shutil.copyfile(file, file + '_backup')
        file_text = file_text.replace("_tr('", f"QApplication.translate('{tr_id}', '")
        with open(file, 'w') as py_file:
            py_file.write(file_text)
    except Exception as err:
        print(err)

try:
    command = ['pylupdate6', *translation_files, '-ts', TS_PATH]
    subprocess.run(command)
except Exception as err:
    print(err)


for file in translation_files:
    assert os.path.exists(file + '_backup')
    shutil.move(file + '_backup', file)

tree = ElementTree()
xml_root = tree.parse(TS_PATH)
assert xml_root.tag == 'TS'
xml_root.set('language', 'en_US')


def find_or_add_context(context_name):
    for context_elem in xml_root:
        if not context_elem.tag == 'context':
            continue
        name_tag = context_elem[0]
        assert name_tag.tag == 'name'
        if name_tag.text == context_name:
            return context_elem
    new_context_element = Element('context')
    name_element = Element('name')
    name_element.text = context_name
    new_context_element.append(name_element)
    xml_root.append(new_context_element)
    return new_context_element


def add_message(context_elem, filename, message, line=None):
    message_elem = Element('message')
    location_elem = Element('location', filename=filename)
    if line is not None:
        location_elem.set('line', str(line))
    message_elem.append(location_elem)
    source_elem = Element('source')
    source_elem.text = message
    message_elem.append(source_elem)
    message_elem.append(Element('translation', type='unfinished'))
    context_elem.append(message_elem)


for content_key, json_prefix in (
        ('a1111_config', 'a1111_setting'),
        ('application_config', 'application_config'),
        ('cache', 'cache_value'),
        ('key_config', 'key_config')
        ):
    full_key = f'config.{content_key}'
    src_path = f'../../src/config/{content_key}.py'
    json_path = f'resources/config/{json_prefix}_definitions.json'
    saved_json_path = f'../config/{json_prefix}_definitions.json'

    context_elem = find_or_add_context(full_key)
    with open(json_path, encoding='utf-8') as json_file:
        lines = json_file.readlines()
        json_data = json.loads('\n'.join(lines))

    def _find_line_num(text):
        for i, line in enumerate(lines):
            if text in line:
                return i + 1
        return None
    for entry in json_data.values():
        add_message(context_elem, saved_json_path, entry['label'], _find_line_num(entry['label']))
        add_message(context_elem, saved_json_path, entry['description'], _find_line_num(entry['description']))

# Copy sources to translations:
for context_elem in xml_root:
    if context_elem.tag != 'context':
        continue
    for message_elem in context_elem:
        if message_elem.tag != 'message':
            continue
        source_elem = message_elem[-2]
        assert source_elem.tag == 'source'
        source_text = source_elem.text
        translate_elem = message_elem[-1]
        assert translate_elem.tag == 'translation'
        message_elem.remove(translate_elem)
        translate_elem = Element('translation')
        message_elem.append(translate_elem)
        translate_elem.text = source_text

xml_content = ET.tostring(xml_root, encoding='utf-8').decode('utf-8')
xml_temp = 'temp.xml'
with open(xml_temp, 'w', encoding='utf-8') as ts_file:
    ts_file.write('<?xml version="1.0" encoding="utf-8"?>\n')
    ts_file.write('<!DOCTYPE TS>\n')
    ts_file.write(xml_content)
try:
    subprocess.run(['xmllint', '--format', xml_temp, '-o', TS_PATH])
except Exception:
    if os.path.exists(xml_temp):
        shutil.move(xml_temp, TS_PATH)
