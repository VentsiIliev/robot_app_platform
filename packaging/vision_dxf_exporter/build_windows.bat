@echo off
setlocal

cd /d "%~dp0\..\.."

if not exist ".venv\Scripts\python.exe" (
  where py.exe >nul 2>nul
  if errorlevel 1 (
    echo Missing .venv\Scripts\python.exe and py.exe. Install Windows Python or create a Windows .venv.
    exit /b 1
  )
  py.exe -3 -m PyInstaller packaging\vision_dxf_exporter\vision_dxf_exporter.spec --noconfirm --clean
) else (
  ".venv\Scripts\python.exe" -m PyInstaller packaging\vision_dxf_exporter\vision_dxf_exporter.spec --noconfirm --clean
)
exit /b %ERRORLEVEL%
