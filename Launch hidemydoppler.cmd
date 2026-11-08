@echo off
rem hidemydoppler - double-click to check prerequisites and launch the app
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Program\prepare_windows.ps1" -AutoRun %*
