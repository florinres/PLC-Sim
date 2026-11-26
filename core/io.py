import json
from core.model import Circuit


def save_circuit(circuit: Circuit, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(circuit.to_dict(), f, indent=2, ensure_ascii=False)


def load_circuit(path) -> Circuit:
    with open(path, encoding="utf-8") as f:
        return Circuit.from_dict(json.load(f))
