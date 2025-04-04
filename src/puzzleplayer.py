from gettext import install
import sys
import random
import os
import csv
import io
from pathlib import Path
import requests

import chess
import chess.svg
from PySide6.QtCore import Qt, QSize, Signal, Slot, QTimer, QMimeData, QPoint
from PySide6.QtGui import QPixmap, QIcon, QDrag, QCursor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QLabel, QPushButton, QComboBox, 
                              QFileDialog, QMessageBox, QSplitter, QFrame)
from PySide6.QtSvgWidgets import QSvgWidget
import polars as pl

from dialogs import start_hf_download

PUZZLES_LOADED_FLAG = False
PUZZLES_DB = None

class ChessBoard(QSvgWidget):
    """Chess board widget using SVG rendering."""
    clicked = Signal(tuple)
    move_made = Signal(chess.Move)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = chess.Board()
        self.selected_square = None
        self.last_move = None
        self.correct_move = None
        self.player_color = chess.WHITE  # default player color
        self.setMinimumSize(400, 400)
        self.setAcceptDrops(True)  # Enable drop events
        self.drag_start_position = None
        self.update_board()
        
    def update_board(self):
        """Update the board display with current position and highlights."""
        lastmove = self.last_move
        check = self.board.king(self.board.turn) if self.board.is_check() else None
        
        # Highlight squares
        squares = {}
        if self.selected_square is not None:
            squares[self.selected_square] = "#aaff00"  # highlight selected square
            
            # Highlight legal moves from selected square
            for move in self.board.legal_moves:
                if move.from_square == self.selected_square:
                    squares[move.to_square] = "#aaaaff"
        
        # Generate SVG and load it, with board orientation set to player_color.
        svg_data = chess.svg.board(
            board=self.board,
            lastmove=lastmove,
            check=check,
            squares=squares,
            size=self.width(),
            orientation=self.player_color  # flips board if player is black
        )
        self.load(bytearray(svg_data, encoding='utf-8'))
        
    def square_at_position(self, pos):
        """Convert screen coordinates to chess square taking board orientation into account."""
        file_size = self.width() / 8
        rank_size = self.height() / 8
        if self.player_color == chess.WHITE:
            file_idx = int(pos.x() / file_size)
            rank_idx = 7 - int(pos.y() / rank_size)
        else:
            # If the board is flipped (player is black), invert the x coordinate and y mapping.
            file_idx = 7 - int(pos.x() / file_size)
            rank_idx = int(pos.y() / rank_size)
        if 0 <= file_idx < 8 and 0 <= rank_idx < 8:
            return chess.square(file_idx, rank_idx)
        return None
        
    def get_piece_svg(self, piece, square):
        """Generate SVG for a single piece."""
        size = self.width() // 8  # size of one square
        piece_svg = chess.svg.piece(piece, size=size)
        return piece_svg

    def mousePressEvent(self, event):
        """Handle mouse press events for drag and click functionality."""
        if event.button() == Qt.LeftButton:
            square = self.square_at_position(event.position())
            if square is not None:
                # Store the start position for potential drag operation
                self.drag_start_position = event.position()
                
                # If clicking on a piece that can move, select it
                piece = self.board.piece_at(square)
                if piece and piece.color == self.board.turn:
                    self.selected_square = square
                    self.update_board()
            
    def mouseMoveEvent(self, event):
        """Handle mouse move events for drag operations."""
        if not (event.buttons() & Qt.LeftButton):
            return
            
        # Check if we've moved far enough to start a drag
        if self.drag_start_position is None:
            return
            
        # Calculate distance moved
        distance = (event.position() - self.drag_start_position).manhattanLength()
        if distance < QApplication.startDragDistance():
            return
            
        # Get the square at the drag start position
        from_square = self.square_at_position(self.drag_start_position)
        if from_square is None:
            return
            
        # Check if there's a piece that can be moved
        piece = self.board.piece_at(from_square)
        if not (piece and piece.color == self.board.turn):
            return
            
        # Start drag operation
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(from_square))
        drag.setMimeData(mime_data)

        # Create piece image for dragging
        piece_svg = self.get_piece_svg(piece, from_square)
        pixmap = QPixmap(100, 100)  # Fixed size for drag image
        pixmap.fill(Qt.transparent)
        pixmap.loadFromData(piece_svg.encode(), 'SVG')
        
        # Set the drag pixmap with the piece image
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))
        
        # Execute the drag
        self.selected_square = from_square
        self.update_board()
        result = drag.exec_(Qt.MoveAction)
        
        # Reset drag start position
        self.drag_start_position = None
            
    def mouseReleaseEvent(self, event):
        """Handle mouse release events for click-based moves."""
        if event.button() == Qt.LeftButton and self.drag_start_position is not None:
            # This is a click (not a drag) if we still have drag_start_position
            square = self.square_at_position(event.position())
            from_square = self.square_at_position(self.drag_start_position)
            
            # Reset drag start position
            self.drag_start_position = None
            
            if square is not None and from_square is not None:
                if square == from_square:
                    # Click on the same square (already handled in press event for selection)
                    pass
                else:
                    # Try to make a move
                    self.try_make_move(from_square, square)
            
    def dragEnterEvent(self, event):
        """Handle drag enter events."""
        if event.mimeData().hasText():
            event.acceptProposedAction()
    
    def dragMoveEvent(self, event):
        """Handle drag move events."""
        if event.mimeData().hasText():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """Handle drop events to complete a move."""
        if event.mimeData().hasText():
            # Get the source square from mime data
            from_square = int(event.mimeData().text())
            
            # Get the destination square from drop position
            to_square = self.square_at_position(event.position())
            
            if to_square is not None:
                # Try to make the move
                self.try_make_move(from_square, to_square)
                
            event.acceptProposedAction()
    
    def try_make_move(self, from_square, to_square):
        """Try to make a move and emit signals if successful."""
        # Create the move
        move = chess.Move(from_square, to_square)
        
        # Check if promotion
        if (self.board.piece_at(from_square).piece_type == chess.PAWN and 
            ((to_square >= 56 and self.board.turn == chess.WHITE) or 
             (to_square <= 7 and self.board.turn == chess.BLACK))):
            # Automatically promote to queen for simplicity
            move = chess.Move(from_square, to_square, promotion=chess.QUEEN)
        
        # Check if the move is legal
        if move in self.board.legal_moves:
            # Emit the move signal
            self.move_made.emit(move)
        
        # Reset selection regardless of move legality
        self.selected_square = None
        self.update_board()
        
    def resizeEvent(self, event):
        """Update the board when resized."""
        super().resizeEvent(event)
        self.update_board()
        
    def reset_board(self):
        """Reset the board to starting position."""
        self.board.reset()
        self.selected_square = None
        self.last_move = None
        self.correct_move = None
        self.update_board()
        
    def set_fen(self, fen):
        """Set the board to a specific FEN position and set player color.
           Player color is the opposite of the side to move (since computer plays first).
        """
        self.board.set_fen(fen)
        self.player_color = not self.board.turn  # set player to be the opposite color
        self.selected_square = None
        self.last_move = None
        self.update_board()


class PuzzleManager:
    """Handles loading and managing chess puzzles."""
    def __init__(self):
        self.puzzles = []
        self.current_puzzle = None
        self.current_move_index = 0
        self.puzzles_by_rating = {}
        self.dataframe = None
        
    def load_puzzle_dataset(self):
        """Load puzzles from Hugging Face parquet file using polars."""
        global PUZZLES_LOADED_FLAG
        global PUZZLES_DB
        
        if PUZZLES_LOADED_FLAG and PUZZLES_DB is not None:
            self.dataframe = PUZZLES_DB
            return PUZZLES_DB

        try:
            QApplication.processEvents()
            # df = pl.scan_parquet("hf://datasets/Lichess/chess-puzzles/data/train-00000-of-00003.parquet")
            abs_pth = os.path.abspath(sys.argv[0])
            install_dir = os.path.dirname(abs_pth)
            data_dir = os.path.join(install_dir, "datasets")
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            if not os.path.exists(os.path.join(data_dir, "data", "train-00000-of-00001.parquet")):
                start_hf_download(label_txt="Downloading Puzzle Dataset...", repo_id="Lichess/chess-puzzles", hf_filename="data/train-00000-of-00003.parquet", local_dir=data_dir)
            df = pl.scan_parquet(os.path.join(data_dir, "data", "train-00000-of-00003.parquet"))
            QApplication.processEvents()
            df = df.collect()
            self.dataframe = df
            PUZZLES_DB = df
            PUZZLES_LOADED_FLAG = True
            return df
        except Exception as e:
            print(f"Error loading puzzle dataset: {e}")
            return None
    
    def process_puzzles_from_dataframe(self, min_rating=400, max_rating=2000, limit=1000):
        """Process puzzles from the loaded dataframe within a rating range."""
        if self.dataframe is None:
            return False
            
        try:
            # Filter the dataframe by rating
            filtered_df = self.dataframe.filter(
                (pl.col("Rating") >= min_rating) & 
                (pl.col("Rating") <= max_rating)
            )
            
            # Limit the number of puzzles if needed
            if limit > 0:
                filtered_df = filtered_df.head(limit)
                
            self.puzzles = []
            self.puzzles_by_rating = {}
            
            # Convert dataframe rows to puzzle dictionaries
            for row in filtered_df.iter_rows(named=True):
                puzzle = {
                    'id': row.get('PuzzleId', ''),
                    'fen': row.get('FEN', ''),
                    'moves': row.get('Moves', '').split(),
                    'rating': row.get('Rating', 0),
                    'themes': row.get('Themes', '').split()
                }
                
                self.puzzles.append(puzzle)
                
                # Organize puzzles by rating range (in 100-point buckets)
                rating_bucket = (puzzle['rating'] // 100) * 100
                if rating_bucket not in self.puzzles_by_rating:
                    self.puzzles_by_rating[rating_bucket] = []
                self.puzzles_by_rating[rating_bucket].append(len(self.puzzles) - 1)
            
            return True
            
        except Exception as e:
            print(f"Error processing puzzles from dataframe: {e}")
            return False
    
    def load_puzzles_from_hf(self, min_rating=400, max_rating=2000, limit=1000):
        """Load puzzles from Hugging Face dataset within a rating range."""
        try:
            # URL for the Hugging Face Lichess puzzle dataset
            url = "https://huggingface.co/datasets/lichess/lichess-puzzles/resolve/main/lichess_db_puzzle.csv"
            
            # Download a sample of puzzles (first 10,000 lines)
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Process the CSV data
            content = io.StringIO(response.text)
            reader = csv.reader(content)
            
            # Skip header row if present
            header = next(reader, None)
            
            count = 0
            self.puzzles = []
            for row in reader:
                if count >= limit:
                    break
                    
                puzzle_id, fen, moves, rating, *_ = row
                rating = int(rating)
                
                if min_rating <= rating <= max_rating:
                    self.puzzles.append({
                        'id': puzzle_id,
                        'fen': fen,
                        'moves': moves.split(),
                        'rating': rating
                    })
                    count += 1
                    
                    # Organize puzzles by rating range (in 100-point buckets)
                    rating_bucket = (rating // 100) * 100
                    if rating_bucket not in self.puzzles_by_rating:
                        self.puzzles_by_rating[rating_bucket] = []
                    self.puzzles_by_rating[rating_bucket].append(len(self.puzzles) - 1)
            
            return True
            
        except Exception as e:
            print(f"Error loading puzzles: {e}")
            return False
    
    def load_puzzles_from_file(self, file_path):
        """Load puzzles from a local CSV file."""
        try:
            with open(file_path, 'r') as f:
                reader = csv.reader(f)
                # Skip header if exists
                header = next(reader, None)
                
                self.puzzles = []
                for row in reader:
                    puzzle_id, fen, moves, rating, *_ = row
                    rating = int(rating)
                    
                    self.puzzles.append({
                        'id': puzzle_id,
                        'fen': fen,
                        'moves': moves.split(),
                        'rating': rating
                    })
                    
                    # Organize puzzles by rating range (in 100-point buckets)
                    rating_bucket = (rating // 100) * 100
                    if rating_bucket not in self.puzzles_by_rating:
                        self.puzzles_by_rating[rating_bucket] = []
                    self.puzzles_by_rating[rating_bucket].append(len(self.puzzles) - 1)
                
            return True
            
        except Exception as e:
            print(f"Error loading puzzles from file: {e}")
            return False
    
    def get_puzzle_by_rating(self, min_rating, max_rating):
        """Get a random puzzle within the specified rating range."""
        eligible_puzzles = []
        for rating in range((min_rating // 100) * 100, max_rating + 1, 100):
            if rating in self.puzzles_by_rating:
                eligible_puzzles.extend(self.puzzles_by_rating[rating])
        
        if not eligible_puzzles:
            return None
        
        puzzle_idx = random.choice(eligible_puzzles)
        self.current_puzzle = self.puzzles[puzzle_idx]
        self.current_move_index = 0
        return self.current_puzzle
    
    def get_next_correct_move(self):
        """Get the next correct move in the current puzzle."""
        if not self.current_puzzle or self.current_move_index >= len(self.current_puzzle['moves']):
            return None
        
        correct_move = self.current_puzzle['moves'][self.current_move_index]
        return correct_move
    
    def advance_puzzle(self):
        """Advance to the next move in the puzzle."""
        if self.current_puzzle:
            self.current_move_index += 1
            return self.current_move_index < len(self.current_puzzle['moves'])
        return False


class ChessPuzzleApp(QMainWindow):
    """Main application window for the chess puzzle trainer."""
    def __init__(self):
        super().__init__()

        self.setWindowIcon(QIcon("./img/king.ico"))
        
        self.chess_board = ChessBoard()
        self.puzzle_manager = PuzzleManager()
        
        self.setWindowTitle("Chess Puzzle Trainer")
        self.setMinimumSize(800, 600)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the user interface."""
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        
        # Left side - chess board
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(self.chess_board, 1)
        
        # Feedback display
        self.feedback_label = QLabel()
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.feedback_label.setMinimumHeight(50)
        self.feedback_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        left_layout.addWidget(self.feedback_label)
        
        # Right side - controls
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Rating range selection
        rating_layout = QHBoxLayout()
        rating_layout.addWidget(QLabel("Rating Range:"))
        
        self.min_rating_combo = QComboBox()
        self.max_rating_combo = QComboBox()
        
        # Populate rating combos
        ratings = [r for r in range(400, 2901, 100)]
        for rating in ratings:
            self.min_rating_combo.addItem(str(rating))
            self.max_rating_combo.addItem(str(rating))
        
        # Set default values
        self.min_rating_combo.setCurrentText("400")
        self.max_rating_combo.setCurrentText("1300")
        
        rating_layout.addWidget(self.min_rating_combo)
        rating_layout.addWidget(QLabel("to"))
        rating_layout.addWidget(self.max_rating_combo)
        right_layout.addLayout(rating_layout)
        
        # Puzzle information
        self.puzzle_info = QLabel("No puzzle loaded")
        self.puzzle_info.setAlignment(Qt.AlignCenter)
        self.puzzle_info.setWordWrap(True)
        right_layout.addWidget(self.puzzle_info)
        
        # Interaction help
        help_label = QLabel("Drag pieces to move or click source and destination squares")
        help_label.setAlignment(Qt.AlignCenter)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("font-style: italic; color: #666;")
        right_layout.addWidget(help_label)
        
        # Spacer
        right_layout.addStretch(1)
        
        # Buttons
        # load_hf_button = QPushButton("Load from CSV")
        load_hf_parquet_button = QPushButton("Load Puzzles")
        load_file_button = QPushButton("Load from File")
        next_puzzle_button = QPushButton("Next Puzzle")
        reset_button = QPushButton("Reset Current Puzzle")

        right_layout.addWidget(load_hf_parquet_button)
        # right_layout.addWidget(load_hf_button)
        right_layout.addWidget(load_file_button)
        right_layout.addWidget(next_puzzle_button)
        right_layout.addWidget(reset_button)
        
        # Status display
        self.status_label = QLabel("Ready to load puzzles")
        self.status_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.status_label)
        
        # Add widgets to main layout
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 200])
        
        main_layout.addWidget(splitter)
        self.setCentralWidget(main_widget)
        
        # Connect signals
        self.chess_board.move_made.connect(self.handle_move_made)
        # load_hf_button.clicked.connect(self.load_puzzles_from_hf)
        load_hf_parquet_button.clicked.connect(self.load_puzzles_from_hf_parquet)
        load_file_button.clicked.connect(self.load_puzzles_from_file)
        next_puzzle_button.clicked.connect(self.load_next_puzzle)
        reset_button.clicked.connect(self.reset_current_puzzle)
        
    def handle_move_made(self, move):
        """Handle moves made on the board."""
        # Get the expected correct move (this will be the second move in the puzzle)
        correct_move_uci = self.puzzle_manager.get_next_correct_move()
        correct_move = chess.Move.from_uci(correct_move_uci) if correct_move_uci else None
        
        # Check if the move is correct
        if correct_move and move == correct_move:
            # Correct move
            self.show_feedback(True)
            self.chess_board.board.push(move)
            self.chess_board.last_move = move
            self.chess_board.update_board()
            
            # Advance to the next move in the puzzle
            has_more_moves = self.puzzle_manager.advance_puzzle()
            
            # If there are more moves, the engine makes its move (for moves beyond the second)
            if has_more_moves:
                QTimer.singleShot(500, self.make_engine_move)
            else:
                # Puzzle completed successfully
                msg_box = QMessageBox(self); msg_box.setWindowTitle("Puzzle Complete"); msg_box.setText("Congratulations! Puzzle solved correctly."); next_button = msg_box.addButton("Next", QMessageBox.AcceptRole); msg_box.exec_(); next_button == msg_box.clickedButton() and self.load_next_puzzle()
        else:
            # Incorrect move
            self.show_feedback(False)
    
    def make_engine_move(self):
        """Make the engine's move in the puzzle."""
        if self.puzzle_manager.current_puzzle:
            correct_move_uci = self.puzzle_manager.get_next_correct_move()
            if correct_move_uci:
                move = chess.Move.from_uci(correct_move_uci)
                self.chess_board.board.push(move)
                self.chess_board.last_move = move
                self.chess_board.update_board()
                self.puzzle_manager.advance_puzzle()
    
    def show_feedback(self, is_correct):
        """Show visual feedback for correct/incorrect moves."""
        if is_correct:
            self.feedback_label.setText("✓ Correct Move!")
            self.feedback_label.setStyleSheet("color: green; font-size: 24px; font-weight: bold;")
        else:
            self.feedback_label.setText("✗ Incorrect Move!")
            self.feedback_label.setStyleSheet("color: red; font-size: 24px; font-weight: bold;")
        
        # Clear feedback after a delay
        QTimer.singleShot(2000, self.clear_feedback)
    
    def clear_feedback(self):
        """Clear the feedback message."""
        self.feedback_label.setText("")
    
    # def load_puzzles_from_hf(self):
    #     """Load puzzles from Hugging Face dataset (CSV)."""
    #     self.status_label.setText("Loading puzzles from Hugging Face (CSV)...")
    #     QApplication.processEvents()
        
    #     min_rating = int(self.min_rating_combo.currentText())
    #     max_rating = int(self.max_rating_combo.currentText())
        
    #     success = self.puzzle_manager.load_puzzles_from_hf(min_rating, max_rating)
        
    #     if success:
    #         self.status_label.setText(f"Loaded {len(self.puzzle_manager.puzzles)} puzzles")
    #         self.load_next_puzzle()
    #     else:
    #         self.status_label.setText("Failed to load puzzles")
    #         QMessageBox.warning(self, "Error", "Failed to load puzzles from Hugging Face. Check your internet connection.")
    
    def load_puzzles_from_hf_parquet(self):
        """Load puzzles from Hugging Face dataset (Parquet)."""
        self.status_label.setText("Loading puzzles from Hugging Face (Parquet)...")
        QApplication.processEvents()
        
        # First check if puzzles are already loaded
        global PUZZLES_LOADED_FLAG
        if PUZZLES_LOADED_FLAG:
            self.status_label.setText("Using cached puzzle dataset...")
            QApplication.processEvents()
        
        # Load or use cached dataset
        df = self.puzzle_manager.load_puzzle_dataset()
        
        if df is not None:
            min_rating = int(self.min_rating_combo.currentText())
            max_rating = int(self.max_rating_combo.currentText())
            
            self.status_label.setText("Processing puzzles...")
            QApplication.processEvents()
            
            # Process the dataset
            success = self.puzzle_manager.process_puzzles_from_dataframe(min_rating, max_rating)
            
            if success:
                self.status_label.setText(f"Loaded {len(self.puzzle_manager.puzzles)} puzzles")
                self.load_next_puzzle()
            else:
                self.status_label.setText("Failed to process puzzles")
                QMessageBox.warning(self, "Error", "Failed to process puzzles from dataset.")
        else:
            self.status_label.setText("Failed to load dataset")
            QMessageBox.warning(self, "Error", "Failed to load puzzle dataset from Hugging Face. Check your internet connection and make sure the polars library is installed.")
    
    def load_puzzles_from_file(self):
        """Load puzzles from a local CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Puzzle File", "", "CSV Files (*.csv)"
        )
        
        if file_path:
            self.status_label.setText("Loading puzzles from file...")
            QApplication.processEvents()
            
            success = self.puzzle_manager.load_puzzles_from_file(file_path)
            
            if success:
                self.status_label.setText(f"Loaded {len(self.puzzle_manager.puzzles)} puzzles")
                self.load_next_puzzle()
            else:
                self.status_label.setText("Failed to load puzzles from file")
                QMessageBox.warning(self, "Error", "Failed to load puzzles from file. Check the file format.")
    
    def load_next_puzzle(self):
        """Load the next puzzle in the specified rating range."""
        if not self.puzzle_manager.puzzles:
            QMessageBox.information(self, "No Puzzles", "No puzzles available. Please load puzzles first.")
            return
        
        min_rating = int(self.min_rating_combo.currentText())
        max_rating = int(self.max_rating_combo.currentText())
        
        puzzle = self.puzzle_manager.get_puzzle_by_rating(min_rating, max_rating)
        
        if puzzle:
            self.chess_board.set_fen(puzzle['fen'])
            # Automatically let the engine (computer) make the first move.
            if puzzle['moves']:
                QTimer.singleShot(500, self.make_engine_move)
                self.puzzle_info.setText(
                    f"Puzzle ID: {puzzle['id']}\n"
                    f"Rating: {puzzle['rating']}\n"
                    f"Computer has moved. Your turn to play the second move."
                )
            else:
                self.puzzle_info.setText(
                    f"Puzzle ID: {puzzle['id']}\n"
                    f"Rating: {puzzle['rating']}\n"
                    f"Your turn to move."
                )
            self.feedback_label.setText("")
        else:
            QMessageBox.information(
                self, "No Puzzles", 
                f"No puzzles available in the rating range {min_rating}-{max_rating}."
            )
    
    def reset_current_puzzle(self):
        """Reset the current puzzle to its starting position and reapply computer move."""
        if self.puzzle_manager.current_puzzle:
            self.chess_board.set_fen(self.puzzle_manager.current_puzzle['fen'])
            self.puzzle_manager.current_move_index = 0
            self.feedback_label.setText("")
            # Automatically perform the computer move for the puzzle restart.
            if self.puzzle_manager.current_puzzle['moves']:
                QTimer.singleShot(500, self.make_engine_move)
                self.puzzle_info.setText(
                    f"Puzzle ID: {self.puzzle_manager.current_puzzle['id']}\n"
                    f"Rating: {self.puzzle_manager.current_puzzle['rating']}\n"
                    f"Computer has moved. Your turn to play the second move."
                )
    
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    window = ChessPuzzleApp()
    window.show()
    
    sys.exit(app.exec())
