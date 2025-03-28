@echo off
setlocal

REM Define installation path
set TARGET_PATH=%USERPROFILE%\BoardMaster

REM Create installation directory
if not exist "%TARGET_PATH%" mkdir "%TARGET_PATH%"
REM Copy BoardMaster.exe
echo Copying BoardMaster.exe...
copy "%~dp0BoardMaster.exe" "%TARGET_PATH%" /Y

REM Confirm installation success
echo BoardMaster has been installed successfully to %TARGET_PATH%!
powershell -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$env:USERPROFILE\Desktop\BoardMaster.lnk\");$s.TargetPath=\"%TARGET_PATH%\BoardMaster.exe\";$s.Save()"
echo You can run it from there or from the desktop shortcut.
pause
