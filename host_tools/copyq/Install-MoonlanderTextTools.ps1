[CmdletBinding(SupportsShouldProcess)]
param(
    [switch]$ActivateShortcuts,
    [string]$CopyQPath = 'C:\Program Files\CopyQ\copyq.exe',
    [string]$ReselectHelperPath = (Join-Path $PSScriptRoot '..\reselect\Moonlander.Reselect\bin\Release\net10.0-windows\win-x64\publish\Moonlander.Reselect.exe')
)

$ErrorActionPreference = 'Stop'

function ConvertTo-JavaScriptPath {
    param([Parameter(Mandatory)][string]$Path)
    return $Path.Replace('\', '/').Replace("'", "\'")
}

if (-not (Test-Path -LiteralPath $CopyQPath -PathType Leaf)) {
    throw "CopyQ executable not found: $CopyQPath"
}
if (-not (Test-Path -LiteralPath $ReselectHelperPath -PathType Leaf)) {
    throw "Reselection helper not found. Publish it first: $ReselectHelperPath"
}

$installRoot = Join-Path $env:LOCALAPPDATA 'MoonlanderTextTools'
$backupRoot = Join-Path $installRoot 'backups'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupPath = Join-Path $backupRoot "copyq-commands-$timestamp.ini"
$generatedCommandsPath = Join-Path $installRoot 'moonlander-commands.ini'
$helperDestination = Join-Path $installRoot 'Moonlander.Reselect.exe'

if (-not $PSCmdlet.ShouldProcess($installRoot, 'Back up CopyQ commands and install Moonlander text tools')) {
    return
}

[IO.Directory]::CreateDirectory($backupRoot) | Out-Null

$exportedCommands = & $CopyQPath eval -- 'exportCommands(commands())' 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "CopyQ command backup failed: $($exportedCommands -join [Environment]::NewLine)"
}
[IO.File]::WriteAllText(
    $backupPath,
    ($exportedCommands -join [Environment]::NewLine),
    [Text.UTF8Encoding]::new($false)
)

Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'transformations.js') -Destination $installRoot -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'transaction.js') -Destination $installRoot -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install_commands.js') -Destination $installRoot -Force
Copy-Item -LiteralPath $ReselectHelperPath -Destination $helperDestination -Force

$installPathForJavaScript = ConvertTo-JavaScriptPath $installRoot
$helperPathForJavaScript = ConvertTo-JavaScriptPath $helperDestination
$template = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'commands.template.ini') -Raw
$rendered = $template.Replace('{{INSTALL_DIR}}', $installPathForJavaScript)
$rendered = $rendered.Replace('{{RESELECT_HELPER}}', $helperPathForJavaScript)
[IO.File]::WriteAllText($generatedCommandsPath, $rendered, [Text.UTF8Encoding]::new($false))

$installerScript = ConvertTo-JavaScriptPath (Join-Path $installRoot 'install_commands.js')
$commandsScript = ConvertTo-JavaScriptPath $generatedCommandsPath
$activate = if ($ActivateShortcuts) { 'true' } else { 'false' }
$expression = "source('$installerScript'); MoonlanderCommandInstaller.install('$commandsScript', $activate);"
$installOutput = & $CopyQPath eval -- $expression 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "CopyQ command installation failed. Backup: $backupPath`n$($installOutput -join [Environment]::NewLine)"
}

$mode = if ($ActivateShortcuts) { 'active shortcuts' } else { 'staged without shortcuts' }
Write-Output "Installed Moonlander CopyQ commands ($mode)."
Write-Output "Backup: $backupPath"
