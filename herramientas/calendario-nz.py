#!/usr/bin/env python3
"""Calendario de trabajo estacional del mapa mural (datos/calendario-nz.json).

    python3 herramientas/calendario-nz.py

Fuentes (se bajan a cache/calendario/):
  - Work and Income, «Fruit and vegetable seasonal work»: calendario mensual por
    región, zona, cultivo y tarea; en negrita, los meses con más trabajo.
  - Work and Income, «Finding seasonal work»: ventanas generales de los demás
    trabajos (frigoríficos, esquila, esquí, turismo, pesca, lechería, forestal).
  - PickNZ, «Work and play in Marlborough»: viñedos casi todo el año (sin meses).

Las filas de fruta salen de los meses que publica Work and Income para esa región
y ese cultivo, sin extrapolar a otras regiones. Las ventanas generales se
transcriben de la página y el script verifica que el texto siga ahí.
"""
import html
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / 'cache' / 'calendario'
SALIDA = RAIZ / 'datos' / 'calendario-nz.json'

URL_CAL = 'https://www.workandincome.govt.nz/work/find-jobs/where-to-look-for-jobs/seasonal-work-calendar.html'
URL_GEN = 'https://www.workandincome.govt.nz/work/find-jobs/where-to-look-for-jobs/finding-seasonal-work'
URL_PICK = 'https://www.picknz.co.nz/work-opportunities/work-planner/work-and-play-in-marlborough/'
MESES = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
         'september', 'october', 'november', 'december']

# Filas de fruta y hortalizas: (etiqueta, zona, sector, región de Work and Income, cultivos)
FRUTA = [
    ('Kiwi', 'Bay of Plenty', 'fruta', 'Bay of Plenty', ['Kiwifruit']),
    ('Manzana y pera', "Hawke's Bay", 'fruta', 'Hawkes Bay', ['Apples', 'Pears']),
    ('Manzana y pera', 'Nelson-Tasman', 'fruta', 'Nelson', ['Apples', 'Pears']),
    ('Cereza', 'Central Otago', 'fruta', 'Otago', ['Cherries', 'Cheries']),
    ('Carozo', 'Central Otago', 'fruta', 'Otago', ['Apricots', 'Peaches', 'Nectarines', 'Plums']),
    ('Palta', 'Northland', 'fruta', 'Northland', ['Avocado']),
    ('Lúpulo', 'Tasman', 'fruta', 'Tasman', ['Hops']),
    ('Uva', 'Wairarapa', 'vid', 'Wellington', ['Grapes']),
    ('Hortalizas', 'Horowhenua', 'hortalizas', 'Manawatu-Whanganui', ['General vegetables']),
]
# Tareas, de la que más gente pide a la que menos: la celda muestra la primera que aparezca
TAREAS = [('picking', 'C'), ('pruning', 'P'), ('thinning', 'R'), ('maintenance', 'M')]

# Ventanas generales de «Finding seasonal work»: (etiqueta, sector, texto de la página, meses, meses de más trabajo)
GENERALES = [
    ('Frigoríficos', 'frigorificos', 'October to May, and July to August', [10, 11, 12, 1, 2, 3, 4, 5, 7, 8], []),
    ('Parición y esquila', 'ovinos', 'August to May', [8, 9, 10, 11, 12, 1, 2, 3, 4, 5], []),
    ('Lechería', 'lecheria', 'Almost year round', list(range(1, 13)), []),
    ('Forestal', 'forestal', 'All year round, particularly autumn', list(range(1, 13)), [3, 4, 5]),
    ('Viñedos (Marlborough y otras)', 'vid', 'Usually available all year', list(range(1, 13)), []),
    ('Esquí', 'esqui', 'June to September', [6, 7, 8, 9], []),
    ('Turismo, temporada alta', 'turismo', 'November to February', [11, 12, 1, 2], []),
    ('Pesca y mariscos', 'pesca', 'June to September', [6, 7, 8, 9], []),
]


def bajar(url, archivo):
    destino = CACHE / archivo
    if not destino.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        print('  bajando', url)
        req = urllib.request.Request(url, headers={'User-Agent': 'para-imprimir/atlas-nz'})
        with urllib.request.urlopen(req, timeout=120) as r:
            destino.write_bytes(r.read())
    return destino.read_text(encoding='utf-8', errors='replace')


def texto(c):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', '', c)).split())


def registros(pagina):
    """(mes, región, zona, cultivo, tareas, pico) de cada fila del calendario."""
    trozos = re.split(r'<details id="(\w+)"', pagina)
    out = []
    for j in range(1, len(trozos), 2):
        mes, cuerpo = trozos[j], trozos[j + 1]
        if mes not in MESES:
            continue
        partes = re.split(r'<h2[^>]*>\s*([^<]+?)\s*</h2>', cuerpo)
        for i in range(1, len(partes), 2):
            region = html.unescape(partes[i].strip()).replace('/', '-')
            for fila in re.findall(r'<tr[^>]*>(.*?)</tr>', partes[i + 1], re.S):
                celdas = re.findall(r'<td[^>]*>(.*?)</td>', fila, re.S)
                if len(celdas) == 3:
                    pico = '<strong>' in celdas[1] or '<strong>' in celdas[2]
                    zona, cultivo, tareas = (texto(c) for c in celdas)
                    out.append((MESES.index(mes) + 1, region, zona, cultivo, tareas.lower(), pico))
    return out


def fila_fruta(regs, etiqueta, zona, sector, region, cultivos):
    meses = [None] * 12
    zonas = set()
    for mes, reg, z, cultivo, tareas, pico in regs:
        if reg != region or cultivo not in cultivos:
            continue
        zonas.add(z)
        tipo = next((t for clave, t in TAREAS if clave in tareas), None)
        if not tipo:
            continue
        actual = meses[mes - 1]
        orden = [t for _, t in TAREAS]
        if actual is None or orden.index(tipo) < orden.index(actual['t']):
            meses[mes - 1] = {'t': tipo, 'pico': pico or bool(actual and actual['pico'])}
        elif pico:
            actual['pico'] = True
    if not any(meses):
        raise SystemExit(f'Work and Income no trae {cultivos} en {region}: revisar la fila «{etiqueta}»')
    return {'etiqueta': etiqueta, 'zona': zona, 'sector': sector, 'fuente': 'winz-calendario',
            'zonas_winz': sorted(zonas), 'meses': meses}


def main():
    regs = registros(bajar(URL_CAL, 'calendario.html'))
    general = texto(bajar(URL_GEN, 'general.html'))
    pick = texto(bajar(URL_PICK, 'picknz-marlborough.html'))
    filas = [fila_fruta(regs, *f) for f in FRUTA]
    for etiqueta, sector, frase, meses, picos in GENERALES:
        if frase.lower() not in general.lower():
            raise SystemExit(f'La página de Work and Income ya no dice «{frase}»: revisar la fila «{etiqueta}»')
        filas.append({'etiqueta': etiqueta, 'zona': '', 'sector': sector, 'fuente': 'winz-general', 'texto_fuente': frase,
                      'meses': [{'t': 'V', 'pico': m in picos} if m in meses else None for m in range(1, 13)]})
    if 'almost all year round' not in pick.lower():
        raise SystemExit('PickNZ ya no dice que en Marlborough hay trabajo de viñedo casi todo el año')
    actualizada = re.search(r'Updated on (\d+ \w+ \d{4})', general)
    SALIDA.write_text(json.dumps({
        '_nota': ('Calendario de trabajo estacional del mapa mural. Tareas: C = cosecha (picking), P = poda (pruning), '
                  'R = raleo (thinning), M = mantenimiento de plantas, V = ventana general sin desglose de tareas. '
                  '«pico» = mes con más trabajo según Work and Income (en negrita en su calendario). '
                  'Ventanas orientativas: varían según cultivo, clima, empleador y año. '
                  'Generado por herramientas/calendario-nz.py.'),
        'consultado': date.today().isoformat(),
        'fuentes': {
            'winz-calendario': f'Work and Income, «Fruit and vegetable seasonal work» ({URL_CAL}).',
            'winz-general': f'Work and Income, «Finding seasonal work», actualizada el {actualizada.group(1) if actualizada else "?"} ({URL_GEN}).',
            'picknz': f'PickNZ, «Work and play in Marlborough» ({URL_PICK}): viñedos casi todo el año.',
        },
        'registros_winz': len(regs),
        'filas': filas,
    }, ensure_ascii=False, indent=1) + '\n')
    for f in filas:
        celdas = ''.join((m['t'].lower() if not m['pico'] else m['t']) if m else '·' for m in f['meses'])
        print(f'  {f["etiqueta"][:28]:28s} {f["zona"][:16]:16s} {celdas}')
    print(f'  {SALIDA.relative_to(RAIZ)} ({len(regs)} registros de Work and Income)')


if __name__ == '__main__':
    main()
