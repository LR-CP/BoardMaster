"""
Chess Game Analyzer
Requires: python-chess, PySide6, Stockfish engine installed
Save as chess_analyzer.py and run with: python chess_analyzer.py
"""

import chess
import chess.pgn
import chess.engine
import chess.svg
import io
from PySide6.QtWidgets import *
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QIcon, QScreen
import sys
from pathlib import Path
import os
from interactive_board import ChessGUI, ChessBoard
from math import exp

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
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 30)
        self.depth_spin.setValue(self.settings.value("engine/depth", 20, int))
        layout.addWidget(QLabel("Analysis Depth:"))
        layout.addWidget(self.depth_spin)

        self.arrows_spin = QSpinBox()
        self.arrows_spin.setRange(1, 10)
        self.arrows_spin.setValue(self.settings.value("engine/lines", 3, int))
        layout.addWidget(QLabel("Number of Lines:"))
        layout.addWidget(self.arrows_spin)

        self.seconds_input = QDoubleSpinBox()
        self.seconds_input.setRange(0,5)
        self.seconds_input.setSingleStep(0.1)
        self.seconds_input.setValue(self.settings.value("analysis/postime", 0.1, float))
        layout.addWidget(QLabel("Time for single position analysis (seconds):"))
        layout.addWidget(self.seconds_input)

        self.seconds_input2 = QDoubleSpinBox()
        self.seconds_input2.setRange(0,5)
        self.seconds_input2.setSingleStep(0.1)
        self.seconds_input2.setValue(self.settings.value("analysis/fulltime", 0.1, float))
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
        self.accept()

class GameTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = parent.engine
        self.settings = QSettings("BoardMaster", "BoardMaster")
        self.current_game = None
        self.current_board = chess.Board()
        self.moves = []
        self.played_moves = []  # Track actual moves played
        self.current_move_index = 0
        self.move_evaluations = []
        self.selected_square = None
        self.legal_moves = set()
        self.square_size = 70
        self.flipped = False
        
        self.create_gui()

    def create_gui(self):
        layout = QHBoxLayout(self)

        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        self.game_details = QLabel()
        left_layout.addWidget(self.game_details)

        board_layout = QHBoxLayout()
        self.win_bar = QLabel()
        self.win_bar.setFixedSize(20, 600)
        self.board_display = QSvgWidget()
        self.board_display.setFixedSize(600, 600)
        board_layout.addWidget(self.win_bar)
        board_layout.addWidget(self.board_display)
        left_layout.addLayout(board_layout)

        nav_layout = QHBoxLayout()
        for text, func in [
            ("<<", self.first_move),
            ("<", self.prev_move),
            (">", self.next_move),
            (">>", self.last_move),
            ("↻", self.board_flip),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            nav_layout.addWidget(btn)
        left_layout.addLayout(nav_layout)

        self.fen_box = QLineEdit("FEN: ")
        self.fen_box.setReadOnly(True)
        left_layout.addWidget(self.fen_box)

        self.summary_label = QLabel()
        left_layout.addWidget(self.summary_label)

        # Right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        right_layout.addWidget(QLabel("Move List:"))
        self.move_list = QListWidget()
        self.move_list.itemClicked.connect(self.move_selected)
        right_layout.addWidget(self.move_list)

        right_layout.addWidget(QLabel("Analysis:"))
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        right_layout.addWidget(self.analysis_text)

        layout.addWidget(left_panel)
        layout.addWidget(right_panel)
        self.update_display()

        # Connect mouse events
        self.board_display.mousePressEvent = self.mousePressEvent
    
    def show_loading(self, title="Loading...", text="Analyzing game...", max=0):
        self.progress = QProgressDialog(labelText=text, cancelButtonText=None, minimum=0, maximum=max, parent=self)
        self.progress.setWindowTitle(title)
        self.progress.setWindowModality(Qt.WindowModality.NonModal)
        self.progress.setMinimumDuration(0)
        self.progress.setCancelButton(None)
        self.progress.setWindowFlags(
            Qt.WindowType.Dialog | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint  # Keeps dialog on top while allowing window movement
        )
        self.progress.setValue(1)
        return self.progress

    def load_pgn(self, pgn_string):
        try:
            hdrs_io = io.StringIO(pgn_string)
            hdrs = chess.pgn.read_headers(hdrs_io)
            self.game_details.setText(f"White: {hdrs.get("White")}({hdrs.get("WhiteElo")})\nBlack: {hdrs.get("Black")}({hdrs.get("BlackElo")})\n{hdrs.get("Date")}\nResult: {hdrs.get("Termination")}\n\n\nOpening: {hdrs.get("Opening")}")
        except Exception as e:
            print(f"Error loading game: {str(e)}")
            return False
        try:
            pgn_io = io.StringIO(pgn_string)
            self.current_game = chess.pgn.read_game(pgn_io)
            if not self.current_game:
                return False

            self.moves = list(self.current_game.mainline_moves())
            total_moves = len(self.moves)
            self.loading_bar = self.show_loading(max=total_moves)
            self.progress.setMaximum(total_moves)
            self.current_board = self.current_game.board()
            self.current_move_index = 0
            self.analyze_all_moves()
            self.update_display()
            self.update_game_summary()
            self.loading_bar.close()
            return True
        except Exception as e:
            print(f"Error loading game: {str(e)}")
            return False

    def analyze_all_moves(self):
        temp_board = chess.Board()
        self.move_evaluations = []
        self.accuracies = {'white': [], 'black': []}
        self.move_evaluations_scores = []

        def eval_to_cp(eval_score):
            """Convert evaluation to centipawns, handles Mate cases."""
            if eval_score.is_mate():
                if eval_score.mate() > 0:
                    return 10000
                else:
                    return -10000
            return eval_score.score()

        def calculate_accuracy(eval_diff):
            """Lichess-like accuracy formula based on centipawn loss."""
            # Accuracy curve using a smoother evaluation difference scaling.
            return max(0, 100 * (1 - (eval_diff / 500)**0.6))

        for i, move in enumerate(self.moves):
            if temp_board.is_game_over():
                break

            # Get top moves evaluation (MultiPV)
            analysis = self.engine.analyse(
                temp_board,
                chess.engine.Limit(time=self.settings.value("analysis/fulltime", 0.1, int)),  # Longer time for accurate evaluation
                multipv=3  # Analyze top 3 moves
            )

            # Extract the best move evaluation
            best_eval = eval_to_cp(analysis[0]["score"].relative)

            self.move_evaluations_scores.append(best_eval)

            # Extract evaluation for the played move
            played_eval = None
            for pv in analysis:
                if pv["pv"] and pv["pv"][0] == move:
                    played_eval = eval_to_cp(pv["score"].relative)
                    break

            if played_eval is None:
                # If played move is not in top 3, evaluate the board after the move
                temp_board.push(move)
                played_eval_info = self.engine.analyse(temp_board, chess.engine.Limit(time=self.settings.value("analysis/fulltime", 0.1, int)))
                played_eval = eval_to_cp(played_eval_info["score"].relative)
                temp_board.pop()

            # Make the actual move
            temp_board.push(move)

            # Calculate evaluation difference (centipawn loss)
            eval_diff = abs(best_eval - played_eval)

            # Calculate accuracy (higher difference means lower accuracy)
            accuracy = calculate_accuracy(eval_diff)

            # Store accuracy
            if i % 2 == 0:  # White's move
                self.accuracies['white'].append(accuracy)
            else:  # Black's move
                self.accuracies['black'].append(accuracy)

            # Annotate move based on eval difference
            evaluation = ""
            if eval_diff < 20:
                evaluation = "✅"  # Excellent / Best move
            elif eval_diff < 50:
                evaluation = "👍"  # Good move
            elif eval_diff < 150:
                evaluation = "⚠️"  # Inaccuracy
            elif eval_diff < 400:
                evaluation = "❌"  # Mistake
            else:
                evaluation = "🔥"  # Blunder

            self.move_evaluations.append(evaluation)

            # Update progress bar
            self.progress.setValue(i + 1)
            QApplication.processEvents()

        # Final accuracy scores
        self.white_accuracy = round(sum(self.accuracies['white']) / len(self.accuracies['white']), 2) if self.accuracies['white'] else 0
        self.black_accuracy = round(sum(self.accuracies['black']) / len(self.accuracies['black']), 2) if self.accuracies['black'] else 0

    def update_game_summary(self):
        white_excellent = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "✅" and i % 2 == 0
        )
        white_good = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "👍" and i % 2 == 0
        )
        white_inacc = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "⚠️" and i % 2 == 0
        )
        white_mistake = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "❌" and i % 2 == 0
        )
        white_blunder = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "🔥" and i % 2 == 0
        )

        black_excellent = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "✅" and i % 2 == 0
        )
        black_good = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "👍" and i % 2 == 0
        )
        black_inacc = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "⚠️" and i % 2 == 0
        )
        black_mistake = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "❌" and i % 2 == 0
        )
        black_blunder = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "🔥" and i % 2 == 0
        )

        summary = f"""Game Summary:
White (Accuracy: {self.white_accuracy}): Excellent: {white_excellent}✅, Good: {white_good}👍, Inaccuracy: {white_inacc}⚠️, Mistake: {white_mistake}❌, Blunder: {white_blunder}🔥
Black (Accuracy: {self.black_accuracy}): Excellent: {black_excellent}✅, Good: {black_good}👍, Inaccuracy: {black_inacc}⚠️, Mistake: {black_mistake}❌, Blunder: {black_blunder}🔥"""
        self.summary_label.setText(summary)

    def update_display(self):
        arrows = []
        annotations = {}
        eval_score = 0

        if not self.current_board.is_game_over() and self.settings.value(
            "display/show_arrows", True, bool
        ):
            info = self.engine.analyse(
                self.current_board,
                chess.engine.Limit(time=self.settings.value("analysis/postime", 0.1, float)),
                multipv=self.settings.value("engine/lines", 3, int),
            )

            for i, pv in enumerate(info):
                move = pv["pv"][0]
                score = pv["score"].white().score() if pv["score"].white().score() is not None else 0
                eval_score = score

                color = "#00ff00" if i == 0 else "#007000" if i == 1 else "#003000"
                arrows.append(chess.svg.Arrow(tail=move.from_square, head=move.to_square, color=color))
                annotations[move.to_square] = f"{score / 100.0:.2f}"

        if self.current_move_index > 0 and self.moves:
            eval_score = self.move_evaluations_scores[self.current_move_index - 1]
            last_move = self.moves[self.current_move_index - 1]
            arrows.append(chess.svg.Arrow(tail=last_move.from_square, head=last_move.to_square, color="#674ea7"))

        squares = {}
        if self.selected_square is not None:
            squares[self.selected_square] = "#ffff00"
            for move in self.legal_moves:
                squares[move.to_square] = "#00ff00"

        # Generate the base SVG board
        board_svg = chess.svg.board(
            self.current_board,
            arrows=arrows,
            squares=squares,
            size=600,
            orientation=chess.BLACK if getattr(self, 'board_orientation', False) else chess.WHITE,
        )

        # Inject evaluation symbol onto the last move's square
        if self.current_move_index > 0 and self.moves:
            last_move = self.moves[self.current_move_index - 1]
            last_to_square = last_move.to_square

            evaluation_symbol = self.move_evaluations[self.current_move_index - 1] if self.current_move_index - 1 < len(self.move_evaluations) else ""

            if evaluation_symbol:
                # Calculate the position of the square
                file_index = chess.square_file(last_to_square)
                rank_index = chess.square_rank(last_to_square)
                square_size = self.square_size
                x = file_index * square_size
                y = (7 - rank_index) * square_size

                # Optional: Color based on evaluation symbol (you can customize this)
                if evaluation_symbol == "✅":
                    symbol_color = "green"
                elif evaluation_symbol == "👍":
                    symbol_color = "blue"
                elif evaluation_symbol == "⚠️":
                    symbol_color = "orange"
                elif evaluation_symbol == "❌":
                    symbol_color = "red"
                elif evaluation_symbol == "🔥":
                    symbol_color = "purple"
                else:
                    symbol_color = "black"

                # Inject custom SVG text in the **top-left corner of the square**
                symbol_svg = f'''
                    <text x="{0}" y="{18}" font-size="20" font-family="Arial"
                        font-weight="bold" fill="{symbol_color}">
                        {evaluation_symbol}
                    </text>
                '''

                # Insert symbol SVG into the existing SVG just before </svg>
                board_svg = board_svg.replace("</svg>", symbol_svg + "</svg>")

        self.board_display.load(QByteArray(board_svg.encode("utf-8")))

        white_percentage = max(0, min(100, 50 + eval_score / 2))
        self.win_bar.setStyleSheet(
            f"background: qlineargradient(y1:0, y2:1, stop:0 white, stop:{white_percentage/100} white, "
            f"stop:{white_percentage/100} black, stop:1 black);"
        )

        # Move list updates
        self.move_list.clear()
        temp_board = chess.Board()
        for i, move in enumerate(self.moves):
            move_san = temp_board.san(move)
            evaluation = self.move_evaluations[i] if i < len(self.move_evaluations) else ""
            self.move_list.addItem(f"{(i // 2) + 1}. {move_san} {evaluation}")
            temp_board.push(move)

        self.fen_box.setText(f"FEN: {self.current_board.fen()}")

        self.move_list.setCurrentRow(self.current_move_index - 1)

        # self.analyze_position() # Remove this for pre analysis (keep for move based analysis)

    def analyze_position(self):
        if not self.current_board.is_game_over():
            info = self.engine.analyse(
                self.current_board, chess.engine.Limit(time=self.settings.value("analysis/postime", 0.1, float)), multipv=self.settings.value("engine/lines", 3, int)
            )

            analysis_text = f"Move {(self.current_move_index + 1) // 2} "
            analysis_text += (
                f"({'White' if self.current_move_index % 2 == 0 else 'Black'})\n\n"
            )

            analysis_text += "Top moves:\n"
            for i, pv in enumerate(info, 1):
                move = pv["pv"][0]
                score = (
                    pv["score"].white().score() / 100.0
                    if pv["score"].white().score() is not None
                    else 0
                )
                analysis_text += (
                    f"{i}. {self.current_board.san(move)} (eval: {score:+.2f})\n"
                )

            self.analysis_text.setText(analysis_text)

    def move_selected(self, item):
        self.goto_move(self.move_list.row(item))

    def goto_move(self, index):
        self.current_board = chess.Board()
        for i in range(index + 1):
            self.current_board.push(self.moves[i])
        self.current_move_index = index + 1
        self.update_display()

    def next_move(self):
        if self.current_move_index < len(self.moves):
            self.current_board.push(self.moves[self.current_move_index])
            self.current_move_index += 1
            self.update_display()

    def prev_move(self):
        if self.current_move_index > 0:
            self.current_move_index -= 1
            self.current_board.pop()
            self.update_display()

    def first_move(self):
        while self.current_move_index > 0:
            self.prev_move()

    def last_move(self):
        while self.current_move_index < len(self.moves):
            self.next_move()

    def board_flip(self):
        self.flipped = not self.flipped
        self.board_orientation = not getattr(self, 'board_orientation', False)
        self.update_display()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.prev_move()
        elif event.key() == Qt.Key_Right:
            self.next_move()
        else:
            super().keyPressEvent(event)
    
    def mousePressEvent(self, event):
        try:
            file_idx = int(event.position().x() // self.square_size)
            rank_idx = int(event.position().y() // self.square_size)
            
            if not (0 <= file_idx <= 7 and 0 <= rank_idx <= 7):
                return
                
            # Adjust coordinates based on board orientation
            if not self.flipped:
                rank_idx = 7 - rank_idx
            else:
                file_idx = 7 - file_idx
                
            square = chess.square(file_idx, rank_idx)

            if self.selected_square is None:
                piece = self.current_board.piece_at(square)
                if piece and piece.color == self.current_board.turn:
                    self.selected_square = square
                    self.legal_moves = {move for move in self.current_board.legal_moves 
                                    if move.from_square == square}
                    self.update_display()
            else:
                if square == self.selected_square:
                    self.selected_square = None
                    self.legal_moves = set()
                    self.update_display()
                    return

                move = chess.Move(self.selected_square, square)
                
                piece = self.current_board.piece_at(self.selected_square)
                if (piece and piece.symbol().lower() == 'p' and
                    ((rank_idx == 7 and self.current_board.turn == chess.WHITE) or 
                    (rank_idx == 0 and self.current_board.turn == chess.BLACK))):
                    move = chess.Move(self.selected_square, square, promotion=chess.QUEEN)

                if move in self.legal_moves:
                    self.current_board.push(move)
                    self.played_moves.append(move)
                    self.current_move_index += 1
                
                self.selected_square = None
                self.legal_moves = set()
                self.update_display()
        except Exception as e:
            print(f"Error handling mouse press: {e}")
            self.selected_square = None
            self.legal_moves = set()
            self.update_display()


class BoardMaster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BoardMaster")
        self.setGeometry(100, 100, 1400, 900)
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.engine = self.initialize_engine()
        if not self.engine:
            return

        self.settings = QSettings("BoardMaster", "BoardMaster")
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

    def create_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        open_pgn = QAction("Open PGN File", self)
        open_pgn.triggered.connect(self.open_pgn_file)
        file_menu.addAction(open_pgn)

        tool_menu = menubar.addMenu("&Tools")
        interactive_board_action = QAction("Play Current Position", self)
        interactive_board_action.triggered.connect(self.open_interactive_board)
        tool_menu.addAction(interactive_board_action)

        settings_menu = menubar.addMenu("&Settings")
        open_settings = QAction("Engine Settings", self)
        open_settings.triggered.connect(self.open_settings)
        settings_menu.addAction(open_settings)

        help_menu = menubar.addMenu("&Help")
        open_help = QAction("How To Use", self)
        open_help.triggered.connect(self.open_help)
        help_menu.addAction(open_help)

    def initialize_engine(self):
        # List of possible Stockfish executable names
        stockfish_names = ["stockfish.exe", "stockfish"]
        
        # List of common installation directories
        extra_paths = [
            "C:/Program Files/Stockfish/",
            "C:/Program Files (x86)/Stockfish/",
            "./stockfish/",
            str(Path.home() / "Stockfish"),
            str(Path.home() / "Downloads" / "Stockfish")
        ]

        # Function to show error dialog
        def show_error(message):
            QMessageBox.critical(self, "Stockfish Error", message)

        # Try to find Stockfish in PATH and common locations
        try:
            # First try direct initialization
            try:
                return chess.engine.SimpleEngine.popen_uci("stockfish")
            except FileNotFoundError:
                pass

            # Then try with .exe extension on Windows
            if sys.platform == "win32":
                try:
                    return chess.engine.SimpleEngine.popen_uci("stockfish.exe")
                except FileNotFoundError:
                    pass

            # Search in PATH
            path_dirs = os.environ["PATH"].split(os.pathsep)
            
            # Add extra directories to search
            search_dirs = path_dirs + extra_paths
            
            # Debug info
            debug_info = "Searched directories:\n"
            
            for directory in search_dirs:
                debug_info += f"\n{directory}"
                for stockfish_name in stockfish_names:
                    full_path = os.path.join(directory, stockfish_name)
                    debug_info += f"\n  Trying: {full_path}"
                    if os.path.isfile(full_path):
                        try:
                            return chess.engine.SimpleEngine.popen_uci(full_path)
                        except:
                            debug_info += " (found but failed to initialize)"
                    else:
                        debug_info += " (not found)"

            # If we get here, Stockfish wasn't found
            error_message = (
                "Stockfish not found. Please ensure:\n\n"
                "1. Stockfish is installed\n"
                "2. The executable is named 'stockfish.exe' (Windows) or 'stockfish' (Mac/Linux)\n"
                "3. The installation directory is in your system PATH\n\n"
                "Technical Details:\n" + debug_info
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
        self.interactive_board = ChessGUI(fen=self.new_tab.current_board.fen())
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BoardMaster()
    srcSize = QScreen.availableGeometry(QApplication.primaryScreen())
    frmX = (srcSize.width() - window.width())/2
    frmY = (srcSize.height() - window.height())/2
    window.move(frmX, frmY)
    if window.engine:
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(1)
