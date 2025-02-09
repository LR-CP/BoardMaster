import chess
import chess.pgn
import chess.engine
import chess.svg
import io
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QPushButton, QTextEdit, QLabel, QMessageBox,
                              QListWidget)
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QByteArray
from PySide6.QtCore import Qt
import sys
from pathlib import Path
import os

class ChessAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Game Analyzer")
        self.setGeometry(100, 100, 1400, 900)
        self.engine = self.initialize_engine()
        if not self.engine:
            return

        self.current_game = None
        self.current_board = chess.Board()
        self.moves = []
        self.current_move_index = 0
        self.move_evaluations = []
        self.create_gui()

    def create_gui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left panel
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Game details header
        self.game_details = QLabel()
        self.game_details.setStyleSheet("font-size: 14px; padding: 10px; background-color: #f0f0f0;")
        left_layout.addWidget(self.game_details)

        horizontal_layout = QHBoxLayout()
        # Winning bar
        self.win_bar = QLabel()
        self.win_bar.setFixedSize(20, 600)
        self.win_bar.setStyleSheet("background: qlineargradient(y1:0, y2:1, stop:0 white, stop:0.5 gray, stop:1 black);")
        # Chess board
        self.board_display = QSvgWidget()
        self.board_display.setFixedSize(600, 600)

        # Add widgets to the horizontal layout
        horizontal_layout.addWidget(self.win_bar)
        horizontal_layout.addWidget(self.board_display)

        # Now add the horizontal layout to your main layout (assuming main_layout is defined)
        main_layout.addLayout(horizontal_layout)

        # Navigation
        nav_layout = QHBoxLayout()
        for text, func in [("<<", self.first_move), ("<", self.prev_move),
                          (">", self.next_move), (">>", self.last_move)]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            nav_layout.addWidget(btn)
        left_layout.addLayout(nav_layout)

        # Right panel
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # PGN input
        right_layout.addWidget(QLabel("Paste PGN here:"))
        self.pgn_text = QTextEdit()
        self.pgn_text.setMinimumHeight(100)
        right_layout.addWidget(self.pgn_text)
        load_button = QPushButton("Load Game")
        load_button.clicked.connect(self.load_game)
        right_layout.addWidget(load_button)

        # Move list
        right_layout.addWidget(QLabel("Move List:"))
        self.move_list = QListWidget()
        self.move_list.itemClicked.connect(self.move_selected)
        right_layout.addWidget(self.move_list)

        # Analysis
        right_layout.addWidget(QLabel("Analysis:"))
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        right_layout.addWidget(self.analysis_text)

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)
        self.update_display()

    def load_game(self):
        pgn_string = self.pgn_text.toPlainText()
        pgn_io = io.StringIO(pgn_string)
        self.current_game = chess.pgn.read_game(pgn_io)
        
        if self.current_game is None:
            self.analysis_text.setText("Error: Invalid PGN format")
            return

        self.current_board = self.current_game.board()
        self.moves = list(self.current_game.mainline_moves())
        self.current_move_index = 0
        self.move_evaluations = []
        
        headers = self.current_game.headers
        self.game_details.setText(
            f"White: {headers.get('White', 'Unknown')} ({headers.get('WhiteElo', '?')})\n"
            f"Black: {headers.get('Black', 'Unknown')} ({headers.get('BlackElo', '?')})\n"
            f"Event: {headers.get('Event', 'Unknown')} - Date: {headers.get('Date', 'Unknown')}"
        )
        
        self.analyze_all_moves()
        self.update_display()

    def initialize_engine(self):
        # List of possible Stockfish executable names
        stockfish_names = ["stockfish.exe", "stockfish"]
        
        # List of common installation directories
        extra_paths = [
            "C:/Program Files/Stockfish/",
            "C:/Program Files (x86)/Stockfish/",
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

    def update_display(self):
        arrows = []
        annotations = {}
        eval_score = 0
        
        if not self.current_board.is_game_over():
            analysis = self.engine.analyse(self.current_board, chess.engine.Limit(time=0.1), multipv=3)
            
            for i, pv in enumerate(analysis):
                move = pv["pv"][0]
                score = pv["score"].white().score() if pv["score"].white().score() is not None else 0
                eval_score = score  # Store evaluation score for win bar
                
                color = "#00ff00" if i == 0 else "#007000" if i == 1 else "#003000"
                arrows.append(chess.svg.Arrow(tail=move.from_square, head=move.to_square, color=color))
                annotations[move.to_square] = f"{score / 100.0:.2f}"  # Fix: Use square index instead of string
            
            if self.current_move_index > 0:
                last_move = self.moves[self.current_move_index - 1]
                arrows.append(chess.svg.Arrow(tail=last_move.from_square, head=last_move.to_square, color="#FF0000"))
                annotations[last_move.to_square] = "Your Move"  # Fix: Use square index instead of string
        
        board_svg = chess.svg.board(self.current_board, arrows=arrows, size=600, 
                                    squares=annotations)
        self.board_display.load(QByteArray(board_svg.encode('utf-8')))
        
        self.update_win_bar(eval_score)
        
        self.move_list.clear()
        temp_board = chess.Board()
        for i, move in enumerate(self.moves):
            move_san = temp_board.san(move)
            evaluation = self.move_evaluations[i] if i < len(self.move_evaluations) else ""
            annotation_map = {"!!": "!!", "!": "!", "??": "??", "?": "?"}  # Ensure proper symbols
            evaluation_display = annotation_map.get(evaluation, "")
            self.move_list.addItem(f"{(i // 2) + 1}. {move_san} {evaluation_display}")
            temp_board.push(move)
        self.move_list.setCurrentRow(self.current_move_index - 1)
        
        self.analyze_position()
    
    def update_win_bar(self, eval_score):
        white_percentage = max(0, min(100, 50 + eval_score / 2))
        black_percentage = 100 - white_percentage
        self.win_bar.setStyleSheet(f"background: qlineargradient(y1:0, y2:1, stop:0 white, stop:{white_percentage / 100} white, stop:{white_percentage / 100} black, stop:1 black);")

    def analyze_all_moves(self):
        temp_board = chess.Board()
        self.move_evaluations = []
        
        for move in self.moves:
            info = self.engine.analyse(temp_board, chess.engine.Limit(time=0.1))
            prev_score = info["score"].white().score() if info["score"].white().score() is not None else 0
            
            temp_board.push(move)
            info = self.engine.analyse(temp_board, chess.engine.Limit(time=0.1))
            new_score = info["score"].white().score() if info["score"].white().score() is not None else 0
            
            score_diff = (new_score - prev_score) if temp_board.turn == chess.WHITE else -(new_score - prev_score)
            
            evaluation = "!!" if score_diff > 50 else "!" if score_diff > 20 else \
                        "??" if score_diff < -100 else "?" if score_diff < -50 else ""
            self.move_evaluations.append(evaluation)

    # Enable arrow key scrolling
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.prev_move()
        elif event.key() == Qt.Key_Right:
            self.next_move()
        else:
            super().keyPressEvent(event)
        
    def analyze_position(self):
        # Get engine analysis
        info = self.engine.analyse(
            self.current_board,
            chess.engine.Limit(time=0.1),
            multipv=3
        )

        # Prepare analysis text
        analysis_text = ""
        
        # Display current move number
        if self.current_move_index > 0:
            move_number = (self.current_move_index + 1) // 2
            color = "Black" if self.current_move_index % 2 else "White"
            analysis_text += f"Move {move_number} ({color})\n\n"

        # Display top moves and evaluations
        analysis_text += "Top moves:\n"
        for i, pv in enumerate(info, 1):
            move = pv["pv"][0]
            score = pv["score"].white().score() / 100.0
            analysis_text += f"{i}. {self.current_board.san(move)} (eval: {score:+.2f})\n"

        self.analysis_text.setText(analysis_text)

    # New method to handle move selection
    def move_selected(self, item):
        index = self.move_list.row(item)
        self.goto_move(index)

    # New method to jump to a specific move
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

    def closeEvent(self, event):
        if hasattr(self, 'engine') and self.engine:
            self.engine.quit()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChessAnalyzer()
    if window.engine:  # Only show window if engine initialized successfully
        window.show()
        sys.exit(app.exec_())
    else:
        sys.exit(1)