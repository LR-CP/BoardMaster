# BoardMaster ![BoardMasterLogo](./img/king.ico)

A free chess analysis tool

## Setup

### pip

To setup your dev environment you will need to run the following command:

`pip install chess PySide2 nuitka`

Ensure you are using **Python 3.10** or higher

**OR**

You can run the `setup.sh` script to setup a Python venv and install the `requirements.txt` file.

### Stockfish

You will need to download [stockfish](https://stockfishchess.org/download/) to be able to use this program.

Once you have downloaded stockfish, follow these steps to add it to your PATH:

1. Extract the downloaded zip file onto your PC.
2. Go into the *stockfish* folder and change the exe name to just `stockfish`.
3. Copy the *stockfish* folder to your *C:\Program Files* folder.
4. Open up your Environment Variables window (type environment into your search bar on Windows and open the program titled "Edit the system environment variables")
5. Press the "Environment Variables..." button at the bottom of the window.
6. In both the top and bottom panes of the new window, double click the entry with variable name "Path", click the "New" button on the right side of the new window and copy *C:\Program Files\stockfish*.
7. Press "Enter" and then "OK" on all windows until they are closed.
8. You may need to reboot your computer or just close and open the terminal to invoke the new Path.

This is everything you need to run the source code.

## License

This program is licensed under the GNU General Public License and can be seen in the [LICENSE](./LICENSE) file

## Citations

Logo used from https://www.iconfinder.com/search?q=chess+king&price=free