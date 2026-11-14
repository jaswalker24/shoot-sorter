# Install Shoot Sorter

Tags, ranks and culls photo shoots locally on Apple silicon and writes keywords to XMP sidecars for Lightroom Classic. Keywords are added only. Stars, colour labels and develop settings are never changed. Photos never leave the Mac.

## Quick start

Prefer an app? The packaged **Shoot Sorter.app** (`.pkg` installer, menu-bar launcher, no Terminal needed) is described in [packaging/INSTALL.md](packaging/INSTALL.md), including the right-click **Open** step for unsigned apps. The rest of this page covers the script install.

You need an **Apple-silicon Mac (M1 or newer)**, **macOS 14 or newer**, and about **15 GB** of free disk the first time. Lightroom Classic is used afterwards to read the sidecars; it does not need to be open while jobs run. Intel Macs are not supported (the installer will say why and stop).

1. Clone or unzip this repository.
2. Open **Terminal**, go into the folder, and run:

```bash
cd /path/to/shoot-sorter
./install.sh
```

The first run can take 10–20 minutes, mostly downloading Python packages and the local vision model.

The installer is safe to re-run. It will not overwrite an existing `~/shoot-sorter/config.json` or the control-panel login token, and it will not restart a control panel that is already running.

3. Follow the “Next steps” the script prints. Then open the **Shoot Sorter** Dock shortcut, or go to http://127.0.0.1:8766/.

## What the installer does

It puts everything in `~/shoot-sorter` (or `$SHOOT_SORTER_HOME` if you set that):

- A Python 3.12 virtualenv and the pinned packages
- A portable ExifTool and a standalone Ollama (listens on `127.0.0.1` only)
- The `qwen2.5vl:3b` caption / VLM weights, plus optional ranking and face-grouping weights
- `config.json` from the example, **only if you do not already have one**
- A new login token at `~/shoot-sorter/gui/auth.token` with mode `600`, **only if missing**. The token is never printed
- The `com.shootsorter.gui` Login item (LaunchAgent), loaded only if it is not already running
- The **Shoot Sorter** app in `~/Applications` and a Dock shortcut

It does **not** install a Lightroom plug-in, and it does not write to a catalogue. Homebrew is optional.

Useful flags:

```bash
./install.sh --dry-run                  # show the plan, change nothing
./install.sh --skip-models              # skip Ollama pulls and weight downloads
./install.sh --with-translation-model   # also pull qwen3:8b (~5 GB) for OCR translation
```

## Intel Macs

**Intel Macs are not supported.** The installer detects the architecture and stops. PyTorch 2.15 only publishes macOS ARM wheels, so the environment cannot be installed on Intel. Use an Apple-silicon Mac.

## Permissions

In **System Settings → Privacy & Security**, grant **Full Disk Access** to Terminal and `~/shoot-sorter/venv/bin/python` if your originals live on a NAS or an external disk. The control panel LaunchAgent is a Python process under your account. If a job cannot see a mounted volume, add that same Python path under Full Disk Access.

Shoot Sorter does not need Automation permission for Lightroom. Sidecars are written while Lightroom can be closed.

## Lightroom setup (once)

1. Optionally import `~/shoot-sorter/keywords/keyword-library.txt` with **Metadata → Import Keywords** so the keyword hierarchy already exists in the catalogue. The XMP writer does not require this; Lightroom will create keywords when it reads the sidecars.
2. Keep **Automatically write changes into XMP** **off** for folders this tool will tag, until you have used **Metadata → Read Metadata from Files** on them. If Lightroom writes its own XMP first, it can overwrite keywords that have not been read yet.
3. After a job finishes, select the folder in Lightroom and choose **Metadata → Read Metadata from Files**. You should see a “metadata changed on disk” badge beforehand. Check that keywords appeared and that stars, labels and develop settings did not change.

### Smart collections for the cull

Create three smart collections whose keyword rule matches:

- `Cull | Sharp + Burst Best`
- `Cull | Rank Best`
- `Cull | Shortlist`

Re-running a job is safe: the same keywords are not added twice.

## NAS mounts and paths

1. Mount the volume that holds your photo folders.
2. In the control panel open **Settings → Locations** and set Camera Imports, Camera Exports, optional Photos root, Other Exports and Schedules, or edit `~/shoot-sorter/config.json`.

Defaults in the example config use generic `/Volumes/your-nas/...` paths. Auto-queue looks under Camera Imports for `YYYY-MM-DD…` folders and queues a job once the folder has **stopped changing**. Lightroom does not need to be open.

## After a job: read the sidecars

The tool writes `<stem>.xmp` next to each image. Image bytes are never modified. For classic RAW files (CR3, ARW, NEF, RAF and so on) Lightroom reads that sidecar. For JPEG, TIFF, DNG and HEIC, Lightroom usually prefers metadata stored inside the file; this edition still writes a sidecar (it does not embed) and reports those files. Use **Read Metadata from Files** to pick the keywords up. If a sidecar already existed, a `.xmp.bak` copy is kept (`xmp_backup` in `config.json`, on by default).

Undo, from the History tab, removes only the keywords that job added.

## Updating

Pull or copy a newer tree, then re-run `./install.sh`. Existing config, token, models and a running panel are left alone. To load new panel code once the queue is idle:

```bash
~/shoot-sorter/venv/bin/python ~/shoot-sorter/gui/reload_when_idle.py
```

That command only restarts `com.shootsorter.gui`.

## Remote access

The control panel binds to `127.0.0.1:8766` by default, so it is only reachable on that Mac. To open it from another computer (for example a headless Mac), set `"gui_host": "0.0.0.0"` in `~/shoot-sorter/config.json`, or set the environment variable `SHOOT_SORTER_GUI_HOST=0.0.0.0` (you can add that key under `EnvironmentVariables` in `~/Library/LaunchAgents/com.shootsorter.gui.plist`). Then reload the panel:

```bash
~/shoot-sorter/venv/bin/python ~/shoot-sorter/gui/reload_when_idle.py
```

The in-panel folder browser (Settings → Locations → Browse) also needs this if you are using the panel from another computer. Keep the login token private; binding to `0.0.0.0` exposes the login page on the local network.

## Uninstalling

```bash
./install.sh --uninstall
```

This removes `com.shootsorter.gui`, `~/Applications/Shoot Sorter.app` and `~/shoot-sorter`. Photos, Lightroom catalogues, and XMP sidecars already written next to your images are left alone. You can delete the Dock tile if it is still there.

## Troubleshooting

**Keywords are in the sidecar but not in Lightroom**  
Select the folder and use **Metadata → Read Metadata from Files**. Confirm “Automatically write changes into XMP” was off until after that read.

**Stars or a colour label look wrong**  
This tool never writes `xmp:Rating`, `xmp:Label` or Camera Raw develop settings. If something drifted, compare the current sidecar to the `.xmp.bak` next to it, or use Lightroom’s own metadata conflict badge.

**JPEG / DNG keywords did not appear**  
Those formats normally store metadata inside the file. The sidecar was still written; use Read Metadata from Files. Embedding into the image is not implemented.

**Panel will not start / wrong port**  
This edition listens on http://127.0.0.1:8766/ by default. To change the address or port, set `gui_host` / `gui_port` in `config.json` or `SHOOT_SORTER_GUI_HOST` / `SHOOT_SORTER_GUI_PORT`, then reload the panel. See [Remote access](#remote-access).

**First run is slow**  
SigLIP weights download on first use into `~/shoot-sorter/models/hf`. Later runs reuse them.
