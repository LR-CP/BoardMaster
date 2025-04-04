#!/bin/bash
# installer.sh
# This script installs BoardMaster on Linux by copying all extracted files
# from the build folder into a user‑specified installation directory.
#
# It is intended to be bundled inside your self‑extracting .run installer.

clear
echo "==========================================="
echo "           BoardMaster Installer"
echo "==========================================="
echo ""
echo "This installer will copy BoardMaster files to your system."
echo ""

# Default installation directory (you can change this as needed)
DEFAULT_INSTALL_DIR="/home/$(whoami)/BoardMaster"
# read -p "Enter installation directory [${DEFAULT_INSTALL_DIR}]: " INSTALL_DIR
# if [ -z "$INSTALL_DIR" ]; then
INSTALL_DIR=$DEFAULT_INSTALL_DIR
# fi

echo ""
echo "Installing BoardMaster to: $INSTALL_DIR"
echo ""

# Create the installation directory if it doesn't exist
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Creating installation directory..."
    mkdir -p "$INSTALL_DIR"
    if [ $? -ne 0 ]; then
        echo "Error: Unable to create installation directory."
        echo "Please run as root or choose another directory."
        exit 1
    fi
fi

# Copy the contents of the Linux release folder (current directory) to the installation directory.
echo "Copying files..."
cp -r * "$INSTALL_DIR"
if [ $? -ne 0 ]; then
    echo "Error: Failed to copy files."
    exit 1
fi

# Modify the desktop file to contain correct path
sed -i "s/USER/$(whoami)/g" $INSTALL_DIR/BoardMaster.dekstop
sudo cp $INSTALL_DIR/BoardMaster.dekstop /usr/share/applications/

chmod +x $INSTALL_DIR/BoardMaster.bin

echo ""
echo "Installation complete!"
echo "BoardMaster has been installed to: $INSTALL_DIR"
echo "You may now run BoardMaster from the installation directory or create a shortcut as desired."
echo ""
read -p "Press Enter to exit..."
exit 0
