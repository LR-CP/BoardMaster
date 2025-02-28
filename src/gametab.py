import chess
import chess.pgn
import chess.engine
import chess.svg
import io
import json
from PySide6.QtWidgets import *
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QByteArray, QSettings, Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPixmap, QPen, QFont
import math
from utils import MoveRow, EvaluationGraphPG

#TODO: Add feature to load fen on live game tab
#TODO: Add board editor feature to live game tab

class CustomSVGWidget(QSvgWidget):
    def __init__(self, parent=None):
        """
        @brief Initialize the custom SVG widget for board overlays.
        @param parent Parent widget.
        """
        super().__init__(parent)
        self.squares = {}  # {square: QColor, ...}
        self.square_size = 70
        self.drag_info = {}  # New: info dict passed from GameTab
        self.highlight_moves = []  # NEW: squares to highlight
        self.last_move_eval = None  # NEW: Store evaluation symbol for last move
        self.flipped = False
        self.user_circles = set()  # Initialize user_circles as empty set

    def paintEvent(self, event):
        """
        @brief Overridden paint event to draw highlights, drag images and evaluation symbols.
        @param event The paint event.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        board_size = 8 * self.square_size
        global_offset = (self.width() - board_size) / 2
        inner_offset = 0  # simplified

        def get_square_coordinates(square, type=None):
            f = chess.square_file(square)
            r = chess.square_rank(square)
            if type is not None and self.flipped:
                return 7 - f, r  # Flip file, keep rank as-is
            else:
                return f, 7 - r  # Normal: invert rank for top-left origin

        def get_square_center(square):
            disp_file, disp_rank = get_square_coordinates(square)
            x = global_offset + disp_file * self.square_size + self.square_size/2
            y = global_offset + disp_rank * self.square_size + self.square_size/2
            return QPointF(x, y)

        # Draw square overlays
        for square, color in self.squares.items(): # For mouse release yellow highlight of clicked piece
            disp_file, disp_rank = get_square_coordinates(square, "clicked")
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
                file, rank = get_square_coordinates(sq, "circles")
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
            
        pen = QPen(QColor(255, 170, 0, 160), 5)
        painter.setPen(pen)
        # Find the top-level GameTab widget that has our arrows and current_arrow attributes.
        game_tab = self.parent()
        while game_tab and not hasattr(game_tab, 'arrows'):
            game_tab = game_tab.parent()
        
        # Draw each committed arrow from the GameTab instance
        if game_tab is not None:
            for arrow in game_tab.arrows:
                start_sq, end_sq = arrow
                start_center = get_square_center(start_sq)
                end_center = get_square_center(end_sq)
                painter.drawLine(start_center, end_center)
        
            # Draw current (temporary) arrow during right-click drag
            if game_tab is not None and game_tab.current_arrow is not None:
                start_sq, end_sq = game_tab.current_arrow
                start_center = get_square_center(start_sq)
                end_center = get_square_center(end_sq)
                painter.drawLine(start_center, end_center)

        # Draw user circles
        if hasattr(self, 'user_circles') and self.user_circles:
            painter.setRenderHint(QPainter.Antialiasing, True)
            # Use a thick pen and no fill to draw an open circle covering the square
            pen = QPen(QColor(255, 170, 0, 160), 4)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            for sq in self.user_circles:
                # Compute top-left and center for the square
                f, r = chess.square_file(sq), chess.square_rank(sq)
                # If flipped, adjust file
                if self.flipped:
                    f = 7 - f
                disp_x = global_offset + f * self.square_size
                disp_y = global_offset + (7 - r) * self.square_size
                # Draw an open circle that nearly fills the square.
                margin = 4
                center = QPointF(disp_x + self.square_size/2, disp_y + self.square_size/2)
                radius = (self.square_size / 2) - margin
                painter.drawEllipse(center, radius, radius)
        
        painter.end()
        

class GameTab(QWidget):
    def __init__(self, parent=None):
        """
        @brief Initialize a game analysis tab.
        @param parent Parent widget (typically the main window).
        """
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
        self.move_evaluations_scores = []  # existing evaluations list for graphing
        self.white_moves = [] # NEW: store white evaluations per move pair
        self.black_moves = [] # NEW: store black evaluations per move pair
        self.arrows = []           # List of committed arrows as tuples: (start_square, end_square)
        self.arrow_start = None    # Starting square for the current arrow drawing
        self.current_arrow = None
        self.user_circles = set()  # NEW: Set of squares with circle markers
        self.show_arrows = True  # Add this after other initializations
        self.last_shown_game_over = False  # Add this to track if we've shown the game over dialog
        self.has_been_analyzed = False  # Add this new flag
        self.move_notes = {}  # Add this new dict to store move notes

        # NEW: Initialize accuracy attributes to avoid attribute errors
        self.white_accuracy = 0
        self.black_accuracy = 0

        self.create_gui()

    def create_gui(self):
        """
        @brief Create and arrange the GUI elements for the game tab.
        """
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
        
        self.arrow_button = QPushButton("Arrows: ✅")
        self.arrow_button.clicked.connect(self.arrow_toggle)
        nav_layout.addWidget(self.arrow_button)

        # Add analyze button
        self.analyze_button = QPushButton("Analyze Game")
        self.analyze_button.clicked.connect(self.analyze_completed_game)
        self.analyze_button.setVisible(False)  # Initially hidden
        nav_layout.addWidget(self.analyze_button)

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

        # NEW: Add evaluation graph widget below analysis text
        self.eval_graph = EvaluationGraphPG(self)
        right_layout.addWidget(self.eval_graph)

        layout.addWidget(left_panel)
        layout.addWidget(right_panel)
        self.update_display()

        # Connect mouse events
        self.board_display.mousePressEvent = self.mousePressEvent

    def show_loading(self, title="Loading...", text="Analyzing game...", max=0):
        """
        @brief Show a loading dialog for long-running analysis.
        @param title Title for the dialog.
        @param text Message text.
        @param max Maximum progress value.
        @return The progress dialog.
        """
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
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.progress.setValue(1)
        return self.progress

    def load_pgn(self, pgn_string):
        """
        Load a PGN game from a provided PGN string.
        Returns True if loaded successfully; otherwise False.
        """
        self.is_live_game = False
        self.current_variation = None
        self.variations = {}
        self.variation_evaluations = {}
        try:
            # Read the game once from the PGN string.
            pgn_io = io.StringIO(pgn_string)
            self.current_game = chess.pgn.read_game(pgn_io)
            if not self.current_game:
                return False
            # Save headers from the loaded game.
            self.hdrs = self.current_game.headers
            self.game_details.setText(
                f"White: {self.hdrs.get('White')}({self.hdrs.get('WhiteElo')})\n"
                f"Black: {self.hdrs.get('Black')}({self.hdrs.get('BlackElo')})\n"
                f"{self.hdrs.get('Date')}\nResult: {self.hdrs.get('Termination')}\n\n\n"
                f"Opening: {self.hdrs.get('Opening')}"
            )
        except Exception as e:
            print(f"Error loading game: {str(e)}")
            return False
        try:
            self.moves = list(self.current_game.mainline_moves())
            total_moves = len(self.moves)
            self.loading_bar = self.show_loading(max=total_moves)
            self.progress.setMaximum(total_moves)
            self.current_board = self.current_game.board()
            self.current_move_index = 0
            self.has_been_analyzed = False
            self.analyze_button.setVisible(True)
            self.update_display()
            self.update_game_summary()
            self.loading_bar.close()
            return True
        except Exception as e:
            print(f"Error loading game: {str(e)}")
            return False

    def analyze_all_moves(self):
        """
        @brief Analyze all moves of the loaded game to calculate evaluations and accuracies.
        """
        temp_board = chess.Board()
        self.move_evaluations = []
        self.accuracies = {"white": [], "black": []}
        self.move_evaluations_scores = []

        def calculate_accuracy(eval_diff, position_eval):
            """
            Calculate move accuracy using a more sophisticated formula.
            """
            max_loss = 300  
            if abs(position_eval) > 200:
                max_loss *= 1.5
            elif abs(position_eval) < 50:
                max_loss *= 0.8
            accuracy = max(0, 100 * (1 - (eval_diff / max_loss) ** 0.5))
            if eval_diff > max_loss * 2:
                accuracy *= 0.5
            return max(0, min(100, accuracy))

        for i, move in enumerate(self.moves):
            if temp_board.is_game_over():
                break

            pre_move_analysis = self.engine.analyse(
                temp_board,
                chess.engine.Limit(time=self.settings.value("analysis/fulltime", 0.1, int)),
                multipv=1
            )
            pre_move_eval = self.eval_to_cp(pre_move_analysis[0]["score"].relative)
            temp_board.push(move)
            post_move_analysis = self.engine.analyse(
                temp_board,
                chess.engine.Limit(time=self.settings.value("analysis/fulltime", 0.1, int)),
                multipv=1
            )
            post_move_eval = -self.eval_to_cp(post_move_analysis[0]["score"].relative)
            eval_diff = abs(post_move_eval - pre_move_eval)
            self.move_evaluations_scores.append(post_move_eval)
            accuracy = calculate_accuracy(eval_diff, pre_move_eval)
            if i % 2 == 0:
                self.accuracies["white"].append(accuracy)
            else:
                self.accuracies["black"].append(accuracy)
            base_threshold = 25 if abs(pre_move_eval) < 200 else 40
            evaluation = ""
            if eval_diff < base_threshold:
                evaluation = "✅"
            elif eval_diff < base_threshold * 2:
                evaluation = "👍"
            elif eval_diff < base_threshold * 4:
                evaluation = "⚠️"
            elif eval_diff < base_threshold * 8:
                evaluation = "❌"
            else:
                evaluation = "🔥"
            self.move_evaluations.append(evaluation)
            self.progress.setValue(i + 1)
            QApplication.processEvents()

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
        """
        @brief Update the game summary based on move evaluations.
        """
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
        """
        @brief Convert an evaluation object to centipawns.
        @param eval_score The evaluation score object.
        @return The centipawn value.
        """
        if eval_score.is_mate():
            if eval_score.mate() > 0:
                return 20000 - eval_score.mate() * 10
            else:
                return -20000 - eval_score.mate() * 10
        return eval_score.score()

    def update_display(self):
        """
        @brief Update the board display, move list and evaluation graph.
        """
        arrows = []
        annotations = {}
        eval_score = 0
        squares = {}

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
                if "pv" in pv.keys():
                    move = pv["pv"][0]
                    score = self.eval_to_cp(pv["score"].relative) if hasattr(self, 'eval_to_cp') else 0
                    analysis_text += f"{i}. {self.current_board.san(move)} (eval: {score/100:+.2f})\n"
                    color = QColor("#00ff00") if i <= 1 else QColor("#007000")
                    if self.show_arrows:
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

        if self.current_move_index > 0 and self.moves:
            last_move = self.moves[self.current_move_index - 1]
            squares[last_move.to_square] = QColor(128, 0, 128, 100)
            squares[last_move.from_square] = QColor(128, 0, 128, 100)

        if self.current_board.is_check():
            king_square = self.current_board.king(self.current_board.turn)
            if king_square is not None:
                squares[king_square] = QColor(255, 0, 0, 150)

        board_svg = chess.svg.board(
            self.current_board,
            arrows=arrows,
            size=600,
            orientation=chess.BLACK if self.flipped else chess.WHITE
        )
        self.board_display.load(QByteArray(board_svg.encode("utf-8")))
        self.board_display.squares = squares
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

        self.move_list.clear()
        temp_board = chess.Board()
        move_number = 1
        i = 0
        
        while i < len(self.moves):
            white_move = temp_board.san(self.moves[i])
            white_eval = self.move_evaluations[i] if i < len(self.move_evaluations) else ""
            temp_board.push(self.moves[i])
            
            black_move = None
            black_eval = None
            if i + 1 < len(self.moves):
                black_move = temp_board.san(self.moves[i + 1])
                black_eval = self.move_evaluations[i + 1] if i + 1 < len(self.move_evaluations) else ""
                temp_board.push(self.moves[i + 1])
            
            move_widget = MoveRow(
                move_number, 
                white_move, white_eval, i,
                self,
                black_move, black_eval, i + 1 if black_move else None
            )
            
            if i in self.variations:
                for var_index, variation in enumerate(self.variations[i]):
                    var_temp_board = temp_board.copy()
                    var_move_number = move_number
                    variation_text = "    Variation {}: ".format(var_index + 1)
                    for j, var_move in enumerate(variation):
                        move_san = var_temp_board.san(var_move)
                        eval_symbol = self.variation_evaluations[i][var_index][j] if i in self.variation_evaluations else ""
                        variation_text += f"{move_san}{eval_symbol} "
                        var_temp_board.push(var_move)
                    var_item = QListWidgetItem(variation_text)
                    var_item.setForeground(Qt.GlobalColor.blue)
                    self.move_list.addItem(var_item)
            
            item = QListWidgetItem(self.move_list)
            item.setSizeHint(move_widget.sizeHint())
            self.move_list.addItem(item)
            self.move_list.setItemWidget(item, move_widget)
            
            if i < self.current_move_index <= i + 1:
                move_widget.highlight_white()
            elif i + 1 < self.current_move_index <= i + 2:
                move_widget.highlight_black()
            else:
                move_widget.highlight_off()
            
            note_dict = {}
            for k, v in self.move_notes.items():
                note_dict[int(k) if isinstance(k, str) else k] = v
            self.move_notes = note_dict

            # Then apply to move widgets
            if i in self.move_notes:
                move_widget.white_label.note = self.move_notes[i]
                move_widget.white_label.setToolTip(f"Note: {self.move_notes[i]}")
                move_widget.white_label.update_style()
                
            if i + 1 in self.move_notes and black_move:
                move_widget.black_label.note = self.move_notes[i + 1]
                move_widget.black_label.setToolTip(f"Note: {self.move_notes[i + 1]}")
                move_widget.black_label.update_style()
            
            i += 2
            move_number += 1

        if self.current_move_index > 0:
            row = (self.current_move_index - 1) // 2
            self.move_list.setCurrentRow(row)
        
        self.white_moves = []
        self.black_moves = []
        board = chess.Board()
        for i, move in enumerate(self.moves):
            board.push(move)
            if i % 2 == 0:
                if i < len(self.move_evaluations_scores):
                    self.white_moves.append(self.move_evaluations_scores[i])
            else:
                if i < len(self.move_evaluations_scores):
                    self.black_moves.append(self.move_evaluations_scores[i])
        self.eval_graph.update_graph(self.white_moves, self.black_moves)
        self.eval_graph.set_current_move((self.current_move_index + 1) // 2)
        self.check_game_over()

    def analyze_position(self):
        """
        @brief Analyze the current board position and update analysis text.
        """
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
        """
        @brief Handle selection of a move from the move list.
        @param item The selected QListWidgetItem.
        """
        move_indices = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(move_indices, tuple):
            white_index, black_index = move_indices
            if self.current_move_index <= white_index:
                self.goto_move(white_index)
            elif self.current_move_index > white_index and black_index < len(self.moves):
                self.goto_move(black_index)
            else:
                self.goto_move(white_index)

    def goto_move(self, index):
        """
        @brief Jump to the specified move index in the game.
        @param index The move index.
        """
        self.current_board = chess.Board()
        for i in range(index + 1):
            self.current_board.push(self.moves[i])
        self.current_move_index = index + 1
        self.update_display()

    def next_move(self):
        """
        @brief Advance the game by one move.
        """
        if self.current_move_index < len(self.moves):
            self.current_board.push(self.moves[self.current_move_index])
            self.current_move_index += 1
            self.update_display()

    def export_pgn(self):
        """Rebuild and return a full PGN string directly from headers and moves."""
        game = chess.pgn.Game()

        # Apply headers if available
        if hasattr(self, 'hdrs') and self.hdrs:
            for key, value in self.hdrs.items():
                game.headers[key] = value

        # Fix the Termination/Result header
        if "Termination" in game.headers:
            game.headers["Result"] = game.headers.pop("Termination", "*")

        # Rebuild the mainline moves
        node = game
        for move in self.moves:
            node = node.add_main_variation(move)

        # Convert game to PGN string
        pgn_text = str(game)

        # Create a filename
        filename = (
            f"{game.headers.get('White', 'White')}_"
            f"{game.headers.get('Black', 'Black')}_"
            f"{game.headers.get('Date', 'Unknown').replace('.', '_')}.pgn"
        )
        json_filename = (
            f"{game.headers.get('White', 'White')}_"
            f"{game.headers.get('Black', 'Black')}_"
            f"{game.headers.get('Date', 'Unknown').replace('.', '_')}.pgn"
        )

        return pgn_text, filename

    ## NEW METHODS FOR SAVING/LOADING ANALYSIS ##
    def rebuild_pgn_from_move_list(self):
        """
        Rebuild the PGN directly from the move_list (the visible move list widget).
        This ensures that the saved PGN reflects exactly what the user sees, including notes.
        """
        # Apply headers if available
        if hasattr(self, 'hdrs') and self.hdrs:
            for key, value in self.hdrs.items():
                self.current_game.headers[key] = value

        if "Termination" in self.current_game.headers:
            self.current_game.headers["Result"] = self.current_game.headers.pop("Termination", "*")

        node = self.current_game

        move_count = len(self.moves)
        for row in range(self.move_list.count()):
            item = self.move_list.item(row)
            move_row = self.move_list.itemWidget(item)

            if not isinstance(move_row, MoveRow):
                continue  # Skip non-move rows like variation headers if they exist.

            # Process white move (always present in MoveRow)
            if move_row.white_label:
                move_index = move_row.white_label.move_index
                if move_index < move_count:
                    node = node.add_main_variation(self.moves[move_index])
                    if move_row.white_label.note:
                        node.comment = move_row.white_label.note

            # Process black move (optional in MoveRow)
            if move_row.black_label and move_row.black_label.text().strip():
                move_index = move_row.black_label.move_index
                if move_index < move_count:
                    node = node.add_main_variation(self.moves[move_index])
                    if move_row.black_label.note:
                        node.comment = move_row.black_label.note

        return str(self.current_game)

    # def load_analysis_prompt(self):
    #     file_path, _ = QFileDialog.getOpenFileName(self, "Load Analysis", "", "Analysis Files (*.json)")
    #     if file_path:
    #         self.load_analysis(file_path)

    def prev_move(self):
        """
        @brief Go back one move.
        """
        if self.current_move_index > 0:
            self.current_move_index -= 1
            self.current_board.pop()
            self.update_display()

    def first_move(self):
        """
        @brief Jump to the first move of the game.
        """
        while self.current_move_index > 0:
            self.prev_move()

    def last_move(self):
        """
        @brief Jump to the last move of the game.
        """
        while self.current_move_index < len(self.moves):
            self.next_move()

    def board_flip(self):
        """
        @brief Flip the board display orientation.
        """
        self.flipped = not self.flipped
        self.board_display.flipped = self.flipped
        self.board_orientation = not getattr(self, "board_orientation", False)
        self.update_display()

    def keyPressEvent(self, event):
        """
        @brief Process key press events for move navigation.
        @param event The key press event.
        """
        if event.key() == Qt.Key_Left:
            self.prev_move()
        elif event.key() == Qt.Key_Right:
            self.next_move()
        else:
            super().keyPressEvent(event)
        
    def is_within_board(self, pos):
        """
        @brief Check if a given position is within the board boundaries.
        @param pos The QPoint position.
        @return True if within boundaries, else False.
        """
        board_size = 8 * self.square_size
        global_offset = (self.board_display.width() - board_size) / 2
        board_x = global_offset
        board_y = global_offset
        return (board_x <= pos.x() <= board_x + board_size and 
                board_y <= pos.y() <= board_y + board_size)

    def arrow_toggle(self):
        self.show_arrows = not self.show_arrows
        if not self.show_arrows:
            self.arrows = []
        self.arrow_button.setText(f"Arrows: {'✅' if self.show_arrows else '❌'}")
        self.update_display()

    def mousePressEvent(self, event):
        pos = event.localPos()
        
        if not self.is_within_board(pos):
            return super().mousePressEvent(event)
            
        if self.flipped:
            file_idx = 7 - int(pos.x() // self.square_size)
            rank_idx = int(pos.y() // self.square_size)
        else:
            file_idx = int(pos.x() // self.square_size)
            rank_idx = 7 - int(pos.y() // self.square_size)
            
        square = chess.square(file_idx, rank_idx)
        piece = self.current_board.piece_at(square)
        
        if event.button() == Qt.RightButton:
            self.arrow_start = square
            self.current_arrow = (square, square)
            self.right_click_pos = pos
            event.accept()
            self.board_display.repaint()
            return

        if event.button() == Qt.LeftButton:
            if not piece:
                self.arrows = []
                self.current_arrow = None
                self.arrow_start = None
                self.user_circles = set()
                self.board_display.user_circles = set()
                self.board_display.repaint()
                return
            
            if piece:
                legal = [move for move in self.current_board.legal_moves if move.from_square == square]
                self.board_display.highlight_moves = [move.to_square for move in legal]
                self.selected_square = square
                self.board_display.update()
                self.dragging = True
                self.drag_start_square = square
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
                self.board_display.repaint()
                return
                
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.RightButton and self.current_arrow is not None:
            pos = event.localPos()
            if not self.is_within_board(pos):
                return
            board_size = 8 * self.square_size
            global_offset = (self.board_display.width() - board_size) / 2
            adjusted_x = pos.x() - global_offset - 44
            adjusted_y = pos.y() - global_offset - 129
            if self.flipped:
                file_idx = int(adjusted_x // self.square_size)
                rank_idx = 7 - int(adjusted_y // self.square_size)
            else:
                file_idx = int(adjusted_x // self.square_size)
                rank_idx = 7 - int(adjusted_y // self.square_size)
            if 0 <= file_idx <= 7 and 0 <= rank_idx <= 7:
                square = chess.square(file_idx, rank_idx)
                self.current_arrow = (self.arrow_start, square)
                self.board_display.update()
            return

        if self.dragging:
            self.drag_current_pos = event.localPos()
            if self.is_live_game is False:
                y_off = 129
            else:
                y_off = 129
            self.drag_current_pos = QPointF(self.drag_current_pos.x() - 44, self.drag_current_pos.y() - y_off)
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

    def update_live_eval(self):
        """
        @brief Get and store evaluation for the current position in live games.
        """
        if not self.current_board.is_game_over():
            info = self.engine.analyse(
                self.current_board,
                chess.engine.Limit(time=self.settings.value("analysis/postime", 0.1, float)),
                multipv=1
            )
            eval_score = self.eval_to_cp(info[0]["score"].relative)
            if not hasattr(self, 'move_evaluations_scores'):
                self.move_evaluations_scores = []
            if self.current_move_index - 1 < len(self.move_evaluations_scores):
                self.move_evaluations_scores[self.current_move_index - 1] = eval_score
            else:
                self.move_evaluations_scores.append(eval_score)
            self.white_moves = [self.move_evaluations_scores[i] for i in range(0, len(self.move_evaluations_scores), 2)]
            self.black_moves = [self.move_evaluations_scores[i] for i in range(1, len(self.move_evaluations_scores), 2)]
            self.eval_graph.update_graph(self.white_moves, self.black_moves)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton and self.current_arrow is not None:
            start, end = self.current_arrow
            if start == end:
                if start in self.user_circles:
                    self.user_circles.remove(start)
                else:
                    self.user_circles.add(start)
                self.board_display.user_circles = self.user_circles
            else:
                self.arrows.append(self.current_arrow)
            self.current_arrow = None
            self.arrow_start = None
            self.board_display.repaint()
            return

        if self.dragging:
            pos = event.localPos()
            if self.is_live_game is False:
                pos = pos - QPointF(44, 129)
            else:
                pos = pos - QPointF(44, 129)
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
                if self.is_live_game:
                    if self.current_move_index < len(self.moves):
                        self.moves = self.moves[:self.current_move_index]
                        if hasattr(self, 'move_evaluations'):
                            self.move_evaluations = self.move_evaluations[:self.current_move_index]
                        if hasattr(self, 'move_evaluations_scores'):
                            self.move_evaluations_scores = self.move_evaluations_scores[:self.current_move_index]
                    self.moves.append(move)
                    self.current_move_index += 1
                    self.board_display.last_move_eval = None
                    self.update_live_eval()
                    self.check_game_over()
                    if hasattr(self, 'computer_color') and \
                       self.current_board.turn == self.computer_color:
                        self.make_computer_move()
            self.dragging = False
            self.drag_start_square = None
            self.drag_current_pos = None
            self.drag_offset = None
            self.board_display.drag_info = {"dragging": False}
            self.board_display.highlight_moves = []
            self.update_display()
        else:
            super().mouseReleaseEvent(event)

    def get_piece_pixmap(self, piece):
        """
        @brief Retrieve the QPixmap for a given chess piece.
        @param piece The chess piece.
        @return Scaled QPixmap of the chess piece.
        """
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

    def save_game_with_notes(self):
        """Save the game PGN with move notes."""
        game = chess.pgn.Game()
        node = game
        if hasattr(self, 'hdrs') and self.hdrs:
            for key, value in self.hdrs.items():
                game.headers[key] = value
        for i, move in enumerate(self.moves):
            node = node.add_variation(move)
            move_widget = self.move_list.itemAt(i // 2).widget()
            if i % 2 == 0:
                note = move_widget.white_label.note
            else:
                note = move_widget.black_label.note
            if note:
                node.comment = note
        return str(game)

    def configure_engine_for_play(self, elo):
        """
        @brief Configure Stockfish engine for play at specified ELO.
        @param elo The target ELO rating.
        """
        user_elo = max(400, min(3000, elo))
        effective_elo = max(1320, user_elo)
        self.engine.configure({
            "UCI_LimitStrength": True,
            "UCI_Elo": effective_elo,
            "Skill Level": min(20, max(0, (effective_elo - 1000) // 100)),
        })

    def start_game_vs_computer(self, player_color, elo):
        """
        @brief Start a new game against the computer.
        @param player_color 'white', 'black', or 'random'
        @param elo Stockfish ELO rating to use
        """
        import random
        
        self.is_live_game = True
        self.current_board = chess.Board()
        self.moves = []
        self.current_move_index = 0
        self.move_evaluations = []
        self.move_evaluations_scores = []
        self.computer_color = chess.BLACK if player_color == 'white' else \
                            chess.WHITE if player_color == 'black' else \
                            random.choice([chess.WHITE, chess.BLACK])
        
        self.configure_engine_for_play(elo)
        self.update_display()
        
        if self.computer_color == chess.WHITE:
            self.make_computer_move()
        self.has_been_analyzed = False

    def make_computer_move(self):
        """
        @brief Have the computer make its move.
        """
        if not self.current_board.is_game_over():
            result = self.engine.play(
                self.current_board,
                chess.engine.Limit(time=1.0)
            )
            if result.move:
                self.current_board.push(result.move)
                self.moves.append(result.move)
                self.current_move_index += 1
                self.update_live_eval()
                self.update_display()
                self.check_game_over()

    def check_game_over(self):
        """
        @brief Check if the game is over and show appropriate dialog.
        """
        if self.current_board.is_game_over() and not self.last_shown_game_over:
            self.last_shown_game_over = True
            result = ""
            if self.current_board.is_checkmate():
                winner = "Black" if self.current_board.turn == chess.WHITE else "White"
                result = f"Checkmate! {winner} wins!"
            elif self.current_board.is_stalemate():
                result = "Game Over - Stalemate!"
            elif self.current_board.is_insufficient_material():
                result = "Game Over - Draw by insufficient material!"
            elif self.current_board.is_fifty_moves():
                result = "Game Over - Draw by fifty move rule!"
            elif self.current_board.is_repetition():
                result = "Game Over - Draw by repetition!"
            else:
                result = "Game Over - Draw!"

            QMessageBox.information(self, "Game Over", result)
            self.analyze_button.setVisible(True)

    def analyze_completed_game(self):
        """
        @brief Analyze the completed game and show the analysis.
        """
        if not self.moves or self.has_been_analyzed:
            return

        self.loading_bar = self.show_loading(
            title="Analyzing Game",
            text="Analyzing moves...",
            max=len(self.moves)
        )

        self.engine.configure({
            "UCI_LimitStrength": False,
            "Skill Level": 20
        })

        self.analyze_all_moves()
        self.update_display()
        self.update_game_summary()
        self.loading_bar.close()
        self.has_been_analyzed = True
        self.analyze_button.setVisible(False)
        QMessageBox.information(
            self,
            "Analysis Complete",
            f"Game analyzed!\nWhite Accuracy: {self.white_accuracy}%\nBlack Accuracy: {self.black_accuracy}%"
        )