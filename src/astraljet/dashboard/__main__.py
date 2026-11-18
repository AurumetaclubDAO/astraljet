import uvicorn
from .config import HOST, PORT
from .api.app import create_app


def main():
    uvicorn.run(create_app(), host=HOST, port=PORT, workers=1, access_log=False, log_level='warning')


if __name__ == '__main__':
    main()
