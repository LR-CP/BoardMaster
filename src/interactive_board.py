import sys
import chess
import chess.engine
import chess.svg
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMenu, QLineEdit
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt, QByteArray, QPointF
from PySide6.QtGui import QPainter, QIcon, QColor, QAction, QPen, QPixmap

class ChessBoard(QSvgWidget):
    def __init__(self, engine : chess.engine = None, threads=None, multipv=None, mem=None, time=None, depth=None, parent=None):
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
        # Drag/drop state
        self.dragging = False
        self.drag_start_square = None
        self.drag_current_pos = None
        self.drag_offset = None
        self.update_board()

    def update_board(self):
        board_svg = chess.svg.board(
            self.board,
            size=self.board_size,
            orientation=self.board_orientation
        )
        self.load(QByteArray(board_svg.encode("utf-8")))
        self.update()

    def flip_board(self):
        self.board_orientation = chess.BLACK if self.board_orientation == chess.WHITE else chess.WHITE
        self.update_board()

    def set_piece(self, square, piece_symbol):
        self.move_stack.append(self.board.fen())
        if piece_symbol == '':
            self.board.remove_piece_at(square)
        else:
            piece = chess.Piece.from_symbol(piece_symbol)
            self.board.set_piece_at(square, piece)
        self.best_moves = []
        self.update_board()

    def set_fen(self, fen):
        try:
            self.board.set_fen(fen)
            self.best_moves = []
            self.update_board()
        except ValueError:
            self.parent().status_label.setText("Invalid FEN")

    def undo_move(self):
        if self.move_stack:
            fen = self.move_stack.pop()
            self.board.set_fen(fen)
            self.best_moves = []
            self.update_board()

    def analyze_position(self):
        arrows = []
        self.current_move_index = 1
        result = self.engine.analyse(self.board, chess.engine.Limit(time=self.time), multipv=self.multipv)
        self.best_moves = [info['pv'][0] for info in result]
        # Get the main line evaluation
        main_eval = result[0]["score"].relative
        # eval_score = self.eval_to_cp(main_eval) if hasattr(self, 'eval_to_cp') else 0
        
        # Update analysis text
        analysis_text = f"Move {(self.current_move_index + 1) // 2} "
        analysis_text += f"({'White' if self.current_move_index % 2 == 0 else 'Black'})\n\n"
        analysis_text += "Top moves:\n"
        
        for i, pv in enumerate(result, 1):
            move = pv["pv"][0]
            # score = self.eval_to_cp(pv["score"].relative) if hasattr(self, 'eval_to_cp') else 0
            # analysis_text += f"{i}. {self.board.san(move)} (eval: {score/100:+.2f})\n"
            
            # Add arrows
            color = "#00ff00" if i == 0 else "#007000" if i == 1 else "#003000"
            arrows.append(chess.svg.Arrow(
                tail=move.from_square,
                head=move.to_square,
                color=color
            ))
            # annotations[move.to_square] = f"{score / 100.0:.2f}"
        
        # Generate the base SVG board
        board_svg = chess.svg.board(
            self.board,
            arrows=arrows,
            orientation=self.board_orientation,
        )

        self.load(QByteArray(board_svg._repr_svg_().encode("utf-8")))

        # self.update_board()

    # NEW: Helper method to map a display position to board square indexes.
    def map_position_to_square(self, pos):
        # pos is a QPointF in widget coordinates.
        if self.board_orientation == chess.WHITE:
            file_idx = int(pos.x() // self.square_size)
            rank_idx = 7 - int(pos.y() // self.square_size)
        else:  # For flipped board (BLACK orientation)
            file_idx = 7 - int(pos.x() // self.square_size)
            rank_idx = int(pos.y() // self.square_size)
        return file_idx, rank_idx

    # Update mousePressEvent to use the mapping.
    def mousePressEvent(self, event):
        pos = event.position()  # localPos()
        file_idx, rank_idx = self.map_position_to_square(pos)
        square = chess.square(file_idx, rank_idx)
        piece = self.board.piece_at(square)
        if event.button() == Qt.LeftButton and piece is not None:
            # NEW: Add highlight moves
            legal = [move for move in self.board.legal_moves if move.from_square == square]
            self.highlight_moves = [move.to_square for move in legal]
            self.dragging = True
            self.drag_start_square = square
            # Instead of computing a global offset from self.width(),
            # use the fixed board area (self.square_size*8) as reference.
            if self.board_orientation == chess.WHITE:
                target_top_left = QPointF(file_idx * self.square_size,
                                          (7 - rank_idx) * self.square_size)
            else:
                target_top_left = QPointF((7 - file_idx) * self.square_size,
                                          rank_idx * self.square_size)
            self.drag_offset = pos - target_top_left
            self.drag_current_pos = pos
        else:
            super().mousePressEvent(event)
        self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.drag_current_pos = event.position()
            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            pos = event.position()
            file_idx, rank_idx = self.map_position_to_square(pos)
            drop_square = chess.square(file_idx, rank_idx)
            move = chess.Move(self.drag_start_square, drop_square)
            if move in self.board.legal_moves:
                self.board.push(move)
            self.dragging = False
            self.drag_start_square = None
            self.drag_current_pos = None
            self.drag_offset = None
            self.highlight_moves = []  # NEW: Clear highlights
            self.update_board()  # re-render board
        else:
            super().mouseReleaseEvent(event)

    def show_piece_menu(self, pos, square):
        menu = QMenu(self)
        pieces = {'Empty': '', 'White Pawn': 'P', 'White Knight': 'N', 'White Bishop': 'B', 'White Rook': 'R', 'White Queen': 'Q', 'White King': 'K', 'Black Pawn': 'p', 'Black Knight': 'n', 'Black Bishop': 'b', 'Black Rook': 'r', 'Black Queen': 'q', 'Black King': 'k'}

        for name, symbol in pieces.items():
            action = QAction(name, self)
            action.triggered.connect(lambda checked, s=symbol: self.set_piece(square, s))
            menu.addAction(action)

        menu.exec(pos)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        
        # NEW: Add global_offset calculation like in gametab.py
        board_size = 8 * self.square_size
        global_offset = (self.width() - board_size) / 2

        if self.selected_square is not None:
            file = chess.square_file(self.selected_square)
            rank = 7 - chess.square_rank(self.selected_square)
            painter.fillRect(file * self.square_size, rank * self.square_size, self.square_size, self.square_size, QColor(200, 200, 0, 100))

            for move in self.legal_moves:
                to_file = chess.square_file(move.to_square)
                to_rank = 7 - chess.square_rank(move.to_square)
                painter.fillRect(to_file * self.square_size, to_rank * self.square_size, self.square_size, self.square_size, QColor(0, 200, 0, 100))

        # Updated circle drawing with correct offset
        if self.highlight_moves:
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor(0, 150, 0, 200), 2)  # Reduced pen width
            painter.setPen(pen)
            brush = QColor(0, 150, 0, 100)
            painter.setBrush(brush)
            for sq in self.highlight_moves:
                file = chess.square_file(sq)
                rank = 7 - chess.square_rank(sq)
                # Calculate center position based on square coordinates
                square_center_x = (file + 0.5) * self.square_size
                square_center_y = (rank + 0.5) * self.square_size
                center = QPointF(square_center_x, square_center_y)
                radius = self.square_size / 5  # Smaller radius (was /3)
                painter.drawEllipse(center, radius, radius)

        # if self.best_moves: # Keep maybe can change arrows to use this
        #     pen = QPen(QColor(255, 0, 0))
        #     pen.setWidth(3)
        #     painter.setPen(pen)

        #     for move in self.best_moves:
        #         from_square = move.from_square
        #         to_square = move.to_square

        #         from_x = (chess.square_file(from_square) + 0.5) * self.square_size
        #         from_y = (7 - chess.square_rank(from_square) + 0.5) * self.square_size
        #         to_x = (chess.square_file(to_square) + 0.5) * self.square_size
        #         to_y = (7 - chess.square_rank(to_square) + 0.5) * self.square_size

        #         painter.drawLine(from_x, from_y, to_x, to_y)

        if self.dragging and self.drag_start_square is not None and self.drag_current_pos is not None:
            piece = self.board.piece_at(self.drag_start_square)
            if piece:
                # Draw the piece image instead of text
                pixmap = self.get_piece_pixmap(piece)
                target_pos = self.drag_current_pos - self.drag_offset
                painter.drawPixmap(target_pos, pixmap)

        painter.end()

    def get_piece_pixmap(self, piece):
        prefix = "w" if piece.color == chess.WHITE else "b"
        letter = piece.symbol().upper()
        path = f"c:/Users/LPC/Documents/Programs/BoardMaster/piece_images/{prefix.lower()}{letter.lower()}.png"
        pixmap = QPixmap(path)
        if pixmap.isNull():
            print(f"Error: Failed to load image from {path}")
            pixmap = QPixmap(self.square_size, self.square_size)
            pixmap.fill(Qt.transparent)
            temp_painter = QPainter(pixmap)
            temp_painter.setPen(Qt.black)
            temp_painter.drawText(pixmap.rect(), Qt.AlignCenter, piece.symbol())
            temp_painter.end()
        return pixmap.scaled(self.square_size, self.square_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

class BoardEditor(QMainWindow):
    def __init__(self, engine : chess.engine = None, fen=None, threads=None, multipv=None, mem=None, time=None, depth=None):
        super().__init__()
        self.setWindowTitle("Chess Board Editor")
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.setFixedSize(600, 700)

        self.fen = fen

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

        self.fen_input = QLineEdit()
        self.fen_input.setPlaceholderText("Enter FEN")
        if self.fen:
            self.fen_input.setText(self.fen)
            self.set_fen_position()
        self.fen_input.returnPressed.connect(self.set_fen_position)

        layout = QVBoxLayout()
        layout.addWidget(self.board_widget)
        layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.toggle_edit_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.undo_button)
        button_layout.addWidget(self.analyze_button)
        button_layout.addWidget(self.flip_button)

        layout.addLayout(button_layout)
        layout.addWidget(self.fen_input)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def toggle_edit_mode(self):
        self.board_widget.edit_mode = not self.board_widget.edit_mode
        status = "ON" if self.board_widget.edit_mode else "OFF"
        self.status_label.setText(f"Edit Mode: {status}")

    def clear_board(self):
        self.board_widget.board.clear()
        self.board_widget.best_moves = []
        self.board_widget.update_board()

    def set_fen_position(self):
        fen = self.fen_input.text()
        self.board_widget.set_fen(fen)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    engine_path = "/usr/bin/stockfish"  # Adjust path as needed
    # engine_path = "C:\\Users\\LPC\\Documents\\Programs\\ChessEngine\\x64\\Debug\\ChessEngine.exe"
    window = BoardEditor(engine_path)
    window.show()
    sys.exit(app.exec())
