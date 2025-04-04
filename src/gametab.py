import sys
import os
import chess
import chess.pgn
import chess.engine
import chess.svg
import io
from datasets import load_dataset
import polars as pl
import re
from PySide6.QtWidgets import *
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import QByteArray, QSettings, Qt, QPointF, QRectF, QMimeData, QPoint, QTimer
from PySide6.QtGui import QPainter, QColor, QPixmap, QPen, QFont, QDrag
import math
from utils import MoveRow, EvaluationGraphPG
from dialogs import LoadingDialog, clean_pgn_moves, load_openings, OPENINGS_DB, OPENINGS_LOADED_FLAG, PromotionDialog

class CustomSVGWidget(QSvgWidget):
    def __init__(self, parent=None):
        """
        @brief Initialize the custom SVG widget for board overlays.
        @param parent Parent widget.
        """
        super().__init__(parent)
        self.squares = {}  # {square: QColor, ...}
        self.square_size = 60
        self.drag_info = {}  # New: info dict passed from GameTab
        self.highlight_moves = []  # NEW: squares to highlight
        self.last_move_eval = None  # NEW: Store evaluation symbol for last move
        self.flipped = False
        self.previous_move = None
        self.user_circles = set()  # Initialize user_circles as empty set
        self.drag_start_position = None  # Add this line
        self.setAcceptDrops(True)  # Add this line to explicitly enable drops
        self.game_tab = parent  # Store reference to GameTab parent
    
    def resizeEvent(self, event):
        """
        Handle resize events to maintain a square board.
        """
        # Make the widget square based on the smaller dimension
        min_size = min(self.width(), self.height())
        
        # Set both dimensions equal to maintain square shape
        self.setMinimumSize(min_size, min_size)
        self.setMaximumSize(min_size, min_size)
        
        # Calculate square size based on the widget size
        self.square_size = min_size / 8
        
        super().resizeEvent(event)

    def paintEvent(self, event):
        """
        Overridden paint event to draw highlights, drag images and evaluation symbols.
        """
        super().paintEvent(event)
        painter = QPainter(self)
        board_size = 8 * self.square_size
        
        # Calculate global offsets to center the board
        global_offset_x = (self.width() - board_size) / 2
        global_offset_y = (self.height() - board_size) / 2

        # Map a chess square to its (file, rank) coordinates with proper flipping
        def get_square_coordinates(square):
            f = chess.square_file(square)
            r = chess.square_rank(square)
            if self.flipped:
                return 7 - f, r
            else:
                return f, 7 - r

        # Return a QRectF for a square at its position including global offset
        def get_square_rect(square):
            disp_file, disp_rank = get_square_coordinates(square)
            x = global_offset_x + disp_file * self.square_size
            y = global_offset_y + disp_rank * self.square_size
            x = x - (disp_file - (disp_file + 1))
            y = y - (disp_rank - (disp_rank + 1))
            return QRectF(x, y, self.square_size, self.square_size)

        # Calculate the center of a square
        def get_square_center(square):
            rect = get_square_rect(square)
            return rect.center()
        
        # Draw evaluation symbol in the square of the last move
        if self.last_move_eval:
            painter.setFont(QFont('Segoe UI Symbol', int(self.square_size / 3)))
            last_move = self.last_move_eval['move']
            eval_symbol = self.last_move_eval['symbol']
            if eval_symbol == '✅':
                painter.setPen(QColor("green"))
            elif eval_symbol == '👍':
                painter.setPen(QColor("yellow"))
            elif eval_symbol == '⚠️':
                painter.setPen(QColor("yellow"))
            elif eval_symbol == '❌':
                painter.setPen(QColor("red"))
            elif eval_symbol == '🔥':
                painter.setPen(QColor("orange"))
            
            rect = get_square_rect(last_move.to_square)
            alignment = Qt.AlignRight | Qt.AlignTop
            painter.drawText(rect, alignment, eval_symbol)

        # Draw highlighted circles for legal moves
        if self.highlight_moves:
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor(0, 150, 0, 200), 2)
            painter.setPen(pen)
            brush = QColor(0, 150, 0, 100)
            painter.setBrush(brush)
            for sq in self.highlight_moves:
                center = get_square_center(sq)
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

        # Draw arrows
        pen = QPen(QColor(255, 170, 0, 160), 5)
        painter.setPen(pen)
        game_tab = self.parent()
        while game_tab and not hasattr(game_tab, 'arrows'):
            game_tab = game_tab.parent()
        
        if self.user_circles:
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor(255, 170, 0, 160), 5)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            for sq in self.user_circles:
                center = get_square_center(sq)
                radius = self.square_size / 3
                painter.drawEllipse(center, radius, radius)
        
        if game_tab is not None:
            for arrow in game_tab.arrows:
                start_sq, end_sq = arrow
                start_center = get_square_center(start_sq)
                end_center = get_square_center(end_sq)
                painter.drawLine(start_center, end_center)
            
            if game_tab.current_arrow is not None:
                start_sq, end_sq = game_tab.current_arrow
                start_center = get_square_center(start_sq)
                end_center = get_square_center(end_sq)
                painter.drawLine(start_center, end_center)

        painter.end()
    
    def dragEnterEvent(self, event):
        """Handle drag enter events."""
        event.accept()  # Accept all drag enters
    
    def dragMoveEvent(self, event):
        """Handle drag move events."""
        square = self.square_at_position(event.position())
        if square is not None:
            event.accept()  # Accept drag if over valid square
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle drop events."""
        square = self.square_at_position(event.position())
        if square is not None and event.mimeData().hasText():
            from_square = int(event.mimeData().text())
            if self.game_tab:
                # Check if this would be a pawn promotion move
                is_promotion = (
                    self.game_tab.current_board.piece_type_at(from_square) == chess.PAWN and
                    ((chess.square_rank(square) == 7 and self.game_tab.current_board.turn == chess.WHITE) or
                     (chess.square_rank(square) == 0 and self.game_tab.current_board.turn == chess.BLACK))
                )
                
                if is_promotion:
                    # Show promotion dialog
                    dialog = PromotionDialog(self.game_tab.current_board.turn)
                    if dialog.exec() == QDialog.Accepted and dialog.selected_piece:
                        # Create move with promotion
                        promotion_piece = chess.Piece.from_symbol(dialog.selected_piece).piece_type
                        move = chess.Move(from_square, square, promotion=promotion_piece)
                    else:
                        event.ignore()
                        return
                else:
                    # Regular move
                    move = chess.Move(from_square, square)

                if move in self.game_tab.current_board.legal_moves:
                    # First update the board display immediately
                    self.game_tab.current_board.push(move)
                    self.highlight_moves = []
                    # Then handle the move consequences in a deferred manner
                    QTimer.singleShot(0, lambda: self.handle_move_consequences(move))

                    self.update()
                    event.acceptProposedAction()
                    return
        event.ignore()

    def handle_move_consequences(self, move):
        """Handle move consequences after the piece is dropped."""
        if self.game_tab.is_live_game:
            if self.game_tab.current_move_index < len(self.game_tab.moves):
                self.game_tab.moves = self.game_tab.moves[:self.game_tab.current_move_index]
                self.game_tab.move_evaluations = self.game_tab.move_evaluations[:self.game_tab.current_move_index]
                self.game_tab.move_evaluations_scores = self.game_tab.move_evaluations_scores[:self.game_tab.current_move_index]
            self.game_tab.moves.append(move)
            self.game_tab.current_move_index += 1
            self.last_move_eval = None
            self.game_tab.update_live_eval()
            self.game_tab.check_game_over()
            if hasattr(self.game_tab, 'computer_color') and self.game_tab.current_board.turn == self.game_tab.computer_color:
                QTimer.singleShot(500, self.game_tab.make_computer_move)
        self.game_tab.update_display()

    def square_at_position(self, pos):
        """Convert screen coordinates to chess square."""
        board_size = 8 * self.square_size
        global_offset_x = (self.width() - board_size) / 2
        global_offset_y = (self.height() - board_size) / 2
        
        adjusted_x = pos.x() - global_offset_x
        adjusted_y = pos.y() - global_offset_y
        
        if adjusted_x < 0 or adjusted_y < 0:
            return None
            
        file_size = board_size / 8
        rank_size = board_size / 8
        
        if self.flipped:
            file_idx = 7 - int(adjusted_x / file_size)
            rank_idx = int(adjusted_y / rank_size)
        else:
            file_idx = int(adjusted_x / file_size)
            rank_idx = 7 - int(adjusted_y / rank_size)
            
        if 0 <= file_idx < 8 and 0 <= rank_idx < 8:
            return chess.square(file_idx, rank_idx)
        return None

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
        self.is_live_game = False
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
        self.last_made_move = None

        self.white_accuracy = 0
        self.black_accuracy = 0

        self.create_gui()

    def create_gui(self):
        # Main layout preserving the original structure
        layout = QHBoxLayout(self)
        
        # Left panel - similar to original but with dock widget for board
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Board area as a dock widget
        self.board_dock_container = QMainWindow()
        self.board_dock_container.setDockNestingEnabled(True)
        
        # Dummy central widget (required for QMainWindow)
        dummy_central = QWidget()
        self.board_dock_container.setCentralWidget(dummy_central)
        dummy_central.setMaximumSize(0, 0)  # Make it invisible
        
        # Create board dock
        self.board_dock = QDockWidget("Chess Board", self.board_dock_container)
        self.board_dock.setObjectName("board_dock")
        self.board_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.board_dock.setFeatures(QDockWidget.DockWidgetMovable | 
                                   QDockWidget.DockWidgetFloatable |
                                   QDockWidget.DockWidgetClosable)
        
        # Create board container with win bar
        board_container = QWidget()
        board_layout = QHBoxLayout(board_container)
        
        # Win bar
        self.win_bar = QLabel()
        self.win_bar.setFixedSize(20, 600)
        board_layout.addWidget(self.win_bar)
        
        # Board display
        self.board_display = CustomSVGWidget(self)
        self.board_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.board_display.setMinimumSize(400, 400)
        board_layout.addWidget(self.board_display)
        
        # Add board container to dock and dock to window
        self.board_dock.setWidget(board_container)
        self.board_dock_container.addDockWidget(Qt.TopDockWidgetArea, self.board_dock)
        
        # Add dock container to layout
        left_layout.addWidget(board_container) # Smushes the board when fullscreen on 1920x1080
        
        # Navigation buttons - same as original
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
        self.analyze_button.setVisible(True)
        nav_layout.addWidget(self.analyze_button)
        
        left_layout.addLayout(nav_layout)
        
        # FEN box
        self.fen_box = QLineEdit("FEN: ")
        self.fen_box.setReadOnly(True)
        left_layout.addWidget(self.fen_box)
        
        # Summary label
        self.summary_label = QLabel()
        left_layout.addWidget(self.summary_label)
        
        # Right panel with dock widgets
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Create dock container for right panel
        self.right_dock_container = QMainWindow()
        self.right_dock_container.setDockNestingEnabled(True)
        
        # Dummy central widget for right panel
        dummy_central_right = QWidget()
        self.right_dock_container.setCentralWidget(dummy_central_right)
        dummy_central_right.setMaximumSize(0, 0)  # Make it invisible

        # Game details and opening label
        self.game_details_dock = QDockWidget("Game Details", self.right_dock_container)
        self.game_details_dock.setObjectName("game_details_dock")
        self.game_details_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.game_details_dock.setFeatures(QDockWidget.DockWidgetMovable | 
                                       QDockWidget.DockWidgetFloatable |
                                       QDockWidget.DockWidgetClosable)
        self.game_detail_container = QWidget()
        detail_layout = QVBoxLayout(self.game_detail_container)
        self.game_details = QLabel()
        detail_layout.addWidget(self.game_details)
        self.opening_label = QLabel()
        self.opening_label.setWordWrap(True)
        detail_layout.addWidget(self.opening_label)
        self.game_details_dock.setWidget(self.game_detail_container)
        self.right_dock_container.addDockWidget(Qt.TopDockWidgetArea, self.game_details_dock)
        
        # Create move list dock
        self.move_list_dock = QDockWidget("Move List", self.right_dock_container)
        self.move_list_dock.setObjectName("move_list_dock")
        self.move_list_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.move_list_dock.setFeatures(QDockWidget.DockWidgetMovable | 
                                       QDockWidget.DockWidgetFloatable |
                                       QDockWidget.DockWidgetClosable)
        
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
            QToolTip {
                background-color: black;
                color: white;
                border: 1px solid white;
            }
        """)
        self.move_list.itemClicked.connect(self.move_selected)
        self.move_list_dock.setWidget(self.move_list)
        self.right_dock_container.addDockWidget(Qt.TopDockWidgetArea, self.move_list_dock)
        
        # Create analysis dock
        self.analysis_dock = QDockWidget("Analysis", self.right_dock_container)
        self.analysis_dock.setObjectName("analysis_dock")
        self.analysis_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.analysis_dock.setFeatures(QDockWidget.DockWidgetMovable | 
                                      QDockWidget.DockWidgetFloatable |
                                      QDockWidget.DockWidgetClosable)
        
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_dock.setWidget(self.analysis_text)
        self.right_dock_container.addDockWidget(Qt.BottomDockWidgetArea, self.analysis_dock)
        
        # Create evaluation graph dock
        self.graph_dock = QDockWidget("Evaluation Graph", self.right_dock_container)
        self.graph_dock.setObjectName("graph_dock")
        self.graph_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
        self.graph_dock.setFeatures(QDockWidget.DockWidgetMovable | 
                                   QDockWidget.DockWidgetFloatable |
                                   QDockWidget.DockWidgetClosable)
        
        self.eval_graph = EvaluationGraphPG(self)
        self.graph_dock.setWidget(self.eval_graph)
        
        # Split docks to maintain original layout
        self.right_dock_container.splitDockWidget(self.analysis_dock, self.graph_dock, Qt.Vertical)
        
        right_layout.addWidget(self.right_dock_container)
        
        # Add both panels to the main layout
        layout.addWidget(left_panel)
        layout.addWidget(right_panel)
        
        # Save/restore dock layouts
        self.restore_dock_layouts()
        
        # Connect mouse events
        self.board_display.mousePressEvent = self.mousePressEvent
        self.board_display.mouseMoveEvent = self.mouseMoveEvent
        self.board_display.mouseReleaseEvent = self.mouseReleaseEvent
        
        self.update_display()

    def save_dock_layouts(self):
        """Save the current dock widget layouts to settings."""
        left_state = self.board_dock_container.saveState()
        right_state = self.right_dock_container.saveState()
        self.settings.setValue("left_dock_layout", left_state)
        self.settings.setValue("right_dock_layout", right_state)
        
    def restore_dock_layouts(self):
        """Restore the dock widget layouts from settings."""
        # Check if there are saved states
        if self.settings.contains("left_dock_layout"):
            left_state = self.settings.value("left_dock_layout")
            self.board_dock_container.restoreState(left_state)
            
        if self.settings.contains("right_dock_layout"):
            right_state = self.settings.value("right_dock_layout")
            self.right_dock_container.restoreState(right_state)
            
    def closeEvent(self, event):
        """Handle the close event to save dock layouts."""
        self.save_dock_layouts()
        super().closeEvent(event)
        
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

    def load_pgn(self, pgn_string, is_analysis=False):
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
            game_detail_text = f"""
White: {self.hdrs.get('White')}({self.hdrs.get('WhiteElo')})
Black: {self.hdrs.get('Black')}({self.hdrs.get('BlackElo')})
{self.hdrs.get('Date')}\nResult: {self.hdrs.get('Termination')}
"""
            self.game_details.setText(game_detail_text)

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
        
        global OPENINGS_DB, OPENINGS_LOADED_FLAG
        if len(OPENINGS_DB) == 0 or not OPENINGS_LOADED_FLAG:
            # dialog = LoadingDialog(title="Loading Openings dataset...", label_text="Please wait while the openings dataset is loaded.")
            # dialog.show()
            QApplication.processEvents()
            OPENINGS_DB = load_openings()
            QApplication.processEvents()
            # dialog.accept()
            OPENINGS_LOADED_FLAG = True

        self.opening = self.get_opening_from_moves(temp_board)
        self.opening_name = self.opening['name'] if self.opening else "Unknown"
        self.opening_eco = self.opening['eco'] if self.opening else ""
        if self.opening:
            self.opening_label.setText(f"Opening: {self.opening_name} ({self.opening_eco})")
        else:
            self.opening_label.setText("Opening: Unknown")

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

        # Get the position BEFORE the current move
        if self.is_live_game == False:
            if self.current_move_index > 0:
                previous_board = chess.Board()
                for move in self.moves[:self.current_move_index - 1]:
                    previous_board.push(move)
            else:
                previous_board = self.current_board
        else:
            # Handle live game previous position
            previous_board = chess.Board()
            if self.current_move_index > 0:
                for move in self.moves[:self.current_move_index - 1]:
                    previous_board.push(move)
            else:
                previous_board = chess.Board()  # Start position for live game

        if not self.current_board.is_game_over() and self.settings.value("display/show_arrows", True, bool):
            # Analyze the previous position (not the current one) to show what you could have played
            if not self.settings.value("display/arrow_move", True, bool) and self.is_live_game == False:
                info = self.engine.analyse(
                    previous_board,  # Use previous_board here
                    chess.engine.Limit(time=self.settings.value("analysis/postime", 0.1, float)),
                    multipv=self.settings.value("engine/lines", 3, int)
                )
            else:
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

            for i, pv in enumerate(info, 0):
                if "pv" in pv.keys():
                    move = pv["pv"][0]
                    score = self.eval_to_cp(pv["score"].relative) if hasattr(self, 'eval_to_cp') else 0
                    if self.is_live_game == False:
                        analysis_text += f"{i+1}. {previous_board.san(move)} (eval: {score/100:+.2f})\n"
                    else:
                        analysis_text += f"{i+1}. {self.current_board.san(move)} (eval: {score/100:+.2f})\n"

                    color = QColor("#00ff00") if i <= 0 else QColor("#007000")

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

        if self.current_board.is_check():
            king_square = self.current_board.king(self.current_board.turn)
            if king_square is not None:
                squares[king_square] = QColor(255, 0, 0, 150)

        board_size = int(self.board_display.square_size * 8)
        check = self.current_board.king(self.current_board.turn) if self.current_board.is_check() else None
        lastmove = self.moves[self.current_move_index - 1] if self.current_move_index > 0 else None

        board_svg = chess.svg.board(
            self.current_board,
            arrows=arrows,
            lastmove=lastmove,
            size=board_size,
            check=check,
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

        # Process opening detection for live games
        global OPENINGS_LOADED_FLAG
        if self.is_live_game == True and self.settings.value("game/load_openings", True, bool):
            if not OPENINGS_LOADED_FLAG:
                # dialog = LoadingDialog(title="Loading Openings Database...", label_text="Please wait while the openings database is loaded...")
                # dialog.show()
                QApplication.processEvents()
                load_openings()
                QApplication.processEvents()
                # dialog.accept()
                OPENINGS_LOADED_FLAG = True
            
            # Get opening for the current game state
            self.opening = self.get_opening_from_moves(self.moves[:self.current_move_index])
            if self.opening and 'name' in self.opening and 'eco' in self.opening:
                opening_name = self.opening['name']
                opening_eco = self.opening['eco']
                self.opening_label.setText(f"Opening: {opening_name} ({opening_eco})")

        # Always update the move list regardless of game type
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

        self.analyze_position()
        
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
        index = self.current_move_index

        # Apply headers if available
        if hasattr(self, 'hdrs') and self.hdrs:
            for key, value in self.hdrs.items():
                game.headers[key] = value

        # Fix the Termination/Result header and ensure Result is set
        if "Termination" in game.headers:
            game.headers["Result"] = game.headers.pop("Termination", "*")
        elif "Result" not in game.headers:
            # Set default result if not present
            result = "*"
            if self.current_board.is_checkmate():
                result = "1-0" if self.current_board.turn == chess.BLACK else "0-1"
            elif self.current_board.is_stalemate() or self.current_board.is_insufficient_material():
                result = "1/2-1/2"
            game.headers["Result"] = result

        # Rebuild the mainline moves
        node = game

        # Ensure we're using all moves up to current_move_index for live games
        moves_to_export = self.moves[:self.current_move_index] if self.is_live_game else self.moves

        print(f"moves to export: {moves_to_export}")

        print(self.moves)
        print("\n\n\n")
        print(self.moves[:self.current_move_index])
        
        for move in moves_to_export:
            node = node.add_main_variation(move)
            
            # Add move evaluations as comments if available
            if hasattr(self, 'move_evaluations') and len(self.move_evaluations) > 0:
                index = moves_to_export.index(move)
                if index < len(self.move_evaluations) and self.move_evaluations[index]:
                    node.comment = f"Eval: {self.move_evaluations[index]}"
            
            # Add move notes if available
            if hasattr(self, 'move_notes') and index in self.move_notes:
                if node.comment:
                    node.comment += f" | Note: {self.move_notes[index]}"
                else:
                    node.comment = f"Note: {self.move_notes[index]}"

        # If there's opening information, add it as a comment to the first move
        if hasattr(self, 'opening') and self.opening and 'name' in self.opening and 'eco' in self.opening:
            first_node = game.variations[0] if game.variations else None
            if first_node:
                opening_comment = f"Opening: {self.opening['name']} ({self.opening['eco']})"
                if first_node.comment:
                    first_node.comment = opening_comment + " | " + first_node.comment
                else:
                    first_node.comment = opening_comment

        # Convert game to PGN string
        pgn_text = str(game)

        # Create a filename
        if self.is_live_game:
            white = self.hdrs.get('White', 'White').replace(' ', '_')
            black = self.hdrs.get('Black', 'Black').replace(' ', '_')
            date = str(self.hdrs.get('Date', 'Unknown')).replace('.', '_')
        else:
            white = game.headers.get('White', 'White').replace(' ', '_')
            black = game.headers.get('Black', 'Black').replace(' ', '_')
            date = game.headers.get('Date', 'Unknown').replace('.', '_')
        
        filename = f"{white}_{black}_{date}.pgn"

        return pgn_text, filename

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
        self.goto_move(0)

    def last_move(self):
        """
        @brief Jump to the last move of the game.
        """
        self.goto_move(len(self.moves)-1)

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
        board_size = 8 * self.board_display.square_size
        global_offset_x = (self.board_display.width() - board_size) / 2
        global_offset_y = (self.board_display.height() - board_size) / 2

        # Calculate actual board boundaries
        left = global_offset_x
        right = global_offset_x + board_size
        top = global_offset_y
        bottom = global_offset_y + board_size
        
        return (left <= pos.x() <= right and top <= pos.y() <= bottom)

    def arrow_toggle(self):
        self.show_arrows = not self.show_arrows
        if not self.show_arrows:
            self.arrows = []
        self.arrow_button.setText(f"Arrows: {'✅' if self.show_arrows else '❌'}")
        self.update_display()

    def mousePressEvent(self, event):
        """Handle mouse press events for piece movement."""
        pos = event.localPos()
        board_size = 8 * self.board_display.square_size
        global_offset = (self.board_display.width() - board_size) / 2

        # Check if click is within board boundaries
        if not self.is_within_board(pos):
            return super().mousePressEvent(event)

        # Calculate square coordinates
        adjusted_x = pos.x() - global_offset
        adjusted_y = pos.y() - global_offset

        # Determine clicked square
        if self.flipped:
            file_idx = 7 - int(adjusted_x // self.board_display.square_size)
            rank_idx = int(adjusted_y // self.board_display.square_size)
        else:
            file_idx = int(adjusted_x // self.board_display.square_size)
            rank_idx = 7 - int(adjusted_y // self.board_display.square_size)
        square = chess.square(file_idx, rank_idx)
        piece = self.current_board.piece_at(square)

        # Handle right-click for arrows
        if event.button() == Qt.RightButton:
            self.arrow_start = square
            self.current_arrow = (square, square)
            event.accept()
            self.board_display.repaint()
            return
        
        # Left-click on an empty square: clear drawn arrows and circles (added back)
        if event.button() == Qt.LeftButton:
            self.arrows = []
            self.user_circles = set()
            self.board_display.user_circles = self.user_circles
            self.board_display.repaint()

        # Handle left-click for piece movement
        if event.button() == Qt.LeftButton and piece:
            # Create drag object
            drag = QDrag(self.board_display)  # Changed to use board_display as parent
            mime_data = QMimeData()
            
            # Store square data in mime data
            mime_data.setText(str(square))
            drag.setMimeData(mime_data)
            
            # Set drag pixmap
            pixmap = self.get_piece_pixmap(piece)
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
            
            # Highlight legal moves
            legal_moves = [move for move in self.current_board.legal_moves if move.from_square == square]
            self.board_display.highlight_moves = [move.to_square for move in legal_moves]
            self.board_display.repaint()
            
            # Execute drag
            result = drag.exec(Qt.MoveAction)
            
            # Reset highlights
            self.board_display.highlight_moves = []
            self.board_display.repaint()
            
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.localPos()
        board_size = 8 * self.board_display.square_size
        global_offset = (self.board_display.width() - board_size) / 2

        if event.buttons() & Qt.RightButton and self.current_arrow is not None:
            if pos.x() < global_offset or pos.x() > global_offset + board_size or \
            pos.y() < global_offset or pos.y() > global_offset + board_size:
                return
            adjusted_x = pos.x() - global_offset
            adjusted_y = pos.y() - global_offset
            if self.flipped:
                file_idx = 7 - int(adjusted_x // self.board_display.square_size)
                rank_idx = int(adjusted_y // self.board_display.square_size)
            else:
                file_idx = int(adjusted_x // self.board_display.square_size)
                rank_idx = 7 - int(adjusted_y // self.board_display.square_size)
            square = chess.square(file_idx, rank_idx)
            self.current_arrow = (self.arrow_start, square)
            self.board_display.update()
            return

        super().mouseMoveEvent(event)
    
    def handle_drop_move(self, start_square, drop_square):
        move = chess.Move(start_square, drop_square)
        if move in self.current_board.legal_moves:
            self.current_board.push(move)
            if self.is_live_game:
                if self.current_move_index < len(self.moves):
                    self.moves = self.moves[:self.current_move_index]
                    self.move_evaluations = self.move_evaluations[:self.current_move_index]
                    self.move_evaluations_scores = self.move_evaluations_scores[:self.current_move_index]
                self.moves.append(move)
                self.current_move_index += 1
                self.board_display.last_move_eval = None
                self.update_live_eval()
                self.check_game_over()
                if hasattr(self, 'computer_color') and self.current_board.turn == self.computer_color:
                    QTimer.singleShot(500, self.make_computer_move)
            self.update_display()

    def mouseReleaseEvent(self, event):
        board_size = 8 * self.board_display.square_size
        global_offset = (self.board_display.width() - board_size) / 2

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
            adjusted_pos = pos - QPointF(global_offset, global_offset)
            if self.flipped:
                file_idx = 7 - int(adjusted_pos.x() // self.board_display.square_size)
                rank_idx = int(adjusted_pos.y() // self.board_display.square_size)
            else:
                file_idx = int(adjusted_pos.x() // self.board_display.square_size)
                rank_idx = 7 - int(adjusted_pos.y() // self.board_display.square_size)
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
                    if hasattr(self, 'computer_color') and self.current_board.turn == self.computer_color:
                        QTimer.singleShot(500, self.make_computer_move)
            self.dragging = False
            self.drag_start_square = None
            self.drag_current_pos = None
            self.drag_offset = None
            self.board_display.drag_info = {"dragging": False}
            self.board_display.highlight_moves = []
            self.update_display()
        else:
            super().mouseReleaseEvent(event)


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

    def get_piece_svg(self, piece):
        """Generate SVG for a single piece."""
        size = self.width() // 8  # size of one square
        piece_svg = chess.svg.piece(piece, size=size)
        return piece_svg
    
    def get_piece_pixmap(self, piece):
        piece_svg = self.get_piece_svg(piece)
        pixmap = QPixmap(100, 100)  # Fixed size for drag image
        pixmap.loadFromData(piece_svg.encode(), 'SVG')
        
        # Handle failed loads
        if pixmap.isNull():
            print(f"Error: Failed to load image for piece")
            pixmap = QPixmap(self.board_display.square_size, self.board_display.square_size)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setPen(Qt.black)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, piece.symbol())
            painter.end()
            
        # Scale using the board display's actual square size
        square_size = self.board_display.square_size
        return pixmap.scaled(square_size, square_size, 
                           Qt.KeepAspectRatio, 
                           Qt.SmoothTransformation)

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
        # Clamp ELO between Stockfish's minimum (1320) and maximum (3000)
        user_elo = max(200, min(3000, elo))
        
        # For ELO requests below 1320, we'll reduce the skill level further
        # to simulate weaker play while keeping UCI_Elo at the minimum
        if elo < 1320:
            # Scale skill level from 0-5 for ELO range 400-1320
            skill_level = max(0, min(5, (elo - 400) // 184))
        else:
            # Scale skill level from 6-20 for ELO range 1320-3000
            skill_level = min(20, max(6, (user_elo - 1320) // 84))
        
        # Configure the engine
        self.engine.configure({
            "UCI_LimitStrength": True,
            "UCI_Elo": user_elo,
            "Skill Level": skill_level,
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
            QTimer.singleShot(500, self.make_computer_move)
            
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
        QMessageBox.information(
            self,
            "Analysis Complete",
            f"Game analyzed!\nWhite Accuracy: {self.white_accuracy}%\nBlack Accuracy: {self.black_accuracy}%"
        )

    def get_opening_from_moves(self, board_or_moves):
        """
        Given either a python-chess board or a list of moves,
        returns the opening that best matches the current move sequence,
        based on the longest matching prefix.
        
        @param board_or_moves: Either a chess.Board object or a list of chess.Move objects
        @return: The best matching opening or None
        """
        moves = []
        temp_board = chess.Board()
        
        # Check if we're getting a board or a list of moves
        if isinstance(board_or_moves, chess.Board):
            # Extract moves from board's move_stack
            for move in board_or_moves.move_stack:
                san = temp_board.san(move)
                moves.append(san)
                temp_board.push(move)
        else:
            # Assume it's a list of chess.Move objects
            for move in board_or_moves:
                san = temp_board.san(move)
                moves.append(san)
                temp_board.push(move)
        
        current_sequence = " ".join(moves)
        
        best_opening = None
        best_length = 0
        global OPENINGS_DB
        for opening in OPENINGS_DB:
            # Clean the PGN field to remove move numbers
            opening_moves = clean_pgn_moves(opening["pgn"])
            move_count = len(opening_moves.split())
            # If the current sequence starts with this opening's moves and it is longer than the best match so far:
            if current_sequence.startswith(opening_moves) and move_count > best_length:
                best_opening = opening
                best_length = move_count

        return best_opening