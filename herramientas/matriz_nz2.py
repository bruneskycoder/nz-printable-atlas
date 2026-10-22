#!/usr/bin/env python3
"""NZ-A-99 v2, «¿Dónde ir?»: las 16 regiones de un vistazo (borrador).

    cd herramientas && python3 matriz_nz2.py

Cuatro preguntas por región, con semáforo (comparando las 16 regiones), dibujitos de los sectores fuertes y un
mini mapa; una columna para pintar tu nota. Mismos datos que las fichas v2.
"""
import json

from atlas_nz import RAIZ, esc
from fichas_nz import datos, mapa_ubicacion
from fichas_nz2 import FECHA, SECTOR_ES, num, rango, sectores
from glifos import glifo_html

COLOR = {'v': 'verde', 'a': 'ambar', 'r': 'rojo'}


def semaforo(valores, menor_es_mejor=True):
    """iso -> 'v', 'a' o 'r' por tercios entre las 16 regiones."""
    orden = sorted(valores, key=lambda iso: valores[iso], reverse=not menor_es_mejor)
    return {iso: 'v' if i < 5 else 'a' if i < 11 else 'r' for i, iso in enumerate(orden)}


def matriz(dest):
    D = datos()
    R = D['regiones']
    dist = json.loads((RAIZ / 'datos' / 'nz' / 'distancias-regiones.json').read_text())
    s_des = semaforo({r['iso']: r['desempleo'] for r in R})
    s_alq = semaforo({r['iso']: r['alquiler'] for r in R})
    # Sectores en los que la región está entre las 3 primeras del país, del mejor puesto al peor (hasta 5)
    fuertes = {r['iso']: [s['clave'] for s in sorted(sectores(), key=lambda s: rango(s, r['iso']) or 99)
                          if (rango(s, r['iso']) or 99) <= 3][:5] for r in R}
    usados = sorted({k for v in fuertes.values() for k in v}, key=list(SECTOR_ES).index)
    pmax = max(r['poblacion'] for r in R)
    amax = max(r['alquiler'] for r in R)
    filas = ''
    for isla, nombre_isla in (('norte', 'North Island'), ('sur', 'South Island')):
        for k, r in enumerate([x for x in R if x['isla'] == isla]):
            es = r['estacion']
            glifos = ''.join(glifo_html(k, 5.2) for k in fuertes[r['iso']]) or '<span class="nada" data-meta>ninguno entre los 3 primeros</span>'
            marca = '*' if r.get('desempleo_grupo') else ''
            filas += (
                f'<tr{" class=\"isla-sur\"" if isla == "sur" and k == 0 else ""}><td class="mini"><div class="mapa">{mapa_ubicacion(r["iso"])}</div></td>'
                f'<td class="reg"><b>{r["n"]}. {esc(r["nombre"])}</b> <span data-meta>{esc(dist[r["iso"]]["ciudad"])}</span></td>'
                f'<td class="trabajo"><span class="chip {COLOR[s_des[r["iso"]]]}">{num(r["desempleo"], 1)} %{marca}</span>'
                f'<span class="glifos">{glifos}</span></td>'
                f'<td class="viv"><span class="chip {COLOR[s_alq[r["iso"]]]}">NZ$ {r["alquiler"]}</span>'
                f'<span class="barra"><i style="width:{r["alquiler"] / amax * 100:.0f}%"></i></span></td>'
                f'<td class="clima"><span><i class="ic sol"></i>{num(es["max"], 0)}°</span><span><i class="ic frio"></i>{num(es["min_jul"], 0)}°</span>'
                f'<span><i class="ic lluvia"></i>{num(es["lluvia"])}</span></td>'
                f'<td class="gente"><span class="barra gris"><i style="width:{max(r["poblacion"] / pmax * 100, 2):.0f}%"></i></span>'
                f'<span>{num(r["poblacion"] / 1000)} mil</span></td>'
                f'<td class="nota">{"<i></i>" * 5}</td></tr>')
    leyenda_glifos = ' '.join(f'<span>{glifo_html(k, 4.5)} {SECTOR_ES[k][0].lower()}</span>' for k in usados)
    hoja = (
        '<div class="hoja apaisada matriz2 mural" data-tinta-max="30">'
        f'<header><span class="coleccion">Atlas de Nueva Zelanda · NZ-A-99 · la decisión · v2 · {FECHA}</span>'
        '<h1>¿Dónde ir? Las 16 regiones de un vistazo</h1>'
        '<p class="bajada">Verde: entre las 5 mejores de las 16 para quien llega con working holiday; rojo: entre las 5 peores; '
        'ámbar: en el medio. Pintá de 1 a 5 círculos según cuánto te atrae cada región.</p></header>'
        '<table><thead><tr><th></th><th>Región<span data-meta>ciudad principal</span></th>'
        '<th>¿Hay trabajo?<span data-meta>desempleo y sectores fuertes</span></th>'
        '<th>¿Cuánto sale vivir?<span data-meta>alquiler semanal típico</span></th>'
        '<th>¿Qué clima?<span data-meta>verano · invierno · lluvia (mm)</span></th>'
        '<th>¿Ciudad o campo?<span data-meta>población</span></th>'
        '<th>Tu nota<span data-meta>pintá de 1 a 5</span></th></tr></thead>'
        f'<tbody>{filas}</tbody></table>'
        f'<footer data-meta><p class="glifos-ley">Sectores fuertes (la región está entre las 3 primeras del país): {leyenda_glifos}</p>'
        '<p>Fuentes: Stats NZ (desempleo, mar. 2026, * publicado junto con regiones vecinas; Censo 2023), Tenancy Services '
        '(contratos nuevos, jun. 2026, media geométrica) y NIWA (1991–2020). Detalle en cada ficha y en NZ-A-fuentes.</p></footer></div>')
    (dest / 'NZ-A-99.html').write_text(
        '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n<title>NZ-A-99 ¿Dónde ir?</title>\n'
        '<link rel="stylesheet" href="../../estilo/combi.css">\n<link rel="stylesheet" href="../../estilo/atlas-nz.css">\n'
        '<link rel="stylesheet" href="../../estilo/mural-nz.css">\n<link rel="stylesheet" href="../../estilo/matriz-nz2.css">\n'
        '<style>@page { size: A4 landscape; }</style>\n'
        f'</head>\n<body>\n{hoja}\n</body>\n</html>\n')
    print('  NZ-A-99.html')


if __name__ == '__main__':
    matriz(RAIZ / 'salida' / 'pruebas')
