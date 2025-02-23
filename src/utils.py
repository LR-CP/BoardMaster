from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QHBoxLayout, QLabel
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QToolTip
from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt

class EvaluationGraphPG(QWidget):
    def __init__(self, game_tab=None, parent=None):
        """
        @brief Construct the evaluation graph widget.
        @param game_tab (Optional) The game tab instance to call goto_move on click.
        @param parent The parent widget.
        """
        super().__init__(parent)
        self.game_tab = game_tab
        self.plot_widget = pg.PlotWidget()
        # Set size policy to allow resizing and a default smaller minimum size
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.plot_widget.setMinimumHeight(100)
        self.plot_widget.setMaximumHeight(200)
        layout = QVBoxLayout(self)
        layout.addWidget(self.plot_widget)
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.setLabel('left', "Evaluation (centipawns)")
        self.plot_widget.setLabel('bottom', "Move Number")
        # Add and show the legend
        self.plot_widget.addLegend(offset=(10, 7))
        self.plot_widget.plotItem.legend.setVisible(True)
        # Set x-axis tick spacing to 1  
        x_axis = self.plot_widget.getAxis('bottom')
        x_axis.setTicks([[(i, str(i)) for i in range(0, 101, 1)]])
        
        self.white_curve = self.plot_widget.plot(pen=pg.mkPen('b', width=2), name="White")
        self.black_curve = self.plot_widget.plot(pen=pg.mkPen('r', width=2), name="Black")

        # Connect signals for hover and click
        self.plot_widget.scene().sigMouseMoved.connect(self.onMouseMoved)
        self.plot_widget.scene().sigMouseClicked.connect(self.onMouseClicked)

    def update_graph(self, white_evals, black_evals):
        """
        @brief Update the graph with new evaluation data.
        @param white_evals List of White evaluations.
        @param black_evals List of Black evaluations.
        """
        x_white = list(range(1, len(white_evals) + 1))
        x_black = list(range(1, len(black_evals) + 1))
        self.white_curve.setData(x_white, white_evals)
        self.black_curve.setData(x_black, black_evals)

    def onMouseMoved(self, pos):
        """
        @brief Show a tooltip with the x index when hovering over the graph.
        @param pos QPointF from the scene.
        """
        vb = self.plot_widget.plotItem.vb
        mousePoint = vb.mapSceneToView(pos)
        x = int(mousePoint.x()+1)
        QToolTip.showText(QCursor.pos(), f"Move: {x}", self.plot_widget)

    def onMouseClicked(self, event):
        """
        @brief On left click in the graph, move to the corresponding move on the chessboard.
        @param event The mouse click event.
        """
        if event.button() == Qt.LeftButton:
            pos = event.scenePos()
            vb = self.plot_widget.plotItem.vb
            mousePoint = vb.mapSceneToView(pos)
            move_index = int(mousePoint.x()+1)
            if self.game_tab is not None:
                self.game_tab.goto_move(move_index*2-1-1) # Dumb way to get the move index but it works


class MoveLabel(QLabel):
    def __init__(self, text, move_index, game_tab, parent=None):
        """
        @brief Initialize a label that represents a move.
        @param text Display text.
        @param move_index Index of the move.
        @param game_tab Reference to the GameTab instance.
        @param parent Parent widget.
        """
        super().__init__(text, parent)
        self.move_index = move_index
        self.game_tab = game_tab
        self.setStyleSheet("padding: 2px; margin: 1px;")
        
    def mousePressEvent(self, event):
        self.game_tab.goto_move(self.move_index)

class MoveRow(QWidget):
    def __init__(self, move_number, white_move, white_eval, white_index, 
                 game_tab, black_move=None, black_eval=None, black_index=None, parent=None):
        """
        @brief Construct a widget representing one move pair with optional variation.
        @param move_number The number of the move pair.
        @param white_move White's move in SAN.
        @param white_eval Evaluation symbol for White.
        @param white_index White move index.
        @param game_tab Parent game tab.
        @param black_move (Optional) Black's move in SAN.
        @param black_eval (Optional) Evaluation symbol for Black.
        @param black_index (Optional) Black move index.
        @param parent Parent widget.
        """
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
        """
        @brief Highlight the white move widget.
        """
        self.white_label.setStyleSheet("background-color: rgba(255, 255, 0, 100);")
        self.black_label.setStyleSheet("background-color: grey")

    def highlight_black(self):
        """
        @brief Highlight the black move widget.
        """
        self.white_label.setStyleSheet("background-color: grey")
        self.black_label.setStyleSheet("background-color: rgba(255, 255, 0, 100);")

    def highlight_off(self):
        """
        @brief Remove all highlights from the move labels.
        """
        self.white_label.setStyleSheet("background-color: grey")
        self.black_label.setStyleSheet("background-color: grey")