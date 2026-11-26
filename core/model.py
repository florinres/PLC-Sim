"""Modelul circuitului: pur Python, fără UI. Același fișier JSON e folosit de editor și simulator."""
from dataclasses import dataclass, field
from core.library import COMPONENT_TYPES


@dataclass
class Component:
    id: str
    type: str
    x: float
    y: float
    tag: str = ""                              # adresa/numele, ex. I0.0, Q0.0, T1
    params: dict = field(default_factory=dict)  # ex. {"PT": "T#5s"}


@dataclass
class Wire:
    src: tuple  # (component_id, port)  - ieșire
    dst: tuple  # (component_id, port)  - intrare


@dataclass
class Circuit:
    components: list = field(default_factory=list)
    wires: list = field(default_factory=list)

    def to_dict(self):
        return {
            "components": [dict(id=c.id, type=c.type, x=c.x, y=c.y, tag=c.tag, params=c.params)
                           for c in self.components],
            "wires": [{"from": list(w.src), "to": list(w.dst)} for w in self.wires],
        }

    @classmethod
    def from_dict(cls, d):
        comps = []
        for c in d.get("components", []):
            if c["type"] not in COMPONENT_TYPES:
                raise ValueError(f"Tip de componentă necunoscut: {c['type']}")
            comps.append(Component(c["id"], c["type"], c["x"], c["y"], c.get("tag", ""), c.get("params", {})))
        wires = [Wire(tuple(w["from"]), tuple(w["to"])) for w in d.get("wires", [])]
        return cls(comps, wires)