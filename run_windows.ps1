param([switch]$Diagnostic)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.runtime/alpaca-venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $pythonPath)) {
    py -3.12 -m venv .runtime/alpaca-venv
    if ($LASTEXITCODE -ne 0) { throw 'Wymagany Python 3.12.' }
}
& $pythonPath -m pip install -r requirements-alpaca.txt -e .
if ($LASTEXITCODE -ne 0) { throw 'Instalacja nieudana.' }
if (!(Test-Path -LiteralPath '.env')) { throw 'Utwórz .env zgodnie z .env.example; nie publikuj kluczy.' }
& $pythonPath -m pytest tests/alpaca_challenge -q
if ($LASTEXITCODE -ne 0) { throw 'Testy nie przeszły.' }
& $pythonPath scripts/acceptance_test.py
if ($LASTEXITCODE -ne 0 -and !$Diagnostic) { throw 'NOT READY. Popraw konfigurację. -Diagnostic uruchamia wyłącznie dry-run mimo blokady brokera.' }
if ($Diagnostic) {
    & $pythonPath -c 'from astraljet.alpaca_challenge.config import Settings; assert not Settings().execute_orders, "Diagnostic wymaga EXECUTE_ORDERS=false"'
    if ($LASTEXITCODE -ne 0) { throw 'Diagnostic: wykonanie zleceń musi być wyłączone.' }
}
$pidFile = Join-Path $PSScriptRoot '.runtime/alpaca/api-process.json'
if (Test-Path -LiteralPath $pidFile) {
    $saved = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
    $existing = Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
    if ($existing -and $existing.StartTime.ToUniversalTime().Ticks -eq ([datetime]$saved.started).ToUniversalTime().Ticks) { throw 'API już działa.' }
}
$apiScript = Join-Path $PSScriptRoot 'scripts/run_alpaca_api.py'
if (Get-NetTCPConnection -State Listen -LocalPort 8876 -ErrorAction SilentlyContinue) { throw 'Port 8876 zajęty. Nie zatrzymano obcego procesu.' }
$serviceProcess = Start-Process -FilePath $pythonPath -ArgumentList ('"' + $apiScript + '"') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput '.runtime/alpaca/stdout.log' -RedirectStandardError '.runtime/alpaca/stderr.log'
@{pid=$serviceProcess.Id;started=$serviceProcess.StartTime.ToUniversalTime().ToString('o');executable=$pythonPath} | ConvertTo-Json | Set-Content -LiteralPath $pidFile
$health = $null
for ($attempt = 0; $attempt -lt 45; $attempt++) {
    Start-Sleep -Seconds 1
    try { $health = Invoke-RestMethod 'http://127.0.0.1:8876/health'; break }
    catch {
        if ($serviceProcess.HasExited) { throw 'Proces API zakończył się. Sprawdź .runtime/alpaca/stderr.log.' }
        if ($attempt -eq 44) { throw 'API nie odpowiedziało przez 45 sekund. Sprawdź logi przed kolejnym startem.' }
    }
}
if ($health.service -ne 'astra-alpaca-challenge') { throw 'Odpowiedział inny serwis.' }
$actualProcess = Get-Process -Id $health.pid
@{pid=$actualProcess.Id;started=$actualProcess.StartTime.ToUniversalTime().ToString('o');executable=$pythonPath} | ConvertTo-Json | Set-Content -LiteralPath $pidFile
$health | ConvertTo-Json
Write-Output 'API: http://127.0.0.1:8876 | Swagger: http://127.0.0.1:8876/docs'
