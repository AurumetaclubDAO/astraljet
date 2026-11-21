import base64
import json
import os
import subprocess
from ..config import TASKS
from ..models import datum, missing, utcnow


def collect(config, run=subprocess.run):
    if not config.schedule_enabled:
        return {name: missing('Harmonogram', 'Odczyt wyłączony w konfiguracji panelu') for name in TASKS}
    names = ','.join("'" + x + "'" for x in TASKS)
    script = "$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';$names=@(" + names + ");$all=@(Get-ScheduledTask -ErrorAction Stop);$out=@();foreach($n in $names){try{$matches=@($all|Where-Object TaskName -eq $n);if($matches.Count -ne 1){throw 'Unknown task'};$t=$matches[0];$i=$t|Get-ScheduledTaskInfo -ErrorAction Stop;$out+=@{name=$n;state=[string]$t.State;last_run=$i.LastRunTime.ToString('o');last_result=$i.LastTaskResult;next_run=$i.NextRunTime.ToString('o')}}catch{$out+=@{name=$n;error=$true}}};ConvertTo-Json -InputObject $out -Compress"
    try:
        result = run(['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                      base64.b64encode(script.encode('utf-16-le')).decode('ascii')], capture_output=True, timeout=30,
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode or len(result.stdout) > 100_000:
            raise ValueError('Harmonogram niedostępny')
        data = json.loads(result.stdout.decode('utf-8-sig'))
        indexed = {x['name']: x for x in data}
    except (OSError, ValueError, subprocess.TimeoutExpired, KeyError, TypeError):
        indexed = {}
    return {name: datum({k: indexed[name].get(k) for k in ('state', 'last_run', 'last_result', 'next_run')},
                        'Harmonogram / ' + name, utcnow(), config.freshness['schedule'])
            if name in indexed and not indexed[name].get('error') else missing('Harmonogram / ' + name, 'Brak odczytu zadania') for name in TASKS}
