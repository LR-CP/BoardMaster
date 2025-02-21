import chess
import chess.pgn
import chess.engine
import chess.svg
import io
from PySide6.QtWidgets import *
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QByteArray, QSettings, Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPixmap, QPen, QFont
import math
from utils import MoveRow

# Updated CustomSVGWidget for centered square overlays and drag overlay
class CustomSVGWidget(QSvgWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.squares = {}  # {square: QColor, ...}
        self.square_size = 70
        self.drag_info = {}  # New: info dict passed from GameTab
        self.highlight_moves = []  # NEW: squares to highlight
        self.last_move_eval = None  # NEW: Store evaluation symbol for last move
        self.flipped = False

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        board_size = 8 * self.square_size
        global_offset = (self.width() - board_size) / 2
        inner_offset = 0  # simplified

        def get_square_coordinates(square, type=None):
            f = chess.square_file(square)
            r = chess.square_rank(square)
            if type is not None and self.flipped:
                return 7 - f, r     # Flip file, keep rank as-is
            else:
                return f, 7 - r     # Normal: invert rank for top-left origin

        # Draw square overlays
        for square, color in self.squares.items():
            disp_file, disp_rank = get_square_coordinates(square)
            x = global_offset + disp_file * self.square_size + inner_offset
            y = global_offset + disp_rank * self.square_size + inner_offset
            painter.fillRect(x, y, self.square_size, self.square_size, color)

        # Draw highlighted circles for legal moves
        if self.highlight_moves:
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor(0, 150, 0, 200), 2)
            painter.setPen(pen)
            brush = QColor(0, 150, 0, 100)
            painter.setBrush(brush)
            for sq in self.highlight_moves:
                file, rank = get_square_coordinates(sq)
                x = global_offset + file * self.square_size
                y = global_offset + rank * self.square_size
                center = QPointF(x + self.square_size / 2, y + self.square_size / 2)
                radius = self.square_size / 5
                painter.drawEllipse(center, radius, radius)

        # Draw drag info
        if self.drag_info.get("dragging"):
            pixmap = self.drag_info.get("pixmap")
            pos = self.drag_info.get("drag_current_pos")
            offset = self.drag_info.get("drag_offset")
            if pixmap and pos and offset:
                target = pos - offset
                painter.drawPixmap(target, pixmap)

        # Draw evaluation symbol with correct coordinates
        if self.last_move_eval:
            painter.setFont(QFont('Segoe UI Symbol', int(self.square_size/3)))
            last_move = self.last_move_eval['move']
            eval_symbol = self.last_move_eval['symbol']
            disp_file, disp_rank = get_square_coordinates(last_move.to_square, "symbol")
            x = global_offset + disp_file * self.square_size
            y = global_offset + disp_rank * self.square_size
            painter.drawText(QRectF(x, y, self.square_size, self.square_size), 
                           Qt.AlignCenter, eval_symbol)
        painter.end()

class GameTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = parent.engine
        self.settings = QSettings("BoardMaster", "BoardMaster")
        self.current_game = None
        self.current_board = chess.Board()
        self.moves = []  # Main line moves
        self.variations = {}  # Dictionary to store variations: {move_index: [variation_moves]}
        self.current_variation = None  # Tuple of (start_index, variation_index)
        self.played_moves = []
        self.current_move_index = 0
        self.move_evaluations = []
        self.variation_evaluations = {}  # Dictionary to store evaluations for variations
        self.selected_square = None
        self.legal_moves = set()
        self.square_size = 70
        self.flipped = False
        self.is_live_game = True
        self.dragging = False
        self.drag_start_square = None
        self.drag_current_pos = None
        self.drag_offset = None

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
        # Use our custom SVG widget
        self.board_display = CustomSVGWidget(self)
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
        self.move_list.setStyleSheet("""
            QListWidget {
                background-color: grey;
                border: 1px solid #ccc;
            }
            QListWidget::item {
                padding: 2px;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)
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
        self.progress = QProgressDialog(
            labelText=text, cancelButtonText=None, minimum=0, maximum=max, parent=self
        )
        self.progress.setWindowTitle(title)
        self.progress.setWindowModality(Qt.WindowModality.NonModal)
        self.progress.setMinimumDuration(0)
        self.progress.setCancelButton(None)
        self.progress.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint  # Keeps dialog on top while allowing window movement
        )
        self.progress.setValue(1)
        return self.progress

    def load_pgn(self, pgn_string):
        self.is_live_game = False
        self.current_variation = None
        self.variations = {}
        self.variation_evaluations = {}
        try:
            hdrs_io = io.StringIO(pgn_string)
            hdrs = chess.pgn.read_headers(hdrs_io)
            self.game_details.setText(
                f"White: {hdrs.get("White")}({hdrs.get("WhiteElo")})\nBlack: {hdrs.get("Black")}({hdrs.get("BlackElo")})\n{hdrs.get("Date")}\nResult: {hdrs.get("Termination")}\n\n\nOpening: {hdrs.get("Opening")}"
            )
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
        self.accuracies = {"white": [], "black": []}
        self.move_evaluations_scores = []

        def calculate_accuracy(eval_diff, position_eval):
            """
            Calculate move accuracy using a more sophisticated formula that considers:
            1. The absolute evaluation difference
            2. The current position's evaluation
            3. Different scaling for winning/losing positions
            """
            # Base scaling factor
            max_loss = 300  # Maximum centipawn loss before accuracy drops significantly
            
            # Adjust scaling based on position
            if abs(position_eval) > 200:
                # In clearly winning/losing positions, be more lenient
                max_loss *= 1.5
            elif abs(position_eval) < 50:
                # In equal positions, be more strict
                max_loss *= 0.8
                
            # Calculate base accuracy
            accuracy = max(0, 100 * (1 - (eval_diff / max_loss) ** 0.5))
            
            # Additional penalties for very large mistakes
            if eval_diff > max_loss * 2:
                accuracy *= 0.5
            
            return max(0, min(100, accuracy))

        for i, move in enumerate(self.moves):
            if temp_board.is_game_over():
                break

            # Get evaluation before the move
            pre_move_analysis = self.engine.analyse(
                temp_board,
                chess.engine.Limit(time=self.settings.value("analysis/fulltime", 0.1, int)),
                multipv=1
            )
            pre_move_eval = self.eval_to_cp(pre_move_analysis[0]["score"].relative)

            # Make the move
            temp_board.push(move)

            # Get evaluation after the move
            post_move_analysis = self.engine.analyse(
                temp_board,
                chess.engine.Limit(time=self.settings.value("analysis/fulltime", 0.1, int)),
                multipv=1
            )
            post_move_eval = -self.eval_to_cp(post_move_analysis[0]["score"].relative)

            # Calculate evaluation difference
            eval_diff = abs(post_move_eval - pre_move_eval)
            
            # Store the evaluation for position display
            self.move_evaluations_scores.append(post_move_eval)

            # Calculate accuracy
            accuracy = calculate_accuracy(eval_diff, pre_move_eval)

            # Store accuracy
            if i % 2 == 0:  # White's move
                self.accuracies["white"].append(accuracy)
            else:  # Black's move
                self.accuracies["black"].append(accuracy)

            # Annotate move based on eval difference and position context
            # These thresholds are now relative to the position's evaluation
            base_threshold = 25 if abs(pre_move_eval) < 200 else 40
            
            evaluation = ""
            if eval_diff < base_threshold:
                evaluation = "✅"  # Excellent / Best move
            elif eval_diff < base_threshold * 2:
                evaluation = "👍"  # Good move
            elif eval_diff < base_threshold * 4:
                evaluation = "⚠️"  # Inaccuracy
            elif eval_diff < base_threshold * 8:
                evaluation = "❌"  # Mistake
            else:
                evaluation = "🔥"  # Blunder

            self.move_evaluations.append(evaluation)

            # Update progress bar
            self.progress.setValue(i + 1)
            QApplication.processEvents()

        # Calculate final accuracy scores
        self.white_accuracy = (
            round(sum(self.accuracies["white"]) / len(self.accuracies["white"]), 2)
            if self.accuracies["white"]
            else 0
        )
        self.black_accuracy = (
            round(sum(self.accuracies["black"]) / len(self.accuracies["black"]), 2)
            if self.accuracies["black"]
            else 0
        )

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
            if eval == "✅" and i % 2 == 1
        )
        black_good = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "👍" and i % 2 == 1
        )
        black_inacc = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "⚠️" and i % 2 == 1
        )
        black_mistake = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "❌" and i % 2 == 1
        )
        black_blunder = sum(
            1
            for i, eval in enumerate(self.move_evaluations)
            if eval == "🔥" and i % 2 == 1
        )

        summary = f"""Game Summary:
White (Accuracy: {self.white_accuracy}): Excellent: {white_excellent}✅, Good: {white_good}👍, Inaccuracy: {white_inacc}⚠️, Mistake: {white_mistake}❌, Blunder: {white_blunder}🔥
Black (Accuracy: {self.black_accuracy}): Excellent: {black_excellent}✅, Good: {black_good}👍, Inaccuracy: {black_inacc}⚠️, Mistake: {black_mistake}❌, Blunder: {black_blunder}🔥"""
        self.summary_label.setText(summary)

    def eval_to_cp(self, eval_score):
        """Convert evaluation to centipawns, handles Mate cases."""
        if eval_score.is_mate():
            # Convert mate scores to high centipawn values
            if eval_score.mate() > 0:
                return 20000 - eval_score.mate() * 10
            else:
                return -20000 - eval_score.mate() * 10
        return eval_score.score()
    
    def get_logical_square(self, square):
        """Convert a board square to its flipped equivalent if board is flipped"""
        if self.flipped:
            return chess.square(7 - chess.square_file(square), 7 - chess.square_rank(square))
        return square

    def update_display(self):
        arrows = []
        annotations = {}
        eval_score = 0  # Default value
        squares = {}  # This dict will be used for colored square overlays

        if not self.current_board.is_game_over() and self.settings.value("display/show_arrows", True, bool):
            info = self.engine.analyse(
                self.current_board,
                chess.engine.Limit(time=self.settings.value("analysis/postime", 0.1, float)),
                multipv=self.settings.value("engine/lines", 3, int)
            )
            main_eval = info[0]["score"].relative
            eval_score = self.eval_to_cp(main_eval) if hasattr(self, 'eval_to_cp') else 0
            analysis_text = f"Move {(self.current_move_index + 1) // 2} "
            analysis_text += f"({'White' if self.current_move_index % 2 == 0 else 'Black'})\n\n"
            analysis_text += "Top moves:\n"
            for i, pv in enumerate(info, 1):
                move = pv["pv"][0]
                score = self.eval_to_cp(pv["score"].relative) if hasattr(self, 'eval_to_cp') else 0
                analysis_text += f"{i}. {self.current_board.san(move)} (eval: {score/100:+.2f})\n"
                # Retain annotation arrows for best moves
                color = QColor("#00ff00") if i <= 1 else QColor("#007000")
                arrows.append(chess.svg.Arrow(
                    tail=move.from_square,
                    head=move.to_square,
                    color=color.name()
                ))
                annotations[move.to_square] = f"{score/100.0:.2f}"
            self.analysis_text.setText(analysis_text)

        if self.current_move_index > 0 and hasattr(self, 'move_evaluations_scores'):
            if self.current_move_index - 1 < len(self.move_evaluations_scores):
                eval_score = self.move_evaluations_scores[self.current_move_index - 1]
            else:
                info = self.engine.analyse(
                    self.current_board,
                    chess.engine.Limit(time=self.settings.value("analysis/postime", 0.1, float)),
                    multipv=1
                )
                eval_score = self.eval_to_cp(info[0]["score"].relative)

        if self.selected_square is not None:
            squares[self.selected_square] = QColor(100, 100, 0, 100)
            for move in self.legal_moves:
                squares[move.to_square] = QColor(0, 100, 0, 100)

        # Overlay a transparent purple square on the destination of the most recent move.
        if self.current_move_index > 0 and self.moves:
            last_move = self.moves[self.current_move_index - 1]
            # Convert move squares to match the display orientation
            display_to_square = self.get_logical_square(last_move.to_square)
            display_from_square = self.get_logical_square(last_move.from_square)
            squares[display_to_square] = QColor(128, 0, 128, 100)
            squares[display_from_square] = QColor(128, 0, 128, 100)

        # Make the king glow red when in check or mate.
        if self.current_board.is_check():
            king_square = self.current_board.king(self.current_board.turn)
            if king_square is not None:
                display_king_square = self.get_logical_square(king_square)
                squares[display_king_square] = QColor(255, 0, 0, 150)

        # Generate the base SVG board (without overlays)
        board_svg = chess.svg.board(
            self.current_board,
            arrows=arrows,
            size=600,
            orientation=chess.BLACK if self.flipped else chess.WHITE
        )
        self.board_display.load(QByteArray(board_svg.encode("utf-8")))
        # Pass the computed squares into our custom widget so its paintEvent draws centered overlays.
        self.board_display.squares = squares
        # NEW: Pass drag info if dragging is active
        if self.dragging and self.drag_current_pos and self.drag_offset:
            piece = self.current_board.piece_at(self.drag_start_square)
            if piece:
                self.board_display.drag_info = {
                    "dragging": True,
                    "drag_current_pos": self.drag_current_pos,
                    "drag_offset": self.drag_offset,
                    "pixmap": self.get_piece_pixmap(piece)
                }
            else:
                self.board_display.drag_info = {"dragging": False}
        else:
            self.board_display.drag_info = {"dragging": False}
        
        # Update last move evaluation display
        if self.current_move_index > 0 and self.moves:
            last_move = self.moves[self.current_move_index - 1]
            if self.current_move_index - 1 < len(self.move_evaluations):
                self.board_display.last_move_eval = {
                    'move': last_move,
                    'symbol': self.move_evaluations[self.current_move_index - 1]
                }
            else:
                self.board_display.last_move_eval = None
        else:
            self.board_display.last_move_eval = None

        self.board_display.repaint()

        self.win_bar.setStyleSheet(
            f"background: qlineargradient(y1:0, y2:1, stop:0 white, stop:{max(0, min(100, 50 + (50 * (2 / (1+math.exp(-eval_score/400)) - 1)) ))/100} white, "
            f"stop:{max(0, min(100, 50 + (50 * (2 / (1+math.exp(-eval_score/400)) - 1)) ))/100} black, stop:1 black);"
        )
        self.fen_box.setText(f"FEN: {self.current_board.fen()}")

        # Update move list
        self.move_list.clear()
        temp_board = chess.Board()
        move_number = 1
        i = 0
        
        while i < len(self.moves):
            # Get white's move
            white_move = temp_board.san(self.moves[i])
            white_eval = self.move_evaluations[i] if i < len(self.move_evaluations) else ""
            temp_board.push(self.moves[i])
            
            # Get black's move if available
            black_move = None
            black_eval = None
            if i + 1 < len(self.moves):
                black_move = temp_board.san(self.moves[i + 1])
                black_eval = self.move_evaluations[i + 1] if i + 1 < len(self.move_evaluations) else ""
                temp_board.push(self.moves[i + 1])
            
            # Create custom widget for the move pair
            move_widget = MoveRow(
                move_number, 
                white_move, white_eval, i,
                self,
                black_move, black_eval, i + 1 if black_move else None
            )
            
            # Add variations if they exist at this move
            if i in self.variations:
                for var_index, variation in enumerate(self.variations[i]):
                    var_temp_board = temp_board.copy()
                    var_move_number = move_number
                    
                    # Create a variation row with indentation
                    variation_text = "    Variation {}: ".format(var_index + 1)
                    for j, var_move in enumerate(variation):
                        move_san = var_temp_board.san(var_move)
                        eval_symbol = self.variation_evaluations[i][var_index][j] if i in self.variation_evaluations else ""
                        variation_text += f"{move_san}{eval_symbol} "
                        var_temp_board.push(var_move)
                    
                    var_item = QListWidgetItem(variation_text)
                    var_item.setForeground(Qt.GlobalColor.blue)  # Make variations blue
                    self.move_list.addItem(var_item)
            
            # Create list item and set custom widget for main line
            item = QListWidgetItem(self.move_list)
            item.setSizeHint(move_widget.sizeHint())
            self.move_list.addItem(item)
            self.move_list.setItemWidget(item, move_widget)
            
            # NEW: Highlight current move
            if i < self.current_move_index <= i + 1:
                move_widget.highlight_white()
            elif i + 1 < self.current_move_index <= i + 2:
                move_widget.highlight_black()
            else:
                move_widget.highlight_off()
            
            i += 2
            move_number += 1

        # Highlight current move's row
        if self.current_move_index > 0:
            row = (self.current_move_index - 1) // 2
            self.move_list.setCurrentRow(row)

        # self.analyze_position() # Remove this for pre analysis (keep for move based analysis)

    def analyze_position(self):
        if not self.current_board.is_game_over():
            info = self.engine.analyse(
                self.current_board,
                chess.engine.Limit(
                    time=self.settings.value("analysis/postime", 0.1, float)
                ),
                multipv=self.settings.value("engine/lines", 3, int),
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
        # Get the stored move indices
        move_indices = item.data(Qt.ItemDataRole.UserRole)
        
        # If clicked on a move pair, determine which move to go to based on current position
        if isinstance(move_indices, tuple):
            white_index, black_index = move_indices
            
            # If we're before or at white's move, go to white's move
            if self.current_move_index <= white_index:
                self.goto_move(white_index)
            # If we're at black's move or after, go to black's move
            elif self.current_move_index > white_index and black_index < len(self.moves):
                self.goto_move(black_index)
            # If black has no move, go to white's move
            else:
                self.goto_move(white_index)

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
        self.board_display.flipped = self.flipped
        self.board_orientation = not getattr(self, "board_orientation", False)
        self.update_display()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.prev_move()
        elif event.key() == Qt.Key_Right:
            self.next_move()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        pos = event.localPos()  # use localPos for consistency
        
        # Adjust coordinate calculation based on board orientation
        if self.flipped:
            file_idx = 7 - int(pos.x() // self.square_size)
            rank_idx = int(pos.y() // self.square_size)
        else:
            file_idx = int(pos.x() // self.square_size)
            rank_idx = 7 - int(pos.y() // self.square_size)
            
        square = chess.square(file_idx, rank_idx)
        piece = self.current_board.piece_at(square)
        if event.button() == Qt.LeftButton and piece:
            legal = [move for move in self.current_board.legal_moves if move.from_square == square]
            self.board_display.highlight_moves = [move.to_square for move in legal]
            self.selected_square = square
            self.board_display.update()
            self.dragging = True
            self.drag_start_square = square
            
            # Compute correct position based on orientation
            global_offset = (self.board_display.width() - (self.square_size * 8)) / 2
            if self.flipped:
                target_top_left = QPointF(global_offset + (7 - file_idx) * self.square_size,
                                        global_offset + rank_idx * self.square_size)
            else:
                target_top_left = QPointF(global_offset + file_idx * self.square_size,
                                        global_offset + (7 - rank_idx) * self.square_size)
                                        
            self.drag_offset = pos - target_top_left
            self.drag_current_pos = pos
            
            self.board_display.drag_info = {
                "dragging": True,
                "drag_current_pos": self.drag_current_pos,
                "drag_offset": self.drag_offset,
                "pixmap": self.get_piece_pixmap(piece)
            }
        else:
            super().mousePressEvent(event)
        self.board_display.repaint()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.drag_current_pos = event.localPos()
            if self.is_live_game is False:
                y_off = 129
            else:
                y_off = 89
            self.drag_current_pos = QPointF(self.drag_current_pos.x() - 44, self.drag_current_pos.y() - y_off)
            # Do not update drag_offset; use the stored value from mousePressEvent
            piece = self.current_board.piece_at(self.drag_start_square)
            if piece:
                self.board_display.drag_info = {
                    "dragging": True,
                    "drag_current_pos": self.drag_current_pos,
                    "drag_offset": self.drag_offset,
                    "pixmap": self.get_piece_pixmap(piece)
                }
            self.board_display.repaint()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging:
            pos = event.localPos()
            if self.is_live_game is False:
                pos = pos - QPointF(44, 129)
            else:
                pos = pos - QPointF(44, 89)
                
            # Adjust coordinate calculation based on board orientation
            if self.flipped:
                file_idx = 7 - int(pos.x() // self.square_size)
                rank_idx = int(pos.y() // self.square_size)
            else:
                file_idx = int(pos.x() // self.square_size)
                rank_idx = 7 - int(pos.y() // self.square_size)
                
            drop_square = chess.square(file_idx, rank_idx)
            move = chess.Move(self.drag_start_square, drop_square)
            if move in self.current_board.legal_moves:
                self.current_board.push(move)
                # Only add/update the move for live games
                if self.is_live_game:
                    # If we're not at the end of the move list, truncate it
                    if self.current_move_index < len(self.moves):
                        self.moves = self.moves[:self.current_move_index]
                        if hasattr(self, 'move_evaluations'):
                            self.move_evaluations = self.move_evaluations[:self.current_move_index]
                    self.moves.append(move)
                    self.current_move_index += 1
                    # Clear last_move_eval since this is a live game move
                    self.board_display.last_move_eval = None

            self.dragging = False
            self.drag_start_square = None
            self.drag_current_pos = None
            self.drag_offset = None
            self.board_display.drag_info = {"dragging": False}
            self.board_display.highlight_moves = []  # Clear highlights
            self.update_display()  # full update after move
        else:
            super().mouseReleaseEvent(event)

    # NEW: Updated helper to load piece image with fallback if not found
    def get_piece_pixmap(self, piece):
        prefix = "w" if piece.color == chess.WHITE else "b"
        letter = piece.symbol().upper()
        path = f"c:/Users/LPC/Documents/Programs/BoardMaster/piece_images/{prefix.lower()}{letter.lower()}.png"
        pixmap = QPixmap(path)
        if pixmap.isNull():
            print(f"Error: Failed to load image from {path}")
            pixmap = QPixmap(self.square_size, self.square_size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setPen(Qt.black)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, piece.symbol())
            painter.end()
        return pixmap.scaled(self.square_size, self.square_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)