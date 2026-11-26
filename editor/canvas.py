import json

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QTransform
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QFormLayout, QGraphicsScene,
                               QGraphicsView, QLineEdit)

from core.library import COMPONENT_TYPES, GRID
from core.model import Circuit, Component, Wire
from editor.items import ComponentItem, PortItem, WireItem


def snap(v):
    return round(v / GRID) * GRID


class PropsDialog(QDialog):
    """Dialog generic: editează adresa (tag) și parametrii unei componente."""

    def __init__(self, parent, item):
        super().__init__(parent)
        self.setWindowTitle(f"Proprietăți - {item.spec['label'].strip()}")
        form = QFormLayout(self)
        self.tag_edit = None
        self.param_edits = {}
        if item.has_tag:
            self.tag_edit = QLineEdit(item.tag)
            form.addRow("Adresă / nume", self.tag_edit)
        for key, val in item.params.items():
            self.param_edits[key] = QLineEdit(str(val))
            form.addRow(key, self.param_edits[key])
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def apply(self, item):
        if self.tag_edit is not None:
            item.tag = self.tag_edit.text().strip()
        for key, edit in self.param_edits.items():
            item.params[key] = edit.text().strip()
        item.update()


class CircuitScene(QGraphicsScene):
    def __init__(self):
        super().__init__(0, 0, 2400, 1400)
        self._counter = 0
        self._temp_wire = None
        self._undo, self._redo = [], []
        self._press_state = None   # stare înainte de un click (pentru a detecta mutări)
        self._wire_state = None    # stare înainte de a începe un fir
        self._last_paste = None

    # ---------- fundal cu grilă ----------
    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor("#fafafa"))
        painter.setPen(QPen(QColor("#c8c8c8"), 1.5))
        x0 = int(rect.left()) - int(rect.left()) % GRID
        y0 = int(rect.top()) - int(rect.top()) % GRID
        for x in range(x0, int(rect.right()) + 1, GRID):
            for y in range(y0, int(rect.bottom()) + 1, GRID):
                painter.drawPoint(x, y)

    # ---------- componente ----------
    def components(self):
        return [i for i in self.items() if isinstance(i, ComponentItem)]

    def wires(self):
        return [i for i in self.items() if isinstance(i, WireItem) and i.dst is not None]

    def _new_id(self, ctype):
        existing = {c.comp_id for c in self.components()}
        while True:
            self._counter += 1
            cid = f"{ctype.lower()}{self._counter}"
            if cid not in existing:
                return cid

    def add_component(self, ctype, pos, comp_id=None, tag=None, params=None, center=False):
        spec = COMPONENT_TYPES[ctype]
        if tag is None:
            tag = spec.get("default_tag", "")
        item = ComponentItem(comp_id or self._new_id(ctype), ctype, tag, params)
        if center:
            pos = QPointF(pos.x() - spec["w"] / 2, pos.y() - spec["h"] / 2)
        self.addItem(item)
        item.setPos(pos)  # itemChange face snap pe grilă
        return item

    def place(self, ctype, pos, center=True):
        """Adaugă o componentă nouă (cu undo) și o selectează."""
        self.push_undo()
        self.clearSelection()
        item = self.add_component(ctype, pos, center=center)
        item.setSelected(True)
        return item

    def connect_ports(self, a, b):
        """Conectează două porturi (ieșire -> intrare). Întoarce firul sau None."""
        if a.kind == "in" and b.kind == "out":
            a, b = b, a
        if a.kind != "out" or b.kind != "in" or a.component is b.component:
            return None
        if any(w.src is a and w.dst is b for w in a.wires):  # fără duplicate
            return None
        wire = WireItem(a)
        self.addItem(wire)
        wire.connect_to(b)
        return wire

    # ---------- undo / redo (instantanee ale întregului circuit) ----------
    def _state(self):
        d = self.to_circuit().to_dict()
        d["components"].sort(key=lambda c: c["id"])
        d["wires"].sort(key=lambda w: (w["from"], w["to"]))
        return json.dumps(d, sort_keys=True)

    def push_undo(self, state=None):
        self._undo.append(state if state is not None else self._state())
        del self._undo[:-100]
        self._redo.clear()

    def reset_history(self):
        self._undo.clear()
        self._redo.clear()
        self._last_paste = None

    def _restore(self, state):
        self.load_circuit(Circuit.from_dict(json.loads(state)))

    def undo(self):
        if self._undo:
            self._redo.append(self._state())
            self._restore(self._undo.pop())

    def redo(self):
        if self._redo:
            self._undo.append(self._state())
            self._restore(self._redo.pop())

    # ---------- clipboard: taie / copiază / lipește / duplică ----------
    def _selection_data(self):
        comps = [i for i in self.selectedItems() if isinstance(i, ComponentItem)]
        if not comps:
            return None
        ids = {c.comp_id for c in comps}
        return {
            "lad": 1,
            "components": [dict(id=c.comp_id, type=c.ctype, x=c.pos().x(), y=c.pos().y(),
                                tag=c.tag, params=dict(c.params)) for c in comps],
            "wires": [{"from": [w.src.component.comp_id, w.src.name], "to": [w.dst.component.comp_id, w.dst.name]}
                      for w in self.wires()
                      if w.src.component.comp_id in ids and w.dst.component.comp_id in ids],
        }

    def copy_selection(self):
        data = self._selection_data()
        if data:
            QApplication.clipboard().setText(json.dumps(data))  # funcționează și între ferestre
        return bool(data)

    def cut_selection(self):
        if self.copy_selection():
            self.delete_selected()

    def _insert(self, data, dx, dy):
        self.push_undo()
        self.clearSelection()
        mapping = {}
        for c in data["components"]:
            if c.get("type") not in COMPONENT_TYPES:
                continue
            item = self.add_component(c["type"], QPointF(c["x"] + dx, c["y"] + dy),
                                      tag=c.get("tag", ""), params=c.get("params", {}))
            item.setSelected(True)
            mapping[c["id"]] = item
        for w in data.get("wires", []):
            a, b = mapping.get(w["from"][0]), mapping.get(w["to"][0])
            if a and b and w["from"][1] in a.ports and w["to"][1] in b.ports:
                self.connect_ports(a.ports[w["from"][1]], b.ports[w["to"][1]])

    def paste(self, at=None):
        """Lipește din clipboard. 'at' = poziția scenei (cursorul); None = decalat cu 40 px."""
        try:
            data = json.loads(QApplication.clipboard().text())
            comps = data["components"] if isinstance(data, dict) and data.get("lad") == 1 else []
        except (ValueError, KeyError, TypeError):
            return False
        if not comps:
            return False
        minx, miny = min(c["x"] for c in comps), min(c["y"] for c in comps)
        ox, oy = (snap(at.x()), snap(at.y())) if at is not None else (minx + 40, miny + 40)
        if self._last_paste == (ox, oy):  # lipiri repetate: nu se suprapun exact
            ox, oy = ox + 40, oy + 40
        self._last_paste = (ox, oy)
        self._insert(data, ox - minx, oy - miny)
        return True

    def duplicate_selection(self):
        data = self._selection_data()
        if data:
            self._insert(data, 40, 40)

    def select_all(self):
        for i in self.items():
            if isinstance(i, (ComponentItem, WireItem)):
                i.setSelected(True)

    # ---------- mouse: tragere fir de la un port ----------
    def _port_at(self, pos):
        for it in self.items(QRectF(pos.x() - 8, pos.y() - 8, 16, 16)):
            if isinstance(it, PortItem):
                return it
        return None

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            port = self._port_at(e.scenePos())
            if port:
                self._wire_state = self._state()
                self._temp_wire = WireItem(port)
                self.addItem(self._temp_wire)
                self._temp_wire.update_path(e.scenePos())
                e.accept()
                return
            self._press_state = self._state()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._temp_wire:
            self._temp_wire.update_path(e.scenePos())
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._temp_wire:
            start = self._temp_wire.src
            self.removeItem(self._temp_wire)
            self._temp_wire = None
            target = self._port_at(e.scenePos())
            if target and target is not start and self.connect_ports(start, target):
                self.push_undo(self._wire_state)
            e.accept()
            return
        before, self._press_state = self._press_state, None
        super().mouseReleaseEvent(e)
        if before is not None and self._state() != before:  # componente mutate
            self.push_undo(before)

    def mouseDoubleClickEvent(self, e):
        item = self.itemAt(e.scenePos(), QTransform())
        while item is not None and not isinstance(item, ComponentItem):
            item = item.parentItem()
        if item and item.editable:
            before = self._state()
            dlg = PropsDialog(self.views()[0], item)
            if dlg.exec():
                dlg.apply(item)
                self.push_undo(before)
            e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
            e.accept()
            return
        super().keyPressEvent(e)

    def delete_selected(self):
        sel = self.selectedItems()
        if not sel:
            return
        self.push_undo()
        comps = [i for i in sel if isinstance(i, ComponentItem)]
        wires = {i for i in sel if isinstance(i, WireItem)}
        for c in comps:
            for port in c.ports.values():
                wires.update(port.wires)
        for w in wires:
            w.detach()
            self.removeItem(w)
        for c in comps:
            self.removeItem(c)

    # ---------- conversie scenă <-> model ----------
    def to_circuit(self):
        comps = [Component(c.comp_id, c.ctype, c.pos().x(), c.pos().y(), c.tag, dict(c.params))
                 for c in self.components()]
        wires = [Wire((w.src.component.comp_id, w.src.name), (w.dst.component.comp_id, w.dst.name))
                 for w in self.wires()]
        return Circuit(comps, wires)

    def load_circuit(self, circuit):
        self.clear()
        self._counter = 0
        by_id = {}
        for c in circuit.components:
            by_id[c.id] = self.add_component(c.type, QPointF(c.x, c.y), comp_id=c.id,
                                             tag=c.tag, params=c.params)
        for w in circuit.wires:
            a = by_id[w.src[0]].ports[w.src[1]]
            b = by_id[w.dst[0]].ports[w.dst[1]]
            self.connect_ports(a, b)


class CircuitView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

    def dragEnterEvent(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        ctype = e.mimeData().text()
        if ctype in COMPONENT_TYPES:
            self.scene().place(ctype, self.mapToScene(e.position().toPoint()))
            e.acceptProposedAction()

    def center_scene_pos(self):
        return self.mapToScene(self.viewport().rect().center())

    def cursor_scene_pos(self):
        """Poziția cursorului în scenă, sau None dacă nu e deasupra canvas-ului."""
        from PySide6.QtGui import QCursor
        if not self.viewport().underMouse():
            return None
        return self.mapToScene(self.viewport().mapFromGlobal(QCursor.pos()))

    def zoom(self, factor):
        self.scale(factor, factor)

    def fit_all(self):
        rect = self.scene().itemsBoundingRect()
        if not rect.isNull():
            self.fitInView(rect.adjusted(-40, -40, 40, 40), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, e):  # Ctrl + rotiță = zoom
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom(1.15 if e.angleDelta().y() > 0 else 1 / 1.15)
        else:
            super().wheelEvent(e)