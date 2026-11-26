"""Aplicația 2: simulatorul de circuite LAD.
Rulare:  python -m simulator.main [circuits/exemplu.json]"""
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QDockWidget, QFileDialog, QLabel, QMainWindow,
                               QMessageBox, QSpinBox, QTableWidget, QTableWidgetItem)

from core.io import load_circuit
from simulator.engine import Engine
from simulator.view import SimScene, SimView

CIRCUITS_DIR = Path(__file__).resolve().parents[1] / "circuits"


class SimWindow(QMainWindow):
    def __init__(self, path=None):
        super().__init__()
        self.engine, self.path = None, None
        self._refreshing, self._last = False, time.monotonic()

        self.scene = SimScene()
        self.scene.tag_clicked.connect(self.on_tag_clicked)
        self.scene.tag_pressed.connect(self.on_tag_pressed)
        self.scene.tag_released.connect(self.on_tag_released)
        self._latched, self._press_scan = set(), {}
        self.setCentralWidget(SimView(self.scene))

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Variabilă", "Valoare"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self.on_cell_edited)
        dock = QDockWidget("Variabile (dublu-click pe valoare = editează)", self)
        dock.setWidget(self.table)
        dock.setMinimumWidth(260)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_tick)

        bar = self.addToolBar("Simulare")
        self._action(bar, "Deschide", self.open, QKeySequence.StandardKey.Open)
        self._action(bar, "Reîncarcă", self.reload, QKeySequence("F5"))
        bar.addSeparator()
        self.run_action = self._action(bar, "Pauză", None, QKeySequence("Space"), checkable=True)
        self.run_action.toggled.connect(self.set_running)
        self._action(bar, "Pas", self.step, QKeySequence("F10"))
        self._action(bar, "Reset", self.reset, QKeySequence("F6"))
        bar.addSeparator()
        bar.addWidget(QLabel(" Interval scan (ms): "))
        self.scan_ms = QSpinBox(); self.scan_ms.setRange(10, 1000); self.scan_ms.setValue(50)
        self.scan_ms.valueChanged.connect(lambda v: self.timer.isActive() and self.timer.setInterval(v))
        bar.addWidget(self.scan_ms)
        bar.addWidget(QLabel("  Pas manual (ms): "))
        self.step_ms = QSpinBox(); self.step_ms.setRange(1, 60000); self.step_ms.setValue(100)
        bar.addWidget(self.step_ms)

        self.statusBar().showMessage("Deschide un circuit salvat din editor. Click pe un contact = comută intrarea.")
        self.resize(1250, 700)
        if path:
            self.load(path)

    def _action(self, bar, text, fn, key, checkable=False):
        act = QAction(text, self)
        act.setShortcut(key)
        act.setCheckable(checkable)
        if fn:
            act.triggered.connect(fn)
        bar.addAction(act)
        return act

    # ---------- încărcare ----------
    def open(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Deschide circuit", str(CIRCUITS_DIR), "Circuit (*.json)")
        if fn:
            self.load(fn)

    def reload(self):
        if self.path:
            self.load(self.path)

    def load(self, path):
        try:
            circuit = load_circuit(path)
            engine = Engine(circuit)
            self.scene.load(circuit)
        except Exception as ex:
            QMessageBox.critical(self, "Eroare la încărcare", str(ex))
            return
        self.engine, self.path = engine, Path(path)
        self.setWindowTitle(f"Simulator LAD - {self.path.name}")
        self.build_table()
        self.update_ui()
        self.run_action.setChecked(False)
        self.run_action.setChecked(True)

    # ---------- rulare ----------
    def set_running(self, on):
        self.run_action.setText("Pauză" if on else "Rulează")
        if on and self.engine:
            self._last = time.monotonic()
            self.timer.start(self.scan_ms.value())
        else:
            self.timer.stop()

    def on_tick(self):
        now = time.monotonic()
        dt, self._last = min(now - self._last, 0.5), now
        self.do_scan(dt)

    def do_scan(self, dt):
        if self.engine:
            self.engine.scan(dt)
            self.update_ui()

    def step(self):
        self.run_action.setChecked(False)
        self.do_scan(self.step_ms.value() / 1000.0)

    def reset(self):
        if self.engine:
            self.engine.reset()
            self.update_ui()

    # ---------- interacțiune ----------
    def on_tag_clicked(self, tag):
        if self.engine and self.engine.toggle(tag):
            self.update_ui()  # efectul circuitului apare la următorul scan

    def set_input(self, tag, value):
        if self.engine and self.engine.set_bool(tag, value):
            self.update_ui()

    def on_tag_pressed(self, tag):
        if not self.engine:
            return
        if self.run_action.isChecked():
            self._press_scan[tag] = self.engine.scans
            self.set_input(tag, True)
        else:  # în pauză butonul rămâne apăsat (comutare), ca să poți face Pas cu el activ
            self._latched.add(tag)
            self.engine.toggle(tag)
            self.update_ui()

    def on_tag_released(self, tag):
        if tag in self._latched:
            self._latched.discard(tag)
        elif self.engine and self.engine.scans == self._press_scan.get(tag):
            # eliberat înainte de vreun scan: amână eliberarea ca apăsarea să fie văzută
            QTimer.singleShot(self.scan_ms.value() + 20, lambda: self.set_input(tag, False))
        else:
            self.set_input(tag, False)

    def on_cell_edited(self, item):
        if self._refreshing or item.column() != 1 or not self.engine:
            return
        self.engine.set_var(self.table.item(item.row(), 0).text(), item.text())
        self.update_ui()

    # ---------- UI ----------
    def build_table(self):
        names = self.engine.variable_names()
        self._refreshing = True
        self.table.setRowCount(len(names))
        for r, name in enumerate(names):
            n = QTableWidgetItem(name)
            n.setFlags(Qt.ItemFlag.ItemIsEnabled)
            v = QTableWidgetItem("")
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            if not self.engine.is_driven(name):
                flags |= Qt.ItemFlag.ItemIsEditable
            v.setFlags(flags)
            self.table.setItem(r, 0, n)
            self.table.setItem(r, 1, v)
        self._refreshing = False

    @staticmethod
    def _fmt(v):
        return ("1" if v else "0") if isinstance(v, bool) else str(v)

    def update_ui(self):
        self.scene.refresh(self.engine)
        self._refreshing = True
        for r, name in enumerate(self.engine.variable_names()):
            text = self._fmt(self.engine.vars[name])
            cell = self.table.item(r, 1)
            if cell is not None and cell.text() != text:
                cell.setText(text)
        self._refreshing = False
        self.statusBar().showMessage(f"Scan #{self.engine.scans}    t = {self.engine.time:.2f} s")


def main():
    app = QApplication(sys.argv)
    w = SimWindow(sys.argv[1] if len(sys.argv) > 1 else None)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()