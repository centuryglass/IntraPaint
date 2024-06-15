"""Instantiate an object, read its dynamic attributes, and add appropriate type hints in the class definition.

Use this on any class with dynamic attributes to get linters/IDEs to support them properly.
"""

import sys
import os
import importlib.util
import re
from PyQt5.QtWidgets import QApplication

app = QApplication(sys.argv)

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
module_path = sys.argv[-1]
DYNAMIC_PROP_LINE = f'\n\n    # DYNAMIC PROPERTIES:\n    # Generate with `python {__file__} {module_path}`\n'

assert module_path.endswith('.py') and os.path.isfile(module_path),  f'Expected Python file argument, got {module_path}'
module_name = os.path.basename(module_path)[:-3]
spec = importlib.util.spec_from_file_location(module_name, module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

altered_text = ''

def type_hint(value):
    if isinstance(value, int):
        return 'int'
    if isinstance(value, float):
        return 'float'
    if isinstance(value, str):
        return 'str'
    if isinstance(value, bool):
        return 'bool'
    def iter_hint(iterable):
        group_hints = set(type_hint(v) for v in iterable)
        if len(group_hints) == 1:
            return group_hints[0]
        return 'Any'
    if isinstance(value, set):
        return f'Set[{iter_hint(value)}]'
    if isinstance(value, tuple):
        return f'Tuple[{iter_hint(value)}]'
    if isinstance(value, list):
        return f'List[{iter_hint(value)}'
    if isinstance(value, dict):
        return f'Dict[{iter_hint(value.keys())},{iter_hint(value.values())}]'
    print(f'warning: unexpected value type: "{value}" (type {type(value)}), returning Any')
    return 'Any'


with open(module_path, 'r', encoding='utf-8') as file:
    file_text = file.read()

pattern = re.compile(r'(:?^|\n)[ \t]*class (?P<class_name>[a-zA-Z0-9_]*)(?:\:|\()[^\n]*\n+(?P<indent>[ \t]*)')
class_items = {}
search_text = file_text
file_idx = 0
while (match := re.search(pattern, file_text[file_idx:])) is not None:
    class_name = match.group('class_name')
    indent = match.group('indent')
    class_idx = match.start() + file_idx
    # Match the first non-empty line with indent less than the class level.
    # This won't work if you're mixing spaces and tabs, but you shouldn't be doing that anyway:
    non_class_pattern = re.compile('\n[ \\t]{0,' + str(len(indent) - 1) + '}[^ \\t\\n]')
    end_match = re.search(non_class_pattern, file_text[class_idx+1:])
    if end_match is not None:
        end_idx = class_idx + end_match.start()
    else:
        end_idx = len(file_text)
    class_items[class_name] = {'start': class_idx, 'end': end_idx, 'indent': indent}
    file_idx = end_idx

insertions = {}


for class_name, data in class_items.items():
    class_text = file_text[data['start']:data['end']]
    insert_index = data['end']
    indent = data['indent']
    if class_name not in dir(module):
        print(f'Couldn\'t find {class_name} in {module_name}, it\'s probably a nested class.  Skipping it.')
        continue
    class_type = getattr(module, class_name)
    inserted = ""

    if (idx := class_text.find(DYNAMIC_PROP_LINE)) != -1:
        class_text = class_text[:idx]
        insert_index = idx + data['start']

    # Some classes don't load dynamic properties until an instance exists, so try creating object instances:
    try:
        instance = class_type()
    except Exception:
        print(f'{class_name} instantiation failed, this may or may not harm {__file__} functionality')
    for attr_name in dir(class_type):
        if attr_name.startswith('_') or f' {attr_name}' in class_text:
            continue
        value = getattr(class_type, attr_name)
        if 'builtin' in str(type(value)):
            continue
        if any(hasattr(base, attr_name) for base in class_type.__bases__):
            continue
        inserted += f'\n{indent}{attr_name.upper()}: {type_hint(value)}'
    if len(inserted) > 0:
        inserted = DYNAMIC_PROP_LINE + inserted
        insertions[insert_index] = (inserted, data)

indexes = list(insertions.keys())
indexes.sort()
for idx in reversed(indexes):
    text, data = insertions[idx]
    file_text = file_text[:idx] + text + file_text[data['end']:]

with open(module_path, 'w', encoding='utf-8') as file:
    file.write(file_text)
