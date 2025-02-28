from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QHBoxLayout, QLabel, QDialog, QTextEdit, QPushButton, QToolTip, QMenu
import pyqtgraph as pg
from PySide6.QtGui import QCursor
from PySide6.QtCore import Qt
from dialogs import NoteDialog

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
        
        # Add a vertical infinite line that tracks current move
        self.current_move_line = pg.InfiniteLine(pos=0, angle=90, pen=pg.mkPen('g', width=2, style=Qt.DotLine))
        self.plot_widget.addItem(self.current_move_line)

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
                self.game_tab.goto_move(move_index*2-1-1)  # Dumb way to get the move index but it works

    def set_current_move(self, move_number):
        """
        @brief Move the vertical tracking line to the given move number (along the x-axis).
        @param move_number The move index to track.
        """
        self.current_move_line.setValue(move_number)

class MoveLabel(QLabel):
    def __init__(self, text, move_index, game_tab, parent=None):
        super().__init__(text, parent)
        self.move_index = move_index
        self.game_tab = game_tab
        self.setStyleSheet("padding: 2px; margin: 1px;")
        self.note = ""  # Store the note text
        # NEW properties to hold evaluation data:
        self.eval_symbol = ""  # For example: "✅", "⚠️", etc.
        self.eval_score = 0    # For example, centipawn value

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.game_tab.goto_move(self.move_index)
        elif event.button() == Qt.RightButton:
            self.show_context_menu(event.pos())
    
    def show_context_menu(self, pos):
        """Show context menu with note options."""
        context_menu = QMenu(self)
        
        if self.note:
            view_action = context_menu.addAction("View Note 📝")
            view_action.triggered.connect(self.view_note)
            edit_action = context_menu.addAction("Edit Note ✏️")
            edit_action.triggered.connect(self.show_note_dialog)

            # delete_action = context_menu.addAction("Delete Note 🗑️")
            # delete_action.triggered.connect(self.view_note)
            # edit_action = context_menu.addAction("Edit Note ✏️")
            # edit_action.triggered.connect(self.show_note_dialog)
        else:
            add_action = context_menu.addAction("Add Note ➕")
            add_action.triggered.connect(self.show_note_dialog)
        
        context_menu.exec_(self.mapToGlobal(pos))
    
    def view_note(self):
        """Show the note in view-only mode."""
        if self.note:
            dialog = NoteDialog(self.note, self)
            dialog.note_edit.setReadOnly(True)
            dialog.setWindowTitle("View Note")
            dialog.exec_()
            
    def show_note_dialog(self):
        """Show dialog for editing the move note."""
        dialog = NoteDialog(self.note, self)
        if dialog.exec_() == QDialog.Accepted:
            self.note = dialog.get_note()
            # Save note to GameTab's persistent storage
            self.game_tab.move_notes[self.move_index] = self.note
            self.update_tooltip()
            self.update_style()
            
    def update_tooltip(self):
        """Update the tooltip to show the note if it exists."""
        if self.note:
            self.setToolTip(self.note)
        else:
            self.setToolTip("")
            
    def update_style(self):
        """Update the label style to indicate presence of a note."""
        if self.note:
            current_text = self.text().split(" 📝")[0]  # Remove existing icon if any
            self.setText(f"{current_text} 📝")  # Add note icon
        else:
            current_text = self.text().split(" 📝")[0]
            self.setText(current_text)

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
        
        # Move number label
        number_label = QLabel(f"{move_number}.")
        number_label.setFixedWidth(30)
        layout.addWidget(number_label)
        
        # White's move label
        white_text = f"{white_move} {white_eval}"
        self.white_label = MoveLabel(white_text, white_index, game_tab, self)
        self.white_label.setFixedWidth(100)
        # NEW: Initialize evaluation properties for white move
        self.white_label.eval_symbol = white_eval
        self.white_label.eval_score = 0  
        layout.addWidget(self.white_label)
        
        # Black's move label if available
        if black_move:
            black_text = f"{black_move} {black_eval}"
            self.black_label = MoveLabel(black_text, black_index, game_tab, self)
            self.black_label.setFixedWidth(100)
            self.black_label.eval_symbol = black_eval
            self.black_label.eval_score = 0
            layout.addWidget(self.black_label)
        else:
            self.black_label = QLabel()
        
        layout.addStretch()

        # Set auto fill background and initialize highlight off.
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
