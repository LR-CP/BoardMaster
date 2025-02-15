from PySide6.QtWidgets import *
from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon
import os


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BoardMaster Help")
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.resize(600, 400)

        layout = QVBoxLayout(self)

        # Help text explaining the program
        help_text = (
            "Welcome to BoardMaster!\n\n"
            "BoardMaster is a chess game analyzer that leverages the Stockfish engine and the python-chess "
            "library to provide move-by-move evaluations for chess games loaded in PGN format. "
            "It provides a rich graphical interface built with PySide6 for navigating through games, "
            "displaying an evaluation bar, annotated moves, and interactive board controls.\n\n"
            "Features:\n"
            "• Load games by pasting PGN text or opening a PGN file.\n"
            "• Automatic analysis of each move to assess accuracy, identify mistakes, and highlight excellent moves.\n"
            "• A dynamic evaluation bar that reflects the positional advantage based on pre-computed game analysis.\n"
            "• Move navigation controls: first, previous, next, and last move, as well as a board flip option.\n"
            "• Interactive board play for testing positions.\n"
            "• Customizable engine settings, including analysis depth and number of analysis lines.\n\n"
            "How to Use BoardMaster:\n"
            "1. Load a game by pasting PGN text into the provided input area or by opening a PGN file.\n"
            "2. Once loaded, the game is automatically analyzed, and move evaluations are computed.\n"
            "3. Use the navigation buttons to move through the game and view evaluations and annotations.\n"
            "4. The evaluation bar visually displays the advantage between White and Black.\n"
            "5. Adjust settings via the Settings menu to customize the engine analysis parameters.\n"
            "6. Use the interactive board tool to experiment with positions directly.\n\n"
            "Enjoy exploring your chess games with BoardMaster!"
        )

        # Using QTextBrowser to allow for rich text or scrolling
        text_browser = QTextBrowser(self)
        text_browser.setPlainText(help_text)
        text_browser.setReadOnly(True)
        layout.addWidget(text_browser)

        # Add an OK button to close the dialog
        button_box = QDialogButtonBox(QDialogButtonBox.Ok, self)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setWindowIcon(QIcon("./img/king.ico"))
        self.settings = QSettings("BoardMaster", "BoardMaster")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Engine Settings:"))

        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, os.cpu_count())
        self.thread_spin.setValue(self.settings.value("engine/threads", 4, int))
        layout.addWidget(QLabel("Threads:"))
        layout.addWidget(self.thread_spin)

        self.memory_spin = QSpinBox()
        self.memory_spin.setRange(1, 8192)
        self.memory_spin.setSingleStep(16)
        self.memory_spin.setValue(self.settings.value("engine/memory", 16, int))
        layout.addWidget(QLabel("Memory:"))
        layout.addWidget(self.memory_spin)

        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 100)
        self.depth_spin.setValue(self.settings.value("engine/depth", 20, int))
        layout.addWidget(QLabel("Analysis Depth:"))
        layout.addWidget(self.depth_spin)

        self.arrows_spin = QSpinBox()
        self.arrows_spin.setRange(1, 10)
        self.arrows_spin.setValue(self.settings.value("engine/lines", 3, int))
        layout.addWidget(QLabel("Number of Lines:"))
        layout.addWidget(self.arrows_spin)

        self.seconds_input = QDoubleSpinBox()
        self.seconds_input.setRange(0, 5)
        self.seconds_input.setSingleStep(0.1)
        self.seconds_input.setValue(self.settings.value("analysis/postime", 0.1, float))
        layout.addWidget(QLabel("Time for single position analysis (seconds):"))
        layout.addWidget(self.seconds_input)

        self.seconds_input2 = QDoubleSpinBox()
        self.seconds_input2.setRange(0, 5)
        self.seconds_input2.setSingleStep(0.1)
        self.seconds_input2.setValue(
            self.settings.value("analysis/fulltime", 0.1, float)
        )
        layout.addWidget(QLabel("Time for full game analysis (seconds):"))
        layout.addWidget(self.seconds_input2)

        self.show_arrows = QCheckBox("Show Analysis Arrows")
        self.show_arrows.setChecked(
            self.settings.value("display/show_arrows", True, bool)
        )
        layout.addWidget(self.show_arrows)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)

    def save_settings(self):
        self.settings.setValue("engine/depth", self.depth_spin.value())
        self.settings.setValue("display/show_arrows", self.show_arrows.isChecked())
        self.settings.setValue("engine/lines", self.arrows_spin.value())
        self.settings.setValue("analysis/postime", self.seconds_input.value())
        self.settings.setValue("analysis/fulltime", self.seconds_input2.value())
        self.settings.setValue("engine/threads", self.thread_spin.value())
        self.settings.setValue("engine/memory", self.memory_spin.value())
        self.parent().engine = self.parent().initialize_engine()
        self.accept()