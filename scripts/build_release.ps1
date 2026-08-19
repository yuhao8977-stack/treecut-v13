param(
    [string]$InstallRoot = 'D:\TreeCut_v13',
    [string]$PayloadRoot = 'D:\TreeCut_installer\output\payload\TreeCut_v13',
    [string]$InstallerScript = 'D:\TreeCut_installer\TreeCut_v13_CPU_Setup.iss',
    [string]$GameInstallerScript = 'D:\TreeCut_installer\TreeCut_v13_Game_Setup.iss',
    [string]$Iscc = 'C:\Users\33186\Documents\Codex\2026-08-04\wo\work\treecut_installer_payload\tools\inno\tools\ISCC.exe'
)
$ErrorActionPreference = 'Stop'
$python = Join-Path $InstallRoot 'runtime\python.exe'

Write-Host '1/3 running tests and compile check'
Push-Location $InstallRoot
& $python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw 'tests failed' }
& $python -m compileall -q src
Pop-Location

Write-Host '2/3 regenerating and verifying release manifest'
$env:PYTHONPATH = Join-Path $InstallRoot 'scripts'
Push-Location $PayloadRoot
& $python -m scripts.generate_release_metadata --root $PayloadRoot
& $python -m scripts.verify_release_manifest --root $PayloadRoot
if ($LASTEXITCODE -ne 0) { throw 'manifest verification failed' }
Pop-Location

Write-Host '3/3 building installers'
& $Iscc $InstallerScript
if ($LASTEXITCODE -ne 0) { throw 'installer build failed' }
& $Iscc $GameInstallerScript
if ($LASTEXITCODE -ne 0) { throw 'game installer build failed' }
Write-Host 'RELEASE_BUILD_OK'
