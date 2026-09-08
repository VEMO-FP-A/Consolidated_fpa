"""
Descarga el index.html público de cada uno de los 4 dashboards VEMO y arma
consolidated_data.json (usado por build.py para regenerar el index.html consolidado).

Correr despues de que los 4 dashboards individuales ya tengan el mes nuevo:
  python build_data.py
"""
import json, os, urllib.request
from extract_d import extract_D

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, '_source_cache')
os.makedirs(CACHE, exist_ok=True)

SOURCES = {
    'DAE_BoardD': 'https://raw.githubusercontent.com/VEMO-FP-A/DAE_BoardD/main/index.html',
    'LTO_BoardD': 'https://raw.githubusercontent.com/VEMO-FP-A/LTO_BoardD/main/index.html',
    'VCN_BoardD': 'https://raw.githubusercontent.com/VEMO-FP-A/VCN_BoardD/main/index.html',
    'EV_BoardD':  'https://raw.githubusercontent.com/VEMO-FP-A/EV_BoardD/main/index.html',
}

def fetch(name, url):
    path = os.path.join(CACHE, f'{name}.html')
    req = urllib.request.Request(url, headers={'User-Agent': 'vemo-consolidated-build'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read()
    with open(path, 'wb') as f:
        f.write(content)
    return path

for name, url in SOURCES.items():
    print('descargando', name, '...')
    fetch(name, url)

def s(d, key, i0, i1):
    arr = d.get(key)
    if arr is None:
        return None
    return sum(arr[i0:i1+1])

def v(d, key, i):
    arr = d.get(key)
    if arr is None:
        return None
    return arr[i]

def series(d, key, i0, i1):
    arr = d.get(key)
    if arr is None:
        return None
    return [round(x, 1) for x in arr[i0:i1+1]]

def spark(d, field, budget_field, i0, i1):
    """monthly actual+budget series for a KPI-card sparkline, same range the
    source dashboards use (current-year-to-date only, i.e. YTD_START..LAI)"""
    a = d.get(field)
    b = d.get(budget_field)
    actual = [round(x, 2) if x is not None else None for x in (a[i0:i1+1] if a else [None]*(i1-i0+1))]
    budget = [round(x, 2) if x is not None else None for x in (b[i0:i1+1] if b else [None]*(i1-i0+1))]
    return {'actual': actual, 'budget': budget}

def mk(d, lai, ytd0, fields, budget_prefix='budget_'):
    out = {}
    for f in fields:
        out[f] = {
            'latest': v(d, f, lai),
            'ytd': s(d, f, ytd0, lai),
            'py_full': s(d, f, 0, 11),
            'budget_ytd': s(d, budget_prefix + f, ytd0, lai),
            'budget_latest': v(d, budget_prefix + f, lai),
        }
    return out

PERIODS = ['latest', 'ytd', 'py_full', 'budget_ytd', 'budget_latest']

companies = {}

# ---------- DAE ----------
d = extract_D(os.path.join(CACHE, 'DAE_BoardD.html'))
lai = d['last_actual_idx']
months = d['months']
dae_fields = ['revenue', 'opex', 'gross_profit', 'gross_margin', 'sga_total', 'ebitda', 'ebitda_margin',
              'da', 'ebit', 'interest_expense', 'ebt', 'taxes', 'net_income', 'ni_margin']
companies['dae'] = {
    'key': 'dae', 'name': 'DAE', 'full_name': 'Driving As Employee', 'logo': 'dae',
    'url': 'https://vemo-fp-a.github.io/DAE_BoardD/',
    'accent': '#11ABAB',
    'pl': mk(d, lai, 12, dae_fields),
    'kpi_ops': {
        'eop_active_drivers': v(d, 'eop_active_drivers', lai),
        'trips_total_ytd': s(d, 'trips_total', 12, lai),
        'total_fleet': v(d, 'total_fleet', lai),
    },
    'chart': {
        'months': months[0:lai+1],
        'revenue': series(d, 'revenue', 0, lai),
        'ebitda': series(d, 'ebitda', 0, lai),
    },
    'kpi_charts': {
        'revenue': spark(d, 'revenue', 'budget_revenue', 12, lai),
        'ebitda': spark(d, 'ebitda', 'budget_ebitda', 12, lai),
        'ebitda_margin': spark(d, 'ebitda_margin', 'budget_ebitda_margin', 12, lai),
        'net_income': spark(d, 'net_income', 'budget_net_income', 12, lai),
    }
}

# ---------- EV FLEETS ----------
d = extract_D(os.path.join(CACHE, 'EV_BoardD.html'))
lai_e = d['last_actual_idx']
months_e = d['months']
ev_fields = ['revenue', 'opex', 'gross_profit', 'gross_margin', 'sga', 'ebitda', 'ebitda_margin',
             'da', 'ebit', 'interest_expense', 'ebt', 'taxes', 'net_income', 'ni_margin']
ev_pl = mk(d, lai_e, 12, ev_fields)
ev_pl['sga_total'] = ev_pl.pop('sga')
companies['ev'] = {
    'key': 'ev', 'name': 'EV Fleets', 'full_name': 'VEMO EV Fleets', 'logo': 'ev',
    'url': 'https://vemo-fp-a.github.io/EV_BoardD/',
    'accent': '#117A45',
    'pl': ev_pl,
    'kpi_ops': {
        'epc_backlog': v(d, 'epc_backlog', lai_e),
        'epc_pipeline': v(d, 'epc_pipeline', lai_e),
        'zee_total_monitored': v(d, 'zee_total_monitored', lai_e),
    },
    'chart': {
        'months': months_e[0:lai_e+1],
        'revenue': series(d, 'revenue', 0, lai_e),
        'ebitda': series(d, 'ebitda', 0, lai_e),
    },
    'kpi_charts': {
        'revenue': spark(d, 'revenue', 'budget_revenue', 12, lai_e),
        'ebitda': spark(d, 'ebitda', 'budget_ebitda', 12, lai_e),
        'ebitda_margin': spark(d, 'ebitda_margin', 'budget_ebitda_margin', 12, lai_e),
        'net_income': spark(d, 'net_income', 'budget_net_income', 12, lai_e),
    }
}

# ---------- VCN ----------
d = extract_D(os.path.join(CACHE, 'VCN_BoardD.html'))
lai_v = d['last_actual_idx']
months_v = d['months']
vcn_fields_direct = ['revenue', 'opex', 'gross_profit', 'gross_margin', 'ebitda', 'ebitda_margin',
                     'da', 'ebit', 'interest_expense', 'ebt', 'taxes', 'net_income', 'ni_margin']
pl_vcn = mk(d, lai_v, 12, vcn_fields_direct)

def derive_sga(pl):
    out = {}
    for period in PERIODS:
        gp = pl['gross_profit'][period]
        eb = pl['ebitda'][period]
        out[period] = (eb - gp) if (gp is not None and eb is not None) else None
    return out

pl_vcn['sga_total'] = derive_sga(pl_vcn)
companies['vcn'] = {
    'key': 'vcn', 'name': 'VCN', 'full_name': 'VEMO Charging Network', 'logo': 'vcn',
    'url': 'https://vemo-fp-a.github.io/VCN_BoardD/',
    'accent': '#168888',
    'pl': pl_vcn,
    'kpi_ops': {
        'installed_capacity_mw': v(d, 'installed_capacity_mw', lai_v),
        'total_connectors': v(d, 'total_connectors', lai_v),
        'utilization': v(d, 'utilization', lai_v),
    },
    'chart': {
        'months': months_v[0:lai_v+1],
        'revenue': series(d, 'revenue', 0, lai_v),
        'ebitda': series(d, 'ebitda', 0, lai_v),
    },
    'kpi_charts': {
        'revenue': spark(d, 'revenue', 'budget_revenue', 12, lai_v),
        'ebitda': spark(d, 'ebitda', 'budget_ebitda', 12, lai_v),
        'ebitda_margin': spark(d, 'ebitda_margin', 'budget_ebitda_margin', 12, lai_v),
        'net_income': spark(d, 'net_income', 'budget_net_income', 12, lai_v),
    }
}

# ---------- LTO / VEMO IMPULSO (negocio financiero: sin revenue/ebitda nativos) ----------
d = extract_D(os.path.join(CACHE, 'LTO_BoardD.html'))
lai_l = d['last_actual_idx']
months_l = d['months']

def mk_lto(d, lai):
    def line(field, budget_field):
        return {'latest': v(d, field, lai), 'ytd': s(d, field, 12, lai),
                'py_full': s(d, field, 0, 11), 'budget_ytd': s(d, budget_field, 12, lai),
                'budget_latest': v(d, budget_field, lai)}
    rev = line('net_operating_revenue', 'budget_net_operating_revenue')
    opex = line('cogs_total', 'budget_cogs_total')

    def gp_calc(period):
        r = rev[period]; o = opex[period]
        return (r - o) if (r is not None and o is not None) else None
    gross_profit = {p: gp_calc(p) for p in PERIODS}
    sga = line('total_sga', 'budget_total_sga')
    da = line('da_total', 'budget_da_total')
    ie = line('interest_expense', 'budget_interest_expense')
    ebt = line('ebt', 'budget_ebt')
    taxes = line('taxes', 'budget_taxes')
    ni = line('net_income', 'budget_net_income')

    def ebitda_calc(period):
        e = ebt[period]; i = ie[period]; dda = da[period]
        return (e + (i or 0) + (dda or 0)) if e is not None else None
    ebitda = {p: ebitda_calc(p) for p in PERIODS}

    def ebit_calc(period):
        e = ebt[period]; i = ie[period]
        return (e + (i or 0)) if e is not None else None
    ebit = {p: ebit_calc(p) for p in PERIODS}

    def margin(num, den):
        return {p: (num[p]/den[p] if (num[p] is not None and den[p] not in (None, 0)) else None) for p in PERIODS}

    return {
        'revenue': rev, 'opex': opex, 'gross_profit': gross_profit, 'gross_margin': margin(gross_profit, rev),
        'sga_total': sga, 'ebitda': ebitda, 'ebitda_margin': margin(ebitda, rev),
        'da': da, 'ebit': ebit, 'interest_expense': ie, 'ebt': ebt, 'taxes': taxes,
        'net_income': ni, 'ni_margin': margin(ni, rev),
    }

companies['lto'] = {
    'key': 'lto', 'name': 'VEMO Impulso', 'full_name': 'VEMO Impulso (LTO)', 'logo': 'lto',
    'url': 'https://vemo-fp-a.github.io/LTO_BoardD/',
    'accent': '#7BDADA',
    'is_financial_model': True,
    'pl': mk_lto(d, lai_l),
    'kpi_ops': {
        'active_units': v(d, 'active_units', lai_l),
        'net_portfolio_board': v(d, 'net_portfolio_board', lai_l),
        'roe_pct_board': v(d, 'roe_pct_board', lai_l),
        'collection_rate': v(d, 'collection_rate', lai_l),
    },
    'chart': {
        'months': months_l[0:lai_l+1],
        'revenue': series(d, 'net_operating_revenue', 0, lai_l),
        'ebitda': [round((v(d, 'ebt', i) or 0) + (v(d, 'interest_expense', i) or 0) + (v(d, 'da_total', i) or 0), 1) for i in range(0, lai_l+1)],
    },
    'kpi_charts': {
        'revenue': spark(d, 'net_operating_revenue', 'budget_net_operating_revenue', 12, lai_l),
        'net_income': spark(d, 'net_income', 'budget_net_income', 12, lai_l),
        'net_portfolio_board': spark(d, 'net_portfolio_board', 'budget_net_portfolio_board', 12, lai_l),
        'roe_pct_board': spark(d, 'roe_pct_board', 'budget_roe_pct_board', 12, lai_l),
    }
}

MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
gen_month = months[lai]
gy, gm = gen_month.split('-')
gen_label = f"{MESES_ES[int(gm)]} {gy}"

with open(os.path.join(ROOT, 'consolidated_data.json'), 'w', encoding='utf-8') as f:
    json.dump({
        'companies': companies,
        'generated_month': gen_month,
        'generated_month_label': gen_label,
        'spark_months': months[12:lai+1],
    }, f, ensure_ascii=False, indent=1)

print('consolidated_data.json listo. mes mas reciente:', gen_month)
