import chess
import chess.pgn
import chess.engine
import chess.svg
import pkg_resources
import tempfile
from PySide6.QtWidgets import *
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
import sys
from interactive_board import BoardEditor
from gametab import GameTab
from dialogs import *

# TODO: Add export PGN functionality

class BoardMaster(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BoardMaster")
        self.setGeometry(100, 100, 1600, 900)
        self.setFixedSize(1600, 900)
        self.setWindowIcon(QIcon("./img/king.ico"))

        self.settings = QSettings("BoardMaster", "BoardMaster")

        self.engine = self.initialize_engine()
        if not self.engine:
            return

        self.create_gui()
        self.create_menus()

    def create_gui(self):
        # Create main layout
        main_layout = QHBoxLayout()
        
        # Left side with tab widget
        self.tab_widget = QTabWidget(tabsClosable=True)
        self.tab_widget.tabCloseRequested.connect(self.tab_widget.removeTab)
        self.new_tab = GameTab(self)
        self.tab_widget.addTab(self.new_tab, "Live Game")
        main_layout.addWidget(self.tab_widget)

        # Right side with PGN input
        right_panel = QWidget()
        right_panel.setFixedWidth(300)  # Fixed width of 300px
        right_layout = QVBoxLayout(right_panel)
        
        # PGN widgets
        right_layout.addWidget(QLabel("PGN Input:"))
        self.pgn_text = QTextEdit()
        load_button = QPushButton("Load Game")
        load_button.clicked.connect(self.load_game)
        
        right_layout.addWidget(self.pgn_text)
        right_layout.addWidget(load_button)
        main_layout.addWidget(right_panel)

        # Create central widget to hold the layout
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # pgn_dock.setWidget(pgn_widget)
        # self.addDockWidget(Qt.RightDockWidgetArea, pgn_dock)

        # # NEW: Create dock widgets for move list, analysis, and evaluation graph extracted from GameTab
        # self.move_dock = QDockWidget("Move List", self)
        # self.move_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        # self.move_dock.setWidget(self.new_tab.move_list)
        # self.addDockWidget(Qt.RightDockWidgetArea, self.move_dock)
        
        # self.analysis_dock = QDockWidget("Analysis", self)
        # self.analysis_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        # self.analysis_dock.setWidget(self.new_tab.analysis_text)
        # self.addDockWidget(Qt.RightDockWidgetArea, self.analysis_dock)
        # # Tabify move list and analysis docks together
        # self.tabifyDockWidget(self.move_dock, self.analysis_dock)
        
        # self.eval_dock = QDockWidget("Game Evaluation", self)
        # self.eval_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        # self.eval_dock.setWidget(self.new_tab.eval_graph)
        # self.addDockWidget(Qt.BottomDockWidgetArea, self.eval_dock)

    def create_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        open_pgn = QAction("Open PGN File", self)
        open_pgn.setShortcut(QKeySequence("Ctrl+O"))
        open_pgn.triggered.connect(self.open_pgn_file)
        file_menu.addAction(open_pgn)

        tool_menu = menubar.addMenu("&Tools")
        interactive_board_action = QAction("Play Current Position", self)
        interactive_board_action.setShortcut(QKeySequence("Ctrl+P"))
        interactive_board_action.triggered.connect(self.open_interactive_board)
        tool_menu.addAction(interactive_board_action)
        # Add PGN Splitter action
        split_pgn_action = QAction("PGN Splitter", self)
        split_pgn_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        split_pgn_action.triggered.connect(self.show_pgn_splitter)
        tool_menu.addAction(split_pgn_action)
        # Add PGN Export action
        export_pgn_action = QAction("Export PGN", self)
        export_pgn_action.setShortcut(QKeySequence("Ctrl+Shift+E"))
        export_pgn_action.triggered.connect(self.export_pgn)
        tool_menu.addAction(export_pgn_action)

        settings_menu = menubar.addMenu("&Settings")
        open_settings = QAction("Engine Settings", self)
        open_settings.setShortcut(QKeySequence("Ctrl+Shift+P"))
        open_settings.triggered.connect(self.open_settings)
        settings_menu.addAction(open_settings)

        help_menu = menubar.addMenu("&Help")
        open_help = QAction("How To Use", self)
        open_help.setShortcut(QKeySequence("F1"))
        open_help.triggered.connect(self.open_help)
        help_menu.addAction(open_help)

    def initialize_engine(self):
        try:
            engine_path = self.settings.value("engine/path", "", str)
            if not engine_path:
                # Show settings dialog if no engine path is set
                QMessageBox.information(self, "Engine Setup Required", 
                                    "No chess engine found. Please select one in Settings.")
                dialog = SettingsDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    # Try to get the newly set engine path
                    engine_path = self.settings.value("engine/path", "", str)
                    if not engine_path:
                        return None
                else:
                    return None
                    
            transport = chess.engine.SimpleEngine.popen_uci(engine_path)
            # Configure engine settings
            transport.configure({
                "Threads": self.settings.value("engine/threads", 4, int),
                "Hash": self.settings.value("engine/memory", 16, int)
            })
            return transport
        except Exception as e:
            QMessageBox.critical(self, "Engine Error", 
                            f"Failed to initialize engine: {str(e)}")
            return None

    def keyPressEvent(self, event):
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, GameTab):
            current_tab.keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()
    
    def show_pgn_splitter(self):
        splitter = PGNSplitterDialog(self)
        splitter.exec()
    
    def export_pgn(self):
        pgn_str, fname = self.new_tab.export_pgn()
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save PGN File", fname, "PGN files (*.pgn)"
        )
        if file_name:
            with open(file_name, "w") as f:
                f.write(pgn_str)

    def open_help(self):
        help_dialog = HelpDialog(self)
        help_dialog.exec()

    def open_pgn_file(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open PGN File", "", "PGN files (*.pgn)"
        )
        if file_name:
            with open(file_name, "r") as f:
                self.pgn_text.setText(f.read())
            self.load_game()

    def open_interactive_board(self):
        if self.new_tab:
            fen=self.new_tab.current_board.fen()
        else:
            fen = None
        self.interactive_board = BoardEditor(engine=self.engine,
                                             fen=fen,
                                             threads=self.settings.value("engine/threads", 4, int),
                                             multipv=self.settings.value("engine/lines", 3, int),
                                             mem=self.settings.value("engine/memory", 16, int),
                                             time=self.settings.value("analysis/postime", 3, int),
                                             depth=self.settings.value("engine/depth", 40, int)
                                             )
        self.interactive_board.show()

    def load_game(self):
        pgn_string = self.pgn_text.toPlainText()
        self.new_tab = GameTab(self)
        if self.new_tab.load_pgn(pgn_string):
            self.tab_widget.addTab(self.new_tab, f"{self.new_tab.hdrs.get("White")}_{self.new_tab.hdrs.get("Black")}_{self.new_tab.hdrs.get("Date").replace(".", "_")}")
            self.tab_widget.setCurrentWidget(self.new_tab)

    def analyze_position(self, board):
        depth = self.settings.value("engine/depth", 20, int)
        self.engine.analyse(board, chess.engine.Limit(depth=depth))

    def closeEvent(self, event):
        if hasattr(self, "engine") and self.engine:
            self.engine.quit()
        super().closeEvent(event)
