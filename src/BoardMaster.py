"""
BoardMaster
A free chess analysis tool
"""

#TODO: Add feature to load fen on live game tab
#TODO: Add board editor feature to live game tab
#TODO: Add qsetting for piece images folder

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QScreen, QGuiApplication, Qt
from main_window import BoardMaster

if __name__ == "__main__":
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    QApplication.processEvents()
    window = BoardMaster()
    srcSize = QScreen.availableGeometry(QApplication.primaryScreen())
    frmX = (srcSize.width() - window.width()) / 2
    frmY = (srcSize.height() - window.height()) / 2
    window.move(frmX, frmY)
    if window.engine:
        window.show()
        # splash.finish(window)
        sys.exit(app.exec())
    else:
        sys.exit(1)
