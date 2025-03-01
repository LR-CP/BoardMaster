from PySide6.QtWidgets import *
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QIcon, QPalette, QColor
import os
import chess.pgn
import io


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        """
        @brief Construct a help dialog for BoardMaster.
        @param parent Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("BoardMaster Help")
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.resize(600, 700)

        layout = QVBoxLayout(self)

        # Help text explaining the program
        help_text = (
            "Welcome to BoardMaster!\n\n"
            "BoardMaster is a chess game analyzer that leverages the Stockfish engine and the python-chess "
            "library to provide move-by-move evaluations for chess games loaded in PGN format. "
            "It provides a rich graphical interface built with PySide6 for navigating through games, "
            "displaying an evaluation bar, annotated moves, and interactive board controls.\n\n"
            "Features:\n"
            "• Load games by pasting PGN text or opening a PGN file\n"
            "• Split large PGN files containing multiple games into individual files\n"
            "• Automatic analysis of each move to assess accuracy, identify mistakes, and highlight excellent moves\n"
            "• A dynamic evaluation bar that reflects the positional advantage based on pre-computed game analysis\n"
            "• Move navigation controls: first, previous, next, and last move, as well as a board flip option\n"
            "• Interactive board play for testing positions\n"
            "• Customizable engine settings including:\n"
            "  - Analysis depth\n"
            "  - Number of analysis lines/arrows\n"
            "  - Engine threads\n"
            "  - Memory allocation\n"
            "  - Analysis time per position\n"
            "  - Analysis time for full games\n"
            "• Configurable game directory for organizing PGN files\n"
            "• Visual arrow indicators showing engine suggestions\n\n"
            "How to Use BoardMaster:\n"
            "1. Configure your chess engine (e.g. Stockfish) in Settings\n"
            "2. Load a game by pasting PGN or opening a PGN file\n"
            "3. Use the PGN Splitter to split large collections into individual game files\n"
            "4. The game will be automatically analyzed with your configured settings\n"
            "5. Navigate moves using the control buttons or arrow keys\n"
            "6. View engine evaluations, arrows, and move annotations\n"
            "7. Adjust analysis parameters in Settings to balance speed and accuracy\n"
            "8. Use the board flip button to view the position from either side\n\n"
            "All settings are automatically saved between sessions. Enjoy analyzing your chess games with BoardMaster!"
        )

        # Using QTextBrowser to allow for rich text or scrolling
        text_browser = QTextBrowser(self)
        text_browser.setPlainText(help_text)
        text_browser.setReadOnly(True)
        layout.addWidget(text_browser)

        # Add an OK button to close the dialog
        button_box = QDialogButtonBox(QDialogButtonBox.Ok, self)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        """
        @brief Initialize the settings dialog.
        @param parent Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(600, 400)
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.settings = QSettings("BoardMaster", "BoardMaster")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Engine Settings:"))

        engine_layout = QHBoxLayout()
        self.engine_path = QLineEdit()
        self.engine_path.setText(self.settings.value("engine/path", "", str))
        self.engine_path.setPlaceholderText("Path to engine executable (e.g. Stockfish)")
        engine_browse = QPushButton("Browse")
        engine_browse.clicked.connect(self.browse_engine)
        engine_layout.addWidget(self.engine_path)
        engine_layout.addWidget(engine_browse)
        layout.addLayout(engine_layout)

        games_dir_layout = QHBoxLayout()
        self.games_dir = QLineEdit()
        self.games_dir.setText(self.settings.value("game_dir", "", str))
        self.games_dir.setPlaceholderText("Path to game directory")
        games_dir_browse = QPushButton("Browse")
        games_dir_browse.clicked.connect(self.browse_game_dir)
        games_dir_layout.addWidget(self.games_dir)
        games_dir_layout.addWidget(games_dir_browse)
        layout.addLayout(games_dir_layout)

        game_analysis_layout = QHBoxLayout()
        self.game_analysis = QLineEdit()
        self.game_analysis.setText(self.settings.value("game_analysis_dir", "", str))
        self.game_analysis.setPlaceholderText("Path to analysis directory")
        game_analysis_browse = QPushButton("Browse")
        game_analysis_browse.clicked.connect(self.browse_analysis_dir)
        game_analysis_layout.addWidget(self.game_analysis)
        game_analysis_layout.addWidget(game_analysis_browse)
        layout.addLayout(game_analysis_layout)

        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, os.cpu_count())
        self.thread_spin.setValue(self.settings.value("engine/threads", 4, int))
        layout.addWidget(QLabel("Threads:"))
        layout.addWidget(self.thread_spin)

        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(1, 8192)
        self.memory_spin.setSingleStep(16)
        self.memory_spin.setValue(self.settings.value("engine/memory", 16, int))
        layout.addWidget(QLabel("Memory:"))
        layout.addWidget(self.memory_spin)

        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 100)
        self.depth_spin.setValue(self.settings.value("engine/depth", 20, int))
        layout.addWidget(QLabel("Analysis Depth:"))
        layout.addWidget(self.depth_spin)

        self.arrows_spin = QSpinBox()
        self.arrows_spin.setRange(1, 10)
        self.arrows_spin.setValue(self.settings.value("engine/lines", 3, int))
        layout.addWidget(QLabel("Number of Lines:"))
        layout.addWidget(self.arrows_spin)

        self.seconds_input = QDoubleSpinBox()
        self.seconds_input.setRange(0, 5)
        self.seconds_input.setSingleStep(0.1)
        self.seconds_input.setValue(self.settings.value("analysis/postime", 0.1, float))
        layout.addWidget(QLabel("Time for single position analysis (seconds):"))
        layout.addWidget(self.seconds_input)

        self.seconds_input2 = QDoubleSpinBox()
        self.seconds_input2.setRange(0, 5)
        self.seconds_input2.setSingleStep(0.1)
        self.seconds_input2.setValue(
            self.settings.value("analysis/fulltime", 0.1, float)
        )
        layout.addWidget(QLabel("Time for full game analysis (seconds):"))
        layout.addWidget(self.seconds_input2)

        self.show_arrows = QCheckBox("Show Analysis Arrows")
        self.show_arrows.setChecked(
            self.settings.value("display/show_arrows", True, bool)
        )
        layout.addWidget(self.show_arrows)

        self.arrow_move_toggle = QCheckBox("Show arrows for move ahead")
        self.arrow_move_toggle.setChecked(
            self.settings.value("display/arrow_move", True, bool)
        )
        layout.addWidget(self.arrow_move_toggle)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)

    def browse_engine(self):
        """
        @brief Open a file dialog to select a chess engine executable.
        """
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Select Chess Engine",
            "",
            "Executable files (*.exe);;All files (*.*)"
        )
        if file_name:
            self.engine_path.setText(file_name)
    
    def browse_game_dir(self):
        """
        @brief Open a directory chooser to select the game folder.
        """
        file_name = QFileDialog.getExistingDirectory(
            self,
            "Select Game Folder",
            ""
        )
        if file_name:
            self.games_dir.setText(file_name)
        
    def browse_analysis_dir(self):
        """
        @brief Open a directory chooser to select the game folder.
        """
        file_name = QFileDialog.getExistingDirectory(
            self,
            "Select Analysis Folder",
            ""
        )
        if file_name:
            self.game_analysis.setText(file_name)
    
    def save_settings(self):
        """
        @brief Save all settings to persistent storage.
        """
        self.settings.setValue("engine/depth", self.depth_spin.value())
        self.settings.setValue("display/show_arrows", self.show_arrows.isChecked())
        self.settings.setValue("display/arrow_move", self.arrow_move_toggle.isChecked())
        self.settings.setValue("engine/lines", self.arrows_spin.value())
        self.settings.setValue("analysis/postime", self.seconds_input.value())
        self.settings.setValue("analysis/fulltime", self.seconds_input2.value())
        self.settings.setValue("engine/threads", self.thread_spin.value())
        self.settings.setValue("engine/memory", self.memory_spin.value())
        self.settings.setValue("engine/path", self.engine_path.text())
        self.settings.setValue("game_dir", self.games_dir.text())
        self.settings.setValue("game_analysis_dir", self.game_analysis.text())
        self.parent().engine = self.parent().initialize_engine()
        self.accept()

class PGNSplitterDialog(QDialog):
    def __init__(self, parent=None):
        """
        @brief Initialize the PGN splitter dialog.
        @param parent Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("PGN Splitter")
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel(
            "Either paste PGN text directly or load from a file.\n"
            "Games will be split into individual PGN files."
        )
        layout.addWidget(instructions)
        
        # Text area for PGN input
        self.pgn_text = QTextEdit()
        self.pgn_text.setPlaceholderText("Paste PGN here...")
        layout.addWidget(self.pgn_text)
        
        # Buttons
        btn_layout = QVBoxLayout()
        self.load_btn = QPushButton("Load PGN File")
        self.load_btn.clicked.connect(self.load_pgn_file)
        btn_layout.addWidget(self.load_btn)
        
        self.split_btn = QPushButton("Split and Save")
        self.split_btn.clicked.connect(self.split_pgn)
        btn_layout.addWidget(self.split_btn)
        
        layout.addLayout(btn_layout)
    
    def load_pgn_file(self):
        """
        @brief Load PGN text from a file into the dialog.
        """
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open PGN File", "", "PGN files (*.pgn);;All files (*.*)"
        )
        if file_name:
            with open(file_name, 'r') as f:
                self.pgn_text.setText(f.read())
    
    def split_pgn(self):
        """
        @brief Split the loaded PGN text into individual games and save them.
        """
        pgn_content = self.pgn_text.toPlainText()
        if not pgn_content.strip():
            return
            
        # Get output directory
        output_dir = QFileDialog.getExistingDirectory(
            self, "Select Output Directory"
        )
        if not output_dir:
            return
            
        # Create a progress dialog
        progress = QProgressDialog(
            "Splitting PGN files...", "Cancel", 0, 100, self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            # Read games from the PGN text
            pgn_io = io.StringIO(pgn_content)
            game_count = 0
            while True:
                game = chess.pgn.read_game(pgn_io)
                if game is None:
                    break
                    
                # Generate filename from game metadata
                white = game.headers.get("White", "Unknown")
                black = game.headers.get("Black", "Unknown")
                date = game.headers.get("Date", "Unknown").replace(".", "-")
                fname = f"{white}_vs_{black}_{date}_{game_count}.pgn"
                fname = "".join(c for c in fname if c.isalnum() or c in "._- ")
                
                # Save individual game
                with open(os.path.join(output_dir, fname), 'w') as f:
                    f.write(str(game))
                
                game_count += 1
                progress.setValue(int((game_count % 100) * (100/100)))
                
            progress.setValue(100)
            self.pgn_text.clear()
            self.pgn_text.setPlaceholderText(
                f"Successfully split {game_count} games into {output_dir}"
            )
            
        except Exception as e:
            progress.cancel()
            self.pgn_text.setPlaceholderText(f"Error splitting PGN: {str(e)}")

class PlayStockfishDialog(QDialog):
    def __init__(self, parent=None):
        """
        @brief Dialog for setting up a game against Stockfish.
        @param parent Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Play Against Stockfish")
        self.setWindowIcon(QIcon("./img/king.ico"))
        
        layout = QVBoxLayout(self)
        
        # Color selection
        color_group = QGroupBox("Play as")
        color_layout = QHBoxLayout()
        self.white_radio = QRadioButton("White")
        self.black_radio = QRadioButton("Black")
        self.random_radio = QRadioButton("Random")
        self.white_radio.setChecked(True)
        color_layout.addWidget(self.white_radio)
        color_layout.addWidget(self.black_radio)
        color_layout.addWidget(self.random_radio)
        color_group.setLayout(color_layout)
        layout.addWidget(color_group)
        
        # ELO selection
        elo_layout = QHBoxLayout()
        elo_layout.addWidget(QLabel("Stockfish ELO:"))
        self.elo_combo = QComboBox()
        elos = ["800", "1000", "1200", "1400", "1600", "1800", "2000", "2200", "2400", "2600"]
        self.elo_combo.addItems(elos)
        self.elo_combo.setCurrentText("1400")  # Default ELO
        elo_layout.addWidget(self.elo_combo)
        layout.addLayout(elo_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        """
        @brief Get the selected game settings.
        @return Tuple of (color, elo) where color is 'white', 'black', or 'random'.
        """
        if self.white_radio.isChecked():
            color = 'white'
        elif self.black_radio.isChecked():
            color = 'black'
        else:
            color = 'random'
            
        return color, int(self.elo_combo.currentText())
    
class NoteDialog(QDialog):
    """Dialog for adding/editing move notes."""
    def __init__(self, current_note="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Move Note")
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.setModal(True)
        self.setStyleSheet("""
            NoteDialog {
                background-color: #f5f5dc;  /* Soft beige background */
            }
            QLabel, QPushButton {
                color: #555555;  /* Dark grey text for labels and buttons */
            }
            QTextEdit {
                background-color: #fdfdfd;  /* Very light grey (almost white) */
                color: #333333;  /* Darker text for readability */
                border: 1px solid #cccccc;  /* Soft border */
            }
            QPushButton {
                background-color: #e0e0e0;  /* Light grey buttons */
                border: 1px solid #bbbbbb;  /* Subtle border */
                padding: 6px;
                border-radius: 4px;  /* Slightly rounded buttons */
            }
            QPushButton:hover {
                background-color: #d6d6d6;  /* Slightly darker on hover */
            }
            QPushButton:pressed {
                background-color: #c0c0c0;  /* Even darker when pressed */
            }
        """)



        layout = QVBoxLayout(self)
        
        # Text edit for the note
        self.note_edit = QTextEdit()
        self.note_edit.setText(current_note)
        layout.addWidget(self.note_edit)

        # White blinking cursor
        # palette = self.note_edit.palette()
        # palette.setColor(QPalette.Text, QColor('white'))
        # palette.setColor(QPalette.HighlightedText, QColor('white'))
        # self.note_edit.setPalette(palette)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        
        self.setMinimumWidth(300)
        self.setMinimumHeight(200)

    def get_note(self):
        """Return the current note text."""
        return self.note_edit.toPlainText()

class LoadingDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Loading Openings Database...")
        self.setWindowIcon(QIcon("./img/king.ico"))
        layout = QVBoxLayout()
        self.label = QLabel("Please wait while the openings database is loaded...")
        layout.addWidget(self.label)
        self.setLayout(layout)
        self.setModal(True)  # This blocks interaction with other windows if needed
        self.setFixedSize(300, 100)