#!/usr/bin/env python3
"""Genera las hojas del atlas de Nueva Zelanda (lote 6).

    python3 herramientas/generar-atlas.py mural    # NZ-A-00-1 a 9 (mapa mural, 3 × 3 A4 verticales)
    python3 herramientas/generar-atlas.py mural-previa [--sin-juntas]   # el mural en una sola página
    python3 herramientas/generar-atlas.py fichas   # NZ-A-01 a 16 (una por región)
    python3 herramientas/generar-atlas.py matriz   # NZ-A-99 (¿dónde ir?)

Después: node herramientas/construir.mjs hojas/nz-a/*.html
Datos: datos/nz/ (geografía, ver geo-nz.py) y datos/regiones.json (cifras con fuente).
"""
import json
import re
import sys

from shapely.geometry import LineString, box
from shapely.ops import polylabel, unary_union

from atlas_nz import (MURAL_ESCALA, MURAL_X0, MURAL_Y0, ORDEN_REGIONES, PT, RAIZ, Encuadre, caja_rotulo, capa,
                      esc, nombre_region, recortar, relieve_mural_ventana, rotulo_punto, ruta, tabla)
from bloques_mural import GLIFOS_MAPA, principales
from glifos import glifo_svg

FECHA = '2026-10-21'
VERSION = 2
DESTINO = RAIZ / 'hojas' / 'nz-a'

# ---------------------------------------------------------------------------
# Mural v2: 9 A4 verticales en 3 columnas × 3 filas, solapa de 10 mm.
# La pieza de la derecha va encima de la de la izquierda y la fila de abajo
# encima de la de arriba: cada pieza tapa la franja «pegar acá» de su vecina.
COLS, FILAS = 3, 3
IMG_W, IMG_H = 190, 277          # zona impresa de cada pieza (A4 vertical menos 10 mm de margen)
SOLAPA = 10
PASO_X, PASO_Y = IMG_W - SOLAPA, IMG_H - SOLAPA
MURAL_W = COLS * IMG_W - (COLS - 1) * SOLAPA    # 550 mm
MURAL_H = FILAS * IMG_H - (FILAS - 1) * SOLAPA  # 811 mm
PIEZAS = COLS * FILAS
JUNTAS_X = [k * PASO_X for k in range(1, COLS)]
JUNTAS_Y = [k * PASO_Y for k in range(1, FILAS)]
E_MURAL = Encuadre(MURAL_ESCALA, MURAL_X0, MURAL_Y0)

# Ajuste (mm a 1:2.100.000) del rótulo de región respecto del punto más interior
# del polígono; se escala al mural v2 para conservar el mismo lugar en el terreno
AJUSTE_REGION = {
    'NTL': (4, 4), 'AUK': (-16, -2), 'WKO': (-6, 2), 'BOP': (8, -3), 'GIS': (0, 2), 'HKB': (2, 0),
    'TKI': (4, 6), 'MWT': (6, -12), 'WGN': (8, 10), 'TAS': (-6, 0), 'NLS': (12.3, -15), 'MBH': (4, 6),
    'WTC': (-8, 0), 'CAN': (6, 4), 'OTA': (8, 2), 'STL': (-6, 8),
}
AJUSTE_ESCALA = 2_100_000 / MURAL_ESCALA


def capas_mural():
    """Todas las capas en mm del mural, calculadas una sola vez."""
    E = E_MURAL
    marco = box(0, 0, MURAL_W, MURAL_H)
    # Simplificación a la escala del mapa: 0,06 mm no se ve impreso y aliviana el PDF
    tierra = unary_union([E.geom(g) for _, g in capa('tierra')]).simplify(0.06)
    olas = []
    base = tierra.simplify(0.15)
    for i, d in enumerate((1.0, 2.3, 3.8), start=1):
        borde = base.buffer(d, quad_segs=3).boundary
        olas.append((f'ola o{i}', borde.intersection(marco)))
    rios = unary_union([E.geom(g) for _, g in capa('rios')]).intersection(tierra.buffer(0.2))
    rutas1, rutas2, ferry = [], [], []
    for p, g in capa('rutas'):
        g = E.geom(g)
        if p.get('type') == 'Ferry Route':
            ferry.append(g)
        elif p.get('type') == 'Major Highway' or (p.get('scalerank') or 9) <= 4:
            rutas1.append(g)
        else:
            rutas2.append(g)
    reticula = []
    for lon in range(166, 180):
        reticula.append(('m', lon, LineString([E.lonlat(lon, lat / 10) for lat in range(-480, -330, 2)])))
    for lat in range(-48, -33):
        reticula.append(('p', lat, LineString([E.lonlat(lon / 10, lat) for lon in range(1650, 1800, 2)])))
    parques = {p['nombre']: E.geom(g).simplify(0.08) for p, g in capa('parques')}
    return {
        'marco': marco, 'tierra': tierra, 'olas': olas,
        'lagos': unary_union([E.geom(g) for _, g in capa('lagos')]),
        'rios': rios,
        'limites': unary_union([E.geom(g) for _, g in capa('limites')]).simplify(0.06),
        'ruta1': unary_union(rutas1), 'ruta2': unary_union(rutas2), 'ferry': unary_union(ferry),
        'reticula': reticula,
        # La retícula solo en el mar: el relieve es opaco y va debajo de todo
        'reticula_mar': unary_union([l for _, _, l in reticula]).difference(tierra),
        'regiones': {p['iso']: E.geom(g) for p, g in capa('regiones')},
        'parques': parques,
    }


def simbolo_ciudad(x, y, cat):
    if cat == 1:
        return f'<rect class="c1" x="{x - 1.9:.2f}" y="{y - 1.9:.2f}" width="3.8" height="3.8"/>'
    if cat == 2:
        return f'<circle class="c2" cx="{x:.2f}" cy="{y:.2f}" r="1.45"/>'
    if cat == 3:
        return f'<circle class="c3" cx="{x:.2f}" cy="{y:.2f}" r="1.05"/>'
    return f'<circle class="c4" cx="{x:.2f}" cy="{y:.2f}" r="0.62"/>'


SEP_CAT = {1: 3.0, 2: 2.4, 3: 2.0, 4: 1.4}
TAM_CAT = {1: 14, 2: 11, 3: 9.5, 4: 8.4}  # pt


def avion(x, y, s=0.16):
    # Pictograma de avión (iconos.js, grilla de 24) relleno y chico
    return (f'<path class="avion" transform="translate({x:.2f} {y:.2f}) scale({s}) translate(-12 -12)" '
            'd="M3 11.2 H18.5 a1.6 0.8 0 0 1 0 1.6 H3 Z M10 11.2 L7 4 H8.8 L14.5 11.2 Z M10 12.8 L7 20 H8.8 L14.5 12.8 Z '
            'M4.5 11.2 L3 8 H4.3 L6.5 11.2 Z M4.5 12.8 L3 16 H4.3 L6.5 12.8 Z"/>')


# Estilo de cada clase de rótulo: (tamaño en mm, fuente, peso, espaciado en mm). Igual que atlas-nz.css.
ESTILO = {
    'mar': (7.06, 'titulo', 400, 1.6), 'agua': (3.35, 'texto', 400, 0.15), 'lago': (3.0, 'texto', 400, 0),
    'rio': (2.95, 'texto', 400, 0), 'sierra': (5.3, 'titulo', 700, 1.4), 'sierra-chica': (3.0, 'texto', 700, 0.5),
    'isla': (3.0, 'texto', 700, 0), 'isla-grande': (7.4, 'titulo', 800, 1.2), 'isla-grande-en': (3.9, 'texto', 700, 0.6),
    'reg-n': (3.7, 'texto', 800, 0.55), 'pico-n': (3.0, 'texto', 700, 0), 'parque-n': (3.0, 'texto', 700, 0.2),
    't1': (4.94, 'titulo', 800, 0), 't2': (3.88, 'titulo', 700, 0), 't3': (3.35, 'texto', 700, 0), 't4': (2.95, 'texto', 400, 0),
}


def caja(clase, x, y, texto, ancla, rot=0):
    tam, cual, peso, esp = ESTILO[clase]
    return caja_rotulo(x, y, texto, ancla, tam, cual, peso, esp, rot)


def unir_cajas(*cajas):
    return (min(c[0] for c in cajas), min(c[1] for c in cajas), max(c[2] for c in cajas), max(c[3] for c in cajas))


def posicion(E, r):
    """Posición en mm del mural: x/y directos (datos/nz/mural.json) o lon/lat."""
    return (r['x'], r['y']) if 'x' in r else E.lonlat(r['lon'], r['lat'])


def elementos_mural(C):
    """Rótulos y símbolos del mural: lista de (caja, svg)."""
    E = E_MURAL
    items = []
    rotulos = tabla('rotulos')
    ajustes = tabla('mural')
    # Parques nacionales: nombre corto en verde, dentro del parque
    for r in ajustes['parques']:
        x, y = posicion(E, r)
        rot = f' transform="rotate({r["rot"]} {x:.2f} {y:.2f})"' if r.get('rot') else ''
        svg = f'<text class="parque-n" x="{x:.2f}" y="{y:.2f}" text-anchor="middle"{rot}>{esc(r["t"])}</text>'
        if r.get('guia'):
            # Línea guía desde el borde del rótulo más cercano al parque hasta un punto adentro
            gx, gy = r['guia']
            c = caja('parque-n', x, y, r['t'], 'middle', r.get('rot', 0))
            ox = min(max(gx, c[0]), c[2])
            oy = min(max(gy, c[1]), c[3])
            svg = f'<path class="guia-parque" d="M{ox:.2f} {oy:.2f} L{gx:.2f} {gy:.2f}"/><circle class="guia-parque-p" cx="{gx:.2f}" cy="{gy:.2f}" r="0.45"/>' + svg
        items.append((caja('parque-n', x, y, r['t'], 'middle', r.get('rot', 0)), svg))
    # Picos
    for p in rotulos['picos']:
        p = dict(p, pos=ajustes['picos_pos'].get(p['n'], p['pos']))
        x, y = E.lonlat(p['lon'], p['lat'])
        tri = f'<path class="pico" d="M{x:.2f} {y - 1.3:.2f} L{x + 1.15:.2f} {y + 0.75:.2f} L{x - 1.15:.2f} {y + 0.75:.2f} Z"/>'
        dx = 1.8 if p['pos'] == 'E' else -1.8
        ancla = 'start' if p['pos'] == 'E' else 'end'
        alto = f'{p["h"]:,} m'.replace(',', '.') if p.get('h') else ''
        txt = f'<text class="pico-n" x="{x + dx:.2f}" y="{y - 0.2:.2f}" text-anchor="{ancla}">{esc(p["n"])}</text>'
        if alto:
            txt += f'<text class="pico-h" x="{x + dx:.2f}" y="{y + 3.0:.2f}" text-anchor="{ancla}">{alto}</text>'
        items.append((unir_cajas(caja('pico-n', x + dx, y - 0.2, p['n'], ancla), (x - 1.2, y - 1.3, x + 1.2, y + 3.2)), tri + txt))
    # Rótulos de geografía
    for r in rotulos['rotulos']:
        if r['t'] in ajustes['rotulos_ocultar']:
            continue
        r = dict(r, **ajustes['rotulos_mover'].get(r['t'], {}))
        x, y = posicion(E, r)
        rot = f' transform="rotate({r["rot"]} {x:.2f} {y:.2f})"' if r['rot'] else ''
        items.append((caja(r['clase'], x, y, r['t'], 'middle', r['rot']),
                      f'<text class="{r["clase"]}" x="{x:.2f}" y="{y:.2f}" text-anchor="middle"{rot}>{esc(r["t"])}</text>'))
    # Regiones: número, nombre y glifos de sector
    sectores = {s['clave']: s for s in json.loads((RAIZ / 'datos' / 'sectores-nz.json').read_text())['sectores']}
    tops = {k: principales(sectores[k]) for k, _ in GLIFOS_MAPA}
    for i, iso in enumerate(ORDEN_REGIONES, start=1):
        g = C['regiones'][iso]
        mayor = max(g.geoms, key=lambda h: h.area) if g.geom_type == 'MultiPolygon' else g
        c = polylabel(mayor, tolerance=0.5)
        ax, ay = AJUSTE_REGION.get(iso, (0, 0))
        mx, my = ajustes['regiones_ajuste'].get(iso, (0, 0))
        x, y = c.x + ax * AJUSTE_ESCALA + mx, c.y + ay * AJUSTE_ESCALA + my
        nombre = nombre_region(iso).upper()
        svg = (f'<circle class="reg-c" cx="{x:.2f}" cy="{y:.2f}" r="2.3"/>'
               f'<text class="reg-num" x="{x:.2f}" y="{y + 1.12:.2f}" text-anchor="middle">{i}</text>'
               f'<text class="reg-n" x="{x:.2f}" y="{y + 6.4:.2f}" text-anchor="middle">{esc(nombre)}</text>')
        cajas = [caja('reg-n', x, y + 6.4, nombre, 'middle'), (x - 2.3, y - 2.3, x + 2.3, y + 2.3)]
        # Glifos de los sectores en los que la región está entre las 4 primeras del país
        mios = [k for k, _ in GLIFOS_MAPA if iso in tops[k]]
        for j, k in enumerate(mios):
            gx = x + (j - (len(mios) - 1) / 2) * 4.3
            svg += glifo_svg(k, gx, y + 10.8, 1.95)
        if mios:
            ancho = (len(mios) - 1) * 4.3 / 2 + 2
            cajas.append((x - ancho, y + 8.8, x + ancho, y + 12.8))
        items.append((unir_cajas(*cajas), svg))
    # Ciudades: el avión va del lado contrario al rótulo
    for c in tabla('lugares')['lugares']:
        if c['n'] in ajustes['lugares_ocultar']:
            continue
        c = dict(c, pos=ajustes['lugares_pos'].get(c['n'], c['pos']))
        x, y = E.lonlat(c['lon'], c['lat'])
        cat = c['cat']
        sep = SEP_CAT[cat]
        tam = TAM_CAT[cat] * PT
        txt, tx, ty, ancla = rotulo_punto(x, y, c['n'], c['pos'], sep, tam, f't{cat}')
        svg = simbolo_ciudad(x, y, cat) + txt
        cajas = [caja(f't{cat}', tx, ty, c['n'], ancla), (x - 1.9, y - 1.9, x + 1.9, y + 1.9)]
        if c.get('aero'):
            ax = x - sep - 1.6 if c['pos'] in ('E', 'NE', 'SE') else x + sep + 1.6
            ay = y
            if c.get('aero_pos') == 'N':
                ax, ay = x, y - sep - 1.6
            elif c.get('aero_pos') == 'S':
                ax, ay = x, y + sep + 1.6
            svg += avion(ax, ay)
            cajas.append((ax - 2, ay - 2, ax + 2, ay + 2))
        items.append((unir_cajas(*cajas), svg))
    return items


def grados_mural(C, vx, vy):
    """Rótulos de la retícula en el borde exterior del mural visible en esta pieza."""
    out = []
    for tipo, valor, linea in C['reticula']:
        if tipo == 'm':
            for borde_y, dy in ((0, 4.0), (MURAL_H, -2.0)):
                cruce = linea.intersection(LineString([(0, borde_y), (MURAL_W, borde_y)]))
                if cruce.is_empty or cruce.geom_type != 'Point':
                    continue
                x = cruce.x
                if 6 < x < MURAL_W - 6 and vx + 3 < x < vx + IMG_W - 3 and vy <= borde_y <= vy + IMG_H:
                    out.append(f'<text class="grado" x="{x + 0.8:.2f}" y="{borde_y + dy:.2f}">{valor}° E</text>')
        else:
            for borde_x, ancla, dx in ((0, 'start', 1.2), (MURAL_W, 'end', -1.2)):
                cruce = linea.intersection(LineString([(borde_x, 0), (borde_x, MURAL_H)]))
                if cruce.is_empty or cruce.geom_type != 'Point':
                    continue
                y = cruce.y
                if 6 < y < MURAL_H - 6 and vy + 3 < y < vy + IMG_H - 3 and vx <= borde_x <= vx + IMG_W:
                    out.append(f'<text class="grado" x="{borde_x + dx:.2f}" y="{y - 0.8:.2f}" text-anchor="{ancla}">{-valor}° S</text>')
    return out


def numero(c, r):
    return r * COLS + c + 1


def marcas_union(c, r, vx, vy):
    """Marcas de registro, línea de corte y franja de pegado de una pieza."""
    s = []
    # Juntas verticales: la pieza de la derecha va encima de la de la izquierda
    for k, xj in enumerate(JUNTAS_X):
        if c not in (k, k + 1):
            continue
        izquierda = c == k
        for yy in (vy + 45, vy + 138, vy + 232):
            if izquierda:  # mitad que queda a la vista, termina en la línea de apoyo
                s.append(f'<path class="marca-union" d="M{xj - 9} {yy} H{xj}"/>'
                         f'<path class="marca-union-p" d="M{xj - 9} {yy - 1.2} L{xj - 6.6} {yy} L{xj - 9} {yy + 1.2} Z"/>')
            else:
                s.append(f'<path class="marca-union" d="M{xj} {yy} H{xj + 9}"/>'
                         f'<path class="marca-union-p" d="M{xj + 9} {yy - 1.2} L{xj + 6.6} {yy} L{xj + 9} {yy + 1.2} Z"/>')
        if izquierda:
            vecina = numero(c + 1, r)
            s.append(f'<path class="franja" d="M{xj} {vy} V{vy + IMG_H}"/>')
            ym = vy + IMG_H / 2
            s.append(f'<text class="franja-t" data-encimado-ok x="{xj + 5}" y="{ym:.1f}" text-anchor="middle" '
                     f'transform="rotate(90 {xj + 5} {ym:.1f})">PEGAR ACÁ LA PIEZA {vecina} · LÍNEA = BORDE DE LA PIEZA {vecina}</text>')
        else:
            s.append(f'<path class="corte" d="M{xj + 0.15} {vy} V{vy + IMG_H}"/>')
    # Juntas horizontales: la fila de abajo va encima de la de arriba
    for k, yj in enumerate(JUNTAS_Y):
        if r not in (k, k + 1):
            continue
        abajo = r == k + 1  # esta pieza está debajo de la junta (va encima)
        for xx in (vx + 30, vx + 95, vx + 160):
            if abajo:
                s.append(f'<path class="marca-union" d="M{xx} {yj} V{yj + 9}"/>'
                         f'<path class="marca-union-p" d="M{xx - 1.2} {yj + 9} L{xx} {yj + 6.6} L{xx + 1.2} {yj + 9} Z"/>')
            else:
                s.append(f'<path class="marca-union" d="M{xx} {yj - 9} V{yj}"/>'
                         f'<path class="marca-union-p" d="M{xx - 1.2} {yj - 9} L{xx} {yj - 6.6} L{xx + 1.2} {yj - 9} Z"/>')
        if abajo:
            s.append(f'<path class="corte" d="M{vx} {yj + 0.15} H{vx + IMG_W}"/>')
        else:
            fila = ', '.join(str(numero(cc, k + 1)) for cc in range(COLS - 1)) + f' Y {numero(COLS - 1, k + 1)}'
            s.append(f'<path class="franja" d="M{vx} {yj} H{vx + IMG_W}"/>')
            s.append(f'<text class="franja-t" data-encimado-ok x="{vx + 95:.1f}" y="{yj + 6}" text-anchor="middle">'
                     f'PEGAR ACÁ LA FILA DE ABAJO (PIEZAS {fila})</text>')
    return s


def codigo_pieza(n, c, r, vx, vy):
    """Código de la pieza: en una franja que queda tapada; la última va en la esquina del marco."""
    t = f'NZ-A-00 · pieza {n} de {PIEZAS} · v{VERSION} · {FECHA}'
    if c < COLS - 1:  # franja vertical de la derecha, debajo del texto de pegado
        x, y = vx + IMG_W - 5, vy + IMG_H - 14
        return f'<text class="pieza-t" x="{x}" y="{y}" text-anchor="end" transform="rotate(90 {x} {y})">{t}</text>'
    if r < FILAS - 1:  # última columna: franja de abajo, a la izquierda del texto de pegado
        return f'<text class="pieza-t" x="{vx + 4}" y="{vy + IMG_H - 1.5}">{t}</text>'
    return f'<text class="pieza-t" x="{vx + IMG_W - 3}" y="{vy + IMG_H - 3}" text-anchor="end">{t}</text>'


def glifos_tapados(items):
    """Avisa si una fila de glifos de sector se pisa con otro rótulo o símbolo del mapa."""
    for i, ((a0, b0, a1, b1), svg) in enumerate(items):
        if 'class="glifo' not in svg:
            continue
        fila = svg[svg.index('<g class="glifo'):]
        pos = re.findall(r'<g class="glifo[^"]*" transform="translate\(([\d.]+) ([\d.]+)\)', fila)
        xs, ys = [float(x) for x, _ in pos], [float(y) for _, y in pos]
        g0, g1, h0, h1 = min(xs), max(xs) + 3.9, min(ys), max(ys) + 3.9
        nombre = re.search(r'class="reg-n"[^>]*>([^<]+)', svg).group(1)
        for j, ((c0, d0, c1, d1), otro) in enumerate(items):
            if j != i and c0 < g1 and g0 < c1 and d0 < h1 and h0 < d1:
                texto = re.findall(r'>([^<>]+)</text>', otro)
                print(f'  ! los glifos de {nombre} se pisan con {texto[0] if texto else otro[:40]}')


def cajas_que_cruzan(items):
    """Avisa de rótulos que quedarían partidos por una junta (la línea de corte de la pieza que va encima)."""
    for (x0, y0, x1, y1), svg in items:
        texto = svg[svg.rfind('">', 0, svg.rfind('</text>')) + 2:svg.rfind('</text>')] if '</text>' in svg else svg[:40]
        for j in JUNTAS_X:
            if x0 < j < x1:
                print(f'  ! rótulo partido por la junta vertical x={j}: {texto}')
        for j in JUNTAS_Y:
            if y0 < j < y1:
                print(f'  ! rótulo partido por la junta horizontal y={j}: {texto}')


def zona_visible(c, r):
    """Parte de la pieza que queda a la vista una vez armado el mural (sin las franjas tapadas)."""
    vx, vy = c * PASO_X, r * PASO_Y
    return (vx, vy, vx + (PASO_X if c < COLS - 1 else IMG_W), vy + (PASO_Y if r < FILAS - 1 else IMG_H))


def revisar_bloques(bls):
    """Cada bloque tiene que quedar entero en la parte visible de una sola pieza."""
    for b in bls:
        dentro = [numero(c, r) for r in range(FILAS) for c in range(COLS)
                  if (lambda z: z[0] <= b.x and b.x + b.w <= z[2] and z[1] <= b.y and b.y + b.h <= z[3])(zona_visible(c, r))]
        if not dentro:
            print(f'  ! el bloque {b.clase.split(chr(34))[0]} ({b.x}, {b.y}, {b.w} × {b.h} mm) no entra entero en ninguna pieza')


def capas_svg(C, ventana, img):
    x0, y0, x1, y1 = ventana
    capas = [img]
    capas.append(f'<path class="reticula" d="{ruta(recortar(C["reticula_mar"], *ventana))}"/>')
    for clase, g in C['olas']:
        capas.append(f'<path class="{clase}" d="{ruta(recortar(g, *ventana))}"/>')
    for nombre, g in C['parques'].items():
        capas.append(f'<path class="parque" d="{ruta(recortar(g, *ventana))}"><title>{esc(nombre)}</title></path>')
    for clase in ('lagos', 'rios', 'limites'):
        capas.append(f'<path class="{clase[:-1] if clase != "rios" else "rio"}" d="{ruta(recortar(C[clase], *ventana))}"/>')
    capas.append(f'<path class="costa" d="{ruta(recortar(C["tierra"], *ventana).boundary if not C["tierra"].is_empty else None)}"/>')
    for clase in ('ruta2', 'ruta1', 'ferry'):
        g = recortar(C[clase], *ventana)
        if clase == 'ruta1':
            capas.append(f'<path class="ruta1-borde" d="{ruta(g)}"/>')
        capas.append(f'<path class="{clase}" d="{ruta(g)}"/>')
    return capas


def mural():
    from bloques_mural import bloques
    C = capas_mural()
    items = elementos_mural(C)
    cajas_que_cruzan(items)
    glifos_tapados(items)
    bls = bloques(C, E_MURAL)
    revisar_bloques(bls)
    (DESTINO / 'relieve').mkdir(parents=True, exist_ok=True)
    for viejo in DESTINO.glob('NZ-A-00-*.html'):
        viejo.unlink()
    for viejo in (DESTINO / 'relieve').glob('NZ-A-00-*.jpg'):
        viejo.unlink()
    for r in range(FILAS):
        for c in range(COLS):
            n = numero(c, r)
            vx, vy = c * PASO_X, r * PASO_Y
            ventana = (vx - 1, vy - 1, vx + IMG_W + 1, vy + IMG_H + 1)
            relieve_mural_ventana(vx, vy, IMG_W, IMG_H).save(DESTINO / 'relieve' / f'NZ-A-00-{n}.jpg', quality=88, optimize=True)
            img = f'<image href="relieve/NZ-A-00-{n}.jpg" x="{vx}" y="{vy}" width="{IMG_W}" height="{IMG_H}" preserveAspectRatio="none"/>'
            capas = capas_svg(C, ventana, img)
            capas += [svg for (x0, y0, x1, y1), svg in items
                      if x1 > vx - 2 and x0 < vx + IMG_W + 2 and y1 > vy - 2 and y0 < vy + IMG_H + 2]
            capas += grados_mural(C, vx, vy)
            capas.append(f'<rect class="marco" x="0.22" y="0.22" width="{MURAL_W - 0.44}" height="{MURAL_H - 0.44}"/>')
            capas += marcas_union(c, r, vx, vy)
            capas.append(codigo_pieza(n, c, r, vx, vy))
            html_bloques = ''.join(b.html(vx, vy) for b in bls if b.en(*zona_visible(c, r)))
            svg = (f'<svg class="mapa mural-svg" data-borde-ok viewBox="{vx} {vy} {IMG_W} {IMG_H}" '
                   f'style="width:{IMG_W}mm;height:{IMG_H}mm">\n' + '\n'.join(capas) + '\n</svg>')
            html = f'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>NZ-A-00-{n} Mapa mural de Nueva Zelanda, pieza {n} de {PIEZAS}</title>
<link rel="stylesheet" href="../../estilo/combi.css">
<link rel="stylesheet" href="../../estilo/atlas-nz.css">
<link rel="stylesheet" href="../../estilo/mural-nz.css">
<style>@page {{ size: A4; }}</style>
</head>
<body>
<div class="hoja mural" data-tinta-max="35">
{svg}
{html_bloques}
</div>
</body>
</html>
'''
            (DESTINO / f'NZ-A-00-{n}.html').write_text(html)
            print(f'  hojas/nz-a/NZ-A-00-{n}.html')


def mural_previa():
    """Mural entero en una sola página de 55 × 81 cm (salida/pruebas/): para revisar
    rótulos y juntas, o para imprimirlo de una pieza en una imprenta."""
    from bloques_mural import bloques
    C = capas_mural()
    items = elementos_mural(C)
    dest = RAIZ / 'salida' / 'pruebas'
    dest.mkdir(parents=True, exist_ok=True)
    relieve_mural_ventana(0, 0, MURAL_W, MURAL_H).save(dest / 'mural-relieve.jpg', quality=88)
    img = f'<image href="mural-relieve.jpg" x="0" y="0" width="{MURAL_W}" height="{MURAL_H}"/>'
    capas = capas_svg(C, (-1, -1, MURAL_W + 1, MURAL_H + 1), img)
    capas += [svg for _, svg in items]
    capas.append(f'<rect class="marco" x="0.22" y="0.22" width="{MURAL_W - 0.44}" height="{MURAL_H - 0.44}"/>')
    juntas = '' if '--sin-juntas' in sys.argv else (
        '<path d="' + ' '.join(f'M{x} 0 V{MURAL_H} M{x + SOLAPA} 0 V{MURAL_H}' for x in JUNTAS_X)
        + ' ' + ' '.join(f'M0 {y} H{MURAL_W} M0 {y + SOLAPA} H{MURAL_W}' for y in JUNTAS_Y)
        + '" style="stroke:magenta;stroke-width:0.3;fill:none"/>')
    capas.append(juntas)
    bl = ''.join(b.html(0, 0) for b in bloques(C, E_MURAL))
    html = f'''<!doctype html><html lang="es"><head><meta charset="utf-8">
<link rel="stylesheet" href="../../estilo/combi.css"><link rel="stylesheet" href="../../estilo/atlas-nz.css">
<link rel="stylesheet" href="../../estilo/mural-nz.css">
<style>@page {{ size: {MURAL_W + 20}mm {MURAL_H + 20}mm; }} .hoja {{ width:{MURAL_W + 20}mm; height:{MURAL_H + 20}mm; }}</style></head>
<body><div class="hoja mural"><svg class="mapa" viewBox="0 0 {MURAL_W} {MURAL_H}" style="width:{MURAL_W}mm;height:{MURAL_H}mm">
{chr(10).join(capas)}</svg>{bl}</div></body></html>'''
    (dest / 'mural-completo.html').write_text(html)
    print('  salida/pruebas/mural-completo.html')


if __name__ == '__main__':
    DESTINO.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(RAIZ / 'herramientas'))
    que = sys.argv[1] if len(sys.argv) > 1 else 'todo'
    if que in ('mural', 'todo'):
        mural()
    if que == 'mural-previa':
        mural_previa()
    if que in ('fichas', 'todo'):
        from fichas_nz import fichas
        fichas(DESTINO, sys.argv[2:] or None)
    if que in ('matriz', 'todo'):
        from matriz_nz import matriz
        matriz(DESTINO)
