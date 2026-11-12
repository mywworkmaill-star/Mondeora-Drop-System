@echo off
setlocal
title Mondeora Dropshipping
cd /d "%~dp0"
"C:\Program Files\Python311\python.exe" main.py --mode full %*
pause

