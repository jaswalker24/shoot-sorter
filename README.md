# Shoot Sorter

Tags, ranks and culls photo shoots locally on Apple silicon and writes keywords to XMP sidecars for Lightroom Classic. Keywords are added only. Stars, colour labels and develop settings are never changed. Photos never leave the Mac.

## Requirements

- An Apple-silicon Mac (M1 or newer). Intel Macs are not supported.
- macOS 14 or newer. Apple Vision OCR (text in frame, race numbers, posters) needs macOS.
- Lightroom Classic, if you want the keywords in your catalogue. The tool itself does not need Lightroom to be open.
- About 15 GB free the first time, for Python packages and local models.

Everything runs on the Mac. The local model server listens on localhost only. There is no cloud vision API.

## Install

```bash
cd /path/to/shoot-sorter
./install.sh
```

See **[INSTALL.md](INSTALL.md)** for permissions, updates and uninstall. The installer is safe to re-run. It will not overwrite an existing `~/shoot-sorter/config.json` or the control-panel login token.

The app lives in `~/shoot-sorter`. The control panel is at **http://127.0.0.1:8766/**. The LaunchAgent is `com.shootsorter.gui`. The Dock shortcut is **Shoot Sorter**.

## Lightroom workflow

1. Keep **Automatically write changes into XMP** **off** for folders this tool will tag, until you have read the new sidecars in.
2. Queue a job in the control panel (or run `~/shoot-sorter/tag` from Terminal). With apply on, confident keywords are merged into `<stem>.xmp` next to each image. Image bytes are not modified. An existing sidecar is backed up as `.xmp.bak` by default.
3. In Lightroom Classic, select the folder and choose **Metadata → Read Metadata from Files**. Check that keywords appeared and that stars, labels and develop settings did not change.

Keywords use Lightroom's hierarchy: `General/Rank/Best` is stored as `dc:subject` plus `lr:hierarchicalSubject` `General|Rank|Best`. Re-running a job does not create duplicates.

### Cull smart collections

Lightroom cannot receive smart collections from outside, so the cull pass writes keywords you can filter on:

| Keyword | Meaning |
|---|---|
| `Cull \| Sharp + Burst Best` | Sharp **and** Burst Best, and not Motion Blur or Soft Focus |
| `Cull \| Rank Best` | Rank Best, and not blur |
| `Cull \| Shortlist` | Either of the above |

Build three smart collections (or Library filters) whose keyword rule matches those values.

### JPEG, TIFF, DNG and HEIC

Those formats usually store metadata inside the file. Shoot Sorter still writes a sidecar and does not embed. Use **Read Metadata from Files**. Lightroom may still ignore a JPEG sidecar; that is a known gap.

## First test

1. Start the local model server if needed: `~/shoot-sorter/start-ollama.sh` (localhost only).
2. Optionally import `~/shoot-sorter/keywords/keyword-library.txt` into Lightroom with **Metadata → Import Keywords**. This is optional; Lightroom will create keywords when it reads the sidecars.
3. In the control panel, queue a small sample job (Sample = 3–5) on a test folder, with apply after each pass on.
4. In Lightroom, select that folder and use **Metadata → Read Metadata from Files**.

The first tagging run also downloads the SigLIP image model into `~/shoot-sorter/models/hf` (about 1–2 GB). Keep the Mac awake until it finishes.

## What it does

Pass by pass, on device:

- Focus, camera info, scene, text in frame, and folder or venue keywords
- Burst grouping and ranking (sharpness and aesthetics), trained on your own exports if you use the Training tab
- People: face clustering for you to review; nothing is applied automatically
- Schedule tagging by capture time, from a spreadsheet editor or a poster image dropped in an event folder
- Auto-queue: new Camera Imports folders are picked up once they have stopped changing. Lightroom does not need to be open.

MP4s are ignored. Files named `_schedule*` are skipped by every pass. Changes are additive only.

## Safety

- Existing keywords are never removed (except by History undo, which removes only keywords that job added).
- `xmp:Rating`, `xmp:Label` and Camera Raw develop settings are never written.
- Dry run is the default for Terminal tagging. Pass `--apply` only when you want sidecars updated.

## Known gaps

- Not a Lightroom plug-in. You have to use **Read Metadata from Files** after a job.
- JPEG, TIFF, DNG and HEIC are not embedded; a sidecar is written and may need an explicit read, or may be ignored for JPEG.
- Two files that share a stem share one `.xmp`.
- Apple Vision OCR and poster reading need macOS; they are not available on Linux.
- Intel Macs are not supported (PyTorch 2.15 has no macOS Intel wheels).

## Licence

Released under the MIT Licence. See [LICENSE](LICENSE).
