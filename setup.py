import os
import sys
import subprocess
import platform

def main():
    # Determine the project directory (directory where this script is located)
    project_dir = os.path.abspath(os.path.dirname(__file__))
    print(f"Project directory: {project_dir}")

    # Since this script is running with Python, we assume Python is installed.
    if not sys.executable:
        print("Error: Python is not installed.")
        sys.exit(1)

    # Create a virtual environment in a folder called 'venv'
    venv_dir = os.path.join(project_dir, "venv")
    if not os.path.exists(venv_dir):
        print("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
    else:
        print("Virtual environment already exists.")

    # Determine the path to the pip executable in the virtual environment
    if platform.system() == "Windows":
        pip_executable = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:
        pip_executable = os.path.join(venv_dir, "bin", "pip")

    # Check if pip exists in the virtual environment
    if not os.path.exists(pip_executable):
        print("Error: pip not found in the virtual environment.")
        sys.exit(1)

    # Install required packages from requirements.txt, if the file exists
    requirements_file = os.path.join(project_dir, "requirements.txt")
    if os.path.exists(requirements_file):
        print("Installing required packages...")
        subprocess.check_call([pip_executable, "install", "-r", requirements_file])
    else:
        print("requirements.txt not found. Skipping package installation.")

    print("Setup complete.")
    print("You can now run your program using the run script.")

if __name__ == "__main__":
    main()
