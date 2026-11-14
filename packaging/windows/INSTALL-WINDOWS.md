# Shoot Sorter for Windows

The packaged Windows edition of Shoot Sorter: a tray app with its own Python runtime, installed from `ShootSorter-<version>-Setup.exe`. It does the same work as the Mac app and writes keywords to XMP sidecars for Lightroom Classic. Keywords are added only. Stars, colour labels and develop settings are never changed.

## Requirements

- Windows 10 (1809) or Windows 11, 64-bit (x64).
- An NVIDIA graphics card with a recent driver (580 or newer, CUDA 13) is strongly recommended. Without one, everything runs on the processor, which is much slower.
- About 6 GB for the app and about 12 GB more for models, downloaded on first launch (Ollama for Windows is about 1.6 GB of that).

## Install

1. Double-click `ShootSorter-<version>-Setup.exe`.
2. **If Windows shows "Windows protected your PC" (SmartScreen):** the installer is not code-signed. Click **More info**, then **Run anyway**. You only need to do this once per downloaded file.
3. The installer is per-user. It needs no administrator rights and installs to `%LOCALAPPDATA%\Programs\Shoot Sorter`. You can add a desktop shortcut and start Shoot Sorter when you sign in.

Silent install (no prompts): `ShootSorter-<version>-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES`

## First launch

- A Shoot Sorter icon appears in the notification area (system tray). If you don't see it, click the **^** arrow next to the clock.
- The control panel starts on a free local port (8786 by default; it never uses 8765 or 8766) and opens in your browser, already signed in.
- The first launch downloads the models, with progress shown in the tray menu and in the icon's tooltip: Ollama for Windows (unless an Ollama server is already running on `127.0.0.1:11434`), the `qwen2.5vl:3b` caption model, aesthetic weights, the face models, the SigLIP image model and CLIP ViT-L-14. If a download fails, use **Download Models…** to resume it. Steps that are already complete are skipped.

## Tray menu

| Item | What it does |
|---|---|
| Open Panel (double-click the icon) | Opens the control panel (starts it if stopped) |
| Start / Stop Panel | Starts or stops the control panel and any job it is running |
| Download Models… | Re-runs the model download, skipping what is already there |
| Start at Login | Off by default. Adds `Shoot Sorter.lnk` to your Startup folder, which starts the app in the background when you sign in |
| Show Data Folder / Show Logs | Opens the data folder or its `logs` folder in Explorer |
| Quit Shoot Sorter | Stops the panel, any job, and the app's own Ollama server, then quits |

## Where things live

| What | Where |
|---|---|
| App (treated as read-only) | `%LOCALAPPDATA%\Programs\Shoot Sorter` |
| Settings (`config.json`), panel login token, jobs, history | `%APPDATA%\Shoot Sorter` |
| Models, caches, index, outputs, logs | the same folder (`models\`, `cache\`, `index\`, `out\`, `logs\`) |
| Panel port | `app-settings.json` in the same folder |

The data folder also holds a copy of the app's code, refreshed whenever the installed version changes. `config.json`, the token and everything you create are never overwritten.

## Differences from the Mac app

| macOS | Windows |
|---|---|
| Apple Vision text recognition (car numbers, Read Text in Frame, schedule posters) | RapidOCR (PP-OCR models on ONNX Runtime). Good on numbers and Latin text, reads kanji; kana are weaker than Apple Vision |
| Apple Vision face detection | SCRFD detector from the same InsightFace pack as the face embedding model |
| Apple Vision saliency (subject box for sharpness) | Spectral-residual saliency (OpenCV) |
| Apple GPU (MPS) | NVIDIA GPU (CUDA), else CPU. Force one with `"device": "cpu"` or `"cuda"` in `config.json` |
| Finder folder picker | Windows folder picker |
| `sips` for HEIC posters | `pillow-heif` |
| Thermal and memory-pressure stats in the panel | Not shown |

Folder browsing in the panel covers your drive letters and home folder. Set the photo folders (for example a mapped NAS drive such as `Z:\Camera Imports`) under **Settings → Locations**.

## Lightroom

Same as the Mac edition. See [README.md](../../README.md#lightroom-workflow): keep **Automatically write changes into XMP** off for folders being tagged, then use **Metadata → Read Metadata from Files** after a job.

## Updating

Run a newer installer over the old one. It quits the running app first. Settings, models and history are kept.

## Uninstalling

**Settings → Apps → Installed apps → Shoot Sorter → Uninstall**. The uninstaller asks whether to delete your settings, models and history as well (default: keep them). Silent: `"%LOCALAPPDATA%\Programs\Shoot Sorter\unins000.exe" /VERYSILENT` (keeps data) or add `/PURGE=1` to delete the data folder too. Photos, Lightroom catalogues and XMP sidecars are never touched.

## Building from source

On a Windows x64 PC with Git and [Inno Setup 6.5+](https://jrsoftware.org/isinfo.php):

```powershell
powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1
# -> packaging\build-win\ShootSorter-<version>-Setup.exe
```

`build_windows.ps1` fetches uv and a standalone CPython 3.12 (python-build-standalone) into `packaging\build-win\cache`, installs `packaging\windows\requirements-windows.txt` into it (CUDA builds of torch and torchvision), adds ExifTool for Windows, stages the tracked source files, generates the icon and compiles `packaging\windows\ShootSorter.iss`. Nothing is installed on the build machine.

The installer is not code-signed, which is why the SmartScreen step above is needed.
