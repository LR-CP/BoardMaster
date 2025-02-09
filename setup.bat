@echo off

REM Set the project directory
set PROJECT_DIR=%~dp0

REM Check if Python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Python is not installed.
    goto :eof
)

REM Create a virtual environment
echo Creating virtual environment...
python -m venv %PROJECT_DIR%venv
call %PROJECT_DIR%venv\Scripts\activate

REM Install required packages
echo Installing required packages...
pip install -r %PROJECT_DIR%requirements.txt

echo Setup complete.
echo You can now run your program using the run script.
