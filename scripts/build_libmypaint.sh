#!/usr/bin/env bash
# Builds the libmypaint that IntraPaint bundles in lib/<platform tag>/, for Linux and macOS on the machine it runs on.
#
# Downloads the pinned libmypaint and json-c release tarballs, checks their sha256, builds json-c as a static library
# and links it into a shared libmypaint with i18n, introspection, GEGL and glib disabled. The result depends only on
# libc and libm (and libSystem on macOS). Windows libraries come from MSYS2 instead; see
# .github/workflows/native-libs.yml.
#
# Usage: scripts/build_libmypaint.sh [output dir]
#   Writes <output dir>/<platform tag>/ (default: build/native-libs/) holding the library and a BUILD_INFO.txt that
#   records the versions, sources, sha256 sums and flags, for lib/MANIFEST.md. Changing the pinned libmypaint version
#   means changing it in native-libs.yml's Windows job and EXPECTED_SETTING_COUNT in scripts/check_libmypaint.py,
#   rebuilding every platform and updating lib/MANIFEST.md.
#
# Needs a C compiler, make, cmake, pkg-config, curl and python3. On macOS, MACOSX_DEPLOYMENT_TARGET defaults to 11.0,
# the oldest release that supports arm64.
set -euo pipefail

LIBMYPAINT_VERSION=1.6.1
LIBMYPAINT_URL="https://github.com/mypaint/libmypaint/releases/download/v${LIBMYPAINT_VERSION}/libmypaint-${LIBMYPAINT_VERSION}.tar.xz"
LIBMYPAINT_SHA256=741754f293f6b7668f941506da07cd7725629a793108bb31633fb6c3eae5315f
JSON_C_VERSION=0.18
JSON_C_URL="https://s3.amazonaws.com/json-c_releases/releases/json-c-${JSON_C_VERSION}.tar.gz"
JSON_C_SHA256=876ab046479166b869afc6896d288183bbc0e5843f141200c677b3e8dfb11724

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_ROOT="$(mkdir -p "${1:-$PROJECT_DIR/build/native-libs}" && cd "${1:-$PROJECT_DIR/build/native-libs}" && pwd)"
PLATFORM_TAG="$(cd "$PROJECT_DIR" && python3 -c 'from src.util.platform_tag import PLATFORM_TAG; print(PLATFORM_TAG)')"
OUTPUT_DIR="$OUTPUT_ROOT/$PLATFORM_TAG"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
PREFIX="$WORK_DIR/prefix"

case "$(uname -s)" in
    Linux)
        OS=linux
        JOBS="$(nproc)"
        sha256() { sha256sum "$1" | cut -d' ' -f1; }
        ;;
    Darwin)
        OS=macos
        JOBS="$(sysctl -n hw.ncpu)"
        export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-11.0}"
        sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }
        ;;
    *)
        echo "Unsupported OS $(uname -s): build the Windows libraries with MSYS2 (.github/workflows/native-libs.yml)." >&2
        exit 1
        ;;
esac

# Downloads $1 to $2 and fails unless its sha256 is $3.
fetch() {
    curl --fail --silent --show-error --location --retry 3 --output "$2" "$1"
    local actual
    actual="$(sha256 "$2")"
    if [ "$actual" != "$3" ]; then
        echo "sha256 mismatch for $1: expected $3, got $actual" >&2
        exit 1
    fi
}

COMMON_CFLAGS="-O2 -fPIC"

echo "Building json-c $JSON_C_VERSION (static)"
fetch "$JSON_C_URL" "$WORK_DIR/json-c.tar.gz" "$JSON_C_SHA256"
tar -xzf "$WORK_DIR/json-c.tar.gz" -C "$WORK_DIR"
JSON_C_CMAKE_FLAGS=(
    -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_INSTALL_PREFIX="$PREFIX"
    -DCMAKE_INSTALL_LIBDIR=lib
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON
    -DBUILD_SHARED_LIBS=OFF
    -DBUILD_STATIC_LIBS=ON
    -DBUILD_TESTING=OFF
    -DBUILD_APPS=OFF
    -DDISABLE_EXTRA_LIBS=ON
)
cmake -S "$WORK_DIR/json-c-$JSON_C_VERSION" -B "$WORK_DIR/json-c-build" "${JSON_C_CMAKE_FLAGS[@]}" \
    -DCMAKE_C_FLAGS="$COMMON_CFLAGS"
cmake --build "$WORK_DIR/json-c-build" --parallel "$JOBS"
cmake --install "$WORK_DIR/json-c-build"

echo "Building libmypaint $LIBMYPAINT_VERSION"
fetch "$LIBMYPAINT_URL" "$WORK_DIR/libmypaint.tar.xz" "$LIBMYPAINT_SHA256"
tar -xJf "$WORK_DIR/libmypaint.tar.xz" -C "$WORK_DIR"
LIBMYPAINT_CONFIGURE_FLAGS=(
    --prefix="$PREFIX"
    --enable-shared
    --disable-static
    --disable-i18n
    --disable-nls
    --disable-openmp
    --disable-docs
    --disable-gegl
    --enable-introspection=no
    --without-glib
    --disable-dependency-tracking
)
LIBMYPAINT_LDFLAGS=""
if [ "$OS" = linux ]; then
    # Keeps the static json-c's symbols out of libmypaint's exports, so they can't clash with a system json-c.
    LIBMYPAINT_LDFLAGS="-Wl,--exclude-libs,ALL"
fi
(
    cd "$WORK_DIR/libmypaint-$LIBMYPAINT_VERSION"
    PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig" CFLAGS="$COMMON_CFLAGS" LDFLAGS="$LIBMYPAINT_LDFLAGS" \
        ./configure "${LIBMYPAINT_CONFIGURE_FLAGS[@]}"
    make -j"$JOBS"
    make install
)

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
if [ "$OS" = linux ]; then
    LIBRARY_FILE=libmypaint.so
    cp "$(readlink -f "$(ls "$PREFIX"/lib/libmypaint*.so | head -n 1)")" "$OUTPUT_DIR/$LIBRARY_FILE"
    strip --strip-unneeded "$OUTPUT_DIR/$LIBRARY_FILE"
    DEPENDENCIES="$(readelf -d "$OUTPUT_DIR/$LIBRARY_FILE" | grep NEEDED || true)"
    GLIBC_FLOOR="$(objdump -T "$OUTPUT_DIR/$LIBRARY_FILE" | grep -o 'GLIBC_[0-9.]*' | sort -uV | tail -n 1 || true)"
else
    LIBRARY_FILE=libmypaint.dylib
    cp "$(python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$PREFIX/lib/libmypaint.dylib")" \
        "$OUTPUT_DIR/$LIBRARY_FILE"
    install_name_tool -id "@rpath/$LIBRARY_FILE" "$OUTPUT_DIR/$LIBRARY_FILE"
    strip -x "$OUTPUT_DIR/$LIBRARY_FILE"
    codesign --force --sign - "$OUTPUT_DIR/$LIBRARY_FILE"
    DEPENDENCIES="$(otool -L "$OUTPUT_DIR/$LIBRARY_FILE" | tail -n +2)"
    GLIBC_FLOOR="n/a (minimum macOS $MACOSX_DEPLOYMENT_TARGET)"
fi

if echo "$DEPENDENCIES" | grep -Eqi 'json|glib|gobject|intl'; then
    echo "$LIBRARY_FILE links a library that should be built in or disabled:" >&2
    echo "$DEPENDENCIES" >&2
    exit 1
fi

SETTING_CHECK="$(python3 "$PROJECT_DIR/scripts/check_libmypaint.py" "$OUTPUT_DIR")"

cat > "$OUTPUT_DIR/BUILD_INFO.txt" <<EOF
platform: $PLATFORM_TAG
library: $LIBRARY_FILE
sha256: $(sha256 "$OUTPUT_DIR/$LIBRARY_FILE")
check: $SETTING_CHECK
libmypaint: $LIBMYPAINT_VERSION, $LIBMYPAINT_URL, sha256 $LIBMYPAINT_SHA256
json-c: $JSON_C_VERSION (static), $JSON_C_URL, sha256 $JSON_C_SHA256
compiler: $(cc --version | head -n 1)
CFLAGS: $COMMON_CFLAGS
json-c cmake flags: ${JSON_C_CMAKE_FLAGS[*]//$PREFIX/<prefix>}
libmypaint configure flags: ${LIBMYPAINT_CONFIGURE_FLAGS[*]//$PREFIX/<prefix>}
libmypaint LDFLAGS: $LIBMYPAINT_LDFLAGS
glibc floor: $GLIBC_FLOOR
dependencies:
$DEPENDENCIES
EOF
cat "$OUTPUT_DIR/BUILD_INFO.txt"
