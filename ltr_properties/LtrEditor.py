from .ObjectTree import ObjectTree
from .Icons import Icons
from .PropertyEditorWidget import PropertyEditorWidget
from .Serializer import Serializer
from . import TypeUtils

import inspect
import threading
import os

from PyQt5.QtCore import QSize
from PyQt5.QtWidgets import QWidget, QTabWidget, QHBoxLayout, QVBoxLayout, QScrollArea, QShortcut, QPushButton, QMessageBox
from PyQt5.QtGui import QKeySequence

class LtrEditor(QWidget):
    def __init__(self, root, classModule, classModuleRootFolders=None, serializerIndent = None, threadLock=threading.Lock(), parent=None):
        super().__init__(parent)

        # Make sure icons are loaded before we use them.
        Icons.LoadIcons()

        self._threadLock = threadLock

        if classModuleRootFolders == None:
            classModuleRootFolders = [os.path.dirname(inspect.getfile(classModule))]

        classDict = TypeUtils.getClasses(classModule, classModuleRootFolders)

        self._serializer = Serializer(root, classDict, indent=serializerIndent)

        mainLayout = QHBoxLayout(self)

        self._objectTree = ObjectTree(root, classDict)
        sizePolicy = self._objectTree.sizePolicy()
        sizePolicy.setHorizontalStretch(1)
        self._objectTree.setSizePolicy(sizePolicy)
        self._objectTree.fileActivated.connect(self._openFile)
        self._objectTree.pathDeleted.connect(self._onPathDeleted)
        mainLayout.addWidget(self._objectTree)

        rightPanel = QWidget()
        sizePolicy = rightPanel.sizePolicy()
        sizePolicy.setHorizontalStretch(2)
        rightPanel.setSizePolicy(sizePolicy)
        mainLayout.addWidget(rightPanel)

        rightLayout = QVBoxLayout(rightPanel)
        rightLayout.setContentsMargins(0, 0, 0, 0)

        buttonWidget = QWidget()
        self._buttonLayout = QHBoxLayout(buttonWidget)
        self._buttonLayout.setContentsMargins(0, 0, 0, 0)
        rightLayout.addWidget(buttonWidget)

        self._saveButton = QPushButton(Icons.Save, "")
        self._saveButton.clicked.connect(self._onSaveClicked)
        self._saveShortcut = QShortcut(QKeySequence("Ctrl+S"), self, self._onSaveClicked)
        self._saveButton.setFixedSize(24, 24)
        self._saveButton.setIconSize(QSize(24, 24))
        self._buttonLayout.addWidget(self._saveButton)

        self._revertButton = QPushButton(Icons.Revert, "")
        self._revertButton.clicked.connect(self._onRevertClicked)
        self._revertButton.setFixedSize(24, 24)
        self._revertButton.setIconSize(QSize(24, 24))
        self._buttonLayout.addWidget(self._revertButton)

        self._buttonLayout.addStretch()

        self._tabWidget = QTabWidget()
        self._tabWidget.setTabsClosable(True)
        self._tabWidget.tabCloseRequested.connect(self._onTabCloseRequested)
        self._tabWidget.currentChanged.connect(self._updateDirtyState)
        self._closeTabShortcut = QShortcut(QKeySequence("Ctrl+W"), self, self._onCloseCurrentTab)
        rightLayout.addWidget(self._tabWidget)

        self._customEditorMappings = {}
        self._tabInfo = []

        self._updateDirtyState()

    def addTargetObject(self, obj, name, path, dataChangeCallback=None):
        scrollArea = QScrollArea()

        pe = PropertyEditorWidget(self._serializer)
        pe.setThreadLock(self._threadLock)
        for objType, editType in self._customEditorMappings.items():
            pe.registerCustomEditor(objType, editType)
        pe.setTargetObject(obj)

        pe.editorGenerator().gotoObject.connect(self._onGotoObject)

        scrollArea.setWidget(pe)

        if dataChangeCallback:
            pe.dataChanged.connect(dataChangeCallback)

        pe.dataChanged.connect(lambda: self._markTabDirty(path))

        tabInfo = {"path": path, "dirty": False}
        self._tabInfo.append(tabInfo)

        self._tabWidget.addTab(scrollArea, name)

    def addCustomEditorMapping(self, objType, editorType):
        self._customEditorMappings[objType] = editorType

    def customEditorMappings(self):
        return self._customEditorMappings

    def objectTree(self):
        return self._objectTree

    def threadLock(self):
        return self._threadLock

    def _markTabDirty(self, path):
        for tabIndex, info in enumerate(self._tabInfo):
            if info["path"] == path and not info["dirty"]:
                info["dirty"] = True

                tabText = self._tabWidget.tabText(tabIndex)
                self._tabWidget.setTabText(tabIndex, tabText + "*")
                self._updateDirtyState()

    def _onGotoObject(self, path):
        name = os.path.basename(path).replace(".json", "")
        self._openFile(name, path)

    def _onCloseCurrentTab(self):
        if self._tabWidget.count() > 0: 
            self._onTabCloseRequested(self._tabWidget.currentIndex())

    def _onPathDeleted(self, path):
        for i in range(len(self._tabInfo) - 1, -1, -1):
            if path in self._tabInfo[i]["path"]:
                del self._tabInfo[i]
                self._tabWidget.removeTab(i)

    def _onRevertClicked(self):
        if self._tabWidget.currentIndex() >= 0:
            path = self._tabInfo[self._tabWidget.currentIndex()]["path"]
            targetObject = self._serializer.load(path)
            self._tabWidget.currentWidget().widget().setTargetObject(targetObject)

    def _onSaveClicked(self):
        tabIndex = self._tabWidget.currentIndex()
        if tabIndex >= 0:
            self._saveTab(tabIndex)

    def _onTabCloseRequested(self, index):
        actuallyClose = True
        tabInfo = self._tabInfo[index]
        if tabInfo["dirty"]:
            reply = QMessageBox.question(self, "Save?", "Save changes to " + tabInfo["path"] + "?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            
            if reply == QMessageBox.Yes:
                self._saveTab(index)
            elif reply == QMessageBox.Cancel:
                actuallyClose = False

        if actuallyClose:
            self._tabWidget.removeTab(index)
            del self._tabInfo[index]

    def _openFile(self, name, path):
        path = os.path.abspath(path)
        obj = self._serializer.load(path)

        foundIndex = -1
        for tabIndex in range(self._tabWidget.count()):
            if self._tabInfo[tabIndex]["path"] == path:
                foundIndex = tabIndex
                break

        if foundIndex == -1:
            foundIndex = self._tabWidget.count()
            self.addTargetObject(obj, name, path)

        self._tabWidget.setCurrentIndex(foundIndex)
        self._tabWidget.setFocus()
        self._updateDirtyState()

    def _saveTab(self, tabIndex):
        tabInfo = self._tabInfo[tabIndex]
        path = tabInfo["path"]
        pe = self._tabWidget.widget(tabIndex).widget()
        targetObject = pe.targetObject()
        self._serializer.save(path, targetObject)
        tabText = self._tabWidget.tabText(tabIndex)
        self._tabWidget.setTabText(tabIndex, tabText.replace("*", ""))
        tabInfo["dirty"] = False
        self._updateDirtyState()

    def _updateDirtyState(self):
        dirty = False
        if self._tabWidget.currentIndex() >= 0:
            dirty = self._tabInfo[self._tabWidget.currentIndex()]["dirty"]
        self._saveButton.setEnabled(dirty)
        self._revertButton.setEnabled(dirty)
        self._saveShortcut.setEnabled(dirty)