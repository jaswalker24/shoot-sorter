"""Build helper: move torch and torchvision out of the Windows installer.

The CUDA build of PyTorch is about 2 GB compressed, so the installer ships
without it and runtime/first_run.py downloads it on first launch (the CUDA
build when an NVIDIA driver is present, otherwise the CPU build).

  python torch_split.py <built site-packages> <staged site-packages> <manifest.json>

* removes every top-level entry that belongs to the torch / torchvision
  distributions (from their RECORD files) from the staged site-packages;
* writes shootsorter_torch.pth, which adds python\\torch-libs to sys.path
  (first_run.py installs the wheels there);
* writes the manifest: exact wheel URLs and SHA-256 for both variants, read
  from the PyTorch package index.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import urllib.request
from pathlib import Path

DISTS = ("torch", "torchvision")
INDEX = "https://download.pytorch.org/whl/{variant}/{name}/"
VARIANTS = ("cu132", "cpu")


def dist_info(site: Path, name: str) -> Path:
    hits = [p for p in site.glob(f"{name}-*.dist-info") if p.name.split("-")[0].lower() == name]
    if len(hits) != 1:
        raise SystemExit(f"expected one {name} dist-info in {site}, found {hits}")
    return hits[0]


def top_levels(di: Path) -> set[str]:
    tops = set()
    for line in (di / "RECORD").read_text(encoding="utf-8").splitlines():
        path = line.split(",")[0].replace("\\", "/")   # uv on Windows writes backslashes
        if path:
            tops.add(path.split("/")[0])
    return tops


def find_wheel(name: str, version: str, variant: str) -> dict:
    url = INDEX.format(variant=variant, name=name)
    with urllib.request.urlopen(url, timeout=60) as r:
        html = r.read().decode("utf-8", "replace")
    pat = re.compile(r'href="([^"]*/' + re.escape(name) + "-" + re.escape(version) + r'%2B' + variant +
                     r'-(?:cp312-cp312|py3-none)-win_amd64\.whl)#sha256=([0-9a-f]{64})"')
    m = pat.search(html)
    if not m:
        raise SystemExit(f"{name} {version}+{variant} for cp312 win_amd64 not found on {url}")
    href = m.group(1)
    if href.startswith("/"):
        href = "https://download.pytorch.org" + href
    fname = href.rsplit("/", 1)[1].replace("%2B", "+")
    return {"name": name, "file": fname, "url": href, "sha256": m.group(2)}


def main() -> int:
    built, staged, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    versions, removed = {}, []
    for name in DISTS:
        di = dist_info(built, name)
        versions[name] = di.name[len(name) + 1:-len(".dist-info")].split("+")[0]
        for top in sorted(top_levels(di)):
            if top in ("..", "") or top.endswith(".data"):
                continue
            p = staged / top
            if p.is_dir():
                shutil.rmtree(p); removed.append(top)
            elif p.exists():
                p.unlink(); removed.append(top)
    (staged / "shootsorter_torch.pth").write_text("../../torch-libs\n", encoding="utf-8")
    manifest = {"versions": versions, "variants": {}}
    for v in VARIANTS:
        manifest["variants"][v] = [find_wheel(n, versions[n], v) for n in DISTS]
    out.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("removed from installer:", ", ".join(removed))
    print("manifest:", json.dumps(manifest["versions"]), "->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
