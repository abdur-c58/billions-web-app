$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BinDir = Join-Path $env:USERPROFILE "bin"
$Launcher = Join-Path $BinDir "ytserver.cmd"
$OldLauncher = Join-Path $BinDir "server.cmd"

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

@(
    "@echo off",
    "cd /d `"$ProjectRoot`"",
    "call npm run server"
) | Set-Content -Path $Launcher -Encoding ASCII

if (Test-Path $OldLauncher) {
    Remove-Item $OldLauncher -Force
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$BinDir*") {
    $updated = if ($userPath) { "$userPath;$BinDir" } else { $BinDir }
    [Environment]::SetEnvironmentVariable("Path", $updated, "User")
    $env:Path = "$env:Path;$BinDir"
}

Write-Host ""
Write-Host "Installed global command: ytserver" -ForegroundColor Green
Write-Host "Launcher: $Launcher"
Write-Host "Project:  $ProjectRoot"
Write-Host ""
Write-Host "Open a NEW terminal, then run:" -ForegroundColor Yellow
Write-Host "  ytserver"
Write-Host ""
Write-Host "Or from the project folder:" -ForegroundColor Yellow
Write-Host "  npm run server"
Write-Host ""
