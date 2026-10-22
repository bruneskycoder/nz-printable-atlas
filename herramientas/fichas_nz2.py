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
    capas = [f'<image href="{destino_jpg.name}" x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="none"/>']
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


FUENTE_SECTOR = {'aps2025': 'Stats NZ, encuesta agropecuaria (30 jun. 2025), vía Figure.NZ.',
                 'aps2022': 'Stats NZ, censo agropecuario 2022, vía Figure.NZ.',
                 'bds2025': 'Stats NZ, demografía de empresas (feb. 2025), vía Figure.NZ.'}
ETIQUETAS = {'dato': 'dato oficial', 'est': 'estimación', 'calc': 'cálculo', 'rec': 'recomendación', 'ori': 'orientativo'}


def etq(tipo):
    return f'<span class="etq {tipo}" data-meta>{ETIQUETAS[tipo]}</span>'


class Fuentes:
    """Fuentes numeradas: cada bloque cita las suyas con un número que remite a la lista del dorso."""

    def __init__(self):
        self.lista = []

    def __call__(self, texto):
        if texto not in self.lista:
            self.lista.append(texto)
        return f'<sup data-meta>{self.lista.index(texto) + 1}</sup>'

    def html(self):
        return ' '.join(f'<span data-meta><b>{i}</b> {t}</span>' for i, t in enumerate(self.lista, start=1))


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
    return (top + resto)[:max(3, min(5, len(top)))]


def destaca(iso):
    """Sectores en los que la región es la primera del país (cálculo sobre los datos de la tabla)."""
    return [(SECTOR_ES[s['clave']][0].lower(), s['fuente']) for s in sectores() if rango(s, iso) == 1]


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
    top = destaca(r['iso'])
    destaque = '—'
    if top:
        partes = [f'{n}{F(FUENTE_SECTOR[f])}' for n, f in top]
        lista = ', '.join(partes[:-1]) + ' y ' + partes[-1] if len(partes) > 1 else partes[0]
        destaque = f'1.ª del país en {lista}'
    contexto = (f'<div><span data-meta>Población</span><b>{num(r["poblacion"])}</b>'
                f'<i>Censo 2023{F("Stats NZ, Censo 2023: población por consejo regional.")}</i></div>'
                f'<div><span data-meta>Superficie</span><b>{num(r["superficie"])} km²</b><i>{num(r["poblacion"] / r["superficie"], 1)} hab./km²</i></div>'
                f'<div><span data-meta>Ciudad principal</span><b>{esc(dist["ciudad"])}</b></div>'
                f'<div class="ancha"><span data-meta>Limita con</span><b class="chico">{esc(vecinas)}</b></div>'
                f'<div class="ancha"><span data-meta>Se destaca</span><b class="chico">{destaque}</b></div>')
    lugares = ''.join(f'<li><span class="num">{i}</span><span><b>{esc(ingles(n))}</b> {esc(d)}</span></li>'
                      for i, (n, d, _, _) in enumerate(r['naturaleza'], start=1))
    cur = json.loads((DATOS / 'curiosidades-regiones.json').read_text()).get(r['iso'])
    especie = ''
    if cur:
        dibujo = f'<img class="dibujo" src="{imagen_lapiz(cur["imagen"], 1400, vineta=0.12, fino=True)}" alt="">'
        especie = (f'<section class="especie">{dibujo}<div><h2>{cur["titulo"]}</h2><p>{cur["texto"]}{F(cur["fuente_texto"])}</p>'
                   f'<p class="credito" data-meta>{cur["credito"]}</p></div></section>')
    mi = f'En māori, la región se llama <b>{esc(r["mi"])}</b>. ' if r.get('mi') else ''
    te_ara = F('Te Ara, la enciclopedia de Nueva Zelanda: iwi y cultura de la región.')
    return (f'<div class="hoja ficha2 mural" data-tinta-max="40">'
            '<header class="cabecera"><div>'
            f'<span class="coleccion">Atlas de Nueva Zelanda · región {r["n"]} de 16 · {isla}</span>'
            f'<h1>{esc(r["nombre"])}</h1><p class="bajada">{esc(r["rasgo"])}</p></div>'
            f'<div class="sello">{mapa_ubicacion(r["iso"])}<span class="n">{r["n"]}</span></div></header>'
            f'<div class="contexto">{contexto}</div>'
            f'{mapa(r, destino / f"{codigo}-relieve.jpg")}'
            f'<section class="conocer"><h2>Para conocer <span class="donde">los números del mapa</span></h2>'
            f'<ol class="lugares">{lugares}</ol></section>'
            '<div class="identidad">'
            f'<section class="cultura"><h2>Cultura māori</h2><p>{mi}Iwi: <b>{esc(", ".join(r["iwi"]))}</b>.</p>'
            f'<p>{esc(r["cultura"])}{te_ara}</p></section>{especie}</div>'
            f'<footer class="pie" data-meta><span>{codigo} · frente · v{VERSION} · {FECHA}</span>'
            f'<span>Mural NZ-A-00, pieza {pieza_mural(r)} · fuentes numeradas al dorso</span></footer></div>')


def dorso(r, D, F):
    p = D['pais']
    codigo = f'NZ-A-{r["n"]:02d}'
    practico = json.loads((DATOS / 'fichas-practico.json').read_text())
    # Trabajo: qué mide cada porcentaje, con su unidad, su año y su fuente
    sect = sectores_region(r['iso'])
    filas = ''
    for _, v, s in sect:
        k = s['clave']
        filas += (f'<div class="sec">{glifo_html(k, 5)}<div class="n">{SECTOR_ES[k][0]} <i>{SECTOR_ES[k][1]}</i>'
                  f'<small data-meta>{num(s["valores"][r["iso"]])} {s["unidad"]}{F(FUENTE_SECTOR[s["fuente"]])}</small></div>'
                  f'<span class="barra"><i style="width:{min(100, v * 2.2):.0f}%;background:var(--s-{k})"></i></span>'
                  f'<b>{num(v)} %<small class="r" data-meta>{rango(s, r["iso"])}.ª de 16</small></b></div>')
    claves = {s['clave'] for _, _, s in sect}
    fuertes = {s['clave'] for s in sectores() if (rango(s, r['iso']) or 99) <= 4}
    con = claves | fuertes | ({'esqui'} if r['iso'] in CON_ESQUI else set())
    puestos = [x for x in practico['puestos'] if set(x['sectores']) & con][:5]
    tabla_p = ''.join(f'<div class="puesto"><div class="t"><b>{esc(x["titulo"])}</b> <span class="es">{esc(x["es"])}</span></div>'
                      f'<p><span class="cont">{x["continuidad"]}.</span> {x["requisitos"]}</p></div>' for x in puestos)
    fuente_p = F(practico['fuente_puestos'])
    filas_cal, cal = calendario_region(r, claves)
    cab = '<tr><th></th>' + ''.join(f'<td class="m" data-meta>{m}</td>' for m in MESES) + '</tr>'
    fuente_cal = F('Work and Income, calendario de temporada; PickNZ.')
    trabajo = ('<section class="trabajo"><h2>Trabajo</h2>'
               f'<h3>De qué vive la región {etq("dato")}</h3>'
               '<p class="bajada">Parte del total del país; cada sector se mide distinto.</p>'
               f'<div class="sectores">{filas}</div>'
               f'<h3>Puestos de entrada para investigar {etq("ori")}{fuente_p}</h3>'
               f'<div class="puestos">{tabla_p}</div>'
               '<p class="nota">Es una línea de investigación, no una lista de vacantes: confirmalo en avisos actuales.</p>'
               f'<h3>Cuándo hay temporada {etq("ori")}{fuente_cal}</h3>'
               f'<table class="temporada">{cab}{"".join(filas_cal)}</table>'
               '<p class="leyenda-cal"><span class="mu"></span> con trabajo <span class="mu pico"></span> meses pico. '
               f'{etq("rec")} Se contrata antes de que empiece la temporada: buscá unas semanas antes. Cambia cada año y no '
               'garantiza trabajo.</p></section>')
    # Plata: dato, estimación y cálculo separados y a la vista
    sal, cu = practico['salario_minimo'], practico['cuarto']
    cuarto = cu['mediana']
    horas = cuarto / sal['valor']
    plata = ('<section class="plata"><h2>Plata</h2><div class="cifras">'
             f'<div><b>NZ$ {r["alquiler"]}</b><span>por semana: casa entera, mediana de la región (bonos nuevos, jun. 2026) '
             f'{etq("dato")}{F("Tenancy Services, datos de alquiler por bonos, junio 2026.")}</span></div>'
             f'<div><b>NZ$ {cuarto}</b><span>por semana: cuarto compartido, mediana de todo el país ({cu["periodo"]}); no hay '
             f'dato por región {etq("dato")}{F(cu["fuente"])}</span></div>'
             f'<div><b>NZ$ {num(sal["valor"], 2)}</b><span>por hora: salario mínimo adulto, bruto, desde {sal["desde"]} '
             f'{etq("dato")}{F(sal["fuente"])}</span></div>'
             f'<div><b>{num(horas, 1)} h</b><span>de salario mínimo bruto pagan el cuarto ({cuarto} ÷ {num(sal["valor"], 2)}) '
             f'{etq("calc")}</span></div></div>'
             '<p class="nota">Muchos cuartos no registran bono: el precio real varía. Sumá comida, transporte, teléfono y servicios.</p>'
             '</section>')
    # Clima: de qué estación, qué variable, qué período y contra qué se compara
    es = r['estacion']
    otras = [x['estacion'] for x in D['regiones']]

    def puesto(clave, valor):
        orden = sorted({o[clave] for o in otras}, reverse=True)
        return orden.index(valor) + 1, len(orden)
    lugar = es['n'].replace(' (la más cercana)', '')
    pmx, n = puesto('max', es['max'])
    pmn, _ = puesto('min_jul', es['min_jul'])
    pll, _ = puesto('lluvia', es['lluvia'])
    clima = (f'<section class="clima-s"><h2>Clima <span class="donde">en {esc(lugar)}, promedios 1991–2020</span></h2>'
             f'<div class="clima"><div><span class="ic sol"></span><b>{num(es["max"], 1)} °C</b><span>máxima media de '
             f'{es["mes_max"].lower()}: {pmx}.ª más alta de las {n} estaciones del atlas</span></div>'
             f'<div><span class="ic frio"></span><b>{num(es["min_jul"], 1)} °C</b><span>mínima media de julio: {pmn}.ª más alta de {n}</span></div>'
             f'<div><span class="ic lluvia"></span><b>{num(es["lluvia"])} mm</b><span>de lluvia por año, en {es["dias"]} días: '
             f'{pll}.ª más lluviosa de {n}</span></div></div>'
             f'<p class="nota">Es el clima de {esc(lugar)}, no el de toda la región {etq("dato")}'
             f'{F("NIWA, normales climáticas 1991–2020 (días de lluvia: 1981–2010), vía Figure.NZ.")}</p></section>')
    # Movilidad
    dist = json.loads((DATOS / 'distancias-regiones.json').read_text())[r['iso']]
    km = ''.join(f'<li><b>{esc(v["ciudad"])}</b> <span>{v["km"]} km</span></li>' for v in dist['vecinas'] if v['km'])
    mov = practico['movilidad'].get(r['iso'], {})
    extras = ''.join(f'<p><b>{esc(k)}:</b> {v}</p>' for k, v, f in mov.get('items', []))
    if extras:
        extras += f'<p class="nota" data-meta>Conexiones: sitios oficiales de aeropuertos, KiwiRail, InterCity y ferris{F("Sitios oficiales de aeropuertos, Great Journeys NZ (KiwiRail), InterCity, Interislander, Bluebridge y RealNZ.")}</p>'
    movilidad = ('<section class="movilidad"><h2>Movilidad</h2>'
                 f'<h3>De {esc(dist["ciudad"])} a las ciudades vecinas, por ruta {etq("calc")}'
                 f'{F("Cálculo propio sobre la red de rutas de LINZ (1:250k), redondeado a 5 km.")}</h3>'
                 f'<ul class="km">{km}</ul>{extras}</section>')
    return (f'<div class="hoja ficha2 mural dorso" data-tinta-max="40">'
            f'<header class="cabecera-dorso"><h1>{esc(r["nombre"])}</h1><span>trabajo, plata, clima y movilidad</span>'
            f'<span class="cod" data-meta>{codigo} · dorso · v{VERSION} · {FECHA}</span></header>'
            f'<div class="columnas"><div class="izq">{trabajo}'
            f'<p class="tipos" data-meta>{etq("dato")} de un organismo oficial · {etq("est")} aproximación con supuestos a la vista · '
            f'{etq("calc")} cuenta con datos de la ficha · {etq("rec")} consejo práctico · {etq("ori")} útil, sin garantía.</p></div>'
            f'<div class="der">{plata}{clima}{movilidad}'
            f'<section class="fuentes"><h2>Fuentes <span class="donde" data-meta>consultadas entre el 2026-10-21 y el {FECHA}</span></h2>'
            f'<p class="lista">{F.html()}</p></section></div></div>'
            '</div>')


def ficha(r, D, destino):
    F = Fuentes()
    cara = frente(r, D, destino, F)
    atras = dorso(r, D, F)
    return ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
            f'<title>NZ-A-{r["n"]:02d} {esc(r["nombre"])}</title>\n'
            '<link rel="stylesheet" href="../../estilo/combi.css">\n<link rel="stylesheet" href="../../estilo/atlas-nz.css">\n'
            '<link rel="stylesheet" href="../../estilo/mural-nz.css">\n<link rel="stylesheet" href="../../estilo/ficha-nz.css">\n'
            f'</head>\n<body>\n{cara}\n{atras}\n</body>\n</html>\n')


if __name__ == '__main__':
    D = datos()
    dest = RAIZ / 'salida' / 'pruebas'
    dest.mkdir(parents=True, exist_ok=True)
    for r in D['regiones']:
        if r['iso'] in sys.argv[1:] or str(r['n']) in sys.argv[1:]:
            (dest / f'NZ-A-{r["n"]:02d}.html').write_text(ficha(r, D, dest))
            print(f'  salida/pruebas/NZ-A-{r["n"]:02d}.html')
