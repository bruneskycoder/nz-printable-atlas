"""Fichas por región del atlas de Nueva Zelanda (NZ-A-01 a 16).

Una plantilla única, alimentada por datos/regiones.json. Los rótulos del mapa
regional se ubican con un colocador simple: prueba posiciones alrededor de
cada punto y descarta las que pisan algo ya ubicado.
"""
import json
import math

from shapely.ops import polylabel, unary_union

from atlas_nz import (MURAL_ESCALA, MURAL_X0, MURAL_Y0, PT, RAIZ, RELIEVE_ESCALA, RELIEVE_X0, RELIEVE_Y0, Encuadre,
                      caja_rotulo, capa, esc, recortar, relieve_ventana, rotulo_punto, ruta, tabla)

FECHA = '2026-10-17'
VERSION = 1
MAPA_W, MAPA_H = 122, 84
UBIC_W, UBIC_H = 26, 37
MESES = ['E', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
ESTILO = {
    'agua': (3.35, 'texto', 500, 0.15), 'lago': (3.0, 'texto', 500, 0), 'rio': (2.95, 'texto', 400, 0),
    'sierra': (5.3, 'titulo', 700, 1.4), 'sierra-chica': (3.0, 'texto', 700, 0.5), 'isla': (3.0, 'texto', 700, 0),
    'pico-n': (3.0, 'texto', 700, 0), 'vecina': (2.85, 'texto', 700, 0.4),
    't1': (4.94, 'titulo', 800, 0), 't2': (3.88, 'titulo', 700, 0), 't3': (3.35, 'texto', 700, 0), 't4': (2.95, 'texto', 400, 0),
}
SEP_CAT = {1: 3.0, 2: 2.4, 3: 2.0, 4: 1.4}
TAM_CAT = {1: 14, 2: 11, 3: 9.5, 4: 8.4}


def num(n, dec=0):
    """Número con punto de miles y coma decimal."""
    s = f'{n:,.{dec}f}'
    return s.replace(',', '§').replace('.', ',').replace('§', '.')


def datos():
    return json.loads((RAIZ / 'datos' / 'regiones.json').read_text())


# ---------------------------------------------------------------------------
class Colocador:
    """Guarda cajas ocupadas y dice si una nueva entra en el mapa sin pisar nada."""

    def __init__(self, w, h, margen=1.2):
        self.w, self.h, self.m = w, h, margen
        self.ocupadas = []

    def libre(self, c):
        x0, y0, x1, y1 = c
        if x0 < self.m or y0 < self.m or x1 > self.w - self.m or y1 > self.h - self.m:
            return False
        return not any(x0 < b[2] and b[0] < x1 and y0 < b[3] and b[1] < y1 for b in self.ocupadas)

    def ocupar(self, c, holgura=0.35):
        self.ocupadas.append((c[0] - holgura, c[1] - holgura, c[2] + holgura, c[3] + holgura))


def caja(clase, x, y, texto, ancla, rot=0):
    tam, cual, peso, esp = ESTILO[clase]
    return caja_rotulo(x, y, texto, ancla, tam, cual, peso, esp, rot)


def encuadre_region(geom_nztm):
    minx, miny, maxx, maxy = geom_nztm.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    ancho = max(maxx - minx, 70_000) * 1.12
    alto = max(maxy - miny, 60_000) * 1.12
    necesaria = max(ancho / MAPA_W, alto / MAPA_H) * 1000  # escala mínima
    escala = math.ceil(necesaria / 50_000) * 50_000  # redondeo a 50.000 hacia arriba
    m_por_mm = escala / 1000
    return Encuadre(escala, cx - MAPA_W / 2 * m_por_mm, cy + MAPA_H / 2 * m_por_mm)


def barra_escala(E, x=4, y=MAPA_H - 5):
    objetivo_km = 24 / (E.k * 1000)
    largo_km = next(v for v in (5, 10, 20, 25, 50, 75, 100, 150, 200) if v >= objetivo_km * 0.8)
    largo = largo_km * 1000 * E.k
    return (f'<rect x="{x - 1.5}" y="{y - 4.2}" width="{largo + 13}" height="6.2" style="fill:white;fill-opacity:0.85"/>'
            f'<path d="M{x} {y - 1} V{y} H{x + largo:.2f} V{y - 1}" style="fill:none;stroke:#000;stroke-width:0.35"/>'
            f'<text class="escala-t" x="{x}" y="{y - 1.6}">0</text>'
            f'<text class="escala-t" x="{x + largo:.2f}" y="{y - 1.6}" text-anchor="middle">{largo_km} km</text>'
            f'<text class="escala-t" x="{x + largo + 2.5:.2f}" y="{y + 0.4}">1:{num(E.escala)}</text>'), \
        (x - 1.5, y - 4.2, x + largo + 3.5 + caja('t4', 0, 0, '1:' + num(E.escala), 'start')[2], y + 2)


def mapa_region(r, destino_png):
    iso = r['iso']
    regiones = {p['iso']: g for p, g in capa('regiones')}
    E = encuadre_region(regiones[iso])
    W, H = MAPA_W, MAPA_H
    vista = (-1, -1, W + 1, H + 1)
    # Simplificación a la escala del mapa: 0,06 mm no se ve impreso y aliviana el PDF
    tierra = unary_union([E.geom(g) for _, g in capa('tierra')])
    tierra_v = recortar(tierra, -20, -20, W + 20, H + 20).simplify(0.06)
    reg = E.geom(regiones[iso]).simplify(0.06)
    capas = []
    relieve_ventana(0, 0, W, H, E, px_mm=0.15).save(destino_png, quality=88, optimize=True)
    capas.append(f'<image href="relieve/{destino_png.name}" x="0" y="0" width="{W}" height="{H}" preserveAspectRatio="none"/>')
    base = tierra_v.simplify(0.1)
    for i, d in enumerate((0.8, 1.8, 3.0), start=1):
        capas.append(f'<path class="ola o{i}" d="{ruta(recortar(base.buffer(d, quad_segs=3).boundary, *vista))}"/>')
    capas.append(f'<path class="velo" d="{ruta(recortar(tierra_v.difference(reg), *vista))}"/>')
    lagos = unary_union([E.geom(g) for _, g in capa('lagos')])
    rios = unary_union([E.geom(g) for _, g in capa('rios')]).intersection(tierra_v.buffer(0.2))
    capas.append(f'<path class="lago" d="{ruta(recortar(lagos, *vista))}"/>')
    capas.append(f'<path class="rio" d="{ruta(recortar(rios, *vista))}"/>')
    limites = unary_union([E.geom(g) for _, g in capa('limites')])
    capas.append(f'<path class="limite" d="{ruta(recortar(limites, *vista).simplify(0.06))}"/>')
    capas.append(f'<path class="costa" d="{ruta(recortar(tierra_v.boundary, *vista))}"/>')
    r1, r2, fe = [], [], []
    for p, g in capa('rutas'):
        g = E.geom(g)
        if p.get('type') == 'Ferry Route':
            fe.append(g)
        elif p.get('type') == 'Major Highway' or (p.get('scalerank') or 9) <= 4:
            r1.append(g)
        else:
            r2.append(g)
    for clase, gs in (('ruta2', r2), ('ruta1', r1), ('ferry', fe)):
        capas.append(f'<path class="{clase}" d="{ruta(recortar(unary_union(gs), *vista))}"/>')
    # Borde de la región solo tierra adentro: sobre la costa basta la línea de costa
    interior = reg.boundary.difference(tierra_v.boundary.buffer(0.2))
    capas.append(f'<path class="contorno" d="{ruta(recortar(interior, *vista))}"/>')

    col = Colocador(W, H)
    textos = []
    # Llamadas de naturaleza (fijas)
    fuera = []
    for i, (n, _, lon, lat) in enumerate(r['naturaleza'], start=1):
        x, y = E.lonlat(lon, lat)
        if not (3 < x < W - 3 and 3 < y < H - 3):
            fuera.append(i)
            continue
        # Si la llamada cae sobre una ciudad, se corre para no taparla
        cerca = [E.lonlat(c['lon'], c['lat']) for c in tabla('lugares')['lugares']]
        if any(math.hypot(x - cx, y - cy) < 3.2 for cx, cy in cerca):
            for dx, dy in ((3.6, -3.6), (-3.6, -3.6), (3.6, 3.6), (-3.6, 3.6), (5, 0), (-5, 0)):
                if not any(math.hypot(x + dx - cx, y + dy - cy) < 3.2 for cx, cy in cerca):
                    textos.append(f'<path d="M{x:.2f} {y:.2f} L{x + dx:.2f} {y + dy:.2f}" style="stroke:var(--ocre);stroke-width:0.35"/>')
                    x, y = x + dx, y + dy
                    break
        textos.append(f'<circle class="llamada" cx="{x:.2f}" cy="{y:.2f}" r="2.3"/>'
                      f'<text class="llamada-n" x="{x:.2f}" y="{y + 1.05:.2f}" text-anchor="middle">{i}</text>')
        col.ocupar((x - 2.4, y - 2.4, x + 2.4, y + 2.4), 0.2)
    # Símbolos de ciudades (fijos) y después sus rótulos
    lugares = []
    for c in tabla('lugares')['lugares']:
        x, y = E.lonlat(c['lon'], c['lat'])
        if 1.5 < x < W - 1.5 and 1.5 < y < H - 1.5:
            lugares.append((c, x, y))
            s = {1: 1.9, 2: 1.5, 3: 1.1, 4: 0.7}[c['cat']]
            textos.append(simbolo(x, y, c['cat']))
            col.ocupar((x - s, y - s, x + s, y + s), 0.2)
    # Barra de escala: la primera esquina libre de llamadas y ciudades
    for ex, ey in ((4, H - 5), (W - 44, H - 5), (4, 9), (W - 44, 9)):
        escala_svg, escala_caja = barra_escala(E, ex, ey)
        if col.libre(escala_caja):
            break
    col.ocupar(escala_caja)
    for p in tabla('rotulos')['picos']:
        x, y = E.lonlat(p['lon'], p['lat'])
        if not (2 < x < W - 2 and 2 < y < H - 2):
            continue
        textos.append(f'<path class="pico" d="M{x:.2f} {y - 1.3:.2f} L{x + 1.15:.2f} {y + 0.75:.2f} L{x - 1.15:.2f} {y + 0.75:.2f} Z"/>')
        col.ocupar((x - 1.2, y - 1.3, x + 1.2, y + 0.8), 0.2)
        alto = f'{p["h"]:,} m'.replace(',', '.')
        for dx, ancla in ((1.8, 'start'), (-1.8, 'end')):
            c1 = caja('pico-n', x + dx, y - 0.2, p['n'], ancla)
            c2 = caja('pico-n', x + dx, y + 3.0, alto, ancla)
            cc = (min(c1[0], c2[0]), c1[1], max(c1[2], c2[2]), c2[3])
            if col.libre(cc):
                col.ocupar(cc)
                textos.append(f'<text class="pico-n" x="{x + dx:.2f}" y="{y - 0.2:.2f}" text-anchor="{ancla}">{esc(p["n"])}</text>'
                              f'<text class="pico-h" x="{x + dx:.2f}" y="{y + 3.0:.2f}" text-anchor="{ancla}">{alto}</text>')
                break
    orden = ['E', 'O', 'NE', 'SE', 'NO', 'SO', 'N', 'S']
    for c, x, y in sorted(lugares, key=lambda t: t[0]['cat']):
        cat = c['cat']
        tam = TAM_CAT[cat] * PT
        preferidas = [c['pos']] + [p for p in orden if p != c['pos']]
        for pos in preferidas:
            txt, tx, ty, ancla = rotulo_punto(x, y, c['n'], pos, SEP_CAT[cat], tam, f't{cat}')
            cc = caja(f't{cat}', tx, ty, c['n'], ancla)
            if col.libre(cc):
                col.ocupar(cc)
                textos.append(txt)
                break
    # Rótulos de geografía (del mural) que entren sin pisar nada
    for rt in tabla('rotulos')['rotulos']:
        if rt['clase'] in ('mar', 'isla-grande', 'isla-grande-en'):
            continue
        x, y = E.lonlat(rt['lon'], rt['lat'])
        clase = 'lago' if rt['clase'] == 'lago' else rt['clase']
        cc = caja(clase, x, y, rt['t'], 'middle', rt['rot'])
        if col.libre(cc):
            col.ocupar(cc)
            rot = f' transform="rotate({rt["rot"]} {x:.2f} {y:.2f})"' if rt['rot'] else ''
            textos.append(f'<text class="{rt["clase"]}" x="{x:.2f}" y="{y:.2f}" text-anchor="middle"{rot}>{esc(rt["t"])}</text>')
    # Regiones vecinas, en gris
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
    capas.extend(textos)
    capas.append(escala_svg)
    capas.append(f'<rect class="marco" x="0.2" y="0.2" width="{W - 0.4}" height="{H - 0.4}"/>')
    svg = (f'<svg class="mapa mapa-region" viewBox="0 0 {W} {H}" style="width:{W}mm;height:{H}mm">\n'
           + '\n'.join(capas) + '\n</svg>')
    return svg, E, fuera


def simbolo(x, y, cat):
    if cat == 1:
        return f'<rect class="c1" x="{x - 1.9:.2f}" y="{y - 1.9:.2f}" width="3.8" height="3.8"/>'
    if cat == 2:
        return f'<circle class="c2" cx="{x:.2f}" cy="{y:.2f}" r="1.45"/>'
    if cat == 3:
        return f'<circle class="c3" cx="{x:.2f}" cy="{y:.2f}" r="1.05"/>'
    return f'<circle class="c4" cx="{x:.2f}" cy="{y:.2f}" r="0.62"/>'


def mapa_ubicacion(iso):
    E = Encuadre(40_000_000, 1_069_500, 6_211_500)
    partes = []
    for p, g in capa('regiones-chico'):
        clase = 'u-region' if p['iso'] == iso else 'u-otra'
        partes.append(f'<path class="{clase}" d="{ruta(E.geom(g), 2)}"/>')
    # La región va arriba para que su borde no quede tapado; si es muy chica, un círculo la señala
    partes.sort(key=lambda s: 'u-region' in s)
    g = [E.geom(g) for p, g in capa('regiones-chico') if p['iso'] == iso][0]
    if g.area < 2:
        c = g.centroid
        partes.append(f'<circle cx="{c.x:.2f}" cy="{c.y:.2f}" r="2.2" style="fill:none;stroke:var(--bermellon);stroke-width:0.5"/>')
    return (f'<svg class="mapa ubic" viewBox="0 0 {UBIC_W} {UBIC_H}" style="width:{UBIC_W}mm;height:{UBIC_H}mm">'
            + ''.join(partes) + '</svg>')


# ---------------------------------------------------------------------------
# Gráficos chicos
def barra(etq, valor, pais, maximo, unidad='%', clase='', tipo='dato'):
    w = 54  # mm reales: el SVG se dibuja a escala 1:1
    ancho = valor / maximo * w
    xp = pais / maximo * w
    v = f'{num(valor, 1)} {unidad}'.strip()
    marca = ' (cálculo)' if tipo == 'calculo' else ''
    return (f'<div class="barra"><span>{etq}</span>'
            f'<svg viewBox="0 0 {w} 8" style="width:{w}mm;height:8mm;overflow:visible">'
            f'<path class="eje" d="M0 4.6 H{w}"/>'
            f'<rect class="valor {clase}" x="0" y="2.4" width="{ancho:.2f}" height="2.2"/>'
            f'<path class="pais" d="M{xp:.2f} 1.2 V5.8"/>'
            f'<text x="{min(ancho, w - 18) + 1.5:.2f}" y="2" style="font-size:3.53px">{v}{marca}</text>'
            f'<text class="ref" x="{xp:.2f}" y="8.6" text-anchor="middle">NZ {num(pais, 1)}</text>'
            '</svg></div>')


def puntos(etq, valores, actual, lo, hi, clase, unidad, marcas):
    w = 58  # mm reales
    a = lambda v: (v - lo) / (hi - lo) * w
    otros = ''.join(f'<circle class="otro" cx="{a(v):.2f}" cy="3.2" r="0.9"/>' for v in valores)
    ejes = ''.join(f'<path class="eje" d="M{a(m):.2f} 4.4 V5.2"/><text x="{a(m):.2f}" y="7.6" text-anchor="middle">{num(m)}</text>'
                   for m in marcas)
    x = a(actual)
    ancla = 'end' if x > w * 0.8 else 'start'
    dx = -2.2 if ancla == 'end' else 2.2
    return (f'<div class="puntos"><span>{etq}</span>'
            f'<svg viewBox="0 0 {w} 8.4" style="width:{w}mm;height:8.4mm;overflow:visible">'
            f'<path class="eje" d="M0 4.4 H{w}"/>{ejes}{otros}'
            f'<circle class="este {clase}" cx="{x:.2f}" cy="3.2" r="1.5"/>'
            f'<text class="v" x="{x + dx:.2f}" y="2.1" text-anchor="{ancla}">{num(actual, 1 if isinstance(actual, float) and actual % 1 else 0)} {unidad}</text>'
            '</svg></div>')


# Rayado vectorial para las celdas de temporada: un degradé repetido de CSS
# Chromium lo pasa al PDF como una imagen de página entera por celda
RAYADO = ('<svg class="rayado" viewBox="0 0 8 4" preserveAspectRatio="none">'
          + ''.join(f'<path d="M{x} 4 L{x + 4} 0"/>' for x in (-3, -1, 1, 3, 5, 7)) + '</svg>')


def calendario(r, sectores):
    filas = []
    for clave, meses in r['trabajo']:
        if meses == 'todo':
            continue  # lo que dura todo el año va en la nota de abajo
        celdas = ''
        for m in range(1, 13):
            if meses == 'todo':
                celdas += '<td class="siempre"></td>'
            else:
                celdas += f'<td class="si">{RAYADO}</td>' if m in meses else '<td></td>'
        filas.append(f'<tr><td class="s">{esc(sectores[clave])}</td>{celdas}</tr>')
    cab = '<tr><th class="sector"></th>' + ''.join(f'<th data-meta>{m}</th>' for m in MESES) + '</tr>'
    return f'<table class="calendario">{cab}{"".join(filas)}</table>'


# ---------------------------------------------------------------------------
def pieza_mural(r):
    """Pieza del mural v2 (3 × 3 A4 verticales, paso de 180 × 267 mm) donde cae el centro de la región."""
    E = Encuadre(MURAL_ESCALA, MURAL_X0, MURAL_Y0)
    g = [E.geom(g) for p, g in capa('regiones') if p['iso'] == r['iso']][0]
    mayor = max(g.geoms, key=lambda h: h.area) if g.geom_type == 'MultiPolygon' else g
    c = polylabel(mayor, tolerance=0.5)
    col = min(2, int(c.x // 180))
    fila = min(2, int(c.y // 267))
    return fila * 3 + col + 1


def ficha(r, D, destino):
    p = D['pais']
    todas = D['regiones']
    codigo = f'NZ-A-{r["n"]:02d}'
    svg_mapa, E, fuera = mapa_region(r, destino / 'relieve' / f'{codigo}.jpg')
    densidad = r['poblacion'] / r['superficie']
    isla = 'Isla Norte' if r['isla'] == 'norte' else 'Isla Sur'
    mi = f'<i>{esc(r["mi"])}</i> · ' if r.get('mi') else ''

    # Gente
    distritos = ''.join(f'<span>{esc(n)}</span><span class="num-d">{num(v)}</span>' for n, v in r['distritos'][:4])
    edad = (f'<p>Edad mediana: <b>{num(r["edad_mediana"], 1)} años</b> (NZ: {num(p["edad_mediana"], 1)}).</p>'
            if r.get('edad_mediana') else '')
    grupo = ''
    if r.get('desempleo_grupo'):
        otras_g = [x.strip() for x in r['desempleo_grupo'].replace(' y ', ', ').split(',') if x.strip() != r['nombre']]
        grupo = f' Desempleo: dato conjunto con {esc(", ".join(otras_g[:-1]) + " y " + otras_g[-1] if len(otras_g) > 1 else otras_g[0])}.'
    gente = ('<h2>Gente y empleo <span class="tipo" data-meta>dato · la raya negra es NZ</span></h2>'
             + barra('Nacidos en el exterior', r['nacidos_exterior'], p['nacidos_exterior'], 60)
             + barra('Población māori', r['maori'], p['maori'], 60, clase='ocre', tipo=r.get('maori_tipo', 'dato'))
             + barra('Desempleo, mar. 2026', r['desempleo'], p['desempleo_mar2026'], 10, clase='rojo')
             + edad.replace('</p>', f'{grupo}</p>'))
    titulo_d = 'Distritos más poblados' if len(r['distritos']) > 1 else 'Un solo consejo para la región'
    bloque_distritos = f'<div class="cifra"><span class="h3">{titulo_d}</span><div class="distritos">{distritos}</div></div>'

    # Clima
    es = r['estacion']
    nota_est = ' Estación más cercana: Nelson.' if 'cercana' in es['n'] else ''
    otras = [x['estacion'] for x in todas if x['iso'] != r['iso'] and x['estacion']['n'] != es['n']]
    clima = (f'<h2>Clima en {esc(es["n"].replace(" (la más cercana)", ""))} <span class="tipo" data-meta>dato · NIWA 1991–2020</span></h2>'
             + puntos(f'Máxima en {es["mes_max"]}.', [o['max'] for o in otras], es['max'], 15, 30, 'calor', '°C', [15, 20, 25, 30])
             + puntos('Mínima de julio', [o['min_jul'] for o in otras], es['min_jul'], -3, 12, 'frio', '°C', [0, 5, 10])
             + puntos('Lluvia por año', [o['lluvia'] for o in otras], es['lluvia'], 0, 3000, 'agua', 'mm', [0, 1000, 2000, 3000])
             + f'<p>Llueve unos <b>{es["dias"]} días por año</b> (1981–2010).{nota_est} Los puntos grises son las otras regiones.</p>')

    # Trabajo y plata
    trabajo = ('<h2>Trabajo por temporada <span class="tipo" data-meta>estimación</span></h2>'
               + calendario(r, D['sectores'])
               + '<p class="leyenda-tipos" data-meta>Rayado: meses de más demanda, aproximados; cambian cada año. '
                 'Todo el año: hotelería y gastronomía.</p>')
    cuarto = round(r['alquiler'] / 3 / 5) * 5
    horas = cuarto / p['salario_minimo']
    plata = ('<h2>Plata</h2><div class="plata">'
             f'<div class="item"><b>NZ$ {r["alquiler"]}</b><span>por semana: alquiler mediano de una vivienda, junio 2026'
             '<span class="etq dato" data-meta>dato</span></span></div>'
             f'<div class="item est"><b>NZ$ {cuarto}</b><span>un cuarto en casa compartida: un tercio de la vivienda'
             '<span class="etq est" data-meta>estimación</span></span></div>'
             f'<div class="item"><b>{num(horas, 1)} h</b><span>de salario mínimo (NZ$ {num(p["salario_minimo"], 2)}/h) para pagar ese cuarto'
             '<span class="etq calc" data-meta>cálculo</span></span></div>'
             '</div>')

    # Naturaleza y cultura māori
    items = []
    for i, (n, d, _, _) in enumerate(r['naturaleza'], start=1):
        nota = ' <span class="gris">(fuera del mapa)</span>' if i in fuera else ''
        items.append(f'<li><span class="num">{i}</span><span><b>{esc(n)}</b>: {esc(d)}{nota}</span></li>')
    natu = '<h2>Naturaleza y actividades</h2><ol class="natu">' + ''.join(items) + '</ol>'
    maori = ('<h2>Iwi y cultura māori <span class="tipo" data-meta>Te Ara</span></h2>'
             + f'<p class="iwi"><b>Iwi:</b> {esc(", ".join(r["iwi"]))}.</p>'
             + f'<p>{esc(r["cultura"])}</p>')

    cifras = (f'<div class="cifra grande"><b>{num(r["poblacion"])}</b><span>habitantes (Censo 2023)</span></div>'
              f'<div class="cifra"><b>{num(r["superficie"])} km²</b><span>{num(densidad, 1)} hab. por km² '
              '<span class="etq calc" data-meta>cálculo</span></span></div>')

    return f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>{codigo} {esc(r["nombre"])}</title>
<link rel="stylesheet" href="../../estilo/combi.css">
<link rel="stylesheet" href="../../estilo/atlas-nz.css">
</head>
<body>
<div class="hoja ficha">
  <header class="cabecera">
    <div class="codigo">{codigo}</div>
    <div>
      <span class="coleccion">Atlas de Nueva Zelanda · región {r["n"]} de 16 · {isla}</span>
      <h1 class="titulo">{esc(r["nombre"])}</h1>
      <p class="bajada">{mi}{esc(r["rasgo"])}</p>
    </div>
    <div class="lateral">Mapa mural: NZ-A-00, pieza {pieza_mural(r)}<br>Comparar regiones: NZ-A-99</div>
  </header>

  <main class="cuerpo">
    <div class="fila fila-a" data-hero>
      {svg_mapa}
      <div class="lado">
        {mapa_ubicacion(r["iso"])}
        <div class="cifras">{cifras}</div>
        {bloque_distritos}
      </div>
    </div>
    <div class="fila fila-b">
      <section>{gente}</section>
      <section>{clima}</section>
    </div>
    <div class="fila fila-c">
      <section>{trabajo}</section>
      <section>{plata}</section>
    </div>
    <div class="fila fila-d">
      <section>{natu}</section>
      <section>{maori}</section>
    </div>
  </main>

  <footer class="pie">
    <span>{codigo} · versión {VERSION} · {FECHA}</span>
    <span class="fuentes">Población, nacidos en el exterior, edad y māori: Stats NZ, Censo 2023. Clima: NIWA, promedios 1991–2020 (vía Figure.NZ). Alquiler: Tenancy Services, bonos de junio 2026. Desempleo: Stats NZ, encuesta de fuerza laboral, mar. 2026. Salario mínimo: Employment NZ. Iwi: Te Ara. Mapa: Stats NZ (geoBoundaries), Natural Earth, relieve LINZ. Trabajo por temporada y cuarto: estimaciones. Consultado el {FECHA}.</span>
    <span>Enciclopedia para imprimir</span>
  </footer>
</div>
</body>
</html>
'''


def fichas(destino, solo=None):
    D = datos()
    (destino / 'relieve').mkdir(parents=True, exist_ok=True)
    for r in D['regiones']:
        if solo and r['iso'] not in solo and str(r['n']) not in solo:
            continue
        codigo = f'NZ-A-{r["n"]:02d}'
        (destino / f'{codigo}.html').write_text(ficha(r, D, destino))
        print(f'  hojas/nz-a/{codigo}.html')
