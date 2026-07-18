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

function Invoke-CopyQExpression {
    param(
        [Parameter(Mandatory)][string]$Expression,
        [Parameter(Mandatory)][string]$Operation
    )

    # CopyQ is a GUI executable. On Windows, PowerShell must pipe its output to
    # wait for the CLI response and receive the server's exit code.
    $output = @(& $CopyQPath eval -- $Expression 2>&1 | Write-Output)
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        throw "$Operation did not return a CopyQ CLI exit code. Is the running CopyQ instance available to this Windows user?"
    }
    if ($exitCode -ne 0) {
        throw "$Operation failed with CopyQ exit code ${exitCode}: $($output -join [Environment]::NewLine)"
    }
    return $output
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
$helperDestination = Join-Path $installRoot 'Moonlander.Reselect.exe'

if (-not $PSCmdlet.ShouldProcess($installRoot, 'Back up CopyQ commands and install Moonlander text tools')) {
    return
}

[IO.Directory]::CreateDirectory($backupRoot) | Out-Null

$probeOutput = @(Invoke-CopyQExpression -Expression "'MOONLANDER_COPYQ_READY'" -Operation 'CopyQ readiness probe')
if (($probeOutput -join [Environment]::NewLine).Trim() -ne 'MOONLANDER_COPYQ_READY') {
    throw "CopyQ readiness probe returned unexpected output: $($probeOutput -join [Environment]::NewLine)"
}
$exportedCommands = @(Invoke-CopyQExpression -Expression 'exportCommands(commands())' -Operation 'CopyQ command backup')
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
$installerScript = ConvertTo-JavaScriptPath (Join-Path $installRoot 'install_commands.js')
$activate = if ($ActivateShortcuts) { 'true' } else { 'false' }
$expression = "source('$installerScript'); MoonlanderCommandInstaller.install('$installPathForJavaScript', '$helperPathForJavaScript', $activate);"
$installOutput = @(Invoke-CopyQExpression -Expression $expression -Operation "CopyQ command installation (backup: $backupPath)")

$expectedNames = @(
    'Moonlander: Smart Title Case'
    'Moonlander: Cycle Case'
    'Moonlander: Transplant Hebrew-English'
)
$expectedShortcutByName = [ordered]@{
    'Moonlander: Smart Title Case' = 'F13'
    'Moonlander: Cycle Case' = 'F19'
    'Moonlander: Transplant Hebrew-English' = 'F22'
}
$verificationExpression = @"
(function () {
    var wanted = ['Moonlander: Smart Title Case', 'Moonlander: Cycle Case', 'Moonlander: Transplant Hebrew-English'];
    return JSON.stringify(commands()
        .filter(function (command) { return wanted.indexOf(command.name) !== -1; })
        .map(function (command) {
            return {
                name: command.name,
                globalShortcuts: command.globalShortcuts || [],
                isGlobalShortcut: Boolean(command.isGlobalShortcut)
            };
        }));
}())
"@
$verificationOutput = @(Invoke-CopyQExpression -Expression $verificationExpression -Operation 'CopyQ command verification')
$verificationJson = ($verificationOutput -join [Environment]::NewLine).Trim()
try {
    # Windows PowerShell 5.1 preserves a top-level JSON array as one nested
    # pipeline object. Enumerate it explicitly so each command is verified
    # against only its own shortcut.
    $parsedCommands = ConvertFrom-Json -InputObject $verificationJson
    $actualCommands = @(foreach ($command in $parsedCommands) { $command })
} catch {
    throw "CopyQ command verification returned invalid JSON: $verificationJson. Backup: $backupPath"
}
$actualNames = @($actualCommands | ForEach-Object { $_.name })
$nameDifference = @(Compare-Object -ReferenceObject ($expectedNames | Sort-Object) -DifferenceObject ($actualNames | Sort-Object))
if ($nameDifference.Count -ne 0) {
    throw "CopyQ command verification failed. Expected all three Moonlander commands; CopyQ returned: $($actualNames -join ', '). Backup: $backupPath"
}

foreach ($name in $expectedNames) {
    $actualCommand = @($actualCommands | Where-Object { $_.name -eq $name })[0]
    $actualShortcuts = @($actualCommand.globalShortcuts | ForEach-Object { [string]$_ })
    $expectedShortcuts = if ($ActivateShortcuts) { @($expectedShortcutByName[$name]) } else { @() }
    $shortcutDifference = @(Compare-Object -ReferenceObject $expectedShortcuts -DifferenceObject $actualShortcuts -CaseSensitive)
    if ($shortcutDifference.Count -ne 0 -or [bool]$actualCommand.isGlobalShortcut -ne [bool]$ActivateShortcuts) {
        throw "CopyQ shortcut verification failed for '$name'. Expected: $($expectedShortcuts -join ', '); actual: $($actualShortcuts -join ', '). Backup: $backupPath"
    }
}

$mode = if ($ActivateShortcuts) { 'active shortcuts' } else { 'staged without shortcuts' }
Write-Output "Installed Moonlander CopyQ commands ($mode)."
Write-Output "Backup: $backupPath"
