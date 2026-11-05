"""Verifica clase_japones.html (imágenes rotas, etiquetas balanceadas, japonés sin romaji, índice de
gramática) y vocab.js, la lista maestra del vocabulario (romaji, japonés en `es` sin `esro`, imágenes,
opuestos recíprocos, lección y categoría válidas, clase existente, duplicados).

Uso:
    python3 tools/check_html.py            # resumen de todo el documento
    python3 tools/check_html.py p-l9       # detalle de una o más secciones (ids de <section>)

Requiere: python3 -m pip install beautifulsoup4
"""
import os, re, sys
from collections import defaultdict
from html.parser import HTMLParser
from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(os.path.join(ROOT, 'clase_japones.html'), encoding='utf-8').read()

# 1) imágenes
srcs = re.findall(r'<img[^>]+src="([^"]+)"', html)
rotas = [s for s in srcs if not os.path.exists(os.path.join(ROOT, s))]
print(f'IMÁGENES: {len(srcs)} referencias, {len(set(srcs))} únicas, rotas: {rotas or "ninguna"}')

# 2) etiquetas balanceadas
class Bal(HTMLParser):
    VOID = {'img', 'br', 'meta', 'input', 'link', 'hr'}
    def __init__(s): super().__init__(); s.stack = []; s.err = []
    def handle_starttag(s, t, a):
        if t not in s.VOID: s.stack.append((t, s.getpos()[0]))
    def handle_endtag(s, t):
        if t in s.VOID: return
        if s.stack and s.stack[-1][0] == t: s.stack.pop()
        else: s.err.append((t, s.getpos()[0], s.stack[-1] if s.stack else None))
b = Bal(); b.feed(html)
print(f'ETIQUETAS: errores de cierre: {b.err[:10] or "ninguno"}; sin cerrar: {b.stack or "ninguna"}')

# 3) japonés sin romaji
# ・ (U+30FB) y ゛゜ (U+309B/C) solos son signos sin lectura propia: no cuentan como japonés
JP = re.compile(r'[぀-゚ゝ-ヺー-ヿ一-鿿]')
LAT = re.compile(r'[A-Za-zÀ-ÿ]{2,}')
soup = BeautifulSoup(html, 'html.parser')

def has_romaji_marker(el):
    if el.select_one('.ro-cell, .romaji, .r, i'): return True
    return 'vchip' in (el.get('class') or []) and bool(el.find('span'))

problems = defaultdict(list); seen = set()
sec_of = lambda el: (el.find_parent('section') or {}).get('id', '(fuera de sección)')
for scope in ([soup.find(id=x) for x in sys.argv[1:]] or [soup.body]):
    # unidades estructuradas (fila, epígrafe, tarjeta…): basta un marcador de romaji dentro
    for u in scope.select('tr, figcaption, .card, .kana, .vchip, .formula, .pchip, li'):
        if u.find_parent(['tr', 'figcaption', 'li']) and u.name != 'tr': continue
        seen.add(id(u))
        if JP.search(u.get_text()) and not has_romaji_marker(u) and not (u.name == 'tr' and u.find('th')):
            problems[sec_of(u)].append(('unidad ' + u.name, u.get_text(' ', strip=True)[:90]))
    # texto suelto (notas, párrafos, títulos): tras cada tramo japonés debe venir un <i>/ro-cell
    # antes de que aparezca texto en español (una frase partida en etiquetas cuenta como un tramo)
    for node in scope.find_all(string=JP):
        if node.find_parent(['script', 'style', 'title', 'i']) or any(id(p) in seen for p in node.parents): continue
        if node.find_parent(class_=['ro-cell', 'romaji', 'r', 'kana']): continue
        ok = False
        for nxt in node.next_elements:
            if isinstance(nxt, Tag) and (nxt.name == 'i' or set(nxt.get('class') or []) & {'ro-cell', 'romaji'}):
                ok = True; break
            if isinstance(nxt, NavigableString) and nxt is not node and LAT.search(nxt): break
        if not ok:
            blk = node.find_parent(['p', 'div', 'h2', 'h3', 'h4', 'td', 'th', 'small', 'footer', 'button', 'span']) or node.parent
            problems[sec_of(node)].append((blk.name + '.' + '.'.join(blk.get('class') or []), node.strip()[:60]))

print(f'JAPONÉS SIN ROMAJI: {sum(len(v) for v in problems.values())}')
for sec, items in problems.items():
    print(f'  [{sec}] {len(items)}')
    if sys.argv[1:]:
        for kind, txt in items: print(f'     {kind:22} {txt}')

# 4) índice de gramática: cada fila con lección (.lz) necesita data-clase="c-MMDD …" con ids que existan
#    (sin eso la fila no aparece en el 📏 Resumen ni lleva el botón 📅 a su clase)
gram = soup.find(id='p-gramatica')
avisos = []
for tr in (gram.select('tr') if gram else []):
    if not tr.select_one('.lz'): continue
    jp = (tr.select_one('.jp-cell') or tr).get_text(' ', strip=True)[:60]
    ids = (tr.get('data-clase') or '').split()
    if not ids: avisos.append(('sin data-clase', jp))
    for i in ids:
        if not soup.find(id=i): avisos.append((f'id inexistente: {i}', jp))
print(f'ÍNDICE DE GRAMÁTICA: filas sin data-clase o con id inexistente: {len(avisos)}')
for kind, txt in avisos: print(f'     {kind:22} {txt}')

# 5) vocab.js: la lista maestra del vocabulario (const VOCAB = [ {…}, … ];)
VALID_LEC = {'L7', 'L8', 'L9', 'práctica', '⚽'}
VALID_CAT = {'persona', 'verbo', 'objeto', 'estudio', 'lugar', 'evento', 'mundial', 'expresion', 'adjna', 'adji'}
import json
vjs = open(os.path.join(ROOT, 'vocab.js'), encoding='utf-8').read()
m = re.search(r'const\s+VOCAB\s*=\s*(\[.*\])\s*;?\s*$', vjs, re.S)
errores, avisos_v = [], []
try:
    VOCAB = json.loads(re.sub(r',\s*\]$', ']', m.group(1))) if m else None
except ValueError as e:
    VOCAB = None; errores.append(f'no se pudo leer (¿coma de más o comillas?): {e}')
if VOCAB is None and not errores: errores.append('no encontré "const VOCAB = [ … ];"')
VOCAB = VOCAB or []
jp_de = lambda e: e.get('kana', '') + (f"（{e['kanji']}）" if e.get('kanji') else '') if not (e.get('kana') or '').endswith('（な）') or not e.get('kanji') \
    else e['kana'][:-3] + f"（{e['kanji']}）（な）"
claves = defaultdict(list)
for i, e in enumerate(VOCAB):
    jp = jp_de(e); donde = f'#{i} {jp}'
    if not (e.get('kana') or '').strip(): errores.append(f'{donde}: falta kana')
    if not (e.get('ro') or '').strip(): errores.append(f'{donde}: romaji vacío')
    if not (e.get('es') or '').strip(): errores.append(f'{donde}: español vacío')
    if JP.search(e.get('ro') or ''): errores.append(f'{donde}: el romaji tiene japonés')
    resto = e.get('es') or ''
    for tramo, ro in (e.get('esro') or {}).items():
        if tramo not in resto: errores.append(f'{donde}: esro "{tramo}" no está en es')
        if not (ro or '').strip(): errores.append(f'{donde}: esro "{tramo}" sin romaji')
        resto = resto.replace(tramo, '')
    if JP.search(resto): errores.append(f'{donde}: japonés en es sin romaji (agregalo en esro): {resto}')
    if e.get('lec') not in VALID_LEC: errores.append(f'{donde}: lec inválida {e.get("lec")!r}')
    if e.get('cat') not in VALID_CAT: errores.append(f'{donde}: cat inválida {e.get("cat")!r}')
    if e.get('clase') and not soup.find(id=e['clase']): errores.append(f'{donde}: clase inexistente {e["clase"]}')
    if not isinstance(e.get('clave'), bool): errores.append(f'{donde}: clave tiene que ser true/false')
    if e.get('img') and not os.path.exists(os.path.join(ROOT, e['img'])): errores.append(f'{donde}: imagen inexistente {e["img"]}')
    claves[(jp, e.get('lec'))].append(i)
por_jp = defaultdict(list)
for e in VOCAB: por_jp[jp_de(e)].append(e)
for e in VOCAB:
    jp = jp_de(e)
    pares = e.get('par') or []
    for p in ([pares] if isinstance(pares, str) else pares):
        if p not in por_jp: errores.append(f'{jp}: par "{p}" no existe en VOCAB'); continue
        def tiene(o):
            q = o.get('par') or []
            return jp in ([q] if isinstance(q, str) else q)
        if not any(tiene(o) for o in por_jp[p]): errores.append(f'{jp}: par "{p}" no es recíproco')
for (jp, lec), idx in claves.items():
    if len(idx) > 1: errores.append(f'duplicado: {jp} ({lec}) en #{idx}')
# aviso: mismo kana base en la misma lección, sin kanji que los distinga (p. ej. いい / いい（よい）（良い）)
base = lambda e: re.sub(r'（.*?）', '', e.get('kana') or '').strip()
grupos = defaultdict(list)
for i, e in enumerate(VOCAB): grupos[(base(e), e.get('lec'))].append(i)
for (b_, lec), idx in grupos.items():
    kj = [VOCAB[i].get('kanji') for i in idx]
    if len({jp_de(VOCAB[i]) for i in idx}) > 1 and (None in kj or len(set(kj)) < len(kj)):
        avisos_v.append(f'mismo kana en {lec}: ' + ' · '.join(jp_de(VOCAB[i]) for i in idx))
con_img = sum(1 for e in VOCAB if e.get('img'))
con_par = sum(1 for e in VOCAB if e.get('par'))
print(f'VOCAB.JS: {len(VOCAB)} palabras, {con_img} con imagen, {con_par} con opuesto; errores: {len(errores)}, avisos: {len(avisos_v)}')
for x in errores: print('     ✗ ' + x)
for x in avisos_v: print('     ⚠ ' + x)
