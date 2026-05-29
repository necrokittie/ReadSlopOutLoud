@echo off
cd /d "%~dp0"
python "%~dp0read_slop_out_loud.py"
if errorlevel 1 (pause)
