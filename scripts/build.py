"""
Regenera index.html (UN SOLO archivo autocontenido) a partir de:
  - template.py             (HTML_TEMPLATE embebido: layout/CSS/estructura, con placeholders __X__)
  - app.js                  (logica de render, se incrusta inline en el <script> final)
  - consolidated_data.json  (generado por build_data.py a partir de los 4 dashboards)
  - logos/*.png             (convertidos a base64 e incrustados en el HTML)

El resultado (index.html) no depende de ningun otro archivo: CSS, JS y datos
van todos incrustados en ese unico HTML. Los demas archivos de esta carpeta
(build.py, build_data.py, extract_d.py, app.js, template.py, logos/) son
solo herramientas para regenerarlo cada mes; no hace falta abrirlos.

Uso:
  1) python build_data.py  # descarga los 4 index.html publicos y arma consolidated_data.json
  2) python build.py       # arma el index.html final (este script)
"""
import json, base64, os
from template import HTML_TEMPLATE

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # repo root (donde vive el index.html final)

with open(os.path.join(ROOT, 'consolidated_data.json'), encoding='utf-8') as f:
    data = json.load(f)

logos_b64 = {}
for name in ['dae', 'ev', 'vcn', 'lto']:
    path = os.path.join(HERE, 'logos', f'{name}.png')
    with open(path, 'rb') as f:
        logos_b64[name] = base64.b64encode(f.read()).decode()

with open(os.path.join(HERE, 'app.js'), encoding='utf-8') as f:
    app_js = f.read()

tpl = HTML_TEMPLATE
tpl = tpl.replace('__GENERATED_MONTH_LABEL__', data['generated_month_label'])
tpl = tpl.replace('__DATA_JSON__', json.dumps(data, ensure_ascii=False))
for name in ['dae', 'ev', 'vcn', 'lto']:
    tpl = tpl.replace(f'__LOGO_{name.upper()}__', f"data:image/png;base64,{logos_b64[name]}")
tpl = tpl.replace('</script>\n</body>', f'\n{app_js}\n</script>\n</body>')

with open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(tpl)

print('index.html regenerado (un solo archivo autocontenido):', len(tpl), 'bytes')
