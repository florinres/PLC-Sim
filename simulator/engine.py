"""Motorul de simulare LAD (fără UI). Rulează "scan-uri" ca un PLC:
rungurile se evaluează de sus în jos, iar în fiecare rung componentele de la stânga la dreapta.
Comportamentul vine din spec["logic"] (vezi core/library.py), nu din numele tipului."""
import re
from collections import defaultdict

from core.library import COMPONENT_TYPES

_TIME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)", re.I)
_UNITS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}

CONTACT_LOGIC = ("no", "nc", "p", "n")
COIL_LOGIC = ("coil", "coil_n", "set", "reset")
_CMP = {"==": lambda a, b: a == b, "<>": lambda a, b: a != b, ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}


def _div(a, b):
    if b == 0:
        raise ZeroDivisionError
    return int(a / b) if isinstance(a, int) and isinstance(b, int) else a / b  # întregi: trunchiere spre zero


_MATH = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b,
         "/": _div, "move": lambda a, b: a}


def parse_time(text):
    """'T#5s', 'T#1m30s', 'T#500ms', '2s500ms' -> secunde. Un număr simplu = milisecunde."""
    t = re.sub(r"^\s*(T|TIME)#", "", str(text), flags=re.I)
    parts = _TIME_RE.findall(t)
    if parts:
        return sum(float(v) * _UNITS[u.lower()] for v, u in parts)
    try:
        return float(t) / 1000.0
    except ValueError:
        return 0.0


def _num(text):
    """Număr dacă textul e un literal numeric, altfel None."""
    try:
        f = float(str(text).strip())
    except ValueError:
        return None
    return int(f) if f.is_integer() else f


def parse_value(text, like=None):
    s = str(text).strip().lower()
    if s in ("true", "on"):
        return True
    if s in ("false", "off"):
        return False
    n = _num(s)
    if n is None:
        return like if like is not None else 0
    return bool(n) if isinstance(like, bool) else n


class Engine:
    def __init__(self, circuit):
        self.circuit = circuit
        self.comps = {c.id: c for c in circuit.components}
        self.incoming = defaultdict(list)  # (id, port) -> [(id_sursă, port_sursă), ...]
        for w in circuit.wires:
            self.incoming[tuple(w.dst)].append(tuple(w.src))
        self.order = self._compute_order()
        self._initial, self.driven = self._discover()
        self.reset()

    # ---------- pregătire ----------
    def _compute_order(self):
        parent = {c: c for c in self.comps}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        succ, indeg = defaultdict(set), {c: 0 for c in self.comps}
        for w in self.circuit.wires:
            s, d = w.src[0], w.dst[0]
            if s not in self.comps or d not in self.comps:
                continue
            parent[find(s)] = find(d)
            if d not in succ[s]:
                succ[s].add(d)
                indeg[d] += 1
        groups = defaultdict(list)
        for c in self.comps:
            groups[find(c)].append(c)

        key = lambda c: (self.comps[c].x, self.comps[c].y)
        order = []
        # rungurile (grupuri conectate) de sus în jos; în rung, ordine topologică stânga -> dreapta
        for members in sorted(groups.values(), key=lambda g: (min(self.comps[c].y for c in g),
                                                              min(self.comps[c].x for c in g))):
            ready = sorted([c for c in members if indeg[c] == 0], key=key)
            done = []
            while ready:
                c = ready.pop(0)
                done.append(c)
                for d in sorted(succ[c], key=key):
                    indeg[d] -= 1
                    if indeg[d] == 0:
                        ready.append(d)
                        ready.sort(key=key)
            seen = set(done)
            done += sorted([c for c in members if c not in seen], key=key)  # fallback pentru bucle
            order += done
        return order

    def _discover(self):
        """Găsește toate variabilele folosite și care dintre ele sunt comandate de circuit."""
        init, driven = {}, set()
        for c in self.comps.values():
            lg, tag = COMPONENT_TYPES[c.type]["logic"], c.tag.strip()
            if lg in CONTACT_LOGIC and tag:
                init.setdefault(tag, False)
            elif (lg in COIL_LOGIC or lg in ("sr", "rs")) and tag:
                init.setdefault(tag, False)
                driven.add(tag)
            elif lg in ("ton", "tof", "tp") and tag:
                init[f"{tag}.Q"], init[f"{tag}.ET"] = False, 0
                driven |= {f"{tag}.Q", f"{tag}.ET"}
            elif lg in ("ctu", "ctd") and tag:
                init[f"{tag}.Q"], init[f"{tag}.CV"] = False, 0
                driven |= {f"{tag}.Q", f"{tag}.CV"}
        for c in self.comps.values():
            if COMPONENT_TYPES[c.type]["logic"] in ("cmp", "math"):
                for k, v in c.params.items():
                    v = str(v).strip()
                    if v and _num(v) is None:
                        init.setdefault(v, 0)
                        if k == "OUT":
                            driven.add(v)
        return init, driven

    def reset(self):
        self.vars = dict(self._initial)
        self.state, self.signals, self.active = {}, {}, {}
        self.time, self.scans = 0.0, 0
        self.scan(0.0)  # stare inițială vizibilă (șinele alimentate)
        self.time, self.scans = 0.0, 0

    # ---------- acces la variabile ----------
    def variable_names(self):
        return sorted(self.vars)

    def is_driven(self, name):
        return name in self.driven

    def set_var(self, name, text):
        if name in self.vars:
            self.vars[name] = parse_value(text, self.vars[name])

    def set_bool(self, tag, value):
        """Setează o intrare booleană (nu una comandată de circuit). True dacă s-a schimbat ceva."""
        if tag in self.vars and tag not in self.driven and isinstance(self.vars[tag], bool):
            changed = self.vars[tag] != bool(value)
            self.vars[tag] = bool(value)
            return changed
        return False

    def toggle(self, tag):
        return tag in self.vars and self.set_bool(tag, not self.vars[tag])

    def _operand(self, text):
        s = str(text).strip()
        n = _num(s)
        if n is not None:
            return n
        v = self.vars.get(s, 0)
        return int(v) if isinstance(v, bool) else v

    # ---------- scan ----------
    def _power(self, cid, port, sig):
        return any(sig.get(s, self.signals.get(s, False)) for s in self.incoming.get((cid, port), ()))

    def scan(self, dt):
        self.time += dt
        self.scans += 1
        sig = {}
        for cid in self.order:
            self._eval(self.comps[cid], sig, dt)
        self.signals = sig

    def _eval(self, c, sig, dt):
        spec = COMPONENT_TYPES[c.type]
        lg, cid, tag, params = spec["logic"], c.id, c.tag.strip(), c.params
        power = lambda port="in": self._power(cid, port, sig)
        out = act = False

        if lg == "rail_l":
            out = act = True
        elif lg == "rail_r":
            act = power()
        elif lg == "junction":
            out = act = power()
        elif lg in CONTACT_LOGIC:
            bit = bool(self.vars.get(tag, False))
            prev = self.state.get(cid, False)
            ok = {"no": bit, "nc": not bit, "p": bit and not prev, "n": prev and not bit}[lg]
            self.state[cid] = bit
            out = act = power() and ok
        elif lg == "not":
            out = act = not power()
        elif lg in COIL_LOGIC:
            p = power()
            if tag:
                if lg == "coil":
                    self.vars[tag] = p
                elif lg == "coil_n":
                    self.vars[tag] = not p
                elif lg == "set" and p:
                    self.vars[tag] = True
                elif lg == "reset" and p:
                    self.vars[tag] = False
            out = act = p
        elif lg in ("sr", "rs"):
            q = bool(self.vars.get(tag, False)) if tag else self.state.get(cid, False)
            if lg == "sr":   # set dominant
                q = power("S1") or (q and not power("R"))
            else:            # reset dominant
                q = (not power("R1")) and (power("S") or q)
            if tag:
                self.vars[tag] = q
            else:
                self.state[cid] = q
            out = act = q
        elif lg in ("ton", "tof", "tp"):
            st = self.state.setdefault(cid, {"et": 0.0, "q": False, "prev": False})
            pt, p = parse_time(params.get("PT", "0")), power("IN")
            if lg == "ton":
                if p:
                    st["et"] = min(st["et"] + dt, pt)
                    st["q"] = st["et"] >= pt
                else:
                    st["et"], st["q"] = 0.0, False
            elif lg == "tof":
                if p:
                    st["q"], st["et"] = True, 0.0
                elif st["q"]:
                    st["et"] = min(st["et"] + dt, pt)
                    if st["et"] >= pt:
                        st["q"] = False
            else:  # tp: impuls de durată fixă, pornit de frontul pozitiv
                if p and not st["prev"] and not st["q"]:
                    st["q"], st["et"] = True, 0.0
                if st["q"]:
                    st["et"] = min(st["et"] + dt, pt)
                    if st["et"] >= pt:
                        st["q"] = False
                elif not p:
                    st["et"] = 0.0
                st["prev"] = p
            out = act = st["q"]
            if tag:
                self.vars[f"{tag}.Q"], self.vars[f"{tag}.ET"] = st["q"], int(st["et"] * 1000)
        elif lg == "ctu":
            st = self.state.setdefault(cid, {"cv": 0, "prev": False})
            cu = power("CU")
            if power("R"):
                st["cv"] = 0
            elif cu and not st["prev"]:
                st["cv"] = min(st["cv"] + 1, 32767)
            st["prev"] = cu
            out = act = st["cv"] >= self._operand(params.get("PV", "0"))
            if tag:
                self.vars[f"{tag}.Q"], self.vars[f"{tag}.CV"] = out, st["cv"]
        elif lg == "ctd":
            st = self.state.setdefault(cid, {"cv": 0, "prev": False})
            cd = power("CD")
            if power("LD"):
                st["cv"] = self._operand(params.get("PV", "0"))
            elif cd and not st["prev"]:
                st["cv"] = max(st["cv"] - 1, -32768)
            st["prev"] = cd
            out = act = st["cv"] <= 0
            if tag:
                self.vars[f"{tag}.Q"], self.vars[f"{tag}.CV"] = out, st["cv"]
        elif lg == "cmp":
            a, b = self._operand(params.get("A", "0")), self._operand(params.get("B", "0"))
            out = act = power("IN") and _CMP[spec["op"]](a, b)
        elif lg == "math":
            out = act = power("EN")
            if out:
                a = self._operand(params.get("IN1", params.get("IN", "0")))
                b = self._operand(params.get("IN2", "0"))
                try:
                    res = _MATH[spec["op"]](a, b)
                except ZeroDivisionError:
                    out = act = False
                else:
                    dest = str(params.get("OUT", "")).strip()
                    if dest and _num(dest) is None:
                        self.vars[dest] = round(res, 6) if isinstance(res, float) else res
        elif lg in ("and", "or", "xor"):
            p1, p2 = power("IN1"), power("IN2")
            out = act = {"and": p1 and p2, "or": p1 or p2, "xor": p1 != p2}[lg]

        for name, _ in spec["outputs"]:
            sig[(cid, name)] = bool(out)
        self.active[cid] = bool(act)

    # ---------- text de stare pentru UI ----------
    def status_text(self, cid):
        c = self.comps[cid]
        lg, tag = COMPONENT_TYPES[c.type]["logic"], c.tag.strip()
        if lg in CONTACT_LOGIC + COIL_LOGIC + ("sr", "rs"):
            return "1" if self.vars.get(tag) else "0"
        st = self.state.get(cid)
        if lg in ("ton", "tof", "tp") and st:
            return f"ET {int(st['et'] * 1000)} ms"
        if lg in ("ctu", "ctd") and st:
            return f"CV {st['cv']}"
        if lg == "math":
            dest = str(c.params.get("OUT", "")).strip()
            return f"= {self.vars[dest]}" if dest in self.vars else ""
        return ""
