# Shoot Sorter

Tags, ranks and culls photo shoots locally on Apple silicon and writes keywords to XMP sidecars for Lightroom Classic. Keywords are added only. Stars, colour labels and develop settings are never changed. Photos never leave the Mac.

## Requirements

- An Apple-silicon Mac (M1 or newer). Intel Macs are not supported.
- macOS 14 or newer. Apple Vision OCR (text in frame, race numbers, posters) needs macOS.
- Lightroom Classic, if you want the keywords in your catalogue. The tool itself does not need Lightroom to be open.
- About 15 GB free the first time, for Python packages and local models.

Tagging runs on the Mac. The local model server listens on localhost only. There is no cloud vision API. See [Disclaimer](#disclaimer) for the full network picture.

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

Released under the MIT Licence. See [LICENSE](LICENSE). The MIT licence covers Shoot Sorter's own code only. Models and engines stay under their own terms; see [Models and licences](#models-and-licences). Python packages and bundled tools are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

## Disclaimer

Shoot Sorter is not affiliated with, endorsed by or sponsored by Adobe (including Lightroom and Lightroom Classic), Capture One A/S, Apple, Alibaba or the Qwen team, InsightFace, or OpenAI. All trademarks belong to their owners and are used only to describe compatibility.

The software is provided "as is", without warranty of any kind, as set out in the [MIT Licence](LICENSE). Back up your Lightroom catalogue and your photos before you use it. The authors are not liable for lost, changed or unreadable metadata, sidecars, catalogues or image files.

Third-party models are downloaded separately and remain under their own licences. You must comply with those terms, including any non-commercial restrictions. See [Models and licences](#models-and-licences).

The People (faces) feature processes biometric data. If you run it on photographs of other people, especially for client or commercial work, you are responsible for having a lawful basis and any required consent under laws that apply to you, such as UK or EU GDPR and Illinois BIPA. The feature is optional and is off by default: it is not in the default pass list, and none of the built-in Quick, Standard or Full bundles include it. Leave **People (faces)** unticked when you queue a job, and do not add it to an auto-queue profile. To run it, tick that pass or run `~/shoot-sorter/tag faces`.

Tagging and model inference run on the Mac. The app does not upload your photos. Outbound network use is: the installer and first tagging run downloading tools and model weights from GitHub, ExifTool's site and Hugging Face; optional job-status notifications, only if you turn on Telegram or email in Settings (off by default, text only, no photos); and calls to the local Ollama server on 127.0.0.1. Hugging Face client libraries used to fetch SigLIP and CLIP weights have usage telemetry disabled by default (`HF_HUB_DISABLE_TELEMETRY=1`). Model downloads still run as usual. The control panel is login-protected and listens on 127.0.0.1:8766 by default. To reach it from another computer (for example a headless Mac), set `gui_host` to `0.0.0.0` in `config.json` or set `SHOOT_SORTER_GUI_HOST=0.0.0.0`, then reload the panel. The in-panel folder browser needs that bind address when you open the panel from another computer. The panel does not send images.

## Models and licences

Shoot Sorter does not ship model weights in this repository. `install.sh` (and, for SigLIP and CLIP, the first tagging run) downloads them onto the Mac, into `~/shoot-sorter/models` or the local Ollama models folder. Those files remain under their makers' licences, not MIT. You are responsible for complying with those terms, including any restriction on commercial use.

Licences below were checked against the official model card, licence file or project README at the time of writing. They can change; follow the linked source if you need a current answer.

| Model or engine | Used for | Licence | Commercial use |
|---|---|---|---|
| [Qwen2.5-VL-3B](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct) (`qwen2.5vl:3b`) | Captions, VLM confirmation of scene flags and race numbers, optional export captions | [Qwen Research Licence](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/blob/main/LICENSE) | No |
| [Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) (`qwen3:8b`, optional) | Japanese-to-English OCR translation, journal and ask | [Apache 2.0](https://huggingface.co/Qwen/Qwen3-8B/blob/main/LICENSE) | Yes |
| [SigLIP ViT-B-16-256](https://huggingface.co/timm/ViT-B-16-SigLIP-256) (`ViT-B-16-SigLIP-256`, `webli`) | Scene keywords, image index, search and burst grouping | [Apache 2.0](https://huggingface.co/timm/ViT-B-16-SigLIP-256) | Yes |
| [OpenAI CLIP ViT-L/14](https://huggingface.co/openai/clip-vit-large-patch14) (`ViT-L-14`, `openai`) | Image embeddings for the aesthetic scorer | [MIT](https://github.com/openai/CLIP/blob/main/LICENSE) (official code repo; the Hugging Face card does not declare a licence) | Check |
| [LAION improved aesthetic predictor](https://github.com/christophschuhmann/improved-aesthetic-predictor) (`sac+logos+ava1-l14-linearMSE.pth`) | Aesthetic scores used by ranking and the cull | [Apache 2.0](https://github.com/christophschuhmann/improved-aesthetic-predictor/blob/main/LICENSE) | Yes |
| [InsightFace buffalo_s](https://github.com/deepinsight/insightface) (`w600k_mbf.onnx`) | Face embeddings for the people pass (clustering and library match) | [InsightFace model terms](https://github.com/deepinsight/insightface#license) (non-commercial research only) | No |
| [Apple Vision](https://developer.apple.com/documentation/vision) | Text in frame, poster reading, face detection and landmarks, subject region for sharpness | Apple software licence (part of macOS) | Check |
| [Ollama](https://github.com/ollama/ollama) | Local server that runs the Qwen models (localhost only) | [MIT](https://github.com/ollama/ollama/blob/main/LICENSE) | Yes |

Ollama's MIT licence covers the server only, not the models it pulls. The aesthetic predictor's own weights are Apache 2.0, but they run on top of CLIP ViT-L/14, whose commercial terms you should check separately. Face *detection* uses Apple Vision; only the InsightFace embedding file is restricted.

### Restricted models

**`qwen2.5vl:3b`** is the default caption model. Its official card uses the [Qwen Research Licence](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/blob/main/LICENSE), which allows use for research or evaluation only. Commercial use needs a separate licence from Alibaba Cloud. The 7B and larger Qwen2.5-VL models are [Apache 2.0](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct). For commercial use you can pull `qwen2.5vl:7b` (~6 GB) and set `vlm_model` in `config.json` to that tag. It needs more memory than the 3B model.

**`w600k_mbf.onnx`** comes from InsightFace's `buffalo_s` package. InsightFace's README and site state that the code is MIT, but the pre-trained models (including buffalo_s) are for non-commercial research only, and a commercial licence is required otherwise. They ask commercial users to contact [recognition-oss-pack@insightface.ai](mailto:recognition-oss-pack@insightface.ai). Until you have that licence, skip the people pass for commercial work, or replace the embedding model with one whose terms allow it.

The personal ranking model trained from your own exports is your data; it is not a third-party weight.
