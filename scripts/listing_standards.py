"""Canonical GET-only recurring listing-standards job; safe to schedule."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.jobs import main

if __name__ == '__main__':
    raise SystemExit(main(['listing_standards', '--semantic-outcome', *sys.argv[1:]]))
