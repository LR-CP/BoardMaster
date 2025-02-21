import chess
import chess.pgn
import chess.engine
import chess.svg
from PySide6.QtWidgets import *
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
import sys
from interactive_board import BoardEditor
from gametab import GameTab
from dialogs import *

class BoardMaster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BoardMaster")
        self.setGeometry(100, 100, 1400, 900)
        self.setWindowIcon(QIcon("./img/king.ico"))

        self.settings = QSettings("BoardMaster", "BoardMaster")

        self.engine = self.initialize_engine()
        if not self.engine:
            return

        self.create_gui()
        self.create_menus()

    def create_gui(self):
        self.tab_widget = QTabWidget(tabsClosable=True)
        self.tab_widget.tabCloseRequested.connect(self.tab_widget.removeTab)
        self.setCentralWidget(self.tab_widget)

        pgn_dock = QDockWidget("PGN Input", self)
        pgn_widget = QWidget()
        pgn_layout = QVBoxLayout(pgn_widget)

        self.pgn_text = QTextEdit()
        load_button = QPushButton("Load Game")
        load_button.clicked.connect(self.load_game)

        pgn_layout.addWidget(self.pgn_text)
        pgn_layout.addWidget(load_button)

        pgn_dock.setWidget(pgn_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, pgn_dock)

        self.new_tab = GameTab(self)
        self.tab_widget.addTab(self.new_tab, f"Game {self.tab_widget.count() + 1}")

    def create_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        open_pgn = QAction("Open PGN File", self)
        open_pgn.setShortcut(QKeySequence("Ctrl+O"))
        open_pgn.triggered.connect(self.open_pgn_file)
        file_menu.addAction(open_pgn)

        tool_menu = menubar.addMenu("&Tools")
        interactive_board_action = QAction("Play Current Position", self)
        interactive_board_action.setShortcut(QKeySequence("Ctrl+P"))
        interactive_board_action.triggered.connect(self.open_interactive_board)
        tool_menu.addAction(interactive_board_action)
        # Add PGN Splitter action
        split_pgn_action = QAction("PGN Splitter", self)
        split_pgn_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        split_pgn_action.triggered.connect(self.show_pgn_splitter)
        tool_menu.addAction(split_pgn_action)

        settings_menu = menubar.addMenu("&Settings")
        open_settings = QAction("Engine Settings", self)
        open_settings.setShortcut(QKeySequence("Ctrl+Shift+P"))
        open_settings.triggered.connect(self.open_settings)
        settings_menu.addAction(open_settings)

        help_menu = menubar.addMenu("&Help")
        open_help = QAction("How To Use", self)
        open_help.setShortcut(QKeySequence("F1"))
        open_help.triggered.connect(self.open_help)
        help_menu.addAction(open_help)

    def initialize_engine(self):
        # List of possible Stockfish executable names
        stockfish_names = ["stockfish.exe"]

        config = {
            "Threads": self.settings.value("engine/threads", 4, int),
            "Hash": self.settings.value("engine/memory", 16, int)
        }

        # List of common installation directories
        extra_paths = [
            "C:/Program Files/stockfish/",
            "C:/Program Files (x86)/stockfish/",
            "./stockfish/",
        ]

        # Function to show error dialog
        def show_error(message):
            QMessageBox.critical(self, "Stockfish Error", message)

        for path in extra_paths:
            if os.path.exists(path):
                executable = f"{path}/stockfish.exe"
                print(executable)

        # executable = "C:/Users/LPC/Documents/Programs/ChessEngine/x64/Debug/ChessEngine.exe"

        # Try to find Stockfish in PATH and common locations
        try:
            if sys.platform == "win32":
                try:
                    engine = chess.engine.SimpleEngine.popen_uci(executable)
                    engine.configure(config)
                    return engine
                
                except FileNotFoundError:
                    pass

            error_message = (
                "Stockfish not found. Please ensure:\n\n"
                "1. Stockfish is installed\n"
                "2. The executable is named 'stockfish.exe' (Windows) or 'stockfish' (Mac/Linux)\n"
                "3. The installation directory is in your system PATH\n\n"
            )
            show_error(error_message)
            return None

        except Exception as e:
            show_error(f"Error initializing Stockfish: {str(e)}")
            return None

    def keyPressEvent(self, event):
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, GameTab):
            current_tab.keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()
    
    def show_pgn_splitter(self):
        splitter = PGNSplitterDialog(self)
        splitter.exec()

    def open_help(self):
        help_dialog = HelpDialog(self)
        help_dialog.exec()

    def open_pgn_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open PGN File", "", "PGN files (*.pgn)"
        )
        if file_name:
            with open(file_name, "r") as f:
                self.pgn_text.setText(f.read())
            self.load_game()

    def open_interactive_board(self):
        if self.new_tab:
            fen=self.new_tab.current_board.fen()
        else:
            fen = None
        self.interactive_board = BoardEditor(engine=self.engine,
                                             fen=fen,
                                             threads=self.settings.value("engine/threads", 4, int),
                                             multipv=self.settings.value("engine/lines", 3, int),
                                             mem=self.settings.value("engine/memory", 16, int),
                                             time=self.settings.value("analysis/postime", 3, int),
                                             depth=self.settings.value("engine/depth", 40, int)
                                             )
        self.interactive_board.show()

    def load_game(self):
        pgn_string = self.pgn_text.toPlainText()
        self.new_tab = GameTab(self)
        if self.new_tab.load_pgn(pgn_string):
            self.tab_widget.addTab(self.new_tab, f"Game {self.tab_widget.count() + 1}")
            self.tab_widget.setCurrentWidget(self.new_tab)

    def analyze_position(self, board):
        depth = self.settings.value("engine/depth", 20, int)
        self.engine.analyse(board, chess.engine.Limit(depth=depth))

    def closeEvent(self, event):
        if hasattr(self, "engine") and self.engine:
            self.engine.quit()
        super().closeEvent(event)
