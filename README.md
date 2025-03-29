# BoardMaster ![BoardMasterLogo](./img/king.ico)

A free chess analysis tool for reviewing and improving your chess games. BoardMaster provides powerful analysis features using the Stockfish engine to help players understand their games better.

## Features

- Analyze chess games with Stockfish engine integration
- Interactive board for testing positions
- Move navigation with evaluation bar
- Visual arrow indicators for engine suggestions
- Automatic analysis of moves to identify mistakes and excellent plays
- PGN import/export support
- Opening recognition
- Game vs Stockfish mode
- Puzzle mode for practice
- Customizable engine settings

## Setup Development Environment

### Prerequisites

- Python 3.10 or higher
- pip package manager
- Git (for cloning the repository)

### Installation Steps

1. Clone the repository:
```sh
git clone https://github.com/yourusername/BoardMaster.git
cd BoardMaster
```

2. Install required Python packages:
```sh
pip install -r requirements.txt
```

Alternatively, you can use the setup script to create a Python virtual environment:
```sh
python setup.py
```

### Stockfish Setup

BoardMaster requires Stockfish chess engine to function. Follow these steps to set it up:

1. Download [Stockfish](https://stockfishchess.org/download/) for your operating system
2. Extract the downloaded zip file and save wherever you'd like on your system (you will be prompted to select the stockfish executable on first launch of the program)

## Running BoardMaster

1. Navigate to the project directory:
```sh
cd BoardMaster
```

1. Run the main application:
```sh
python src/BoardMaster.py
```

1. On first launch, you'll be prompted to configure the Stockfish engine path in Settings

## Configuration

- Engine settings can be adjusted in Tools > Settings
- Customize analysis depth, number of lines, engine threads, and memory allocation
- Configure game directory for PGN files

## License

This project is licensed under the GNU General Public License - see the [LICENSE](./LICENSE) file for details.

## Credits

- Chess piece icons from [IconFinder](https://www.iconfinder.com/search?q=chess+king&price=free)
- Stockfish chess engine