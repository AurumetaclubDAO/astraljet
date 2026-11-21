$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'dashboard_site_publish.py'
$processes = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($script) }
foreach ($process in $processes) { Stop-Process -Id $process.ProcessId -ErrorAction Stop }
Write-Output 'Zatrzymano tylko publikator witryny. Lokalny dashboard i boty pozostaja bez zmian.'
