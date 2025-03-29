import os
import sys
import subprocess
import platform
import shutil

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def usage(script_name):
    print(f"Usage: {script_name} <command>")
    print("Available commands:")
    print("  quick")
    print("  debug")
    print("  full")

def get_venv_python(project_dir):
    """Return the path to the virtual environment's Python executable."""
    if os.name == "nt":
        return os.path.join(project_dir, "venv", "Scripts", "python.exe")
    else:
        return os.path.join(project_dir, "venv", "bin", "python")

def build_with_nuitka(venv_python, mode):
    """Build the project using Nuitka with options depending on the mode."""
    if mode == "debug":
        base_command = [
            venv_python,
            "-m", "nuitka",
            "--standalone",
            "--onefile",
            "--plugin-enable=pyside6",
            "--windows-icon-from-ico=./img/king.ico",
            "src/BoardMaster.py"
        ]
    elif mode == "quick":
        base_command = [
            venv_python,
            "-m", "nuitka",
            "--standalone",
            "--onefile",
            "--windows-console-mode=disable",
            "--plugin-enable=pyside6",
            "--windows-icon-from-ico=./img/king.ico",
            "src/BoardMaster.py"
        ]
    
    elif mode == "full":
        base_command = [
            venv_python,
            "-m", "nuitka",
            "--standalone",
            "--onefile",
            "--windows-console-mode=disable",
            "--plugin-enable=pyside6",
            "--windows-icon-from-ico=./img/king.ico",
            "--lto=yes",
            "--remove-output",
            "src/BoardMaster.py"
        ]

    command = base_command

    print("Building BoardMaster binary using Nuitka...")
    subprocess.check_call(command)

def create_installer(venv_python):
    # Move built binary into build dir
    project_dir = os.path.dirname(__file__)

    if platform.system() == "Windows":
        release_dir = os.path.join(project_dir, "release", "Windows")
        if not os.path.exists(release_dir):
            os.makedirs(release_dir)
        binary_name = "BoardMaster.exe"
        binary_path = os.path.join(project_dir, binary_name)
        target_path = os.path.join(release_dir, binary_name)
        if os.path.exists(target_path):
            os.remove(target_path)
        os.rename(binary_path, target_path)
    else:
        release_dir = os.path.join(project_dir, "release", "Linux")
        if not os.path.exists(release_dir):
            os.makedirs(release_dir)
        binary_name = "BoardMaster.bin"
        binary_path = os.path.join(project_dir, binary_name)
        target_path = os.path.join(release_dir, binary_name)
        if os.path.exists(target_path):
            os.remove(target_path)
        os.rename(binary_path, target_path)

def package_final_installer(venv_python):
    """
    Packages the build folder into a final installer:
      - On Windows: creates a self-extracting installer using IExpress.
      - On Linux: creates a self-extracting .run installer using makeself.
    """
    project_dir = os.path.abspath(os.path.dirname(__file__))
    if platform.system() == "Windows":
        release_dir = os.path.join(project_dir, "release", "Windows")
    else:
        release_dir = os.path.join(project_dir, "release", "Linux")
    print("Packaging final installer...")

    if platform.system() == "Windows":

        # Create a startup.cmd file for post-installation
        install_cmd_path = os.path.join(release_dir, "install.cmd")
        with open(install_cmd_path, "w") as f:
            f.write('@echo off\n')
            f.write('setlocal\n\n')
            f.write('REM Define installation path\n')
            f.write('set TARGET_PATH=%USERPROFILE%\\BoardMaster\n\n')
            f.write('REM Create installation directory\n')
            f.write('if not exist "%TARGET_PATH%" mkdir "%TARGET_PATH%"\n')
            f.write('REM Copy BoardMaster.exe\n')
            f.write('echo Copying BoardMaster.exe...\n')
            f.write('copy "%~dp0BoardMaster.exe" "%TARGET_PATH%" /Y\n\n')
            f.write('REM Confirm installation success\n')
            f.write('echo BoardMaster has been installed successfully to %TARGET_PATH%!\n')
            f.write(r'powershell -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$env:USERPROFILE\Desktop\BoardMaster.lnk\");$s.TargetPath=\"%TARGET_PATH%\BoardMaster.exe\";$s.Save()"')
            f.write("\n")
            f.write('echo You can run it from there or from the desktop shortcut.\n')
            f.write('pause\n')
                
        # Define the target installer output path
        target_installer = os.path.join(release_dir, "BoardMasterInstaller.exe")
        
        # Create a temporary .sed file for IExpress configuration.
        sed_content =f"""[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=0
UseLongFileName=0
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=%AdminQuietInstCmd%
UserQuietInstCmd=%UserQuietInstCmd%
SourceFiles=SourceFiles
[Strings]
InstallPrompt=Are you sure you want to install? You may get too good at chess.
DisplayLicense={project_dir}\\LICENSE
FinishMessage=Installation Completed!
TargetName={project_dir}\\release\\Windows\\BoardMasterInstaller.exe
FriendlyName=BoardMaster
AppLaunched=install.cmd
PostInstallCmd={project_dir}\\release\\Windows\\install.cmd
AdminQuietInstCmd=
UserQuietInstCmd=
FILE0="BoardMaster.exe"
[SourceFiles]
SourceFiles0={project_dir}\\release\\Windows\\
[SourceFiles0]
%FILE0%=
"""
        sed_path = os.path.join(release_dir, "installer.sed")
        with open(sed_path, "w", encoding="windows-1252") as f:
            f.write(sed_content)
        
        # Call IExpress to create the installer.
        iexpress_path = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", "iexpress.exe")
        print("Running IExpress...")
        subprocess.check_call([iexpress_path, "/N", "/M", sed_path])
        print(f"IExpress installer created at: {target_installer}")
    else:
        # For Linux, create a self-extracting .run file using makeself.
        run_installer = os.path.join(release_dir, "BoardMasterInstaller.run")
        installer_script = os.path.join(release_dir, "install.sh")
        if not os.path.exists(installer_script):
            print("Error: installer.sh not found in build folder. Please create one to handle installation.")
            return
        if os.path.exists(run_installer):
            os.remove(run_installer)
        subprocess.check_call(["makeself", release_dir, run_installer, "BoardMaster Installer", "./install.sh"])
        print(f"Linux .run installer created at: {run_installer}")

def main():
    project_dir = os.path.abspath(os.path.dirname(__file__))

    if len(sys.argv) < 2:
        usage(os.path.basename(sys.argv[0]))
        sys.exit(1)

    mode = sys.argv[1].lower()
    if mode not in ["quick", "debug", "full"]:
        usage(os.path.basename(sys.argv[0]))
        sys.exit(1)

    clear_screen()
    
    venv_python = get_venv_python(project_dir)
    if not os.path.exists(venv_python):
        print(f"Error: Virtual environment not found at {venv_python}.")
        sys.exit(1)

    build_with_nuitka(venv_python, mode)
    create_installer(venv_python)
    package_final_installer(venv_python)
    print("Build complete.")

if __name__ == "__main__":
    main()