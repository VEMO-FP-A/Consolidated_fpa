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
        {'l': 'Repossessions (% Total Fleet)', 'keys': ['vrpm_repo_pct'], 'unit': '%', 'type': 'pct', 'better': 'down'},
        {'l': 'Used Vehicle Inventory', 'keys': ['vrpm_uvi_total'], 'unit': '#', 'type': 'num', 'fmt': 'int', 'better': 'down'},
        {'l': 'Used Vehicle Inventory (% Total Fleet)', 'keys': ['vrpm_uvi_pct'], 'unit': '%', 'type': 'pct', 'better': 'down'},
        {'l': 'Portfolio Default Rate', 'keys': ['vrpm_default_rate'], 'unit': '%', 'type': 'pct', 'better': 'down'},
    ],
}


COMPANIES_META = {
    'vcn': {'name': 'VCN', 'full': 'VEMO Charging Network', 'url': 'https://vemo-fp-a.github.io/VCN_BoardD/', 'file': 'VCN_BoardD'},
    'lto': {'name': 'VEMO Impulso', 'full': 'Lease-to-Own', 'url': 'https://vemo-fp-a.github.io/LTO_BoardD/', 'file': 'LTO_BoardD'},
    'dae': {'name': 'DAE', 'full': 'Driver as Employee', 'url': 'https://vemo-fp-a.github.io/DAE_BoardD/', 'file': 'DAE_BoardD'},
    'ev':  {'name': 'EV Fleets', 'full': 'Electric Vehicle Fleets', 'url': 'https://vemo-fp-a.github.io/EV_BoardD/', 'file': 'EV_BoardD'},
}

MONTHS_EN = ['January','February','March','April','May','June','July','August',
             'September','October','November','December']

PL_FIELDS = ['revenue', 'opex', 'gross_profit', 'sga_total', 'ebitda', 'da',
             'ebit', 'interest_expense', 'ebt', 'taxes', 'net_income']

# The official, accounting-approved Consolidated P&L (with real intercompany
# eliminations) lives in this workbook on the user's OneDrive, sheet
# "Board Outputs", "Normalized" P&L block (Revenues -> Net income (Normalized)).
# It has no Budget columns, so Budget stays sourced from the sum of each
# company's own budget_ fields (see pl_lines() above).
BOARD_XLSX_CANDIDATES = [
    os.path.join(ROOT, '..', '..', 'VEMO 2026 Consolidated Financials FV.xlsx'),
]


def extract_consolidated_pl_from_board_xlsx(path, months, lai):
    """Reads the real Consolidated P&L (actuals only) from the 'Board Outputs'
    sheet of the official consolidated financials workbook. Locates rows
    dynamically by label text (robust to rows shifting when the sheet is
    edited month to month) instead of hardcoded row numbers. Returns None
    (caller falls back to summing the 4 dashboards) if the file/sheet/labels
    aren't found -- e.g. running outside the user's OneDrive-synced machine."""
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

        col_for_month = {}
        for c in range(1, min(ws.max_column, 60) + 1):
            v = ws.cell(row=6, column=c).value
            if hasattr(v, 'strftime'):
                col_for_month[v.strftime('%Y-%m')] = c

        def find_label(target, r0, r1):
            for r in range(r0, r1 + 1):
                v = ws.cell(row=r, column=2).value
                if v is not None and str(v).strip() == target:
                    return r
            return None

        scan_limit = min(ws.max_row, 500)
        candidates = []
        for r in range(1, scan_limit + 1):
            v = ws.cell(row=r, column=2).value
            if v is not None and str(v).strip() == 'Normalized EBITDA':
                candidates.append(r)
        ebitda_row = None
        for cand in candidates:
            if find_label('Net income (Normalized)', cand + 1, cand + 15):
                ebitda_row = cand
                break
        if ebitda_row is None:
            return None

        pre_lo, pre_hi = max(1, ebitda_row - 25), ebitda_row - 1
        post_lo, post_hi = ebitda_row + 1, ebitda_row + 15
        rows = {
            'revenue': find_label('Revenues', pre_lo, pre_hi),
            'opex': find_label('OPEX', pre_lo, pre_hi),
            'gross_profit': find_label('Gross profit', pre_lo, pre_hi),
            'sga_total': find_label('Total SG&A', pre_lo, pre_hi),
            'da': find_label('D&A', post_lo, post_hi),
            'ebit': find_label('EBIT', post_lo, post_hi),
            'interest_expense': find_label('Interest Expense', post_lo, post_hi),
            'ebt': find_label('EBT', post_lo, post_hi),
            'taxes': find_label('Income taxes', post_lo, post_hi),
            'net_income': find_label('Net income (Normalized)', post_lo, post_hi),
        }
        rows['ebitda'] = ebitda_row
        if any(v is None for v in rows.values()):
            print('Board Outputs: no se pudieron ubicar todas las filas del P&L Normalized -- usando fallback.')
            return None

        n = len(months)
        out = {}
        for key, r in rows.items():
            vals = []
            for m in months:
                c = col_for_month.get(m)
                v = ws.cell(row=r, column=c).value if c else None
                vals.append(round(v, 2) if isinstance(v, (int, float)) else None)
            out[key] = vals
        for key in out:
            for i in range(lai + 1, n):
                if out[key][i] == 0:
                    out[key][i] = None
        return out
    except Exception as e:
        print('Error leyendo el Consolidated P&L oficial (usando fallback):', e)
        return None


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
        kpis = [resolve_kpi(d, ki, n) for ki in KPI_DEFS[ck]]
        companies[ck] = {
            'name': meta['name'], 'full': meta['full'], 'url': meta['url'],
            'kpis': kpis,
        }

    all_lines = {ck: pl_lines(d, ck, n) for ck, d in dsets.items()}
    # Budget: always the sum of each company's own budget_ fields (no official
    # consolidated budget source was found).
    budgets = {}
    for f in PL_FIELDS:
        tot_b = [None] * n
        for ck in dsets:
            _, b = all_lines[ck][f]
            for i in range(n):
                if b[i] is not None:
                    tot_b[i] = (tot_b[i] or 0) + b[i]
        budgets[f] = [round(x, 2) if x is not None else None for x in tot_b]

    # Actuals: prefer the official Consolidated P&L (with real eliminations) from
    # the Board Outputs workbook; fall back to summing the 4 dashboards' own
    # lines (no eliminations) if that workbook isn't reachable.
    board_actuals = None
    for xlsx_path in BOARD_XLSX_CANDIDATES:
        board_actuals = extract_consolidated_pl_from_board_xlsx(xlsx_path, months, lai)
        if board_actuals is not None:
            break

    consolidated_pl_source = 'board_xlsx' if board_actuals is not None else 'summed_fallback'
    consolidated_pl = {}
    for f in PL_FIELDS:
        if board_actuals is not None:
            actual = board_actuals[f]
        else:
            tot_a = [None] * n
            for ck in dsets:
                a, _ = all_lines[ck][f]
                for i in range(n):
                    if a[i] is not None:
                        tot_a[i] = (tot_a[i] or 0) + a[i]
            actual = [round(x, 2) if x is not None else None for x in tot_a]
        consolidated_pl[f] = {'actual': actual, 'budget': budgets[f]}

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
    with open(os.path.join(ROOT, 'consolidated_data.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('consolidated_data.json listo. mes mas reciente:', data['generated_month'])
    return data



# ---------- 4) plantilla HTML (con placeholders __X__) ----------
HTML_TEMPLATE = '<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>VEMO — Consolidated Executive Summary</title>\n<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">\n<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n<style>\n:root{\n  --forest:#1F5454;--teal:#11ABAB;--teal-deep:#168888;--mint:#7BDADA;\n  --red:#C0392B;--green:#117A45;--amber:#E59500;--bg:#f5f6f7;--sf:#fff;--b:#e8eaed;\n  --tx:#222;--tx2:#555;--tx3:#888;--rs:6px;--r:10px;\n}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:\'Space Grotesk\',sans-serif;background:var(--bg);color:var(--tx);line-height:1.4}\nbody.dark-mode{--bg:#1a1f23;--sf:#22282d;--b:#353c42;--tx:#e6ebee;--tx2:#d4dae0;--tx3:#9aa3ac;--forest:#7BDADA;color:#e6ebee!important}\nbody.dark-mode *{color:inherit}\n.wrap{max-width:1400px;margin:0 auto;padding:28px 24px 60px}\n.topbar{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:28px}\n.title{font-size:28px;font-weight:700;color:var(--forest)}\n.subtitle{font-size:13px;color:var(--tx2);margin-top:4px}\n.iconbtn{width:34px;height:34px;border-radius:999px;border:1px solid var(--b);background:var(--sf);color:var(--tx2);cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center}\n\n.company-block{background:var(--sf);border:1px solid var(--b);border-radius:14px;padding:22px 24px;margin-bottom:22px}\n.company-head{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;margin-bottom:18px}\n.company-id{display:flex;align-items:center;gap:14px}\n.company-logo{height:46px;max-width:130px;object-fit:contain}\n.company-names .cname{font-size:19px;font-weight:700;color:var(--tx)}\n.company-names .cfull{font-size:12px;color:var(--tx3)}\n.company-link{display:inline-flex;align-items:center;gap:6px;background:var(--forest);color:#fff!important;text-decoration:none;font-size:12.5px;font-weight:600;padding:9px 16px;border-radius:999px;white-space:nowrap;transition:.15s}\n.company-link:hover{opacity:.85}\n\n/* KPI cards — ported from each company\'s OWN live "Executive Summary" KPI13 cards */\n.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:11px;margin-bottom:18px}\n.kpi-card{background:var(--sf);border:1px solid var(--b);border-radius:10px;padding:13px 15px 14px;position:relative;overflow:hidden;display:flex;flex-direction:column}\n.kpi-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--teal)}\n.kpi-card.amber::before{background:var(--amber)}\n.kpi-l{font-size:9.5px;font-weight:700;color:var(--tx3);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px}\n.kpi-v{font-size:22px;font-weight:700;color:var(--forest);margin-bottom:3px;font-variant-numeric:tabular-nums;line-height:1.05}\n.kpi-mom{font-size:10.5px;color:var(--tx2);display:flex;align-items:center;gap:5px;margin-top:3px}\n.kpi-mom .arr{font-size:9px}\n.kpi-bud{font-size:10.5px;color:var(--tx2);margin-top:9px;padding-top:8px;border-top:1px dashed #ececec;display:flex;justify-content:space-between;align-items:center;gap:6px}\n.kpi-bud .lbl{color:var(--tx3);font-size:9.5px;letter-spacing:0.04em;text-transform:uppercase}\n.kpi-bud .v{font-weight:600;font-variant-numeric:tabular-nums}\n.neg{color:var(--red)}\n.pos{color:var(--teal)}\n.kpi-spark{margin-top:10px;height:50px;overflow:hidden}\nbody.dark-mode .kpi-spark svg path[stroke="#11ABAB"]{stroke:#7BDADA!important}\nbody.dark-mode .kpi-spark svg path[stroke="#1F5454"]{stroke:#9aa3ac!important}\nbody.dark-mode .kpi-bud{border-top-color:#353c42}\nbody.dark-mode .kpi-card{background:#22282d;border-color:#353c42}\n.kpi-spark-legend{display:flex;justify-content:center;align-items:center;gap:5px;font-size:9px;color:var(--tx3);margin-top:2px}\n.kpi-spark-legend .sw{display:inline-block;width:11px;height:0;border-top:1.6px solid var(--teal);margin-right:1px}\n.kpi-spark-legend .sw-budget{border-top:1.6px dashed var(--forest);margin-left:8px}\n.kpi-spark-foot{display:flex;justify-content:space-between;font-size:9.5px;color:var(--tx3);margin-top:4px;padding:0 2px}\n\n/* KPI Trend — dropdown chart, one per company */\n.kpi-trend-bar{background:var(--forest);color:#fff;padding:10px 16px;border-radius:10px 10px 0 0;display:flex;align-items:center;gap:14px;flex-wrap:wrap}\n.kpi-trend-bar .ttl{font-weight:700;font-size:13px;letter-spacing:.02em}\n.kpi-trend-bar select{margin-left:auto;font:inherit;font-size:11px;padding:5px 10px;border:1px solid rgba(255,255,255,.3);background:rgba(255,255,255,.1);color:#fff;border-radius:5px;cursor:pointer;font-weight:600}\n.kpi-trend-bar select option{color:#222}\n.kpi-trend-bar label{font-size:11px;display:flex;align-items:center;gap:5px;cursor:pointer;white-space:nowrap}\n.kpi-trend-box{background:var(--sf);border:1px solid var(--b);border-top:none;border-radius:0 0 10px 10px;padding:16px 18px 10px;height:300px;position:relative}\nbody.dark-mode .kpi-trend-box{background:#22282d;border-color:#353c42}\n\n.section-title-row{margin-top:36px}\n.section-title{font-size:18px;font-weight:700;color:var(--forest);margin:0 0 4px}\n.section-note{font-size:12px;color:var(--tx3);margin-bottom:0;max-width:820px}\n\n.recon-wrap{background:var(--sf);border:1px solid var(--b);border-radius:14px;padding:22px 24px 26px;margin-top:16px;overflow-x:auto}\n.foot-note{font-size:11px;color:var(--tx3);margin-top:14px;line-height:1.6}\n.foot-note sup{color:var(--teal)}\n\n/* vemo-tbl — ported from the source dashboards\' own P&L table format */\n.vemo-tbl{border-collapse:separate;border-spacing:0;width:100%;min-width:980px;font-size:11px;font-variant-numeric:tabular-nums}\n.vemo-tbl th,.vemo-tbl td{padding:7px 10px;text-align:right;background:var(--sf);white-space:nowrap}\n.vemo-tbl thead.grp th{background:var(--teal)!important;color:#fff!important;font-weight:600;font-size:13px;text-align:center;letter-spacing:.02em;padding:11px 10px;border:none;border-right:4px solid #fff!important;border-bottom:4px solid #fff!important}\n.vemo-tbl thead.grp th.firstcol{background:transparent;color:transparent;border:none}\n.vemo-tbl thead.sub th{background:var(--teal)!important;color:#fff!important;font-weight:700;font-size:11px;padding:11px 8px;border-right:2px solid #fff!important;text-align:center;line-height:1.2;letter-spacing:.02em}\n.vemo-tbl thead.sub th.cur{background:var(--mint)!important}\n.vemo-tbl thead.grp th.gend,.vemo-tbl thead.sub th.gend,.vemo-tbl tbody td.gend{border-right:4px solid #fff!important}\n.vemo-tbl thead th.firstcol{background:var(--teal-deep)!important;color:#fff!important;text-align:left;padding-left:16px;font-weight:700;font-size:13px;border-top:0;border-bottom:none}\n.vemo-tbl tbody td{border-bottom:1px solid #ececec;color:var(--tx);background:var(--sf);text-align:center!important}\n.vemo-tbl tbody td.lbl{background:var(--teal-deep)!important;color:#fff!important;font-weight:500;padding-left:16px;text-align:left!important;min-width:210px}\n.vemo-tbl tbody td.cur{background:#e3f4f4!important}\n.vemo-tbl tbody td.italic{font-style:italic;color:#888;font-size:10.5px}\n.vemo-tbl tbody td.lbl.italic{font-style:italic;font-weight:500;color:rgba(255,255,255,.85);font-size:11px;background:var(--teal-deep)}\n.vemo-tbl tbody td.neg{color:var(--red);font-weight:700}\n.vemo-tbl tbody td.pos{color:var(--green);font-weight:700}\n.vemo-tbl tbody tr.subtot td{background:#d4edec!important;font-weight:700;color:var(--forest);font-size:11.5px}\n.vemo-tbl tbody tr.subtot td.lbl{background:var(--teal)!important;color:#fff!important;font-weight:700;font-size:12px}\n.vemo-tbl tbody tr.subtot td.cur{background:#bfe4e3!important}\n.vemo-tbl tbody tr.subtot td.neg{color:var(--red)}\n.vemo-tbl tbody tr.subtot td.pos{color:var(--teal-deep)}\nbody.dark-mode .vemo-tbl{background:#22282d;color:#d4dae0}\nbody.dark-mode .vemo-tbl tbody td{color:#d4dae0!important;background:#22282d}\nbody.dark-mode .vemo-tbl tbody td.cur{background:#2a3137!important}\nbody.dark-mode .vemo-tbl tbody tr.subtot td{background:#2a3137!important;color:var(--mint)!important}\nbody.dark-mode .vemo-tbl tbody tr.subtot td.cur{background:#324047!important}\n\nfooter{text-align:center;font-size:11px;color:var(--tx3);margin-top:40px}\n</style>\n</head>\n<body>\n<div class="wrap">\n  <div class="topbar">\n    <div>\n      <div class="title">VEMO — Consolidated Executive Summary</div>\n      <div class="subtitle" id="subtitleText">DAE · VEMO Impulso · EV Fleets · VCN — updated through __GENERATED_MONTH_LABEL__</div>\n    </div>\n    <div class="topctrls">\n      <button class="iconbtn" id="darkToggle" title="Dark mode">🌙</button>\n    </div>\n  </div>\n\n  <div id="companies"></div>\n\n  <div class="section-title-row">\n    <div>\n      <div class="section-title">Consolidated P&amp;L</div>\n      <div class="section-note">Combined total of VEMO\'s 4 businesses (DAE, VEMO Impulso, EV Fleets, VCN), in the same P&amp;L format used by each individual dashboard.</div>\n    </div>\n  </div>\n  <div class="recon-wrap">\n    <table class="vemo-tbl" id="reconTable"></table>\n    <div class="foot-note" id="reconFootnote"></div>\n  </div>\n\n  <footer>VEMO FP&amp;A · Consolidated_fpa · auto-generated from each company\'s dashboard</footer>\n</div>\n\n<script>\nconst DATA = __DATA_JSON__;\nconst LOGOS = {\n  dae: "__LOGO_DAE__",\n  ev: "__LOGO_EV__",\n  vcn: "__LOGO_VCN__",\n  lto: "__LOGO_LTO__"\n};\n</script>\n</body>\n</html>\n'


# ---------- 5) logica de render (se incrusta inline en index.html) ----------
APP_JS = '/* ===================================================================\n   VEMO — Consolidated Executive Summary — app.js\n   KPI cards, KPI Trend chart and P&L table match the format of the 4\n   individual company dashboards (English throughout).\n   =================================================================== */\n\nlet YTD_START = 0;\nconst charts = {};\n\n/* ---------------- generic formatters ---------------- */\nfunction fmtInt(v){ if(v==null) return \'n.a.\'; return Math.round(v).toLocaleString(\'en-US\'); }\nfunction fmtN(v,d){ if(v==null) return \'n.a.\'; return v.toLocaleString(\'en-US\',{minimumFractionDigits:d,maximumFractionDigits:d}); }\nfunction fmtPct(v,d){ if(v==null) return \'n.a.\'; const s=Math.abs(v).toFixed(d)+\'%\'; return v<0?\'(\'+s+\')\':s; }\nfunction fmtMm(v){ if(v==null) return \'n.a.\'; const m=v/1e6; const s=Math.abs(m).toLocaleString(\'en-US\',{minimumFractionDigits:1,maximumFractionDigits:1}); return m<0?\'(\'+s+\'M)\':s+\'M\'; }\nfunction fmtK(v){ if(v==null) return \'n.a.\'; const k=v/1000; const s=Math.abs(k).toLocaleString(\'en-US\',{minimumFractionDigits:1,maximumFractionDigits:1}); return k<0?\'(\'+s+\'k)\':s+\'k\'; }\nconst MONTHS_EN = [\'Jan\',\'Feb\',\'Mar\',\'Apr\',\'May\',\'Jun\',\'Jul\',\'Aug\',\'Sep\',\'Oct\',\'Nov\',\'Dec\'];\nfunction mlbl(m){\n  if(!m) return \'\';\n  const [y,mo]=m.split(\'-\');\n  return MONTHS_EN[parseInt(mo,10)-1]+\' \'+y.slice(2);\n}\nfunction unitSuffixFor(unit){\n  if(!unit) return \'\';\n  if(unit===\'#\'||unit===\'%\') return \'\';\n  if(/\\$/.test(unit)) return \'\';\n  return unit;\n}\nfunction fmtValCard(v, ki){\n  if(v==null) return \'n.a.\';\n  let s;\n  if(ki.type===\'pct\') return fmtPct(v*100,1);\n  if(ki.type===\'money\'){\n    s = ki.fmt===\'mm\' ? fmtMm(v) : fmtN(v,1);\n    if(/MXN|\\$/.test(ki.unit||\'\')) s=\'$\'+s;\n    return s;\n  }\n  switch(ki.fmt){\n    case \'int\': s=fmtInt(v); break;\n    case \'k\':   s=fmtK(v); break;\n    case \'mm\':  s=fmtMm(v); break;\n    case \'n0\':  s=fmtN(v,0); break;\n    case \'n2\':  s=fmtN(v,2); break;\n    case \'n1\':\n    default:    s=fmtN(v,1);\n  }\n  if(/MXN|\\$/.test(ki.unit||\'\')) s=\'$\'+s;\n  return s;\n}\n/* range-footer formatting: generic magnitude scaling, no currency sign\n   (matches the source dashboards\' KPI13 card footer, e.g. "1.1M - 8.4M"\n   or "1,465 - 2,121") */\nfunction fmtRangeVal(v, isPct){\n  if(v==null || isNaN(v)) return \'\';\n  if(isPct) return (v*100).toFixed(1)+\'%\';\n  const a = Math.abs(v);\n  if(a>=1e9) return (v/1e9).toFixed(1)+\'B\';\n  if(a>=1e6) return (v/1e6).toFixed(1)+\'M\';\n  if(a>=1e3) return Math.round(v).toLocaleString(\'en-US\');\n  return v.toFixed(a<10?2:1);\n}\n\n/* ---------------- sparkline (Actuals solid + Budget dashed) ---------------- */\nfunction sparklineSVG(data, budget, w, h){\n  w = w||180; h = h||44;\n  const budVals = (budget||[]).filter(v=>v!=null && v!==0);\n  const allVals = data.filter(v=>v!=null).concat(budVals);\n  if(allVals.length < 2) return \'\';\n  const min=Math.min(...allVals), max=Math.max(...allVals);\n  const range = (max-min)||1;\n  const n=data.length;\n  const stepX = w/((n-1)||1);\n  function y(v){ return h-2 - ((v-min)/range)*(h-4); }\n\n  const pts=[];\n  data.forEach((v,i)=>{ if(v!=null) pts.push([i*stepX, y(v)]); });\n  if(pts.length<2) return \'\';\n  const linePath = \'M\'+pts.map(p=>p[0].toFixed(1)+\',\'+p[1].toFixed(1)).join(\' L\');\n  const last=pts[pts.length-1], first=pts[0];\n  const areaPath = linePath+` L${last[0].toFixed(1)},${h} L${first[0].toFixed(1)},${h} Z`;\n\n  let budgetPath = \'\';\n  if(budget && budget.length){\n    const bpts=[];\n    budget.forEach((v,i)=>{ if(v!=null && v!==0) bpts.push([i*stepX, y(v)]); });\n    if(bpts.length>=2) budgetPath = \'M\'+bpts.map(p=>p[0].toFixed(1)+\',\'+p[1].toFixed(1)).join(\' L\');\n  }\n\n  return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none">\n    <path d="${areaPath}" fill="rgba(123,218,218,0.25)" stroke="none"/>\n    ${budgetPath ? `<path d="${budgetPath}" fill="none" stroke="#1F5454" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.75"/>` : \'\'}\n    <path d="${linePath}" fill="none" stroke="#11ABAB" stroke-width="1.6"/>\n  </svg>`;\n}\n\n/* ---------------- KPI card ---------------- */\nfunction kpiCardHTML(ki, LI){\n  const data = ki.data, spark = ki.spark || ki.data, budget = ki.budget;\n  const cur = data[LI], prev = LI>=1?data[LI-1]:null, yoy = LI>=12?data[LI-12]:null;\n  const mom = (cur!=null && prev!=null && prev!==0) ? (cur-prev)/Math.abs(prev) : null;\n  const bud = budget ? budget[LI] : null;\n  const vsBud = (cur!=null && bud!=null && bud!==0) ? (cur-bud)/Math.abs(bud) : null;\n  const better = ki.better || \'up\';\n  const momGood = mom!=null && ((better===\'up\'&&mom>=0)||(better===\'down\'&&mom<=0));\n  const isAmber = mom!=null && !momGood;\n  const momCls = mom==null ? \'\' : (momGood?\'pos\':\'neg\');\n  const arrow = mom==null ? \'\' : (mom>=0?\'▲\':\'▼\');\n  const budGood = vsBud!=null && ((better===\'up\'&&vsBud>=0)||(better===\'down\'&&vsBud<=0));\n  const budCls = vsBud==null ? \'\' : (budGood?\'pos\':\'neg\');\n  const sparkData = spark.slice(0, LI+1);\n  const sparkBudget = budget ? budget.slice(0, LI+1) : null;\n  const startIdx = Math.max(0, LI - sparkData.filter(v=>v!=null).length + 1);\n  const unitSuffix = unitSuffixFor(ki.unit);\n\n  const rangeVals = sparkData.filter(v=>v!=null);\n  let rangeTxt = \'\';\n  if(rangeVals.length){\n    const mn = Math.min(...rangeVals), mx = Math.max(...rangeVals);\n    rangeTxt = fmtRangeVal(mn, ki.type===\'pct\') + \' – \' + fmtRangeVal(mx, ki.type===\'pct\');\n  }\n  // crop the sparkline itself to the informed range (no blank lead-in for\n  // months without data) -- the SVG\'s x-axis should span only startIdx..LI\n  const sparkDataCropped = sparkData.slice(startIdx);\n  const sparkBudgetCropped = sparkBudget ? sparkBudget.slice(startIdx) : null;\n\n  return `<div class="kpi-card${isAmber?\' amber\':\'\'}">\n    <div class="kpi-l">${ki.l}</div>\n    <div class="kpi-v">${fmtValCard(cur,ki)}${unitSuffix?`<span style="font-size:11px;font-weight:600;color:var(--tx3)"> ${unitSuffix}</span>`:\'\'}</div>\n    <div class="kpi-mom">${mom!=null\n        ? `<span class="arr ${momCls}">${arrow}</span><span class="${momCls}">${fmtDevPct(mom)}</span><span style="color:var(--tx3)">vs ${mlbl(DATA.months[prev!=null?LI-1:LI])}</span>`\n        : `<span style="color:var(--tx3)">No prior-month data</span>`}</div>\n    <div class="kpi-bud"><span><span class="lbl">VS BUDGET</span> ${bud!=null?fmtValCard(bud,ki):\'n.a.\'}</span><span class="v ${budCls}">${bud!=null?fmtDevPct(vsBud):\'n.a.\'}</span></div>\n    <div class="kpi-spark">${sparklineSVG(sparkDataCropped, sparkBudgetCropped)}</div>\n    <div class="kpi-spark-legend"><span class="sw sw-actual"></span>Actuals<span class="sw sw-budget"></span>Budget</div>\n    <div class="kpi-spark-foot"><span>${rangeTxt}</span><span>${mlbl(DATA.months[startIdx])} – ${mlbl(DATA.months[LI])}</span></div>\n  </div>`;\n}\n\n/* ---------------- company block ---------------- */\nfunction renderCompanyBlock(ck){\n  const c = DATA.companies[ck];\n  const LI = DATA.last_actual_idx;\n  const cardsHtml = c.kpis.map(ki=>kpiCardHTML(ki,LI)).join(\'\');\n  const optsHtml = c.kpis.map((ki,i)=>`<option value="${i}">${ki.l}</option>`).join(\'\');\n  return `<div class="company-block" id="block-${ck}">\n    <div class="company-head">\n      <div class="company-id">\n        <img class="company-logo" src="${LOGOS[ck]}" alt="${c.name}">\n        <div class="company-names"><div class="cname">${c.name}</div><div class="cfull">${c.full}</div></div>\n      </div>\n      <a class="company-link" href="${c.url}" target="_blank" rel="noopener">Full Dashboard &rarr;</a>\n    </div>\n    <div class="kpi-grid">${cardsHtml}</div>\n    <div class="kpi-trend-bar">\n      <span class="ttl">\\u{1F4C8} KPI Trend</span>\n      <label><input type="checkbox" class="kt-bud" data-c="${ck}" checked> Budget</label>\n      <label><input type="checkbox" class="kt-proj" data-c="${ck}"> Run-Rate</label>\n      <select class="kt-picker" data-c="${ck}">${optsHtml}</select>\n    </div>\n    <div class="kpi-trend-box"><canvas id="chart-${ck}"></canvas></div>\n  </div>`;\n}\n\n/* ---------------- KPI Trend chart (one per company) ---------------- */\nfunction renderTrendChart(ck){\n  const c = DATA.companies[ck];\n  const sel = document.querySelector(`.kt-picker[data-c="${ck}"]`);\n  const showBud = document.querySelector(`.kt-bud[data-c="${ck}"]`).checked;\n  const showProj = document.querySelector(`.kt-proj[data-c="${ck}"]`).checked;\n  const ki = c.kpis[parseInt(sel.value,10)];\n  const LI = DATA.last_actual_idx;\n  const months = DATA.months;\n  let endIdx = Math.min(months.length-1, LI + (showProj?3:0));\n  // crop the x-axis to the range that actually has information for this KPI\n  // -- don\'t show empty months before its first real value\n  let startIdx = 0;\n  for(let i=0;i<=LI;i++){ if(ki.data[i]!=null){ startIdx=i; break; } }\n  const labels = months.slice(startIdx,endIdx+1).map(mlbl);\n  const mainData = months.slice(startIdx,endIdx+1).map((m,i)=>{ const idx=startIdx+i; return idx<=LI ? ki.data[idx] : null; });\n\n  const datasets = [{\n    label: ki.l, data: mainData,\n    borderColor:\'#11ABAB\', backgroundColor:\'rgba(123,218,218,0.30)\',\n    fill:true, tension:0.32, pointRadius:2.5, pointBackgroundColor:\'#168888\',\n    borderWidth:2, spanGaps:true\n  }];\n\n  if(showBud && ki.budget){\n    const curYear = months[LI].split(\'-\')[0];\n    const budData = months.slice(startIdx,endIdx+1).map((m,i)=>{\n      const idx=startIdx+i;\n      const b = ki.budget[idx];\n      if(b==null || b===0) return null;\n      return m >= curYear+\'-01\' ? b : null;\n    });\n    datasets.push({\n      label: ki.l+\' (Budget)\', data: budData,\n      borderColor:\'#1F5454\', borderDash:[6,4], fill:false,\n      pointRadius:0, borderWidth:1.6, spanGaps:true\n    });\n  }\n\n  if(showProj){\n    const window3 = ki.data.slice(Math.max(0,LI-2), LI+1).filter(v=>v!=null);\n    if(window3.length>=1){\n      const avg = window3.reduce((a,b)=>a+b,0)/window3.length;\n      const projData = months.slice(startIdx,endIdx+1).map((m,i)=>{\n        const idx=startIdx+i;\n        if(idx===LI) return ki.data[LI];\n        if(idx>LI) return avg;\n        return null;\n      });\n      datasets.push({\n        label:\'Run-Rate (3m avg.)\', data: projData,\n        borderColor:\'#7BDADA\', borderDash:[3,3], fill:false,\n        pointRadius:0, borderWidth:1.6, spanGaps:true\n      });\n    }\n  }\n\n  const canvas = document.getElementById(`chart-${ck}`);\n  if(charts[ck]) charts[ck].destroy();\n  charts[ck] = new Chart(canvas, {\n    type:\'line\',\n    data:{labels, datasets},\n    options:{\n      responsive:true, maintainAspectRatio:false,\n      interaction:{mode:\'index\',intersect:false},\n      plugins:{\n        legend:{display: datasets.length>1, position:\'bottom\', labels:{boxWidth:12,font:{size:10}}},\n        tooltip:{callbacks:{label:(ctx)=> `${ctx.dataset.label}: ${fmtValCard(ctx.parsed.y, ki)}`}}\n      },\n      scales:{\n        y:{ ticks:{ callback:(v)=>fmtValCard(v,ki), font:{size:10} }, grid:{color:\'rgba(0,0,0,0.06)\'} },\n        x:{ ticks:{ maxRotation:0, autoSkip:true, font:{size:10} }, grid:{display:false} }\n      }\n    }\n  });\n}\n\nfunction bindCompanyControls(ck){\n  document.querySelector(`.kt-picker[data-c="${ck}"]`).addEventListener(\'change\', ()=>renderTrendChart(ck));\n  document.querySelector(`.kt-bud[data-c="${ck}"]`).addEventListener(\'change\', ()=>renderTrendChart(ck));\n  document.querySelector(`.kt-proj[data-c="${ck}"]`).addEventListener(\'change\', ()=>renderTrendChart(ck));\n}\n\n/* ---------------- P&L Consolidado table ---------------- */\nfunction sumRange(arr,start,end){\n  let s=0, any=false;\n  for(let i=start;i<=end;i++){ if(arr[i]!=null){ s+=arr[i]; any=true; } }\n  return any ? s : null;\n}\nfunction pctDelta(cur,base){\n  if(cur==null||base==null||base===0) return null;\n  return (cur-base)/Math.abs(base);\n}\n/* "not meaningful" guard: a swing off a near-zero base (e.g. EBITDA crossing\n   zero) produces a huge, uninformative percentage -- show "n.m." instead,\n   the standard finance convention */\nfunction fmtDevPct(v){\n  if(v==null) return \'—\';\n  if(Math.abs(v)>9.99) return \'n.m.\';\n  return fmtPct(v*100,1);\n}\nfunction fmtMoney(v){ return v==null ? \'—\' : fmtMm(v); }\nfunction clsSign(v){ if(v==null) return \'\'; return v>0?\'pos\':(v<0?\'neg\':\'\'); }\n\nfunction plHeaderRows(){\n  const LI = DATA.last_actual_idx;\n  const mYoY = mlbl(DATA.months[LI-12]), mPrev = mlbl(DATA.months[LI-1]), mCur = mlbl(DATA.months[LI]);\n  return `<thead class="grp"><tr>\n    <th class="firstcol"></th>\n    <th colspan="4">Actuals</th>\n    <th colspan="2">Budget</th>\n    <th colspan="4">Deviation ($)</th>\n    <th colspan="4">Deviation (%)</th>\n  </tr></thead>\n  <thead class="sub"><tr>\n    <th class="firstcol"></th>\n    <th>${mYoY}</th><th>${mPrev}</th><th class="cur">${mCur}</th><th class="cur gend">YTD</th>\n    <th class="cur">${mCur}</th><th class="cur gend">YTD</th>\n    <th>vs ${mPrev}</th><th>vs Budget</th><th>vs ${mYoY}</th><th class="gend">vs Budget YTD</th>\n    <th>vs ${mPrev}</th><th>vs Budget</th><th>vs ${mYoY}</th><th class="gend">vs Budget YTD</th>\n  </tr></thead>`;\n}\n\nfunction rowLineInner(label, key, trClass){\n  const s = DATA.consolidated_pl[key];\n  const LI = DATA.last_actual_idx;\n  const a = s.actual, b = s.budget;\n  const yoy = LI>=12?a[LI-12]:null, prev = LI>=1?a[LI-1]:null, cur = a[LI];\n  const ytd = sumRange(a, YTD_START, LI);\n  const budCur = b ? b[LI] : null;\n  const budYtd = b ? sumRange(b, YTD_START, LI) : null;\n\n  const devMomD = (cur!=null&&prev!=null)?cur-prev:null;\n  const devBudD = (cur!=null&&budCur!=null)?cur-budCur:null;\n  const devYoyD = (cur!=null&&yoy!=null)?cur-yoy:null;\n  const devYtdD = (ytd!=null&&budYtd!=null)?ytd-budYtd:null;\n  const devMomP = pctDelta(cur,prev), devBudP = pctDelta(cur,budCur), devYoyP = pctDelta(cur,yoy), devYtdP = pctDelta(ytd,budYtd);\n\n  const trc = trClass ? ` class="${trClass}"` : \'\';\n  return `<tr${trc}>\n    <td class="lbl">${label}</td>\n    <td>${fmtMoney(yoy)}</td><td>${fmtMoney(prev)}</td><td class="cur">${fmtMoney(cur)}</td><td class="cur gend">${fmtMoney(ytd)}</td>\n    <td class="cur">${fmtMoney(budCur)}</td><td class="cur gend">${fmtMoney(budYtd)}</td>\n    <td class="${clsSign(devMomD)}">${fmtMoney(devMomD)}</td><td class="${clsSign(devBudD)}">${fmtMoney(devBudD)}</td><td class="${clsSign(devYoyD)}">${fmtMoney(devYoyD)}</td><td class="gend ${clsSign(devYtdD)}">${fmtMoney(devYtdD)}</td>\n    <td class="${clsSign(devMomP)}">${fmtDevPct(devMomP)}</td><td class="${clsSign(devBudP)}">${fmtDevPct(devBudP)}</td><td class="${clsSign(devYoyP)}">${fmtDevPct(devYoyP)}</td><td class="gend ${clsSign(devYtdP)}">${fmtDevPct(devYtdP)}</td>\n  </tr>`;\n}\nfunction rowLine(label,key){ return rowLineInner(label,key,\'\'); }\nfunction rowSubtot(label,key){ return rowLineInner(label,key,\'subtot\'); }\n\nfunction rowMargin(label, numKey, denKey){\n  const num = DATA.consolidated_pl[numKey], den = DATA.consolidated_pl[denKey];\n  const LI = DATA.last_actual_idx;\n  const a_n=num.actual, a_d=den.actual, b_n=num.budget, b_d=den.budget;\n  const mk=(n,d)=> (n!=null&&d!=null&&d!==0) ? (n/d*100) : null;\n  const yoy = LI>=12?mk(a_n[LI-12],a_d[LI-12]):null;\n  const prev = LI>=1?mk(a_n[LI-1],a_d[LI-1]):null;\n  const cur = mk(a_n[LI],a_d[LI]);\n  const ytdN = sumRange(a_n,YTD_START,LI), ytdD = sumRange(a_d,YTD_START,LI);\n  const ytd = mk(ytdN,ytdD);\n  const budCur = mk(b_n?b_n[LI]:null, b_d?b_d[LI]:null);\n  const budYtdN = b_n?sumRange(b_n,YTD_START,LI):null, budYtdD = b_d?sumRange(b_d,YTD_START,LI):null;\n  const budYtd = mk(budYtdN,budYtdD);\n  const fp=(v)=> v==null ? \'—\' : v.toFixed(1)+\'%\';\n  return `<tr>\n    <td class="lbl italic">${label}</td>\n    <td class="italic">${fp(yoy)}</td><td class="italic">${fp(prev)}</td><td class="cur italic">${fp(cur)}</td><td class="cur gend italic">${fp(ytd)}</td>\n    <td class="cur italic">${fp(budCur)}</td><td class="cur gend italic">${fp(budYtd)}</td>\n    <td class="italic">—</td><td class="italic">—</td><td class="italic">—</td><td class="gend italic">—</td>\n    <td class="italic">—</td><td class="italic">—</td><td class="italic">—</td><td class="gend italic">—</td>\n  </tr>`;\n}\n\nfunction renderReconTable(){\n  const table = document.getElementById(\'reconTable\');\n  const rows = [\n    rowLine(\'Revenues (net of interco)\',\'revenue\'),\n    rowLine(\'COGS + Opex\',\'opex\'),\n    rowSubtot(\'Normalized Gross Profit\',\'gross_profit\'),\n    rowMargin(\'Gross Margin\',\'gross_profit\',\'revenue\'),\n    rowLine(\'SG&amp;A\',\'sga_total\'),\n    rowSubtot(\'Normalized EBITDA\',\'ebitda\'),\n    rowMargin(\'EBITDA Margin\',\'ebitda\',\'revenue\'),\n    rowLine(\'D&amp;A\',\'da\'),\n    rowSubtot(\'EBIT\',\'ebit\'),\n    rowLine(\'Net Interest\',\'interest_expense\'),\n    rowSubtot(\'EBT\',\'ebt\'),\n    rowLine(\'Taxes\',\'taxes\'),\n    rowSubtot(\'Normalized Net Income\',\'net_income\'),\n    rowMargin(\'Net Margin\',\'net_income\',\'revenue\'),\n  ].join(\'\');\n  table.innerHTML = plHeaderRows() + \'<tbody>\' + rows + \'</tbody>\';\n  document.getElementById(\'reconFootnote\').innerHTML =\n    `Figures in millions of MXN. YTD = cumulative Jan–${mlbl(DATA.months[DATA.last_actual_idx])}. ` +\n    `Aggregated total of VCN + VEMO Impulso + DAE + EV Fleets, net of intercompany eliminations` +\n    (DATA.consolidated_pl_source === \'board_xlsx\'\n      ? \' (sourced from the official Consolidated P&amp;L, "Board Outputs" tab).\'\n      : \' (approximated as the sum of the 4 dashboards -- official consolidated file not available for this build).\');\n}\n\n/* ---------------- init ---------------- */\nfunction computeYtdStart(){\n  const curYear = DATA.months[DATA.last_actual_idx].split(\'-\')[0];\n  const idx = DATA.months.findIndex(m=>m===curYear+\'-01\');\n  return idx>=0 ? idx : 0;\n}\n\ndocument.addEventListener(\'DOMContentLoaded\', ()=>{\n  YTD_START = computeYtdStart();\n  document.getElementById(\'subtitleText\').textContent =\n    `VCN · VEMO Impulso · DAE · EV Fleets — updated through ${DATA.generated_month_label}`;\n\n  document.getElementById(\'companies\').innerHTML =\n    Object.keys(DATA.companies).map(renderCompanyBlock).join(\'\');\n\n  Object.keys(DATA.companies).forEach(ck=>{\n    bindCompanyControls(ck);\n    renderTrendChart(ck);\n  });\n\n  renderReconTable();\n\n  const darkToggle = document.getElementById(\'darkToggle\');\n  let dark = false;\n  try{ dark = localStorage.getItem(\'vemo-consolidated-dark\')===\'1\'; }catch(e){}\n  if(dark){ document.body.classList.add(\'dark-mode\'); darkToggle.textContent=\'☀️\'; }\n  darkToggle.addEventListener(\'click\', ()=>{\n    document.body.classList.toggle(\'dark-mode\');\n    const isDark = document.body.classList.contains(\'dark-mode\');\n    darkToggle.textContent = isDark ? \'☀️\' : \'🌙\';\n    try{ localStorage.setItem(\'vemo-consolidated-dark\', isDark?\'1\':\'0\'); }catch(e){}\n    Object.keys(DATA.companies).forEach(ck=>renderTrendChart(ck));\n  });\n});\n'


# ---------- 6) armar index.html (un solo archivo autocontenido) ----------
def build_index_html(data):
    logos_b64 = {}
    for name in ['dae', 'ev', 'vcn', 'lto']:
        path = os.path.join(HERE, 'logos', f'{name}.png')
        with open(path, 'rb') as f:
            logos_b64[name] = base64.b64encode(f.read()).decode()

    tpl = HTML_TEMPLATE
    tpl = tpl.replace('__GENERATED_MONTH_LABEL__', data['generated_month_label'])
    tpl = tpl.replace('__DATA_JSON__', json.dumps(data, ensure_ascii=False))
    for name in ['dae', 'ev', 'vcn', 'lto']:
        tpl = tpl.replace(f'__LOGO_{name.upper()}__', f"data:image/png;base64,{logos_b64[name]}")
    tpl = tpl.replace('</script>\n</body>', f'\n{APP_JS}\n</script>\n</body>')

    with open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(tpl)
    print('index.html regenerado (un solo archivo autocontenido):', len(tpl), 'bytes')


if __name__ == '__main__':
    data = build_consolidated_data()
    build_index_html(data)
