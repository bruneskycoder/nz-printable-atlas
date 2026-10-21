"""Bloques de texto del mapa mural v2 (título, leyenda, tablas, armado, fuentes).
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
    celdas = ''.join(f'<div><i style="background:rgb{color[a]}"></i>{a:,}'.replace(',', '.') + '</div>' for a in cortes)
    return f'<div class="tintas">{celdas}<div class="u">m</div></div>'


GLIFOS_MAPA = [('lecheria', 'Lechería'), ('ovinos', 'Ovinos'), ('vacunos', 'Vacunos de carne'), ('fruta', 'Fruta'),
               ('vid', 'Viñedos'), ('hortalizas', 'Hortalizas'), ('forestal', 'Forestal'), ('frigorificos', 'Frigoríficos'),
               ('alojamiento', 'Alojamiento y turismo')]
NOMBRE_CORTO = {'vacunos': 'Vacunos', 'transporte': 'Transporte', 'tecnicos': 'Arquitectura e ing.', 'alojamiento': 'Alojamiento'}


def coma(x, dec=1):
    return f'{x:.{dec}f}'.replace('.', ',')


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
    cab1 = (f'<tr><th></th><th class="grupo" colspan="{len(campo)}">En el campo: animales y hectáreas</th>'
            f'<th class="grupo sep" colspan="{len(empleo)}">Empleos, febrero 2025</th></tr>')
    cab2 = '<tr><th></th>' + ''.join(
        f'<th class="cab{" sep" if s is empleo[0] else ""}"><span class="n">{NOMBRE_CORTO.get(s["clave"], s["nombre"])}</span>'
        f'{glifo_html(s["clave"], 4.6)}</th>' for s in sect) + '</tr>'
    tops = {s['clave']: principales(s) for s in sect}
    filas = []
    for i, iso in enumerate(ORDEN_REGIONES, start=1):
        if i in (1, 10):
            filas.append(f'<tr class="isla"><td colspan="{len(sect) + 1}" data-meta>'
                         f'{"Isla Norte · Te Ika-a-Māui" if i == 1 else "Isla Sur · Te Waipounamu"}</td></tr>')
        celdas = [f'<td class="reg"><span class="num" data-meta>{i}</span>{esc(nombre_region(iso))}</td>']
        for s in sect:
            v = s['porcentaje'][iso]
            sep = ' sep' if s is empleo[0] else ''
            if v is None:
                celdas.append(f'<td class="sd{sep}" data-meta>s/d</td>')
                continue
            tinte = min(62, round(v * 1.7))
            clase = ('top ' if iso in tops[s['clave']] else '') + ('oscuro' if tinte > 44 else '')
            celdas.append(f'<td class="{clase}{sep}" style="background:color-mix(in srgb, var(--s-{s["clave"]}) {tinte}%, white)">'
                          f'{coma(v)}</td>')
        filas.append('<tr>' + ''.join(celdas) + '</tr>')
    return ('<h2>¿Qué se produce en cada región?</h2>'
            '<p class="bajada">Qué parte del total del país tiene cada región, en %. Cuanto más oscura la celda, más concentrado '
            'está el sector; en negrita, las 4 regiones principales, que en el mapa llevan el glifo.</p>'
            f'<table class="tabla-sectores"><colgroup>{cols}</colgroup><thead>{cab1}{cab2}</thead><tbody>{"".join(filas)}</tbody></table>'
            '<p class="nota"><span class="aviso">Sectores y zonas orientativos; no representan vacantes activas, salarios ni '
            'garantía de contratación.</span> Muestran dónde está la actividad, no dónde hay puestos libres hoy.</p>'
            '<p class="nota">Campo: ganado al 30 de junio de 2025; fruta, viñedos, hortalizas y bosque, en hectáreas del censo '
            'de 2022. Empleos: personas empleadas en el lugar de trabajo (no cuenta a los dueños que trabajan solos). '
            '«s/d»: dato reservado por Stats NZ.</p>'
            '<p class="fuente" data-meta>Fuentes: Stats NZ, Agricultural Production Statistics 2025 (AGR003AA) y Agricultural '
            'Production Census 2022; Business Demography Statistics 2025 (BDS_BDS_001), vía Figure.NZ. Consultado el '
            f'{d["consultado"]}. Datos en datos/sectores-nz.json.</p>')


MESES_INI = ['E', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
TINTE_TAREA = {'C': 70, 'P': 45, 'R': 28, 'M': 18, 'V': 32}


def calendario():
    d = json.loads((RAIZ / 'datos' / 'calendario-nz.json').read_text())
    cols = '<col class="et">' + '<col>' * 12
    est = ('<tr class="estacion" data-meta><th></th><th class="verano" colspan="2">Verano</th><th class="otono" colspan="3">Otoño</th>'
           '<th class="invierno" colspan="3">Invierno</th><th class="primavera" colspan="3">Primavera</th>'
           '<th class="verano">Ver.</th></tr>')
    meses = '<tr><th></th>' + ''.join(f'<th>{m}</th>' for m in MESES_INI) + '</tr>'
    filas = []
    grupos = {'winz-calendario': 'Fruta, uva y hortalizas, mes a mes', 'winz-general': 'Otros trabajos, ventana general'}
    previo = None
    for f in d['filas']:
        if f['fuente'] != previo:
            filas.append(f'<tr class="grupo"><td colspan="13">{grupos[f["fuente"]]}</td></tr>')
            previo = f['fuente']
        zona = f' <span class="z">· {esc(f["zona"])}</span>' if f['zona'] else ''
        celdas = [f'<td class="et">{glifo_html(f["sector"], 3.6)}{esc(f["etiqueta"])}{zona}</td>']
        for m in f['meses']:
            if not m:
                celdas.append('<td class="vacio"></td>')
                continue
            tinte = TINTE_TAREA[m['t']]
            letra = '' if m['t'] == 'V' else m['t']
            color = 'white' if tinte >= 60 else '#1d2a36'
            sector = {'turismo': 'alojamiento', 'esqui': 'alojamiento'}.get(f['sector'], f['sector'])
            celdas.append(f'<td class="{"pico" if m["pico"] else ""}" style="background:color-mix(in srgb, var(--s-{sector}) {tinte}%, white);'
                          f'color:{color}">{letra}</td>')
        filas.append('<tr>' + ''.join(celdas) + '</tr>')
    return ('<h2>¿Cuándo hay trabajo de temporada?</h2>'
            f'<table class="tabla-calendario"><colgroup>{cols}</colgroup><thead>{est}{meses}</thead><tbody>{"".join(filas)}</tbody></table>'
            '<p class="nota"><b>C</b> cosecha · <b>P</b> poda · <b>R</b> raleo · <b>M</b> mantenimiento de plantas · '
            'recuadro: los meses de más trabajo. Ventanas orientativas: las temporadas cambian según cultivo, clima, '
            'empleador y año. En Marlborough, los viñedos dan trabajo casi todo el año (PickNZ), sin calendario mensual oficial.</p>'
            '<p class="fuente" data-meta>Fuentes: Work and Income, «Fruit and vegetable seasonal work» y «Finding seasonal '
            f'work»; PickNZ. Consultado el {d["consultado"]}. Datos en datos/calendario-nz.json.</p>')


def bloques(C, E):
    b = []
    pais = datos_pais()
    datos = ''
    if pais:
        datos = ('<div class="datos">'
                 f'<div><b>{pais["poblacion_txt"]}</b>habitantes (Censo {pais["censo"]})</div>'
                 f'<div><b>{pais["superficie_txt"]}</b>km² en las 16 regiones</div>'
                 '<div><b>16</b>regiones</div><div><b>13</b>parques nacionales</div></div>')
    escala_txt = f'1:{MURAL_ESCALA:,}'.replace(',', '.')
    b.append(Bloque('m-titulo', 8, 8, 164, 70, (
        '<span class="coleccion">Atlas de Nueva Zelanda · NZ-A-00 · mapa mural en 9 piezas</span>'
        '<h1>Nueva Zelanda<span class="mi">Aotearoa</span></h1>'
        '<p>Las 16 regiones, el relieve, los parques nacionales, las ciudades y las rutas. '
        'El número del círculo es la ficha de cada región: <b>NZ-A-01</b> a <b>16</b>.</p>'
        f'<p><b>Escala {escala_txt}</b> · 1 cm del mapa = {MURAL_ESCALA / 100_000:g} km · el norte está arriba.</p>'
        + datos)))

    filas = [
        (muestra('<rect class="c1" x="2.6" y="0.35" width="3.8" height="3.8"/>'), 'Más de 1 millón de habitantes'),
        (muestra('<path class="ruta1-borde" d="M0 2.25 H9"/><path class="ruta1" d="M0 2.25 H9"/>'), 'Ruta principal (<i>State Highway</i>)'),
        (muestra('<circle class="c2" cx="4.5" cy="2.25" r="1.45"/>'), '100.000 a 500.000'),
        (muestra('<path class="ruta2" d="M0 2.25 H9"/>'), 'Otra ruta importante'),
        (muestra('<circle class="c3" cx="4.5" cy="2.25" r="1.05"/>'), '25.000 a 100.000'),
        (muestra('<path class="ferry" d="M0 2.25 H9"/>'), 'Ferry entre las islas (por mar)'),
        (muestra('<circle class="c4" cx="4.5" cy="2.25" r="0.62"/>'), 'Pueblo o destino'),
        (muestra('<path class="limite" d="M0 2.25 H9"/>'), 'Límite de región'),
        (muestra('<path class="avion" transform="translate(4.5 2.25) scale(0.2) translate(-12 -12)" d="M3 11.2 H18.5 a1.6 0.8 0 0 1 0 1.6 H3 Z M10 11.2 L7 4 H8.8 L14.5 11.2 Z M10 12.8 L7 20 H8.8 L14.5 12.8 Z M4.5 11.2 L3 8 H4.3 L6.5 11.2 Z M4.5 12.8 L3 16 H4.3 L6.5 12.8 Z"/>'),
         'Aeropuerto con vuelos internacionales'),
        (muestra('<circle class="reg-c" cx="4.5" cy="2.25" r="2.1"/><text class="reg-num" x="4.5" y="3.35" text-anchor="middle">1</text>'),
         'Región y número de su ficha'),
        (muestra('<rect class="parque" x="0.5" y="0.5" width="8" height="3.5" rx="0.8"/>'), 'Parque nacional (DOC)'),
        (muestra('<path class="rio" d="M0 3 C3 0.5 6 4 9 1.5"/>'), 'Río'),
        (muestra('<path class="pico" d="M4.5 0.9 L5.65 2.95 L3.35 2.95 Z"/>'), 'Pico, con su altura'),
        (muestra('<rect class="lago" x="1.5" y="0.6" width="6" height="3.3" rx="1.2"/>'), 'Lago'),
    ]
    b.append(Bloque('leyenda', 8, 84, 164, 120, (
        '<h2>Cómo leer el mapa</h2><div class="filas">'
        + ''.join(f'<div class="f">{s}<span>{t}</span></div>' for s, t in filas)
        + '</div>'
        '<h3>Altura del terreno</h3>' + tintas_altura()
        + '<p class="nota">El sombreado imita una luz del noroeste: las laderas en sombra se oscurecen.</p>'
        f'<h3>Escala {escala_txt}</h3>' + escala_grafica()
        + '<h3>Sectores productivos</h3><p class="nota glifos-leyenda">'
        + ' '.join(f'<span>{glifo_html(k, 4.2)} {n}</span>' for k, n in GLIFOS_MAPA)
        + '</p><p class="nota">Cada sector marca con su glifo sus <b>4 regiones principales</b> del país (los números, en la '
          'tabla de abajo). Construcción, mantenimiento, logística y dibujo técnico siguen a la '
          'población: hay más trabajo donde hay más gente.</p>'
        + '<p class="nota">Tamaño de las ciudades: categoría aproximada, según el Censo 2023 de Stats NZ. Los nombres son los oficiales '
          '(LINZ), en inglés y en te reo māori; la barra «/» separa los dos nombres oficiales de un mismo lugar.</p>')))

    b.append(Bloque('m-matriz', 8, 276, 164, 250, matriz()))
    b.append(Bloque('m-calendario', 372, 548, 166, 132, calendario()))

    # Chatham Islands (pieza 9), a la misma escala
    ch = [g for _, g in capa('chatham')]
    citm = Encuadre(MURAL_ESCALA, 3_468_000, 10_036_000)
    geo = unary_union([citm.geom(g) for g in ch])
    minx, miny, maxx, maxy = geo.bounds
    b.append(Bloque('m-chatham', 462, 345, 84, 80, (
        f'<svg class="mapa" viewBox="{minx - 3:.1f} {miny - 3:.1f} {maxx - minx + 6:.1f} {maxy - miny + 6:.1f}" '
        f'style="width:{maxx - minx + 6:.1f}mm;height:{maxy - miny + 6:.1f}mm;margin:0 auto 1.5mm">'
        f'<path class="lago" style="fill:none" d="{ruta(geo.buffer(1.0).boundary)}"/>'
        f'<path style="fill:#f3f0e1;stroke:#1f3a55;stroke-width:0.26" d="{ruta(geo)}"/></svg>'
        '<p class="t"><b>Chatham Islands / Rēkohu</b><br>Están a unos 800 km al este de Banks Peninsula, a la misma latitud '
        'que este recuadro. Dibujadas a la misma escala que el mapa, pero corridas de su lugar. No son una de las 16 regiones: '
        'tienen un consejo propio.</p>')))

    b.append(Bloque('m-armado', 8, 467, 164, 64, (
        '<h2>Cómo armar el mural</h2><ol>'
        '<li><b>Prueba de unión primero.</b> Imprimí solo las piezas 2 y 3 a tamaño real (100 %), una sola cara, y unilas como '
        'dice el paso 3. Si las marcas ▶◀ quedan desfasadas menos de 1 mm, imprimí las otras siete.</li>'
        '<li><b>Cortá</b> el margen izquierdo de las piezas de la 2.ª y la 3.ª columna, y el de arriba de las de la 2.ª y la '
        '3.ª fila, por la línea de rayas.</li>'
        '<li><b>Uní cada fila</b> de izquierda a derecha: apoyá cada pieza sobre la franja «pegar acá» de la anterior y corréla '
        'hasta que cada par de marcas ▶◀ forme una línea recta. Pegá con adhesivo en barra o cinta por detrás.</li>'
        '<li><b>Uní las filas</b> de arriba hacia abajo: la de abajo va encima, con las marcas ▲▼ alineadas.</li>'
        '</ol>')))

    b.append(Bloque('m-datos', 372, 690, 166, 70, (
        '<h2>Datos útiles</h2><ul>'
        '<li><b>Las islas:</b> North Island / Te Ika-a-Māui, South Island / Te Waipounamu y Stewart Island / Rakiura.</li>'
        '<li><b>Estaciones del hemisferio sur:</b> verano de diciembre a febrero, otoño de marzo a mayo, invierno de junio a '
        'agosto y primavera de septiembre a noviembre.</li>'
        '<li><b>Para qué sirve este mapa:</b> orientarte y planificar. No confirma empleos, salarios ni condiciones de la visa: '
        'eso se verifica en immigration.govt.nz y en cada aviso de trabajo.</li>'
        '<li><b>Fechas:</b> parques, sectores y calendario consultados el 2026-10-21; población del Censo 2023.</li>'
        '</ul>')))

    b.append(Bloque('m-fuentes" data-meta="', 462, 432, 84, 98, (
        '<b>Fuentes.</b> Límites de las regiones: Stats NZ (2017) vía geoBoundaries, CC BY 4.0. '
        'Parques nacionales: Department of Conservation, «DOC Public Conservation Land» (NaPALIS), CC BY 4.0, consultado el 2026-10-21. '
        'Lagos, ríos y rutas: Natural Earth 1:10 m, dominio público. '
        'Sectores: Stats NZ (encuesta agropecuaria 2025, censo agropecuario 2022, demografía de empresas 2025), vía Figure.NZ. '
        'Calendario: Work and Income y PickNZ. '
        'Relieve: Terrain Tiles (Mapzen, en AWS) con el modelo de elevación de LINZ (CC BY 4.0), SRTM y ETOPO1. '
        'Población: Stats NZ, Censo 2023. Nombres: New Zealand Gazetteer (LINZ). Alturas: Aoraki / Mount Cook, '
        'medición de 2014; Taranaki Maunga, ley Te Kāhui Tupua de 2025; las demás, valores de referencia. '
        'Proyección NZTM2000.<br>'
        'NZ-A-00 · versión 2 · 2026-10-21 · Enciclopedia para imprimir')))
    return b
