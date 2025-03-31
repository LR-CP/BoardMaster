import sys
import os
import chess
import chess.engine
import chess.svg
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMenu, QLineEdit, QDialog
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt, QByteArray, QPointF, QMimeData, QPoint
from PySide6.QtGui import QPainter, QIcon, QColor, QAction, QPen, QPixmap, QDrag

class PromotionDialog(QDialog):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Promotion Piece")
        layout = QHBoxLayout()
        
        pieces = ['q', 'r', 'b', 'n'] if color == chess.BLACK else ['Q', 'R', 'B', 'N']
        self.selected_piece = None
        
        for piece in pieces:
            button = QPushButton()
            piece_svg = chess.svg.piece(chess.Piece.from_symbol(piece))
            pixmap = QPixmap(50, 50)
            pixmap.loadFromData(piece_svg.encode())
            button.setIcon(QIcon(pixmap))
            button.setIconSize(pixmap.size())
            button.clicked.connect(lambda checked, p=piece: self.select_piece(p))
            layout.addWidget(button)
            
        self.setLayout(layout)

    def select_piece(self, piece):
        self.selected_piece = piece
        self.accept()

class ChessBoard(QSvgWidget):
    def __init__(self, engine : chess.engine = None, threads=None, multipv=None, mem=None, time=None, depth=None, parent=None):
        """
        @brief Initialize the chess board widget.
        @param engine The chess engine instance.
        @param threads Number of threads.
        @param multipv Number of analysis lines.
        @param mem Memory allocation for engine.
        @param time Time for analysis.
        @param depth Depth for analysis.
        @param parent Parent widget.
        """
        super().__init__(parent)
        self.board = chess.Board()  # Default starting position
        self.threads = threads
        self.multipv= multipv
        self.mem = mem
        self.time = time
        self.depth_an = depth
        self.edit_mode = False
        self.square_size = 70
        self.board_size = self.square_size * 8
        self.setFixedSize(self.board_size, self.board_size)
        self.board_orientation = chess.WHITE
        self.move_stack = []
        self.engine = engine
        self.best_moves = []
        self.selected_square = None
        self.legal_moves = []
        self.highlight_moves = []  # NEW: stores squares to highlight for legal moves
        self.dragging = False
        self.drag_start_square = None
        self.drag_current_pos = None
        self.drag_offset = None
        self.game_tab = parent
        self.setAcceptDrops(True)  # Add this line to explicitly enable drops
        self.update_board()

    def update_board(self):
        """
        @brief Render and update the board display.
        """
        # Get king square if in check
        check = self.board.king(self.board.turn) if self.board.is_check() else None
        
        board_svg = chess.svg.board(
            self.board,
            size=self.board_size,
            orientation=self.board_orientation,
            check=check  # Add check parameter
        )
        self.load(QByteArray(board_svg.encode("utf-8")))
        self.update()
        # Always update parent's FEN display
        if self.parent() and hasattr(self.parent(), 'fen_input'):
            self.parent().fen_input.setText(self.board.fen())

    def flip_board(self):
        """
        @brief Flip the board orientation.
        """
        self.board_orientation = chess.BLACK if self.board_orientation == chess.WHITE else chess.WHITE
        self.update_board()

    def set_piece(self, square, piece_symbol):
        """
        @brief Set or remove a piece on the board.
        @param square The target square.
        @param piece_symbol The piece symbol; empty string removes the piece.
        """
        self.move_stack.append(self.board.fen())
        if piece_symbol == '':
            self.board.remove_piece_at(square)
        else:
            piece = chess.Piece.from_symbol(piece_symbol)
            self.board.set_piece_at(square, piece)
        self.best_moves = []
        self.update_board()

    def set_fen(self, fen):
        """
        @brief Set the board from a FEN string.
        @param fen The FEN string.
        """
        try:
            self.board.set_fen(fen)
            self.best_moves = []
            self.update_board()
        except ValueError:
            self.parent().status_label.setText("Invalid FEN")

    def undo_move(self):
        """
        @brief Undo the last move.
        """
        if self.move_stack:
            fen = self.move_stack.pop()
            self.board.set_fen(fen)
            self.best_moves = []
            self.update_board()

    def analyze_position(self):
        """
        @brief Analyze the current board position using the engine.
        """
        try:
            result = self.engine.analyse(self.board, chess.engine.Limit(time=self.time), multipv=self.multipv)
        except Exception as e:
            print(f"Engine error: {e}")
            if hasattr(self.parent(), 'engine_path'):
                try:
                    self.engine = chess.engine.SimpleEngine.popen_uci(self.parent().engine_path)
                    result = self.engine.analyse(self.board, chess.engine.Limit(time=self.time), multipv=self.multipv)
                except Exception as e:
                    print(f"Failed to restart engine: {e}")
                    return
            else:
                print("No engine path available for restart")
                return

        # Continue with existing analysis code
        self.best_moves = [info['pv'][0] for info in result]
        arrows = []
        for i, pv in enumerate(result, 1):
            move = pv["pv"][0]
            color = "#00ff00" if i == 1 else "#007000" if i == 2 else "#003000"
            arrows.append(chess.svg.Arrow(
                tail=move.from_square,
                head=move.to_square,
                color=color
            ))
        
        board_svg = chess.svg.board(
            self.board,
            arrows=arrows,
            orientation=self.board_orientation,
        )
        self.load(QByteArray(board_svg.encode("utf-8")))

    def map_position_to_square(self, pos):
        """
        @brief Map a widget coordinate to a board square index.
        @param pos QPointF representing the position.
        @return Tuple (file_idx, rank_idx).
        """
        # pos is a QPointF in widget coordinates.
        if self.board_orientation == chess.WHITE:
            file_idx = int(pos.x() // self.square_size)
            rank_idx = 7 - int(pos.y() // self.square_size)
        else:  # For flipped board (BLACK orientation)
            file_idx = 7 - int(pos.x() // self.square_size)
            rank_idx = int(pos.y() // self.square_size)
        return file_idx, rank_idx

    def mousePressEvent(self, event):
        """Handle mouse press events for piece movement and editing."""
        pos = event.position()
        file_idx, rank_idx = self.map_position_to_square(pos)
        square = chess.square(file_idx, rank_idx)

        # Handle right-click in edit mode
        if event.button() == Qt.RightButton and self.edit_mode:
            self.show_piece_menu(event.globalPos(), square)
            return

        # Regular piece movement logic
        if not self.edit_mode and event.button() == Qt.LeftButton:
            piece = self.board.piece_at(square)
            if piece:
                # Create drag object
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(str(square))
                drag.setMimeData(mime_data)
                
                # Set drag pixmap
                pixmap = self.get_piece_pixmap(piece)
                drag.setPixmap(pixmap)
                drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
                
                # Show legal moves
                legal = [move for move in self.board.legal_moves if move.from_square == square]
                self.highlight_moves = [move.to_square for move in legal]
                self.update()
                
                # Execute drag
                result = drag.exec(Qt.MoveAction | Qt.CopyAction)
                
                # Clear highlights
                self.highlight_moves = []
                self.update()
                return

    def mouseMoveEvent(self, event):
        """Handle mouse move events."""
        if self.dragging:
            self.drag_current_pos = event.position()
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release events."""
        if self.dragging and self.drag_start_square is not None:
            pos = event.position()
            file_idx, rank_idx = self.map_position_to_square(pos)
            drop_square = chess.square(file_idx, rank_idx)
            
            move = chess.Move(self.drag_start_square, drop_square)
            if move in self.board.legal_moves:
                self.move_stack.append(self.board.fen())
                self.board.push(move)
                self.best_moves = []
                self.update_board()
                
            self.dragging = False
            self.drag_start_square = None
            self.drag_current_pos = None
            self.drag_offset = None
            self.highlight_moves = []
            self.update()

    def dragEnterEvent(self, event):
        """Handle drag enter events."""
        if event.mimeData().hasText():
            event.setAccepted(True)
            event.accept()  # Explicitly accept the event
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """Handle drag move events."""
        pos = event.position()
        if 0 <= pos.x() <= self.width() and 0 <= pos.y() <= self.height():
            square = self.square_at_position(pos)
            if square is not None:
                event.setAccepted(True)
                event.accept()
                return
        event.ignore()

    def dropEvent(self, event):
        """Handle drop events."""
        pos = event.position()
        to_square = self.square_at_position(pos)
        
        if to_square is not None and event.mimeData().hasText():
            from_square = int(event.mimeData().text())
            
            # Check if this is a pawn promotion move
            piece = self.board.piece_at(from_square)
            is_promotion = (piece is not None and piece.piece_type == chess.PAWN and 
                          ((to_square >= 56 and piece.color == chess.WHITE) or
                           (to_square <= 7 and piece.color == chess.BLACK)))
            
            if is_promotion:
                promotion_piece = self.get_promotion_piece(piece.color)
                move = chess.Move(from_square, to_square, promotion=promotion_piece.piece_type)
            else:
                move = chess.Move(from_square, to_square)
            
            if move in self.board.legal_moves:
                self.move_stack.append(self.board.fen())
                self.board.push(move)
                self.best_moves = []
                self.update_board()
                event.acceptProposedAction()
                return
        
        event.ignore()

    def square_at_position(self, pos):
        """Convert screen coordinates to chess square."""
        # Convert position to file and rank indices
        file_idx, rank_idx = self.map_position_to_square(pos)
        
        # Check if indices are valid
        if 0 <= file_idx < 8 and 0 <= rank_idx < 8:
            return chess.square(file_idx, rank_idx)
        return None

    def show_piece_menu(self, pos, square):
        """
        @brief Show a popup menu to set or remove a piece.
        @param pos The position where the menu is shown.
        @param square The board square.
        """
        menu = QMenu(self)
        pieces = {'Empty': '', 'White Pawn': 'P', 'White Knight': 'N', 'White Bishop': 'B', 'White Rook': 'R', 'White Queen': 'Q', 'White King': 'K', 'Black Pawn': 'p', 'Black Knight': 'n', 'Black Bishop': 'b', 'Black Rook': 'r', 'Black Queen': 'q', 'Black King': 'k'}

        for name, symbol in pieces.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked, s=symbol: self.set_piece(square, s))
            menu.addAction(action)

        menu.exec(pos)

    def paintEvent(self, event):
        """
        @brief Paint the board and any overlays.
        @param event The paint event.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        
        # Draw highlighted moves
        if self.highlight_moves:
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor(0, 150, 0, 200), 2)
            painter.setPen(pen)
            brush = QColor(0, 150, 0, 100)
            painter.setBrush(brush)
            for sq in self.highlight_moves:
                file = chess.square_file(sq)
                rank = 7 - chess.square_rank(sq)
                if self.board_orientation == chess.BLACK:
                    file = 7 - file
                    rank = 7 - rank
                square_center_x = (file + 0.5) * self.square_size
                square_center_y = (rank + 0.5) * self.square_size
                center = QPointF(square_center_x, square_center_y)
                radius = self.square_size / 5
                painter.drawEllipse(center, radius, radius)

        painter.end()

    def get_piece_pixmap(self, piece):
        """
        @brief Get SVG pixmap for a chess piece.
        @param piece The chess piece.
        @return A QPixmap of the piece.
        """
        piece_svg = chess.svg.piece(piece)
        pixmap = QPixmap(100, 100)  # Fixed size for drag image
        pixmap.loadFromData(piece_svg.encode(), 'SVG')
        return pixmap.scaled(self.square_size, self.square_size, 
                           Qt.KeepAspectRatio, 
                           Qt.SmoothTransformation)

    def rebuild_board_state(self):
        """Rebuild the board state and prepare for analysis"""
        self.best_moves = []
        self.selected_square = None
        self.legal_moves = []
        self.highlight_moves = []
        self.update_board()

    def set_turn(self, color):
        """Set whose turn it is to move"""
        self.board.turn = color
        self.update_board()

    def get_promotion_piece(self, color):
        """Show promotion dialog and return selected piece"""
        dialog = PromotionDialog(color, self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_piece:
            return chess.Piece.from_symbol(dialog.selected_piece)
        return chess.Piece.from_symbol('q' if color == chess.BLACK else 'Q')  # Default to queen

class BoardEditor(QMainWindow):
    def __init__(self, engine : chess.engine = None, fen=None, threads=4, multipv=3, mem=128, time=0.1, depth=50):
        """
        @brief Initialize the board editor window.
        @param engine The chess engine instance.
        @param fen Initial board FEN, if any.
        @param threads Number of threads.
        @param multipv Number of analysis lines.
        @param mem Memory allocation for engine.
        @param time Time for analysis.
        @param depth Analysis depth.
        """
        super().__init__()
        self.setWindowTitle("Chess Board Editor")
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.setFixedSize(600, 700)

        self.fen = fen
        self.fen_input = QLineEdit()
        self.fen_input.setPlaceholderText("Enter FEN")

        # NEW: If engine is a string, launch it as a UCI engine.
        self.engine_path = engine if isinstance(engine, str) else "./stockfish/stockfish.exe"
        if isinstance(engine, str):
            engine = chess.engine.SimpleEngine.popen_uci(engine)
        self.board_widget = ChessBoard(engine=engine, threads=threads, multipv=multipv, mem=mem, time=time, depth=depth, parent=self)

        self.status_label = QLabel("Edit Mode: OFF")
        self.status_label.setAlignment(Qt.AlignCenter)

        self.toggle_edit_button = QPushButton("Toggle Edit Mode")
        self.toggle_edit_button.clicked.connect(self.toggle_edit_mode)

        self.clear_button = QPushButton("Clear Board")
        self.clear_button.clicked.connect(self.clear_board)

        self.undo_button = QPushButton("Undo")
        self.undo_button.clicked.connect(self.board_widget.undo_move)

        self.analyze_button = QPushButton("Analyze Position")
        self.analyze_button.clicked.connect(self.board_widget.analyze_position)

        self.flip_button = QPushButton("Flip Board")
        self.flip_button.clicked.connect(self.board_widget.flip_board)

        # NEW: Add turn selector button
        self.turn_button = QPushButton("White to Move")
        self.turn_button.clicked.connect(self.toggle_turn)
        self.turn_button.setEnabled(False)  # Only enabled in edit mode

        self.fen_input = QLineEdit()
        self.fen_input.setPlaceholderText("Enter FEN")
        if self.fen:
            self.fen_input.setText(self.fen)
            self.set_fen_position()
        self.fen_input.returnPressed.connect(self.set_fen_position)

        self.refresh_button = QPushButton("Refresh Board")
        self.refresh_button.clicked.connect(self.refresh_board)

        layout = QVBoxLayout()
        layout.addWidget(self.board_widget)
        layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.toggle_edit_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.undo_button)
        button_layout.addWidget(self.analyze_button)
        button_layout.addWidget(self.flip_button)
        button_layout.addWidget(self.turn_button)  # Add turn button to layout

        layout.addLayout(button_layout)
        layout.addWidget(self.fen_input)
        layout.addWidget(self.refresh_button)  # Add refresh button at bottom

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def toggle_edit_mode(self):
        """
        @brief Toggle the board edit mode on/off.
        """
        self.refresh_board()
        self.board_widget.edit_mode = not self.board_widget.edit_mode
        status = "ON" if self.board_widget.edit_mode else "OFF"
        self.status_label.setText(f"Edit Mode: {status}")
        # Enable/disable turn button based on edit mode
        self.turn_button.setEnabled(self.board_widget.edit_mode)
        if not self.board_widget.edit_mode:
            self.board_widget.update_board()

    def toggle_turn(self):
        """Toggle between White and Black to move"""
        self.board_widget.board.turn = not self.board_widget.board.turn
        button_text = "White to Move" if self.board_widget.board.turn else "Black to Move"
        self.board_widget.update_board()
        self.turn_button.setText(button_text)

    def clear_board(self):
        """
        @brief Clear the entire board.
        """
        self.board_widget.board.clear()
        self.board_widget.best_moves = []
        self.board_widget.update_board()

    def set_fen_position(self):
        """
        @brief Set the board position from a FEN string input.
        """
        fen = self.fen_input.text()
        self.board_widget.set_fen(fen)

    def update_fen(self, fen):
        """Update FEN string in the input box"""
        self.fen_input.setText(fen)

    def refresh_board(self):
        """Refresh the board state and prepare for new operations"""
        # self.board_widget.rebuild_board_state()
        self.board_widget.board.set_fen(self.board_widget.board.fen())
        self.board_widget.update()
        self.board_widget.update_board()
        self.update_fen(self.board_widget.board.fen())
        self.status_label.setText("Board Refreshed")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    engine_path = "./stockfish/stockfish.exe"  # Adjust path as needed
    # engine_path = "C:\\Users\\LPC\\Documents\\Programs\\ChessEngine\\x64\\Debug\\ChessEngine.exe"
    window = BoardEditor(engine_path)
    window.show()
    sys.exit(app.exec())
