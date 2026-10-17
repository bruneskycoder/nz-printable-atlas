"""Bloques de texto del mapa mural (título, leyendas, índice, armado, fuentes).
Cada bloque se ubica en mm del mural y aparece en la pieza que lo contiene entera.
Van sobre el mar, lejos de las juntas, para que ninguno quede partido."""
import json

from atlas_nz import ORDEN_REGIONES, RAIZ, Encuadre, capa, esc, nombre_region, ruta
from shapely.ops import unary_union

KM_MM = 1 / 2.1  # 1 km a 1:2.100.000, en mm


class Bloque:
    def __init__(self, clase, x, y, w, h, contenido):
        self.clase, self.x, self.y, self.w, self.h, self.contenido = clase, x, y, w, h, contenido

    def en(self, vx, vy, W, H):
        return vx <= self.x and self.x + self.w <= vx + W and vy <= self.y and self.y + self.h <= vy + H

    def html(self, vx, vy):
        return (f'<div class="bloque {self.clase}" style="left:{10 + self.x - vx:.1f}mm;top:{10 + self.y - vy:.1f}mm;'
                f'width:{self.w}mm">{self.contenido}</div>\n')


def muestra(svg):
    return f'<svg class="mapa" viewBox="0 0 9 4.5">{svg}</svg>'


def datos_pais():
    ruta_json = RAIZ / 'datos' / 'regiones.json'
    if not ruta_json.exists():
        return None
    return json.loads(ruta_json.read_text()).get('pais')


def bloques(C, E):
    b = []
    pais = datos_pais()
    datos = ''
    if pais:
        datos = ('<div class="datos">'
                 f'<div><b>{pais["poblacion_txt"]}</b>habitantes (Censo {pais["censo"]})</div>'
                 f'<div><b>{pais["superficie_txt"]}</b>km² en las 16 regiones</div>'
                 '<div><b>16</b>regiones</div></div>')
    b.append(Bloque('m-titulo', 14, 14, 226, 92, (
        '<span class="coleccion">Atlas de Nueva Zelanda · NZ-A-00 · mapa mural en 8 piezas</span>'
        '<h1>Nueva Zelanda<span class="mi">Aotearoa</span></h1>'
        '<p>Las 16 regiones, el relieve, las ciudades y las rutas principales. Cada región tiene su ficha: '
        'el número del círculo es la hoja <b>NZ-A-01</b> a <b>16</b>.</p>'
        '<p><b>Escala 1:2.100.000</b> · 1 cm del mapa = 21 km · el norte está arriba.</p>' + datos)))

    filas = [
        (muestra('<rect class="c1" x="2.6" y="0.35" width="3.8" height="3.8"/>'), 'Más de 1 millón de habitantes'),
        (muestra('<path class="ruta1" d="M0 2.25 H9"/>'), 'Ruta principal (<i>State Highway</i>)'),
        (muestra('<circle class="c2" cx="4.5" cy="2.25" r="1.45"/>'), '100.000 a 500.000'),
        (muestra('<path class="ruta2" d="M0 2.25 H9"/>'), 'Otra ruta importante'),
        (muestra('<circle class="c3" cx="4.5" cy="2.25" r="1.05"/>'), '25.000 a 100.000'),
        (muestra('<path class="ferry" d="M0 2.25 H9"/>'), 'Ferry entre las islas'),
        (muestra('<circle class="c4" cx="4.5" cy="2.25" r="0.62"/>'), 'Pueblo o destino'),
        (muestra('<path class="limite" d="M0 2.25 H9"/>'), 'Límite de región'),
        (muestra('<path class="avion" transform="translate(4.5 2.25) scale(0.2) translate(-12 -12)" d="M3 11.2 H18.5 a1.6 0.8 0 0 1 0 1.6 H3 Z M10 11.2 L7 4 H8.8 L14.5 11.2 Z M10 12.8 L7 20 H8.8 L14.5 12.8 Z M4.5 11.2 L3 8 H4.3 L6.5 11.2 Z M4.5 12.8 L3 16 H4.3 L6.5 12.8 Z"/>'),
         'Aeropuerto con vuelos internacionales'),
        (muestra('<circle class="reg-c" cx="4.5" cy="2.25" r="2.1"/><text class="reg-num" x="4.5" y="3.35" text-anchor="middle">1</text>'),
         'Región y número de su ficha'),
        (muestra('<path class="rio" d="M0 3 C3 0.5 6 4 9 1.5"/>'), 'Río'),
        (muestra('<path class="pico" d="M4.5 0.9 L5.65 2.95 L3.35 2.95 Z"/>'), 'Pico, con su altura'),
        (muestra('<rect class="lago" x="1.5" y="0.6" width="6" height="3.3" rx="1.2"/>'), 'Lago'),
    ]
    b.append(Bloque('leyenda', 14, 110, 226, 64, (
        '<h2>Cómo leer el mapa</h2><div class="filas">'
        + ''.join(f'<div class="f">{s}<span>{t}</span></div>' for s, t in filas)
        + '</div><p class="nota">Tamaño de las ciudades: categoría aproximada, según el Censo 2023 de Stats NZ. Los nombres son los oficiales '
          '(LINZ), en inglés y en te reo māori; la barra «/» separa los dos nombres oficiales de un mismo lugar.</p>')))

    # Índice de regiones (pieza 2)
    li = []
    for i, iso in enumerate(ORDEN_REGIONES, start=1):
        if i == 1:
            li.append('<li class="isla" style="display:block;border:0">Isla Norte · Te Ika-a-Māui</li>')
        if i == 10:
            li.append('<li class="isla" style="display:block;border:0">Isla Sur · Te Waipounamu</li>')
        li.append(f'<li><span class="num">{i}</span><span>{esc(nombre_region(iso))}</span><span class="cod" data-meta>NZ-A-{i:02d}</span></li>')
    b.append(Bloque('m-regiones', 410, 14, 122, 150, '<h2>Las 16 regiones</h2><ol>' + ''.join(li) + '</ol>'))

    # Relieve y escala (pieza 3)
    km = KM_MM
    barra = ''.join(
        f'<rect x="{i * 50 * km:.2f}" y="1" width="{50 * km:.2f}" height="1.6" style="fill:{"#000" if i % 2 == 0 else "#fff"};stroke:#000;stroke-width:0.25"/>'
        for i in range(4))
    marcas = ''.join(f'<text class="grado" x="{i * 50 * km:.2f}" y="6.2" text-anchor="middle" style="font-size:3.53px;fill:#000">{i * 50}</text>' for i in range(5))
    b.append(Bloque('m-relieve', 14, 200, 156, 70, (
        '<h2>Relieve</h2>'
        '<div class="tintas">'
        '<div><i style="background:#fff"></i>0 a 1000 m</div>'
        '<div><i style="background:color-mix(in srgb, var(--ocre) 17%, white)"></i>1000 a 1500 m</div>'
        '<div><i style="background:color-mix(in srgb, var(--ocre) 27%, white)"></i>1500 a 2000 m</div>'
        '<div><i style="background:color-mix(in srgb, var(--ocre) 38%, white)"></i>más de 2000 m</div></div>'
        '<p class="nota">El sombreado imita una luz que viene del noroeste: las laderas en sombra se oscurecen. '
        'Así se leen las cordilleras sin curvas de nivel.</p>'
        f'<h2 style="margin-top:3mm">Escala 1:2.100.000</h2>'
        f'<svg class="mapa" viewBox="-3 0 {200 * km + 12:.1f} 7" style="width:{200 * km + 12:.1f}mm;height:7mm;overflow:visible">{barra}{marcas}'
        f'<text class="grado" x="{200 * km + 4:.2f}" y="2.9" style="font-size:3.53px;fill:#000">km</text></svg>')))

    # Chatham Islands (pieza 8), a la misma escala
    ch = [g for _, g in capa('chatham')]
    citm = Encuadre(2_100_000, 3_468_000, 10_036_000)
    geo = unary_union([citm.geom(g) for g in ch])
    minx, miny, maxx, maxy = geo.bounds
    b.append(Bloque('m-chatham', 300, 556, 110, 44, (
        f'<svg class="mapa" viewBox="{minx - 3:.1f} {miny - 3:.1f} {maxx - minx + 6:.1f} {maxy - miny + 6:.1f}" '
        f'style="width:{maxx - minx + 6:.1f}mm;height:{maxy - miny + 6:.1f}mm;float:left;margin-right:3mm">'
        f'<path class="lago" style="fill:none" d="{ruta(geo.buffer(1.0).boundary)}"/>'
        f'<path style="fill:#fff;stroke:#000;stroke-width:0.26" d="{ruta(geo)}"/></svg>'
        '<p class="t"><b>Chatham Islands</b><br>Están a unos 800 km al este de Banks Peninsula, a la misma latitud '
        'que este recuadro. Dibujadas a la misma escala que el mapa. No son una de las 16 regiones: '
        'tienen un consejo propio.</p>')))

    b.append(Bloque('m-armado', 300, 606, 232, 80, (
        '<h2>Cómo armar el mural</h2><ol>'
        '<li><b>Prueba de unión primero.</b> Imprimí solo las piezas 1 y 2, a tamaño real (100 %), una sola cara. '
        'Unilas como dice el paso 3: si las marcas ▶◀ quedan desfasadas menos de 1 mm, imprimí las otras seis.</li>'
        '<li><b>Cortá.</b> En las piezas 2, 4, 6 y 8 cortá el margen izquierdo por la línea de rayas. En las piezas 3 a 8, '
        'también el margen de arriba. Las piezas 1 y 2 conservan el margen de arriba, que hace de marco.</li>'
        '<li><b>Uní cada fila.</b> Apoyá la pieza derecha sobre la franja «pegar acá» de la izquierda, con el borde cortado '
        'sobre la línea de puntos. Corré la pieza hasta que cada par de marcas ▶◀ forme una sola línea recta '
        'y la costa siga sin saltos. Pegá con adhesivo en barra o con cinta por detrás.</li>'
        '<li><b>Uní las filas</b> de arriba hacia abajo, igual: la fila de abajo va encima, con sus marcas ▲▼ alineadas.</li>'
        '</ol>')))

    b.append(Bloque('m-fuentes" data-meta="', 300, 690, 232, 32, (
        '<b>Fuentes.</b> Límites de las regiones: Stats NZ (2017) vía geoBoundaries, CC BY 4.0. '
        'Costa simplificada con Mapshaper. Lagos, ríos y rutas: Natural Earth 1:10 m, dominio público. '
        'Relieve: Terrain Tiles (Mapzen, en AWS) con el modelo de elevación de LINZ (CC BY 4.0), SRTM y ETOPO1. '
        'Población: Stats NZ, Censo 2023. Nombres: New Zealand Gazetteer (LINZ). Alturas: Aoraki / Mount Cook, '
        'medición de 2014; Taranaki Maunga, ley Te Kāhui Tupua de 2025; las demás, valores de referencia. '
        'Proyección NZTM2000. Consultado el 2026-10-17.<br>'
        'NZ-A-00 · versión 1 · 2026-10-17 · Enciclopedia para imprimir')))
    return b
