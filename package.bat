@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=C:\Users\siski\AppData\Local\Programs\Python\Python311\python.exe"
set "VENV_PYTHON=.venv\Scripts\python.exe"
if exist "%PYTHON_EXE%" (
    set "PYTHON_CMD=%PYTHON_EXE%"
) else (
    set "PYTHON_CMD=py -3.11"
)

if not exist "%VENV_PYTHON%" (
    %PYTHON_CMD% -m venv .venv || goto :error
)

"%VENV_PYTHON%" -m ensurepip --upgrade >nul 2>nul
"%VENV_PYTHON%" -m pip install --upgrade pip || goto :error
"%VENV_PYTHON%" -m pip install -r requirements.txt || goto :error
"%VENV_PYTHON%" -m PyInstaller --noconfirm --clean --windowed --name BlinkCue --icon="icon.ico" --add-data "models;models" --add-data "icon.ico;." --hidden-import mediapipe.tasks.c --collect-submodules mediapipe.tasks.c --collect-binaries mediapipe.tasks.c main.py || goto :error
echo Build complete: dist\BlinkCue\BlinkCue.exe
goto :eof

:error
echo Failed to build BlinkCue.
exit /b 1
