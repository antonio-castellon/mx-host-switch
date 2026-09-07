# Build a one-file, no-install MXHostSwitch.exe
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = (Get-Command python).Source
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    & $python -m venv .venv
}

$py = ".\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt
& $py -c "from mxhost.icon import write_assets; print(write_assets())"

$icon = Join-Path $PSScriptRoot "assets\icon.ico"
& $py -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name MXHostSwitch `
    --icon $icon `
    --hidden-import hid `
    --hidden-import pystray._win32 `
    --hidden-import PIL._imaging `
    --collect-all hid `
    --collect-submodules pystray `
    mx_host_switch.py

$built = Join-Path $PSScriptRoot "dist\MXHostSwitch.exe"
if (-not (Test-Path $built)) {
    throw "Build failed: $built was not created"
}
Write-Output "OK $built"
