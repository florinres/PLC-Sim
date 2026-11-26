from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsItem

from core.library import GRID
from editor.items import ComponentItem, WireItem, DARK

ACTIVE = QColor("#16a34a")   # verde = trece curent
IDLE_WIRE = QColor("#6b7280")


class SimComponentItem(ComponentItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.active, self.status = False, ""

    def draw_color(self):
        return ACTIVE if self.active else DARK

    def status_text(self):
        return self.status

    def is_lit(self):
        return self.active

    def set_state(self, active, status):
        if (active, status) != (self.active, self.status):
            self.active, self.status = active, status
            self.update()


class SimWire(WireItem):
    def __init__(self, src_port):
        super().__init__(src_port)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self._on = None
        self.set_energized(False)

    def set_energized(self, on):
        if on != self._on:
            self._on = on
            self.setPen(QPen(ACTIVE, 3.5) if on else QPen(IDLE_WIRE, 2))


class SimScene(QGraphicsScene):
    tag_clicked = Signal(str)   # click pe un contact (cu reținere) -> comută variabila lui
    tag_pressed = Signal(str)   # buton momentan: apăsat
    tag_released = Signal(str)  # buton momentan: eliberat

    def __init__(self):
        super().__init__()
        self.items_by_id, self.sim_wires = {}, []
        self._held = None

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor("#fafafa"))
        painter.setPen(QPen(QColor("#c8c8c8"), 1.5))
        x0 = int(rect.left()) - int(rect.left()) % GRID
        y0 = int(rect.top()) - int(rect.top()) % GRID
        for x in range(x0, int(rect.right()) + 1, GRID):
            for y in range(y0, int(rect.bottom()) + 1, GRID):
                painter.drawPoint(x, y)

    def load(self, circuit):
        self.clear()
        self.items_by_id, self.sim_wires = {}, []
        for c in circuit.components:
            item = SimComponentItem(c.id, c.type, c.tag, c.params)
            self.addItem(item)
            item.setPos(c.x, c.y)
            self.items_by_id[c.id] = item
        for w in circuit.wires:
            a = self.items_by_id[w.src[0]].ports[w.src[1]]
            b = self.items_by_id[w.dst[0]].ports[w.dst[1]]
            wire = SimWire(a)
            self.addItem(wire)
            wire.connect_to(b)
            self.sim_wires.append((wire, tuple(w.src)))
        self.setSceneRect(self.itemsBoundingRect().adjusted(-80, -80, 80, 80))

    def refresh(self, engine):
        for wire, key in self.sim_wires:
            wire.set_energized(engine.signals.get(key, False))
        for cid, item in self.items_by_id.items():
            item.set_state(engine.active.get(cid, False), engine.status_text(cid))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(e.scenePos(), QTransform())
            while item is not None and not isinstance(item, ComponentItem):
                item = item.parentItem()
            if item is not None and item.spec["kind"] == "contact" and item.tag.strip():
                tag = item.tag.strip()
                if item.spec["momentary"]:
                    self._held = tag
                    self.tag_pressed.emit(tag)
                else:
                    self.tag_clicked.emit(tag)
                e.accept()
                return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if self._held is not None:
            tag, self._held = self._held, None
            self.tag_released.emit(tag)
            e.accept()
            return
        super().mouseReleaseEvent(e)


class SimView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def wheelEvent(self, e):  # Ctrl + rotiță = zoom
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            f = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
            self.scale(f, f)
        else:
            super().wheelEvent(e)