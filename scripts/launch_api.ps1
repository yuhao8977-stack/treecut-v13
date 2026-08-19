param(
    [string]$HostAddress = '127.0.0.1',
    [int]$Port = 8765,
    [switch]$DevelopmentMode,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
if ($HostAddress -notin @('127.0.0.1', 'localhost', '::1')) {
    throw 'TreeCut API only permits local access.'
}
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$dataRoot = Join-Path $root 'runtime_data'
$python = Join-Path $root 'runtime\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'TreeCut v13 portable Python runtime is not installed.'
}
if ($ValidateOnly) {
    Write-Output $python
    exit 0
}
$probe = [System.Net.Sockets.TcpClient]::new()
try {
    $connect = $probe.BeginConnect($HostAddress, $Port, $null, $null)
    if ($connect.AsyncWaitHandle.WaitOne(300) -and $probe.Connected) {
        throw "Port $Port is already in use. TreeCut API may already be running."
    }
} finally {
    $probe.Dispose()
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
$env:TREECUT_API_HOST = $HostAddress
$env:TREECUT_API_PORT = [string]$Port
if ($DevelopmentMode) {
    $env:TREECUT_DEVELOPMENT_MODE = '1'
} else {
    Remove-Item Env:TREECUT_DEVELOPMENT_MODE -ErrorAction SilentlyContinue
}
$process = Start-Process -FilePath $python -ArgumentList '-m', 'treecut.api' -WorkingDirectory $root -WindowStyle Hidden -PassThru
$health = "http://$HostAddress`:$Port/health"
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 500
    if ($process.HasExited) {
        throw "TreeCut API startup process exited with code $($process.ExitCode). Check runtime_data\logs."
    }
    try {
        $null = Invoke-RestMethod -Uri $health -TimeoutSec 2 -UseBasicParsing
        Write-Output "TreeCut API started and passed health check: $health"
        Write-Output "API token file: $(Join-Path $dataRoot 'config\api_token.txt')"
        exit 0
    } catch {
        # Server may still be importing local models and database metadata.
    }
}
if (-not $process.HasExited) {
    Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
}
throw "TreeCut API did not pass health check within 20 seconds and was stopped. Check runtime_data\logs."
