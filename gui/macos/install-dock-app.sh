#!/bin/bash
# Installs ~/Applications/Shoot Sorter.app and adds it to the Dock.
# Does not remove other Dock icons.
set -euo pipefail
APP="$HOME/Applications/Shoot Sorter.app"
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/Applications"
rm -rf "$APP"
if [ -d "$ROOT/Shoot Sorter.app" ]; then
  cp -R "$ROOT/Shoot Sorter.app" "$APP"
else
  mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
  cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Shoot Sorter</string>
  <key>CFBundleDisplayName</key><string>Shoot Sorter</string>
  <key>CFBundleIdentifier</key><string>com.shootsorter.panel</string>
  <key>CFBundleExecutable</key><string>ShootSorter</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
</dict></plist>
PLIST
  cat > "$APP/Contents/MacOS/ShootSorter" <<'SH'
#!/bin/bash
TOKEN_FILE="${SHOOT_SORTER_HOME:-$HOME/shoot-sorter}/gui/auth.token"
BASE="http://127.0.0.1:8766/"
if [ -f "$TOKEN_FILE" ]; then
  TOKEN=$(tr -d '\r\n' < "$TOKEN_FILE")
  open "${BASE}?token=${TOKEN}"
else
  open "$BASE"
fi
SH
  chmod +x "$APP/Contents/MacOS/ShootSorter"
fi
chmod +x "$APP/Contents/MacOS/ShootSorter" 2>/dev/null || true
if [ "${SHOOT_SORTER_SKIP_DOCK_RESTART:-0}" = "1" ]; then
  echo "App installed at $APP (Dock left unchanged)"
  exit 0
fi
BACKUP_DIR="${SHOOT_SORTER_HOME:-$HOME/shoot-sorter}/gui"
mkdir -p "$BACKUP_DIR"
defaults export com.apple.dock "$BACKUP_DIR/dock-backup-$(date +%Y%m%d-%H%M%S).plist" 2>/dev/null || true
python3 - <<'PY'
import plistlib, subprocess
from pathlib import Path
export_path = Path("/tmp/dock-current-ss.plist")
subprocess.check_call(["defaults", "export", "com.apple.dock", str(export_path)])
dock = plistlib.load(open(export_path, "rb"))
app_url = f"file://{Path.home()}/Applications/Shoot%20Sorter.app/"
apps = []
for tile in dock.get("persistent-apps", []):
    url = tile.get("tile-data", {}).get("file-data", {}).get("_CFURLString", "")
    label = tile.get("tile-data", {}).get("file-label", "")
    bid = tile.get("tile-data", {}).get("bundle-identifier", "")
    if url == app_url or label == "Shoot Sorter" or bid == "com.shootsorter.panel":
        continue
    apps.append(tile)
apps.append({"tile-type":"file-tile","tile-data":{"file-data":{"_CFURLString":app_url,"_CFURLStringType":15},"file-label":"Shoot Sorter","bundle-identifier":"com.shootsorter.panel"}})
dock["persistent-apps"] = apps
plistlib.dump(dock, open("/tmp/dock-new-ss.plist","wb"), fmt=plistlib.FMT_BINARY)
subprocess.check_call(["defaults", "import", "com.apple.dock", "/tmp/dock-new-ss.plist"])
subprocess.call(["killall", "Dock"])
print("Dock updated with Shoot Sorter")
PY
echo "App installed at $APP"
