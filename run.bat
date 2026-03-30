@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=C:\Users\siski\AppData\Local\Programs\Python\Python311\python.exe"
if exist "%PYTHON_EXE%" (
    set "PYTHON_CMD=%PYTHON_EXE%"
) else (
    set "PYTHON_CMD=py -3.11"
)

if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv || goto :error
)

call ".venv\Scripts\activate.bat" || goto :error
python -m pip install --upgrade pip || goto :error
python -m pip install -r requirements.txt || goto :error
python main.py
goto :eof

:error
echo Failed to run BlinkGuard.
exit /b 1
