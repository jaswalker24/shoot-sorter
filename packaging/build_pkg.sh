#!/bin/bash
# Build the Shoot Sorter installer package from packaging/build/Shoot Sorter.app.
#
# Usage: packaging/build_pkg.sh [--build-app]
#   --build-app   run build_app.sh first
#
# Output: packaging/build/ShootSorter-<version>.pkg (unsigned; no Developer ID)
#
# The package installs "Shoot Sorter.app" into /Applications. Installer also
# offers "Install for me only", which puts it in ~/Applications and needs no
# administrator password. No LaunchAgent is installed; "Start at Login" is a
# menu toggle in the app (off by default).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BUILD="${SHOOT_SORTER_BUILD_DIR:-$HERE/build}"
APP="$BUILD/Shoot Sorter.app"
PKG_ID="com.shootsorter.app.pkg"

if [[ "${1:-}" == "--build-app" ]]; then
  "$HERE/build_app.sh"
fi
[[ -d "$APP" ]] || { echo "Build the app first: packaging/build_app.sh" >&2; exit 1; }

VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")"
STAGE="$BUILD/pkgroot"
WORK="$BUILD/pkgwork"
OUT="$BUILD/ShootSorter-$VERSION.pkg"

echo "==> Staging"
rm -rf "$STAGE" "$WORK"
mkdir -p "$STAGE" "$WORK/resources"
ditto "$APP" "$STAGE/Shoot Sorter.app"
codesign --verify --deep --strict "$STAGE/Shoot Sorter.app"

# Never let Installer "relocate" the app onto another copy it finds on disk
# (for example a build folder); always install to the chosen location.
pkgbuild --analyze --root "$STAGE" "$WORK/component.plist" >/dev/null
for key in BundleIsRelocatable BundleIsVersionChecked; do
  /usr/libexec/PlistBuddy -c "Delete :0:$key" "$WORK/component.plist" >/dev/null 2>&1 || true
  /usr/libexec/PlistBuddy -c "Add :0:$key bool false" "$WORK/component.plist"
done

echo "==> pkgbuild"
pkgbuild --root "$STAGE" \
  --component-plist "$WORK/component.plist" \
  --install-location "/Applications" \
  --identifier "$PKG_ID" \
  --version "$VERSION" \
  --scripts "$HERE/pkg/scripts" \
  "$WORK/ShootSorter-component.pkg"

cp "$HERE/pkg/welcome.html" "$WORK/resources/welcome.html"
cp "$HERE/../LICENSE" "$WORK/resources/LICENSE.txt"
sed -e "s/__VERSION__/$VERSION/g" -e "s/__PKG_ID__/$PKG_ID/g" \
  "$HERE/pkg/distribution.xml" > "$WORK/distribution.xml"

echo "==> productbuild"
productbuild --distribution "$WORK/distribution.xml" \
  --package-path "$WORK" \
  --resources "$WORK/resources" \
  "$OUT"

pkgutil --check-signature "$OUT" >/dev/null 2>&1 || true
echo "Built: $OUT ($(du -h "$OUT" | cut -f1))"
