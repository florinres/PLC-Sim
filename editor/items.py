from PySide6.QtCore import QPointF, QRectF, QLineF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainterPath, QPainterPathStroker, QPen
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem

from core.library import COMPONENT_TYPES, GRID

DARK = QColor("#222222")
SEL = QColor("#1d4ed8")
AL = Qt.AlignmentFlag


class PortItem(QGraphicsEllipseItem):
    R = 5

    def __init__(self, parent, name, kind):
        super().__init__(-self.R, -self.R, 2 * self.R, 2 * self.R, parent)
        self.name = name
        self.kind = kind  # "in" sau "out"
        self.wires = []
        self.setBrush(QBrush(QColor("#f5a623")))
        self.setPen(QPen(DARK, 1))
        self.setZValue(2)

    @property
    def component(self):
        return self.parentItem()


class ComponentItem(QGraphicsItem):
    def __init__(self, comp_id, ctype, tag="", params=None):
        super().__init__()
        self.spec = COMPONENT_TYPES[ctype]
        self.comp_id, self.ctype, self.tag = comp_id, ctype, tag
        self.params = {**self.spec["params"], **(params or {})}
        self.w, self.h = self.spec["w"], self.spec["h"]
        self.has_tag = self.spec["has_tag"]
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.ports = {}
        for name, y in self.spec["inputs"]:
            p = PortItem(self, name, "in")
            p.setPos(0, y)
            self.ports[name] = p
        for name, y in self.spec["outputs"]:
            p = PortItem(self, name, "out")
            p.setPos(self.w, y)
            self.ports[name] = p

    @property
    def editable(self):
        return self.has_tag or bool(self.params)

    def label_text(self):
        try:
            return self.spec["fmt"].format(tag=self.tag, **self.params)
        except (KeyError, IndexError):
            return self.tag

    def draw_color(self):  # suprascris în simulator
        return SEL if self.isSelected() else DARK

    def status_text(self):  # suprascris în simulator (text sub componentă)
        return ""

    def boundingRect(self):
        return QRectF(-40, -26, self.w + 80, self.h + 52)

    def paint(self, p, option, widget=None):
        col = self.draw_color()
        pen = QPen(col, 2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        w, h = self.w, self.h
        cx, cy = w / 2, h / 2
        kind, mark = self.spec["kind"], self.spec["mark"]

        def line(x1, y1, x2, y2):
            p.drawLine(QLineF(x1, y1, x2, y2))

        def text(rect, s, size=9, flags=AL.AlignCenter):
            p.setPen(col)
            p.setFont(QFont("Sans", size, QFont.Weight.Bold))
            p.drawText(rect, flags, s)
            p.setPen(pen)

        if kind == "rail":
            left = bool(self.spec["outputs"])
            x = 3 if left else w - 3
            p.setPen(QPen(col, 5)); line(x, 0, x, h)
            p.setPen(pen)
            line(x, cy, w, cy) if left else line(0, cy, x, cy)
        elif kind == "junction":
            line(0, cy, w, cy)
            p.setBrush(QBrush(col)); p.drawEllipse(QPointF(cx, cy), 4, 4); p.setBrush(Qt.BrushStyle.NoBrush)
        elif kind == "contact":
            line(0, cy, cx - 8, cy); line(cx + 8, cy, w, cy)
            line(cx - 8, cy - 14, cx - 8, cy + 14)
            line(cx + 8, cy - 14, cx + 8, cy + 14)
            if mark == "/":
                line(cx - 6, cy + 12, cx + 6, cy - 12)
            elif mark:
                text(QRectF(cx - 8, cy - 14, 16, 28), mark, 8)
        elif kind == "coil":
            line(0, cy, cx - 12, cy); line(cx + 12, cy, w, cy)
            p.drawArc(QRectF(cx - 16, cy - 14, 12, 28), 90 * 16, 180 * 16)
            p.drawArc(QRectF(cx + 4, cy - 14, 12, 28), 270 * 16, 180 * 16)
            if mark == "/":
                line(cx - 6, cy + 12, cx + 6, cy - 12)
            elif mark:
                text(QRectF(cx - 12, cy - 14, 24, 28), mark, 8)
        elif kind == "box":
            p.drawRect(QRectF(0, 0, w, h))
            for name, y in self.spec["inputs"]:
                text(QRectF(7, y - 8, 40, 16), name, 8, AL.AlignLeft | AL.AlignVCenter)
            for name, y in self.spec["outputs"]:
                text(QRectF(w - 47, y - 8, 40, 16), name, 8, AL.AlignRight | AL.AlignVCenter)
            text(QRectF(30, 0, w - 60, h), self.spec["title"], 11)

        label = self.label_text()
        if label:
            text(QRectF(-40, -24, w + 80, 20), label, 9, AL.AlignCenter | AL.AlignBottom)
        status = self.status_text()
        if status:
            text(QRectF(-40, h + 2, w + 80, 16), status, 8, AL.AlignCenter | AL.AlignTop)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            return QPointF(round(value.x() / GRID) * GRID, round(value.y() / GRID) * GRID)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for port in self.ports.values():
                for wire in port.wires:
                    wire.update_path()
        return super().itemChange(change, value)


class WireItem(QGraphicsPathItem):
    def __init__(self, src_port):
        super().__init__()
        self.src, self.dst = src_port, None
        self._pen = QPen(DARK, 2)
        self._pen_sel = QPen(SEL, 3)
        self.setPen(self._pen)
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)

    def connect_to(self, dst_port):
        self.dst = dst_port
        self.src.wires.append(self)
        self.dst.wires.append(self)
        self.update_path()

    def detach(self):
        for port in (self.src, self.dst):
            if port is not None and self in port.wires:
                port.wires.remove(self)

    def update_path(self, end_pos=None):
        p1 = self.src.scenePos()
        p2 = self.dst.scenePos() if self.dst else end_pos
        if p2 is None:
            return
        mid = (p1.x() + p2.x()) / 2
        path = QPainterPath(p1)
        path.lineTo(mid, p1.y())
        path.lineTo(mid, p2.y())
        path.lineTo(p2)
        self.setPath(path)

    def shape(self):  # zonă de click mai lată
        stroker = QPainterPathStroker()
        stroker.setWidth(10)
        return stroker.createStroke(self.path())

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.setPen(self._pen_sel if value else self._pen)
        return super().itemChange(change, value)