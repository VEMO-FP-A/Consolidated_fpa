"""
VEMO -- Consolidated Executive Summary: UN SOLO script que hace todo.

  python build.py

Descarga los 4 dashboards individuales (DAE, LTO, EV Fleets, VCN) desde GitHub,
extrae su objeto `const D` embebido, arma consolidated_data.json, y genera
index.html -- un solo archivo autocontenido (CSS + JS + datos incrustados,
nada que abrir aparte).

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

PERIODS = ['latest', 'ytd', 'py_full', 'budget_ytd', 'budget_latest']


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


# ---------- 3) armar consolidated_data.json a partir de los 4 `D` extraidos ----------
def _build_companies():
    companies = {}

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
        """monthly actual+budget series for a KPI-card sparkline — full available
        history (0..LAI), matching the source dashboards' KPI13 cards which use
        spStart=0 (NOT just current-year YTD)"""
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
            'revenue': spark(d, 'revenue', 'budget_revenue', 0, lai),
            'ebitda': spark(d, 'ebitda', 'budget_ebitda', 0, lai),
            'ebitda_margin': spark(d, 'ebitda_margin', 'budget_ebitda_margin', 0, lai),
            'net_income': spark(d, 'net_income', 'budget_net_income', 0, lai),
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
            'revenue': spark(d, 'revenue', 'budget_revenue', 0, lai_e),
            'ebitda': spark(d, 'ebitda', 'budget_ebitda', 0, lai_e),
            'ebitda_margin': spark(d, 'ebitda_margin', 'budget_ebitda_margin', 0, lai_e),
            'net_income': spark(d, 'net_income', 'budget_net_income', 0, lai_e),
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
            'revenue': spark(d, 'revenue', 'budget_revenue', 0, lai_v),
            'ebitda': spark(d, 'ebitda', 'budget_ebitda', 0, lai_v),
            'ebitda_margin': spark(d, 'ebitda_margin', 'budget_ebitda_margin', 0, lai_v),
            'net_income': spark(d, 'net_income', 'budget_net_income', 0, lai_v),
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
            'revenue': spark(d, 'net_operating_revenue', 'budget_net_operating_revenue', 0, lai_l),
            'net_income': spark(d, 'net_income', 'budget_net_income', 0, lai_l),
            'net_portfolio_board': spark(d, 'net_portfolio_board', 'budget_net_portfolio_board', 0, lai_l),
            'roe_pct_board': spark(d, 'roe_pct_board', 'budget_roe_pct_board', 0, lai_l),
        }
    }

    MESES_ES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    gen_month = months[lai]
    gy, gm = gen_month.split('-')
    gen_label = f"{MESES_ES[int(gm)]} {gy}"

    return {
        'companies': companies,
        'generated_month': gen_month,
        'generated_month_label': gen_label,
        'spark_months': months[0:lai+1],
    }


def build_consolidated_data():
    download_sources()
    data = _build_companies()
    with open(os.path.join(ROOT, 'consolidated_data.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('consolidated_data.json listo. mes mas reciente:', data['generated_month'])
    return data


# ---------- 4) plantilla HTML (con placeholders __X__) ----------
HTML_TEMPLATE = '<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>VEMO — Consolidated Executive Summary</title>\n<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">\n<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n<style>\n:root{\n  --forest:#1F5454;--teal:#11ABAB;--teal-deep:#168888;--mint:#7BDADA;\n  --red:#C0392B;--green:#117A45;--amber:#E59500;--bg:#f5f6f7;--sf:#fff;--b:#e8eaed;\n  --tx:#222;--tx2:#555;--tx3:#888;--rs:6px;--r:10px;\n}\n*{box-sizing:border-box;margin:0;padding:0}\nbody{font-family:\'Space Grotesk\',sans-serif;background:var(--bg);color:var(--tx);line-height:1.4}\nbody.dark-mode{--bg:#1a1f23;--sf:#22282d;--b:#353c42;--tx:#e6ebee;--tx2:#d4dae0;--tx3:#9aa3ac;--forest:#7BDADA;color:#e6ebee!important}\nbody.dark-mode *{color:inherit}\n.wrap{max-width:1360px;margin:0 auto;padding:28px 24px 60px}\n.topbar{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:28px}\n.title{font-size:28px;font-weight:700;color:var(--forest)}\n.subtitle{font-size:13px;color:var(--tx2);margin-top:4px}\n.topctrls{display:flex;gap:10px;align-items:center;flex-wrap:wrap}\n.seg{display:flex;background:var(--sf);border:1px solid var(--b);border-radius:999px;padding:3px;gap:2px}\n.seg button{border:none;background:transparent;padding:6px 16px;border-radius:999px;font:inherit;font-size:12.5px;font-weight:600;color:var(--tx2);cursor:pointer;transition:.15s}\n.seg button.active{background:var(--forest);color:#fff}\n.iconbtn{width:34px;height:34px;border-radius:999px;border:1px solid var(--b);background:var(--sf);color:var(--tx2);cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center}\n\n.company-block{background:var(--sf);border:1px solid var(--b);border-radius:14px;padding:22px 24px;margin-bottom:22px}\n.company-head{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;margin-bottom:18px}\n.company-id{display:flex;align-items:center;gap:14px}\n.company-logo{height:46px;max-width:130px;object-fit:contain}\n.company-names .cname{font-size:19px;font-weight:700;color:var(--tx)}\n.company-names .cfull{font-size:12px;color:var(--tx3)}\n.company-link{display:inline-flex;align-items:center;gap:6px;background:var(--forest);color:#fff!important;text-decoration:none;font-size:12.5px;font-weight:600;padding:9px 16px;border-radius:999px;white-space:nowrap;transition:.15s}\n.company-link:hover{opacity:.85}\n\n/* KPI cards — matching the sibling per-company dashboards\' Executive Summary cards exactly */\n.kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(195px,1fr));gap:11px;margin-bottom:18px}\n.kpi-card{background:var(--sf);border:1px solid var(--b);border-radius:10px;padding:13px 15px 14px;position:relative;overflow:hidden;display:flex;flex-direction:column}\n.kpi-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--teal)}\n.kpi-card.amber::before{background:var(--amber)}\n.kpi-card.red::before{background:var(--red)}\n.kpi-l{font-size:9.5px;font-weight:700;color:var(--tx3);text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px}\n.kpi-v{font-size:22px;font-weight:700;color:var(--forest);margin-bottom:3px;font-variant-numeric:tabular-nums;line-height:1.05}\n.kpi-mom{font-size:10.5px;color:var(--tx2);display:flex;align-items:center;gap:5px;margin-top:3px}\n.kpi-mom .arr{font-size:9px}\n.kpi-bud{font-size:10.5px;color:var(--tx2);margin-top:9px;padding-top:8px;border-top:1px dashed #ececec;display:flex;justify-content:space-between;align-items:center;gap:6px}\n.kpi-bud .lbl{color:var(--tx3);font-size:9.5px;letter-spacing:0.04em;text-transform:uppercase}\n.kpi-bud .v{font-weight:600;font-variant-numeric:tabular-nums}\n.neg{color:var(--red)}\n.pos{color:var(--teal)}\n.kpi-spark{margin-top:10px;height:50px;overflow:hidden}\nbody.dark-mode .kpi-spark svg path[stroke="#11ABAB"]{stroke:#7BDADA!important}\nbody.dark-mode .kpi-spark svg path[stroke="#1F5454"]{stroke:#9aa3ac!important}\nbody.dark-mode .kpi-bud{border-top-color:#353c42}\nbody.dark-mode .kpi-card{background:#22282d;border-color:#353c42}\n.kpi-spark-foot{display:flex;justify-content:space-between;font-size:9.5px;color:var(--tx3);margin-top:4px;padding:0 2px}\n\n.chart-box{background:var(--bg);border:1px solid var(--b);border-radius:var(--r);padding:16px 18px 10px;position:relative;height:230px}\n.chart-title{font-size:12px;font-weight:600;color:var(--tx2);margin-bottom:6px}\n\n.section-title-row{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:14px;margin-top:36px}\n.section-title{font-size:18px;font-weight:700;color:var(--forest);margin:0 0 4px}\n.section-note{font-size:12px;color:var(--tx3);margin-bottom:0;max-width:820px}\n\n.recon-wrap{background:var(--sf);border:1px solid var(--b);border-radius:14px;padding:22px 24px 26px;margin-top:16px;overflow-x:auto}\ntable.recon{border-collapse:collapse;width:100%;min-width:820px;font-size:13px}\ntable.recon th, table.recon td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--b);white-space:nowrap}\ntable.recon th{font-size:11px;text-transform:uppercase;letter-spacing:.3px;color:var(--tx3);font-weight:600}\ntable.recon td:first-child, table.recon th:first-child{text-align:left;font-weight:600;color:var(--tx)}\ntable.recon tr.total td{font-weight:700;border-top:2px solid var(--forest);border-bottom:2px solid var(--forest);color:var(--forest)}\ntable.recon tr.sub td{color:var(--tx3);font-size:12px}\ntable.recon td.neg{color:var(--red)}\ntable.recon td.pos{color:var(--green)}\n.foot-note{font-size:11px;color:var(--tx3);margin-top:14px;line-height:1.6}\n.foot-note sup{color:var(--teal)}\n\n.link-row{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0 8px}\n.link-btn{flex:1;min-width:200px;text-align:center;background:var(--sf);border:1.5px solid var(--forest);color:var(--forest)!important;text-decoration:none;font-weight:600;font-size:13px;padding:13px 16px;border-radius:10px;transition:.15s}\n.link-btn:hover{background:var(--forest);color:#fff!important}\n\nfooter{text-align:center;font-size:11px;color:var(--tx3);margin-top:40px}\n\n@media (max-width:900px){\n  .kpi-row{grid-template-columns:repeat(2,1fr)}\n}\n</style>\n</head>\n<body>\n<div class="wrap">\n  <div class="topbar">\n    <div>\n      <div class="title">VEMO — Consolidated Executive Summary</div>\n      <div class="subtitle" id="subtitleText">DAE · VEMO Impulso · EV Fleets · VCN — actualizado a __GENERATED_MONTH_LABEL__</div>\n    </div>\n    <div class="topctrls">\n      <button class="iconbtn" id="darkToggle" title="Modo oscuro">🌙</button>\n    </div>\n  </div>\n\n  <div id="companies"></div>\n\n  <div class="section-title-row">\n    <div>\n      <div class="section-title">P&amp;L Consolidado — Conciliación</div>\n      <div class="section-note">Suma agregada de los 4 negocios de VEMO en la vista managerial de cada dashboard. No incluye eliminaciones intercompañía adicionales a las ya reflejadas en cada P&amp;L individual.</div>\n    </div>\n    <div class="seg" id="periodSeg">\n      <button data-period="ytd" class="active">YTD 2026</button>\n      <button data-period="latest">Mes actual</button>\n    </div>\n  </div>\n  <div class="recon-wrap">\n    <table class="recon" id="reconTable"></table>\n    <div class="foot-note" id="reconFootnote"></div>\n  </div>\n\n  <footer>VEMO FP&amp;A · Consolidated_fpa · generado automáticamente desde los dashboards de cada empresa</footer>\n</div>\n\n<script>\nconst DATA = __DATA_JSON__;\nconst LOGOS = {\n  dae: "__LOGO_DAE__",\n  ev: "__LOGO_EV__",\n  vcn: "__LOGO_VCN__",\n  lto: "__LOGO_LTO__"\n};\n</script>\n</body>\n</html>\n'


# ---------- 5) logica de render (se incrusta inline en index.html) ----------
APP_JS = '/* VEMO Consolidated Executive Summary — render logic */\nlet currentPeriod = \'ytd\'; // \'ytd\' | \'latest\' — only drives the P&L reconciliation table\nconst budgetKeyFor = { ytd: \'budget_ytd\', latest: \'budget_latest\' };\nconst chartInstances = {};\n\n/* ---------- formatting helpers (ported to match the sibling per-company\n   dashboards\' KPI13 cards byte-for-byte: parens for negatives, "$" for\n   money, "bps"/"%" with parens, mlblShort month labels) ---------- */\nconst MN = [\'Ene\',\'Feb\',\'Mar\',\'Abr\',\'May\',\'Jun\',\'Jul\',\'Ago\',\'Sep\',\'Oct\',\'Nov\',\'Dic\'];\nfunction mlblShort(m){\n  if (!m) return \'—\';\n  const [y, mo] = m.split(\'-\');\n  return (MN[+mo - 1] || mo) + \' \' + y.slice(2);\n}\nfunction fmtMm(n){ // money in millions, parens for negative — e.g. "$42.5" / "($12.3)"\n  if (n===null || n===undefined || isNaN(n)) return \'—\';\n  const v = n/1e6, a = Math.abs(v);\n  return (v<0?\'($\':\'$\') + a.toFixed(1) + (v<0?\')\':\'\');\n}\nfunction fmtPctParen(p){ // p is a fraction (e.g. -0.0725) -> "(7.3%)" / "7.3%"\n  if (p===null || p===undefined || isNaN(p)) return \'—\';\n  const pct = p*100, a = Math.abs(pct);\n  return (pct<0?\'(\':\'\') + a.toFixed(1) + \'%\' + (pct<0?\')\':\'\');\n}\nfunction fmtBps(b){\n  if (b===null || b===undefined || isNaN(b)) return \'—\';\n  const a = Math.abs(b);\n  return (b<0?\'(\':\'\') + Math.round(a).toLocaleString() + \' bps\' + (b<0?\')\':\'\');\n}\n// plain (non-parens) versions, used in the P&L reconciliation table & big charts\nfunction fmtMoney(v){\n  if (v===null || v===undefined || isNaN(v)) return \'—\';\n  const abs = Math.abs(v);\n  const sign = v<0 ? \'-\' : \'\';\n  return sign + \'$\' + (abs/1e6).toLocaleString(\'es-MX\',{minimumFractionDigits:1,maximumFractionDigits:1}) + \'M\';\n}\nfunction fmtPct(v){\n  if (v===null || v===undefined || isNaN(v)) return \'—\';\n  return (v*100).toLocaleString(\'es-MX\',{minimumFractionDigits:1,maximumFractionDigits:1}) + \'%\';\n}\n\n/* ---------- KPI card spec per company ----------\n   isPct: value is a fraction (margin/ROE) needing *100 for display & bps deltas\n   better: \'up\' -> higher is favorable (all 8 of our metrics are \'up\') */\nconst KPI_SPECS = {\n  dae: [\n    {label:\'Revenue\', dataKey:\'revenue\', isPct:false},\n    {label:\'EBITDA\', dataKey:\'ebitda\', isPct:false},\n    {label:\'EBITDA Margin\', dataKey:\'ebitda_margin\', isPct:true},\n    {label:\'Utilidad Neta\', dataKey:\'net_income\', isPct:false},\n  ],\n  ev: [\n    {label:\'Revenue\', dataKey:\'revenue\', isPct:false},\n    {label:\'EBITDA\', dataKey:\'ebitda\', isPct:false},\n    {label:\'EBITDA Margin\', dataKey:\'ebitda_margin\', isPct:true},\n    {label:\'Utilidad Neta\', dataKey:\'net_income\', isPct:false},\n  ],\n  vcn: [\n    {label:\'Revenue\', dataKey:\'revenue\', isPct:false},\n    {label:\'EBITDA\', dataKey:\'ebitda\', isPct:false},\n    {label:\'EBITDA Margin\', dataKey:\'ebitda_margin\', isPct:true},\n    {label:\'Utilidad Neta\', dataKey:\'net_income\', isPct:false},\n  ],\n  lto: [\n    {label:\'Ingreso Oper. Neto\', dataKey:\'revenue\', isPct:false},\n    {label:\'Utilidad Neta\', dataKey:\'net_income\', isPct:false},\n    {label:\'Cartera Neta\', dataKey:\'net_portfolio_board\', isPct:false},\n    {label:\'ROE (mensual)\', dataKey:\'roe_pct_board\', isPct:true},\n  ],\n};\n\nfunction devPct(a, b){ if (b===null || b===undefined || !b || isNaN(b)) return null; return (a-b)/Math.abs(b)*100; }\nfunction devBps(a, b){ if (b===null || b===undefined || isNaN(b)) return null; return (a-b)*10000; }\nfunction isNegBetter(p){ if (p===null || p===undefined) return false; return p < 0; } // all our metrics are better:\'up\'\n\n/* ---------- inline SVG sparkline — ported verbatim from the sibling dashboards ---------- */\nfunction kpiSparkline(series, budgetSeries, w, h){\n  w = w || 260; h = h || 50;\n  const vals = series.filter(v => v !== null && v !== undefined && !isNaN(v));\n  if (!vals.length) return \'\';\n  const budVals = (budgetSeries || []).filter(v => v !== null && v !== undefined && !isNaN(v) && v !== 0);\n  const allVals = vals.concat(budVals);\n  const mn = Math.min(0, Math.min.apply(null, allVals)), mx = Math.max.apply(null, allVals);\n  const range = mx - mn || 1;\n  const n = series.length;\n  const stepX = n > 1 ? w / (n - 1) : w;\n  function y(v){ return h - ((v - mn) / range) * (h - 6) - 3; }\n  let path = \'M0,\' + h + \' \';\n  for (let i=0; i<n; i++){\n    const v = series[i]; if (v === null || v === undefined || isNaN(v)) continue;\n    path += \'L\' + (i*stepX).toFixed(1) + \',\' + y(v).toFixed(1) + \' \';\n  }\n  path += \'L\' + w + \',\' + h + \' Z\';\n  let linePath = \'\', started = false;\n  for (let i=0; i<n; i++){\n    const v = series[i]; if (v === null || v === undefined || isNaN(v)) continue;\n    linePath += (started ? \'L\' : \'M\') + (i*stepX).toFixed(1) + \',\' + y(v).toFixed(1) + \' \';\n    started = true;\n  }\n  let budgetPath = \'\';\n  if (budgetSeries && budgetSeries.length){\n    let bs = false;\n    for (let i=0; i<n; i++){\n      const bv = budgetSeries[i]; if (bv === null || bv === undefined || isNaN(bv) || bv === 0) continue;\n      budgetPath += (bs ? \'L\' : \'M\') + (i*stepX).toFixed(1) + \',\' + y(bv).toFixed(1) + \' \';\n      bs = true;\n    }\n  }\n  return \'<svg viewBox="0 0 \' + w + \' \' + h + \'" preserveAspectRatio="none" style="display:block;width:100%;height:100%">\' +\n    \'<defs><linearGradient id="spg" x1="0" y1="0" x2="0" y2="1">\' +\n    \'<stop offset="0%" stop-color="#11ABAB" stop-opacity="0.30"/>\' +\n    \'<stop offset="100%" stop-color="#11ABAB" stop-opacity="0.03"/>\' +\n    \'</linearGradient></defs>\' +\n    \'<path d="\' + path + \'" fill="url(#spg)" stroke="none"/>\' +\n    \'<path d="\' + linePath + \'" fill="none" stroke="#11ABAB" stroke-width="1.8"/>\' +\n    (budgetPath ? \'<path d="\' + budgetPath + \'" fill="none" stroke="#1F5454" stroke-width="1.2" stroke-dasharray="3,2" opacity="0.7"/>\' : \'\') +\n    \'</svg>\';\n}\n\nfunction fmtRangeVal(v, isPct){\n  if (v === null || v === undefined || isNaN(v)) return \'\';\n  if (isPct) return (v*100).toFixed(0) + \'%\';\n  const a = Math.abs(v);\n  if (a >= 1e9) return (v/1e9).toFixed(1) + \'B\';\n  if (a >= 1e6) return (v/1e6).toFixed(1) + \'M\';\n  if (a >= 1e3) return (v/1e3).toFixed(0) + \'k\';\n  return v.toFixed(1);\n}\n\nfunction kpiCardHTML(spec, company){\n  const kc = company.kpi_charts[spec.dataKey];\n  const months = DATA.spark_months;\n  const n = months.length;\n  const cur = n - 1, prev = n - 2;\n  const actual = kc ? kc.actual : [];\n  const budget = kc ? kc.budget : [];\n  const val = actual[cur];\n  const valPrev = actual[prev];\n  const valBud = budget[cur];\n\n  const momPct = spec.isPct ? null : devPct(val, valPrev);\n  const momBps = spec.isPct ? devBps(val, valPrev) : null;\n  const budPct = spec.isPct ? null : (valBud ? devPct(val, valBud) : null);\n  const budBps = spec.isPct ? devBps(val, valBud) : null;\n\n  const momTxt = spec.isPct ? fmtBps(momBps) : (momPct===null ? \'—\' : fmtPctParen(momPct/100));\n  const budTxt = spec.isPct ? fmtBps(budBps) : (budPct===null ? \'n.a.\' : fmtPctParen(budPct/100));\n  const momVal = spec.isPct ? momBps : momPct;\n  const budVal = spec.isPct ? budBps : budPct;\n  const momCls = isNegBetter(momVal) ? \'neg\' : \'pos\';\n  const budCls = isNegBetter(budVal) ? \'neg\' : \'pos\';\n  const arrSym = momVal===null ? \'\' : (momVal>=0 ? \'▲\' : \'▼\');\n  // amber left-border: ported verbatim from the source dashboards\' KPI13 cards —\n  // triggered by an unfavorable MoM move, NOT by vs-Budget performance\n  const cardCls = isNegBetter(momVal) ? \'amber\' : \'\';\n\n  const fmtCardVal = spec.isPct ? fmtPctParen(val) : fmtMm(val);\n  const fmtBudVal = spec.isPct ? fmtPctParen(valBud) : fmtMm(valBud);\n\n  const sparkline = kpiSparkline(actual, budget, 260, 50);\n  const rangeVals = actual.filter(v => v !== null && v !== undefined && !isNaN(v));\n  let rangeTxt = \'\';\n  if (rangeVals.length){\n    const mn = Math.min(...rangeVals), mx = Math.max(...rangeVals);\n    rangeTxt = fmtRangeVal(mn, spec.isPct) + \' – \' + fmtRangeVal(mx, spec.isPct);\n  }\n  const dateRangeTxt = mlblShort(months[0]) + \' – \' + mlblShort(months[cur]);\n\n  return `<div class="kpi-card ${cardCls}">\n    <div class="kpi-l">${spec.label}</div>\n    <div class="kpi-v">${fmtCardVal}</div>\n    <div class="kpi-mom"><span class="arr ${momCls}">${arrSym}</span> <span class="${momCls}">${momTxt}</span> <span style="color:var(--tx3)">vs ${mlblShort(months[prev])}</span></div>\n    ${valBud!==null && valBud!==undefined ? `<div class="kpi-bud"><span><span class="lbl">vs Budget</span> ${fmtBudVal}</span><span class="v ${budCls}">${budTxt}</span></div>` : \'\'}\n    <div class="kpi-spark">${sparkline}</div>\n    <div class="kpi-spark-foot"><span>${rangeTxt}</span><span>${dateRangeTxt}</span></div>\n  </div>`;\n}\n\nfunction monthLabel(m){\n  const meses = {\'01\':\'Ene\',\'02\':\'Feb\',\'03\':\'Mar\',\'04\':\'Abr\',\'05\':\'May\',\'06\':\'Jun\',\'07\':\'Jul\',\'08\':\'Ago\',\'09\':\'Sep\',\'10\':\'Oct\',\'11\':\'Nov\',\'12\':\'Dic\'};\n  const [y,mo] = m.split(\'-\');\n  return meses[mo] + " \'" + y.slice(2);\n}\n\nfunction renderCompanyBlock(c){\n  const spec = KPI_SPECS[c.key];\n  const kpiHTML = spec.map(s => kpiCardHTML(s, c)).join(\'\');\n  const chartId = `chart-${c.key}`;\n  return `\n  <div class="company-block">\n    <div class="company-head">\n      <div class="company-id">\n        <img class="company-logo" src="${LOGOS[c.logo]}" alt="${c.name} logo">\n        <div class="company-names">\n          <div class="cname">${c.name}</div>\n          <div class="cfull">${c.full_name}</div>\n        </div>\n      </div>\n      <a class="company-link" href="${c.url}" target="_blank" rel="noopener">Company Board Deck →</a>\n    </div>\n    <div class="kpi-grid">${kpiHTML}</div>\n    <div class="chart-box">\n      <div class="chart-title">${c.key === \'lto\' ? \'Ingreso Operativo Neto (barras) vs. Utilidad Neta (línea) · mensual\' : \'Revenue (barras) vs. EBITDA (línea) · mensual\'}</div>\n      <canvas id="${chartId}"></canvas>\n    </div>\n  </div>`;\n}\n\nfunction buildChart(c){\n  const ctx = document.getElementById(`chart-${c.key}`);\n  if (!ctx) return;\n  const months = c.chart.months.map(monthLabel);\n  const isDark = document.body.classList.contains(\'dark-mode\');\n  const gridColor = isDark ? \'#353c42\' : \'#e8eaed\';\n  const txColor = isDark ? \'#9aa3ac\' : \'#888\';\n  if (chartInstances[c.key]) chartInstances[c.key].destroy();\n  chartInstances[c.key] = new Chart(ctx, {\n    data: {\n      labels: months,\n      datasets: [\n        {\n          type: \'bar\',\n          label: c.key === \'lto\' ? \'Ingreso Oper. Neto\' : \'Revenue\',\n          data: c.chart.revenue,\n          backgroundColor: c.accent + \'55\',\n          borderColor: c.accent,\n          borderWidth: 1,\n          borderRadius: 3,\n          order: 2,\n          yAxisID: \'y\',\n        },\n        {\n          type: \'line\',\n          label: c.key === \'lto\' ? \'Utilidad Neta\' : \'EBITDA\',\n          data: c.chart.ebitda,\n          borderColor: \'#1F5454\',\n          backgroundColor: \'#1F5454\',\n          pointRadius: 2,\n          tension: 0.3,\n          order: 1,\n          yAxisID: \'y\',\n        },\n      ],\n    },\n    options: {\n      responsive: true,\n      maintainAspectRatio: false,\n      interaction: { mode: \'index\', intersect: false },\n      plugins: {\n        legend: { position: \'bottom\', labels: { boxWidth: 10, font: { size: 10 }, color: txColor } },\n        tooltip: {\n          callbacks: {\n            label: (item) => `${item.dataset.label}: ${fmtMoney(item.raw)}`,\n          }\n        },\n      },\n      scales: {\n        x: { grid: { display: false }, ticks: { font: { size: 9 }, color: txColor, maxRotation: 0 } },\n        y: {\n          grid: { color: gridColor },\n          ticks: { font: { size: 9 }, color: txColor, callback: (v) => fmtMoney(v) },\n        },\n      },\n    },\n  });\n}\n\n// ---------- P&L reconciliation table ----------\nconst RECON_ROWS = [\n  {label:\'Revenue / Ingreso Operativo Neto\', field:\'revenue\'},\n  {label:\'Costo Operativo (Opex)\', field:\'opex\', neg:true},\n  {label:\'Utilidad Bruta\', field:\'gross_profit\', subtotal:true},\n  {label:\'SG&A\', field:\'sga_total\', neg:true},\n  {label:\'EBITDA\', field:\'ebitda\', subtotal:true, note:1},\n  {label:\'D&A\', field:\'da\', neg:true},\n  {label:\'EBIT\', field:\'ebit\', subtotal:true},\n  {label:\'Gastos Financieros\', field:\'interest_expense\', neg:true},\n  {label:\'EBT (Utilidad antes de Impuestos)\', field:\'ebt\', subtotal:true},\n  {label:\'Impuestos\', field:\'taxes\', neg:true},\n  {label:\'Utilidad Neta Consolidada\', field:\'net_income\', total:true},\n];\nconst RECON_ORDER = [\'dae\',\'lto\',\'ev\',\'vcn\'];\n\nfunction cellClass(val, neg){\n  if (val===null || val===undefined) return \'\';\n  if (neg) return val < 0 ? \'neg\' : (val > 0 ? \'pos\' : \'\');\n  return \'\';\n}\n\nfunction renderRecon(){\n  const periodKey = currentPeriod;\n  const companies = DATA.companies;\n  let thead = `<thead><tr><th>Línea (${currentPeriod===\'ytd\'?\'YTD 2026\':DATA.generated_month_label})</th>`;\n  RECON_ORDER.forEach(k => thead += `<th>${companies[k].name}</th>`);\n  thead += `<th>Total VEMO</th></tr></thead>`;\n\n  let tbody = \'<tbody>\';\n  RECON_ROWS.forEach(row => {\n    let total = 0, hasAny = false;\n    let cells = \'\';\n    RECON_ORDER.forEach(k => {\n      const line = companies[k].pl[row.field];\n      const val = line ? line[periodKey] : null;\n      if (val !== null && val !== undefined){ total += val; hasAny = true; }\n      cells += `<td class="${cellClass(val, row.neg)}">${fmtMoney(val)}</td>`;\n    });\n    const rowCls = row.total ? \'total\' : (row.subtotal ? \'sub\' : \'\');\n    const noteSup = row.note ? \'<sup>1</sup>\' : \'\';\n    tbody += `<tr class="${rowCls}"><td>${row.label}${noteSup}</td>${cells}<td>${hasAny ? fmtMoney(total) : \'—\'}</td></tr>`;\n  });\n  tbody += \'</tbody>\';\n  document.getElementById(\'reconTable\').innerHTML = thead + tbody;\n\n  document.getElementById(\'reconFootnote\').innerHTML =\n    `<sup>1</sup> VEMO Impulso (LTO) es un negocio financiero (leasing) y no reporta EBITDA nativamente; ` +\n    `para esta conciliación se calcula como EBT + Gastos Financieros + D&amp;A, de forma consistente con el resto de las empresas. ` +\n    `Sus KPIs propios (ROE, Cartera Neta) se muestran en su tarjeta arriba en vez de EBITDA.`;\n}\n\n// ---------- init ----------\nfunction renderCompanies(){\n  const wrap = document.getElementById(\'companies\');\n  const order = [\'dae\',\'lto\',\'ev\',\'vcn\'];\n  wrap.innerHTML = order.map(k => renderCompanyBlock(DATA.companies[k])).join(\'\');\n  order.forEach(k => buildChart(DATA.companies[k]));\n}\n\ndocument.getElementById(\'periodSeg\').addEventListener(\'click\', (e) => {\n  const btn = e.target.closest(\'button\');\n  if (!btn) return;\n  currentPeriod = btn.dataset.period;\n  [...document.getElementById(\'periodSeg\').children].forEach(b => b.classList.toggle(\'active\', b===btn));\n  renderRecon();\n});\n\ndocument.getElementById(\'darkToggle\').addEventListener(\'click\', () => {\n  document.body.classList.toggle(\'dark-mode\');\n  document.getElementById(\'darkToggle\').textContent = document.body.classList.contains(\'dark-mode\') ? \'☀️\' : \'🌙\';\n  buildChart_all();\n});\nfunction buildChart_all(){\n  [\'dae\',\'lto\',\'ev\',\'vcn\'].forEach(k => buildChart(DATA.companies[k]));\n}\n\nrenderCompanies();\nrenderRecon();\n'


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
