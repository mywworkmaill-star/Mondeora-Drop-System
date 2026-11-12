#!/bin/bash
set -e
cd "$(dirname "$0")"
if [[ -x "C:/Program Files/Python311/python.exe" ]]; then
  exec "C:/Program Files/Python311/python.exe" main.py --mode full "$@"
fi
exec python3.11 main.py --mode full "$@"

