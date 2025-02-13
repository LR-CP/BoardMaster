import sys
import chess
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QBrush, QIcon

class ChessBoard(QSvgWidget):
    def __init__(self, fen : str = None, parent=None):
        super().__init__(parent)

        self.fen = fen
        if self.fen is not None:
            self.board = chess.Board(self.fen)
        else:
            self.board = chess.Board()

        self.selected_square = None
        self.legal_moves = set()
        self.square_size = 70
        self.board_size = self.square_size * 8
        self.setMinimumSize(self.board_size, self.board_size)
        self.setMaximumSize(self.board_size, self.board_size)
        self.update_board()

    def update_board(self):
        try:
            self.load(self.board._repr_svg_().encode('utf-8'))
            # self.update_move_label()
            self.update()
        except Exception as e:
            print(f"Error updating board: {e}")
    
    def update_move_label(self):
        if self.board.turn == chess.WHITE:
            self.parent().status_label.setText("White to move.")
        elif self.board.turn == chess.BLACK:
            self.parent().status_label.setText("Black to move.")
        else:
            self.status_label.setText("White to move.")
    
    def analyze_all_moves(self):
        temp_board = chess.Board()
        self.move_evaluations = []     
       
        for i, move in enumerate(self.moves):
            info = self.engine.analyse(temp_board, chess.engine.Limit(time=0.1))
            prev_score = info["score"].white().score() if info["score"].white().score() is not None else 0
            
            temp_board.push(move)
            info = self.engine.analyse(temp_board, chess.engine.Limit(time=0.1))
            new_score = info["score"].white().score() if info["score"].white().score() is not None else 0
            
            score_diff = (new_score - prev_score) if temp_board.turn == chess.WHITE else -(new_score - prev_score)
            
            evaluation = "!!" if score_diff > 50 else "!" if score_diff > 20 else \
                        "??" if score_diff < -100 else "?" if score_diff < -50 else ""
            self.move_evaluations.append(evaluation)

            self.progress_bar.set_value(i + 1)
            QApplication.processEvents()
        
    def update_game_status(self):
        try:
            if not isinstance(self.parent(), ChessGUI):
                return
            
            if self.board.is_checkmate():
                winner = "Black" if self.board.turn == chess.WHITE else "White"
                self.parent().status_label.setText(f"Checkmate! {winner} wins!")
            elif self.board.is_stalemate():
                self.parent().status_label.setText("Stalemate!")
            elif self.board.is_check():
                current_player = "White" if self.board.turn == chess.WHITE else "Black"
                self.parent().status_label.setText(f"Check! {current_player} to move")
            else:
                current_player = "White" if self.board.turn == chess.WHITE else "Black"
                self.parent().status_label.setText(f"{current_player} to move")
        except Exception as e:
            print(f"Error updating status: {e}")

    def paintEvent(self, event):
        try:
            super().paintEvent(event)
            painter = QPainter(self)
            
            if self.selected_square is not None:
                # Highlight selected square
                file = chess.square_file(self.selected_square)
                rank = 7 - chess.square_rank(self.selected_square)
                painter.setBrush(QBrush(QColor(255, 255, 0, 80)))
                painter.setPen(Qt.NoPen)
                painter.drawRect(file * self.square_size, 
                               rank * self.square_size,
                               self.square_size, 
                               self.square_size)
                
                # Draw legal move indicators
                for move in self.legal_moves:
                    x = (chess.square_file(move.to_square)) * self.square_size
                    y = (7 - chess.square_rank(move.to_square)) * self.square_size
                    
                    painter.setBrush(QBrush(QColor(0, 255, 0, 80)))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(x + self.square_size/3, 
                                      y + self.square_size/3,
                                      self.square_size/3, 
                                      self.square_size/3)
        except Exception as e:
            print(f"Error in paint event: {e}")

    def mousePressEvent(self, event):
        try:
            file_idx = int(event.position().x() // self.square_size)
            rank_idx = 7 - int(event.position().y() // self.square_size)
            
            # Ensure indices are within bounds
            if not (0 <= file_idx <= 7 and 0 <= rank_idx <= 7):
                return
                
            square = chess.square(file_idx, rank_idx)

            if self.selected_square is None:
                # First click - select piece
                piece = self.board.piece_at(square)
                if piece and piece.color == self.board.turn:
                    self.selected_square = square
                    self.legal_moves = {move for move in self.board.legal_moves 
                                      if move.from_square == square}
                    self.update()
            else:
                # Second click - attempt to move
                if square == self.selected_square:
                    # Clicked same square - deselect
                    self.selected_square = None
                    self.legal_moves = set()
                    self.update()
                    return

                # Try to make the move
                move = chess.Move(self.selected_square, square)
                
                # Check for pawn promotion
                piece = self.board.piece_at(self.selected_square)
                if (piece and piece.symbol().lower() == 'p' and
                    ((rank_idx == 7 and self.board.turn == chess.WHITE) or 
                     (rank_idx == 0 and self.board.turn == chess.BLACK))):
                    move = chess.Move(self.selected_square, square, promotion=chess.QUEEN)

                # Make the move if it's legal
                if move in self.legal_moves:
                    self.board.push(move)
                    self.update_game_status()
                
                # Clear selection
                self.selected_square = None
                self.legal_moves = set()
                self.update_board()
        except Exception as e:
            print(f"Error handling mouse press: {e}")
            self.selected_square = None
            self.legal_moves = set()
            self.update_board()

class ChessGUI(QMainWindow):
    def __init__(self, fen : str = None):
        super().__init__()
        self.setWindowTitle("Chess Game")
        self.setFixedSize(700, 700)  # Fixed window size
        self.setWindowIcon(QIcon("./img/king.ico"))

        self.fen = fen
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create and add chess board
        self.chess_board = ChessBoard(fen=self.fen)
        layout.addWidget(self.chess_board, alignment=Qt.AlignCenter)
        
        # Create and add status label
        self.status_label = QLabel()
        self.update_move_label()

        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumHeight(30)
        layout.addWidget(self.status_label)
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        # Create buttons
        new_game_button = QPushButton("New Game")
        new_game_button.clicked.connect(self.new_game)
        undo_button = QPushButton("Undo Move")
        undo_button.clicked.connect(self.undo_move)
        
        button_layout.addWidget(new_game_button)
        button_layout.addWidget(undo_button)
        layout.addLayout(button_layout)

    def new_game(self):
        try:
            self.chess_board.board.reset()
            self.chess_board.selected_square = None
            self.chess_board.legal_moves = set()
            self.chess_board.update_board()
            self.chess_board.update_game_status()
        except Exception as e:
            print(f"Error starting new game: {e}")
    
    def update_move_label(self):
        if self.chess_board.board.turn == chess.WHITE:
            self.status_label.setText("White to move.")
        elif self.chess_board.board.turn == chess.BLACK:
            self.status_label.setText("Black to move.")
        else:
            self.status_label.setText("White to move.")

    def undo_move(self):
        try:
            if len(self.chess_board.board.move_stack) > 0:
                self.chess_board.board.pop()
                self.chess_board.selected_square = None
                self.chess_board.legal_moves = set()
                self.chess_board.update_board()
                self.chess_board.update_game_status()
        except Exception as e:
            print(f"Error undoing move: {e}")
    
    def analyze_position(self):
        if not self.parent.current_board.is_game_over():
            info = self.parent.engine.analyse(
                self.parent.current_board, chess.engine.Limit(time=0.1), multipv=self.parent.settings.value("engine/lines", 3, int)
            )

            analysis_text = f"Move {(self.parent.current_move_index + 1) // 2} "
            analysis_text += (
                f"({'White' if self.parent.current_move_index % 2 == 0 else 'Black'})\n\n"
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
                    f"{i}. {self.parent.current_board.san(move)} (eval: {score:+.2f})\n"
                )

            self.analysis_text.setText(analysis_text)

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        window = ChessGUI()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error running application: {e}")