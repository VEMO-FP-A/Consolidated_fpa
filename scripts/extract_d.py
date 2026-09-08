import json, re, sys

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

if __name__ == '__main__':
    for name in ['DAE_BoardD','LTO_BoardD','VCN_BoardD','EV_BoardD']:
        d = extract_D(f'{name}.html')
        print(f'\n=== {name} ===')
        if d is None:
            print('NO D FOUND')
            continue
        keys = list(d.keys())
        print(f'num keys: {len(keys)}')
        print('keys:', keys)
        lai = d.get('last_actual_idx')
        print('last_actual_idx:', lai, 'month:', d.get('months',[None]*100)[lai] if lai is not None else None)
