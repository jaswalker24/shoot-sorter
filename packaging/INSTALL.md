# Shoot Sorter.app

The packaged edition of Shoot Sorter: a menu-bar app with its own Python runtime, installed from a `.pkg`. It does the same work as the script install (`install.sh`) and writes keywords to XMP sidecars for Lightroom Classic. Keywords are added only. Stars, colour labels and develop settings are never changed.

## Requirements

- Apple-silicon Mac (M1 or newer). Intel Macs are not supported, and the installer refuses them.
- macOS 14 or newer.
- About 1.3 GB for the app and about 7 GB more for models, downloaded on first launch.

## Install

1. Double-click `ShootSorter-<version>.pkg`.
2. **If macOS says the package "can't be opened" or is from an unidentified developer:** the package and the app are not signed with an Apple Developer ID. Right-click (or Control-click) the `.pkg` in Finder and choose **Open**, then **Open** again. On recent macOS versions, if there is no Open button, go to **System Settings → Privacy & Security**, scroll down, and click **Open Anyway** next to the Shoot Sorter message.
3. Choose where to install:
   - **Install for all users of this computer** puts the app in `/Applications` and asks for an administrator password.
   - **Install for me only** puts it in `~/Applications` and needs no password.
4. Open **Shoot Sorter** from Applications. If macOS blocks the app itself the first time, do the same: right-click **Shoot Sorter.app** → **Open** → **Open**. You only need to do this once.

From Terminal (no prompts):

```bash
# just for you, no password
installer -pkg ShootSorter-1.0.0.pkg -target CurrentUserHomeDirectory
# for everyone, into /Applications
sudo installer -pkg ShootSorter-1.0.0.pkg -target /
```

## First launch

- A camera-aperture icon appears in the menu bar. The app has no Dock icon.
- The control panel starts on a free local port (8786 by default; it never uses 8765 or 8766) and opens in your browser, already signed in.
- The first launch downloads the models, with progress shown in the menu (and as a percentage next to the icon):
  Ollama, the `qwen2.5vl:3b` caption model, aesthetic weights, the face model, the SigLIP image model and CLIP ViT-L-14. If a download fails, use **Download Models…** to resume it. Steps that are already complete are skipped.
- If an Ollama server is already running on `127.0.0.1:11434`, Shoot Sorter uses it, and only pulls `qwen2.5vl:3b` into it if that model is missing.

## Menu

| Item | What it does |
|---|---|
| Open Panel | Opens the control panel (starts it if stopped) |
| Start / Stop Panel | Starts or stops the control panel and any job it is running |
| Download Models… | Re-runs the model download, skipping what is already there |
| Start at Login | Off by default. Writes `~/Library/LaunchAgents/com.shootsorter.app.login.plist`, which opens the app in the background at login |
| Show Data Folder / Show Logs | Opens the data folder or its `logs` folder in Finder |
| Quit Shoot Sorter | Stops the panel and quits |

## Where things live

| What | Where |
|---|---|
| App (read-only) | `/Applications/Shoot Sorter.app` or `~/Applications/Shoot Sorter.app` |
| Settings (`config.json`), panel login token, jobs, history | `~/Library/Application Support/Shoot Sorter` |
| Models, caches, index, outputs, logs | the same folder (`models/`, `cache/`, `index/`, `out/`, `logs/`) |
| Panel port | `app-settings.json` in the same folder |

The data folder contains links into the app for the code. They are refreshed on every launch, so updating or moving the app is safe. `config.json`, the token and everything you create are never overwritten.

This edition is separate from a script install in `~/shoot-sorter` (port 8766, LaunchAgent `com.shootsorter.gui`). Both can be installed at once. They keep separate settings and models, and share only the Ollama server on port 11434.

## Permissions

If your photos are on a NAS or an external disk, set the folders in the panel under **Settings → Locations**. If macOS refuses access, add the bundled Python to **System Settings → Privacy & Security → Full Disk Access**:

```
/Applications/Shoot Sorter.app/Contents/Resources/python/bin/python3.12
```

(Use `~/Applications/...` if you installed it just for yourself. In the file picker, press Command-Shift-G and paste the path.)

## Lightroom

Same as the script edition. See [README.md](../README.md#lightroom-workflow): keep **Automatically write changes into XMP** off for folders being tagged, then use **Metadata → Read Metadata from Files** after a job.

## Updating

Install a newer `.pkg` over the old one. The installer quits the running app first. Settings, models and history are kept.

## Uninstalling

```bash
"/Applications/Shoot Sorter.app/Contents/Resources/uninstall.sh"            # keeps settings and models
"/Applications/Shoot Sorter.app/Contents/Resources/uninstall.sh" --purge    # also deletes them
```

Add `--dry-run` to see what would be removed. Removing a copy in `/Applications` asks for an administrator password. The script removes the app, the login item and the installer receipt. Photos, Lightroom catalogues and XMP sidecars are never touched.

## Building from source

On an Apple-silicon Mac with Xcode or the Command Line Tools:

```bash
packaging/build_app.sh     # -> packaging/build/Shoot Sorter.app (ad-hoc signed)
packaging/build_pkg.sh     # -> packaging/build/ShootSorter-<version>.pkg
```

`build_app.sh` fetches a standalone CPython 3.12 (python-build-standalone, via uv), installs `requirements.txt` into it, copies the tracked source files into the bundle, bundles ExifTool, compiles the Swift launcher (`packaging/launcher/ShootSorterApp.swift`) and ad-hoc signs the result. Downloads are cached in `packaging/build/cache`. The version is in `packaging/VERSION`.

There is no Developer ID signing or notarisation, which is why the right-click **Open** step above is needed.
