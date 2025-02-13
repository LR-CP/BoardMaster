@echo off
REM Define paths
set DIST_DIR=BoardMaster
set OUTPUT=BoardMaster.zip
set EXE_FILE=BoardMaster.exe
set DATA_FOLDER=data

if "%~1" == "" (
    echo Usage: .\%~n0.bat ^<command^>
    echo Available commands:
    echo   - nuitka
    @REM echo   - pyinstaller
    goto :eof
)

if "%~1" == "nuitka" (
    cls
    echo Building using Nuitka
    venv\Scripts\python.exe -m nuitka --standalone --onefile --windows-console-mode=disable --plugin-enable=pyside6 --include-data-files=./stockfish/stockfish.exe=stockfish.exe --windows-icon-from-ico=.\img\king.ico BoardMaster.py
    goto :build_complete
)
@REM else if "%~1" == "pyinstaller" (
@REM     echo Building using PyInstaller
@REM     venv\Scripts\python.exe -m PyInstaller --onefile --windowed --add-data ".\\data\\*.json;." --add-data ".\\data\\exercises.csv;." --add-data ".\\img\\weight.ico;." --icon=".\\img\\weight.ico" --name "MuscleMaster" .\MuscleMaster.py
@REM     goto :build_complete
@REM )

:build_complete
echo Build complete.

@REM set SEVEN_ZIP_PATH="C:\Program Files\7-Zip\7z.exe"
@REM REM Full path to 7-Zip executable
@REM if not exist %SEVEN_ZIP_PATH% (
@REM     echo ERROR: 7zip not installed.
@REM )

@REM @REM REM Ensure data directory exists
@REM @REM if not exist %DATA_FOLDER% (
@REM @REM     echo ERROR: data folder not found
@REM @REM )
@REM REM Ensure executable exists
@REM if not exist %EXE_FILE% (
@REM     echo ERROR: executable file not found
@REM )

@REM REM Clean up old ZIP if it exists
@REM if exist %OUTPUT% (
@REM     echo Deleting old ZIP archive...
@REM     del %OUTPUT%
@REM )

@REM REM Compress files into a ZIP archive
@REM echo Compressing files into %OUTPUT%...
@REM %SEVEN_ZIP_PATH% a -tzip %OUTPUT% %DATA_FOLDER%/* %EXE_FILE%

@REM echo Packaging complete! Archive created: %OUTPUT%
