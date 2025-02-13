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

> Stockfish is compiled into the release binary using the `build_release.bat` script which uses `nuitka`

For *dev* purposes you will need to download the stockfish exe from the website by following the instructions below:

You will need to download [stockfish](https://stockfishchess.org/download/) to be able to use this program.

Once you have downloaded stockfish, follow these steps:

1. Extract the downloaded zip file onto your PC.
2. Go into the *stockfish* folder and change the exe name to just `stockfish`.
3. Create a folder named *stockfish* in your repo folder and copy the *stockfish.exe* file to the *stockfish* folder in your local clone of this repo.

This is everything you need to run the source code.

## License

This program is licensed under the GNU General Public License and can be seen in the [LICENSE](./LICENSE) file

## Citations

Logo used from https://www.iconfinder.com/search?q=chess+king&price=free