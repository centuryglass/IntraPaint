# Bundled native libraries

Prebuilt libmypaint binaries that IntraPaint loads for the MyPaint brush tool. `load_libmypaint` in
`src/image/mypaint/libmypaint.py` defines the load order. A system libmypaint found by `ctypes.util.find_library` wins
over these on Linux. No file records where the binaries below came from or how they were built. GitHub issue #65 tracks
replacing them with libmypaint 1.6.1 builds from `.github/workflows/native-libs.yml`, which runs
`scripts/build_libmypaint.sh` on Linux and macOS and takes MSYS2's package on Windows.

| File | Platform | Notes |
|---|---|---|
| `libmypaint.so` | Linux x86_64 | Soname `libmypaint.so.0`, 1.5+/1.6 API with 64 brush settings. Needs `libjson-c.so.5`, `libglib-2.0.so.0`, `libgobject-2.0.so.0` and glibc 2.29 or newer from the system. |
| `libmypaint-1-4-0.dll` | Windows x86_64 | libmypaint 1.4.0, MinGW build, 56 brush settings. |
| `libiconv-2.dll`, `libintl-8.dll`, `libjson-c-2.dll` | Windows x86_64 | Dependencies of `libmypaint-1-4-0.dll`, loaded before it. |

- `_get_setting_count` in `src/image/mypaint/mypaint_brush.py` reads the brush setting count from the loaded library.
- `_load_from_dir` loads every file in `lib/<platform tag>/`, so the directory holds only libraries.
- There is no macOS or aarch64 build.
