"""Fichas por región v2 (NZ-A-01 a 16): borrador del rediseño.

Misma familia visual que el mural v2 (relieve con tintas de altura, rutas de LINZ con su
número, parques en verde, texto sin cajas) con toques de postal ilustrada: una
curiosidad por región con un dibujo a lápiz. Nombres de lugares en inglés; la
información, en castellano. Menos datos que la v1, más fáciles de leer.

    python3 herramientas/fichas_nz2.py CAN    # deja la ficha en salida/pruebas/
"""
import json
import math
import sys

from shapely.geometry import shape
from shapely.ops import polylabel, unary_union

from atlas_nz import (DATOS, PT, RAIZ, Encuadre, caja_rotulo, capa, esc, recortar, relieve_mural_encuadre,
                      rotulo_punto, ruta, tabla)
from bloques_mural import imagen_lapiz
from fichas_nz import Colocador, SEP_CAT, TAM_CAT, datos, mapa_ubicacion, pieza_mural, simbolo
from glifos import glifo_html

FECHA = '2026-10-22'
VERSION = 2
MAPA_W, MAPA_H = 182, 114
MAX_PUESTOS = 5
ESTILO = {
    'agua': (3.35, 'texto', 400, 0.15), 'lago': (3.0, 'texto', 400, 0), 'sierra': (4.6, 'titulo', 700, 1.2),
    'sierra-chica': (3.0, 'texto', 700, 0.5), 'isla': (3.0, 'texto', 700, 0), 'rio': (2.95, 'texto', 400, 0),
    'pico-n': (3.0, 'texto', 700, 0), 'vecina': (3.0, 'texto', 800, 0.6), 'parque-n': (3.0, 'texto', 700, 0.2),
    't1': (4.94, 'titulo', 800, 0), 't2': (3.88, 'titulo', 700, 0), 't3': (3.35, 'texto', 700, 0), 't4': (2.95, 'texto', 400, 0),
}
# Zona del calendario de Work and Income -> regiones (consejo regional)
ZONA_REGION = {'Bay of Plenty': ['BOP'], "Hawke's Bay": ['HKB'], 'Nelson-Tasman': ['NLS', 'TAS'], 'Central Otago': ['OTA'],
               'Northland': ['NTL'], 'Tasman': ['TAS'], 'Wairarapa': ['WGN'], 'Horowhenua': ['MWT']}
# Fila general del calendario -> sector de la tabla que la habilita en una región
GENERAL_SECTOR = {'frigorificos': 'frigorificos', 'ovinos': 'ovinos', 'lecheria': 'lecheria', 'forestal': 'forestal',
                  'vid': 'vid', 'turismo': 'alojamiento', 'pesca': None, 'esqui': None}
CON_ESQUI = {'CAN', 'OTA', 'MWT'}  # Mt Hutt y otros; Queenstown y Wānaka; Ruapehu
SECTOR_ES = {'lecheria': ('Lechería', 'dairy'), 'ovinos': ('Ovejas', 'sheep'), 'vacunos': ('Ganado de carne', 'beef'),
             'fruta': ('Fruta', 'orchards'), 'vid': ('Viñedos', 'vineyards'), 'hortalizas': ('Hortalizas', 'vegetables'),
             'forestal': ('Forestal', 'forestry'), 'frigorificos': ('Frigoríficos', 'meat processing'),
             'alojamiento': ('Alojamiento', 'hospitality'), 'construccion': ('Construcción', 'construction'),
             'transporte': ('Transporte', 'transport'), 'tecnicos': ('Arquitectura e ingeniería', 'engineering')}
ETIQUETA_ES = {'Parición y esquila': 'Parición y esquila', 'Turismo, temporada alta': 'Turismo, temporada alta',
               'Viñedos (Marlborough y otras)': 'Viñedos', 'Esquí': 'Centros de esquí'}
MESES = ['E', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']


def num(n, dec=0):
    s = f'{n:,.{dec}f}'
    return s.replace(',', '§').replace('.', ',').replace('§', '.')


def caja(clase, x, y, texto, ancla, rot=0):
    tam, cual, peso, espaciado = ESTILO[clase]
    return caja_rotulo(x, y, texto, ancla, tam, cual, peso, espaciado, rot)


def ingles(nombre):
    """Parte inglesa de un nombre doble («Aoraki / Mount Cook» -> «Mount Cook»), como en el mural."""
    if ' / ' not in nombre:
        return nombre
    partes = [p.strip() for p in nombre.split(' / ')]
    claves = ('Mount', 'Mt ', 'Lake', 'Bay', 'Island', 'Sound', 'Cape', 'Glacier', 'Gulf', 'River', 'Pass', 'Peninsula')
    return next((p for p in partes if any(k in p for k in claves)), partes[0])


def encuadre(geom):
    minx, miny, maxx, maxy = geom.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    necesaria = max(max(maxx - minx, 70_000) * 1.1 / MAPA_W, max(maxy - miny, 60_000) * 1.1 / MAPA_H) * 1000
    escala = math.ceil(necesaria / 50_000) * 50_000
    m = escala / 1000
    return Encuadre(escala, cx - MAPA_W / 2 * m, cy + MAPA_H / 2 * m)


def mapa(r, destino_jpg):
    iso = r['iso']
    W, H = MAPA_W, MAPA_H
    vista = (-1, -1, W + 1, H + 1)
    regiones = {p['iso']: g for p, g in capa('regiones')}
    E = encuadre(regiones[iso])
    tierra = recortar(unary_union([E.geom(g) for _, g in capa('tierra')]), -20, -20, W + 20, H + 20).simplify(0.06)
    reg = E.geom(regiones[iso]).simplify(0.06)
    relieve_mural_encuadre(E, W, H).save(destino_jpg, quality=88, optimize=True)
    href = f'relieve/{destino_jpg.name}' if destino_jpg.parent.name == 'relieve' else destino_jpg.name
    capas = [f'<image href="{href}" x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="none"/>']
    base = tierra.simplify(0.1)
    for i, d in enumerate((0.8, 1.8, 3.0), start=1):
        capas.append(f'<path class="ola o{i}" d="{ruta(recortar(base.buffer(d, quad_segs=3).boundary, *vista))}"/>')
    parques = [(p['nombre'], E.geom(g)) for p, g in capa('parques')]
    for n, g in parques:
        capas.append(f'<path class="parque" d="{ruta(recortar(g, *vista).simplify(0.08))}"/>')
    capas.append(f'<path class="velo" d="{ruta(recortar(tierra.difference(reg), *vista))}"/>')
    lagos = unary_union([E.geom(g) for _, g in capa('linz/lagos')])
    rios = unary_union([E.geom(g) for _, g in capa('rios')]).intersection(tierra.buffer(0.2))
    capas.append(f'<path class="lago" d="{ruta(recortar(lagos, *vista))}"/>')
    capas.append(f'<path class="rio" d="{ruta(recortar(rios, *vista))}"/>')
    limites = unary_union([E.geom(g) for _, g in capa('limites')])
    capas.append(f'<path class="limite" d="{ruta(recortar(limites, *vista).simplify(0.06))}"/>')
    capas.append(f'<path class="costa" d="{ruta(recortar(tierra.boundary, *vista))}"/>')
    sh1, otras, numeradas = [], [], []
    for p, g in capa('linz/rutas'):
        g = E.geom(g)
        (sh1 if p['hway_num'] == '1' else otras).append(g)
        numeradas.append((p['hway_num'], g))
    ferry = [E.geom(g) for p, g in capa('rutas') if p.get('type') == 'Ferry Route']
    capas.append(f'<path class="ruta2" d="{ruta(recortar(unary_union(otras), *vista))}"/>')
    u1 = ruta(recortar(unary_union(sh1), *vista))
    capas.append(f'<path class="ruta1-borde" d="{u1}"/><path class="ruta1" d="{u1}"/>')
    capas.append(f'<path class="ferry" d="{ruta(recortar(unary_union(ferry), *vista))}"/>')
    interior = reg.boundary.difference(tierra.boundary.buffer(0.2))
    d_int = ruta(recortar(interior, *vista))
    capas.append(f'<path class="contorno-halo" d="{d_int}"/><path class="contorno" d="{d_int}"/>')

    col = Colocador(W, H)
    col.ocupar((W - 10, 3, W - 1, 19), 0)  # flecha del norte y su «N»
    textos = []
    nombres = tabla('mural').get('nombres', {})
    # Lugares para conocer: número en un círculo (fijos)
    ocupados = ([E.lonlat(c['lon'], c['lat']) for c in tabla('lugares')['lugares']]
                + [E.lonlat(pk['lon'], pk['lat']) for pk in tabla('rotulos')['picos']])
    for i, (n, _, lon, lat) in enumerate(r['naturaleza'], start=1):
        x, y = E.lonlat(lon, lat)
        if 3 < x < W - 3 and 3 < y < H - 3:
            if any(math.hypot(x - cx, y - cy) < 3.2 for cx, cy in ocupados):
                for dx, dy in ((3.8, -3.8), (-3.8, -3.8), (3.8, 3.8), (-3.8, 3.8), (5.2, 0), (-5.2, 0)):
                    if not any(math.hypot(x + dx - cx, y + dy - cy) < 3.4 for cx, cy in ocupados):
                        textos.append(f'<path class="lugar-guia" d="M{x:.2f} {y:.2f} L{x + dx:.2f} {y + dy:.2f}"/>')
                        x, y = x + dx, y + dy
                        break
            textos.append(f'<circle class="lugar-c" cx="{x:.2f}" cy="{y:.2f}" r="2.4"/>'
                          f'<text class="lugar-n" x="{x:.2f}" y="{y + 1.05:.2f}" text-anchor="middle">{i}</text>')
            col.ocupar((x - 2.5, y - 2.5, x + 2.5, y + 2.5), 0.2)
    lugares = []
    for c in tabla('lugares')['lugares']:
        x, y = E.lonlat(c['lon'], c['lat'])
        if 1.5 < x < W - 1.5 and 1.5 < y < H - 1.5:
            c = dict(c, n=nombres.get(c['n'], {}).get('t', c['n']))
            lugares.append((c, x, y))
            s = {1: 1.9, 2: 1.5, 3: 1.1, 4: 0.7}[c['cat']]
            textos.append(simbolo(x, y, c['cat']))
            col.ocupar((x - s, y - s, x + s, y + s), 0.2)
    for p in tabla('rotulos')['picos']:
        x, y = E.lonlat(p['lon'], p['lat'])
        if not (2 < x < W - 2 and 2 < y < H - 2):
            continue
        n = ingles(nombres.get(p['n'], {}).get('t', p['n']))
        textos.append(f'<path class="pico" d="M{x:.2f} {y - 1.3:.2f} L{x + 1.15:.2f} {y + 0.75:.2f} L{x - 1.15:.2f} {y + 0.75:.2f} Z"/>')
        col.ocupar((x - 1.2, y - 1.3, x + 1.2, y + 0.8), 0.2)
        alto = f'{p["h"]:,} m'.replace(',', '.')
        for dx, ancla in ((1.8, 'start'), (-1.8, 'end')):
            c1, c2 = caja('pico-n', x + dx, y - 0.2, n, ancla), caja('pico-n', x + dx, y + 3.0, alto, ancla)
            cc = (min(c1[0], c2[0]), c1[1], max(c1[2], c2[2]), c2[3])
            if col.libre(cc):
                col.ocupar(cc)
                textos.append(f'<text class="pico-n" x="{x + dx:.2f}" y="{y - 0.2:.2f}" text-anchor="{ancla}">{esc(n)}</text>'
                              f'<text class="pico-h" x="{x + dx:.2f}" y="{y + 3.0:.2f}" text-anchor="{ancla}">{alto}</text>')
                break
    orden = ['E', 'O', 'NE', 'SE', 'NO', 'SO', 'N', 'S']
    for c, x, y in sorted(lugares, key=lambda t: t[0]['cat']):
        cat = c['cat']
        for pos in [c['pos']] + [p for p in orden if p != c['pos']]:
            txt, tx, ty, ancla = rotulo_punto(x, y, c['n'], pos, SEP_CAT[cat], TAM_CAT[cat] * PT, f't{cat}')
            cc = caja(f't{cat}', tx, ty, c['n'], ancla)
            if col.libre(cc):
                col.ocupar(cc)
                textos.append(txt)
                break
    # Escudos de State Highway: uno por ruta en el tramo más largo que se ve
    for n, g in numeradas:
        partes = [p for p in getattr(recortar(g, 4, 4, W - 4, H - 4), 'geoms', [recortar(g, 4, 4, W - 4, H - 4)])
                  if not p.is_empty and p.length > 18]
        if not partes:
            continue
        parte = max(partes, key=lambda h: h.length)
        w = 1.9 * len(n) + 2.2
        for f in (0.5, 0.35, 0.65, 0.2, 0.8):
            pt = parte.interpolate(f, normalized=True)
            cc = (pt.x - w / 2, pt.y - 1.7, pt.x + w / 2, pt.y + 1.7)
            if col.libre(cc):
                col.ocupar(cc)
                clase = 'escudo sh1' if n == '1' else 'escudo'
                textos.append(f'<g class="{clase}"><rect x="{cc[0]:.2f}" y="{cc[1]:.2f}" width="{w:.2f}" height="3.4" rx="0.8"/>'
                              f'<text x="{pt.x:.2f}" y="{pt.y + 1.02:.2f}" text-anchor="middle">{n}</text></g>')
                break
    # Parques nacionales que se ven: nombre corto en verde, donde entre
    for n, g in parques:
        gg = recortar(g, 3, 3, W - 3, H - 3)
        if gg.is_empty or gg.area < 40:
            continue
        mayor = max(gg.geoms, key=lambda h: h.area) if gg.geom_type == 'MultiPolygon' else gg
        c = polylabel(mayor, tolerance=0.5)
        t = ingles(n.replace('National Park', 'NP').replace('/Tai Poutini NP', ' NP').split(' (')[0])
        cc = caja('parque-n', c.x, c.y, t, 'middle')
        if col.libre(cc):
            col.ocupar(cc)
            textos.append(f'<text class="parque-n" x="{c.x:.2f}" y="{c.y:.2f}" text-anchor="middle">{esc(t)}</text>')
    # Regiones vecinas y mares
    for p, g in capa('regiones'):
        if p['iso'] == iso:
            continue
        gg = recortar(E.geom(g), 3, 3, W - 3, H - 3)
        if gg.is_empty or gg.area < 120:
            continue
        mayor = max(gg.geoms, key=lambda h: h.area) if gg.geom_type == 'MultiPolygon' else gg
        if mayor.geom_type != 'Polygon':
            continue
        c = polylabel(mayor, tolerance=0.5)
        t = p['nombre'].upper()
        cc = caja('vecina', c.x, c.y, t, 'middle')
        if col.libre(cc):
            col.ocupar(cc)
            textos.append(f'<text class="vecina" x="{c.x:.2f}" y="{c.y:.2f}" text-anchor="middle">{esc(t)}</text>')
    for rt in tabla('rotulos')['rotulos']:
        if rt['clase'] not in ('agua', 'sierra', 'sierra-chica', 'isla', 'lago'):
            continue
        x, y = E.lonlat(rt['lon'], rt['lat'])
        t = ingles(nombres.get(rt['t'], {}).get('t', rt['t']))
        cc = caja(rt['clase'], x, y, t, 'middle', rt['rot'])
        if col.libre(cc):
            col.ocupar(cc)
            rot = f' transform="rotate({rt["rot"]} {x:.2f} {y:.2f})"' if rt['rot'] else ''
            textos.append(f'<text class="{rt["clase"]}" x="{x:.2f}" y="{y:.2f}" text-anchor="middle"{rot}>{esc(t)}</text>')
    capas += textos
    # Escala gráfica, en la primera esquina libre
    km = next(v for v in (5, 10, 20, 25, 50, 100) if v * 1000 * E.k >= 18)
    largo = km * 1000 * E.k
    # Recorre los bordes de abajo y de arriba hasta encontrar un hueco
    for ex, ey in [(x, y) for y in (H - 4, 9) for x in range(4, int(W - largo - 8), 6)]:
        if col.libre((ex - 1, ey - 8, ex + largo + 4, ey + 1)):
            break
    capas.append(f'<g class="escala"><path d="M{ex} {ey - 1} V{ey} H{ex + largo:.2f} V{ey - 1}"/>'
                 f'<text x="{ex}" y="{ey - 2}">0</text><text x="{ex + largo:.2f}" y="{ey - 2}" text-anchor="middle">{km} km</text></g>')
    capas.append(f'<g class="norte"><path d="M{W - 8} 14 L{W - 5.5} 6 L{W - 3} 14 L{W - 5.5} 12 Z"/>'
                 f'<text x="{W - 5.5}" y="18.5" text-anchor="middle">N</text></g>')
    return (f'<svg class="mapa mapa-region" viewBox="0 0 {W} {H}" style="width:{W}mm;height:{H}mm">\n'
            + '\n'.join(capas) + '\n</svg>')


FUENTE_SECTOR = {'aps2025': 'Stats NZ, encuesta agropecuaria, 30 jun. 2025.',
                 'aps2022': 'Stats NZ, censo agropecuario 2022.',
                 'bds2025': 'Stats NZ, demografía de empresas, feb. 2025.'}
ETIQUETAS = {'dato': 'dato oficial', 'est': 'estimación', 'calc': 'cálculo', 'rec': 'recomendación', 'ori': 'orientativo'}


def etq(tipo):
    return f'<span class="etq {tipo}" data-meta>{ETIQUETAS[tipo]}</span>'


# Referencia completa y enlace de cada cita abreviada, para NZ-A-fuentes (herramientas/fuentes_nz.py)
_REG = json.loads((RAIZ / 'datos' / 'regiones.json').read_text())['fuentes']
_SEC = json.loads((RAIZ / 'datos' / 'sectores-nz.json').read_text())['fuentes']
_CAL = json.loads((RAIZ / 'datos' / 'calendario-nz.json').read_text())['fuentes']
REFERENCIAS = {
    'Stats NZ, Censo 2023.': (_REG['censo'], 'https://www.stats.govt.nz/2023-census/'),
    'Stats NZ, encuesta agropecuaria, 30 jun. 2025.': (_SEC['aps2025'], 'https://figure.nz/'),
    'Stats NZ, censo agropecuario 2022.': (_SEC['aps2022'], 'https://figure.nz/'),
    'Stats NZ, demografía de empresas, feb. 2025.': (_SEC['bds2025'], 'https://figure.nz/'),
    'Te Ara, enciclopedia de NZ.': (_REG['iwi'], 'https://teara.govt.nz/'),
    'Work and Income, calendario de temporada; PickNZ.': (_CAL['winz-calendario'] + ' ' + _CAL['winz-general'] + ' ' + _CAL['picknz'],
                                                          'https://www.workandincome.govt.nz/work/find-jobs/where-to-look-for-jobs/seasonal-work-calendar.html'),
    'Tahatū Career Navigator (ex Careers NZ), perfiles de puestos; Site Safe; NZSki.': (
        'Tahatū Career Navigator (Tertiary Education Commission), perfiles de ocupaciones; Site Safe, Construction Passport; NZSki, empleos.',
        'https://tahatu.govt.nz/work/explore-career-ideas'),
    'Avisos de empleo de packhouses (Find a Job), oct. 2026.': (
        'Avisos de empleo de packhouses en Find a Job (Work and Income), consultados en oct. 2026. Ningún organismo publica '
        'fechas de la temporada de empaque; Tahatū y Work and Income tampoco.', 'https://new.my.msd.govt.nz/en/jobs.html'),
    'Tenancy Services, alquileres por bonos, jun. 2026.': (_REG['alquiler'] + ' Datos provisorios por la migración del sistema de bonos.',
                                                           'https://www.tenancy.govt.nz/about-tenancy-services/data-and-statistics/rental-bond-data/'),
    'Tenancy Services, alquileres de mercado, «Room», mar.–ago. 2026.': (
        'Tenancy Services, herramienta de alquileres de mercado, categoría «Room» («a room rented separately with shared facilities '
        'in a building intended for less than 6 people»), bonos activos de mar. a ago. 2026, por barrio.',
        'https://www.tenancy.govt.nz/rent-bond-and-bills/market-rent/'),
    'Tenancy Services, herramienta de alquileres de mercado, mar.–ago. 2026.': (
        'Tenancy Services, herramienta de alquileres de mercado, categoría «Room», mar.–ago. 2026: ningún barrio de la ciudad '
        'principal llega a 30 bonos activos.', 'https://www.tenancy.govt.nz/rent-bond-and-bills/market-rent/'),
    'Employment NZ, salario mínimo.': (_REG['salario'],
                                       'https://www.employment.govt.nz/pay-and-hours/pay-and-wages/minimum-wage/minimum-wage-rates-and-types'),
    'NIWA, normales climáticas 1991–2020 y 1981–2010.': (_REG['clima'], 'https://figure.nz/'),
}


class Fuentes:
    """Fuentes numeradas: cada bloque cita las suyas con un número que remite a la lista del dorso. Guarda además la
    referencia completa y el enlace de cada una, para NZ-A-fuentes."""

    def __init__(self):
        self.lista = []
        self.detalle = {}

    def __call__(self, texto, url=None, completo=None):
        if texto not in self.lista:
            self.lista.append(texto)
            ref = REFERENCIAS.get(texto, (texto, None))
            self.detalle[texto] = (completo or ref[0], url or ref[1])
        return f'<sup data-meta>{self.lista.index(texto) + 1}</sup>'

    def html(self):
        return ' · '.join(f'<span data-meta><b>{i}</b> {t.rstrip(".")}</span>' for i, t in enumerate(self.lista, start=1))


def sectores():
    return json.loads((RAIZ / 'datos' / 'sectores-nz.json').read_text())['sectores']


def rango(s, iso):
    v = s['porcentaje'].get(iso)
    return None if v is None else sorted((x for x in s['porcentaje'].values() if x is not None), reverse=True).index(v) + 1


def sectores_region(iso):
    """Sectores donde la región pesa: entre las 4 primeras del país. Construcción, transporte y técnicos
    quedan aparte porque siguen a la población."""
    filas = [(rango(s, iso), s['porcentaje'][iso], s) for s in sectores() if s['porcentaje'].get(iso) is not None]
    poblacion = {'construccion', 'transporte', 'tecnicos'}
    top = sorted([f for f in filas if f[0] <= 4 and f[2]['clave'] not in poblacion], key=lambda f: -f[1])
    resto = sorted([f for f in filas if f[2]['clave'] not in poblacion and f not in top], key=lambda f: -f[1])
    return (top + resto)[:max(3, min(4, len(top)))]


def destaca(iso, puesto=1):
    """Sectores en los que la región ocupa ese puesto en el país (cálculo sobre los datos de la tabla)."""
    return [(SECTOR_ES[s['clave']][0].lower(), s['fuente']) for s in sectores() if rango(s, iso) == puesto]


def calendario_region(r, claves):
    cal = json.loads((RAIZ / 'datos' / 'calendario-nz.json').read_text())
    filas = []
    for f in cal['filas']:
        if f['fuente'] == 'winz-calendario':
            if r['iso'] not in ZONA_REGION.get(f['zona'], []):
                continue
            etiqueta = f'{f["etiqueta"]} · {f["zona"]}'
        else:
            sec = f['sector']
            if sec == 'esqui':
                if r['iso'] not in CON_ESQUI:
                    continue
            elif GENERAL_SECTOR.get(sec) not in claves:
                continue
            etiqueta = ETIQUETA_ES.get(f['etiqueta'], f['etiqueta'])
        celdas = ''
        for m in f['meses']:
            if not m:
                celdas += '<td></td>'
                continue
            sector = {'turismo': 'alojamiento', 'esqui': 'alojamiento'}.get(f['sector'], f['sector'])
            celdas += f'<td class="si{" pico" if m["pico"] else ""}" style="background:var(--s-{sector})"></td>'
        filas.append(f'<tr><th>{glifo_html(f["sector"], 3.6)} {esc(etiqueta)}</th>{celdas}</tr>')
    return filas, cal


def frente(r, D, destino, F):
    codigo = f'NZ-A-{r["n"]:02d}'
    isla = 'North Island' if r['isla'] == 'norte' else 'South Island'
    dist = json.loads((DATOS / 'distancias-regiones.json').read_text())[r['iso']]
    vecinas = ', '.join(v['region'] for v in dist['vecinas'])
    puesto = min((rango(x, r['iso']) or 99) for x in sectores())  # el mejor puesto de la región en algún sector
    top = destaca(r['iso'], puesto) if puesto <= 4 else []
    destaque = '—'
    if top:
        partes = [f'{n}{F(FUENTE_SECTOR[f])}' for n, f in top]
        lista = ', '.join(partes[:-1]) + ' y ' + partes[-1] if len(partes) > 1 else partes[0]
        destaque = f'{puesto}.ª del país en {lista}'
    contexto = (f'<div><span data-meta>Población</span><b>{num(r["poblacion"])}</b>'
                f'<i>Censo 2023{F("Stats NZ, Censo 2023.")}</i></div>'
                f'<div><span data-meta>Superficie</span><b>{num(r["superficie"])} km²</b><i>{num(r["poblacion"] / r["superficie"], 1)} hab./km²</i></div>'
                f'<div><span data-meta>Ciudad principal</span><b>{esc(dist["ciudad"])}</b></div>'
                f'<div class="ancha"><span data-meta>Limita con</span><b class="chico">{esc(vecinas)}</b></div>'
                + (f'<div class="ancha"><span data-meta>Se destaca</span><b class="chico">{destaque}</b></div>' if top else ''))
    lugares = ''.join(f'<li><span class="num">{i}</span><span><b>{esc(ingles(n))}</b> {esc(d)}</span></li>'
                      for i, (n, d, _, _) in enumerate(r['naturaleza'], start=1))
    cur = json.loads((DATOS / 'curiosidades-regiones.json').read_text()).get(r['iso'])
    especie = ''
    if cur:
        hay = (RAIZ / 'imagenes' / cur['imagen'] / 'maestra.jpg').exists()
        dibujo = f'<img class="dibujo" src="{imagen_lapiz(cur["imagen"], 1400, vineta=0.12, fino=True)}" alt="">' if hay else ''
        especie = (f'<section class="especie{"" if hay else " sin-dibujo"}">{dibujo}<div><h2>{cur["titulo"]}</h2><p>{cur["texto"]}{F(cur["fuente_texto"], url=cur["fuente"])}</p>'
                   f'<p class="credito" data-meta>{cur["credito"]}</p></div></section>')
    mi = f'En māori, la región se llama <b>{esc(r["mi"])}</b>. ' if r.get('mi') else ''
    te_ara = F('Te Ara, enciclopedia de NZ.')
    return (f'<div class="hoja ficha2 mural" data-tinta-max="40">'
            '<header class="cabecera"><div>'
            f'<span class="coleccion">Atlas de Nueva Zelanda · región {r["n"]} de 16 · {isla}</span>'
            f'<h1>{esc(r["nombre"])}</h1><p class="bajada">{esc(r["rasgo"])}</p></div>'
            f'<div class="sello">{mapa_ubicacion(r["iso"])}<span class="n">{r["n"]}</span></div></header>'
            f'<div class="contexto">{contexto}</div>'
            f'{mapa(r, destino / "relieve" / f"{codigo}.jpg" if destino.name == "nz-a" else destino / f"{codigo}-relieve.jpg")}'
            f'<section class="conocer"><h2>Para conocer <span class="donde">los números del mapa</span></h2>'
            f'<ol class="lugares">{lugares}</ol></section>'
            '<div class="identidad">'
            f'<section class="cultura"><h2>Cultura māori</h2><p>{mi}Iwi: <b>{esc(", ".join(r["iwi"]))}</b>.</p>'
            f'<p>{esc(r["cultura"])}{te_ara}</p></section>{especie}</div>'
            f'<footer class="pie" data-meta><span>{codigo} · frente · v{VERSION} · {FECHA}</span>'
            f'<span>Mural NZ-A-00, pieza {pieza_mural(r)} · fuentes numeradas al dorso</span></footer></div>')


CULTIVO_ES = {'Apples': 'manzana', 'Pears': 'pera', 'Kiwifruit': 'kiwi', 'Berries': 'frutos rojos', 'Capsicum': 'pimiento',
              'Tomatoes': 'tomate', 'Grapes': 'uva', 'General vegetables': 'hortalizas', 'Apricots': 'damasco',
              'Nectarines': 'nectarina', 'Peaches': 'durazno', 'Plums': 'ciruela', 'Asparagus': 'espárrago',
              'Cherries': 'cereza', 'Avocado': 'palta', 'Citrus': 'cítricos', 'Kumara': 'batata',
              'Persimmons': 'caqui', 'Hops': 'lúpulo'}
TAREA_ES = {'C': 'cosecha', 'P': 'poda', 'R': 'raleo', 'M': 'mantenimiento'}
MES_ABR = ['ene.', 'feb.', 'mar.', 'abr.', 'may.', 'jun.', 'jul.', 'ago.', 'sep.', 'oct.', 'nov.', 'dic.']


def rango_meses(meses):
    """[2, 3, 4, 5] -> «feb.–may.»; los tramos pueden cruzar el año (dic.–feb.)."""
    if len(meses) == 12:
        return 'todo el año'
    tramos, actual = [], []
    for m in range(1, 13):
        if m in meses:
            actual.append(m)
        elif actual:
            tramos.append(actual)
            actual = []
    if actual:
        if tramos and tramos[0][0] == 1:
            tramos[0] = actual + tramos[0]
        else:
            tramos.append(actual)
    txt = [MES_ABR[t[0] - 1] if len(t) == 1 else f'{MES_ABR[t[0] - 1]}–{MES_ABR[t[-1] - 1]}' for t in tramos]
    return y_lista(txt)


def y_lista(cosas):
    return cosas[0] if len(cosas) == 1 else ', '.join(cosas[:-1]) + ' y ' + cosas[-1]


def cultivos_region(r, clave):
    """Cultivos que Work and Income publica para la región: uva para el viñedo, el resto para fruta y hortalizas.
    Los que comparten zonas y meses van juntos (manzana y pera)."""
    cal = json.loads((RAIZ / 'datos' / 'calendario-nz.json').read_text())
    grupos = {}
    for c in cal['por_region'].get(r['iso'], []):
        if (c['cultivo'] == 'Grapes') != (clave == 'vid'):
            continue
        g = grupos.setdefault((tuple(c['zonas']), json.dumps(c['meses'])), {'zonas': c['zonas'], 'meses': c['meses'], 'cultivos': []})
        g['cultivos'].append(CULTIVO_ES[c['cultivo']])
    return sorted(grupos.values(), key=lambda g: -sum(1 for m in g['meses'] if m and m['pico']))


def tira_meses(r, clave):
    """Franja de 12 meses de un puesto y detalle por cultivo, del calendario de Work and Income, o (None, '')."""
    if not clave:
        return None, ''
    if clave in ('fruta', 'vid'):
        grupos = cultivos_region(r, clave)
        if grupos:
            meses = [None] * 12
            for g in grupos:
                for i, m in enumerate(g['meses']):
                    if m:
                        meses[i] = {'pico': m['pico'] or bool(meses[i] and meses[i]['pico'])}
            frases = []
            for g in grupos[:3]:
                partes = []
                for t in 'CPRM':
                    todos = [i + 1 for i, m in enumerate(g['meses']) if m and m['t'][:1] == t]
                    pico = [i for i in todos if g['meses'][i - 1]['pico']]
                    if t == 'C' and todos:
                        partes.append(f'cosecha {rango_meses(todos)}' + (f', pico {rango_meses(pico)}' if pico and pico != todos else ''))
                    elif pico:
                        partes.append(f'{TAREA_ES[t]}, pico {rango_meses(pico)}')
                zonas = f' ({y_lista(g["zonas"])})' if len(g['zonas']) <= 3 else ''
                frases.append(f'{y_lista(g["cultivos"]).capitalize()}{zonas}: {"; ".join(partes).rstrip(".")}.')
            if len(grupos) > 3:
                frases.append(f'También {y_lista([c for g in grupos[3:] for c in g["cultivos"]])}.')
            sector = 'vid' if clave == 'vid' else 'fruta'
            celdas = ''.join('<i></i>' if not m else
                             f'<i class="si{" pico" if m["pico"] else ""}" style="background:var(--s-{sector})"></i>' for m in meses)
            return celdas, ' '.join(frases)
        if clave == 'fruta':
            return None, ''
    cal = json.loads((RAIZ / 'datos' / 'calendario-nz.json').read_text())
    for f in cal['filas']:
        if f['fuente'] == 'winz-general' and f['sector'] == clave:
            sector = {'turismo': 'alojamiento', 'esqui': 'alojamiento'}.get(f['sector'], f['sector'])
            return ''.join('<i></i>' if not m else
                           f'<i class="si{" pico" if m["pico"] else ""}" style="background:var(--s-{sector})"></i>'
                           for m in f['meses']), ''
    return None, ''


def dorso(r, D, F):
    codigo = f'NZ-A-{r["n"]:02d}'
    nombre = esc(r['nombre'])
    practico = json.loads((DATOS / 'fichas-practico.json').read_text())
    # 1. Sectores en los que la región destaca: participación en el total nacional de cada indicador
    sect = sectores_region(r['iso'])
    filas = ''
    for _, v, s in sect:
        k = s['clave']
        filas += (f'<div class="sec">{glifo_html(k, 5)}<div class="n">{SECTOR_ES[k][0]} <i>{SECTOR_ES[k][1]}</i>'
                  f'<small data-meta>{num(s["valores"][r["iso"]])} {s["unidad"]}{F(FUENTE_SECTOR[s["fuente"]])}</small></div>'
                  f'<span class="barra"><i style="width:{min(100, v * 2.2):.0f}%;background:var(--s-{k})"></i></span>'
                  f'<b>{num(v)} %<small class="r" data-meta>{rango(s, r["iso"])}.ª de 16</small></b></div>')
    sectores_html = (f'<section class="trabajo"><h2>Sectores en los que {nombre} destaca</h2>'
                     f'<p class="bajada">{etq("dato")} Participación de {nombre} en el total nacional de cada indicador. Las unidades cambian '
                     'entre sectores, y las barras no muestran cómo se reparte el empleo de la región.</p>'
                     f'<div class="sectores">{filas}</div></section>')
    # 2. Temporadas y puestos: cada puesto con sus meses, lo que suelen pedir y lo que hay que confirmar
    claves = {s['clave'] for _, _, s in sect}
    fuertes = {s['clave'] for s in sectores() if (rango(s, r['iso']) or 99) <= 4}
    con = claves | fuertes | ({'esqui'} if r['iso'] in CON_ESQUI else set())
    puestos = [x for x in practico['puestos'] if set(x['sectores']) & con][:MAX_PUESTOS]
    meses = ''.join(f'<span data-meta>{m}</span>' for m in MESES)
    filas_p = ''
    for x in puestos:
        tira, detalle = tira_meses(r, x.get('calendario'))
        tira = (f'<div class="tira">{tira}</div>' if tira
                else f'<div class="tira vacia" data-meta>{"Work and Income no la incluye" if x.get("calendario") else "todo el año"}</div>')
        detalle = f'<p class="cultivos">{detalle}</p>' if detalle else ''
        filas_p += (f'<div class="puesto"><div class="t"><b>{esc(x["titulo"])}</b> <span class="es">{esc(x["es"])}</span></div>{tira}'
                    f'{detalle}<p><span class="cont">{x["continuidad"].rstrip(".")}.</span> {x["requisitos"]}'
                    f'{" " + x["nota"] + F(x["fuente_nota"]) if x.get("nota") else ""}</p>'
                    f'<p class="confirmar"><span>Confirmá:</span> {x["confirmar"]}.</p></div>')
    temporadas = ('<section class="temporadas"><h2>Temporadas y puestos para investigar ' + etq('ori') + '</h2>'
                  '<p class="bajada">Meses con trabajo según Work and Income (no son fechas de contratación); '
                  'con borde, los de más trabajo. Requisitos: Tahatū Career Navigator'
                  f'{F("Work and Income, calendario de temporada; PickNZ.")}{F(practico["fuente_puestos"])}.</p>'
                  f'<div class="meses"><span></span><div>{meses}</div></div>{filas_p}'
                  f'<p class="nota">{etq("rec")} Buscá unas semanas antes de que empiece cada temporada. '
                  'Son pistas para investigar, no vacantes.</p></section>')
    # 3. Vivienda: alquiler local, con su categoría, su fecha y su estado provisional
    viv = practico.get('vivienda', {}).get(r['iso'], {})
    sal = practico['salario_minimo']
    casa = (f'<div><b>NZ$ {r["alquiler"]}</b><span>por semana: alquiler típico de la región (media geométrica). Nuevos contratos de alquiler '
            f'registrados (bonos), jun. 2026 {etq("dato")}{F("Tenancy Services, alquileres por bonos, jun. 2026.")}</span></div>')
    hab = ''
    horas = ''
    if viv.get('mediana'):
        hab = (f'<div><b>NZ$ {viv["mediana"]}</b><span>por semana: habitación alquilada sola, con cocina y baño compartidos '
               f'(«Room»), en {esc(viv["area"])}; mediana de mar.–ago. 2026, {viv["bonos"]} bonos activos {etq("dato")}'
               f'{F(viv["fuente"])}</span></div>')
        h = viv['mediana'] / sal['valor']
        horas = (f'<div><b>{num(h, 1)} h</b><span>equivalente en horas de salario mínimo adulto bruto: {viv["mediana"]} ÷ '
                 f'{num(sal["valor"], 2)} {etq("calc")}{F(sal["fuente"])}</span></div>')
    elif viv.get('sin_datos'):
        hab = (f'<div><b>s/d</b><span>habitación: no hay datos suficientes en {esc(viv["sin_datos"])} (menos de 30 contratos '
               f'por barrio) {etq("dato")}{F("Tenancy Services, herramienta de alquileres de mercado, mar.–ago. 2026.")}</span></div>')
    vivienda = (f'<section class="vivienda"><h2>Vivienda</h2><div class="cifras">{casa}{hab}{horas}</div>'
                '<p class="nota">Datos provisorios (Tenancy Services está migrando su sistema de bonos). Las horas comparan '
                'regiones: no son ingreso neto ni incluyen comida, transporte o servicios.</p></section>')
    # 4. Clima y movilidad
    es = r['estacion']
    otras = [x['estacion'] for x in D['regiones']]

    def puesto(clave, valor):
        orden = sorted({o[clave] for o in otras}, reverse=True)
        return orden.index(valor) + 1, len(orden)
    lugar = es['n'].replace(' (la más cercana)', '')
    pmx, n = puesto('max', es['max'])
    pmn, _ = puesto('min_jul', es['min_jul'])
    pll, _ = puesto('lluvia', es['lluvia'])
    clima = (f'<section class="clima-s"><h2>Clima <span class="donde">medido en {esc(lugar)}: no representa toda la región</span></h2>'
             f'<div class="clima fila3"><div><b><span class="ic sol"></span>{num(es["max"], 1)} °C</b><span>máxima media de '
             f'{es["mes_max"].lower()}; {pmx}.ª de {n}</span></div>'
             f'<div><b><span class="ic frio"></span>{num(es["min_jul"], 1)} °C</b><span>mínima media de julio; {pmn}.ª de {n}</span></div>'
             f'<div><b><span class="ic lluvia"></span>{num(es["lluvia"])} mm</b><span>de lluvia al año, en {es["dias"]} días; '
             f'{pll}.ª de {n}</span></div></div>'
             f'<p class="nota">{etq("dato")} Promedios 1991–2020 (días de lluvia: 1981–2010); puesto entre las {n} '
             f'estaciones del atlas{F("NIWA, normales climáticas 1991–2020 y 1981–2010.")}.</p></section>')
    dist = json.loads((DATOS / 'distancias-regiones.json').read_text())[r['iso']]
    km = ''.join(f'<li><b>{esc(v["ciudad"])}</b> <span>{v["km"]} km</span></li>' for v in dist['vecinas'] if v['km'])
    mov = practico['movilidad'].get(r['iso'], {})
    extras = ''.join(f'<p><b>{esc(k)}:</b> {v}</p>' for k, v, _ in mov.get('items', []))
    urbano = practico.get('urbano', {}).get(r['iso'])
    if urbano:
        extras += f'<p><b>En la ciudad:</b> {urbano}</p>'
    movilidad = ('<section class="movilidad"><h2>Movilidad</h2>'
                 f'<h3>Km desde {esc(dist["ciudad"])} {etq("calc")}{F("Cálculo propio sobre la red de rutas de LINZ (1:250k), redondeado a 5 km.", url='https://data.linz.govt.nz/layer/50184/', completo='Cálculo propio: camino más corto entre ciudades principales sobre la red de rutas de LINZ (Topo 1:250k, todas las rutas), redondeado a 5 km; ver herramientas/distancias-nz.py.')}</h3>'
                 f'<ul class="km">{km}</ul>{extras}'
                 f'<p class="nota">{etq("rec")} {practico["vehiculo"]}'
                 f'{F("Sitios oficiales de cada servicio de transporte.", completo='Conexiones: ' + ' '.join(f'{k}: {f}' for k, _, f in mov.get('items', [])))}</p></section>')
    return (f'<div class="hoja ficha2 mural dorso" data-tinta-max="40">'
            f'<header class="cabecera-dorso"><h1>{nombre}</h1><span>trabajo, vivienda, clima y movilidad</span>'
            f'<span class="cod" data-meta>{codigo} · dorso · v{VERSION} · {FECHA}</span></header>'
            f'<div class="columnas"><div class="izq">{sectores_html}{temporadas}'
            f'<p class="tipos" data-meta>{etq("dato")} organismo público · {etq("est")} aproximación · {etq("calc")} con datos '
            f'de la ficha · {etq("rec")} consejo · {etq("ori")} sin garantía</p></div>'
            f'<div class="der">{vivienda}{clima}{movilidad}'
            f'<section class="fuentes"><h2>Fuentes <span class="donde" data-meta>consultadas el 21 y 22 oct. 2026 · '
            f'con enlaces en NZ-A-fuentes.pdf</span></h2><p class="lista" data-meta>{F.html()} · Stats NZ y NIWA, '
            'vía Figure.NZ.</p></section></div></div></div>')


def ficha(r, D, destino, F=None):
    F = F if F is not None else Fuentes()
    cara = frente(r, D, destino, F)
    atras = dorso(r, D, F)
    return ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
            f'<title>NZ-A-{r["n"]:02d} {esc(r["nombre"])}</title>\n'
            '<link rel="stylesheet" href="../../estilo/combi.css">\n<link rel="stylesheet" href="../../estilo/atlas-nz.css">\n'
            '<link rel="stylesheet" href="../../estilo/mural-nz.css">\n<link rel="stylesheet" href="../../estilo/ficha-nz.css">\n'
            f'</head>\n<body>\n{cara}\n{atras}\n</body>\n</html>\n')


def fichas(destino, solo=None):
    """Las 16 fichas (o las de 'solo') en destino, con el alto de mapa y los puestos de datos/nz/fichas-ajuste.json."""
    global MAPA_H, MAX_PUESTOS
    D = datos()
    (destino / 'relieve').mkdir(parents=True, exist_ok=True)
    ajuste = json.loads((DATOS / 'fichas-ajuste.json').read_text())
    for r in D['regiones']:
        if solo and r['iso'] not in solo and str(r['n']) not in solo:
            continue
        a = ajuste.get(r['iso'], {})
        MAPA_H, MAX_PUESTOS = a.get('mapa', 114), a.get('puestos', 5)
        codigo = f'NZ-A-{r["n"]:02d}'
        (destino / f'{codigo}.html').write_text(ficha(r, D, destino))
        print(f'  {destino.relative_to(RAIZ)}/{codigo}.html')
    MAPA_H, MAX_PUESTOS = 114, 5


def desbordes(html):
    """(mm que el frente se pasa del margen, si la columna izquierda del dorso no entra), según construir.mjs."""
    import re
    import subprocess
    salida = subprocess.run(['node', str(RAIZ / 'herramientas' / 'construir.mjs'), str(html), '--forzar'],
                            capture_output=True, text=True).stdout
    pag1 = 'página 1: hay tinta' in salida
    peor = 0.0
    for linea in salida.splitlines():
        if 'fuera-de-margen' in linea and ('· frente ·' in linea or 'Mural NZ-A-00' in linea or pag1):
            m = re.search(r'queda a (-?[\d.]+) mm', linea)
            peor = max(peor, 8.2 - float(m.group(1)) if m else 20)  # 0,2 mm de holgura por redondeo
    izquierda = 'página 2: hay tinta' in salida and any('fuera-de-margen' in l and ('p.tipos' in l or 'etq.' in l)
                                                         for l in salida.splitlines())
    return peor, izquierda


if __name__ == '__main__':
    # Uso: python3 fichas_nz2.py CAN 14 ... [--ajustar]
    # --ajustar achica el mapa de cada ficha cuyo frente no entra y guarda el alto en datos/nz/fichas-ajuste.json
    D = datos()
    dest = RAIZ / 'salida' / 'pruebas'
    dest.mkdir(parents=True, exist_ok=True)
    archivo_ajuste = DATOS / 'fichas-ajuste.json'
    ajuste = json.loads(archivo_ajuste.read_text()) if archivo_ajuste.exists() else {}
    for r in D['regiones']:
        if r['iso'] in sys.argv[1:] or str(r['n']) in sys.argv[1:]:
            html = dest / f'NZ-A-{r["n"]:02d}.html'
            a = ajuste.get(r['iso'], {})
            MAPA_H, MAX_PUESTOS = a.get('mapa', 114), a.get('puestos', 5)
            html.write_text(ficha(r, D, dest))
            while '--ajustar' in sys.argv:
                falta, izquierda = desbordes(html)
                if falta <= 0 and (not izquierda or MAX_PUESTOS <= 3):
                    break
                if falta > 0:
                    MAPA_H -= math.ceil(falta + 0.5)
                if izquierda:
                    MAX_PUESTOS -= 1
                ajuste[r['iso']] = {'mapa': MAPA_H, 'puestos': MAX_PUESTOS}
                html.write_text(ficha(r, D, dest))
            print(f'  salida/pruebas/{html.name}  (mapa de {MAPA_H} mm, {MAX_PUESTOS} puestos)')
    if '--ajustar' in sys.argv:
        archivo_ajuste.write_text(json.dumps(dict(sorted(ajuste.items())), indent=1) + '\n')
