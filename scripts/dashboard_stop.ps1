$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root '.runtime/dashboard/process.json'
if (!(Test-Path -LiteralPath $pidFile)) { Write-Output 'Brak zapisanego procesu dashboardu.'; exit 0 }
$saved = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
if ($saved.module -ne 'astraljet.dashboard' -or $saved.root -ne $root) { throw 'Nieprawidlowy plik procesu.' }
$process = Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
if (!$process) { Write-Output 'Dashboard juz zatrzymany.'; exit 0 }
$command = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $process.Id)
if ($process.StartTime.ToUniversalTime().Ticks -ne ([datetime]$saved.started).ToUniversalTime().Ticks -or $process.Path -ne $saved.executable -or $command.CommandLine -notmatch 'astraljet\.dashboard') {
    throw 'PID ma inna tozsamosc. Odmowa zatrzymania.'
}
Stop-Process -Id $process.Id -ErrorAction Stop
Write-Output 'Zatrzymano wylacznie zapisany proces dashboardu.'
