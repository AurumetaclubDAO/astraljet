import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from aj_common import write
from datetime import datetime, timezone
REASONS = {'AJ-00': 'Wyłączony: AI witryny zablokowane (billing); brak płatnych usług',
           'AJ-02': 'Wyłączony: brak workera (rejestr ręczny)', 'AJ-04': 'Wyłączony: brak workera na Solyg',
           'AJ-05': 'Wyłączony: badania ręczne (PDF/research)', 'AJ-08': 'Wyłączony: brak workera (werdykt v-B 22.10 ręcznie)',
           'AJ-11': 'Wyłączony: brak darmowego, wiarygodnego źródła', 'AJ-14': 'Wyłączony: brak workera (koncentracja w Risk Managerze)',
           'AJ-17': 'Wyłączony: brak workera; polityka 0 USD', 'AJ-18': 'Wyłączony: poza zakresem tradingu'}
for r, why in REASONS.items():
    write(r, 'DISABLED', why, 'brak', '-', 10 ** 9)
write('AJ-07'.replace('AJ-07', 'AJ-07'), 'IDLE', 'Backtesty offline 15.10: TECH limit-retest (B) > wybicie (A); reszta hipotez odrzucona', 'box /workspace/bt', 'BT-2026-10-15-offline.md', 7 * 86400)
