from PySide6.QtWidgets import *
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QIcon
import os
import chess.pgn
import io


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BoardMaster Help")
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.resize(600, 400)

        layout = QVBoxLayout(self)

        # Help text explaining the program
        help_text = (
            "Welcome to BoardMaster!\n\n"
            "BoardMaster is a chess game analyzer that leverages the Stockfish engine and the python-chess "
            "library to provide move-by-move evaluations for chess games loaded in PGN format. "
            "It provides a rich graphical interface built with PySide6 for navigating through games, "
            "displaying an evaluation bar, annotated moves, and interactive board controls.\n\n"
            "Features:\n"
            "• Load games by pasting PGN text or opening a PGN file.\n"
            "• Automatic analysis of each move to assess accuracy, identify mistakes, and highlight excellent moves.\n"
            "• A dynamic evaluation bar that reflects the positional advantage based on pre-computed game analysis.\n"
            "• Move navigation controls: first, previous, next, and last move, as well as a board flip option.\n"
            "• Interactive board play for testing positions.\n"
            "• Customizable engine settings, including analysis depth and number of analysis lines.\n\n"
            "How to Use BoardMaster:\n"
            "1. Load a game by pasting PGN text into the provided input area or by opening a PGN file.\n"
            "2. Once loaded, the game is automatically analyzed, and move evaluations are computed.\n"
            "3. Use the navigation buttons to move through the game and view evaluations and annotations.\n"
            "4. The evaluation bar visually displays the advantage between White and Black.\n"
            "5. Adjust settings via the Settings menu to customize the engine analysis parameters.\n"
            "6. Use the interactive board tool to experiment with positions directly.\n\n"
            "Enjoy exploring your chess games with BoardMaster!"
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
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.settings = QSettings("BoardMaster", "BoardMaster")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Engine Settings:"))

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

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)

    def save_settings(self):
        self.settings.setValue("engine/depth", self.depth_spin.value())
        self.settings.setValue("display/show_arrows", self.show_arrows.isChecked())
        self.settings.setValue("engine/lines", self.arrows_spin.value())
        self.settings.setValue("analysis/postime", self.seconds_input.value())
        self.settings.setValue("analysis/fulltime", self.seconds_input2.value())
        self.settings.setValue("engine/threads", self.thread_spin.value())
        self.settings.setValue("engine/memory", self.memory_spin.value())
        self.parent().engine = self.parent().initialize_engine()
        self.accept()

class PGNSplitterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PGN Splitter")
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
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open PGN File", "", "PGN files (*.pgn);;All files (*.*)"
        )
        if file_name:
            with open(file_name, 'r') as f:
                self.pgn_text.setText(f.read())
    
    def split_pgn(self):
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