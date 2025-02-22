from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QHBoxLayout, QLabel
import pyqtgraph as pg

class EvaluationGraphPG(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_widget = pg.PlotWidget(title="Game Evaluation")
        # Set size policy to allow resizing and a default smaller minimum size
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_widget.setMinimumHeight(100)
        self.plot_widget.setMaximumHeight(200)
        layout = QVBoxLayout(self)
        layout.addWidget(self.plot_widget)
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', "Evaluation (centipawns)")
        self.plot_widget.setLabel('bottom', "Move Number")
        # Set x-axis tick spacing to 1
        x_axis = self.plot_widget.getAxis('bottom')
        x_axis.setTickSpacing(1, 1)
        
        self.white_curve = self.plot_widget.plot(pen=pg.mkPen('b', width=2), symbol='o', name="White")
        self.black_curve = self.plot_widget.plot(pen=pg.mkPen('r', width=2), symbol='o', name="Black")

    def update_graph(self, white_evals, black_evals):
        x_white = list(range(1, len(white_evals) + 1))
        x_black = list(range(1, len(black_evals) + 1))
        self.white_curve.setData(x_white, white_evals)
        self.black_curve.setData(x_black, black_evals)


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
        self.white_label = MoveLabel(white_text, white_index, game_tab, self)
        self.white_label.setFixedWidth(100)
        layout.addWidget(self.white_label)
        
        # Black's move if exists
        if black_move:
            black_text = f"{black_move} {black_eval}"
            self.black_label = MoveLabel(black_text, black_index, game_tab, self)
            self.black_label.setFixedWidth(100)
            layout.addWidget(self.black_label)
        else:
            self.black_label = QLabel()
        
        layout.addStretch()

        # NEW: Add method to highlight moves
        self.white_label.setAutoFillBackground(True)
        self.black_label.setAutoFillBackground(True)
        self.highlight_off()

    def highlight_white(self):
        self.white_label.setStyleSheet("background-color: rgba(255, 255, 0, 100);")
        self.black_label.setStyleSheet("background-color: grey")

    def highlight_black(self):
        self.white_label.setStyleSheet("background-color: grey")
        self.black_label.setStyleSheet("background-color: rgba(255, 255, 0, 100);")

    def highlight_off(self):
        self.white_label.setStyleSheet("background-color: grey")
        self.black_label.setStyleSheet("background-color: grey")