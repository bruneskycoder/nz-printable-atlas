#!/usr/bin/env python3
"""NZ-A-fuentes: las fuentes completas de las 16 fichas regionales, con enlace, y cómo se calculó cada dato.

    cd herramientas && python3 fuentes_nz.py

Escribe salida/pruebas/NZ-A-fuentes.html. Los números de cada región son los mismos que imprime el dorso de su
ficha, porque se arman con el mismo recorrido (fichas_nz2.ficha con un registro de Fuentes).
"""
import json
import re

from atlas_nz import RAIZ, esc
from fichas_nz2 import ETIQUETAS, FECHA, Fuentes, datos, ficha

CURIOSIDADES = json.loads((RAIZ / 'datos' / 'nz' / 'curiosidades-regiones.json').read_text())

METODOS = [
    ('Sectores en los que la región destaca',
     'Participación de la región en el total nacional de cada indicador: valor de la región ÷ total del país. El puesto '
     'ordena las 16 regiones en ese indicador. Los indicadores cambian entre sectores (hectáreas, cabezas de ganado, '
     'empleados) y no muestran cómo se reparte el empleo dentro de la región. Los valores que Stats NZ suprime por '
     'confidencialidad no se cuentan. En el frente, «Se destaca» muestra el mejor puesto de la región, solo si está '
     'entre los cuatro primeros.'),
    ('Temporadas y puestos',
     'Work and Income publica, por región, zona y cultivo, las tareas de cada mes (cosecha, poda, raleo, mantenimiento) '
     'y marca en negrita los meses de más trabajo. La franja de cada puesto pinta los meses con alguna tarea y pone '
     'borde a los de más trabajo; debajo se detalla cada cultivo. No son fechas de contratación: se contrata antes. '
     'Para frigoríficos, esquila, lechería, forestal, turismo y esquí se usa la página general de Work and Income, '
     'sin desglose por región. Los huertos que Work and Income publica como «Nelson» cuentan también para Tasman. '
     'Taranaki, West Coast y Southland no figuran en el calendario de fruta. Ningún organismo publica fechas de la '
     'temporada de empaque: la nota sale de avisos de empleo. Requisitos según Tahatū Career Navigator.'),
    ('Vivienda',
     'Bono: depósito de garantía que se registra en Tenancy Services al firmar un contrato; «nuevos contratos '
     'registrados» son los bonos presentados en el período. Alquiler de la región: media geométrica de los contratos '
     'nuevos de junio de 2026. Habitación: categoría «Room» de la herramienta de alquileres de mercado («a room rented '
     'separately with shared facilities in a building intended for less than 6 people»), en el barrio central de la '
     'ciudad principal; si tiene menos de 30 bonos activos, en el barrio con más bonos; si ninguno llega, «sin datos». '
     'Tenancy Services advierte que los datos son provisorios por la migración de su sistema de bonos. Horas: alquiler '
     'semanal de la habitación ÷ salario mínimo adulto bruto (NZ$23,95 por hora desde el 1 abr. 2026). Sirve para '
     'comparar regiones: no es ingreso neto ni incluye comida, transporte o servicios.'),
    ('Clima',
     'Normales de NIWA 1991–2020 (días de lluvia: 1981–2010) de la estación de la ciudad principal o la más cercana. '
     'Una estación no representa toda la región. Los puestos comparan las 12 estaciones del atlas.'),
    ('Movilidad',
     'Kilómetros por ruta entre la ciudad principal de la región y la de cada región vecina: camino más corto sobre la '
     'red de rutas de LINZ (Topo 1:250k, todas las rutas), con las puntas sueltas empalmadas a menos de 60 m y '
     'redondeado a 5 km. Contra distancias conocidas da un error de pocos km; un GPS puede elegir otra ruta. Las '
     'conexiones (aeropuertos, trenes, ferris, buses) salen de los sitios oficiales de cada servicio.'),
    ('Mapas',
     'Rutas, State Highways y lagos: LINZ, Topo 1:250k, CC BY 4.0. Ríos y ferri: Natural Earth 1:10 m, dominio '
     'público. Relieve: Terrain Tiles (Mapzen, en AWS) con el modelo de elevación de LINZ (CC BY 4.0), SRTM y ETOPO1. '
     'Límites regionales: Stats NZ (2017) vía geoBoundaries, CC BY 4.0.'),
]


def pagina(contenido, n, total):
    return (f'<div class="hoja fuentes-nz" data-tinta-max="15">{contenido}'
            f'<footer class="pie" data-meta><span>NZ-A-fuentes · v1 · {FECHA}</span><span>hoja {n} de {total}</span></footer></div>')


def main(dest=RAIZ / 'salida' / 'pruebas'):
    import fichas_nz2
    D = datos()
    pruebas = RAIZ / 'salida' / 'pruebas'  # ahí van los relieves de las fichas que se arman solo para numerar las fuentes
    pruebas.mkdir(parents=True, exist_ok=True)
    ajuste = json.loads((RAIZ / 'datos' / 'nz' / 'fichas-ajuste.json').read_text())
    regiones = []
    for r in D['regiones']:
        F = Fuentes()
        fichas_nz2.MAX_PUESTOS = ajuste.get(r['iso'], {}).get('puestos', 5)  # misma lista de puestos que la ficha
        ficha(r, D, pruebas, F)
        items = ''.join(f'<li data-meta><b>{i}</b> {esc(re.sub(r" \(https?://[^)]*\)", "", F.detalle[t][0]))}'
                        + (f' <a href="{esc(F.detalle[t][1])}">{esc(F.detalle[t][1])}</a>' if F.detalle[t][1] else '') + '</li>'
                        for i, t in enumerate(F.lista, start=1))
        regiones.append(f'<section class="region"><h2>NZ-A-{r["n"]:02d} · {esc(r["nombre"])}</h2><ol>{items}</ol></section>')
    etiquetas = ' · '.join(f'<b>{v}</b>' for v in ETIQUETAS.values())
    metodos = ''.join(f'<section><h3>{t}</h3><p>{tx}</p></section>' for t, tx in METODOS)
    portada = ('<header class="cabecera-f"><span class="coleccion">Atlas de Nueva Zelanda · fichas regionales NZ-A-01 a 16</span>'
               '<h1>Fuentes y métodos</h1><p class="bajada">Cada ficha numera sus fuentes al dorso. Acá están completas, con '
               'enlace, y se explica cómo se calculó cada dato. Consultadas el 21 y 22 oct. 2026.</p></header>'
               f'<p class="etiquetas">Tipos de dato: {etiquetas}. Dato oficial: publicado por un organismo. Estimación: '
               'aproximación. Cálculo: cuenta propia con datos de la ficha. Recomendación: consejo práctico. Orientativo: '
               'útil, sin garantía.</p>' + metodos)
    dibujos = ''
    for r in D['regiones']:
        c = CURIOSIDADES.get(r['iso'])
        if not c:
            continue
        ruta = RAIZ / 'imagenes' / c['imagen'] / 'ficha.json'
        pag = json.loads(ruta.read_text()).get('pagina', '') if ruta.exists() else ''
        dibujos += (f'<li data-meta><b>{esc(r["nombre"])}</b>: {esc(c["credito"])}'
                    + (f' <a href="{esc(pag)}">{esc(pag)}</a>' if pag else '') + '</li>')
    dibujos = ('<section class="dibujos"><h2>Dibujos</h2><p data-meta>Cada dibujo es una versión a lápiz, hecha con un filtro, '
               f'de una lámina de Wikimedia Commons.</p><ol>{dibujos}</ol></section>')
    bloques = [portada] + [''.join(regiones[i:i + 2]) for i in range(0, 16, 2)] + [dibujos]
    hojas = ''.join(pagina(b, i, len(bloques)) for i, b in enumerate(bloques, start=1))
    (dest / 'NZ-A-fuentes.html').write_text(
        '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n<title>NZ-A-fuentes</title>\n'
        '<link rel="stylesheet" href="../../estilo/combi.css">\n<link rel="stylesheet" href="../../estilo/atlas-nz.css">\n'
        '<link rel="stylesheet" href="../../estilo/fuentes-nz.css">\n'
        f'</head>\n<body>\n{hojas}\n</body>\n</html>\n')
    fichas_nz2.MAX_PUESTOS = 5
    print(f'  {(dest / "NZ-A-fuentes.html").relative_to(RAIZ)}')


if __name__ == '__main__':
    main()
