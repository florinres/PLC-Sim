"""Definițiile componentelor LAD. Editorul și simulatorul citesc de aici.
Porturile sunt (nume, y_în_px); intrările stau pe marginea stângă, ieșirile pe cea dreaptă.
'logic' spune simulatorului ce face componenta; 'kind' spune editorului cum se desenează."""

GRID = 20  # pasul grilei (px); toate dimensiunile sunt multipli de GRID

_DEFAULTS = dict(kind="contact", logic=None, mark="", actuator="", momentary=False, op="", title="",
                 params={}, has_tag=True, default_tag="", fmt="{tag}", w=80, h=40,
                 inputs=[("in", 20)], outputs=[("out", 20)])


def _spec(**kw):
    return {**_DEFAULTS, **kw}


def _cmp(op, name):
    return _spec(label=f"Comparator  A {op} B ({name})", group="Comparatoare", kind="box", logic="cmp", op=op,
                 w=100, h=40, title=op, has_tag=False, params={"A": "MW0", "B": "0"},
                 inputs=[("IN", 20)], outputs=[("OUT", 20)], fmt="{A} " + op + " {B}")


def _math(title, op, sym, name):
    return _spec(label=f"{title}  OUT := IN1 {sym} IN2 ({name})", group="Matematică", kind="box", logic="math",
                 op=op, w=120, h=40, title=title, has_tag=False,
                 params={"IN1": "MW0", "IN2": "1", "OUT": "MW1"},
                 inputs=[("EN", 20)], outputs=[("ENO", 20)], fmt="{OUT} := {IN1} " + sym + " {IN2}")


def _gate(title, logic, name):
    return _spec(label=f"Poartă {title} ({name})", group="Logică", kind="box", logic=logic, w=100, h=60,
                 title=title, has_tag=False, inputs=[("IN1", 20), ("IN2", 40)], outputs=[("OUT", 20)], fmt="")


COMPONENT_TYPES = {
    # ---- structură ----
    "RAIL_L":   _spec(label="Șină stânga (L+)", group="Structură", kind="rail", logic="rail_l", w=20, h=120,
                      inputs=[], outputs=[("out", 60)], has_tag=False, fmt=""),
    "RAIL_R":   _spec(label="Șină dreapta (L-)", group="Structură", kind="rail", logic="rail_r", w=20, h=120,
                      inputs=[("in", 60)], outputs=[], has_tag=False, fmt=""),
    "JUNCTION": _spec(label="Nod (ramificare / SAU)", group="Structură", kind="junction", logic="junction",
                      w=20, h=40, has_tag=False, fmt=""),
    "COMMENT":  _spec(label="Comentariu (text liber)", group="Structură", kind="note", w=160, h=60,
                      inputs=[], outputs=[], has_tag=False, fmt="", params={"TEXT": "Comentariu"}),
    # ---- contacte ----
    "NO":     _spec(label="Contact NO  -| |-",    group="Contacte", logic="no", default_tag="I0.0"),
    "NC":     _spec(label="Contact NC  -|/|-",    group="Contacte", logic="nc", mark="/", default_tag="I0.1"),
    "P_TRIG": _spec(label="Front pozitiv -|P|-",  group="Contacte", logic="p", mark="P", default_tag="I0.2"),
    "N_TRIG": _spec(label="Front negativ -|N|-",  group="Contacte", logic="n", mark="N", default_tag="I0.3"),
    "NOT":    _spec(label="Inversare flux -|!|-", group="Contacte", logic="not", mark="!", has_tag=False, fmt=""),
    # ---- butoane / senzori ----
    "BTN_NO":   _spec(label="Buton NO (apăsat = închide)", group="Butoane / senzori", logic="no",
                      actuator="button", momentary=True, default_tag="I1.0"),
    "BTN_NC":   _spec(label="Buton NC (apăsat = deschide)", group="Butoane / senzori", logic="nc", mark="/",
                      actuator="button", momentary=True, default_tag="I1.1"),
    "ESTOP":    _spec(label="Oprire de urgență (NC)", group="Butoane / senzori", logic="nc", mark="/",
                      actuator="estop", default_tag="I1.2"),
    "LIMIT_NO": _spec(label="Limitator NO", group="Butoane / senzori", logic="no", actuator="limit",
                      default_tag="I1.3"),
    "LIMIT_NC": _spec(label="Limitator NC", group="Butoane / senzori", logic="nc", mark="/", actuator="limit",
                      default_tag="I1.4"),
    "SENSOR":   _spec(label="Senzor de proximitate (NO)", group="Butoane / senzori", logic="no",
                      actuator="sensor", default_tag="I1.5"),
    # ---- bobine ----
    "COIL":   _spec(label="Bobină      -( )-", group="Bobine", kind="coil", logic="coil", default_tag="Q0.0"),
    "COIL_N": _spec(label="Bobină neg. -(/)-", group="Bobine", kind="coil", logic="coil_n", mark="/", default_tag="Q0.1"),
    "SET":    _spec(label="Set          -(S)-", group="Bobine", kind="coil", logic="set", mark="S", default_tag="Q0.2"),
    "RESET":  _spec(label="Reset        -(R)-", group="Bobine", kind="coil", logic="reset", mark="R", default_tag="Q0.3"),
    # ---- sarcini / ieșiri ----
    "LAMP":   _spec(label="Bec / lampă", group="Sarcini (ieșiri)", kind="load", logic="coil", mark="X", default_tag="Q1.0"),
    "MOTOR":  _spec(label="Motor", group="Sarcini (ieșiri)", kind="load", logic="coil", mark="M", default_tag="Q1.1"),
    "BUZZER": _spec(label="Sirenă / buzzer", group="Sarcini (ieșiri)", kind="load", logic="coil", mark="~", default_tag="Q1.2"),
    "VALVE":  _spec(label="Electroventil", group="Sarcini (ieșiri)", kind="load", logic="coil", mark="V", default_tag="Q1.3"),
    # ---- bistabile ----
    "SR": _spec(label="Bistabil SR (set dominant)", group="Bistabile", kind="box", logic="sr", w=100, h=60,
                title="SR", default_tag="M0.0", inputs=[("S1", 20), ("R", 40)], outputs=[("Q1", 20)]),
    "RS": _spec(label="Bistabil RS (reset dominant)", group="Bistabile", kind="box", logic="rs", w=100, h=60,
                title="RS", default_tag="M0.1", inputs=[("S", 20), ("R1", 40)], outputs=[("Q1", 20)]),
    # ---- timere / contoare ----
    "TON": _spec(label="Timer TON (întârziere la anclanșare)", group="Timere / contoare", kind="box", logic="ton",
                 w=100, h=60, title="TON", default_tag="T1", params={"PT": "T#5s"},
                 inputs=[("IN", 20)], outputs=[("Q", 20)], fmt="{tag}  PT={PT}"),
    "TOF": _spec(label="Timer TOF (întârziere la declanșare)", group="Timere / contoare", kind="box", logic="tof",
                 w=100, h=60, title="TOF", default_tag="T2", params={"PT": "T#5s"},
                 inputs=[("IN", 20)], outputs=[("Q", 20)], fmt="{tag}  PT={PT}"),
    "TP":  _spec(label="Timer TP (impuls de durată fixă)", group="Timere / contoare", kind="box", logic="tp",
                 w=100, h=60, title="TP", default_tag="T3", params={"PT": "T#2s"},
                 inputs=[("IN", 20)], outputs=[("Q", 20)], fmt="{tag}  PT={PT}"),
    "CTU": _spec(label="Contor CTU (numără în sus)", group="Timere / contoare", kind="box", logic="ctu",
                 w=100, h=60, title="CTU", default_tag="C1", params={"PV": "10"},
                 inputs=[("CU", 20), ("R", 40)], outputs=[("Q", 20)], fmt="{tag}  PV={PV}"),
    "CTD": _spec(label="Contor CTD (numără în jos)", group="Timere / contoare", kind="box", logic="ctd",
                 w=100, h=60, title="CTD", default_tag="C2", params={"PV": "10"},
                 inputs=[("CD", 20), ("LD", 40)], outputs=[("Q", 20)], fmt="{tag}  PV={PV}"),
    # ---- comparatoare ----
    "CMP_EQ": _cmp("==", "egal"),
    "CMP_NE": _cmp("<>", "diferit"),
    "CMP_GT": _cmp(">", "mai mare"),
    "CMP_GE": _cmp(">=", "mai mare sau egal"),
    "CMP_LT": _cmp("<", "mai mic"),
    "CMP_LE": _cmp("<=", "mai mic sau egal"),
    # ---- matematică ----
    "ADD":  _math("ADD", "+", "+", "adunare"),
    "SUB":  _math("SUB", "-", "-", "scădere"),
    "MUL":  _math("MUL", "*", "*", "înmulțire"),
    "DIV":  _math("DIV", "/", "/", "împărțire"),
    "MOVE": _spec(label="MOVE  OUT := IN (copiere valoare)", group="Matematică", kind="box", logic="math",
                  op="move", w=120, h=40, title="MOVE", has_tag=False, params={"IN": "0", "OUT": "MW0"},
                  inputs=[("EN", 20)], outputs=[("ENO", 20)], fmt="{OUT} := {IN}"),
    # ---- logică ----
    "AND2": _gate("AND", "and", "toate intrările active"),
    "OR2":  _gate("OR", "or", "cel puțin una activă"),
    "XOR2": _gate("XOR", "xor", "exact una activă"),
}