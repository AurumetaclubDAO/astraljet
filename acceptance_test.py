"""Entry point odbioru lokalnego Alpaca Paper, bez zleceń."""
import asyncio
import sys
from scripts.acceptance_test import run

if __name__=='__main__':
    sys.exit(asyncio.run(run()))
