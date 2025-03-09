@echo off
setlocal

REM Define installation path
set TARGET_PATH=%USERPROFILE%\BoardMaster

REM Create installation directory
if not exist "%TARGET_PATH%" mkdir "%TARGET_PATH%"
if not exist "%TARGET_PATH%\piece_images" mkdir "%TARGET_PATH%\piece_images"

REM Copy BoardMaster.exe
echo Copying BoardMaster.exe...
copy "%~dp0BoardMaster.exe" "%TARGET_PATH%" /Y

REM Copy piece images from the pieces folder to piece_images folder
echo Copying piece images...
for %%f in ("%~dp0pieces\*.png") do (
    copy "%%f" "%TARGET_PATH%\piece_images\" /Y
)

REM Confirm installation success
echo BoardMaster has been installed successfully to %TARGET_PATH%!
powershell -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$env:USERPROFILE\Desktop\BoardMaster.lnk\");$s.TargetPath=\"%~dp0BoardMaster.exe\";$s.Save()"
echo You can run it from there or from the desktop shortcut.
pause
