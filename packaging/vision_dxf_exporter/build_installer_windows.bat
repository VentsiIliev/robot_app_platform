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
if errorlevel 1 exit /b %ERRORLEVEL%

set "ISCC_EXE=iscc.exe"
where iscc.exe >nul 2>nul
if errorlevel 1 (
  if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  ) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
  ) else (
    echo Missing Inno Setup compiler. Install Inno Setup 6 or add iscc.exe to PATH.
    exit /b 1
  )
)

"%ISCC_EXE%" packaging\vision_dxf_exporter\installer.iss
exit /b %ERRORLEVEL%
