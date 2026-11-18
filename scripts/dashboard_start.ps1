$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$python = Join-Path $root '.runtime/dashboard-venv/Scripts/python.exe'
$stateDir = Join-Path $root '.runtime/dashboard'
if (!(Test-Path -LiteralPath $python)) { throw 'Brak srodowiska dashboardu. Zobacz docs/dashboard/README.md.' }
if (Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq 8877) {
    throw 'Port 8877 jest zajety. Nie zatrzymano jego wlasciciela.'
}
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
$env:PYTHONPATH = Join-Path $root 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
$env:TEMP = Join-Path $stateDir 'tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$process = Start-Process -FilePath $python -ArgumentList '-B','-m','astraljet.dashboard' -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $stateDir 'stdout.log') -RedirectStandardError (Join-Path $stateDir 'stderr.log')
$health = $null
for ($attempt=0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Seconds 1
    try { $health=Invoke-RestMethod -Uri 'http://127.0.0.1:8877/api/health' -TimeoutSec 2; break } catch {}
}
if (!$health -or $health.service -ne 'astraljet-dashboard') { throw 'Brak odpowiedzi dashboardu. Sprawdz lokalny log; nie zatrzymano innych procesow.' }
$actual = Get-Process -Id $health.pid -ErrorAction Stop
$command = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $actual.Id)
if ($command.CommandLine -notmatch 'astraljet\.dashboard') { throw 'Niepotwierdzona tozsamosc procesu.' }
@{pid=$actual.Id; started=$actual.StartTime.ToUniversalTime().ToString('o'); executable=$actual.Path; module='astraljet.dashboard'; root=$root} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $stateDir 'process.json') -Encoding UTF8
Write-Output 'Dashboard: http://127.0.0.1:8877 | Tylko odczyt. Pierwsza runda danych moze potrwac do 30 sekund.'
