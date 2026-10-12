"""Single-process Windows entry point. Configuration errors exit before binding."""
import logging
from pathlib import Path
import uvicorn
from astraljet.alpaca_challenge.config import Settings
from astraljet.alpaca_challenge.main import create_app


if __name__=='__main__':
    settings=Settings()
    logs=Path(__file__).resolve().parents[1]/'.runtime/alpaca/logs'
    logs.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s',
                        handlers=[logging.FileHandler(logs/'service.log',encoding='utf-8'),logging.StreamHandler()])
    # httpx INFO may contain URLs, and debug transports can contain headers; keep disabled.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    uvicorn.run(create_app(settings),host='127.0.0.1',port=8876,workers=1,access_log=False)
