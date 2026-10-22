"""Bloques de texto del mapa mural v2 (título, leyenda, tablas, armado, fuentes).
El mural va todo en inglés (lo pidió así el usuario: es el idioma que va a usar
allá); las fichas regionales siguen en castellano.
Cada bloque se ubica en mm del mural y aparece en la pieza que lo contiene entero.
Van sobre el mar, en la parte de cada pieza que queda a la vista, para que
ninguno quede partido por una junta (generar-atlas.py avisa si pasa)."""
import json

from atlas_nz import HIPSO, MURAL_ESCALA, ORDEN_REGIONES, RAIZ, Encuadre, capa, esc, nombre_region, ruta
from glifos import glifo_html
from shapely.ops import unary_union

KM_MM = 1_000_000 / MURAL_ESCALA  # 1 km del terreno, en mm del mural


class Bloque:
    def __init__(self, clase, x, y, w, h, contenido):
        self.clase, self.x, self.y, self.w, self.h, self.contenido = clase, x, y, w, h, contenido

    def en(self, x0, y0, x1, y1):
        return x0 <= self.x and self.x + self.w <= x1 and y0 <= self.y and self.y + self.h <= y1

    def html(self, vx, vy):
        return (f'<div class="bloque {self.clase}" style="left:{10 + self.x - vx:.1f}mm;top:{10 + self.y - vy:.1f}mm;'
                f'width:{self.w}mm">{self.contenido}</div>\n')


def muestra(svg):
    return f'<svg class="mapa" viewBox="0 0 9 4.5">{svg}</svg>'


def escudo_muestra(num, clase):
    """Escudo de State Highway para la leyenda, igual al del mapa."""
    return (f'<g class="{clase}"><rect x="2.6" y="0.55" width="3.8" height="3.4" rx="0.8"/>'
            f'<text x="4.5" y="3.27" text-anchor="middle">{num}</text></g>')


def datos_pais():
    ruta_json = RAIZ / 'datos' / 'regiones.json'
    if not ruta_json.exists():
        return None
    return json.loads(ruta_json.read_text()).get('pais')


def escala_grafica():
    km = KM_MM
    barra = ''.join(
        f'<rect x="{i * 50 * km:.2f}" y="1" width="{50 * km:.2f}" height="1.6" style="fill:{"#000" if i % 2 == 0 else "#fff"};stroke:#000;stroke-width:0.25"/>'
        for i in range(4))
    marcas = ''.join(f'<text class="grado" x="{i * 50 * km:.2f}" y="6.2" text-anchor="middle" style="font-size:3.53px;fill:#000;stroke:none">{i * 50}</text>'
                     for i in range(5))
    return (f'<svg class="mapa" viewBox="-3 0 {200 * km + 12:.1f} 7" style="width:{200 * km + 12:.1f}mm;height:7mm;overflow:visible">{barra}{marcas}'
            f'<text class="grado" x="{200 * km + 4:.2f}" y="2.9" style="font-size:3.53px;fill:#000;stroke:none">km</text></svg>')


def tintas_altura():
    """Franja de las tintas de altura del relieve, con sus cortes en metros."""
    cortes = [0, 250, 600, 1000, 1500, 2000, 2400]
    color = {a: c for a, c in HIPSO}
    celdas = ''.join(f'<div><i style="background:rgb{color[a]}"></i>{a:,}</div>' for a in cortes)
    return f'<div class="tintas">{celdas}<div class="u">m</div></div>'


GLIFOS_MAPA = [('lecheria', 'Dairy'), ('ovinos', 'Sheep'), ('vacunos', 'Beef cattle'), ('fruta', 'Fruit'),
               ('vid', 'Vineyards'), ('hortalizas', 'Vegetables'), ('forestal', 'Forestry'), ('frigorificos', 'Meat processing'),
               ('alojamiento', 'Accommodation & tourism')]
# Nombre en inglés de cada sector de datos/sectores-nz.json (que los guarda en castellano), corto para la tabla
SECTOR_EN = {'lecheria': 'Dairy', 'ovinos': 'Sheep', 'vacunos': 'Beef', 'fruta': 'Fruit', 'vid': 'Vineyards',
             'hortalizas': 'Vegetables', 'forestal': 'Forestry', 'frigorificos': 'Meat processing',
             'alojamiento': 'Accommodation', 'construccion': 'Construction', 'transporte': 'Transport',
             'tecnicos': 'Architecture & eng.'}
# Filas del calendario (datos/calendario-nz.json las guarda en castellano)
ETIQUETA_EN = {'Kiwi': 'Kiwifruit', 'Manzana y pera': 'Apples & pears', 'Cereza': 'Cherries', 'Carozo': 'Stonefruit',
               'Palta': 'Avocados', 'Lúpulo': 'Hops', 'Uva': 'Grapes', 'Hortalizas': 'Vegetables',
               'Frigoríficos': 'Meat processing', 'Parición y esquila': 'Lambing & shearing', 'Lechería': 'Dairy farms',
               'Forestal': 'Forestry', 'Viñedos (Marlborough y otras)': 'Vineyards (Marlborough & others)',
               'Esquí': 'Ski fields', 'Turismo, temporada alta': 'Tourism, high season', 'Pesca y mariscos': 'Fishing & seafood'}
# Letra de cada tarea en el calendario: C cosecha, P poda, R raleo, M mantenimiento (los datos) -> inglés
LETRA_EN = {'C': 'H', 'P': 'P', 'R': 'T', 'M': 'M'}


def num(x, dec=1):
    return f'{x:.{dec}f}'


def principales(sector, n=4):
    """Las n regiones con más participación en el sector (las del glifo en el mapa)."""
    pares = [(v, k) for k, v in sector['porcentaje'].items() if v is not None]
    return {k for _, k in sorted(pares, reverse=True)[:n]}


def matriz():
    d = json.loads((RAIZ / 'datos' / 'sectores-nz.json').read_text())
    sect = d['sectores']
    campo = [s for s in sect if s['fuente'] != 'bds2025']
    empleo = [s for s in sect if s['fuente'] == 'bds2025']
    cols = '<col class="reg">' + '<col>' * len(sect)
    cab1 = (f'<tr><th></th><th class="grupo" colspan="{len(campo)}">Farming: livestock and hectares</th>'
            f'<th class="grupo sep" colspan="{len(empleo)}">Jobs, February 2025</th></tr>')
    cab2 = '<tr><th></th>' + ''.join(
        f'<th class="cab{" sep" if s is empleo[0] else ""}"><span class="n">{SECTOR_EN[s["clave"]]}</span>'
        f'{glifo_html(s["clave"], 4.6)}</th>' for s in sect) + '</tr>'
    tops = {s['clave']: principales(s) for s in sect}
    filas = []
    for i, iso in enumerate(ORDEN_REGIONES, start=1):
        if i in (1, 10):
            filas.append(f'<tr class="isla"><td colspan="{len(sect) + 1}" data-meta>'
                         f'{"North Island" if i == 1 else "South Island"}</td></tr>')
        celdas = [f'<td class="reg"><span class="num" data-meta>{i}</span>{esc(nombre_region(iso))}</td>']
        for s in sect:
            v = s['porcentaje'][iso]
            sep = ' sep' if s is empleo[0] else ''
            if v is None:
                celdas.append(f'<td class="sd{sep}" data-meta>n/a</td>')
                continue
            tinte = min(62, round(v * 1.7))
            clase = ('top ' if iso in tops[s['clave']] else '') + ('oscuro' if tinte > 44 else '')
            celdas.append(f'<td class="{clase}{sep}" style="background:color-mix(in srgb, var(--s-{s["clave"]}) {tinte}%, transparent)">'
                          f'{num(v)}</td>')
        filas.append('<tr>' + ''.join(celdas) + '</tr>')
    return ('<h2>What does each region produce?</h2>'
            '<p class="bajada">Each region\'s share of the New Zealand total, in %. The darker the cell, the more concentrated '
            'the sector; in bold, the top 4 regions, which carry the sector\'s symbol on the map.</p>'
            f'<table class="tabla-sectores"><colgroup>{cols}</colgroup><thead>{cab1}{cab2}</thead><tbody>{"".join(filas)}</tbody></table>'
            '<p class="nota"><span class="aviso">Indicative sectors and areas: not current job vacancies, wages or a guarantee '
            'of work.</span> They show where the activity is, not where jobs are open today.</p>'
            '<p class="nota">Farming: livestock at 30 June 2025; fruit, vineyards, vegetables and forestry in hectares, 2022 '
            'census. Jobs: employees at their place of work (owners working alone are not counted). '
            '“n/a”: suppressed by Stats NZ.</p>'
            '<p class="fuente" data-meta>Sources: Stats NZ, Agricultural Production Statistics 2025 (AGR003AA) and Agricultural '
            'Production Census 2022; Business Demography Statistics 2025 (BDS_BDS_001), via Figure.NZ. Accessed '
            f'{d["consultado"]}. Data in datos/sectores-nz.json.</p>')


MESES_INI = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
TINTE_TAREA = {'C': 70, 'P': 45, 'R': 28, 'M': 18, 'V': 32}


def calendario():
    d = json.loads((RAIZ / 'datos' / 'calendario-nz.json').read_text())
    cols = '<col class="et">' + '<col>' * 12
    est = ('<tr class="estacion" data-meta><th></th><th class="verano" colspan="2">Summer</th><th class="otono" colspan="3">Autumn</th>'
           '<th class="invierno" colspan="3">Winter</th><th class="primavera" colspan="3">Spring</th>'
           '<th class="verano">Sum.</th></tr>')
    meses = '<tr><th></th>' + ''.join(f'<th>{m}</th>' for m in MESES_INI) + '</tr>'
    filas = []
    grupos = {'winz-calendario': 'Fruit, grapes and vegetables, month by month', 'winz-general': 'Other work, general season'}
    previo = None
    for f in d['filas']:
        if f['fuente'] != previo:
            filas.append(f'<tr class="grupo"><td colspan="13">{grupos[f["fuente"]]}</td></tr>')
            previo = f['fuente']
        zona = f' <span class="z">· {esc(f["zona"])}</span>' if f['zona'] else ''
        celdas = [f'<td class="et">{glifo_html(f["sector"], 3.6)}{esc(ETIQUETA_EN[f["etiqueta"]])}{zona}</td>']
        for m in f['meses']:
            if not m:
                celdas.append('<td class="vacio"></td>')
                continue
            tinte = TINTE_TAREA[m['t']]
            letra = '' if m['t'] == 'V' else LETRA_EN[m['t']]
            color = 'white' if tinte >= 60 else '#1d2a36'
            sector = {'turismo': 'alojamiento', 'esqui': 'alojamiento'}.get(f['sector'], f['sector'])
            celdas.append(f'<td class="{"pico" if m["pico"] else ""}" style="background:color-mix(in srgb, var(--s-{sector}) {tinte}%, transparent);'
                          f'color:{color}">{letra}</td>')
        filas.append('<tr>' + ''.join(celdas) + '</tr>')
    return ('<h2>When is there seasonal work?</h2>'
            f'<table class="tabla-calendario"><colgroup>{cols}</colgroup><thead>{est}{meses}</thead><tbody>{"".join(filas)}</tbody></table>'
            '<p class="nota"><b>H</b> harvest (picking) · <b>P</b> pruning · <b>T</b> thinning · <b>M</b> plant maintenance · '
            'outlined: busiest months. Indicative windows: seasons change with the crop, the weather, the employer and the '
            'year. In Marlborough, vineyards offer work almost all year round (PickNZ), with no official monthly calendar.</p>'
            '<p class="fuente" data-meta>Sources: Work and Income, “Fruit and vegetable seasonal work” and “Finding seasonal '
            f'work”; PickNZ. Accessed {d["consultado"]}. Data in datos/calendario-nz.json.</p>')


# Nombres dobles oficiales (Gazetteer de LINZ): el mapa muestra el inglés y este recuadro, el māori
NOMBRES_MAORI = [
    ('Aotearoa', 'New Zealand'), ('Te Ika-a-Māui', 'North Island'), ('Te Waipounamu', 'South Island'),
    ('Rakiura', 'Stewart Island'), ('Kā Tiritiri o te Moana', 'Southern Alps'), ('Aoraki', 'Mount Cook'),
    ('Tititea', 'Mount Aspiring'), ('Piopiotahi', 'Milford Sound'), ('Te Rerenga Wairua', 'Cape Reinga'),
    ('Tīkapa Moana', 'Hauraki Gulf'), ('Mohua', 'Golden Bay'), ('Te Tai-o-Aorere', 'Tasman Bay'),
    ('Mata-Au', 'Clutha River'), ('Waiau', 'Franz Josef (village)'),
]


def nombres_maori():
    pares = ''.join(f'<div><b>{esc(m)}</b> {esc(e)}</div>' for m, e in NOMBRES_MAORI)
    return ('<h2>Māori names you will see on signs</h2>'
            f'<div class="pares">{pares}</div>'
            '<p class="nota">Aotearoa is the everyday Māori name for New Zealand. <b>Saying them:</b> vowels as in Spanish, '
            'ā = long a, <i>wh</i> ≈ <i>f</i>, <i>ng</i> as in <i>sing</i>. Taupō or Whangārei are Māori names used in '
            'English too.</p>')


def bloques(C, E):
    b = []
    pais = datos_pais()
    datos = ''
    if pais:
        superficie = int(pais['superficie_txt'].replace('.', ''))
        datos = ('<div class="datos">'
                 f'<div><b>{pais["poblacion"]:,}</b>people ({pais["censo"]} Census)</div>'
                 f'<div><b>{superficie:,}</b>km² in the 16 regions</div>'
                 '<div><b>16</b>regions</div><div><b>13</b>national parks</div></div>')
    escala_txt = f'1:{MURAL_ESCALA:,}'
    b.append(Bloque('m-titulo n0', 8, 8, 164, 70, (
        '<span class="coleccion">Atlas of New Zealand · NZ-A-00 · wall map in 9 pieces</span>'
        '<h1>New Zealand</h1>'
        '<p>The 16 regions, the terrain, the national parks, the towns and the highways. '
        'The number in each circle is the region\'s fact sheet: <b>NZ-A-01</b> to <b>16</b>.</p>'
        f'<p><b>Scale {escala_txt}</b> · 1 cm on the map = {MURAL_ESCALA / 100_000:g} km · north is up.</p>'
        + datos)))

    filas = [
        (muestra('<rect class="c1" x="2.6" y="0.35" width="3.8" height="3.8"/>'), 'Over 1 million people'),
        (muestra('<path class="ruta1-borde" d="M0 2.25 H9"/><path class="ruta1" d="M0 2.25 H9"/>' + escudo_muestra('1', 'escudo sh1')),
         'State Highway 1, the main highway'),
        (muestra('<circle class="c2" cx="4.5" cy="2.25" r="1.45"/>'), '100,000 to 500,000'),
        (muestra('<path class="ruta2" d="M0 2.25 H9"/>' + escudo_muestra('6', 'escudo')), 'Other State Highway, with its number'),
        (muestra('<circle class="c3" cx="4.5" cy="2.25" r="1.05"/>'), '25,000 to 100,000'),
        (muestra('<path class="ferry" d="M0 2.25 H9"/>'), 'Cook Strait ferry (by sea)'),
        (muestra('<circle class="c4" cx="4.5" cy="2.25" r="0.62"/>'), 'Town or destination'),
        (muestra('<path class="limite" d="M0 2.25 H9"/>'), 'Region boundary'),
        (muestra('<path class="avion" transform="translate(4.5 2.25) scale(0.2) translate(-12 -12)" d="M3 11.2 H18.5 a1.6 0.8 0 0 1 0 1.6 H3 Z M10 11.2 L7 4 H8.8 L14.5 11.2 Z M10 12.8 L7 20 H8.8 L14.5 12.8 Z M4.5 11.2 L3 8 H4.3 L6.5 11.2 Z M4.5 12.8 L3 16 H4.3 L6.5 12.8 Z"/>'),
         'Airport with international flights'),
        (muestra('<circle class="reg-c" cx="4.5" cy="2.25" r="2.1"/><text class="reg-num" x="4.5" y="3.35" text-anchor="middle">1</text>'),
         'Region and its fact-sheet number'),
        (muestra('<rect class="parque" x="0.5" y="0.5" width="8" height="3.5" rx="0.8"/>'), 'National park (DOC)'),
        (muestra('<path class="rio" d="M0 3 C3 0.5 6 4 9 1.5"/>'), 'River'),
        (muestra('<path class="pico" d="M4.5 0.9 L5.65 2.95 L3.35 2.95 Z"/>'), 'Peak, with its height'),
        (muestra('<rect class="lago" x="1.5" y="0.6" width="6" height="3.3" rx="1.2"/>'), 'Lake'),
    ]
    b.append(Bloque('leyenda n1', 8, 66, 164, 131, (
        '<h2>How to read the map</h2><div class="filas">'
        + ''.join(f'<div class="f">{s}<span>{t}</span></div>' for s, t in filas)
        + '</div>'
        '<h3>Height of the land</h3>' + tintas_altura()
        + '<p class="nota">Hill shading assumes light from the northwest: slopes in shadow are darker.</p>'
        f'<h3>Scale {escala_txt}</h3>' + escala_grafica()
        + '<h3>Main sectors</h3><p class="nota glifos-leyenda">'
        + ' '.join(f'<span>{glifo_html(k, 4.2)} {n}</span>' for k, n in GLIFOS_MAPA)
        + '</p><p class="nota">Each sector puts its symbol on its <b>top 4 regions</b> in New Zealand (figures in the '
          'table below). Construction, maintenance, logistics and drafting follow the population: '
          'more people, more work.</p>'
        + '<p class="nota">Town sizes: approximate category, from Stats NZ\'s 2023 Census. Names are the English names '
          'on the official NZ Gazetteer (LINZ); their Māori names are listed below.</p>')))

    b.append(Bloque('m-maori n2', 8, 201, 164, 58, nombres_maori()))

    b.append(Bloque('m-matriz n1', 8, 276, 164, 250, matriz()))
    b.append(Bloque('m-calendario n1', 372, 548, 166, 132, calendario()))

    # Chatham Islands (pieza 9), a la misma escala
    ch = [g for _, g in capa('chatham')]
    citm = Encuadre(MURAL_ESCALA, 3_468_000, 10_036_000)
    geo = unary_union([citm.geom(g) for g in ch])
    minx, miny, maxx, maxy = geo.bounds
    b.append(Bloque('m-chatham n2', 462, 345, 84, 80, (
        f'<svg class="mapa" viewBox="{minx - 3:.1f} {miny - 3:.1f} {maxx - minx + 6:.1f} {maxy - miny + 6:.1f}" '
        f'style="width:{maxx - minx + 6:.1f}mm;height:{maxy - miny + 6:.1f}mm;margin:0 auto 1.5mm">'
        f'<path class="lago" style="fill:none" d="{ruta(geo.buffer(1.0).boundary)}"/>'
        f'<path style="fill:#f3f0e1;stroke:#1f3a55;stroke-width:0.26" d="{ruta(geo)}"/></svg>'
        '<p class="t"><b>Chatham Islands</b><br>About 800 km east of Banks Peninsula, roughly level with Christchurch. '
        'Drawn at the same scale as the map, but moved from their real place. They are not one of the 16 regions: '
        'they have their own council.</p>')))

    b.append(Bloque('m-armado n4', 8, 465, 164, 53, (
        '<h2>How to put the map together</h2><ol>'
        '<li><b>Test join first.</b> Print only pieces 2 and 3 at actual size (100%), single-sided, and join them as in '
        'step 3. If the ▶◀ marks are less than 1 mm apart, print the other seven.</li>'
        '<li><b>Trim</b> the left margin of the pieces in columns 2 and 3, and the top margin of the pieces in rows 2 '
        'and 3, along the dashed line.</li>'
        '<li><b>Join each row</b> from left to right: lay each piece on the “glue here” strip of the one before and slide '
        'it until each pair of ▶◀ marks makes a straight line. Use a glue stick, or tape on the back.</li>'
        '<li><b>Join the rows</b> from top to bottom: the lower row goes on top, with the ▲▼ marks lined up.</li>'
        '</ol>')))

    b.append(Bloque('m-datos n2', 372, 690, 166, 47, (
        '<h2>Good to know</h2><ul>'
        '<li><b>Southern Hemisphere seasons:</b> summer from December to February, autumn from March to May, winter from '
        'June to August and spring from September to November.</li>'
        '<li><b>What this map is for:</b> finding your way and planning. It does not confirm jobs, wages or visa '
        'conditions: check those on immigration.govt.nz and in each job ad.</li>'
        '<li><b>Dates:</b> parks, sectors and calendar accessed on 2026-10-21; LINZ highways, lakes and names, and the '
        'facts in the curiosity boxes, on 2026-10-22; population from the 2023 Census.</li>'
        '</ul>')))

    b.append(Bloque('m-fuentes n4" data-meta="', 462, 432, 84, 67, (
        '<b>Sources.</b> Region boundaries: Stats NZ (2017) via geoBoundaries, CC BY 4.0. '
        'National parks: Department of Conservation, “DOC Public Conservation Land” (NaPALIS), CC BY 4.0, accessed 2026-10-21. '
        'State Highways and lakes: LINZ, Topo 1:250k, CC BY 4.0, downloaded 2026-10-22. '
        'Rivers and ferry: Natural Earth 1:10 m, public domain. '
        'Sectors: Stats NZ (Agricultural Production Statistics 2025, Agricultural Production Census 2022, Business '
        'Demography 2025), via Figure.NZ. Calendar: Work and Income and PickNZ. '
        'Terrain: Terrain Tiles (Mapzen, on AWS) with the LINZ elevation model (CC BY 4.0), SRTM and ETOPO1. '
        'Population: Stats NZ, 2023 Census. Names: New Zealand Gazetteer (LINZ), 2026-10-22. Heights: Aoraki/Mount Cook, '
        '2014 survey; Taranaki Maunga, Te Kāhui Tupua Act 2025; the others, reference values. '
        'Curiosities: DOC, Te Ara, NZHistory, GeoNet, NIWA, NZKGI, AF8 and others, with links in '
        'datos/nz/curiosidades.json. Kiwi plate: J. G. Keulemans (1888), public domain. '
        'Projection NZTM2000.<br>'
        'NZ-A-00 · version 2 · 2026-10-22 · Enciclopedia para imprimir')))
    b += curiosidades()
    return b


# ---------------------------------------------------------------- curiosidades
# Textos verificados con fuentes oficiales (DOC, Te Ara, NZHistory, GeoNet, NIWA, NZKGI); cada uno lleva sus
# fuentes en datos/nz/curiosidades.json. Van en el mar, en recuadros como los demás.
CUR = json.loads((RAIZ / 'datos' / 'nz' / 'curiosidades.json').read_text())


def imagen_lapiz(slug, ancho_px, vineta=0.0):
    """Versión a lápiz de imagenes/<slug>/maestra.jpg: el trazo sale de una sobreexposición de color (gris sobre su
    negativo desenfocado) y queda en grafito con transparencia, así se apoya en el mar sin recuadro. 'vineta'
    (0 a 1) desvanece los bordes hacia afuera. Devuelve la ruta relativa a hojas/nz-a/ y salida/pruebas/."""
    import numpy as np
    from PIL import Image, ImageFilter
    destino = RAIZ / 'hojas' / 'nz-a' / 'img' / f'{slug}-lapiz.png'
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(RAIZ / 'imagenes' / slug / 'maestra.jpg').convert('L')
        im = im.resize((ancho_px, round(im.height * ancho_px / im.width)), Image.LANCZOS)
        g = np.asarray(im).astype(float)
        borroso = np.asarray(Image.fromarray((255 - g).astype('uint8')).filter(ImageFilter.GaussianBlur(ancho_px / 150)))
        trazo = np.clip(g * 255 / np.maximum(1, 255 - borroso.astype(float)), 0, 255)
        oscuro = np.clip((250 - trazo) / 105, 0, 1) ** 0.75
        if vineta:
            h, w = oscuro.shape
            yy, xx = np.mgrid[0:h, 0:w]
            r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
            oscuro *= np.clip((1 - r) / vineta, 0, 1) ** 0.7
        rgba = np.zeros(oscuro.shape + (4,), dtype='uint8')
        rgba[..., :3] = (58, 48, 40)  # grafito cálido
        rgba[..., 3] = (oscuro * 235).astype('uint8')
        Image.fromarray(rgba, 'RGBA').save(destino, optimize=True)
    return f'../../hojas/nz-a/img/{slug}-lapiz.png'


def curiosidades():
    out = []
    k = CUR['kiwi']
    ave = f'<img class="ave" src="{imagen_lapiz(k["ave"]["imagen"], 700, vineta=0.35)}" alt="">'
    fruta = f'<img class="fruta" src="{imagen_lapiz(k["fruta"]["imagen"], 500, vineta=0.2)}" alt="">'
    out.append(Bloque('m-kiwi n3', 436, 70, 106, 125, (
        '<h2>Kiwi, kiwi and Kiwis</h2>'
        f'<div class="fila">{ave}<p>{k["ave"]["texto"]}</p></div>'
        f'<div class="fila inversa"><p>{k["fruta"]["texto"]}</p>{fruta}</div>'
        f'<p class="gente">{k["gente"]["texto"]}</p>'
        + (f'<p class="credito" data-meta>{k["ave"]["credito"]}</p>' if k['ave'].get('credito') else ''))))
    out.append(Bloque('m-geo n3', 196, 150, 112, 64, (
        '<h2>A young, restless land</h2><dl>'
        + ''.join(f'<dt>{g["t"]}</dt><dd>{g["texto"]}</dd>' for g in CUR['geografia']) + '</dl>')))
    out.append(Bloque('m-slang n3', 238, 681, 118, 47, (
        '<h2>Kiwi English you will hear</h2><div class="pares">'
        + ''.join(f'<div><b>{w}</b> {s}</div>' for w, s in CUR['slang']) + '</div>')))
    out.append(Bloque('m-historia n3', 238, 590, 118, 86, (
        '<h2>A short history</h2><dl>'
        + ''.join(f'<dt>{h["anio"]}</dt><dd>{h["texto"]}</dd>' for h in CUR['historia']) + '</dl>')))
    out.append(Bloque('m-notas n2', 372, 741, 166, 61, (
        '<h2>On the map</h2><dl>'
        + ''.join(f'<dt><span class="cur-l">{n["letra"]}</span></dt><dd><b>{n["lugar"]}.</b> {n["texto"]}</dd>'
                  for n in CUR['mapa']) + '</dl>')))
    return out
