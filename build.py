import os
import sys
import subprocess
import platform

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def usage(script_name):
    print(f"Usage: {script_name} <command>")
    print("Available commands:")
    print("  quick")
    print("  full")

def get_venv_python(project_dir):
    """Return the path to the virtual environment's Python executable."""
    if os.name == "nt":
        return os.path.join(project_dir, "venv", "Scripts", "python.exe")
    else:
        return os.path.join(project_dir, "venv", "bin", "python")

def build_with_nuitka(venv_python, mode):
    """Build the project using Nuitka with options depending on the mode."""
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
    
    if mode == "full":
        # Add extra options for a full build
        full_options = ["--lto=yes", "--remove-output"]
        # Construct the command: insert full_options after "--onefile"
        command = [venv_python, "-m", "nuitka", "--standalone", "--onefile"] \
                  + full_options + base_command[5:]
    else:
        command = base_command

    print("Building using Nuitka...")
    subprocess.check_call(command)

def main():
    project_dir = os.path.abspath(os.path.dirname(__file__))

    if len(sys.argv) < 2:
        usage(os.path.basename(sys.argv[0]))
        sys.exit(1)

    mode = sys.argv[1].lower()
    if mode not in ["quick", "full"]:
        usage(os.path.basename(sys.argv[0]))
        sys.exit(1)

    clear_screen()
    
    venv_python = get_venv_python(project_dir)
    if not os.path.exists(venv_python):
        print(f"Error: Virtual environment not found at {venv_python}.")
        sys.exit(1)

    build_with_nuitka(venv_python, mode)
    print("Build complete.")

if __name__ == "__main__":
    main()
