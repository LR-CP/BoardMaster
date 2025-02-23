"""
Chess Game Analyzer
Requires: python-chess, PySide6, Stockfish engine installed
Save as chess_analyzer.py and run with: python chess_analyzer.py
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QScreen, QGuiApplication
from PySide6.QtCore import Qt
from main_window import BoardMaster

if __name__ == "__main__":
    """
    @brief Main entry point for the BoardMaster application.
    @details Initializes high DPI settings, creates the QApplication and the main window.
    """
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    window = BoardMaster()
    srcSize = QScreen.availableGeometry(QApplication.primaryScreen())
    frmX = (srcSize.width() - window.width()) / 2
    frmY = (srcSize.height() - window.height()) / 2
    window.move(frmX, frmY)
    if window.engine:
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit(1)
