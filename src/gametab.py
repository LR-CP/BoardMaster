import chess
import chess.pgn
import chess.engine
import chess.svg
import io
from PySide6.QtWidgets import *
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QByteArray, QSettings, Qt
import math
from utils import MoveRow

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
    
    def update_display(self):
        arrows = []
        annotations = {}
        eval_score = 0  # Default value
        
        if not self.current_board.is_game_over() and self.settings.value("display/show_arrows", True, bool):
            info = self.engine.analyse(
                self.current_board,
                chess.engine.Limit(time=self.settings.value("analysis/postime", 0.1, float)),
                multipv=self.settings.value("engine/lines", 3, int)
            )
            
            # Get the main line evaluation
            main_eval = info[0]["score"].relative
            eval_score = self.eval_to_cp(main_eval) if hasattr(self, 'eval_to_cp') else 0
            
            # Update analysis text
            analysis_text = f"Move {(self.current_move_index + 1) // 2} "
            analysis_text += f"({'White' if self.current_move_index % 2 == 0 else 'Black'})\n\n"
            analysis_text += "Top moves:\n"
            
            for i, pv in enumerate(info, 1):
                move = pv["pv"][0]
                score = self.eval_to_cp(pv["score"].relative) if hasattr(self, 'eval_to_cp') else 0
                analysis_text += f"{i}. {self.current_board.san(move)} (eval: {score/100:+.2f})\n"
                
                # Add arrows
                color = "#00ff00" if i == 0 else "#007000" if i == 1 else "#003000"
                arrows.append(chess.svg.Arrow(
                    tail=move.from_square,
                    head=move.to_square,
                    color=color
                ))
                annotations[move.to_square] = f"{score / 100.0:.2f}"
            
            self.analysis_text.setText(analysis_text)

        # Get evaluation score for current position
        if self.current_move_index > 0 and hasattr(self, 'move_evaluations_scores'):
            # Only use stored evaluation if we have it for this position
            if self.current_move_index - 1 < len(self.move_evaluations_scores):
                eval_score = self.move_evaluations_scores[self.current_move_index - 1]
            else:
                # Otherwise use the current position evaluation
                info = self.engine.analyse(
                    self.current_board,
                    chess.engine.Limit(time=self.settings.value("analysis/postime", 0.1, float)),
                    multipv=1
                )
                eval_score = self.eval_to_cp(info[0]["score"].relative)

        squares = {}
        if self.selected_square is not None:
            squares[self.selected_square] = "#ffff00"
            for move in self.legal_moves:
                squares[move.to_square] = "#00ff00"

        # Show last move with arrow
        if self.current_move_index > 0 and self.moves: #self.current_variation is None:
            last_move = self.moves[self.current_move_index - 1]
            arrows.append(
                chess.svg.Arrow(
                    tail=last_move.from_square,
                    head=last_move.to_square,
                    color="#674ea7",
                )
            )

        # Generate the base SVG board
        board_svg = chess.svg.board(
            self.current_board,
            arrows=arrows,
            squares=squares,
            size=600,
            orientation=(
                chess.BLACK
                if getattr(self, "board_orientation", False)
                else chess.WHITE
            ),
        )

        # Inject evaluation symbol onto the last move's square
        if self.current_move_index > 0 and self.moves:
            last_move = self.moves[self.current_move_index - 1]
            last_to_square = last_move.to_square

            # Only show evaluation if we have it for this move
            evaluation_symbol = ""
            if self.current_move_index - 1 < len(self.move_evaluations):
                evaluation_symbol = self.move_evaluations[self.current_move_index - 1]

            if evaluation_symbol:
                # Calculate the position of the square
                file_index = chess.square_file(last_to_square)
                rank_index = chess.square_rank(last_to_square)
                square_size = self.square_size
                x = file_index * square_size
                y = (7 - rank_index) * square_size

                # Color based on evaluation symbol
                if evaluation_symbol == "✅":
                    symbol_color = "green"
                elif evaluation_symbol == "👍":
                    symbol_color = "yellow"
                elif evaluation_symbol == "⚠️":
                    symbol_color = "orange"
                elif evaluation_symbol == "❌":
                    symbol_color = "red"
                elif evaluation_symbol == "🔥":
                    symbol_color = "darkred"
                else:
                    symbol_color = "black"

                # Inject custom SVG text
                symbol_svg = f"""
                    <text x="{0}" y="{18}" font-size="20" font-family="Arial"
                        font-weight="bold" fill="{symbol_color}">
                        {evaluation_symbol}
                    </text>
                """

                # Insert symbol SVG into the existing SVG
                board_svg = board_svg.replace("</svg>", symbol_svg + "</svg>")

        # Load the SVG into the display
        self.board_display.load(QByteArray(board_svg.encode("utf-8")))

        # Calculate win bar percentage using logistic function
        win_percentage = 50 + (50 * (2 / (1 + math.exp(-eval_score/400)) - 1))
        white_percentage = max(0, min(100, win_percentage))
        
        self.win_bar.setStyleSheet(
            f"background: qlineargradient(y1:0, y2:1, stop:0 white, stop:{white_percentage/100} white, "
            f"stop:{white_percentage/100} black, stop:1 black);"
        )

        # Update FEN
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
                    self.legal_moves = {
                        move
                        for move in self.current_board.legal_moves
                        if move.from_square == square
                    }
                    self.update_display()
            else:
                if square == self.selected_square:
                    self.selected_square = None
                    self.legal_moves = set()
                    self.update_display()
                    return

                move = chess.Move(self.selected_square, square)

                piece = self.current_board.piece_at(self.selected_square)
                if (
                    piece
                    and piece.symbol().lower() == "p"
                    and (
                        (rank_idx == 7 and self.current_board.turn == chess.WHITE)
                        or (rank_idx == 0 and self.current_board.turn == chess.BLACK)
                    )
                ):
                    move = chess.Move(
                        self.selected_square, square, promotion=chess.QUEEN
                    )

                if move in self.legal_moves:
                    # Check if we're starting a new variation
                    if not self.is_live_game and self.current_move_index < len(self.moves):
                        if self.current_variation is None:
                            # Start a new variation
                            variation_index = len(self.variations.get(self.current_move_index, []))
                            if self.current_move_index not in self.variations:
                                self.variations[self.current_move_index] = []
                            self.variations[self.current_move_index].append([])
                            self.current_variation = (self.current_move_index, variation_index)
                            
                            # Initialize evaluations for this variation
                            if self.current_move_index not in self.variation_evaluations:
                                self.variation_evaluations[self.current_move_index] = []
                            self.variation_evaluations[self.current_move_index].append([])

                    # Make the move
                    self.current_board.push(move)
                    
                    # Store the move in appropriate list
                    if self.current_variation is not None:
                        start_index, var_index = self.current_variation
                        self.variations[start_index][var_index].append(move)
                        
                        # Analyze and store evaluation for variation
                        if hasattr(self, 'engine'):
                            info = self.engine.analyse(
                                self.current_board,
                                chess.engine.Limit(time=self.settings.value("analysis/postime", 0.1, float)),
                                multipv=1
                            )
                            score = self.eval_to_cp(info[0]["score"].relative)
                            
                            # Add evaluation
                            eval_diff = abs(score)
                            if eval_diff < 50:
                                evaluation = "✅"
                            elif eval_diff < 100:
                                evaluation = "👍"
                            elif eval_diff < 200:
                                evaluation = "⚠️"
                            elif eval_diff < 400:
                                evaluation = "❌"
                            else:
                                evaluation = "🔥"
                            self.variation_evaluations[start_index][var_index].append(evaluation)
                    else:
                        self.moves.append(move)
                        if hasattr(self, 'engine'):
                            # Original move evaluation code...
                            info = self.engine.analyse(
                                self.current_board,
                                chess.engine.Limit(time=self.settings.value("analysis/postime", 0.1, float)),
                                multipv=1
                            )
                            score = self.eval_to_cp(info[0]["score"].relative)
                            self.move_evaluations_scores.append(score)
                            
                            eval_diff = abs(score)
                            if eval_diff < 50:
                                evaluation = "✅"
                            elif eval_diff < 100:
                                evaluation = "👍"
                            elif eval_diff < 200:
                                evaluation = "⚠️"
                            elif eval_diff < 400:
                                evaluation = "❌"
                            else:
                                evaluation = "🔥"
                            self.move_evaluations.append(evaluation)
                    
                    self.current_move_index += 1
                    self.update_display()

                self.selected_square = None
                self.legal_moves = set()
                
        except Exception as e:
            print(f"Error handling mouse press: {e}")
            self.selected_square = None
            self.legal_moves = set()
            self.update_display()
