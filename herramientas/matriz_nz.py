"""NZ-A-99, «¿Dónde ir?»: matriz de decisión del atlas de Nueva Zelanda.

Página 1: la tabla. A la izquierda los datos con fuente, en el medio las
estimaciones y a la derecha las columnas vacías para los juicios propios.
Página 2: cómo usarla, qué muestran los datos y renglones para la decisión.
"""
from atlas_nz import esc
from fichas_nz import FECHA, VERSION, datos, num

CRITERIOS = ['Trabajo', 'Plata', 'Experiencia', 'Gente diversa', 'Armonía con el trabajo']


def meses_temporada(r):
    meses = set()
    for _, m in r['trabajo']:
        if m != 'todo':
            meses.update(m)
    return meses


def cuarto(r):
    return round(r['alquiler'] / 3 / 5) * 5


def matriz(destino):
    D = datos()
    p = D['pais']
    R = D['regiones']
    columnas = [  # (título, unidad, valor, decimales)
        ('Población', 'miles', lambda r: r['poblacion'] / 1000, 0),
        ('Nacidos afuera', '%', lambda r: r['nacidos_exterior'], 1),
        ('Māori', '%', lambda r: r['maori'], 1),
        ('Desempleo', '%, mar. 2026', lambda r: r['desempleo'], 1),
        ('Alquiler', 'NZ$ por semana', lambda r: r['alquiler'], 0),
        ('Máxima de verano', '°C', lambda r: r['estacion']['max'], 1),
        ('Mínima de julio', '°C', lambda r: r['estacion']['min_jul'], 1),
        ('Lluvia', 'mm por año', lambda r: r['estacion']['lluvia'], 0),
    ]
    estim = [
        ('Cuarto', 'NZ$ por semana', cuarto, 0),
        ('Horas', 'de salario mínimo', lambda r: cuarto(r) / p['salario_minimo'], 1),
        ('Meses', 'con temporada', lambda r: len(meses_temporada(r)), 0),
    ]
    maximos = [max(f(r) for r in R) for _, _, f, _ in columnas]
    minimos = [min(f(r) for r in R) for _, _, f, _ in columnas]

    def celda_dato(i, r):
        _, _, f, dec = columnas[i]
        v = f(r)
        lo = min(0, minimos[i])
        ancho = (v - lo) / (maximos[i] - lo) * 90 if maximos[i] != lo else 0
        marca = '*' if i == 3 and r.get('desempleo_grupo') else ''
        return f'<td class="dato"><i style="width:{max(ancho, 0):.0f}%"></i>{num(v, dec)}{marca}</td>'

    def rot(t, u, clase):
        unidad = f'<br><span class="u" data-meta>{u}</span>' if u else ''
        return f'<th class="{clase} rot"><span>{t}{unidad}</span></th>'

    cab = ('<colgroup><col style="width:37mm">' + '<col style="width:12.6mm">' * 8
           + '<col style="width:13.2mm">' * 3 + '<col style="width:15.6mm">' * 6 + '</colgroup>')
    grupos = ('<tr class="grupo"><th></th>'
              '<th colspan="8" style="color:var(--azul)">Datos con fuente</th>'
              '<th colspan="3" style="color:var(--ocre)">Estimaciones</th>'
              '<th colspan="6" style="color:var(--bermellon)">Tus juicios, a lápiz: de 1 a 5</th></tr>')
    titulos = ('<tr><th style="text-align:left;vertical-align:bottom">Región</th>'
               + ''.join(rot(t, u, 'g-dato') for t, u, _, _ in columnas)
               + ''.join(rot(t, u, 'g-est') for t, u, _, _ in estim)
               + ''.join(rot(c, '', 'g-juicio') for c in CRITERIOS)
               + rot('Total', 'peso × puntaje', 'g-juicio') + '</tr>')
    pesos = ('<tr class="pesos"><td>Tu peso: de 1 a 3</td>'
             '<td colspan="11" style="font-weight:400">Primero anotá cuánto te importa cada criterio: '
             '1 poco, 2 bastante, 3 mucho. →</td>'
             + '<td class="juicio"></td>' * 5 + '<td style="background:#e6e6e6"></td></tr>')
    filas = []
    for isla in ('norte', 'sur'):
        nombre_isla = 'Isla Norte · Te Ika-a-Māui' if isla == 'norte' else 'Isla Sur · Te Waipounamu'
        filas.append(f'<tr class="isla"><td colspan="18" data-meta>{nombre_isla}</td></tr>')
        for r in [x for x in R if x['isla'] == isla]:
            celdas = ''.join(celda_dato(i, r) for i in range(len(columnas)))
            celdas += ''.join(f'<td class="est">{num(f(r), dec)}</td>' for _, _, f, dec in estim)
            celdas += '<td class="juicio"></td>' * 6
            filas.append(f'<tr><td class="reg"><span class="n">{r["n"]}</span>{esc(r["nombre"])}</td>{celdas}</tr>')
    tabla = f'<table class="matriz">{cab}<thead>{grupos}{titulos}</thead><tbody>{pesos}{"".join(filas)}</tbody></table>'
    nota = ('<p class="m-nota"><span class="etq dato" data-meta>dato</span> publicado por Stats NZ, NIWA o Tenancy Services; '
            'la barrita compara con el máximo de la columna. * Desempleo publicado junto con regiones vecinas. '
            '<span class="etq est" data-meta>estimación</span> cuarto = un tercio del alquiler; horas = cuarto ÷ salario mínimo '
            f'(NZ$ {num(p["salario_minimo"], 2)}); meses = calendario aproximado de las fichas. '
            'Cómo usarla y tu decisión: página 2.</p>')

    def top(f, n=3, alto=True, dec=1, unidad=''):
        orden = sorted(R, key=f, reverse=alto)[:n]
        return ', '.join(f'{esc(r["nombre"])} ({num(f(r), dec)}{unidad})' for r in orden)

    lectura = (
        '<h2>Lo que muestran los datos <span class="etq calc" data-meta>cálculo</span></h2><ul>'
        f'<li><b>Más gente nacida afuera:</b> {top(lambda r: r["nacidos_exterior"], unidad=" %")}.</li>'
        f'<li><b>Desempleo más bajo:</b> {top(lambda r: r["desempleo"], alto=False, unidad=" %")}.</li>'
        f'<li><b>Alquiler más bajo:</b> {top(lambda r: r["alquiler"], alto=False, dec=0)}.</li>'
        f'<li><b>Inviernos más templados:</b> {top(lambda r: r["estacion"]["min_jul"], unidad=" °C")}.</li>'
        f'<li><b>Más meses con temporada</b> (estimación): {top(lambda r: len(meses_temporada(r)), dec=0)}.</li>'
        '</ul><p class="m-nota">Son ordenamientos de la tabla, no recomendaciones. '
        'Una región grande esconde diferencias: mirá los distritos en su ficha.</p>')
    como = ('<h2>Cómo usar la matriz</h2><ol>'
            '<li>Anotá tu <b>peso</b>, de 1 a 3, para cada criterio en la fila roja.</li>'
            '<li>Leé los datos de cada región y su ficha (NZ-A-01 a 16). Poné un <b>puntaje de 1 a 5</b> en cada criterio.</li>'
            '<li><b>Total</b> = suma de peso × puntaje. Las dos regiones con más total son tus candidatas.</li>'
            '<li>Antes de decidir, revisá los avisos de trabajo y de cuartos del mes en que llegás: cambian rápido.</li>'
            '</ol>')
    criterios = ('<h2>Qué mirar para cada criterio</h2><ul>'
                 '<li><b>Trabajo:</b> desempleo y meses con temporada; en la ficha, el calendario.</li>'
                 '<li><b>Plata:</b> alquiler, cuarto y horas de salario mínimo.</li>'
                 '<li><b>Experiencia:</b> naturaleza, actividades y clima de la ficha.</li>'
                 '<li><b>Gente diversa:</b> nacidos afuera, māori y tamaño de las ciudades.</li>'
                 '<li><b>Armonía con el trabajo:</b> lo que te deja la jornada (clima, distancias, ritmo). '
                 'Es el criterio más personal.</li></ul>')
    consignas = (
        '<div class="consigna"><div class="cab"><span class="num">1</span><span class="que"><b>Mis dos regiones y por qué.</b> '
        'Nombrá los datos que te convencen.<span class="pista">Si querés practicar inglés: '
        '<span class="en">I\'d like to go to … because …</span></span></span><span class="ver" data-meta>NZ-A-99</span></div>'
        '<div class="escribir" data-renglones="3"></div></div>'
        '<div class="dos-consignas">'
        '<div class="consigna"><div class="cab"><span class="num">2</span><span class="que"><b>Plan B.</b> '
        'Si no hay trabajo o cuarto, ¿adónde voy?</span><span></span></div>'
        '<div class="escribir" data-renglones="2"></div></div>'
        '<div class="consigna"><div class="cab"><span class="num">3</span><span class="que"><b>Qué verifico antes de ir.</b> '
        'Avisos, alquiler del mes, temporada.</span><span></span></div>'
        '<div class="escribir" data-renglones="2"></div></div></div>')

    def cabecera(pagina, titulo, bajada):
        return (f'  <header class="cabecera">\n    <div class="codigo">NZ-A-99</div>\n    <div>\n'
                f'      <span class="coleccion">Atlas de Nueva Zelanda · proceso: la decisión · {pagina} de 2</span>\n'
                f'      <h1 class="titulo">{titulo}</h1>\n      <p class="bajada">{bajada}</p>\n    </div>\n'
                '    <div class="lateral">Fichas: NZ-A-01 a 16<br>Mapa mural: NZ-A-00</div>\n  </header>')

    pie = (f'  <footer class="pie">\n    <span>NZ-A-99 · versión {VERSION} · {FECHA}</span>\n'
           '    <span class="fuentes">Población, nacidos afuera y māori: Stats NZ, Censo 2023. Desempleo: Stats NZ, '
           'encuesta de fuerza laboral, mar. 2026. Alquiler: Tenancy Services, bonos de junio 2026. Clima: NIWA 1991–2020 '
           '(vía Figure.NZ), en la estación de cada ficha. Salario mínimo: Employment NZ, abril 2026. '
           f'Consultado el {FECHA}.</span>\n    <span>Enciclopedia para imprimir</span>\n  </footer>')

    html = '\n'.join([
        '<!doctype html>', '<html lang="es">', '<head>', '<meta charset="utf-8">',
        '<title>NZ-A-99 ¿Dónde ir? Matriz de decisión</title>',
        '<link rel="stylesheet" href="../../estilo/combi.css">',
        '<link rel="stylesheet" href="../../estilo/escritura.css">',
        '<link rel="stylesheet" href="../../estilo/atlas-nz.css">',
        '<style>@page { size: A4 landscape; }</style>', '</head>', '<body>',
        '<div class="hoja apaisada">',
        cabecera(1, '¿Dónde ir? Las 16 regiones en una tabla',
                 'A la izquierda, lo que se sabe; en el medio, lo que se estima; a la derecha, lo que decidís vos.'),
        f'  <main class="cuerpo">\n    {tabla}\n    {nota}\n  </main>',
        pie, '</div>',
        '<div class="hoja apaisada">',
        cabecera(2, '¿Dónde ir? Cómo decidir',
                 'Usá la tabla de la página 1, escribí tu decisión y mandame una foto si querés que la revisemos.'),
        '  <main class="cuerpo">',
        f'    <div class="m-pie">\n      <section>{como}</section>\n      <section>{criterios}</section>\n'
        f'      <section>{lectura}</section>\n    </div>',
        f'    <h2 class="m-dec">Mi decisión</h2>\n    {consignas}',
        '  </main>', pie, '</div>',
        '<script src="../../estilo/renglones.js"></script>', '</body>', '</html>', ''])
    (destino / 'NZ-A-99.html').write_text(html)
    print('  hojas/nz-a/NZ-A-99.html')
