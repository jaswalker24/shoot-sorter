"""End-to-end smoke test for an installed Shoot Sorter (Windows).

Creates synthetic sample JPEGs in a test folder, signs in to the running
control panel, runs a dry run and then an apply job on that folder through
the panel API, and reports timings, GPU use (nvidia-smi) and the XMP
sidecars written. Touches nothing outside the test folder and the app's
own data folder.

  python.exe smoke_test.py <test folder> [--passes tagger,scene,...] [--skip-apply]
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

HOME = Path(os.environ.get("SHOOT_SORTER_APP_HOME") or Path(os.environ["APPDATA"]) / "Shoot Sorter")
PASSES = ["tagger", "scene", "index", "sharpness", "bursts", "rank", "ocr", "people", "cull"]


def make_samples(folder: Path) -> list[Path]:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    folder.mkdir(parents=True, exist_ok=True)

    def font(sz):
        for f in ("arialbd.ttf", "arial.ttf", "segoeui.ttf"):
            try:
                return ImageFont.truetype(f, sz)
            except OSError:
                continue
        return ImageFont.load_default()

    W, H = 1800, 1200
    out = []

    def save(im, name, i):
        exif = Image.Exif()
        exif[0x0110] = "Sample Camera"                       # Model
        ifd = exif.get_ifd(0x8769)
        ifd[0x9003] = f"2026:11:14 10:{i:02d}:00"
        p = folder / name
        im.convert("RGB").save(p, "JPEG", quality=92, exif=exif)
        out.append(p)

    # 1 street sign with text
    im = Image.new("RGB", (W, H), (120, 160, 210)); d = ImageDraw.Draw(im)
    d.rectangle([0, 700, W, H], fill=(70, 70, 75))
    for x in range(0, W, 300):
        d.rectangle([x + 20, 250, x + 260, 700], fill=(150 + x % 80, 140, 130))
    d.rectangle([500, 330, 1300, 560], fill=(200, 30, 30)); d.text((540, 360), "SHIBUYA 109", font=font(140), fill="white")
    d.text((560, 620), "OPEN 10:00 - 21:00", font=font(60), fill=(255, 240, 120))
    save(im, "S001_street_sign.jpg", 1)
    # 2 race car with a number
    im = Image.new("RGB", (W, H), (90, 140, 90)); d = ImageDraw.Draw(im)
    d.rectangle([0, 650, W, H], fill=(60, 60, 60))
    d.rounded_rectangle([350, 480, 1450, 820], 60, fill=(20, 60, 200))
    d.ellipse([450, 740, 650, 940], fill="black"); d.ellipse([1150, 740, 1350, 940], fill="black")
    d.ellipse([780, 520, 1020, 760], fill="white"); d.text((820, 540), "27", font=font(170), fill="black")
    save(im, "S002_race_car_27.jpg", 2)
    # 3 the same car, blurred (sharpness / bursts)
    save(im.filter(ImageFilter.GaussianBlur(9)), "S003_race_car_27_blur.jpg", 2)
    # 4 night street with lights
    im = Image.new("RGB", (W, H), (10, 10, 25)); d = ImageDraw.Draw(im)
    for i in range(40):
        x, y = (i * 137) % W, 300 + (i * 89) % 600
        d.ellipse([x, y, x + 40, y + 40], fill=(255, 200 - i * 3, 80))
    d.text((300, 150), "RAMEN", font=font(160), fill=(255, 80, 80))
    save(im, "S004_night_street.jpg", 4)
    # 5 water and sky
    im = Image.new("RGB", (W, H), (150, 190, 240)); d = ImageDraw.Draw(im)
    for y in range(600, H, 12):
        d.line([0, y, W, y + 6], fill=(30, 90 + (y % 50), 160), width=8)
    d.ellipse([1300, 120, 1500, 320], fill=(255, 240, 180))
    save(im, "S005_water_sky.jpg", 5)
    # 6 shrine-gate-like shape
    im = Image.new("RGB", (W, H), (200, 220, 235)); d = ImageDraw.Draw(im)
    d.rectangle([0, 900, W, H], fill=(120, 110, 90))
    d.rectangle([500, 300, 1300, 360], fill=(210, 50, 30)); d.rectangle([560, 420, 1240, 460], fill=(210, 50, 30))
    d.rectangle([600, 300, 680, 900], fill=(210, 50, 30)); d.rectangle([1120, 300, 1200, 900], fill=(210, 50, 30))
    save(im, "S006_gate.jpg", 6)
    # 7 stage poster with a schedule
    im = Image.new("RGB", (1200, 1700), (25, 20, 40)); d = ImageDraw.Draw(im)
    d.text((100, 120), "LIVE TONIGHT", font=font(120), fill=(255, 220, 0))
    for i, line in enumerate(["18:00 OPEN", "18:30 START", "19:10 BAND A", "20:00 BAND B"]):
        d.text((140, 420 + i * 200), line, font=font(110), fill="white")
    save(im, "S007_poster.jpg", 7)
    # 8 plain grey frame
    save(Image.new("RGB", (W, H), (128, 128, 128)), "S008_grey.jpg", 8)
    return out


class Panel:
    def __init__(self):
        port = json.loads((HOME / "app-settings.json").read_text(encoding="utf-8"))["port"]
        self.base = f"http://127.0.0.1:{port}"
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        tok = (HOME / "gui" / "auth.token").read_text(encoding="utf-8").strip()
        self.post("/api/login", {"token": tok})

    def post(self, path, data):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(),
                                     headers={"Content-Type": "application/json"})
        with self.op.open(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))

    def get(self, path):
        with self.op.open(self.base + path, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))


class GpuSampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.samples, self.apps, self.stop = [], {}, False

    def run(self):
        while not self.stop:
            try:
                r = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=10, creationflags=0x08000000)
                u, m = [int(x) for x in r.stdout.strip().split(",")[:2]]
                self.samples.append((time.time(), u, m))
                r = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=10, creationflags=0x08000000)
                for ln in r.stdout.strip().splitlines():
                    parts = [p.strip() for p in ln.split(",")]
                    if len(parts) >= 3:
                        name = Path(parts[1]).name
                        self.apps[name] = max(self.apps.get(name, 0), int(parts[2]) if parts[2].isdigit() else 0)
            except Exception:
                pass
            time.sleep(1.0)

    def summary(self):
        if not self.samples:
            return {}
        us = [s[1] for s in self.samples]; ms = [s[2] for s in self.samples]
        return {"samples": len(us), "util_max": max(us), "util_mean": round(sum(us) / len(us), 1),
                "mem_used_max_mib": max(ms), "mem_used_min_mib": min(ms), "compute_apps_max_mib": self.apps}


def run_job(panel: Panel, folder: Path, passes: list[str], dry: bool) -> dict:
    job = panel.post("/api/queue/add", {"folder": str(folder), "profile": "street", "passes": passes,
                                        "dry_run": dry, "apply_each": True, "afpoints": False})["job"]
    gpu = GpuSampler(); gpu.start()
    t0 = time.time(); last = None
    while True:
        j = panel.get(f"/api/job/{job['id']}")
        st = j.get("status")
        line = (j.get("progress") or {}).get("line") or j.get("current_pass")
        if line != last:
            print(f"  [{time.time() - t0:6.1f}s] {st} {j.get('current_pass')} {line or ''}"[:200], flush=True)
            last = line
        if st in ("done", "error", "cancelled", "awaiting_approval"):
            break
        time.sleep(2)
    gpu.stop = True; gpu.join(5)
    return {"id": job["id"], "status": st, "seconds": round(time.time() - t0, 1), "error": j.get("error"),
            "pass_results": j.get("pass_results"), "timings": j.get("timings") or j.get("pass_timings"),
            "added_keywords": j.get("added_keywords"), "gpu": gpu.summary(), "log_tail": (j.get("log") or [])[-25:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--passes", default=",".join(PASSES))
    ap.add_argument("--skip-apply", action="store_true")
    a = ap.parse_args()
    folder = Path(a.folder)
    if not any(folder.glob("*.jpg")):
        make_samples(folder)
    print("samples:", len(list(folder.glob("*.jpg"))), "in", folder)
    passes = [p for p in a.passes.split(",") if p]
    panel = Panel()
    report = {"folder": str(folder), "passes": passes}
    before = sorted(p.name for p in folder.glob("*.xmp"))
    print("== dry run"); report["dry_run"] = run_job(panel, folder, passes, True)
    report["xmp_after_dry_run"] = sorted(p.name for p in folder.glob("*.xmp"))
    report["xmp_before"] = before
    if not a.skip_apply:
        print("== apply"); report["apply"] = run_job(panel, folder, passes, False)
        x = sorted(folder.glob("*.xmp"))
        report["xmp_after_apply"] = [p.name for p in x]
        import re
        report["keywords"] = {p.name: re.findall(r"<rdf:li>([^<]+)</rdf:li>", p.read_text(encoding="utf-8"))[:40] for p in x}
    out = folder.parent / "smoke-report.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("report:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
