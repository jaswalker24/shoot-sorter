# Third-party licences

Shoot Sorter's own code is under the [MIT Licence](LICENSE). This repository does not vendor the packages or tools below. They are downloaded onto your Mac by `install.sh` or, for some model weights, on first use. Each stays under its own licence. You are responsible for complying with those terms.

Licences were taken from PyPI metadata for the pinned versions, or from the project's official licence file, in November 2026. They can change; check the linked source if you need a current answer. Transitive packages pulled in by these pins (for example `certifi` or `sympy`) are not listed here and have their own terms.

Model-weight licences are documented in the README under [Models and licences](README.md#models-and-licences), not in this file.

## Flagged licences

None of the direct Python pins is GPL- or AGPL-only. Two items involve copyleft that you should be aware of, and one has a weak-copyleft component. Nothing was swapped out.

- **LibRaw** (used by `rawpy`, which is required to read camera raws) is dual-licensed [LGPL 2.1 or CDDL 1.0](https://www.libraw.org/about). `rawpy` itself is MIT. LGPL is weak copyleft: linking against an unmodified shared library is commonly accepted in MIT applications, but you should review the terms if you redistribute binaries.
- **ExifTool** 13.61 (bundled by the installer for EXIF reads) is dual-licensed [Artistic Licence or GPL](https://exiftool.org/). The Artistic Licence can be chosen instead of the GPL. It is a hard requirement for the camera-info and preview-extraction steps.
- **`tqdm`** is licensed **MPL-2.0 AND MIT**. MPL is file-level weak copyleft and is generally compatible with distributing an MIT application, provided MPL files stay under MPL.

No AGPL or unknown licences were found among the pinned packages or bundled tools.

## Python packages (`requirements.txt`)

| Package | Version | Licence | Source |
|---|---|---|---|
| torch | 2.15.0 | Apache-2.0 (and other permissive notices) | [PyPI](https://pypi.org/project/torch/2.15.0/) |
| torchvision | 0.29.2 | BSD | [PyPI](https://pypi.org/project/torchvision/0.29.2/) |
| open_clip_torch | 4.2.1 | MIT | [PyPI](https://pypi.org/project/open-clip-torch/4.2.1/) |
| rawpy | 0.28.0 | MIT (wraps LibRaw: LGPL-2.1 or CDDL) | [PyPI](https://pypi.org/project/rawpy/0.28.0/), [LibRaw](https://www.libraw.org/about) |
| pyobjc-core | 13.0 | MIT | [PyPI](https://pypi.org/project/pyobjc-core/13.0/) |
| pyobjc-framework-Cocoa | 13.0 | MIT | [PyPI](https://pypi.org/project/pyobjc-framework-Cocoa/13.0/) |
| pyobjc-framework-Quartz | 13.0 | MIT | [PyPI](https://pypi.org/project/pyobjc-framework-Quartz/13.0/) |
| pyobjc-framework-Vision | 13.0 | MIT | [PyPI](https://pypi.org/project/pyobjc-framework-Vision/13.0/) |
| pyobjc-framework-CoreML | 13.0 | MIT | [PyPI](https://pypi.org/project/pyobjc-framework-CoreML/13.0/) |
| transformers | 5.22.2 | Apache 2.0 | [PyPI](https://pypi.org/project/transformers/5.22.2/) |
| huggingface_hub | 2.4.0 | Apache 2.0 | [PyPI](https://pypi.org/project/huggingface-hub/2.4.0/) |
| pillow | 13.0.0 | MIT-CMU | [PyPI](https://pypi.org/project/pillow/13.0.0/) |
| requests | 2.34.2 | Apache 2.0 | [PyPI](https://pypi.org/project/requests/2.34.2/) |
| numpy | 2.5.4 | BSD-3-Clause (and other permissive notices) | [PyPI](https://pypi.org/project/numpy/2.5.4/) |
| opencv-python-headless | 5.0.0.93 | Apache 2.0 | [PyPI](https://pypi.org/project/opencv-python-headless/5.0.0.93/) |
| scikit-image | 0.26.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/scikit-image/0.26.0/) |
| scikit-learn | 1.9.1 | BSD-3-Clause | [PyPI](https://pypi.org/project/scikit-learn/1.9.1/) |
| scipy | 1.18.1 | BSD-3-Clause | [PyPI](https://pypi.org/project/scipy/1.18.1/) |
| onnxruntime | 1.31.1 | MIT | [PyPI](https://pypi.org/project/onnxruntime/1.31.1/) |
| timm | 1.0.31 | Apache 2.0 | [PyPI](https://pypi.org/project/timm/1.0.31/) |
| ftfy | 6.3.1 | Apache 2.0 | [PyPI](https://pypi.org/project/ftfy/6.3.1/) |
| regex | 2026.11.9 | Apache-2.0 AND CNRI-Python | [PyPI](https://pypi.org/project/regex/2026.11.9/) |
| safetensors | 0.8.0 | Apache 2.0 | [PyPI](https://pypi.org/project/safetensors/0.8.0/) |
| tokenizers | 0.23.3 | Apache 2.0 | [PyPI](https://pypi.org/project/tokenizers/0.23.3/) |
| sentencepiece | 0.2.3 | Apache 2.0 | [PyPI](https://pypi.org/project/sentencepiece/0.2.3/) |
| tiktoken | 0.14.0 | MIT | [PyPI](https://pypi.org/project/tiktoken/0.14.0/) |
| tqdm | 4.70.1 | MPL-2.0 AND MIT | [PyPI](https://pypi.org/project/tqdm/4.70.1/) |
| PyYAML | 6.0.3 | MIT | [PyPI](https://pypi.org/project/PyYAML/6.0.3/) |
| filelock | 4.2.9 | MIT | [PyPI](https://pypi.org/project/filelock/4.2.9/) |
| fsspec | 2026.9.0 | BSD-3-Clause | [PyPI](https://pypi.org/project/fsspec/2026.9.0/) |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | [PyPI](https://pypi.org/project/packaging/26.3/) |
| typing_extensions | 4.16.0 | PSF-2.0 | [PyPI](https://pypi.org/project/typing-extensions/4.16.0/) |

Standard-library modules used by the app (`json`, `http.server`, `urllib`, `sqlite3`, and so on) are part of Python and covered by the Python Software Foundation licence.

## Tools downloaded by `install.sh`

| Tool | Version | Licence | Source |
|---|---|---|---|
| uv | 0.13.7 | MIT or Apache 2.0 | [astral-sh/uv](https://github.com/astral-sh/uv) |
| ExifTool (Image-ExifTool) | 13.61 | Artistic Licence or GPL | [exiftool.org](https://exiftool.org/) |
| Ollama | 0.40.15 | MIT | [ollama/ollama](https://github.com/ollama/ollama/blob/main/LICENSE) |
| Python | 3.12 | PSF Licence | [python.org](https://docs.python.org/3/license.html) |

Apple Vision and Core ML are part of macOS and are used through the PyObjC bindings above. They are subject to Apple's software licence, not a PyPI licence.
