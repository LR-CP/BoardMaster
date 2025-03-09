"""
BoardMaster
A free chess analysis tool
"""

#TODO: Add feature to load fen on live game tab
#TODO: Add board editor feature to live game tab

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QScreen, QGuiApplication
from PySide6.QtCore import Qt
from main_window import BoardMaster

if __name__ == "__main__":
    # QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
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
