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
MAPA_W, MAPA_H = 190, 86
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
    capas.append(f'<path class="contorno" d="{ruta(recortar(interior, *vista))}"/>')

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
    cur = json.loads((DATOS / 'curiosidades-regiones.json').read_text()).get(iso, {})
    if cur.get('dibujo_mapa'):
        dx, dy, dw = cur['dibujo_mapa']
        src = imagen_lapiz(cur['imagen'], 900, vineta=0.3)
        capas.append(f'<image class="dibujo-mapa" href="{src}" x="{dx}" y="{dy}" width="{dw}"/>')
        col.ocupar((dx, dy, dx + dw, dy + dw * 0.66))
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
    return (f'<svg class="mapa mapa-region" viewBox="0 0 {W} {H}" style="width:{W}mm;height:{H}mm">\n'
            + '\n'.join(capas) + '\n</svg>')


def sectores_region(iso):
    """Sectores donde la región pesa: los que la ponen entre las 4 primeras del país, y si no hay, sus 3 mayores."""
    d = json.loads((RAIZ / 'datos' / 'sectores-nz.json').read_text())
    filas = []
    for s in d['sectores']:
        v = s['porcentaje'].get(iso)
        if v is None:
            continue
        rango = sorted((x for x in s['porcentaje'].values() if x is not None), reverse=True).index(v) + 1
        filas.append((rango, v, s['clave']))
    poblacion = {'construccion', 'transporte', 'tecnicos'}
    top = sorted([f for f in filas if f[0] <= 4 and f[2] not in poblacion], key=lambda f: -f[1])
    resto = sorted([f for f in filas if f[2] not in poblacion and f not in top], key=lambda f: -f[1])
    return (top + resto)[:max(3, min(5, len(top)))]


def bloque_trabajo(r):
    sect = sectores_region(r['iso'])
    filas = ''.join(
        f'<div class="sec">{glifo_html(k, 5)}<span class="n">{SECTOR_ES[k][0]} <i>{SECTOR_ES[k][1]}</i></span>'
        f'<span class="barra"><i style="width:{min(100, v * 2.2):.0f}%;background:var(--s-{k})"></i></span>'
        f'<b>{num(v)} %</b></div>' for _, v, k in sect)
    claves = {k for _, _, k in sect}
    cal = json.loads((RAIZ / 'datos' / 'calendario-nz.json').read_text())
    filas_cal = []
    for f in cal['filas']:
        if f['fuente'] == 'winz-calendario':
            if r['iso'] not in ZONA_REGION.get(f['zona'], []):
                continue
            etq = f['etiqueta']
        else:
            sec = f['sector']
            if sec == 'esqui':
                if r['iso'] not in CON_ESQUI:
                    continue
            elif GENERAL_SECTOR.get(sec) not in claves:
                continue
            etq = ETIQUETA_ES.get(f['etiqueta'], f['etiqueta'])
        celdas = ''
        for m in f['meses']:
            if not m:
                celdas += '<td></td>'
                continue
            sector = {'turismo': 'alojamiento', 'esqui': 'alojamiento'}.get(f['sector'], f['sector'])
            celdas += (f'<td class="si{" pico" if m["pico"] else ""}" style="background:var(--s-{sector})"></td>')
        filas_cal.append(f'<tr><th>{glifo_html(f["sector"], 3.6)} {esc(etq)}</th>{celdas}</tr>')
    cab = '<tr><th></th>' + ''.join(f'<td class="m" data-meta>{m}</td>' for m in MESES) + '</tr>'
    return ('<h2>Trabajo <span class="donde">qué parte de cada sector del país está acá</span></h2>'
            f'<div class="sectores">{filas}</div>'
            '<h3>Cuándo hay temporada</h3>'
            f'<table class="temporada">{cab}{"".join(filas_cal)}</table>'
            '<p class="nota">Orientativo (Work and Income); el recuadro marca los meses de más trabajo.</p>')


def bloque_plata(r, p):
    cuarto = round(r['alquiler'] / 3 / 5) * 5
    horas = cuarto / p['salario_minimo']
    return ('<h2>Plata</h2><div class="cifras">'
            f'<div><b>NZ$ {r["alquiler"]}</b><span>por semana, alquilar una casa entera (mediana, jun. 2026)</span></div>'
            f'<div><b>≈ NZ$ {cuarto}</b><span>un cuarto en casa compartida (estimado: un tercio)</span></div>'
            f'<div><b>{num(horas, 1)} h</b><span>de trabajo con salario mínimo para pagar ese cuarto</span></div></div>')


def bloque_clima(r, todas):
    es = r['estacion']
    otras = [x['estacion'] for x in todas]
    def puesto(clave, valor, alto, bajo):
        orden = sorted(o[clave] for o in otras)
        f = orden.index(valor) / max(1, len(orden) - 1)
        return alto if f > 0.66 else bajo if f < 0.34 else 'en el medio del país'
    lugar = es['n'].replace(' (la más cercana)', '')
    return (f'<h2>Clima <span class="donde">en {esc(lugar)}</span></h2><div class="clima">'
            f'<div><span class="ic sol"></span><b>{num(es["max"], 1)} °C</b><span>máxima de {es["mes_max"].lower()}: '
            f'{puesto("max", es["max"], "de las más calurosas", "de las más frescas")}</span></div>'
            f'<div><span class="ic frio"></span><b>{num(es["min_jul"], 1)} °C</b><span>mínima de julio: '
            f'{puesto("min_jul", es["min_jul"], "de las menos frías", "de las más frías")}</span></div>'
            f'<div><span class="ic lluvia"></span><b>{num(es["lluvia"])} mm</b><span>de lluvia por año, {es["dias"]} días: '
            f'{puesto("lluvia", es["lluvia"], "de las más lluviosas", "de las más secas")}</span></div></div>')


def bloque_lugares(r):
    items = ''.join(f'<li><span class="num">{i}</span><span><b>{esc(ingles(n))}</b> {esc(d)}</span></li>'
                    for i, (n, d, _, _) in enumerate(r['naturaleza'], start=1))
    return f'<h2>Para conocer</h2><ol class="lugares">{items}</ol>'


def bloque_curiosidad(r):
    cur = json.loads((DATOS / 'curiosidades-regiones.json').read_text()).get(r['iso'])
    if not cur:
        return ''
    dibujo = ('' if cur.get('dibujo_mapa') or not cur.get('imagen')
              else f'<img class="dibujo" src="{imagen_lapiz(cur["imagen"], 900, vineta=0.3)}" alt="">')
    return (f'{dibujo}<div class="texto"><h2>{cur["titulo"]}</h2><p>{cur["texto"]}</p>'
            f'<p class="credito" data-meta>{cur["credito"]}</p></div>')


def ficha(r, D, destino):
    p = D['pais']
    codigo = f'NZ-A-{r["n"]:02d}'
    svg = mapa(r, destino / f'{codigo}-relieve.jpg')
    isla = 'North Island' if r['isla'] == 'norte' else 'South Island'
    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{codigo} {esc(r["nombre"])}</title>
<link rel="stylesheet" href="../../estilo/combi.css">
<link rel="stylesheet" href="../../estilo/atlas-nz.css">
<link rel="stylesheet" href="../../estilo/mural-nz.css">
<link rel="stylesheet" href="../../estilo/ficha-nz.css">
</head>
<body>
<div class="hoja ficha2 mural" data-tinta-max="35">
  <header class="cabecera">
    <div>
      <span class="coleccion">Atlas de Nueva Zelanda · región {r["n"]} de 16 · {isla}</span>
      <h1>{esc(r["nombre"])}</h1>
      <p class="bajada">{esc(r["rasgo"])}</p>
      <p class="maori">{f'En māori: <b>{esc(r["mi"])}</b> · ' if r.get('mi') else ''}iwi: <b>{esc(", ".join(r["iwi"]))}</b></p>
    </div>
    <div class="lado">
      {mapa_ubicacion(r["iso"])}
      <div class="datos"><div><b>{num(r["poblacion"])}</b>habitantes</div><div><b>{num(r["superficie"])}</b>km²</div></div>
    </div>
  </header>
  {svg}
  <div class="abajo">
    <section class="trabajo">{bloque_trabajo(r)}</section>
    <div class="col">
      <section class="plata">{bloque_plata(r, p)}</section>
      <section class="clima-s">{bloque_clima(r, D["regiones"])}</section>
    </div>
  </div>
  <div class="abajo2">
    <section class="conocer">{bloque_lugares(r)}</section>
    <section class="curiosidad">{bloque_curiosidad(r)}<p class="cultura"><b>Cultura māori.</b> {esc(r["cultura"])}</p></section>
  </div>
  <footer class="pie" data-meta>
    <span>{codigo} · v{VERSION} · {FECHA} · mural NZ-A-00, pieza {pieza_mural(r)} · Fuentes: Stats NZ (Censo 2023, sectores
    2022–2025), Work and Income, NIWA 1991–2020, Tenancy Services (jun. 2026), Employment NZ, Te Ara, LINZ, DOC.</span>
  </footer>
</div>
</body>
</html>
'''


if __name__ == '__main__':
    D = datos()
    dest = RAIZ / 'salida' / 'pruebas'
    dest.mkdir(parents=True, exist_ok=True)
    for r in D['regiones']:
        if r['iso'] in sys.argv[1:] or str(r['n']) in sys.argv[1:]:
            (dest / f'NZ-A-{r["n"]:02d}.html').write_text(ficha(r, D, dest))
            print(f'  salida/pruebas/NZ-A-{r["n"]:02d}.html')
