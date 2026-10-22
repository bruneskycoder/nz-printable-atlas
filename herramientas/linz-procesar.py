#!/usr/bin/env python3
"""Procesa las capas de LINZ para el mapa mural v2 (datos/nz/linz/).

    git fetch origin datos-linz
    python3 herramientas/linz-procesar.py

Las capas las baja la tarea de GitHub «Datos de LINZ» (ver linz-bajar.py) y
quedan en la rama datos-linz. Este script las lee de ahí con git, sin cambiar
de rama, y escribe en NZTM2000:
  - rutas.json: State Highways (1:250k), con su número (hway_num).
  - rios.json: los ríos de la topografía 1:250k que siguen a los ríos que ya
    mostraba el mural (Natural Earth elige cuáles; LINZ da el trazado exacto).
  - lagos.json: lagos de más de 2 km², con su nombre oficial.
  - nombres.json: el Gazetteer (NZGB) reducido a lo que usa el mural, y
    nombres-informe.txt: cada rótulo del mural comparado con el Gazetteer.

Requiere: Python con shapely.
"""
import gzip
import json
import subprocess
import unicodedata
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import linemerge, unary_union

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / 'datos' / 'nz' / 'linz'
RAMA = 'origin/datos-linz'


def leer(nombre):
    """FeatureCollection de la rama datos-linz."""
    crudo = subprocess.run(['git', '-C', str(RAIZ), 'show', f'{RAMA}:{nombre}'], check=True, capture_output=True).stdout
    return json.loads(gzip.decompress(crudo)) if nombre.endswith('.gz') else json.loads(crudo)


def escribir(nombre, feats):
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / nombre).write_text(json.dumps({'type': 'FeatureCollection', 'features': feats},
                                            ensure_ascii=False, separators=(',', ':')))
    print(f'  datos/nz/linz/{nombre}: {len(feats)} elementos, {(SALIDA / nombre).stat().st_size // 1024} KB')


def redondear(g):
    """GeoJSON con coordenadas al metro."""
    def r(c):
        return [round(c[0]), round(c[1])] if isinstance(c[0], (int, float)) else [r(x) for x in c]
    m = mapping(g)
    return {'type': m['type'], 'coordinates': r(m['coordinates'])}


def rutas():
    por_numero = {}
    for f in leer('rutas.geojson.gz')['features']:
        n = str(f['properties'].get('hway_num') or '').strip()
        if n and f['geometry']:
            por_numero.setdefault(n, []).append(shape(f['geometry']))
    feats = []
    for n, gs in sorted(por_numero.items(), key=lambda t: (len(t[0]), t[0])):
        g = linemerge(unary_union(gs)).simplify(100)
        feats.append({'type': 'Feature', 'properties': {'hway_num': n}, 'geometry': redondear(g)})
    escribir('rutas.json', feats)


def rios():
    ne = unary_union([shape(f['geometry']) for f in json.loads((RAIZ / 'datos' / 'nz' / 'rios.json').read_text())['features']])
    zona = ne.buffer(1500)
    elegidos = []
    for f in leer('rios.geojson.gz')['features']:
        if not f['geometry']:
            continue
        g = shape(f['geometry'])
        if zona.contains(g.interpolate(0.5, normalized=True)):
            elegidos.append(g)
    unidos = linemerge(unary_union(elegidos))
    partes = getattr(unidos, 'geoms', [unidos])
    # Fuera los pedacitos sueltos: afluentes que tocan la franja de 1,5 km
    largos = [p.simplify(100) for p in partes if p.length > 4000]
    escribir('rios.json', [{'type': 'Feature', 'properties': {}, 'geometry': redondear(unary_union(largos))}])


def lagos():
    feats = []
    for f in leer('lagos.geojson.gz')['features']:
        if not f['geometry']:
            continue
        g = shape(f['geometry'])
        if g.area < 2_000_000:
            continue
        p = f['properties']
        feats.append({'type': 'Feature', 'properties': {'nombre': p.get('macronated') == 'Y' and p.get('name') or p.get('name')},
                      'geometry': redondear(g.simplify(60))})
    escribir('lagos.json', feats)


def sin_macrones(t):
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn').lower().strip()


def nombres():
    """Gazetteer reducido: nombres oficiales con su tipo y posición."""
    feats = []
    for f in leer('nombres.geojson.gz')['features']:
        p = f['properties']
        if not p.get('name') or p.get('crd_latitude') is None:
            continue
        feats.append({'n': p['name'], 'tipo': p.get('feat_type'), 'estado': p.get('status'),
                      'lat': round(float(p['crd_latitude']), 5), 'lon': round(float(p['crd_longitude']), 5)})
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / 'nombres.json').write_text(json.dumps(feats, ensure_ascii=False, separators=(',', ':')))
    print(f'  datos/nz/linz/nombres.json: {len(feats)} nombres')
    return feats


def informe(gaz):
    """Compara cada rótulo del mural con el Gazetteer: grafía oficial (macrones, nombre doble) y posición."""
    import math
    indice = {}
    for g in gaz:
        for parte in [g['n']] + [x.strip() for x in g['n'].split('/')]:
            indice.setdefault(sin_macrones(parte), []).append(g)
    nz = RAIZ / 'datos' / 'nz'
    rotulos = []
    for c in json.loads((nz / 'lugares.json').read_text())['lugares']:
        rotulos.append(('lugar', c['n'], c['lon'], c['lat']))
    r = json.loads((nz / 'rotulos.json').read_text())
    for p in r['picos']:
        rotulos.append(('pico', p['n'], p['lon'], p['lat']))
    for x in r['rotulos']:
        rotulos.append(('rótulo', x['t'], x['lon'], x['lat']))
    lineas = []
    for clase, texto, lon, lat in rotulos:
        claves = [sin_macrones(texto)] + [sin_macrones(x) for x in texto.split('/')]
        cands = [g for k in claves for g in indice.get(k, [])]
        if not cands:
            lineas.append(f'SIN DATO   {clase:7s} {texto}')
            continue
        dist = lambda g: 111.2 * math.hypot((g['lon'] - lon) * math.cos(math.radians(lat)), g['lat'] - lat)
        mejor = min(cands, key=dist)
        d = dist(mejor)
        marca = 'IGUAL' if mejor['n'] == texto else 'DISTINTO'
        if d > 5:
            marca += ' LEJOS'
        lineas.append(f'{marca:10s} {clase:7s} {texto} -> {mejor["n"]} ({mejor["tipo"]}, {mejor["estado"]}) a {d:.1f} km')
    (SALIDA / 'nombres-informe.txt').write_text('\n'.join(lineas) + '\n')
    print(f'  datos/nz/linz/nombres-informe.txt: {len(lineas)} rótulos, '
          f'{sum(not l.startswith("IGUAL ") for l in lineas)} para revisar')


def main():
    manifiesto = leer('manifiesto.json')
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / 'manifiesto.json').write_text(json.dumps(manifiesto, ensure_ascii=False, indent=1) + '\n')
    rutas()
    rios()
    lagos()
    informe(nombres())


if __name__ == '__main__':
    main()
