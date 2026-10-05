# Bundled native libraries

Prebuilt libmypaint binaries that IntraPaint loads for the MyPaint brush tool. `load_libmypaint` in
`src/image/mypaint/libmypaint.py` defines the load order. A system libmypaint found by `ctypes.util.find_library` wins
over these on Linux. No file records where these binaries came from or how they were built. GitHub issue #65 tracks
rebuilding them with a recorded provenance.

| File | Platform | Notes |
|---|---|---|
| `libmypaint.so` | Linux x86_64 | Soname `libmypaint.so.0`, 1.5+/1.6 API with 64 brush settings. Needs `libjson-c.so.5`, `libglib-2.0.so.0`, `libgobject-2.0.so.0` and glibc 2.29 or newer from the system. |
| `libmypaint-1-4-0.dll` | Windows x86_64 | libmypaint 1.4.0, MinGW build, 56 brush settings. |
| `libiconv-2.dll`, `libintl-8.dll`, `libjson-c-2.dll` | Windows x86_64 | Dependencies of `libmypaint-1-4-0.dll`, loaded before it. |

- The brush setting count is not read from the library. `_get_max_setting_index` in
  `src/image/mypaint/mypaint_brush.py` hardcodes it per platform, so replacing a binary with a different settings
  count needs a matching change there.
- There is no macOS or aarch64 build.
