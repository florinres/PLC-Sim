# Editor și simulator LAD (Python)

Aplicație desktop în **Python + PySide6** cu două interfețe grafice sincronizate pe același fișier `.json`:

1. **Editor LAD** — desenare prin *drag-and-drop*, cablare, *undo/redo* și clipboard JSON.
2. **Simulator PLC** — execuție pas cu pas sau în timp real, cu vizualizarea fluxului de curent și a stărilor variabilelor.

Circuitele se salvează în **JSON**, pregătind baza pentru exportul viitor către **TIA Portal** (vezi [Planuri](#planuri)).

## Cuprins

- [Cerințe și instalare](#cerințe-și-instalare)
- [Pornire rapidă](#pornire-rapidă)
- [Editorul](#editorul)
- [Simulatorul](#simulatorul)
- [Componente disponibile](#componente-disponibile)
- [Formatul fișierului](#formatul-fișierului)
- [Structura proiectului](#structura-proiectului)
- [Cum adaugi o componentă nouă](#cum-adaugi-o-componentă-nouă)
- [Limitări](#limitări)
- [Planuri](#planuri)
- [Licență](#licență)

## Cerințe și instalare

- **Python** `3.10` sau mai nou
- **PySide6** (Qt for Python)

```bash
git clone <url-repo>
cd circuit_tool
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Pornire rapidă

Rulează comenzile **din rădăcina proiectului**:

```bash
python -m editor.main                                  # editorul
python -m simulator.main circuits/exemplu.json         # simulatorul (calea e opțională)
```

Flux tipic: desenezi în editor → **Salvează** în `circuits/` → deschizi fișierul în simulator.
Când modifici circuitul în editor, apeși **F5** (Reîncarcă) în simulator.

## Editorul

### Lucrul cu componentele

| Acțiune | Cum |
|---|---|
| Adaugi o componentă | Tragi din paletă pe canvas sau **dublu-click** pe ea în paletă (apare în centrul vizibil) |
| Cauți în paletă | Scrii în câmpul de sus (ex. `timer`, `buton`, `motor`); se caută și după numele categoriei |
| Muți | Tragi componenta; se aliniază automat la grilă |
| Legi cu fir | Tragi de la un **port** (cerc portocaliu) la alt port, de la ieșire la intrare |
| Editezi adresa și parametrii | **Dublu-click** pe componentă (`I0.0`, `Q0.0`, `PT`, `PV`, `A`, `B` etc.) |
| Ștergi | `Del` sau `Backspace` (firele componentei dispar odată cu ea) |
| Selectezi mai multe | Tragi un dreptunghi pe zona liberă |

### Scurtături

| Scurtătură | Acțiune |
|---|---|
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` | Nou / Deschide / Salvează |
| `Ctrl+Shift+S` | Salvează ca |
| `Ctrl+Z` / `Ctrl+Y` | Anulează / Refă (până la 100 de pași) |
| `Ctrl+X` / `Ctrl+C` / `Ctrl+V` | Taie / Copiază / Lipește |
| `Ctrl+D` | Duplică selecția |
| `Ctrl+A` | Selectează tot |
| `Ctrl+rotiță` | Zoom |
| `Ctrl+=` / `Ctrl+-` / `Ctrl+0` | Mărește / Micșorează / Potrivește în fereastră |

**Clipboard:** copierea păstrează componentele, parametrii și firele dintre ele. Lipirea pune grupul la poziția cursorului. Clipboard-ul e cel de sistem (text JSON), deci poți copia între două ferestre ale editorului.

### Reguli de desenare

- Orice rung începe la **șina stângă** și se termină la **șina dreaptă**.
- Mai multe fire într-o **intrare** se combină ca **SAU** (ramuri paralele).
- Mai multe fire dintr-o **ieșire** înseamnă ramificare.
- Pentru ramuri paralele, pune ramura la cel puțin **80 px** sub rung, ca textele să nu se suprapună.
- Portul șinei e la `y + 60`, iar al contactelor la `y + 20`. Pune șina cu **40 px mai sus** decât contactele ca firul să iasă drept.

## Simulatorul

Simulatorul rulează **scan-uri** ca un PLC: rungurile se evaluează de sus în jos, iar în fiecare rung componentele de la stânga la dreapta.

| Element | Semnificație |
|---|---|
| Verde | trece curent |
| Gri / negru | nu trece curent |
| Cifra de sub componentă | starea variabilei (`1`/`0`), `ET 1500 ms` la timere, `CV 3` la contoare, `= 15` la blocurile matematice |
| Bec galben | sarcina de tip bec este alimentată |

### Comenzi

| Comandă | Scurtătură | Ce face |
|---|---|---|
| Deschide | `Ctrl+O` | Încarcă un circuit |
| Reîncarcă | `F5` | Reîncarcă fișierul curent |
| Pauză / Rulează | `Space` | Pornește sau oprește scan-ul automat |
| Pas | `F10` | Execută un singur scan (durata e setabilă în „Pas manual") |
| Reset | `F6` | Resetează variabilele, timerele și contoarele |

- **Interval scan (ms)**: cât de des rulează scan-ul în modul automat.
- **Pas manual (ms)**: timpul simulat adăugat la fiecare apăsare de „Pas".

### Intrări și variabile

- **Click pe un contact** comută variabila lui. Variabilele comandate de o bobină, timer sau contor nu se pot comuta.
- **Butoanele momentane** (Buton NO/NC) rămân active cât ții mouse-ul apăsat. În pauză se comportă ca un comutator, ca să poți face `Pas` cu ele active.
- **Tabelul de variabile** (dreapta) afișează toate variabilele. Intrările și valorile numerice (ex. `MW10`) se pot edita cu dublu-click. Valorile acceptate: `0`/`1`, `true`/`false`, numere.
- Timerele expun `T1.Q` și `T1.ET` (în ms). Contoarele expun `C1.Q` și `C1.CV`. Le poți folosi ca adrese la contacte sau ca operanzi la comparatoare.

### Formatul timpului (parametrul `PT`)

`T#5s`, `T#500ms`, `T#1m30s`, `T#2s500ms`, `T#1h`. Un număr simplu este interpretat ca **milisecunde**.

## Componente disponibile

| Categorie | Componente |
|---|---|
| **Structură** | Șină stângă, șină dreaptă, nod (ramificare/SAU), comentariu |
| **Contacte** | NO, NC, front pozitiv (P), front negativ (N), NOT (inversează fluxul) |
| **Butoane / senzori** | Buton NO (momentan), buton NC (momentan), oprire de urgență (NC), limitator NO/NC, senzor de proximitate |
| **Bobine** | Bobină, bobină negată, SET, RESET |
| **Sarcini (ieșiri)** | Bec, motor, sirenă, electroventil |
| **Bistabile** | SR (set dominant), RS (reset dominant) |
| **Timere / contoare** | TON, TOF, TP, CTU, CTD |
| **Comparatoare** | `==`, `<>`, `>`, `>=`, `<`, `<=` |
| **Matematică** | ADD, SUB, MUL, DIV, MOVE (cu EN/ENO) |
| **Logică** | AND, OR, XOR |

### Note despre comportament

- **NOT** inversează fluxul: dacă nu vine curent la intrare, curentul trece mai departe.
- **Contactele P/N** detectează frontul variabilei și produc un impuls de **un singur scan**.
- **TON** întârzie anclanșarea, **TOF** întârzie declanșarea, **TP** dă un impuls de durată fixă pornit de frontul pozitiv.
- **CTU** numără frontul pozitiv de pe `CU` (`R` resetează). **CTD** scade la fiecare front pe `CD` (`LD` încarcă `PV`), iar `Q` e activ când valoarea ajunge la 0 sau sub.
- **Blocurile matematice** se execută doar cât `EN` e activ. `DIV` cu numere întregi trunchiază spre zero, iar împărțirea la zero lasă `ENO` pe 0 și nu scrie rezultatul.
- Bobinele își scriu variabila în ordinea programului. Un contact situat înaintea bobinei, în același rung, vede valoarea din scan-ul anterior, ca pe un PLC real (de aici funcționează automenținerea).

## Formatul fișierului

Circuitele sunt JSON simplu, citit atât de editor, cât și de simulator:

```json
{
  "components": [
    {"id": "rail_l1", "type": "RAIL_L", "x": 40,  "y": 60,  "tag": "",     "params": {}},
    {"id": "btn_no2", "type": "BTN_NO", "x": 100, "y": 100, "tag": "I1.0", "params": {}},
    {"id": "ton3",    "type": "TON",    "x": 220, "y": 100, "tag": "T1",   "params": {"PT": "T#2s"}},
    {"id": "motor4",  "type": "MOTOR",  "x": 360, "y": 100, "tag": "Q1.1", "params": {}},
    {"id": "rail_r5", "type": "RAIL_R", "x": 480, "y": 60,  "tag": "",     "params": {}}
  ],
  "wires": [
    {"from": ["rail_l1", "out"], "to": ["btn_no2", "in"]},
    {"from": ["btn_no2", "out"], "to": ["ton3", "IN"]},
    {"from": ["ton3", "Q"],      "to": ["motor4", "in"]},
    {"from": ["motor4", "out"],  "to": ["rail_r5", "in"]}
  ]
}
```

- `type` trebuie să existe în `core/library.py`.
- `tag` este adresa variabilei (`I`, `Q`, `M`, `T`, `C` etc.).
- `params` conține parametrii specifici (`PT`, `PV`, `A`, `B`, `IN1`, `IN2`, `OUT`, `TEXT`).
- Un fir merge de la o **ieșire** la o **intrare**: `from: [id, port_ieșire]`, `to: [id, port_intrare]`.

## Structura proiectului

```text
circuit_tool/
├── requirements.txt
├── README.md
├── core/                  # partea comună, fără UI
│   ├── library.py         # definițiile tuturor componentelor
│   ├── model.py           # Component, Wire, Circuit (dataclass-uri)
│   └── io.py              # salvare / încărcare JSON
├── editor/                # aplicația 1
│   ├── main.py            # fereastra principală, meniuri, bară de unelte
│   ├── canvas.py          # scena: drag-and-drop, fire, clipboard, undo/redo
│   ├── items.py           # desenul componentelor și al firelor
│   └── palette.py         # paleta cu categorii, căutare și previzualizări
├── simulator/             # aplicația 2
│   ├── engine.py          # motorul de scan (fără UI)
│   ├── view.py            # vizualizarea circuitului cu stări live
│   └── main.py            # fereastra principală, comenzi, tabel de variabile
└── circuits/              # circuitele salvate (.json)
```

Fiecare folder cu cod (`core/`, `editor/`, `simulator/`) trebuie să conțină un fișier `__init__.py` gol.

## Cum adaugi o componentă nouă

1. **`core/library.py`**: adaugi o intrare în `COMPONENT_TYPES` cu `_spec(...)`:
   - `kind` stabilește cum se desenează (`contact`, `coil`, `load`, `box`, `rail`, `junction`, `note`).
   - `logic` stabilește ce face în simulator.
   - Porturile sunt `(nume, y)`, cu `y` multiplu de 20.
2. **`editor/items.py`**: dacă ai nevoie de un simbol nou, adaugi o ramură în `paint`.
3. **`simulator/engine.py`**: dacă folosești o valoare nouă pentru `logic`, adaugi o ramură în `_eval` (și, dacă e cazul, în `_discover` și `status_text`).

Paleta, salvarea și clipboard-ul preiau componenta automat.

## Limitări

- Firele se desenează ortogonal, cu un singur cot, fără rutare automată.
- Rungurile sunt grupuri de componente conectate; ordinea de execuție între rungurile independente este de sus în jos după poziție.
- Bucle de fire (un fir înapoi) sunt tolerate cu valoarea din scan-ul anterior, dar nu sunt recomandate.
- Nu există încă export către TIA Portal.

## Planuri

- [ ] Generator de cod **LAD pentru TIA Portal** (export XML SimaticML sau automatizare prin TIA Openness)
- [ ] Mai multe componente (CTUD, RTO, conversii de tip)
- [ ] Validare circuit (intrări nelegate, bobine fără șină, adrese duplicate)
- [ ] Teste automate pentru motorul de simulare

## Licență

Alege o licență (de ex. MIT) și adaug-o aici.