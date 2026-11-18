"""Uruchamia istniejące testy TQ na lokalnej kopii, nigdy w katalogu runnerów."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(r'C:\Users\karol\Desktop\TQ-Common')
DEST=ROOT/'.runtime/dashboard/tq-test'

if __name__=='__main__':
    (DEST/'tests').mkdir(parents=True,exist_ok=True)
    for name in ('risk_gate.py','gated_order.py','risk_config.json','tests/test_risk_gate.py','tests/test_gated_order.py'):
        shutil.copy2(SOURCE/name,DEST/name)
    env=os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1',TEMP=str(ROOT/'.runtime/dashboard/tmp'),TMP=str(ROOT/'.runtime/dashboard/tmp'))
    result=subprocess.run([sys.executable,'-B','-m','pytest',str(DEST/'tests'),'-v','-p','no:cacheprovider','--rootdir',str(DEST)],env=env,cwd=DEST,capture_output=True,text=True,encoding='utf-8')
    report=ROOT/'docs/dashboard/TEST_TQ.txt'
    report.write_text(result.stdout+result.stderr,encoding='utf-8')
    print(result.stdout)
    sys.exit(result.returncode)
