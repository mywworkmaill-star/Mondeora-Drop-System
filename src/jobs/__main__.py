"""Restores `python -m src.jobs <job>` CLI support (see __init__.py for why)."""
import sys
from src.jobs_impl import main

if __name__ == '__main__':
    sys.exit(main())
