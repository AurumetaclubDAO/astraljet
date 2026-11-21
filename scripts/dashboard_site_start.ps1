$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$stateDir = Join-Path $root '.runtime/dashboard'
$python = Join-Path $root '.runtime/dashboard-venv/Scripts/python.exe'
# Serializuj start reczny i kontrole Harmonogramu. Nie restartuj dzialajacych uslug.
$startupLock = [System.Threading.Mutex]::new($false, 'Local\AstralJetObservatoryStartup')
$locked = $false
try {
    try { $locked = $startupLock.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $locked = $true }
    if (!$locked) { Write-Output 'Inny start Obserwatorium jest w toku.'; return }
    if (!(Test-Path -LiteralPath (Join-Path $stateDir 'site-connection.dpapi'))) { throw 'Brak konfiguracji publikatora witryny.' }
    try { $health = Invoke-RestMethod 'http://127.0.0.1:8877/api/health' -TimeoutSec 3 } catch { $health = $null }
    if (!$health) { & (Join-Path $PSScriptRoot 'dashboard_start.ps1') }
    elseif ($health.service -ne 'astraljet-dashboard') { throw 'Port zajety przez inna aplikacje.' }
    $env:PYTHONDONTWRITEBYTECODE='1'
    $env:PYTHONUTF8='1'
    $script = Join-Path $PSScriptRoot 'dashboard_site_publish.py'
    $commandPattern = '(?i)(?:^|\s)"' + [regex]::Escape($script) + '"(?:\s|$)'
    $existing = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match $commandPattern })
    if ($existing.Count -gt 0) {
        Write-Output 'Dashboard odpowiada; publikator juz dziala.'
        return
    }
    $proc = Start-Process -FilePath $python -ArgumentList @('-B',('"'+$script+'"')) -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $stateDir 'publisher-stdout.log') -RedirectStandardError (Join-Path $stateDir 'publisher-stderr.log')
    Write-Output 'Uruchomiono publikator odczytow do prywatnej witryny AstralJet.'
} finally {
    if ($locked) { $startupLock.ReleaseMutex() }
    $startupLock.Dispose()
}
