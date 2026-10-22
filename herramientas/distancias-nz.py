#!/usr/bin/env python3
"""Distancias por ruta entre la ciudad principal de cada región y la de cada región vecina
(datos/nz/distancias-regiones.json), para el bloque de movilidad de las fichas.

    git fetch origin datos-linz
    python3 herramientas/distancias-nz.py

Es un cálculo propio sobre la red de rutas de LINZ (Topo 1:250k, todas las rutas, no solo las State Highways):
el camino más corto, redondeado a 5 km. (Solo con State Highways faltaba el cruce de la cordillera entre Napier y Palmerston North.) Las líneas de LINZ no están cortadas
en los cruces, así que antes se llevan las puntas sueltas hasta la ruta más cercana (a menos
de 60 m) y se cortan todas en cada cruce. Contra distancias conocidas da un error de pocos
km (Auckland–Wellington 629 km, Christchurch–Queenstown 479 km). Un GPS puede elegir otra
ruta, por caminos que no son State Highway.
"""
import gzip
import heapq
import json
import subprocess
from collections import Counter, defaultdict

from shapely.geometry import LineString, Point, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

from atlas_nz import DATOS, RAIZ, capa, tabla

PASO = 20  # m: puntas a menos de esto son el mismo nodo
# Centro urbano principal de cada región (el mayor de su consejo regional, Censo 2023)
PRINCIPAL = {'NTL': 'Whangārei', 'AUK': 'Auckland', 'WKO': 'Hamilton', 'BOP': 'Tauranga', 'GIS': 'Gisborne',
             'HKB': 'Napier', 'TKI': 'New Plymouth', 'MWT': 'Palmerston North', 'WGN': 'Wellington', 'TAS': 'Richmond',
             'NLS': 'Nelson', 'MBH': 'Blenheim', 'WTC': 'Greymouth', 'CAN': 'Christchurch', 'OTA': 'Dunedin',
             'STL': 'Invercargill'}
EXTRA = {'Richmond': (173.183, -41.338)}  # no figura en lugares.json


def red_state_highways():
    crudo = subprocess.run(['git', '-C', str(RAIZ), 'show', 'origin/datos-linz:rutas.geojson.gz'],
                           check=True, capture_output=True).stdout
    lineas = [shape(f['geometry']) for f in json.loads(gzip.decompress(crudo))['features'] if f['geometry']]

    def nodo(c):
        return (round(c[0] / PASO), round(c[1] / PASO))
    puntas = Counter(nodo(c) for g in lineas for c in (g.coords[0], g.coords[-1]))
    arbol = STRtree(lineas)
    unidas = []
    for i, g in enumerate(lineas):
        cs = list(g.coords)
        for k in (0, -1):
            if puntas[nodo(cs[k])] > 1:
                continue  # ya empalma con otra punta
            p = Point(cs[k])
            cerca = [j for j in arbol.query(p.buffer(60)) if j != i and lineas[j].distance(p) < 60]
            if cerca:
                j = min(cerca, key=lambda j: lineas[j].distance(p))
                q = lineas[j].interpolate(lineas[j].project(p))
                cs[k] = (q.x, q.y)
        unidas.append(LineString(cs))
    grafo = defaultdict(list)
    for s in unary_union(unidas).geoms:
        a, b = nodo(s.coords[0]), nodo(s.coords[-1])
        grafo[a].append((b, s.length))
        grafo[b].append((a, s.length))
    return grafo


def distancia(grafo, origen, destino):
    dist, cola = {origen: 0}, [(0, origen)]
    while cola:
        d, n = heapq.heappop(cola)
        if n == destino:
            return d
        if d > dist[n]:
            continue
        for m, w in grafo[n]:
            if d + w < dist.get(m, float('inf')):
                dist[m] = d + w
                heapq.heappush(cola, (d + w, m))
    return None


def main():
    from pyproj import Transformer
    nztm = Transformer.from_crs(4326, 2193, always_xy=True)
    grafo = red_state_highways()
    nodos = list(grafo)

    def cercano(lon, lat):
        x, y = nztm.transform(lon, lat)
        return min(nodos, key=lambda n: (n[0] * PASO - x) ** 2 + (n[1] * PASO - y) ** 2)
    regiones = {p['iso']: (p['nombre'], g) for p, g in capa('regiones')}
    lugares = {c['n']: c for c in tabla('lugares')['lugares']}
    principal = {iso: lugares.get(n) or {'n': n, 'lon': EXTRA[n][0], 'lat': EXTRA[n][1]} for iso, n in PRINCIPAL.items()}
    salida = {'_nota': ('Distancia por ruta (km, redondeada a 5) entre la ciudad principal de cada región y la de cada región '
                        'vecina. Cálculo propio sobre la red de rutas de LINZ (Topo 1:250k); ver herramientas/distancias-nz.py.')}
    for iso, (nombre, g) in sorted(regiones.items()):
        vecinas = [v for v, (_, h) in regiones.items() if v != iso and g.distance(h) < 1000]
        o = principal[iso]
        filas = []
        for v in vecinas:
            dd = principal[v]
            km = distancia(grafo, cercano(o['lon'], o['lat']), cercano(dd['lon'], dd['lat']))
            filas.append({'region': regiones[v][0], 'iso': v, 'ciudad': dd['n'],
                          'km': round(km / 5000) * 5 if km else None})
        salida[iso] = {'ciudad': o['n'], 'vecinas': sorted(filas, key=lambda f: f['km'] or 9999)}
        print(f'  {nombre}: {o["n"]} -> ' + ', '.join(f'{f["ciudad"]} {f["km"]} km' for f in salida[iso]['vecinas']))
    (DATOS / 'distancias-regiones.json').write_text(json.dumps(salida, ensure_ascii=False, indent=1) + '\n')


if __name__ == '__main__':
    main()
