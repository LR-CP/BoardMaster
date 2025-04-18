import platform
import chess
import chess.pgn
import chess.engine
import chess.svg
import json
import subprocess
import datetime
from PySide6.QtWidgets import *
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from interactive_board import BoardEditor
from gametab import GameTab
from dialogs import *
from puzzleplayer import ChessPuzzleApp

class BoardMaster(QMainWindow):
    def __init__(self):
        """
        @brief Initialize the main window for BoardMaster.
        @details Sets window size, title, engine and loads the GUI.
        """
        super().__init__()
        self.setWindowTitle("BoardMaster")
        self.setGeometry(100, 100, 1700, 800)
        self.setWindowIcon(QIcon("./img/king.ico"))

        self.settings = QSettings("BoardMaster", "BoardMaster")

        self.engine = self.initialize_engine()
        if not self.engine:
            return

        global OPENINGS_LOADED_FLAG
        global OPENINGS_DB
        if OPENINGS_LOADED_FLAG is False and self.settings.value("game/load_openings", True, bool):
            # dialog = LoadingDialog()
            # dialog.show()
            QApplication.processEvents()
            load_openings()
            QApplication.processEvents()
            # dialog.accept()
            
        self.create_gui()
        self.create_menus()

    def create_gui(self):
        """
        @brief Create the main layout and widgets of the GUI.
        """
        # Create main layout
        main_layout = QHBoxLayout()
        
        # Left side with tab widget
        self.tab_widget = QTabWidget(tabsClosable=True)
        self.tab_widget.tabCloseRequested.connect(self.tab_widget.removeTab)
        self.new_tab = GameTab(self)
        self.lg_ctr = 0
        # self.tab_widget.addTab(self.new_tab, f"Live Game {self.lg_ctr}")
        main_layout.addWidget(self.tab_widget)

        # Right side with PGN input
        right_panel = QWidget()
        right_panel.setFixedWidth(300)  # Fixed width of 300px
        right_layout = QVBoxLayout(right_panel)
        
        # PGN widgets
        right_layout.addWidget(QLabel("PGN Input:"))
        self.pgn_text = QTextEdit()
        load_button = QPushButton("Load Game")
        load_button.clicked.connect(self.load_game)
        
        right_layout.addWidget(self.pgn_text)
        right_layout.addWidget(load_button)
        main_layout.addWidget(right_panel)

        # Create central widget to hold the layout
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def create_menus(self):
        """
        @brief Create the menu bar and add menu items.
        """
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        open_pgn = QAction("Open PGN File", self)
        open_pgn.setShortcut(QKeySequence("Ctrl+O"))
        open_pgn.triggered.connect(self.open_pgn_file)
        file_menu.addAction(open_pgn)
        live_game_tab = QAction("Open Live Game", self)
        live_game_tab.setShortcut(QKeySequence("Ctrl+L"))
        live_game_tab.triggered.connect(self.start_live_game)
        file_menu.addAction(live_game_tab)
        save_analysis_action = QAction("Save Analysis", self)
        save_analysis_action.setShortcut(QKeySequence("Ctrl+S"))
        save_analysis_action.triggered.connect(lambda: self.export_pgn(analysis=True))
        load_analysis_action = QAction("Load Analysis", self)
        load_analysis_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        load_analysis_action.triggered.connect(self.load_analysis)
        file_menu.addAction(save_analysis_action)
        file_menu.addAction(load_analysis_action)


        tool_menu = menubar.addMenu("&Tools")
        board_editor_action = QAction("Open Board Editor", self)
        board_editor_action.setShortcut(QKeySequence("Ctrl+B"))
        board_editor_action.triggered.connect(lambda: self.open_interactive_board(be_mode=True))
        tool_menu.addAction(board_editor_action)

        interactive_board_action = QAction("Play Current Position", self)
        interactive_board_action.setShortcut(QKeySequence("Ctrl+P"))
        interactive_board_action.triggered.connect(self.open_interactive_board)
        tool_menu.addAction(interactive_board_action)
        # Play Puzzles
        puzzle_action = QAction("Play Puzzles", self)
        puzzle_action.setShortcut(QKeySequence("Ctrl+G"))
        puzzle_action.triggered.connect(self.open_interactive_puzzle_board)
        tool_menu.addAction(puzzle_action)
        # Add PGN Splitter action
        split_pgn_action = QAction("PGN Splitter", self)
        split_pgn_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        split_pgn_action.triggered.connect(self.show_pgn_splitter)
        tool_menu.addAction(split_pgn_action)
        # Add PGN Export action
        export_pgn_action = QAction("Export PGN", self)
        export_pgn_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_pgn_action.triggered.connect(lambda: self.export_pgn(analysis=False))
        tool_menu.addAction(export_pgn_action)

        load_opening_action = QAction("Load Opening", self)
        load_opening_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        load_opening_action.triggered.connect(self.show_opening_dialog)
        tool_menu.addAction(load_opening_action)

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

        play_menu = self.menuBar().addMenu("Play")
        play_stockfish_action = play_menu.addAction("Play vs Stockfish")
        play_stockfish_action.triggered.connect(self.play_vs_stockfish)

    def initialize_engine(self):
        """
        @brief Initialize and configure the chess engine.
        @return Engine transport instance or None on failure.
        """
        try:
            engine_path = self.settings.value("engine/path", "", str)
            if not engine_path:
                # Show settings dialog if no engine path is set
                QMessageBox.information(self, "Engine Setup Required", 
                                    "No chess engine found. Please select one in Settings.")
                dialog = SettingsDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    # Try to get the newly set engine path
                    engine_path = self.settings.value("engine/path", "", str)
                    if not engine_path:
                        return None
                else:
                    return None
                    
            if platform.system() == "Windows":
                transport = chess.engine.SimpleEngine.popen_uci(engine_path, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                transport = chess.engine.SimpleEngine.popen_uci(engine_path)
            # Configure engine settings
            transport.configure({
                "Threads": self.settings.value("engine/threads", 4, int),
                "Hash": self.settings.value("engine/memory", 16, int)
            })
            return transport
        except Exception as e:
            QMessageBox.critical(self, "Engine Error", 
                            f"Failed to initialize engine: {str(e)}")
            return None

    def keyPressEvent(self, event):
        """
        @brief Handle key press events.
        @param event The key press event.
        """
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, GameTab):
            current_tab.keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def open_settings(self):
        """
        @brief Open the engine settings dialog.
        """
        dialog = SettingsDialog(self)
        dialog.exec()
    
    def show_pgn_splitter(self):
        """
        @brief Open the PGN splitter dialog.
        """
        splitter = PGNSplitterDialog(self)
        splitter.exec()

    def show_opening_dialog(self):
        """Show the opening search dialog."""
        new_tab = GameTab(self)
        dialog = OpeningSearchDialog(game_tab=new_tab)
        # opening = dialog.load_selected_opening()
        if dialog.exec_() == QDialog.Accepted:
            self.load_opening(dialog.selected_opening)
            # Opening was loaded in the dialog's load_selected_opening method
            pass
    
    def load_opening(self, opening_data):
        """
        Load an opening position by converting the provided pgn_text into a complete PGN
        (with headers) and then loading it using load_pgn.
        
        Args:
            opening_data (dict): Opening data from the Lichess dataset.
        """
        # Reset the game state.
        # self.reset_game()
        
        # Set up custom headers.
        self.hdrs = {
            "Event": "Opening Study",
            "Site": "Chess Analysis App",
            "Date": "????.??.??",
            "Round": "?",
            "White": "?",
            "Black": "?"
        }
        if "eco" in opening_data:
            self.hdrs["ECO"] = opening_data["eco"]
        if "name" in opening_data:
            self.hdrs["Opening"] = opening_data["name"]
        
        # Get the PGN text from the opening data.
        pgn_text = opening_data.get("pgn", "")
        if not pgn_text:
            print("No PGN data provided in the opening.")
            return
        
        # Create a new PGN game and add headers.
        game = chess.pgn.Game()
        for key, value in self.hdrs.items():
            game.headers[key] = value

        # Parse the moves from the provided PGN text.
        pgn_io = io.StringIO(pgn_text)
        parsed_game = chess.pgn.read_game(pgn_io)
        if parsed_game is None:
            print("Failed to parse PGN moves from provided text.")
            return

        # Add the moves from the parsed game into our new game.
        node = game
        for move in parsed_game.mainline_moves():
            node = node.add_main_variation(move)

        # Convert the game to a full PGN string.
        full_pgn = str(game)
        print("Constructed PGN:\n", full_pgn)

        # Now load the PGN using your load_pgn method.
        
        self.pgn_text.setText(full_pgn)
        self.load_game(self.hdrs["Opening"])

        # Update the window title if applicable.
        # if hasattr(self, 'parent') and hasattr(self.parent(), 'setWindowTitle'):
        #     self.parent().setWindowTitle(f"Opening Study: {opening_data.get('name', 'Unknown')}")
    
    def export_pgn(self, analysis=False):
        """
        @brief Export the current game to a PGN file.
        """
        pgn_str, fname = self.new_tab.export_pgn()

        if analysis is False:
            file_name, _ = QFileDialog.getSaveFileName(
                self, "Save PGN File", fname, filter="*.pgn"
            )
            if file_name:
                with open(file_name, "w") as f:
                    f.write(pgn_str)

        if analysis is True:
            opening = self.new_tab.opening_label.text()
            analysis_data = {
                "pgn": pgn_str,
                "moves": [move.uci() for move in self.new_tab.moves],
                "move_evaluations": self.new_tab.move_evaluations,
                "move_evaluations_scores": self.new_tab.move_evaluations_scores,
                "white_accuracy": self.new_tab.white_accuracy,
                "black_accuracy": self.new_tab.black_accuracy,
                "move_notes": self.new_tab.move_notes,
                "opening_name": opening,
                # "opening_eco": self.new_tab.opening_eco,
            }

            file_name, _ = QFileDialog.getSaveFileName(
                self, "Save JSON File", fname.replace(".pgn", ".json"), "JSON files (*.json)"
            )
            if file_name:
                with open(file_name, "w", encoding="utf-8") as f:
                    json.dump(analysis_data, f, indent=2)

                QMessageBox.information(self, "Analysis Saved", f"Analysis saved to:\n{file_name}")
    
    def load_analysis(self):
        """
        Load the analysis from a file and restore game state.
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Analysis", self.settings.value("game_analysis_dir", "", str), "Analysis Files (*.json)")
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                analysis_data = json.load(f)
            
            self.new_tab = GameTab(self)
            curr_tab_index = self.tab_widget.addTab(self.new_tab, f"{os.path.basename(file_path)}")
            self.tab_widget.setCurrentIndex(curr_tab_index)
            
            pgn_string = analysis_data.get("pgn", "")
            if not self.new_tab.load_pgn(pgn_string, is_analysis=True):
                QMessageBox.critical(self, "Load Failed", "Failed to load the game from the analysis file.")
                return

            self.new_tab.move_evaluations = analysis_data.get("move_evaluations", [])
            self.new_tab.move_evaluations_scores = analysis_data.get("move_evaluations_scores", [])
            self.new_tab.white_accuracy = analysis_data.get("white_accuracy", 0)
            self.new_tab.black_accuracy = analysis_data.get("black_accuracy", 0)
            self.new_tab.move_notes = analysis_data.get("move_notes", {})
            self.new_tab.opening_label.setText(f"Opening: {analysis_data.get('opening_name', {})} {analysis_data.get('opening_eco', {})}")
            self.new_tab.has_been_analyzed = True
            self.new_tab.update_display()
            self.new_tab.update_game_summary()
            QMessageBox.information(self, "Analysis Loaded", "Analysis loaded successfully.")

    def open_help(self):
        """
        @brief Open the help dialog.
        """
        help_dialog = HelpDialog(self)
        help_dialog.exec()

    def open_pgn_file(self):
        """
        @brief Open a PGN file and load its content.
        """
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open PGN File", self.settings.value("game_dir", "", str), "PGN files (*.pgn)"
        )
        if file_name:
            with open(file_name, "r") as f:
                self.pgn_text.setText(f.read())
            self.load_game()
    
    def start_live_game(self):
        self.lg_ctr += 1
        self.new_tab = GameTab(self)
        self.new_tab.is_live_game = True
        self.new_tab.hdrs = chess.pgn.Headers()
        self.new_tab.game_details.setText(f"White: Player 1(?)\nBlack: Player 2(?)\n{datetime.date.today()}\nResult: In Progress\n\n")
#         White: {self.hdrs.get('White')}({self.hdrs.get('WhiteElo')})
        # Black: {self.hdrs.get('Black')}({self.hdrs.get('BlackElo')})
        # {self.hdrs.get('Date')}\nResult: {self.hdrs.get('Termination')}
        self.new_tab.hdrs["White"] = "Player 1"
        self.new_tab.hdrs["WhiteElo"] = "?"
        self.new_tab.hdrs["Black"] = "Player 2"
        self.new_tab.hdrs["BlackElo"] = "?"
        self.new_tab.hdrs["Date"] = datetime.date.today()
        self.new_tab.hdrs["Termination"] = ""
        self.tab_widget.addTab(self.new_tab, f"Live Game {self.lg_ctr}")

    def open_interactive_board(self, be_mode):
        """
        @brief Open the interactive board with current position.
        """
        if self.new_tab and not be_mode:
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

    def open_interactive_puzzle_board(self):
        """
        @brief Open the interactive board for puzzles.
        """
        self.interactive_board = ChessPuzzleApp()
        self.interactive_board.show()

    def load_game(self, opening=None):
        """
        @brief Load a game from the PGN text input.
        """
        pgn_string = self.pgn_text.toPlainText()
        self.new_tab = GameTab(self)
        if opening is None and self.new_tab.load_pgn(pgn_string):
            self.tab_widget.addTab(self.new_tab, f"{self.new_tab.hdrs.get('White')}_{self.new_tab.hdrs.get('Black')}_{self.new_tab.hdrs.get('Date').replace('.', '_')}")
            self.tab_widget.setCurrentWidget(self.new_tab)
        elif opening is not None and self.new_tab.load_pgn(pgn_string):
            self.tab_widget.addTab(self.new_tab, f"{opening}_Review")
            self.tab_widget.setCurrentWidget(self.new_tab)

    def analyze_position(self, board):
        """
        @brief Analyze a given board position.
        @param board The chess board to analyze.
        """
        depth = self.settings.value("engine/depth", 20, int)
        self.engine.analyse(board, chess.engine.Limit(depth=depth))

    def closeEvent(self, event):
        """
        @brief Cleanup when closing the application.
        @param event The close event.
        """
        if hasattr(self, "engine") and self.engine:
            self.engine.quit()
            print("Engine stopped.")
        super().closeEvent(event)

    def play_vs_stockfish(self):
        """
        @brief Start a game against Stockfish.
        """
        dialog = PlayStockfishDialog(self)
        if dialog.exec() == QDialog.Accepted:
            color, elo = dialog.get_settings()
            # Create new game tab
            new_tab = GameTab(self)
            self.tab_widget.addTab(new_tab, "vs Stockfish")
            self.tab_widget.setCurrentWidget(new_tab)
            # Start the game
            new_tab.start_game_vs_computer(color, elo)
