"""Verifica clase_japones.html: imágenes rotas, etiquetas balanceadas y japonés sin romaji.

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
JP = re.compile(r'[぀-ヿ一-鿿]')
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
