#!/bin/bash
# Uninstall the packaged Shoot Sorter app.
#
#   uninstall.sh            remove the app, its login item and the installer receipt;
#                           keep settings, models and outputs
#   uninstall.sh --purge    also delete ~/Library/Application Support/Shoot Sorter
#                           (settings, downloaded models, caches, job history)
#   uninstall.sh --dry-run  show what would be removed
#
# Photos, Lightroom catalogues and XMP sidecars are never touched.
# Removing a copy in /Applications needs an administrator password (sudo).
set -uo pipefail

PURGE=0
DRY=0
for a in "$@"; do
  case "$a" in
    --purge) PURGE=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "Unknown option: $a" >&2; exit 2 ;;
  esac
done

USER_HOME="${SHOOT_SORTER_USER_HOME:-$HOME}"
DATA="$USER_HOME/Library/Application Support/Shoot Sorter"
AGENT_LABEL="com.shootsorter.app.login"
AGENT="$USER_HOME/Library/LaunchAgents/$AGENT_LABEL.plist"
PKG_ID="com.shootsorter.app.pkg"
APPS=("/Applications/Shoot Sorter.app" "$USER_HOME/Applications/Shoot Sorter.app")

run() {
  if [[ "$DRY" -eq 1 ]]; then echo "[dry-run] $*"; else "$@"; fi
}

is_packaged_app() {
  # Only remove a bundle that is this packaged app (not the older Dock shortcut).
  [[ -d "$1" ]] && [[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$1/Contents/Info.plist" 2>/dev/null)" == "com.shootsorter.app" ]]
}

echo "Uninstalling Shoot Sorter (app only). Photos and XMP sidecars are not touched."

# 1. Quit the app; it stops its own control panel and any running job.
if pgrep -f "Shoot Sorter.app/Contents/MacOS/ShootSorter" >/dev/null 2>&1; then
  run osascript -e 'tell application id "com.shootsorter.app" to quit' >/dev/null 2>&1
  [[ "$DRY" -eq 1 ]] || sleep 3
  run pkill -f "Shoot Sorter.app/Contents/MacOS/ShootSorter" 2>/dev/null
  run pkill -f "Application Support/Shoot Sorter/gui/server.py" 2>/dev/null
fi

# 2. Login item.
if [[ -f "$AGENT" ]]; then
  run launchctl bootout "gui/$(id -u)/$AGENT_LABEL" 2>/dev/null
  run rm -f "$AGENT"
  echo "Removed login item $AGENT"
fi

# 3. App bundles and receipts.
for app in "${APPS[@]}"; do
  if is_packaged_app "$app"; then
    if [[ -w "$(dirname "$app")" ]]; then
      run rm -rf "$app"
    else
      echo "Removing $app needs an administrator password."
      run sudo rm -rf "$app"
    fi
    echo "Removed $app"
  fi
done
if pkgutil --pkg-info "$PKG_ID" >/dev/null 2>&1; then
  run sudo pkgutil --forget "$PKG_ID" >/dev/null
fi
if pkgutil --volume "$USER_HOME" --pkg-info "$PKG_ID" >/dev/null 2>&1; then
  run pkgutil --volume "$USER_HOME" --forget "$PKG_ID" >/dev/null
fi

# 4. Data (only with --purge).
if [[ "$PURGE" -eq 1 ]]; then
  if [[ -d "$DATA" ]]; then
    run rm -rf "$DATA"
    echo "Removed $DATA"
  fi
else
  [[ -d "$DATA" ]] && echo "Kept settings and models in: $DATA (re-run with --purge to delete)"
fi
echo "Done."
