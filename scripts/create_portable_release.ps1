param([string]$Destination = 'G:\TreeCut_v13_release_candidate')
$ErrorActionPreference = 'Stop'
$source = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$destinationPath = [System.IO.Path]::GetFullPath($Destination)
if ($destinationPath -eq $source -or $destinationPath.StartsWith($source + [IO.Path]::DirectorySeparatorChar)) {
    throw 'The release directory cannot be inside the source directory.'
}
if ([IO.Path]::GetPathRoot($destinationPath) -eq 'C:\') {
    throw 'The release directory cannot be on drive C.'
}
if (Test-Path -LiteralPath $destinationPath) {
    throw "The release directory already exists: $destinationPath"
}
New-Item -ItemType Directory -Path $destinationPath -ErrorAction Stop | Out-Null
& robocopy $source $destinationPath /E /R:1 /W:1 /XD runtime_data tests __pycache__ /XF '*.pyc' /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) {
    throw "Release copy failed with robocopy code $LASTEXITCODE"
}
$runtimeData = Join-Path $destinationPath 'runtime_data'
foreach ($name in @('cache','database','logs','materials','output','temp','pycache')) {
    New-Item -ItemType Directory -Path (Join-Path $runtimeData $name) -Force | Out-Null
}
Write-Output "Portable release candidate created: $destinationPath"
Write-Output 'Run the installation diagnostic from the release directory.'
