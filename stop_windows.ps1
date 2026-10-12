$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pidFile = Join-Path $PSScriptRoot '.runtime/alpaca/api-process.json'
if (!(Test-Path -LiteralPath $pidFile)) { Write-Output 'Brak zarejestrowanego procesu API.'; exit 0 }
$saved = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
$serviceProcess = Get-Process -Id $saved.pid -ErrorAction SilentlyContinue
if ($serviceProcess) {
    if ($serviceProcess.StartTime.ToUniversalTime().Ticks -ne ([datetime]$saved.started).ToUniversalTime().Ticks) { throw 'PID należy do innego procesu; odmowa zatrzymania.' }
    # Kill switch first; stopping a process does not close broker positions.
    & '.runtime/alpaca-venv/Scripts/python.exe' -c 'import httpx; from astraljet.alpaca_challenge.config import Settings; s=Settings(); r=httpx.post("http://127.0.0.1:8876/v1/kill-switch/on",headers={"Authorization":"Bearer "+s.executor_bearer_token.get_secret_value()},timeout=30); r.raise_for_status()'
    if ($LASTEXITCODE -ne 0) { throw 'Nie potwierdzono kill switch; proces pozostaje aktywny.' }
    Stop-Process -Id $serviceProcess.Id
    Write-Output 'API zatrzymane, kill switch zapisany. Otwarte pozycje NIE zostały zamknięte; lokalny monitoring zatrzymany.'
}
Remove-Item -LiteralPath $pidFile
