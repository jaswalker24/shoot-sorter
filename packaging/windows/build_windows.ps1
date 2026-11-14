<#
Build the Shoot Sorter Windows installer (x64).

  powershell -ExecutionPolicy Bypass -File packaging\windows\build_windows.ps1 [-Clean] [-SkipPython] [-NoInstaller]

Output: packaging\build-win\ShootSorter-<version>-Setup.exe

The installer bundles:
  python\            standalone CPython 3.12 (python-build-standalone, via uv) + requirements-windows.txt,
                     except torch/torchvision, which first launch downloads (CUDA or CPU build)
  app\               Shoot Sorter code (tracked files only) and ExifTool for Windows
  runtime\           tray launcher, first-run model download, data-folder helper
Models are not bundled; they download on first launch into %APPDATA%\Shoot Sorter.

Needs: git, and Inno Setup 6 (ISCC.exe; user or machine install). uv, Python and
ExifTool are downloaded into packaging\build-win\cache and are not installed on
the build machine.
#>
param([switch]$Clean, [switch]$SkipPython, [switch]$NoInstaller)
# Native tools (uv, git, robocopy) write progress to stderr, which 'Stop' would turn into
# terminating errors on Windows PowerShell 5.1. Failures are checked through $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'

$Here  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo  = (Resolve-Path "$Here\..\..").Path
$Build = if ($env:SHOOT_SORTER_BUILD_DIR) { $env:SHOOT_SORTER_BUILD_DIR } else { Join-Path $Repo 'packaging\build-win' }
$Cache = Join-Path $Build 'cache'
$Stage = Join-Path $Build 'stage'
$PythonVer = '3.12'
$UvVer = '0.13.7'
$ExifVer = '13.63'
$RapidOcrVer = '1.4.4'
$AppVersion = if ($env:APP_VERSION) { $env:APP_VERSION } else { (Get-Content "$Repo\packaging\VERSION" -Raw).Trim() }

function Say($m) { Write-Host "`n==> $m" }
function Fetch($url, $out) {
  & curl.exe -fsSL --retry 3 -o $out $url
  if ($LASTEXITCODE) { throw "download failed: $url" }
}
New-Item -ItemType Directory -Force $Cache | Out-Null
$t0 = Get-Date
$BuildNum = (& git -C $Repo rev-list --count HEAD).Trim()
$GitSha = (& git -C $Repo rev-parse --short HEAD).Trim()

# ---------------------------------------------------------------- uv (build tool only)
$Uv = Join-Path $Cache 'uv\uv.exe'
if (-not (Test-Path $Uv)) {
  Say "Downloading uv $UvVer (build tool only, not shipped)"
  $z = Join-Path $Cache 'uv.zip'
  Fetch "https://github.com/astral-sh/uv/releases/download/$UvVer/uv-x86_64-pc-windows-msvc.zip" $z
  Expand-Archive -Force $z (Join-Path $Cache 'uv'); Remove-Item $z
}
$env:UV_CACHE_DIR = Join-Path $Cache 'uvcache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $Cache 'pythons'
$env:UV_PYTHON_PREFERENCE = 'only-managed'
$env:UV_LINK_MODE = 'copy'

# ---------------------------------------------------------------- Python runtime
$Runtime = Join-Path $Cache 'runtime'
if ($Clean -and (Test-Path $Runtime)) { Remove-Item -Recurse -Force $Runtime }
if (-not (Test-Path "$Runtime\python.exe")) {
  Say "Fetching standalone CPython $PythonVer (python-build-standalone via uv)"
  & $Uv python install $PythonVer; if ($LASTEXITCODE) { throw 'uv python install failed' }
  $src = (& $Uv python find $PythonVer).Trim()
  $srcRoot = Split-Path -Parent $src
  & robocopy $srcRoot $Runtime /E /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { throw 'robocopy runtime failed' }
  $SkipPython = $false
}
$Py = Join-Path $Runtime 'python.exe'
if (-not $SkipPython) {
  Say 'Installing requirements into the build runtime (CUDA torch is about 2 GB; it is used for the import check and left out of the installer)'
  Get-ChildItem "$Runtime\Lib" -Filter EXTERNALLY-MANAGED -ErrorAction SilentlyContinue | Remove-Item -Force
  & $Uv pip install --python $Py --break-system-packages --index-strategy unsafe-best-match -r "$Here\requirements-windows.txt"
  if ($LASTEXITCODE) { throw 'pip install failed' }
  & $Uv pip install --python $Py --break-system-packages --no-deps "rapidocr_onnxruntime==$RapidOcrVer"
  if ($LASTEXITCODE) { throw 'rapidocr install failed' }
}
& $Py -c "import sys, platform; assert platform.machine() in ('AMD64','x86_64'), platform.machine(); print('runtime', sys.version.split()[0])"

# ---------------------------------------------------------------- ExifTool for Windows
$ExifDir = Join-Path $Cache "exiftool-$ExifVer"
if (-not (Test-Path "$ExifDir\exiftool.exe")) {
  Say "Downloading ExifTool $ExifVer (Windows 64-bit)"
  $z = Join-Path $Cache 'exiftool.zip'
  try { Fetch "https://exiftool.org/exiftool-${ExifVer}_64.zip" $z }
  catch { Fetch "https://sourceforge.net/projects/exiftool/files/exiftool-${ExifVer}_64.zip/download" $z }
  $tmp = Join-Path $Cache 'exiftool-x'
  if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
  Expand-Archive -Force $z $tmp; Remove-Item $z
  $exe = Get-ChildItem $tmp -Recurse -Filter 'exiftool*.exe' | Select-Object -First 1
  if (-not $exe) { throw 'exiftool exe not found in zip' }
  New-Item -ItemType Directory -Force $ExifDir | Out-Null
  Copy-Item $exe.FullName "$ExifDir\exiftool.exe"
  $files = Get-ChildItem $exe.Directory.FullName -Directory -Filter 'exiftool_files' | Select-Object -First 1
  if ($files) { & robocopy $files.FullName "$ExifDir\exiftool_files" /E /NFL /NDL /NJH /NJS /NP | Out-Null }
  Remove-Item -Recurse -Force $tmp
}

# ---------------------------------------------------------------- stage
Say "Staging $Stage"
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
New-Item -ItemType Directory -Force "$Stage\app", "$Stage\runtime" | Out-Null
& robocopy $Runtime "$Stage\python" /E /NFL /NDL /NJH /NJS /NP /XD __pycache__ "$Runtime\Lib\test" "$Runtime\Lib\idlelib" "$Runtime\Lib\turtledemo" /XF EXTERNALLY-MANAGED | Out-Null
if ($LASTEXITCODE -ge 8) { throw 'robocopy python failed' }
# PyTorch (about 2 GB compressed) is downloaded on first launch instead of shipped:
# strip torch/torchvision from the staged runtime and record the exact wheels to fetch.
& $Py "$Here\torch_split.py" "$Runtime\Lib\site-packages" "$Stage\python\Lib\site-packages" "$Stage\torch-manifest.json"
if ($LASTEXITCODE) { throw 'torch_split failed' }

# App code: tracked files only, so local config, schedules and data never ship.
$skip = '^(packaging/|install\.sh$|INSTALL-LR\.md$|test_scripts\.sh$|tests/|tests_.*\.py$|gui/macos/|\.git)'
$files = & git -C $Repo ls-files
foreach ($f in $files) {
  if ($f -match $skip) { continue }
  $dst = Join-Path "$Stage\app" ($f -replace '/', '\')
  New-Item -ItemType Directory -Force (Split-Path -Parent $dst) | Out-Null
  Copy-Item (Join-Path $Repo $f) $dst
}
& robocopy $ExifDir "$Stage\app\tools\exiftool" /E /NFL /NDL /NJH /NJS /NP | Out-Null
Copy-Item "$Repo\packaging\runtime\first_run.py", "$Repo\packaging\runtime\prepare_home.py", "$Here\tray.py" "$Stage\runtime\"
Copy-Item "$Repo\LICENSE", "$Repo\THIRD_PARTY_LICENSES.md" "$Stage\"
Copy-Item "$Here\INSTALL-WINDOWS.md" "$Stage\INSTALL.md"
$bi = @{ version = $AppVersion; build = $BuildNum; git = $GitSha; platform = 'windows-x64' } | ConvertTo-Json
[IO.File]::WriteAllText("$Stage\build-info.json", $bi, (New-Object System.Text.UTF8Encoding($false)))
& $Py -c "from PIL import Image; im = Image.open(r'$Repo\gui\static\logo.png').convert('RGBA'); im.save(r'$Stage\ShootSorter.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"

Say 'Pre-compiling Python bytecode (the install folder is treated as read-only)'
& "$Stage\python\python.exe" -m compileall -q -j 0 "$Stage\python\Lib" 2>$null | Out-Null
& "$Stage\python\python.exe" -m compileall -q -j 0 "$Stage\app" "$Stage\runtime" | Out-Null

Say 'Checking the bundled runtime imports'
$chk = @'
import importlib, sys
mods = ["torch", "torchvision", "open_clip", "rawpy", "PIL", "numpy", "cv2", "skimage", "sklearn", "scipy",
        "onnxruntime", "timm", "transformers", "huggingface_hub", "requests", "yaml", "psutil", "pystray",
        "rapidocr_onnxruntime", "pillow_heif"]
bad = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as e:
        bad.append(f"{m}: {e}")
if bad:
    print("Import failures:\n  " + "\n  ".join(bad)); sys.exit(1)
import torch
print("all", len(mods), "imports OK; torch", torch.__version__, "CUDA build", torch.version.cuda,
      "cuda available:", torch.cuda.is_available())
'@
$chk | & "$Stage\python\python.exe" -
if ($LASTEXITCODE) { throw 'import check failed' }
& "$Stage\app\tools\exiftool\exiftool.exe" -ver
$size = (Get-ChildItem $Stage -Recurse -File | Measure-Object Length -Sum).Sum
Say ("Staged {0:N2} GB" -f ($size / 1GB))
if ($NoInstaller) { return }

# ---------------------------------------------------------------- installer
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Inno Setup 6 (ISCC.exe) not found' }
Say "Compiling the installer with $iscc"
& $iscc /Q "/DSourceDir=$Stage" "/DAppVersion=$AppVersion" "/DOutputDir=$Build" "/DBuildInfo=$BuildNum ($GitSha)" "$Here\ShootSorter.iss"
if ($LASTEXITCODE) { throw 'ISCC failed' }
Get-ChildItem $Build -Filter "ShootSorter-$AppVersion-Setup*" | ForEach-Object { "{0}  {1:N0} MB" -f $_.FullName, ($_.Length / 1MB) }
"Build time: {0:N1} min" -f ((Get-Date) - $t0).TotalMinutes
