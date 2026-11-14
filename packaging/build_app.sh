#!/bin/bash
# Build "Shoot Sorter.app" for Apple silicon.
#
# The app bundles:
#   Contents/MacOS/ShootSorter        native menu-bar launcher (Swift)
#   Contents/Resources/python/        standalone CPython 3.12 + requirements.txt
#   Contents/Resources/app/           Shoot Sorter code (tracked files only)
#   Contents/Resources/runtime/       first-run setup and runtime-home helpers
#
# Models are not bundled. They are downloaded on first run into
# ~/Library/Application Support/Shoot Sorter.
#
# Usage: packaging/build_app.sh [--clean] [--skip-python]
#   --clean        rebuild the cached Python runtime from scratch
#   --skip-python  reuse the cached runtime without re-running pip
#
# Output: packaging/build/Shoot Sorter.app (ad-hoc signed)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
BUILD="${SHOOT_SORTER_BUILD_DIR:-$HERE/build}"
CACHE="$BUILD/cache"
APP="$BUILD/Shoot Sorter.app"

APP_VERSION="${APP_VERSION:-$(cat "$HERE/VERSION" 2>/dev/null || echo 1.0.0)}"
PYTHON_VER="3.12"
UV_VER="0.13.7"
EXIFTOOL_VER="13.61"
BUNDLE_ID="com.shootsorter.app"

CLEAN=0
SKIP_PY=0
for a in "$@"; do
  case "$a" in
    --clean) CLEAN=1 ;;
    --skip-python) SKIP_PY=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a" >&2; exit 2 ;;
  esac
done

say() { printf '\n==> %s\n' "$*"; }

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "Build on an Apple-silicon Mac (arm64)." >&2
  exit 1
fi
for t in swiftc codesign curl tar rsync git; do
  command -v "$t" >/dev/null || { echo "Missing $t (install Xcode or its command-line tools)." >&2; exit 1; }
done

mkdir -p "$CACHE"
BUILD_NUM="$(git -C "$REPO" rev-list --count HEAD 2>/dev/null || echo 1)"
GIT_SHA="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"

# ---------------------------------------------------------------- uv
UV="$CACHE/uv/uv"
if [[ ! -x "$UV" ]]; then
  say "Downloading uv $UV_VER (build tool only, not shipped)"
  mkdir -p "$CACHE/uv"
  curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VER}/uv-aarch64-apple-darwin.tar.gz" \
    | tar -xz -C "$CACHE/uv" --strip-components=1
fi
export UV_CACHE_DIR="$CACHE/uvcache"
export UV_PYTHON_INSTALL_DIR="$CACHE/pythons"
export UV_PYTHON_PREFERENCE=only-managed

# ---------------------------------------------------------------- Python runtime
RUNTIME="$CACHE/runtime"
if [[ "$CLEAN" -eq 1 ]]; then
  rm -rf "$RUNTIME"
fi
if [[ ! -x "$RUNTIME/bin/python3" ]]; then
  say "Fetching standalone CPython $PYTHON_VER (python-build-standalone via uv)"
  "$UV" python install "$PYTHON_VER"
  SRC_PY="$("$UV" python find "$PYTHON_VER")"
  SRC_ROOT="$(cd "$(dirname "$SRC_PY")/.." && pwd -P)"
  rm -rf "$RUNTIME"
  rsync -a "$SRC_ROOT"/ "$RUNTIME"/
  SKIP_PY=0
fi
PY="$RUNTIME/bin/python3"
if [[ "$SKIP_PY" -eq 0 ]]; then
  say "Installing requirements into the bundled runtime (several minutes the first time)"
  # The runtime is private to the app, so installing into it directly is intended.
  "$UV" pip install --python "$PY" --break-system-packages -r "$REPO/requirements.txt"
fi
"$PY" -c 'import sys, platform; assert platform.machine()=="arm64", platform.machine(); print("runtime", sys.version.split()[0])'

# ---------------------------------------------------------------- ExifTool (bundled; small, Perl)
EXIF_DIR="$CACHE/Image-ExifTool-$EXIFTOOL_VER"
if [[ ! -x "$EXIF_DIR/exiftool" ]]; then
  say "Downloading ExifTool $EXIFTOOL_VER"
  # exiftool.org only keeps the newest release; older ones move to SourceForge.
  curl -fsSL "https://exiftool.org/Image-ExifTool-$EXIFTOOL_VER.tar.gz" -o "$CACHE/exiftool.tgz" 2>/dev/null \
    || curl -fsSL "https://sourceforge.net/projects/exiftool/files/Image-ExifTool-$EXIFTOOL_VER.tar.gz/download" -o "$CACHE/exiftool.tgz"
  tar -xzf "$CACHE/exiftool.tgz" -C "$CACHE"
  rm -f "$CACHE/exiftool.tgz"
fi

# ---------------------------------------------------------------- bundle skeleton
say "Assembling $APP"
rm -rf "$APP"
CONTENTS="$APP/Contents"
RES="$CONTENTS/Resources"
mkdir -p "$CONTENTS/MacOS" "$RES/app" "$RES/runtime"

# Python runtime, minus the test suite and other dead weight.
rsync -a \
  --exclude 'lib/python3.*/test/' \
  --exclude 'lib/python3.*/idlelib/' \
  --exclude 'lib/python3.*/turtledemo/' \
  --exclude 'lib/python3.*/site-packages/*/tests/' \
  --exclude 'lib/python3.*/site-packages/PyObjCTest/' \
  --exclude '*.dSYM/' \
  --exclude '__pycache__/' \
  "$RUNTIME"/ "$RES/python"/
rm -f "$RES"/python/lib/python3.*/EXTERNALLY-MANAGED

# App code: tracked files only, so local config, schedules and data never ship.
( cd "$REPO" && git ls-files -z ) | (
  cd "$REPO"
  while IFS= read -r -d '' f; do
    case "$f" in
      packaging/*|install.sh|INSTALL-LR.md|test_scripts.sh|tests/*|tests_*.py|gui/macos/*|.git*) continue ;;
    esac
    mkdir -p "$RES/app/$(dirname "$f")"
    cp -p "$f" "$RES/app/$f"
  done
)
mkdir -p "$RES/app/tools"
rsync -a "$EXIF_DIR"/ "$RES/app/tools/Image-ExifTool-$EXIFTOOL_VER"/
chmod +x "$RES/app/tag" "$RES/app/start-ollama.sh" "$RES/app/tools/Image-ExifTool-$EXIFTOOL_VER/exiftool"

cp "$HERE"/runtime/*.py "$HERE"/runtime/*.sh "$RES/runtime/"
chmod +x "$RES"/runtime/*.sh
cp "$REPO/LICENSE" "$REPO/THIRD_PARTY_LICENSES.md" "$RES/"
cp "$HERE/INSTALL.md" "$RES/INSTALL.md"

# Icon from the existing panel shortcut.
if [[ -f "$REPO/gui/macos/Shoot Sorter.app/Contents/Resources/AppIcon.icns" ]]; then
  cp "$REPO/gui/macos/Shoot Sorter.app/Contents/Resources/AppIcon.icns" "$RES/AppIcon.icns"
fi

cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Shoot Sorter</string>
  <key>CFBundleDisplayName</key><string>Shoot Sorter</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleExecutable</key><string>ShootSorter</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundleShortVersionString</key><string>$APP_VERSION</string>
  <key>CFBundleVersion</key><string>$BUILD_NUM</string>
  <key>ShootSorterGitRevision</key><string>$GIT_SHA</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSArchitecturePriority</key><array><string>arm64</string></array>
  <key>LSRequiresNativeExecution</key><true/>
  <key>LSUIElement</key><true/>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSHumanReadableCopyright</key><string>MIT licence. See LICENSE.</string>
</dict>
</plist>
PLIST

# ---------------------------------------------------------------- launcher
say "Compiling the menu-bar launcher"
swiftc -O -target arm64-apple-macos14.0 -framework AppKit \
  "$HERE/launcher/ShootSorterApp.swift" -o "$CONTENTS/MacOS/ShootSorter"

# ---------------------------------------------------------------- bytecode
say "Pre-compiling Python bytecode (the installed app folder is read-only)"
"$PY" -m compileall -q -j 0 "$RES/python/lib" >/dev/null 2>&1 || true
"$RES/python/bin/python3" -m compileall -q -j 0 "$RES/app" "$RES/runtime" >/dev/null

# ---------------------------------------------------------------- sanity
say "Checking the bundled runtime imports"
"$RES/python/bin/python3" - <<'PYCHK'
import importlib, sys
mods = ["torch", "torchvision", "open_clip", "rawpy", "PIL", "numpy", "cv2", "skimage",
        "sklearn", "scipy", "onnxruntime", "timm", "transformers", "huggingface_hub",
        "Vision", "Quartz", "AppKit", "requests", "yaml"]
bad = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as e:
        bad.append(f"{m}: {e}")
if bad:
    print("Import failures:\n  " + "\n  ".join(bad)); sys.exit(1)
print("all", len(mods), "imports OK on", sys.executable)
PYCHK

# ---------------------------------------------------------------- sign
say "Ad-hoc signing (no Developer ID available)"
xattr -cr "$APP"
codesign --force --deep --sign - --identifier "$BUNDLE_ID" "$APP"
codesign --verify --deep --strict "$APP"
echo "Built: $APP ($(du -sh "$APP" | cut -f1)), version $APP_VERSION ($BUILD_NUM, $GIT_SHA)"
