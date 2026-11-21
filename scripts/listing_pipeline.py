"""Release saved reviewed plans via the shared gated job; never retry writes here."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.jobs import main

if __name__ == '__main__':
    raise SystemExit(main(['listing_pipeline', '--semantic-outcome', *sys.argv[1:]]))
