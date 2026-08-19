param([switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$dataRoot = Join-Path $root 'runtime_data'
$pythonw = Join-Path $root 'runtime\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) {
    throw 'TreeCut v13 bundled Python is missing or damaged. Refusing to borrow another installation runtime.'
}
if ($ValidateOnly) {
    Write-Output $pythonw
    exit 0
}
$env:TREECUT_DATA_ROOT = $dataRoot
$env:TREECUT_MODEL_ROOT = Join-Path $root 'models'
$env:TEMP = Join-Path $dataRoot 'temp'
$env:TMP = $env:TEMP
$env:PYTHONPATH = Join-Path $root 'src'
$env:PYTHONPYCACHEPREFIX = Join-Path $dataRoot 'pycache'
$env:HF_HOME = Join-Path $dataRoot 'cache\huggingface'
$env:TORCH_HOME = Join-Path $dataRoot 'cache\torch'
$env:XDG_CACHE_HOME = Join-Path $dataRoot 'cache\xdg'
$env:MPLCONFIGDIR = Join-Path $dataRoot 'cache\matplotlib'
$env:ULTRALYTICS_CONFIG_DIR = Join-Path $dataRoot 'cache\ultralytics'
$env:YOLO_CONFIG_DIR = Join-Path $dataRoot 'cache\ultralytics'
$env:PIP_CACHE_DIR = Join-Path $dataRoot 'cache\pip'
Start-Process -FilePath $pythonw -ArgumentList '-m', 'treecut.desktop' -WorkingDirectory $root
