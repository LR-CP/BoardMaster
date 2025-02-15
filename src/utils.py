from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

class MoveLabel(QLabel):
    def __init__(self, text, move_index, game_tab, parent=None):
        super().__init__(text, parent)
        self.move_index = move_index
        self.game_tab = game_tab
        self.setStyleSheet("padding: 2px; margin: 1px;")
        
    def mousePressEvent(self, event):
        self.game_tab.goto_move(self.move_index)

class MoveRow(QWidget):
    def __init__(self, move_number, white_move, white_eval, white_index, 
                 game_tab, black_move=None, black_eval=None, black_index=None, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        
        # Move number
        number_label = QLabel(f"{move_number}.")
        number_label.setFixedWidth(30)
        layout.addWidget(number_label)
        
        # White's move
        white_text = f"{white_move} {white_eval}"
        white_label = MoveLabel(white_text, white_index, game_tab, self)
        white_label.setFixedWidth(100)
        layout.addWidget(white_label)
        
        # Black's move if exists
        if black_move:
            black_text = f"{black_move} {black_eval}"
            black_label = MoveLabel(black_text, black_index, game_tab, self)
            black_label.setFixedWidth(100)
            layout.addWidget(black_label)
        
        layout.addStretch()