@echo off
setlocal
cd /d "%~dp0"

set PYTHON=
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if not defined PYTHON where python3 >nul 2>&1 && set PYTHON=python3
if not defined PYTHON where py >nul 2>&1 && set PYTHON=py -3
if not defined PYTHON where python >nul 2>&1 && set PYTHON=python

if not defined PYTHON (
    echo Python not found. Install Python 3.10+ from https://www.python.org/downloads/
    exit /b 1
)

echo Using: %PYTHON%
echo Installing RushTV dependencies...
%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 (
    echo pip install failed.
    exit /b 1
)

echo Generating branded assets if missing...
%PYTHON% scripts\generate_assets.py

echo Building RushTV.exe with PyInstaller...
%PYTHON% -m PyInstaller RushTV.spec --noconfirm
if errorlevel 1 (
    echo PyInstaller build failed.
    exit /b 1
)

echo.
echo Build complete: dist\RushTV.exe
endlocal
