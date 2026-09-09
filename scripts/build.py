"""
VEMO -- Consolidated Executive Summary: UN SOLO script que hace todo.

  python build.py

Descarga los 4 dashboards individuales (DAE, LTO, EV Fleets, VCN) desde GitHub,
extrae su objeto `const D` embebido, arma consolidated_data.json, y genera
index.html -- un solo archivo autocontenido (CSS + JS + datos incrustados,
nada que abrir aparte).

Las tarjetas KPI de cada empresa, el grafico "KPI Trend" y las lineas del P&L
Consolidado replican exactamente el formato de los 4 dashboards individuales
(ver KPI_DEFS abajo -- son los mismos KPI13 de cada Executive Summary nativo).

El P&L Consolidado (Actuals) se lee del archivo oficial
"VEMO 2026 Consolidated Financials FV.xlsx" (carpeta 2026, junto a "db bl"),
hoja "Board Outputs", bloque "Normalized" -- el mismo P&L que ya usa el board.
Si ese archivo no esta disponible (por ejemplo corriendo el script fuera de la
maquina con OneDrive sincronizado), cae automaticamente a sumar los P&L de los
4 dashboards individuales (sin eliminaciones).

Correr despues de que los 4 dashboards individuales ya tengan el mes nuevo.
"""
import json, os, base64, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # carpeta donde vive el index.html final
CACHE = os.path.join(HERE, '_source_cache')

SOURCES = {
    'DAE_BoardD': 'https://raw.githubusercontent.com/VEMO-FP-A/DAE_BoardD/main/index.html',
    'LTO_BoardD': 'https://raw.githubusercontent.com/VEMO-FP-A/LTO_BoardD/main/index.html',
    'VCN_BoardD': 'https://raw.githubusercontent.com/VEMO-FP-A/VCN_BoardD/main/index.html',
    'EV_BoardD':  'https://raw.githubusercontent.com/VEMO-FP-A/EV_BoardD/main/index.html',
}


# ---------- 1) extraer el objeto `const D = {...}` embebido en un dashboard ----------

def extract_D(path):
    with open(path, encoding='utf-8') as f:
        content = f.read()
    idx = content.find('const D = {')
    if idx == -1:
        idx = content.find('const D={')
    if idx == -1:
        return None
    start = content.find('{', idx)
    depth = 0
    i = start
    in_str = False
    esc = False
    while i < len(content):
        c = content[i]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    i += 1
                    break
        i += 1
    raw = content[start:i]
    return json.loads(raw)


# ---------- 1b) extraer el arreglo `const KPI13=[...]` embebido en cada
# dashboard fuente -- ASI la lista de tarjetas KPI de cada empresa se lee
# EN CADA BUILD del propio dashboard (no de una copia estatica): si alguien
# agrega, renombra o quita un KPI en su Executive Summary, el proximo
# `python build.py` del consolidado lo recoge solo. KPI13 no es JSON valido
# (keys sin comillas, strings con comilla simple) asi que se usa un parser
# minimo para ese literal JS restringido en vez de json.loads. ----------

def _parse_js_literal(text):
    """Parser minimo para el subconjunto de sintaxis JS usado en KPI13:
    objetos/arreglos anidados, strings con comilla simple o doble,
    true/false/null, numeros, y keys de objeto sin comillas. No es un
    parser de JS general -- solo alcanza para estos arreglos de config
    chicos y escritos a mano."""
    i = 0
    n = len(text)

    def skip_ws():
        # also skips // line comments and /* block */ comments -- some
        # dashboards' KPI13 arrays carry a leading explanatory comment
        nonlocal i
        while i < n:
            if text[i].isspace():
                i += 1
            elif text[i:i + 2] == '//':
                while i < n and ord(text[i]) != 10:  # 10 = newline
                    i += 1
            elif text[i:i + 2] == '/*':
                end = text.find('*/', i + 2)
                i = end + 2 if end != -1 else n
            else:
                break

    def parse_string():
        nonlocal i
        quote = text[i]
        i += 1
        out = []
        while text[i] != quote:
            if ord(text[i]) == 92:  # backslash escape (avoids literal '' here -- see note below)
                out.append(text[i + 1])
                i += 2
            else:
                out.append(text[i])
                i += 1
        i += 1
        return ''.join(out)

    def parse_number():
        nonlocal i
        start = i
        while i < n and (text[i].isdigit() or text[i] in '+-.eE'):
            i += 1
        raw = text[start:i]
        return float(raw) if ('.' in raw or 'e' in raw.lower()) else int(raw)

    def parse_key():
        nonlocal i
        skip_ws()
        if text[i] in ('"', "'"):
            return parse_string()
        start = i
        while i < n and (text[i].isalnum() or text[i] == '_'):
            i += 1
        return text[start:i]

    def parse_value():
        nonlocal i
        skip_ws()
        c = text[i]
        if c == '{':
            return parse_object()
        if c == '[':
            return parse_array()
        if c in ("'", '"'):
            return parse_string()
        if text[i:i + 4] == 'true':
            i += 4
            return True
        if text[i:i + 5] == 'false':
            i += 5
            return False
        if text[i:i + 4] == 'null':
            i += 4
            return None
        return parse_number()

    def parse_object():
        nonlocal i
        i += 1
        obj = {}
        skip_ws()
        while text[i] != '}':
            key = parse_key()
            skip_ws()
            i += 1  # ':'
            obj[key] = parse_value()
            skip_ws()
            if text[i] == ',':
                i += 1
                skip_ws()
        i += 1
        return obj

    def parse_array():
        nonlocal i
        i += 1
        arr = []
        skip_ws()
        while text[i] != ']':
            arr.append(parse_value())
            skip_ws()
            if text[i] == ',':
                i += 1
                skip_ws()
        i += 1
        return arr

    return parse_value()


def extract_kpi13(path):
    """Lee `const KPI13=[...]` directamente del HTML descargado de cada
    dashboard fuente (fresco en cada build) y lo normaliza al esquema que
    usa resolve_kpi() (l/keys/unit/type/fmt/better/add). Devuelve None si
    no se encuentra o si el parseo falla -- el llamador cae de vuelta al
    KPI_DEFS estatico (kpi_defs.py) en ese caso."""
    try:
        with open(path, encoding='utf-8') as f:
            content = f.read()
        idx = content.find('const KPI13=')
        if idx == -1:
            idx = content.find('const KPI13 =')
        if idx == -1:
            return None
        start = content.find('[', idx)
        depth = 0
        i = start
        in_str = False
        quote = None
        while i < len(content):
            c = content[i]
            if in_str:
                if ord(c) == 92:  # backslash escape
                    i += 1
                elif c == quote:
                    in_str = False
            else:
                if c in ("'", '"'):
                    in_str = True
                    quote = c
                elif c == '[':
                    depth += 1
                elif c == ']':
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
            i += 1
        raw = _parse_js_literal(content[start:i])
        out = []
        for entry in raw:
            item = {
                'l': entry.get('l'), 'keys': entry.get('keys'),
                'unit': entry.get('unit'), 'type': entry.get('type'),
                'better': entry.get('better'),
            }
            if 'fmt' in entry:
                item['fmt'] = entry['fmt']
            if 'add' in entry:
                item['add'] = entry['add']
            out.append(item)
        return out if out else None
    except Exception as e:
        print('  (no se pudo leer KPI13 de', path, '-- usando KPI_DEFS estatico:', e, ')')
        return None


# ---------- 2) descargar los 4 dashboards fuente ----------
def fetch(name, url):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f'{name}.html')
    req = urllib.request.Request(url, headers={'User-Agent': 'vemo-consolidated-build'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read()
    with open(path, 'wb') as f:
        f.write(content)
    return path


def download_sources():
    for name, url in SOURCES.items():
        print('descargando', name, '...')
        fetch(name, url)


# ---------- 3) KPI13 reales de cada dashboard (Executive Summary nativo) ----------
# Ported verbatim from each live dashboard's own `const KPI13=[...]` array -- estas
# SON las metricas principales de cada negocio (operativas/comerciales), NO metricas
# financieras genericas -- las financieras viven solo en el P&L Consolidado de abajo.
KPI_DEFS = {
    'dae': [
        {'l': 'Performance Ratio', 'keys': ['performance_ratio'], 'unit': '%', 'type': 'pct', 'better': 'up'},
        {'l': 'Performance Ratio Exc. LTO', 'keys': ['performance_ratio_exc_lto'], 'unit': '%', 'type': 'pct', 'better': 'up'},
        {'l': 'Supply Hours', 'keys': ['supply_hours', 'time_online'], 'unit': 'Hrs', 'type': 'num', 'fmt': 'int', 'better': 'up'},
        {'l': 'Revenue Per Hour (RPH)', 'keys': ['revenue_per_hour', 'rev_per_hour_vemo'], 'unit': 'MXN$', 'type': 'num', 'fmt': 'n1', 'better': 'up'},
        {'l': 'Utilization', 'keys': ['utilization'], 'unit': '%', 'type': 'pct', 'better': 'up'},
        {'l': 'Trips', 'keys': ['trips_total', 'trips_completed'], 'unit': '#', 'type': 'num', 'fmt': 'k', 'better': 'up'},
        {'l': 'Active Drivers (EoP)', 'keys': ['eop_active_drivers', 'active_drivers'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
        {'l': 'Driver Fill Rate (EoP)', 'keys': ['fill_rate_eop', 'fill_rate_avg'], 'unit': '%', 'type': 'pct', 'better': 'up'},
        {'l': 'Total Fleet', 'keys': ['total_fleet'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
        {'l': 'Active Fleet', 'keys': ['operational_vehicles'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
        {'l': 'OOS', 'keys': ['oos_pct', 'oos', 'inactivity_rate'], 'unit': '%', 'type': 'pct', 'better': 'down'},
        {'l': 'Maintenance per km', 'keys': ['maintenance_per_km'], 'unit': 'MXN$/km', 'type': 'num', 'fmt': 'n2', 'better': 'down'},
        {'l': 'Total Incidents', 'keys': ['inc_atfault_total'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'down', 'add': ['inc_notfault_total']},
        {'l': 'Hires per DAE recruiter', 'keys': ['hires_per_recruiter'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
    ],
    'ev': [
        {'l': 'EPC Sales (Third Party)', 'keys': ['epc_sales_3p'], 'unit': 'MXN$m', 'type': 'money', 'fmt': 'mm', 'better': 'up'},
        {'l': 'EPC Backlog', 'keys': ['epc_backlog'], 'unit': 'MXN$m', 'type': 'money', 'fmt': 'mm', 'better': 'up'},
        {'l': 'EPC Pipeline', 'keys': ['epc_pipeline'], 'unit': 'MXN$m', 'type': 'money', 'fmt': 'mm', 'better': 'up'},
        {'l': 'ZEE Monitored LTO Vehicles', 'keys': ['zee_monitored_lto'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
        {'l': 'ZEE Monitored Third-Party Vehicles', 'keys': ['zee_monitored_3p'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
        {'l': 'ZEE Total Monitored Vehicles', 'keys': ['zee_total_monitored'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
    ],
    'vcn': [
        {'l': 'Network Installed Capacity', 'keys': ['installed_capacity_mw'], 'unit': 'MW', 'type': 'num', 'fmt': 'n1', 'better': 'up'},
        {'l': 'Network Active Connectors', 'keys': ['total_connectors'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
        {'l': 'Network Underwritten IRR', 'keys': ['underwritten_irr'], 'unit': '%', 'type': 'pct', 'better': 'up'},
        {'l': 'Throughput', 'keys': ['sessions_total'], 'unit': 'MWh', 'type': 'num', 'fmt': 'k', 'better': 'up'},
        {'l': 'Network Throughput Utilization', 'keys': ['utilization'], 'unit': '%', 'type': 'pct', 'better': 'up'},
        {'l': 'Daily Throughput per Connector', 'keys': ['throughput_per_connector'], 'unit': 'kWh/connector/day', 'type': 'num', 'fmt': 'n0', 'better': 'up'},
        {'l': 'Avg. Revenue per kWh', 'keys': ['rev_per_kwh'], 'unit': 'MXN$/kWh', 'type': 'num', 'fmt': 'n1', 'better': 'up'},
        {'l': 'Daily Revenue per Connector', 'keys': ['revenue_per_connector'], 'unit': 'MXN$/conn/day', 'type': 'num', 'fmt': 'n0', 'better': 'up'},
        {'l': 'Energy Margin per kWh', 'keys': ['energy_margin_kwh'], 'unit': '%', 'type': 'pct', 'better': 'up'},
        {'l': 'Gross Profit Margin per kWh', 'keys': ['gross_margin_kwh'], 'unit': '%', 'type': 'pct', 'better': 'up'},
        {'l': 'Technical Uptime', 'keys': ['uptime_pct'], 'unit': '%', 'type': 'pct', 'better': 'up'},
    ],
    'lto': [
        {'l': 'Gross Portfolio (exc. WK &amp; Other loans)', 'keys': ['vrpm_gross_portfolio_total'], 'unit': 'MXNm', 'type': 'num', 'fmt': 'mm', 'better': 'up'},
        {'l': 'Portfolio Active Fleet', 'keys': ['vrpm_active_fleet_total'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
        {'l': 'Origination of New Vehicles (#)', 'keys': ['vrpm_orig_new_total'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
        {'l': 'Origination of Used Vehicles (#)', 'keys': ['orig_used_total'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'up'},
        {'l': 'Portfolio Asset Yield (YTD)', 'keys': ['vrpm_asset_yield'], 'unit': '%', 'type': 'pct', 'better': 'up'},
        {'l': 'Effective Repossessions', 'keys': ['vrpm_repo_total'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'down'},
        {'l': 'Repossession Rate (L)', 'keys': ['vrpm_repo_pct_legacy'], 'unit': '%', 'type': 'pct', 'better': 'down'},
        {'l': 'Repossession Rate (N)', 'keys': ['vrpm_repo_pct_new'], 'unit': '%', 'type': 'pct', 'better': 'down'},
        {'l': 'Repossessions (% Active Fleet)', 'keys': ['vrpm_repo_pct'], 'unit': '%', 'type': 'pct', 'better': 'down'},
        {'l': 'Used Vehicle Inventory', 'keys': ['vrpm_uvi_total'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'down'},
        {'l': 'Used Vehicle Inventory (% Total Fleet)', 'keys': ['vrpm_uvi_pct'], 'unit': '%', 'type': 'pct', 'better': 'down'},
        {'l': 'Portfolio Default Rate', 'keys': ['vrpm_default_rate'], 'unit': '%', 'type': 'pct', 'better': 'down'},
    ],
}


COMPANIES_META = {
    'vcn': {'name': 'VCN', 'full': 'VEMO Charging Network', 'url': 'https://vemo-fp-a.github.io/VCN_BoardD/', 'file': 'VCN_BoardD'},
    'lto': {'name': 'LTO', 'full': 'Lease-to-Own', 'url': 'https://vemo-fp-a.github.io/LTO_BoardD/', 'file': 'LTO_BoardD'},
    'dae': {'name': 'DAE', 'full': 'Driver as Employee', 'url': 'https://vemo-fp-a.github.io/DAE_BoardD/', 'file': 'DAE_BoardD'},
    'ev':  {'name': 'EV Fleets', 'full': 'Electric Vehicle Fleets', 'url': 'https://vemo-fp-a.github.io/EV_BoardD/', 'file': 'EV_BoardD'},
}

MONTHS_EN = ['January','February','March','April','May','June','July','August',
             'September','October','November','December']

PL_FIELDS = ['revenue', 'opex', 'gross_profit', 'sga_total', 'ebitda', 'da',
             'ebit', 'interest_expense', 'ebt', 'taxes', 'net_income']

# The official, board-presented Consolidated P&L lives in this workbook on
# the user's OneDrive, sheet "Board Outputs" -- the SUMMARY block (not the
# full monthly series blocks above it), which already carries YoY/MoM/Budget/
# Budget YTD, exactly the shape our reconciliation table needs.
BOARD_XLSX_CANDIDATES = [
    os.path.join(ROOT, '..', '..', 'VEMO 2026 Consolidated Financials FV.xlsx'),
]

# field -> row label, searched within the presented block (see below)
BOARD_PRESENTED_LABELS = {
    'revenue': 'Revenues',
    'opex': 'Opex',
    'gross_profit': 'Gross profit',
    'gross_margin': 'Gross Margin (%)',
    'sga_total': 'SG&A',
    'ebitda': 'EBITDA',
    'ebitda_margin': 'EBITDA Margin (%)',
    'da': 'D&A',
    'ebit': 'EBIT',
    'interest_expense': 'Interest Expense',
    'ebt': 'EBT',
    'taxes': 'Taxes',
    'net_income': 'Net income',
    'net_margin': 'Net Income Margin (%)',
}
MARGIN_FIELDS = {'gross_margin', 'ebitda_margin', 'net_margin'}
# columns of the presented block, per its own header row (see below)
BOARD_PRESENTED_COLS = {'yoy': 3, 'prev': 4, 'cur': 5, 'ytd': 6, 'bud_cur': 8, 'bud_ytd': 9}


def extract_consolidated_pl_from_board_xlsx(path):
    """Reads the official, board-presented Consolidated P&L straight from the
    'Board Outputs' sheet -- the summary block that already has YoY/MoM/vs.
    Budget/vs. Budget YTD precomputed (not the two monthly-series blocks
    above it in the same sheet). All 3 blocks share the label 'P&L (MXNm)'
    in col B, so the presented one is told apart by its header row: its
    column 8 says literally 'Budget' (the monthly-series blocks have a date
    there instead). Row lookup is label-based (robust to the sheet being
    edited month to month), not hardcoded row numbers. Returns a dict of
    {field: {yoy, prev, cur, ytd, bud_cur, bud_ytd}} per PL_FIELDS entry plus
    the 3 margin fields (already in percentage-point form), or None (caller
    falls back to summing the 4 dashboards) if the file/sheet/labels aren't
    found -- e.g. running outside the user's OneDrive-synced machine."""
    try:
        import openpyxl
    except ImportError:
        print('openpyxl no disponible -- P&L Consolidado usara el fallback (suma de las 4 empresas).')
        return None
    if not os.path.exists(path):
        return None
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        if 'Board Outputs' not in wb.sheetnames:
            return None
        ws = wb['Board Outputs']

        header_row = None
        scan_limit = min(ws.max_row, 500)
        for r in range(1, scan_limit + 1):
            v = ws.cell(row=r, column=2).value
            if v is not None and str(v).strip() == 'P&L (MXNm)':
                c8 = ws.cell(row=r, column=8).value
                if isinstance(c8, str) and c8.strip().lower().startswith('budget'):
                    header_row = r  # keep the last match -- the current one
        if header_row is None:
            return None

        def find_label(target, r0, r1):
            for r in range(r0, r1 + 1):
                v = ws.cell(row=r, column=2).value
                if v is not None and str(v).strip() == target:
                    return r
            return None

        lo, hi = header_row + 1, header_row + 20
        rows = {key: find_label(label, lo, hi) for key, label in BOARD_PRESENTED_LABELS.items()}
        if any(v is None for v in rows.values()):
            print('Board Outputs: no se pudieron ubicar todas las filas del bloque presentado (fila', header_row, ') -- usando fallback.')
            return None

        out = {}
        for key, r in rows.items():
            vals = {}
            for name, c in BOARD_PRESENTED_COLS.items():
                v = ws.cell(row=r, column=c).value
                if isinstance(v, (int, float)):
                    vals[name] = round(v * 100, 4) if key in MARGIN_FIELDS else round(v, 2)
                else:
                    vals[name] = None
            out[key] = vals
        return out
    except Exception as e:
        print('Error leyendo el Consolidated P&L oficial (usando fallback):', e)
        return None


def ytd_start_idx(months, lai):
    """Espejo de computeYtdStart() en app.js: indice del mes '<anio-en-curso>-01'
    dentro de `months`, usado como inicio del rango YTD (Jan del ano en curso)."""
    year = months[lai].split('-')[0]
    target = f'{year}-01'
    for i, m in enumerate(months):
        if m == target:
            return i
    return 0


def sum_range(arr, i0, i1):
    vals = [v for v in arr[i0:i1 + 1] if v is not None]
    return round(sum(vals), 2) if vals else None


def scalarize_line(actual, budget, lai, ys):
    """Reduce un par de series mensuales (actual, budget) al mismo snapshot
    escalar {yoy, prev, cur, ytd, bud_cur, bud_ytd} que ya entrega el bloque
    'presentado' del Board Outputs -- usado por el fallback (suma de las 4
    empresas) para que ambas rutas produzcan el mismo esquema."""
    yoy = actual[lai - 12] if lai >= 12 else None
    prev = actual[lai - 1] if lai >= 1 else None
    cur = actual[lai]
    ytd = sum_range(actual, ys, lai)
    bud_cur = budget[lai] if budget else None
    bud_ytd = sum_range(budget, ys, lai) if budget else None
    return {'yoy': yoy, 'prev': prev, 'cur': cur, 'ytd': ytd, 'bud_cur': bud_cur, 'bud_ytd': bud_ytd}


def scalarize_margin(num_a, den_a, num_b, den_b, lai, ys):
    """Igual que scalarize_line pero para un margen (numerador/denominador
    mensuales, actual y budget) -- divide primero en cada uno de los 6 puntos
    del snapshot (nunca sumando porcentajes), en puntos porcentuales."""
    def mk(nu, de):
        return round(nu / de * 100, 4) if (nu is not None and de is not None and de != 0) else None

    yoy = mk(num_a[lai - 12], den_a[lai - 12]) if lai >= 12 else None
    prev = mk(num_a[lai - 1], den_a[lai - 1]) if lai >= 1 else None
    cur = mk(num_a[lai], den_a[lai])
    ytd = mk(sum_range(num_a, ys, lai), sum_range(den_a, ys, lai))
    bud_cur = mk(num_b[lai], den_b[lai]) if (num_b and den_b) else None
    bud_ytd = mk(sum_range(num_b, ys, lai), sum_range(den_b, ys, lai)) if (num_b and den_b) else None
    return {'yoy': yoy, 'prev': prev, 'cur': cur, 'ytd': ytd, 'bud_cur': bud_cur, 'bud_ytd': bud_ytd}


def full(d, key, n):
    if key is None:
        return [None] * n
    a = d.get(key)
    if a is None:
        return [None] * n
    a = list(a)
    if len(a) < n:
        a = a + [None] * (n - len(a))
    return [(round(x, 4) if isinstance(x, (int, float)) else None) for x in a[:n]]


def add_arrays(*arrs):
    n = len(arrs[0])
    out = []
    for i in range(n):
        vals = [a[i] for a in arrs if a[i] is not None]
        out.append(round(sum(vals), 4) if vals else None)
    return out


def strip_leading_zeros(arr):
    """Un tramo inicial de ceros (antes del primer valor real) se trata como
    'todavia sin informacion' (None), no como actividad cero -- varios KPIs
    operativos empiezan a reportarse a mitad de periodo y el dashboard fuente
    deja esos meses en 0 en vez de null, lo que graficaba una linea plana en
    $0 en el KPI Trend / sparkline en lugar de no graficar nada."""
    out = list(arr)
    for i in range(len(out)):
        if out[i] == 0:
            out[i] = None
        elif out[i] is not None:
            break
    return out


def arr_cand(d, keys):
    for k in keys:
        a = d.get(k)
        if a and any(v is not None for v in a):
            return k, a
    return None, None


def barr_cand(d, keys):
    for k in keys:
        for bk in ('budget_' + k, k + '_budget'):
            a = d.get(bk)
            if a and any((v is not None and v != 0) for v in a):
                return bk, a
    return None, None


def resolve_kpi(d, ki, n):
    """Resuelve un metric-spec de KPI_DEFS contra el `D` de una empresa: busca la
    primera key candidata con datos reales (arr_cand), su budget si existe
    (barr_cand), y si el spec trae 'add' (ej. DAE 'Total Incidents' = at-fault +
    not-at-fault) lo suma SOLO al valor -- nunca al budget ni al sparkline, tal
    como hacen los dashboards originales."""
    ak, _ = arr_cand(d, ki['keys'])
    bk, _ = barr_cand(d, ki['keys'])
    base = strip_leading_zeros(full(d, ak, n))
    spark = list(base)
    data = list(base)
    if 'add' in ki:
        a2k, _ = arr_cand(d, ki['add'])
        if a2k:
            add_full = strip_leading_zeros(full(d, a2k, n))
            data = [
                (x + y) if (x is not None and y is not None) else (x if x is not None else y)
                for x, y in zip(data, add_full)
            ]
    budget = full(d, bk, n) if bk else None
    return {
        'l': ki['l'], 'unit': ki['unit'], 'type': ki['type'],
        'fmt': ki.get('fmt'), 'better': ki['better'],
        'data': data, 'spark': spark, 'budget': budget,
    }


def pl_lines(d, key, n):
    """Devuelve dict {field: (actual_arr, budget_arr)} -- series mensuales completas,
    ya reconciliadas para que gross_profit == revenue+opex y ebitda == gross_profit+sga_total
    en cada empresa (verificado contra los 4 dashboards fuente)."""
    if key == 'lto':
        # VEMO Impulso es un negocio financiero de leasing: no reporta EBITDA
        # nativamente. Se reconstruye de forma sintetica y consistente:
        # EBITDA = EBT + Gastos Financieros + D&A ; EBIT = EBT + Gastos Financieros.
        rev = full(d, 'net_operating_revenue', n); brev = full(d, 'budget_net_operating_revenue', n)
        opex = full(d, 'cogs_total', n); bopex = full(d, 'budget_cogs_total', n)
        gp = add_arrays(rev, opex); bgp = add_arrays(brev, bopex)
        sga = full(d, 'total_sga', n); bsga = full(d, 'budget_total_sga', n)
        da = full(d, 'da_total', n); bda = full(d, 'budget_da_total', n)
        ie = full(d, 'interest_expense', n); bie = full(d, 'budget_interest_expense', n)
        ebt = full(d, 'ebt', n); bebt = full(d, 'budget_ebt', n)
        taxes = full(d, 'taxes', n); btaxes = full(d, 'budget_taxes', n)
        ni = full(d, 'net_income', n); bni = full(d, 'budget_net_income', n)
        ebitda = add_arrays(ebt, ie, da); bebitda = add_arrays(bebt, bie, bda)
        ebit = add_arrays(ebt, ie); bebit = add_arrays(bebt, bie)
    else:
        rev = full(d, 'revenue', n); brev = full(d, 'budget_revenue', n)
        opex = full(d, 'opex', n); bopex = full(d, 'budget_opex', n)
        gp = full(d, 'gross_profit', n); bgp = full(d, 'budget_gross_profit', n)
        sga_key = 'sga' if key == 'ev' else 'sga_total'
        sga = full(d, sga_key, n); bsga = full(d, 'budget_' + sga_key, n)
        ebitda = full(d, 'ebitda', n); bebitda = full(d, 'budget_ebitda', n)
        da = full(d, 'da', n); bda = full(d, 'budget_da', n)
        ebit = full(d, 'ebit', n); bebit = full(d, 'budget_ebit', n)
        ie = full(d, 'interest_expense', n); bie = full(d, 'budget_interest_expense', n)
        ebt = full(d, 'ebt', n); bebt = full(d, 'budget_ebt', n)
        taxes = full(d, 'taxes', n); btaxes = full(d, 'budget_taxes', n)
        ni = full(d, 'net_income', n); bni = full(d, 'budget_net_income', n)
        if key == 'vcn':
            # VCN's gross_profit ya neta AMBOS cogs_total Y opex (revenue + cogs_total
            # + opex == gross_profit, confirmado contra la fuente), asi que la linea
            # "COGS + Opex" debe combinar ambos; y SG&A (que VCN no reporta como campo
            # propio) es la brecha entre EBITDA y utilidad bruta.
            cogs = full(d, 'cogs_total', n); bcogs = full(d, 'budget_cogs_total', n)
            opex = add_arrays(cogs, opex); bopex = add_arrays(bcogs, bopex)
            sga = [(e - g) if (e is not None and g is not None) else None for e, g in zip(ebitda, gp)]
            bsga = [(e - g) if (e is not None and g is not None) else None for e, g in zip(bebitda, bgp)]
    return {
        'revenue': (rev, brev), 'opex': (opex, bopex), 'gross_profit': (gp, bgp),
        'sga_total': (sga, bsga), 'ebitda': (ebitda, bebitda), 'da': (da, bda),
        'ebit': (ebit, bebit), 'interest_expense': (ie, bie), 'ebt': (ebt, bebt),
        'taxes': (taxes, btaxes), 'net_income': (ni, bni),
    }


def _build_companies():
    dsets = {k: extract_D(os.path.join(CACHE, f"{v['file']}.html")) for k, v in COMPANIES_META.items()}
    months = dsets['dae']['months']
    n = len(months)
    lai = dsets['dae']['last_actual_idx']

    companies = {}
    for ck, d in dsets.items():
        meta = COMPANIES_META[ck]
        # KPI list: prefer parsing the freshly-downloaded dashboard's own
        # KPI13 array (so a KPI added/renamed/removed there shows up here
        # automatically on the next build); fall back to the static
        # KPI_DEFS snapshot (kpi_defs.py) only if that extraction fails.
        kpi_defs_live = extract_kpi13(os.path.join(CACHE, f"{meta['file']}.html"))
        kpi_defs_ck = kpi_defs_live if kpi_defs_live is not None else KPI_DEFS[ck]
        if kpi_defs_live is None:
            print('  KPI13 de', ck, 'no se pudo leer del dashboard -- usando KPI_DEFS estatico (puede estar desactualizado).')
        kpis = [resolve_kpi(d, ki, n) for ki in kpi_defs_ck]
        companies[ck] = {
            'name': meta['name'], 'full': meta['full'], 'url': meta['url'],
            'kpis': kpis,
        }

    all_lines = {ck: pl_lines(d, ck, n) for ck, d in dsets.items()}

    # Actuals + Budget: prefer the official, board-presented Consolidated P&L
    # (real eliminations, real consolidated budget) straight from the "Board
    # Outputs" workbook; fall back to summing the 4 dashboards' own lines (no
    # eliminations, budget summed from each company) if that workbook isn't
    # reachable. Either way the result is {field: {yoy, prev, cur, ytd,
    # bud_cur, bud_ytd}} -- a scalar snapshot, not a monthly series -- since
    # that's the shape the reconciliation table actually needs.
    board_actuals = None
    for xlsx_path in BOARD_XLSX_CANDIDATES:
        board_actuals = extract_consolidated_pl_from_board_xlsx(xlsx_path)
        if board_actuals is not None:
            break

    consolidated_pl_source = 'board_xlsx' if board_actuals is not None else 'summed_fallback'
    if board_actuals is not None:
        # Ya viene armado como {field: {yoy, prev, cur, ytd, bud_cur, bud_ytd}}
        # para los 11 PL_FIELDS + las 3 margenes -- se usa tal cual.
        consolidated_pl = board_actuals
    else:
        ys = ytd_start_idx(months, lai)
        totals_a, totals_b = {}, {}
        for f in PL_FIELDS:
            tot_a = [None] * n
            tot_b = [None] * n
            for ck in dsets:
                a, b = all_lines[ck][f]
                for i in range(n):
                    if a[i] is not None:
                        tot_a[i] = (tot_a[i] or 0) + a[i]
                    if b[i] is not None:
                        tot_b[i] = (tot_b[i] or 0) + b[i]
            totals_a[f] = [round(x, 2) if x is not None else None for x in tot_a]
            totals_b[f] = [round(x, 2) if x is not None else None for x in tot_b]

        consolidated_pl = {}
        for f in PL_FIELDS:
            consolidated_pl[f] = scalarize_line(totals_a[f], totals_b[f], lai, ys)

        for mkey, numf, denf in (
            ('gross_margin', 'gross_profit', 'revenue'),
            ('ebitda_margin', 'ebitda', 'revenue'),
            ('net_margin', 'net_income', 'revenue'),
        ):
            consolidated_pl[mkey] = scalarize_margin(
                totals_a[numf], totals_a[denf], totals_b[numf], totals_b[denf], lai, ys
            )

    y, m = months[lai].split('-')
    generated_month_label = f"{MONTHS_EN[int(m)-1]} {y}"

    return {
        'months': months,
        'last_actual_idx': lai,
        'generated_month': months[lai],
        'generated_month_label': generated_month_label,
        'companies': companies,
        'consolidated_pl': consolidated_pl,
        'consolidated_pl_source': consolidated_pl_source,
    }


def build_consolidated_data():
    download_sources()
    data = _build_companies()
    # NOTA: el dataset conserva TODA la historia (Jan-25 en adelante) -- el
    # P&L Consolidado (incluida la comparacion YoY) necesita 12+ meses hacia
    # atras. El recorte a "solo el ano en curso" aplica unicamente a las
    # tarjetas KPI y al KPI Trend (ver YTD_START en app.js), no al dataset.
    with open(os.path.join(ROOT, 'consolidated_data.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('consolidated_data.json listo. mes mas reciente:', data['generated_month'])
    return data



# ---------- 4) plantilla HTML (con placeholders __X__) ----------
HTML_TEMPLATE = '<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>VEMO — Consolidated Executive Summary</title>\n<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">\n<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n<style>\n:root{\n  --forest:#1F5454;--teal:#11ABAB;--teal-deep:#168888;--mint:#7BDADA;\n  --red:#C0392B;--green:#117A45;--amber:#E59500;--bg:#f5f6f7;--sf:#fff;--b:#e8eaed;\n  --tx:#222;--tx2:#555;--tx3:#888;--rs:6px;--r:10px;\n}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:\'Space Grotesk\',sans-serif;background:var(--bg);color:var(--tx);line-height:1.4;padding-left:34px;position:relative}\nbody.dark-mode{--bg:#1a1f23;--sf:#22282d;--b:#353c42;--tx:#e6ebee;--tx2:#d4dae0;--tx3:#9aa3ac;--forest:#7BDADA;color:#e6ebee!important}\nbody.dark-mode *{color:inherit}\n.wrap{max-width:1400px;margin:0 auto;padding:28px 24px 60px}\n\n/* left/bottom confidentiality ribbons -- ported verbatim from the individual dashboards */\n.ribbon{position:fixed;left:0;top:0;bottom:0;width:28px;background:var(--teal);display:flex;align-items:flex-start;justify-content:center;padding-top:80px;z-index:5}\n.ribbon span{writing-mode:vertical-rl;transform:rotate(180deg);color:#fff;font-size:9px;letter-spacing:0.18em;font-weight:600;text-transform:uppercase}\n.ribbon-bot{position:fixed;left:0;bottom:0;width:28px;height:120px;background:var(--teal);display:flex;align-items:flex-end;justify-content:center;padding-bottom:16px;z-index:5}\n.ribbon-bot span{writing-mode:vertical-rl;transform:rotate(180deg);color:#fff;font-size:8px;letter-spacing:0.18em;font-weight:600;text-transform:uppercase}\n\n.topbar{display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:28px}\n.title{font-size:28px;font-weight:700;color:var(--forest);letter-spacing:-0.01em;line-height:1.05}\n.title b{color:var(--teal);font-weight:800}\n.subtitle{color:var(--tx2);font-size:11px;letter-spacing:0.06em;text-transform:uppercase;margin-top:4px}\n.brand{display:flex;align-items:center;gap:14px}\n.brand .vemo-logo-wrap{background:#fff;padding:10px 20px;border-radius:8px;display:flex;align-items:center;border:1px solid #e8eaed;box-shadow:0 2px 6px rgba(0,0,0,0.04)}\n.brand .vemo-logo-img{height:26px;width:auto;display:block}\n.iconbtn{width:34px;height:34px;border-radius:999px;border:1px solid var(--b);background:var(--sf);color:var(--tx2);cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center}\nbody.dark-mode .ribbon,body.dark-mode .ribbon-bot{background:var(--teal-deep)}\nbody.dark-mode .brand .vemo-logo-wrap{background:#22282d;border-color:#353c42}\n\n.company-block{background:var(--sf);border:1px solid var(--b);border-radius:14px;padding:22px 24px;margin-bottom:22px}\n.company-head{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;margin-bottom:18px}\n.company-id{display:flex;align-items:center;gap:14px}\n.company-logo{height:46px;max-width:130px;object-fit:contain}\n.company-names .cname{font-size:19px;font-weight:700;color:var(--tx)}\n.company-names .cfull{font-size:12px;color:var(--tx3)}\n.company-link{display:inline-flex;align-items:center;gap:6px;background:var(--forest);color:#fff!important;text-decoration:none;font-size:12.5px;font-weight:600;padding:9px 16px;border-radius:999px;white-space:nowrap;transition:.15s}\n.company-link:hover{opacity:.85}\n\n/* KPI cards — ported from each company\'s OWN live "Executive Summary" KPI13 cards */\n.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:11px;margin-bottom:18px}\n.kpi-card{background:var(--sf);border:1px solid var(--b);border-radius:10px;padding:13px 15px 14px;position:relative;overflow:hidden;display:flex;flex-direction:column}\n.kpi-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--teal)}\n.kpi-card.amber::before{background:var(--amber)}\n.kpi-l{font-size:9.5px;font-weight:700;color:var(--tx3);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px}\n.kpi-v{font-size:22px;font-weight:700;color:var(--forest);margin-bottom:3px;font-variant-numeric:tabular-nums;line-height:1.05}\n.kpi-mom{font-size:10.5px;color:var(--tx2);display:flex;align-items:center;gap:5px;margin-top:3px}\n.kpi-mom .arr{font-size:9px}\n.kpi-bud{font-size:10.5px;color:var(--tx2);margin-top:9px;padding-top:8px;border-top:1px dashed #ececec;display:flex;justify-content:space-between;align-items:center;gap:6px}\n.kpi-bud .lbl{color:var(--tx3);font-size:9.5px;letter-spacing:0.04em;text-transform:uppercase}\n.kpi-bud .v{font-weight:600;font-variant-numeric:tabular-nums}\n.neg{color:var(--red)}\n.pos{color:var(--teal)}\n.kpi-spark{margin-top:10px;height:50px;overflow:hidden}\nbody.dark-mode .kpi-spark svg path[stroke="#11ABAB"]{stroke:#7BDADA!important}\nbody.dark-mode .kpi-spark svg path[stroke="#1F5454"]{stroke:#9aa3ac!important}\nbody.dark-mode .kpi-bud{border-top-color:#353c42}\nbody.dark-mode .kpi-card{background:#22282d;border-color:#353c42}\n.kpi-spark-legend{display:flex;justify-content:center;align-items:center;gap:5px;font-size:9px;color:var(--tx3);margin-top:2px}\n.kpi-spark-legend .sw{display:inline-block;width:11px;height:0;border-top:1.6px solid var(--teal);margin-right:1px}\n.kpi-spark-legend .sw-budget{border-top:1.6px dashed var(--forest);margin-left:8px}\n.kpi-spark-foot{display:flex;justify-content:space-between;font-size:9.5px;color:var(--tx3);margin-top:4px;padding:0 2px}\n\n/* KPI Trend — dropdown chart, one per company */\n.kpi-trend-bar{background:var(--forest);color:#fff;padding:10px 16px;border-radius:10px 10px 0 0;display:flex;align-items:center;gap:14px;flex-wrap:wrap}\n.kpi-trend-bar .ttl{font-weight:700;font-size:13px;letter-spacing:.02em;flex:1 1 0}\n.kpi-trend-bar select{flex:0 1 auto;font:inherit;font-size:11px;padding:5px 10px;border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.1);color:#fff;border-radius:5px;cursor:pointer;font-weight:600;min-width:200px;text-align:center;text-align-last:center}\n.kpi-trend-bar select option{color:#222}\n.kpi-trend-ctrls{flex:1 1 0;display:flex;align-items:center;gap:14px;justify-content:flex-end}\n.kpi-trend-bar label{font-size:11px;display:flex;align-items:center;gap:5px;cursor:pointer;white-space:nowrap}\n.kpi-trend-box{background:var(--sf);border:1px solid var(--b);border-top:none;border-radius:0 0 10px 10px;padding:16px 18px 10px;height:300px;position:relative}\nbody.dark-mode .kpi-trend-box{background:#22282d;border-color:#353c42}\n\n.section-title-row{margin-top:36px}\n.section-title{font-size:18px;font-weight:700;color:var(--forest);margin:0 0 4px}\n.section-note{font-size:12px;color:var(--tx3);margin-bottom:0;max-width:820px}\n\n.recon-wrap{background:var(--sf);border:1px solid var(--b);border-radius:14px;padding:22px 24px 26px;margin-top:16px;overflow-x:auto}\n.foot-note{font-size:11px;color:var(--tx3);margin-top:14px;line-height:1.6}\n.foot-note sup{color:var(--teal)}\n.foot-note ul{margin:4px 0 0 16px;padding:0}\n.foot-note li{margin-bottom:2px}\n\n/* Board Level Main P&L KPIs — bridge/waterfall-style mini charts, one per line */\n.pl-bridge-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:16px}\n@media (max-width:860px){.pl-bridge-grid{grid-template-columns:1fr}}\n.pl-bridge-card{background:var(--sf);border:1px solid var(--b);border-radius:14px;overflow:hidden}\n.pl-bridge-header{background:var(--teal);color:#fff;padding:10px 16px;font-weight:700;font-size:13px;letter-spacing:.02em;text-align:center}\n.pl-bridge-svg{width:100%;height:auto;display:block}\nbody.dark-mode .pl-bridge-card{background:#22282d;border-color:#353c42}\n\n/* vemo-tbl — ported from the source dashboards\' own P&L table format */\n.vemo-tbl{border-collapse:separate;border-spacing:0;width:100%;min-width:980px;font-size:11px;font-variant-numeric:tabular-nums}\n.vemo-tbl th,.vemo-tbl td{padding:7px 10px;text-align:right;background:var(--sf);white-space:nowrap}\n.vemo-tbl thead.grp th{background:var(--teal)!important;color:#fff!important;font-weight:600;font-size:13px;text-align:center;letter-spacing:.02em;padding:11px 10px;border:none;border-right:4px solid #fff!important;border-bottom:4px solid #fff!important}\n.vemo-tbl thead.grp th.firstcol{background:transparent;color:transparent;border:none}\n.vemo-tbl thead.sub th{background:var(--teal)!important;color:#fff!important;font-weight:700;font-size:11px;padding:11px 8px;border-right:2px solid #fff!important;text-align:center;line-height:1.2;letter-spacing:.02em}\n.vemo-tbl thead.sub th.cur{background:var(--mint)!important}\n.vemo-tbl thead.grp th.gend,.vemo-tbl thead.sub th.gend,.vemo-tbl tbody td.gend{border-right:4px solid #fff!important}\n.vemo-tbl thead th.firstcol{background:var(--teal-deep)!important;color:#fff!important;text-align:left;padding-left:16px;font-weight:700;font-size:13px;border-top:0;border-bottom:none}\n.vemo-tbl tbody td{border-bottom:1px solid #ececec;color:var(--tx);background:var(--sf);text-align:center!important}\n.vemo-tbl tbody td.lbl{background:var(--teal-deep)!important;color:#fff!important;font-weight:500;padding-left:16px;text-align:left!important;min-width:210px}\n.vemo-tbl tbody td.cur{background:#e3f4f4!important}\n.vemo-tbl tbody td.italic{font-style:italic;color:#888;font-size:10.5px}\n.vemo-tbl tbody td.lbl.italic{font-style:italic;font-weight:500;color:rgba(255,255,255,.85);font-size:11px;background:var(--teal-deep)}\n.vemo-tbl tbody td.neg{color:var(--red);font-weight:700}\n.vemo-tbl tbody td.pos{color:var(--green);font-weight:700}\n.vemo-tbl tbody tr.subtot td{background:#d4edec!important;font-weight:700;color:var(--forest);font-size:11.5px}\n.vemo-tbl tbody tr.subtot td.lbl{background:var(--teal)!important;color:#fff!important;font-weight:700;font-size:12px}\n.vemo-tbl tbody tr.subtot td.cur{background:#bfe4e3!important}\n.vemo-tbl tbody tr.subtot td.neg{color:var(--red)}\n.vemo-tbl tbody tr.subtot td.pos{color:var(--teal-deep)}\nbody.dark-mode .vemo-tbl{background:#22282d;color:#d4dae0}\nbody.dark-mode .vemo-tbl tbody td{color:#d4dae0!important;background:#22282d}\nbody.dark-mode .vemo-tbl tbody td.cur{background:#2a3137!important}\nbody.dark-mode .vemo-tbl tbody tr.subtot td{background:#2a3137!important;color:var(--mint)!important}\nbody.dark-mode .vemo-tbl tbody tr.subtot td.cur{background:#324047!important}\n\nfooter{text-align:center;font-size:11px;color:var(--tx3);margin-top:40px}\n</style>\n</head>\n<body>\n<div class="ribbon"><span>VEMO Monthly Financial Review</span></div>\n<div class="ribbon-bot"><span>Strictly Private &amp; Confidential</span></div>\n<div class="wrap">\n  <div class="topbar">\n    <div>\n      <div class="title">VEMO — <b>Consolidated Executive Summary</b></div>\n      <div class="subtitle">VCN · LTO · DAE · EV Fleets · Financial &amp; Operational · <span id="data-through-label" style="color:var(--teal);font-weight:700"></span></div>\n    </div>\n    <div class="brand">\n      <div class="vemo-logo-wrap"><img class="vemo-logo-img" src="__LOGO_VEMO__" alt="VEMO"></div>\n      <button class="iconbtn" id="darkToggle" title="Dark mode">🌙</button>\n    </div>\n  </div>\n\n  <div class="section-title-row" style="margin-top:0">\n    <div>\n      <div class="section-title">Board Level Main Operational KPIs</div>\n    </div>\n  </div>\n  <div id="companies"></div>\n\n  <div class="section-title-row">\n    <div>\n      <div class="section-title">Board Level Main P&amp;L KPIs</div>\n    </div>\n  </div>\n  <div class="pl-bridge-grid" id="plBridgeGrid"></div>\n\n  <div class="section-title-row">\n    <div>\n      <div class="section-title">Consolidated Monthly &ndash; P&amp;L Summary (Managerial View)</div>\n    </div>\n  </div>\n  <div class="recon-wrap">\n    <table class="vemo-tbl" id="reconTable"></table>\n    <div class="foot-note" id="reconFootnote"></div>\n  </div>\n\n  <footer>VEMO FP&amp;A · Consolidated_fpa · auto-generated from each company\'s dashboard</footer>\n</div>\n\n<script>\nconst DATA = __DATA_JSON__;\nconst LOGOS = {\n  dae: "__LOGO_DAE__",\n  ev: "__LOGO_EV__",\n  vcn: "__LOGO_VCN__",\n  lto: "__LOGO_LTO__"\n};\n</script>\n</body>\n</html>\n'


# ---------- 5) logica de render (se incrusta inline en index.html) ----------
APP_JS = '/* ===================================================================\n   VEMO — Consolidated Executive Summary — app.js\n   KPI cards, KPI Trend chart and P&L table match the format of the 4\n   individual company dashboards (English throughout).\n   =================================================================== */\n\nlet YTD_START = 0;\nconst charts = {};\n\n/* ---------------- generic formatters ---------------- */\nfunction fmtInt(v){ if(v==null) return \'n.a.\'; return Math.round(v).toLocaleString(\'en-US\'); }\nfunction fmtN(v,d){ if(v==null) return \'n.a.\'; return v.toLocaleString(\'en-US\',{minimumFractionDigits:d,maximumFractionDigits:d}); }\nfunction fmtPct(v,d){ if(v==null) return \'n.a.\'; const s=Math.abs(v).toFixed(d)+\'%\'; return v<0?\'(\'+s+\')\':s; }\nfunction fmtMm(v){ if(v==null) return \'n.a.\'; const m=v/1e6; const s=Math.abs(m).toLocaleString(\'en-US\',{minimumFractionDigits:1,maximumFractionDigits:1}); return m<0?\'(\'+s+\'M)\':s+\'M\'; }\nfunction fmtK(v){ if(v==null) return \'n.a.\'; const k=v/1000; const s=Math.abs(k).toLocaleString(\'en-US\',{minimumFractionDigits:1,maximumFractionDigits:1}); return k<0?\'(\'+s+\'k)\':s+\'k\'; }\nconst MONTHS_EN = [\'Jan\',\'Feb\',\'Mar\',\'Apr\',\'May\',\'Jun\',\'Jul\',\'Aug\',\'Sep\',\'Oct\',\'Nov\',\'Dec\'];\nfunction mlbl(m){\n  if(!m) return \'\';\n  const [y,mo]=m.split(\'-\');\n  return MONTHS_EN[parseInt(mo,10)-1]+\' \'+y.slice(2);\n}\nfunction unitSuffixFor(unit){\n  if(!unit) return \'\';\n  if(unit===\'#\'||unit===\'%\') return \'\';\n  if(/\\$/.test(unit)) return \'\';\n  return unit;\n}\nfunction fmtValCard(v, ki){\n  if(v==null) return \'n.a.\';\n  let s;\n  if(ki.type===\'pct\') return fmtPct(v*100,1);\n  if(ki.type===\'money\'){\n    s = ki.fmt===\'mm\' ? fmtMm(v) : fmtN(v,1);\n    if(/MXN|\\$/.test(ki.unit||\'\')) s=\'$\'+s;\n    return s;\n  }\n  switch(ki.fmt){\n    case \'int\': s=fmtInt(v); break;\n    case \'k\':   s=fmtK(v); break;\n    case \'mm\':  s=fmtMm(v); break;\n    case \'n0\':  s=fmtN(v,0); break;\n    case \'n2\':  s=fmtN(v,2); break;\n    case \'n1\':\n    default:    s=fmtN(v,1);\n  }\n  if(/MXN|\\$/.test(ki.unit||\'\')) s=\'$\'+s;\n  return s;\n}\n/* range-footer formatting: generic magnitude scaling, no currency sign\n   (matches the source dashboards\' KPI13 card footer, e.g. "1.1M - 8.4M"\n   or "1,465 - 2,121") */\nfunction fmtRangeVal(v, isPct){\n  if(v==null || isNaN(v)) return \'\';\n  if(isPct) return (v*100).toFixed(1)+\'%\';\n  const a = Math.abs(v);\n  if(a>=1e9) return (v/1e9).toFixed(1)+\'B\';\n  if(a>=1e6) return (v/1e6).toFixed(1)+\'M\';\n  if(a>=1e3) return Math.round(v).toLocaleString(\'en-US\');\n  return v.toFixed(a<10?2:1);\n}\n\n/* ---------------- sparkline (Actuals solid + Budget dashed) ---------------- */\nfunction sparklineSVG(data, budget, w, h){\n  w = w||180; h = h||44;\n  const budVals = (budget||[]).filter(v=>v!=null && v!==0);\n  const allVals = data.filter(v=>v!=null).concat(budVals);\n  if(allVals.length < 2) return \'\';\n  const min=Math.min(...allVals), max=Math.max(...allVals);\n  const range = (max-min)||1;\n  const n=data.length;\n  const stepX = w/((n-1)||1);\n  function y(v){ return h-2 - ((v-min)/range)*(h-4); }\n\n  const pts=[];\n  data.forEach((v,i)=>{ if(v!=null) pts.push([i*stepX, y(v)]); });\n  if(pts.length<2) return \'\';\n  const linePath = \'M\'+pts.map(p=>p[0].toFixed(1)+\',\'+p[1].toFixed(1)).join(\' L\');\n  const last=pts[pts.length-1], first=pts[0];\n  const areaPath = linePath+` L${last[0].toFixed(1)},${h} L${first[0].toFixed(1)},${h} Z`;\n\n  let budgetPath = \'\';\n  if(budget && budget.length){\n    const bpts=[];\n    budget.forEach((v,i)=>{ if(v!=null && v!==0) bpts.push([i*stepX, y(v)]); });\n    if(bpts.length>=2) budgetPath = \'M\'+bpts.map(p=>p[0].toFixed(1)+\',\'+p[1].toFixed(1)).join(\' L\');\n  }\n\n  return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">\n    <path d="${areaPath}" fill="rgba(123,218,218,0.25)" stroke="none"/>\n    ${budgetPath ? `<path d="${budgetPath}" fill="none" stroke="#1F5454" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.75"/>` : \'\'}\n    <path d="${linePath}" fill="none" stroke="#11ABAB" stroke-width="1.6"/>\n  </svg>`;\n}\n\n/* ---------------- KPI card ---------------- */\nfunction kpiCardHTML(ki, LI){\n  const data = ki.data, spark = ki.spark || ki.data, budget = ki.budget;\n  const cur = data[LI], prev = LI>=1?data[LI-1]:null, yoy = LI>=12?data[LI-12]:null;\n  const mom = (cur!=null && prev!=null && prev!==0) ? (cur-prev)/Math.abs(prev) : null;\n  const bud = budget ? budget[LI] : null;\n  const vsBud = (cur!=null && bud!=null && bud!==0) ? (cur-bud)/Math.abs(bud) : null;\n  const better = ki.better || \'up\';\n  const momGood = mom!=null && ((better===\'up\'&&mom>=0)||(better===\'down\'&&mom<=0));\n  const isAmber = mom!=null && !momGood;\n  const momCls = mom==null ? \'\' : (momGood?\'pos\':\'neg\');\n  const arrow = mom==null ? \'\' : (mom>=0?\'▲\':\'▼\');\n  const budGood = vsBud!=null && ((better===\'up\'&&vsBud>=0)||(better===\'down\'&&vsBud<=0));\n  const budCls = vsBud==null ? \'\' : (budGood?\'pos\':\'neg\');\n  const sparkData = spark.slice(0, LI+1);\n  const sparkBudget = budget ? budget.slice(0, LI+1) : null;\n  // first month with real data (leading zeros were already converted to null\n  // upstream), clamped to the start of the current year -- KPI cards/charts\n  // only show the current year forward, even if the KPI has older history\n  const firstRealIdx = Math.max(0, LI - sparkData.filter(v=>v!=null).length + 1);\n  const startIdx = Math.max(firstRealIdx, YTD_START);\n  const unitSuffix = unitSuffixFor(ki.unit);\n\n  // crop the sparkline itself to the visible range (no blank lead-in for\n  // months without data, and no history before the current year) -- the\n  // SVG\'s x-axis should span only startIdx..LI\n  const sparkDataCropped = sparkData.slice(startIdx);\n  const sparkBudgetCropped = sparkBudget ? sparkBudget.slice(startIdx) : null;\n\n  const rangeVals = sparkDataCropped.filter(v=>v!=null);\n  let rangeTxt = \'\';\n  if(rangeVals.length){\n    const mn = Math.min(...rangeVals), mx = Math.max(...rangeVals);\n    rangeTxt = fmtRangeVal(mn, ki.type===\'pct\') + \' – \' + fmtRangeVal(mx, ki.type===\'pct\');\n  }\n\n  return `<div class="kpi-card${isAmber?\' amber\':\'\'}">\n    <div class="kpi-l">${ki.l}</div>\n    <div class="kpi-v">${fmtValCard(cur,ki)}${unitSuffix?`<span style="font-size:11px;font-weight:600;color:var(--tx3)"> ${unitSuffix}</span>`:\'\'}</div>\n    <div class="kpi-mom">${mom!=null\n        ? `<span class="arr ${momCls}">${arrow}</span><span class="${momCls}">${fmtDevPct(mom)}</span><span style="color:var(--tx3)">vs ${mlbl(DATA.months[prev!=null?LI-1:LI])}</span>`\n        : `<span style="color:var(--tx3)">No prior-month data</span>`}</div>\n    ${budget ? `<div class="kpi-bud"><span><span class="lbl">VS BUDGET</span> ${bud!=null?fmtValCard(bud,ki):\'n.a.\'}</span><span class="v ${budCls}">${bud!=null?fmtDevPct(vsBud):\'n.a.\'}</span></div>` : \'\'}\n    <div class="kpi-spark">${sparklineSVG(sparkDataCropped, sparkBudgetCropped)}</div>\n    <div class="kpi-spark-legend"><span class="sw sw-actual"></span>Actuals${budget?\'<span class="sw sw-budget"></span>Budget\':\'\'}</div>\n    <div class="kpi-spark-foot"><span>${rangeTxt}</span><span>${mlbl(DATA.months[startIdx])} – ${mlbl(DATA.months[LI])}</span></div>\n  </div>`;\n}\n\n/* ---------------- company block ---------------- */\nfunction renderCompanyBlock(ck){\n  const c = DATA.companies[ck];\n  const LI = DATA.last_actual_idx;\n  const cardsHtml = c.kpis.map(ki=>kpiCardHTML(ki,LI)).join(\'\');\n  const optsHtml = c.kpis.map((ki,i)=>`<option value="${i}">${ki.l}</option>`).join(\'\');\n  return `<div class="company-block" id="block-${ck}">\n    <div class="company-head">\n      <div class="company-id">\n        <img class="company-logo" src="${LOGOS[ck]}" alt="${c.name}">\n        <div class="company-names"><div class="cname">${c.name}</div><div class="cfull">${c.full}</div></div>\n      </div>\n      <a class="company-link" href="${c.url}" target="_blank" rel="noopener">Full Dashboard &rarr;</a>\n    </div>\n    <div class="kpi-grid">${cardsHtml}</div>\n    <div class="kpi-trend-bar">\n      <span class="ttl">KPI Trend</span>\n      <select class="kt-picker" data-c="${ck}">${optsHtml}</select>\n      <div class="kpi-trend-ctrls">\n        <label><input type="checkbox" class="kt-bud" data-c="${ck}" checked> Budget</label>\n        <label><input type="checkbox" class="kt-proj" data-c="${ck}"> Run-Rate</label>\n      </div>\n    </div>\n    <div class="kpi-trend-box"><canvas id="chart-${ck}"></canvas></div>\n  </div>`;\n}\n\n/* ---------------- KPI Trend chart (one per company) ---------------- */\nfunction renderTrendChart(ck){\n  const c = DATA.companies[ck];\n  const sel = document.querySelector(`.kt-picker[data-c="${ck}"]`);\n  const showBud = document.querySelector(`.kt-bud[data-c="${ck}"]`).checked;\n  const showProj = document.querySelector(`.kt-proj[data-c="${ck}"]`).checked;\n  const ki = c.kpis[parseInt(sel.value,10)];\n  const LI = DATA.last_actual_idx;\n  const months = DATA.months;\n  let endIdx = Math.min(months.length-1, LI + (showProj?3:0));\n  // crop the x-axis to the range that actually has information for this KPI\n  // -- don\'t show empty months before its first real value, and never show\n  // history before the current year (KPI cards/charts are current-year only;\n  // full history is still kept in the underlying data for the P&L table)\n  let firstRealIdx = 0;\n  for(let i=0;i<=LI;i++){ if(ki.data[i]!=null){ firstRealIdx=i; break; } }\n  let startIdx = Math.max(firstRealIdx, YTD_START);\n  const labels = months.slice(startIdx,endIdx+1).map(mlbl);\n  const mainData = months.slice(startIdx,endIdx+1).map((m,i)=>{ const idx=startIdx+i; return idx<=LI ? ki.data[idx] : null; });\n\n  const datasets = [{\n    label: ki.l, data: mainData,\n    borderColor:\'#11ABAB\', backgroundColor:\'rgba(123,218,218,0.30)\',\n    fill:true, tension:0.32, pointRadius:2.5, pointBackgroundColor:\'#168888\',\n    borderWidth:2, spanGaps:true\n  }];\n\n  if(showBud && ki.budget){\n    const curYear = months[LI].split(\'-\')[0];\n    const budData = months.slice(startIdx,endIdx+1).map((m,i)=>{\n      const idx=startIdx+i;\n      const b = ki.budget[idx];\n      if(b==null || b===0) return null;\n      return m >= curYear+\'-01\' ? b : null;\n    });\n    datasets.push({\n      label: ki.l+\' (Budget)\', data: budData,\n      borderColor:\'#1F5454\', borderDash:[6,4], fill:false,\n      pointRadius:0, borderWidth:1.6, spanGaps:true\n    });\n  }\n\n  if(showProj){\n    const window3 = ki.data.slice(Math.max(0,LI-2), LI+1).filter(v=>v!=null);\n    if(window3.length>=1){\n      const avg = window3.reduce((a,b)=>a+b,0)/window3.length;\n      const projData = months.slice(startIdx,endIdx+1).map((m,i)=>{\n        const idx=startIdx+i;\n        if(idx===LI) return ki.data[LI];\n        if(idx>LI) return avg;\n        return null;\n      });\n      datasets.push({\n        label:\'Run-Rate (3m avg.)\', data: projData,\n        borderColor:\'#7BDADA\', borderDash:[3,3], fill:false,\n        pointRadius:0, borderWidth:1.6, spanGaps:true\n      });\n    }\n  }\n\n  const canvas = document.getElementById(`chart-${ck}`);\n  if(charts[ck]) charts[ck].destroy();\n  charts[ck] = new Chart(canvas, {\n    type:\'line\',\n    data:{labels, datasets},\n    options:{\n      responsive:true, maintainAspectRatio:false,\n      interaction:{mode:\'index\',intersect:false},\n      plugins:{\n        legend:{display: datasets.length>1, position:\'bottom\', labels:{boxWidth:12,font:{size:10}}},\n        tooltip:{callbacks:{label:(ctx)=> `${ctx.dataset.label}: ${fmtValCard(ctx.parsed.y, ki)}`}}\n      },\n      scales:{\n        y:{ ticks:{ callback:(v)=>fmtValCard(v,ki), font:{size:10} }, grid:{color:\'rgba(0,0,0,0.06)\'} },\n        x:{ ticks:{ maxRotation:0, autoSkip:true, font:{size:10} }, grid:{display:false} }\n      }\n    }\n  });\n}\n\nfunction bindCompanyControls(ck){\n  document.querySelector(`.kt-picker[data-c="${ck}"]`).addEventListener(\'change\', ()=>renderTrendChart(ck));\n  document.querySelector(`.kt-bud[data-c="${ck}"]`).addEventListener(\'change\', ()=>renderTrendChart(ck));\n  document.querySelector(`.kt-proj[data-c="${ck}"]`).addEventListener(\'change\', ()=>renderTrendChart(ck));\n}\n\n/* ---------------- P&L Consolidado table ---------------- */\nfunction sumRange(arr,start,end){\n  let s=0, any=false;\n  for(let i=start;i<=end;i++){ if(arr[i]!=null){ s+=arr[i]; any=true; } }\n  return any ? s : null;\n}\nfunction pctDelta(cur,base){\n  if(cur==null||base==null||base===0) return null;\n  return (cur-base)/Math.abs(base);\n}\n/* "not meaningful" guard: a swing off a near-zero base (e.g. EBITDA crossing\n   zero) produces a huge, uninformative percentage -- show "n.m." instead,\n   the standard finance convention. Also n.m. whenever cur/base sit on\n   opposite sides of zero (e.g. actual EBITDA negative vs. a positive\n   Budget) -- a % change across a sign flip isn\'t a meaningful ratio either,\n   regardless of how large or small it computes to. cur/base are optional\n   (existing call sites that don\'t pass them just skip the sign-flip check). */\nfunction fmtDevPct(v, cur, base){\n  if(v==null) return \'—\';\n  if(cur!=null && base!=null && ((cur>0&&base<0)||(cur<0&&base>0))) return \'n.m.\';\n  if(Math.abs(v)>9.99) return \'n.m.\';\n  return fmtPct(v*100,1);\n}\nfunction fmtMoney(v){ return v==null ? \'—\' : fmtMm(v); }\nfunction clsSign(v){ if(v==null) return \'\'; return v>0?\'pos\':(v<0?\'neg\':\'\'); }\n\n/* ---------------- Board Level Main P&L KPIs (bridge-style mini charts) ----------------\n   One card per P&L line (Revenue, Gross Profit, EBITDA, Net Income), each with two\n   independently-scaled bar groups -- period (prev/cur/Budget) and YTD (YTD/Budget YTD)\n   -- plus MoM/vs Budget/vs Budget YTD deviation callouts, using the exact same\n   DATA.consolidated_pl scalars and formulas as the P&L table rows below. */\nconst BRIDGE_COLORS = { period: [\'#9AA0A6\', \'var(--teal-deep)\', \'var(--teal)\'], ytd: [\'var(--mint)\', \'var(--green)\'] };\n\nfunction fmtBridgeVal(v){\n  if(v==null) return \'—\';\n  const m = v/1e6;\n  return (m<0?\'-$\':\'$\') + Math.abs(m).toFixed(1);\n}\n\nfunction plBridgeChart(title, s, marginKey){\n  if(!s) return \'\';\n  const LI = DATA.last_actual_idx;\n  const mPrev = mlbl(DATA.months[LI-1]), mCur = mlbl(DATA.months[LI]);\n  const periodVals = [s.prev, s.cur, s.bud_cur];\n  const ytdVals = [s.ytd, s.bud_ytd];\n  const orientUp = (s.cur!=null ? s.cur : 0) >= 0;\n\n  const maxPos = arr => Math.max(0, ...arr.filter(v=>v!=null && v>0));\n  const maxNeg = arr => Math.max(0, ...arr.filter(v=>v!=null && v<0).map(v=>-v));\n  const BASE = 108, UPH = 63, DOWNH = 63;\n  const pUp = maxPos(periodVals), pDn = maxNeg(periodVals);\n  const yUp = maxPos(ytdVals), yDn = maxNeg(ytdVals);\n  const pScaleUp = pUp>0 ? UPH/pUp : 0, pScaleDn = pDn>0 ? DOWNH/pDn : 0;\n  const yScaleUp = yUp>0 ? UPH/yUp : 0, yScaleDn = yDn>0 ? DOWNH/yDn : 0;\n\n  function bar(v, scaleUp, scaleDn){\n    if(v==null) return null;\n    if(v>=0){ const h=v*scaleUp; return {y:BASE-h, h}; }\n    const h=-v*scaleDn; return {y:BASE, h};\n  }\n  const pC = [90,170,250], pW=46;\n  const yC = [390,470], yW=46;\n  const dividerX = 320;\n\n  const pR = periodVals.map(v=>bar(v, pScaleUp, pScaleDn));\n  const yR = ytdVals.map(v=>bar(v, yScaleUp, yScaleDn));\n\n  function rectSVG(cx, w, r, color){\n    if(!r || r.h<0.5) return \'\';\n    return `<rect x="${(cx-w/2).toFixed(1)}" y="${r.y.toFixed(1)}" width="${w}" height="${Math.max(r.h,1.5).toFixed(1)}" rx="3" fill="${color}"/>`;\n  }\n  let bars = \'\';\n  periodVals.forEach((v,i)=>{ bars += rectSVG(pC[i], pW, pR[i], BRIDGE_COLORS.period[i]); });\n  ytdVals.forEach((v,i)=>{ bars += rectSVG(yC[i], yW, yR[i], BRIDGE_COLORS.ytd[i]); });\n\n  const VALY = 208, CATY = 226;\n  const cols = [\n    {x:pC[0], v:periodVals[0], cat:mPrev},\n    {x:pC[1], v:periodVals[1], cat:mCur},\n    {x:pC[2], v:periodVals[2], cat:\'Budget\'},\n    {x:yC[0], v:ytdVals[0], cat:\'YTD\'},\n    {x:yC[1], v:ytdVals[1], cat:\'Budget YTD\'},\n  ];\n  let labels = \'\';\n  cols.forEach(c=>{\n    labels += `<text x="${c.x}" y="${VALY}" text-anchor="middle" font-size="13" font-weight="700" fill="var(--forest)">${fmtBridgeVal(c.v)}</text>`;\n    labels += `<text x="${c.x}" y="${CATY}" text-anchor="middle" font-size="10" fill="var(--tx3)">${c.cat}</text>`;\n  });\n\n  const topZoneY = 22, botZoneY = 172;\n  const zoneY = orientUp ? topZoneY : botZoneY;\n  function callout(x, curVal, baseVal){\n    const dv = pctDelta(curVal, baseVal);\n    if(dv==null) return \'\';\n    const txt = fmtDevPct(dv, curVal, baseVal);\n    const color = dv>0 ? \'var(--green)\' : (dv<0 ? \'var(--red)\' : \'var(--tx3)\');\n    const boxW = 58, boxH = 18;\n    let arrow;\n    if(orientUp){\n      arrow = `<line x1="${x}" y1="${zoneY+boxH}" x2="${x}" y2="${zoneY+boxH+9}" stroke="#9aa3ac" stroke-width="1" stroke-dasharray="2,2"/>\n        <polygon points="${x-3},${zoneY+boxH+9} ${x+3},${zoneY+boxH+9} ${x},${zoneY+boxH+14}" fill="#9aa3ac"/>`;\n    } else {\n      arrow = `<line x1="${x}" y1="${zoneY-9}" x2="${x}" y2="${zoneY}" stroke="#9aa3ac" stroke-width="1" stroke-dasharray="2,2"/>\n        <polygon points="${x-3},${zoneY-9} ${x+3},${zoneY-9} ${x},${zoneY-14}" fill="#9aa3ac"/>`;\n    }\n    return `<rect x="${x-boxW/2}" y="${zoneY}" width="${boxW}" height="${boxH}" rx="4" fill="var(--sf)" stroke="#c7cdd3"/>\n      <text x="${x}" y="${zoneY+13}" text-anchor="middle" font-size="11" font-weight="700" fill="${color}">${txt}</text>\n      ${arrow}`;\n  }\n  let callouts = \'\';\n  callouts += callout((pC[0]+pC[1])/2, periodVals[1], periodVals[0]);\n  callouts += callout((pC[1]+pC[2])/2, periodVals[1], periodVals[2]);\n  callouts += callout((yC[0]+yC[1])/2, ytdVals[0], ytdVals[1]);\n\n  let marginRow = \'\';\n  if(marginKey && DATA.consolidated_pl[marginKey]){\n    const ms = DATA.consolidated_pl[marginKey];\n    const mvals = [ms.prev, ms.cur, ms.bud_cur, ms.ytd, ms.bud_ytd];\n    cols.forEach((c,i)=>{\n      marginRow += `<text x="${c.x}" y="14" text-anchor="middle" font-size="10" font-weight="700" fill="var(--tx3)">${fmtPct(mvals[i],1)}</text>`;\n    });\n  }\n\n  const baselineLine = `<line x1="20" y1="${BASE}" x2="600" y2="${BASE}" stroke="#d8dce0" stroke-width="1"/>`;\n  const divider = `<line x1="${dividerX}" y1="20" x2="${dividerX}" y2="196" stroke="#c7cdd3" stroke-width="1" stroke-dasharray="3,3"/>`;\n\n  return `<div class="pl-bridge-card">\n    <div class="pl-bridge-header">${title}</div>\n    <svg class="pl-bridge-svg" viewBox="0 0 620 235" xmlns="http://www.w3.org/2000/svg">\n      ${marginRow}${baselineLine}${divider}${bars}${labels}${callouts}\n    </svg>\n  </div>`;\n}\n\nfunction renderPlBridgeGrid(){\n  const el = document.getElementById(\'plBridgeGrid\');\n  if(!el) return;\n  const cp = DATA.consolidated_pl;\n  el.innerHTML =\n    plBridgeChart(\'Revenues (MXNm)\', cp.revenue, null) +\n    plBridgeChart(\'Normalized¹ Gross Profit (MXNm)\', cp.gross_profit, \'gross_margin\') +\n    plBridgeChart(\'Normalized¹ EBITDA (MXNm)\', cp.ebitda, \'ebitda_margin\') +\n    plBridgeChart(\'Normalized¹ Net Income (MXNm)\', cp.net_income, null);\n}\n\nfunction plHeaderRows(){\n  const LI = DATA.last_actual_idx;\n  const mYoY = mlbl(DATA.months[LI-12]), mPrev = mlbl(DATA.months[LI-1]), mCur = mlbl(DATA.months[LI]);\n  return `<thead class="grp"><tr>\n    <th class="firstcol"></th>\n    <th colspan="4">Actuals</th>\n    <th colspan="2">Budget</th>\n    <th colspan="4">Deviation ($)</th>\n    <th colspan="4">Deviation (%)</th>\n  </tr></thead>\n  <thead class="sub"><tr>\n    <th class="firstcol"></th>\n    <th>${mYoY}</th><th>${mPrev}</th><th class="cur">${mCur}</th><th class="cur gend">YTD</th>\n    <th class="cur">${mCur}</th><th class="cur gend">YTD</th>\n    <th>vs ${mPrev}</th><th>vs Budget</th><th>vs ${mYoY}</th><th class="gend">vs Budget YTD</th>\n    <th>vs ${mPrev}</th><th>vs Budget</th><th>vs ${mYoY}</th><th class="gend">vs Budget YTD</th>\n  </tr></thead>`;\n}\n\nfunction rowLineInner(label, key, trClass){\n  // DATA.consolidated_pl[key] is a precomputed scalar snapshot -- either read\n  // straight from the official "Board Outputs" presented block, or reduced\n  // to the same shape from the summed-4-companies fallback in build.py.\n  const s = DATA.consolidated_pl[key];\n  const yoy = s.yoy, prev = s.prev, cur = s.cur, ytd = s.ytd;\n  const budCur = s.bud_cur, budYtd = s.bud_ytd;\n\n  const devMomD = (cur!=null&&prev!=null)?cur-prev:null;\n  const devBudD = (cur!=null&&budCur!=null)?cur-budCur:null;\n  const devYoyD = (cur!=null&&yoy!=null)?cur-yoy:null;\n  const devYtdD = (ytd!=null&&budYtd!=null)?ytd-budYtd:null;\n  const devMomP = pctDelta(cur,prev), devBudP = pctDelta(cur,budCur), devYoyP = pctDelta(cur,yoy), devYtdP = pctDelta(ytd,budYtd);\n\n  const trc = trClass ? ` class="${trClass}"` : \'\';\n  return `<tr${trc}>\n    <td class="lbl">${label}</td>\n    <td>${fmtMoney(yoy)}</td><td>${fmtMoney(prev)}</td><td class="cur">${fmtMoney(cur)}</td><td class="cur gend">${fmtMoney(ytd)}</td>\n    <td class="cur">${fmtMoney(budCur)}</td><td class="cur gend">${fmtMoney(budYtd)}</td>\n    <td class="${clsSign(devMomD)}">${fmtMoney(devMomD)}</td><td class="${clsSign(devBudD)}">${fmtMoney(devBudD)}</td><td class="${clsSign(devYoyD)}">${fmtMoney(devYoyD)}</td><td class="gend ${clsSign(devYtdD)}">${fmtMoney(devYtdD)}</td>\n    <td class="${clsSign(devMomP)}">${fmtDevPct(devMomP,cur,prev)}</td><td class="${clsSign(devBudP)}">${fmtDevPct(devBudP,cur,budCur)}</td><td class="${clsSign(devYoyP)}">${fmtDevPct(devYoyP,cur,yoy)}</td><td class="gend ${clsSign(devYtdP)}">${fmtDevPct(devYtdP,ytd,budYtd)}</td>\n  </tr>`;\n}\nfunction rowLine(label,key){ return rowLineInner(label,key,\'\'); }\nfunction rowSubtot(label,key){ return rowLineInner(label,key,\'subtot\'); }\n\nfunction rowMargin(label, marginKey){\n  // Margins are precomputed percentage-point scalars -- either read directly\n  // from the official Board Outputs block, or computed the same way (num/den\n  // at each of the 6 snapshot points, never by dividing summed percentages)\n  // in the summed-4-companies fallback in build.py.\n  const s = DATA.consolidated_pl[marginKey];\n  const yoy = s.yoy, prev = s.prev, cur = s.cur, ytd = s.ytd, budCur = s.bud_cur, budYtd = s.bud_ytd;\n  const fp=(v)=> v==null ? \'—\' : v.toFixed(1)+\'%\';\n  return `<tr>\n    <td class="lbl italic">${label}</td>\n    <td class="italic">${fp(yoy)}</td><td class="italic">${fp(prev)}</td><td class="cur italic">${fp(cur)}</td><td class="cur gend italic">${fp(ytd)}</td>\n    <td class="cur italic">${fp(budCur)}</td><td class="cur gend italic">${fp(budYtd)}</td>\n    <td class="italic"></td><td class="italic"></td><td class="italic"></td><td class="gend italic"></td>\n    <td class="italic"></td><td class="italic"></td><td class="italic"></td><td class="gend italic"></td>\n  </tr>`;\n}\n\nfunction renderReconTable(){\n  const table = document.getElementById(\'reconTable\');\n  const rows = [\n    rowLine(\'Revenues (net of interco)\',\'revenue\'),\n    rowLine(\'COGS + Opex\',\'opex\'),\n    rowSubtot(\'Normalized Gross Profit\',\'gross_profit\'),\n    rowMargin(\'Gross Margin\',\'gross_margin\'),\n    rowLine(\'SG&amp;A\',\'sga_total\'),\n    rowSubtot(\'Normalized EBITDA\',\'ebitda\'),\n    rowMargin(\'EBITDA Margin\',\'ebitda_margin\'),\n    rowLine(\'D&amp;A\',\'da\'),\n    rowSubtot(\'EBIT\',\'ebit\'),\n    rowLine(\'Net Interest\',\'interest_expense\'),\n    rowSubtot(\'EBT\',\'ebt\'),\n    rowLine(\'Taxes\',\'taxes\'),\n    rowSubtot(\'Normalized Net Income\',\'net_income\'),\n    rowMargin(\'Net Margin\',\'net_margin\'),\n  ].join(\'\');\n  table.innerHTML = plHeaderRows() + \'<tbody>\' + rows + \'</tbody>\';\n  document.getElementById(\'reconFootnote\').innerHTML =\n    `<b>P&amp;L Managerial Notes:</b> For comparability purposes vs. Budget:` +\n    `<ul style="margin:4px 0 0 16px;padding:0">` +\n    `<li>Certain Revenue, OPEX and SG&amp;A accounts are reclassified vs. accounting figures.</li>` +\n    `<li>For 2026, VCN&rsquo;s results are normalized for the IFRS 16 treatment of hub lease rent. Specifically, we present actual rent expense within OPEX (i.e., not within Depreciation and Interest). This normalization is applied only to hubs whose contractual grace periods have ended, as opposed to the accounting treatment, which recognizes IFRS 16 impacts for hubs already signed even if they are still within the grace period.</li>` +\n    `<li>Excludes FX gain / (loss).</li>` +\n    `</ul>`;\n}\n\n/* ---------------- init ---------------- */\nfunction computeYtdStart(){\n  const curYear = DATA.months[DATA.last_actual_idx].split(\'-\')[0];\n  const idx = DATA.months.findIndex(m=>m===curYear+\'-01\');\n  return idx>=0 ? idx : 0;\n}\n\ndocument.addEventListener(\'DOMContentLoaded\', ()=>{\n  YTD_START = computeYtdStart();\n  document.getElementById(\'data-through-label\').textContent =\n    `📅 Data through ${DATA.generated_month_label}`;\n\n  document.getElementById(\'companies\').innerHTML =\n    Object.keys(DATA.companies).map(renderCompanyBlock).join(\'\');\n\n  Object.keys(DATA.companies).forEach(ck=>{\n    bindCompanyControls(ck);\n    renderTrendChart(ck);\n  });\n\n  renderPlBridgeGrid();\n  renderReconTable();\n\n  const darkToggle = document.getElementById(\'darkToggle\');\n  let dark = false;\n  try{ dark = localStorage.getItem(\'vemo-consolidated-dark\')===\'1\'; }catch(e){}\n  if(dark){ document.body.classList.add(\'dark-mode\'); darkToggle.textContent=\'☀️\'; }\n  darkToggle.addEventListener(\'click\', ()=>{\n    document.body.classList.toggle(\'dark-mode\');\n    const isDark = document.body.classList.contains(\'dark-mode\');\n    darkToggle.textContent = isDark ? \'☀️\' : \'🌙\';\n    try{ localStorage.setItem(\'vemo-consolidated-dark\', isDark?\'1\':\'0\'); }catch(e){}\n    Object.keys(DATA.companies).forEach(ck=>renderTrendChart(ck));\n  });\n});\n'


# ---------- 6) armar index.html (un solo archivo autocontenido) ----------
def build_index_html(data):
    logos_b64 = {}
    for name in ['dae', 'ev', 'vcn', 'lto', 'vemo']:
        path = os.path.join(HERE, 'logos', f'{name}.png')
        with open(path, 'rb') as f:
            logos_b64[name] = base64.b64encode(f.read()).decode()

    tpl = HTML_TEMPLATE
    tpl = tpl.replace('__GENERATED_MONTH_LABEL__', data['generated_month_label'])
    tpl = tpl.replace('__DATA_JSON__', json.dumps(data, ensure_ascii=False))
    for name in ['dae', 'ev', 'vcn', 'lto', 'vemo']:
        tpl = tpl.replace(f'__LOGO_{name.upper()}__', f"data:image/png;base64,{logos_b64[name]}")
    tpl = tpl.replace('</script>\n</body>', f'\n{APP_JS}\n</script>\n</body>')

    with open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(tpl)
    print('index.html regenerado (un solo archivo autocontenido):', len(tpl), 'bytes')


if __name__ == '__main__':
    data = build_consolidated_data()
    build_index_html(data)
