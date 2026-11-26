from PySide6.QtCore import QMimeData, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QGraphicsScene, QLineEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from core.library import COMPONENT_TYPES
from editor.items import ComponentItem

ROLE = Qt.ItemDataRole.UserRole
ICON = QSize(96, 44)


def make_icon(ctype):
    """Previzualizare desenată chiar cu codul de desen al componentei."""
    scene = QGraphicsScene()
    item = ComponentItem("preview", ctype, "")
    scene.addItem(item)
    pix = QPixmap(ICON)
    pix.fill(Qt.GlobalColor.white)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(p, QRectF(2, 2, ICON.width() - 4, ICON.height() - 4),
                 QRectF(-6, -2, item.w + 12, item.h + 4), Qt.AspectRatioMode.KeepAspectRatio)
    p.end()
    return QIcon(pix)


class _Tree(QTreeWidget):
    def startDrag(self, actions):
        item = self.currentItem()
        ctype = item.data(0, ROLE) if item else None
        if not ctype:
            return
        mime = QMimeData()
        mime.setText(ctype)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(item.icon(0).pixmap(ICON))
        drag.exec(Qt.DropAction.CopyAction)


class Palette(QWidget):
    """Paletă pe categorii, cu căutare. Tragere pe canvas sau dublu-click = adaugă în centru."""
    add_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Caută (ex. timer, buton, motor)...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.tree = _Tree()
        self.tree.setHeaderHidden(True)
        self.tree.setDragEnabled(True)
        self.tree.setIconSize(ICON)
        self.tree.setIndentation(10)
        self.tree.itemDoubleClicked.connect(self._double_clicked)
        layout.addWidget(self.tree)

        groups = {}
        for ctype, spec in COMPONENT_TYPES.items():
            g = groups.get(spec["group"])
            if g is None:
                g = QTreeWidgetItem(self.tree, [spec["group"]])
                g.setFlags(Qt.ItemFlag.ItemIsEnabled)
                f = g.font(0); f.setBold(True); g.setFont(0, f)
                groups[spec["group"]] = g
            child = QTreeWidgetItem(g, [spec["label"]])
            child.setIcon(0, make_icon(ctype))
            child.setData(0, ROLE, ctype)
            child.setToolTip(0, f"{spec['label']}  [{ctype}]")
        self.tree.expandAll()

    def _double_clicked(self, item, column):
        ctype = item.data(0, ROLE)
        if ctype:
            self.add_requested.emit(ctype)

    def _filter(self, text):
        t = text.strip().lower()
        for gi in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(gi)
            any_visible = False
            for ci in range(group.childCount()):
                child = group.child(ci)
                hay = f"{child.text(0)} {child.data(0, ROLE)} {group.text(0)}".lower()
                visible = not t or t in hay
                child.setHidden(not visible)
                any_visible = any_visible or visible
            group.setHidden(not any_visible)
            if t and any_visible:
                group.setExpanded(True)