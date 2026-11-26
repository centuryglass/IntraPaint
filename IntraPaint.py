"""Runs the main IntraPaint inpainting UI.

Assuming you're running the ComfyUI or the Stable Diffusion WebUI API on the same machine with default settings, running
`python IntraPaint.py` should be all you need. For more information on options, run `python IntraPaint.py --help`
"""
import os
import sys

# noinspection PyUnreachableCode
if sys.version_info < (3, 11):
    version_str = '.'.join(map(str, sys.version_info))
    # noinspection PyUnresolvedReferences
    print(f'ERROR: Detected python version {version_str}, IntraPaint only supports Python 3.11 and higher.',
          file=sys.stderr)

import subprocess

from src.util.pyinstaller import is_pyinstaller_bundle
# In a bundle sys.executable is the IntraPaint binary, not Python, so the build subprocess below must stay gated.
if not is_pyinstaller_bundle():
    try:
        import src.util.visual.image_fill
    except ImportError:
        print('Building missing compiled image_fill module with cython...')
        build_result = subprocess.run([sys.executable, 'setup.py', 'build_ext', '--inplace'],
                                      cwd=os.path.dirname(os.path.abspath(__file__)), check=False)
        if build_result.returncode != 0:
            # Startup continues: only the fill tools need the compiled module (see ToolController).
            print('WARNING: Building the image_fill module failed, so the fill and magic wand tools will be '
                  'unavailable. Install a C compiler, then run `python setup.py build_ext --inplace` in the '
                  'IntraPaint directory to enable them. All other tools will work normally.', file=sys.stderr)


from src.startup import main  # Must come after the image_fill build above.

if __name__ == '__main__':
    sys.exit(main())
