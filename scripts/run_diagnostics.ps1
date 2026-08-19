$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $root 'runtime\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'TreeCut portable Python runtime is missing.'
}
$dataRoot = Join-Path $root 'runtime_data'
$env:TREECUT_DATA_ROOT = $dataRoot
$env:TREECUT_MODEL_ROOT = Join-Path $root 'models'
$env:TEMP = Join-Path $dataRoot 'temp'
$env:TMP = $env:TEMP
$env:PYTHONPATH = Join-Path $root 'src'
$env:PYTHONPYCACHEPREFIX = Join-Path $dataRoot 'pycache'
$env:HF_HOME = Join-Path $dataRoot 'cache\huggingface'
$env:TORCH_HOME = Join-Path $dataRoot 'cache\torch'
$env:YOLO_CONFIG_DIR = Join-Path $dataRoot 'cache\ultralytics'
& $python -m treecut.diagnostics --deep
exit $LASTEXITCODE
