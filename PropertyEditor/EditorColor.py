from PyQt5.QtWidgets import QPushButton, QColorDialog
from PyQt5.QtCore import pyqtSignal
from PyQt5.Qt import QColor

# This is a default color editor class that can be used with any color class that supports
# setRgb and getRgb like QColor.
# Should be fairly easy to make it work with other classes as you see fit.
class EditorColor(QPushButton):
    dataChanged = pyqtSignal(object)

    def __init__(self, value):
        super().__init__()

        self._value = value
        self._updateButtonColor()

        self.clicked.connect(self._pickColor)

    def _pickColor(self):
        r, g, b = self._value.getRgb()
        dialog = QColorDialog(QColor(r, g, b), self)
        dialog.setOption(QColorDialog.DontUseNativeDialog)
        dialog.setStyleSheet("")
        if dialog.exec() == QColorDialog.Accepted:
            newR, newG, newB, newA = dialog.currentColor().getRgb()
            if [newR, newG, newB] != [r, g, b]:
                self._value.setRgb(newR, newG, newB)
                self.dataChanged.emit(self._value)
                self._updateButtonColor()

    def _updateButtonColor(self):
        r, g, b = self._value.getRgb()
        self.setStyleSheet("EditorColor {background-color:rgb(" + str(r) + "," + str(g) + "," + str(b) + ")}")
