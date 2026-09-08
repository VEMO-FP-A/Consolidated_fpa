"""
Regenera index.html a partir de:
  - template.html          (layout/CSS/estructura, con placeholders __X__)
  - consolidated_data.json  (generado por build_data.py a partir de los 4 dashboards)
  - logos/*.png             (convertidos a base64 e incrustados en el HTML)

Uso:
  1) python extract_d.py   # opcional, solo para inspeccionar los dashboards fuente
  2) python build_data.py  # descarga los 4 index.html públicos y arma consolidated_data.json
  3) python build.py       # arma el index.html final (este script)
"""
import json, base64, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # repo root (donde viven template.html / index.html finales)

with open(os.path.join(ROOT, 'consolidated_data.json'), encoding='utf-8') as f:
    data = json.load(f)

logos_b64 = {}
for name in ['dae', 'ev', 'vcn', 'lto']:
    path = os.path.join(HERE, 'logos', f'{name}.png')
    with open(path, 'rb') as f:
        logos_b64[name] = base64.b64encode(f.read()).decode()

with open(os.path.join(ROOT, 'template.html'), encoding='utf-8') as f:
    tpl = f.read()

tpl = tpl.replace('__GENERATED_MONTH_LABEL__', data['generated_month_label'])
tpl = tpl.replace('__DATA_JSON__', json.dumps(data, ensure_ascii=False))
for name in ['dae', 'ev', 'vcn', 'lto']:
    tpl = tpl.replace(f'__LOGO_{name.upper()}__', f"data:image/png;base64,{logos_b64[name]}")

with open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(tpl)

print('index.html regenerado:', len(tpl), 'bytes')
