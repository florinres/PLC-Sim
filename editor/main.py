"""Aplicația 1: editorul de circuite LAD.  Rulare:  python -m editor.main"""
import sys
from pathlib import Path

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QDockWidget, QFileDialog, QMainWindow, QMessageBox)
from PySide6.QtCore import Qt

from core.io import load_circuit, save_circuit
from editor.canvas import CircuitScene, CircuitView
from editor.palette import Palette

CIRCUITS_DIR = Path(__file__).resolve().parents[1] / "circuits"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.path = None
        self.scene = CircuitScene()
        self.setCentralWidget(CircuitView(self.scene))

        dock = QDockWidget("Componente (trage pe canvas)", self)
        dock.setWidget(Palette())
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

        bar = self.addToolBar("Fișier")
        for text, key, fn in [("Nou", QKeySequence.StandardKey.New, self.new),
                              ("Deschide", QKeySequence.StandardKey.Open, self.open),
                              ("Salvează", QKeySequence.StandardKey.Save, self.save),
                              ("Salvează ca...", QKeySequence.StandardKey.SaveAs, self.save_as)]:
            act = QAction(text, self)
            act.setShortcut(key)
            act.triggered.connect(fn)
            bar.addAction(act)

        self.statusBar().showMessage(
            "Trage un port (cerc portocaliu) spre alt port ca să faci un fir  |  dublu-click = editează adresa  |  Del = șterge  |  Ctrl+rotiță = zoom")
        self.resize(1100, 700)
        self._update_title()

    def _update_title(self):
        self.setWindowTitle(f"Editor LAD - {self.path.name if self.path else 'fără titlu'}")

    def new(self):
        self.scene.load_circuit(type(self.scene.to_circuit())())
        self.path = None
        self._update_title()

    def open(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Deschide", str(CIRCUITS_DIR), "Circuit (*.json)")
        if fn:
            try:
                self.scene.load_circuit(load_circuit(fn))
                self.path = Path(fn)
                self._update_title()
            except Exception as ex:
                QMessageBox.critical(self, "Eroare", str(ex))

    def save(self):
        if self.path is None:
            return self.save_as()
        save_circuit(self.scene.to_circuit(), self.path)
        self.statusBar().showMessage(f"Salvat: {self.path}", 3000)

    def save_as(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Salvează", str(CIRCUITS_DIR / "circuit.json"), "Circuit (*.json)")
        if fn:
            self.path = Path(fn)
            self._update_title()
            self.save()


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
